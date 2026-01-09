# -*- coding: utf-8 -*-
"""Rule Extraction Service

Decision Tree 기반 규칙 추출 서비스.

주요 기능:
- 승인된 샘플에서 Decision Tree 학습
- Decision Tree → Rhai 스크립트 변환
- 성능 메트릭 계산 (coverage, precision, recall, f1)
- AutoRuleCandidate 생성 및 관리

LRN-FR-030 스펙 참조
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Any
from uuid import UUID

import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score as sklearn_f1_score,
    accuracy_score,
)
from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session

from app.models import Sample, AutoRuleCandidate, ProposedRule
from app.schemas.rule_extraction import (
    RuleExtractionRequest,
    ExtractionMetrics,
    TestSample,
)
from app.tools.rhai import RhaiEngine

logger = logging.getLogger(__name__)


class RuleExtractionService:
    """Decision Tree 기반 규칙 추출 서비스"""

    # 지원하는 특징 필드
    SUPPORTED_FEATURES = [
        "temperature",
        "pressure",
        "humidity",
        "defect_rate",
        "speed",
        "voltage",
        "current",
        "vibration",
        "noise_level",
        "cycle_time",
    ]

    # 분류 클래스
    CLASS_NAMES = ["NORMAL", "WARNING", "CRITICAL"]

    def __init__(self, db: Session):
        self.db = db
        self.rhai_engine = RhaiEngine()

    # ============================================
    # 규칙 추출
    # ============================================

    def extract_rules(
        self,
        tenant_id: UUID,
        request: RuleExtractionRequest,
    ) -> tuple[AutoRuleCandidate, ExtractionMetrics, dict[str, float]]:
        """
        승인된 샘플에서 Decision Tree 학습 후 Rhai 규칙 생성

        Args:
            tenant_id: 테넌트 ID
            request: 추출 요청

        Returns:
            (AutoRuleCandidate, ExtractionMetrics, feature_importance)
        """
        # 1. 샘플 조회
        samples = self._get_approved_samples(
            tenant_id=tenant_id,
            category=request.category,
            min_quality_score=request.min_quality_score,
        )

        if len(samples) < request.min_samples:
            raise ValueError(
                f"샘플이 부족합니다. 필요: {request.min_samples}, 현재: {len(samples)}"
            )

        # 2. 학습 데이터 준비
        X, y, feature_names = self._prepare_training_data(samples)

        if len(np.unique(y)) < 2:
            raise ValueError("최소 2개 이상의 클래스가 필요합니다")

        # 3. Decision Tree 학습
        tree = self._train_decision_tree(
            X=X,
            y=y,
            max_depth=request.max_depth,
            class_weight=request.class_weight,
        )

        # 4. Rhai 코드 생성
        class_names = [self.CLASS_NAMES[int(c)] for c in np.unique(y)]
        rhai_code = self._convert_tree_to_rhai(
            tree=tree,
            feature_names=feature_names,
            class_names=class_names,
            samples_count=len(samples),
        )

        # 5. 성능 메트릭 계산
        metrics = self._calculate_metrics(tree, X, y)

        # 6. 특징 중요도
        feature_importance = {
            feature_names[i]: float(tree.feature_importances_[i])
            for i in range(len(feature_names))
        }

        # 7. AutoRuleCandidate 저장
        candidate = AutoRuleCandidate(
            tenant_id=tenant_id,
            generated_rule=rhai_code,
            rule_language="rhai",
            generation_method="pattern_mining",
            coverage=metrics.coverage,
            precision=metrics.precision,
            recall=metrics.recall,
            f1_score=metrics.f1_score,
            approval_status="pending",
            candidate_metadata={
                "samples_used": len(samples),
                "tree_depth": tree.get_depth(),
                "feature_count": len(feature_names),
                "feature_names": feature_names,
                "class_names": class_names,
                "category": request.category,
                "min_quality_score": request.min_quality_score,
                "accuracy": metrics.accuracy,
            },
        )

        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)

        logger.info(
            f"Created rule candidate {candidate.candidate_id} "
            f"from {len(samples)} samples (F1: {metrics.f1_score:.3f})"
        )

        return candidate, metrics, feature_importance

    def _get_approved_samples(
        self,
        tenant_id: UUID,
        category: Optional[str] = None,
        min_quality_score: float = 0.7,
    ) -> list[Sample]:
        """승인된 고품질 샘플 조회"""
        query = self.db.query(Sample).filter(
            and_(
                Sample.tenant_id == tenant_id,
                Sample.status == "approved",
                Sample.quality_score >= min_quality_score,
            )
        )

        if category:
            query = query.filter(Sample.category == category)

        return query.order_by(desc(Sample.quality_score)).all()

    def _prepare_training_data(
        self,
        samples: list[Sample],
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """샘플에서 학습 데이터 추출"""
        # 사용 가능한 특징 필드 식별
        feature_names = []
        for feature in self.SUPPORTED_FEATURES:
            # 첫 번째 샘플에서 특징 존재 여부 확인
            if samples and feature in (samples[0].input_data or {}):
                feature_names.append(feature)

        if not feature_names:
            raise ValueError("학습에 사용할 특징이 없습니다")

        # 특징 행렬 X 구성
        X = []
        y = []

        for sample in samples:
            input_data = sample.input_data or {}
            expected = sample.expected_output or {}

            # 특징 추출
            features = []
            valid = True
            for feature in feature_names:
                value = input_data.get(feature)
                if value is not None:
                    try:
                        features.append(float(value))
                    except (TypeError, ValueError):
                        valid = False
                        break
                else:
                    valid = False
                    break

            if not valid:
                continue

            # 라벨 추출
            status = expected.get("status") or expected.get("result", "NORMAL")
            if status in self.CLASS_NAMES:
                label = self.CLASS_NAMES.index(status)
            else:
                label = 0  # 기본값 NORMAL

            X.append(features)
            y.append(label)

        if len(X) < 10:
            raise ValueError(f"유효한 샘플이 부족합니다: {len(X)}개")

        return np.array(X), np.array(y), feature_names

    def _train_decision_tree(
        self,
        X: np.ndarray,
        y: np.ndarray,
        max_depth: int = 5,
        class_weight: Optional[str] = None,
    ) -> DecisionTreeClassifier:
        """Decision Tree 학습"""
        tree = DecisionTreeClassifier(
            max_depth=max_depth,
            min_samples_split=5,
            min_samples_leaf=2,
            criterion="gini",
            class_weight=class_weight,
            random_state=42,
        )
        tree.fit(X, y)
        return tree

    # ============================================
    # Rhai 변환
    # ============================================

    def _convert_tree_to_rhai(
        self,
        tree: DecisionTreeClassifier,
        feature_names: list[str],
        class_names: list[str],
        samples_count: int,
    ) -> str:
        """Decision Tree → Rhai 스크립트 변환"""
        tree_structure = tree.tree_

        # 헤더 주석
        header = f"""// Auto-generated rule from Decision Tree
// Generated at: {datetime.utcnow().isoformat()}
// Samples: {samples_count}
// Depth: {tree.get_depth()}
// Features: {', '.join(feature_names)}

"""

        # 재귀적으로 트리 변환
        body = self._tree_to_rhai_recursive(
            tree=tree_structure,
            node_id=0,
            feature_names=feature_names,
            class_names=class_names,
            indent=1,
        )

        # 함수 래핑
        rhai_code = header + f"""fn check(input) {{
{body}
}}

check(input)
"""

        return rhai_code

    def _tree_to_rhai_recursive(
        self,
        tree,
        node_id: int,
        feature_names: list[str],
        class_names: list[str],
        indent: int = 0,
    ) -> str:
        """재귀적 트리 순회 → Rhai if-else 생성"""
        indent_str = "    " * indent

        # Leaf node 확인 (children_left[i] == children_right[i] == TREE_LEAF)
        if tree.children_left[node_id] == tree.children_right[node_id]:
            # Leaf node
            class_idx = int(np.argmax(tree.value[node_id]))
            total = tree.value[node_id].sum()
            confidence = tree.value[node_id][0][class_idx] / total if total > 0 else 0

            # 클래스 이름 결정
            if class_idx < len(class_names):
                status = class_names[class_idx]
            else:
                status = "NORMAL"

            return f'{indent_str}#{{ status: "{status}", confidence: {confidence:.2f} }}'

        # Internal node
        feature_idx = tree.feature[node_id]
        threshold = tree.threshold[node_id]

        if feature_idx < len(feature_names):
            feature = feature_names[feature_idx]
        else:
            feature = f"feature_{feature_idx}"

        # 왼쪽 자식 (<=)
        left = self._tree_to_rhai_recursive(
            tree=tree,
            node_id=tree.children_left[node_id],
            feature_names=feature_names,
            class_names=class_names,
            indent=indent + 1,
        )

        # 오른쪽 자식 (>)
        right = self._tree_to_rhai_recursive(
            tree=tree,
            node_id=tree.children_right[node_id],
            feature_names=feature_names,
            class_names=class_names,
            indent=indent + 1,
        )

        return f"""{indent_str}if input.{feature} <= {threshold:.2f} {{
{left}
{indent_str}}} else {{
{right}
{indent_str}}}"""

    # ============================================
    # 성능 메트릭
    # ============================================

    def _calculate_metrics(
        self,
        tree: DecisionTreeClassifier,
        X: np.ndarray,
        y: np.ndarray,
    ) -> ExtractionMetrics:
        """성능 메트릭 계산"""
        y_pred = tree.predict(X)

        # 다중 클래스 지원을 위해 macro average 사용
        precision = precision_score(y, y_pred, average="macro", zero_division=0)
        recall = recall_score(y, y_pred, average="macro", zero_division=0)
        f1 = sklearn_f1_score(y, y_pred, average="macro", zero_division=0)
        accuracy = accuracy_score(y, y_pred)

        # Coverage: 학습 데이터 중 정확히 예측한 비율
        coverage = accuracy

        return ExtractionMetrics(
            coverage=float(coverage),
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            accuracy=float(accuracy),
        )

    # ============================================
    # 후보 관리
    # ============================================

    def get_candidate(self, candidate_id: UUID) -> Optional[AutoRuleCandidate]:
        """후보 조회"""
        return self.db.query(AutoRuleCandidate).filter(
            AutoRuleCandidate.candidate_id == candidate_id
        ).first()

    def list_candidates(
        self,
        tenant_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AutoRuleCandidate], int]:
        """후보 목록 조회"""
        query = self.db.query(AutoRuleCandidate).filter(
            AutoRuleCandidate.tenant_id == tenant_id
        )

        if status:
            query = query.filter(AutoRuleCandidate.approval_status == status)

        total = query.count()
        candidates = query.order_by(
            desc(AutoRuleCandidate.created_at)
        ).offset((page - 1) * page_size).limit(page_size).all()

        return candidates, total

    def delete_candidate(self, candidate_id: UUID) -> bool:
        """후보 삭제"""
        candidate = self.get_candidate(candidate_id)
        if not candidate:
            return False

        self.db.delete(candidate)
        self.db.commit()

        logger.info(f"Deleted rule candidate: {candidate_id}")
        return True

    def approve_candidate(
        self,
        candidate_id: UUID,
        approver_id: UUID,
        rule_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ProposedRule:
        """후보 승인 → ProposedRule 생성"""
        candidate = self.get_candidate(candidate_id)
        if not candidate:
            raise ValueError("후보를 찾을 수 없습니다")

        if candidate.approval_status != "pending" and candidate.approval_status != "testing":
            raise ValueError(f"승인할 수 없는 상태입니다: {candidate.approval_status}")

        # 후보 상태 업데이트
        candidate.approval_status = "approved"
        candidate.is_approved = True
        candidate.approver_id = approver_id
        candidate.approved_at = datetime.utcnow()

        # ProposedRule 생성
        if not rule_name:
            rule_name = f"Auto-Rule-{candidate.candidate_id.hex[:8]}"

        proposal = ProposedRule(
            tenant_id=candidate.tenant_id,
            rule_name=rule_name,
            rhai_script=candidate.generated_rule,
            description=description or "Decision Tree 기반 자동 생성 규칙",
            source_type="pattern_detection",
            confidence=candidate.f1_score or 0.5,
            status="pending",
            context_data={
                "candidate_id": str(candidate.candidate_id),
                "generation_method": candidate.generation_method,
                "coverage": candidate.coverage,
                "precision": candidate.precision,
                "recall": candidate.recall,
                "f1_score": candidate.f1_score,
            },
        )

        self.db.add(proposal)
        self.db.commit()
        self.db.refresh(proposal)

        logger.info(
            f"Approved candidate {candidate_id} → ProposedRule {proposal.proposal_id}"
        )

        return proposal

    def reject_candidate(
        self,
        candidate_id: UUID,
        reason: str,
    ) -> AutoRuleCandidate:
        """후보 거절"""
        candidate = self.get_candidate(candidate_id)
        if not candidate:
            raise ValueError("후보를 찾을 수 없습니다")

        candidate.approval_status = "rejected"
        candidate.rejection_reason = reason

        self.db.commit()
        self.db.refresh(candidate)

        logger.info(f"Rejected rule candidate: {candidate_id}")
        return candidate

    # ============================================
    # 테스트
    # ============================================

    def test_candidate(
        self,
        candidate_id: UUID,
        test_samples: list[TestSample],
    ) -> dict[str, Any]:
        """후보 규칙 테스트 실행"""
        import time

        candidate = self.get_candidate(candidate_id)
        if not candidate:
            raise ValueError("후보를 찾을 수 없습니다")

        # 테스트 상태로 변경
        if candidate.approval_status == "pending":
            candidate.approval_status = "testing"

        start_time = time.time()
        results = []
        passed = 0
        failed = 0

        for idx, sample in enumerate(test_samples):
            try:
                # Rhai 스크립트 실행
                context = {"input": sample.input}
                result = self.rhai_engine.execute(
                    script=candidate.generated_rule,
                    context=context,
                )

                # 결과 비교
                actual_status = result.get("status", "UNKNOWN")
                expected_status = sample.expected.get("status", "NORMAL")

                is_passed = actual_status == expected_status

                if is_passed:
                    passed += 1
                else:
                    failed += 1

                results.append({
                    "sample_index": idx,
                    "input": sample.input,
                    "expected": sample.expected,
                    "actual": result,
                    "passed": is_passed,
                    "error": None,
                })

            except Exception as e:
                failed += 1
                results.append({
                    "sample_index": idx,
                    "input": sample.input,
                    "expected": sample.expected,
                    "actual": {},
                    "passed": False,
                    "error": str(e),
                })

        execution_time_ms = (time.time() - start_time) * 1000
        total = len(test_samples)
        accuracy = passed / total if total > 0 else 0

        # 테스트 결과 저장
        candidate.test_results = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "accuracy": accuracy,
            "execution_time_ms": execution_time_ms,
            "tested_at": datetime.utcnow().isoformat(),
        }
        self.db.commit()

        logger.info(
            f"Tested candidate {candidate_id}: {passed}/{total} passed ({accuracy:.1%})"
        )

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "accuracy": accuracy,
            "execution_time_ms": execution_time_ms,
            "details": results,
        }

    # ============================================
    # 통계
    # ============================================

    def get_stats(self, tenant_id: UUID) -> dict[str, Any]:
        """추출 통계"""
        # 상태별 카운트
        status_counts = self.db.query(
            AutoRuleCandidate.approval_status,
            func.count(AutoRuleCandidate.candidate_id),
        ).filter(
            AutoRuleCandidate.tenant_id == tenant_id
        ).group_by(
            AutoRuleCandidate.approval_status
        ).all()

        status_dict = {status: count for status, count in status_counts}
        total = sum(status_dict.values())

        # 평균 메트릭
        avg_metrics = self.db.query(
            func.avg(AutoRuleCandidate.f1_score),
            func.avg(AutoRuleCandidate.coverage),
        ).filter(
            AutoRuleCandidate.tenant_id == tenant_id
        ).first()

        # 최근 7일 추출 횟수
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_count = self.db.query(func.count(AutoRuleCandidate.candidate_id)).filter(
            and_(
                AutoRuleCandidate.tenant_id == tenant_id,
                AutoRuleCandidate.created_at >= week_ago,
            )
        ).scalar() or 0

        # 카테고리별 (메타데이터에서)
        candidates = self.db.query(AutoRuleCandidate).filter(
            AutoRuleCandidate.tenant_id == tenant_id
        ).all()

        by_category: dict[str, int] = {}
        for c in candidates:
            meta = c.candidate_metadata or {}
            cat = meta.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_candidates": total,
            "pending_count": status_dict.get("pending", 0),
            "approved_count": status_dict.get("approved", 0),
            "rejected_count": status_dict.get("rejected", 0),
            "testing_count": status_dict.get("testing", 0),
            "avg_f1_score": float(avg_metrics[0] or 0),
            "avg_coverage": float(avg_metrics[1] or 0),
            "recent_extractions": recent_count,
            "by_category": by_category,
        }
