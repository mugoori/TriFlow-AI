"""
Feedback Analyzer Service
피드백 데이터를 분석하여 규칙 개선점을 도출하고 새로운 규칙을 제안
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import FeedbackLog, ProposedRule, Ruleset, Tenant

logger = logging.getLogger(__name__)


class FeedbackPattern:
    """피드백 패턴 분석 결과"""
    def __init__(
        self,
        pattern_type: str,
        description: str,
        frequency: int,
        sample_feedbacks: List[dict],
        suggested_action: str,
        confidence: float,
    ):
        self.pattern_type = pattern_type
        self.description = description
        self.frequency = frequency
        self.sample_feedbacks = sample_feedbacks
        self.suggested_action = suggested_action
        self.confidence = confidence

    def to_dict(self) -> dict:
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "frequency": self.frequency,
            "sample_feedbacks": self.sample_feedbacks,
            "suggested_action": self.suggested_action,
            "confidence": self.confidence,
        }


class FeedbackAnalyzer:
    """피드백 분석기"""

    # 피드백 이유 카테고리 매핑
    FEEDBACK_REASONS = {
        "incorrect": "정보가 틀림",
        "incomplete": "정보가 부족함",
        "irrelevant": "관련 없는 답변",
        "unclear": "이해하기 어려움",
        "slow": "응답이 느림",
        "other": "기타",
    }

    # 센서 타입별 일반적인 임계값 범위
    SENSOR_THRESHOLDS = {
        "temperature": {"warning": 70, "critical": 85, "unit": "°C"},
        "pressure": {"warning": 8, "critical": 10, "unit": "bar"},
        "humidity": {"warning": 80, "critical": 90, "unit": "%"},
        "vibration": {"warning": 4, "critical": 5, "unit": "mm/s"},
        "flow_rate": {"warning": 80, "critical": 100, "unit": "L/min"},
        "defect_rate": {"warning": 3, "critical": 5, "unit": "%"},
    }

    def __init__(self, db: Session):
        self.db = db

    def analyze_feedback_patterns(
        self,
        days: int = 7,
        min_frequency: int = 2,
    ) -> List[FeedbackPattern]:
        """
        최근 피드백에서 패턴 분석

        Args:
            days: 분석할 기간 (일)
            min_frequency: 최소 빈도수

        Returns:
            발견된 패턴 목록
        """
        since = datetime.utcnow() - timedelta(days=days)

        # 부정적/수정 피드백만 조회
        feedbacks = self.db.query(FeedbackLog).filter(
            FeedbackLog.created_at >= since,
            FeedbackLog.feedback_type.in_(["negative", "correction"]),
            FeedbackLog.is_processed == False,
        ).order_by(desc(FeedbackLog.created_at)).all()

        if not feedbacks:
            return []

        patterns = []

        # 1. 에이전트별 부정적 피드백 분석
        agent_patterns = self._analyze_by_agent(feedbacks, min_frequency)
        patterns.extend(agent_patterns)

        # 2. 피드백 이유별 분석
        reason_patterns = self._analyze_by_reason(feedbacks, min_frequency)
        patterns.extend(reason_patterns)

        # 3. 수정 제안 패턴 분석
        correction_patterns = self._analyze_corrections(feedbacks)
        patterns.extend(correction_patterns)

        return patterns

    def _analyze_by_agent(
        self,
        feedbacks: List[FeedbackLog],
        min_frequency: int,
    ) -> List[FeedbackPattern]:
        """에이전트별 부정적 피드백 분석"""
        agent_counts: Dict[str, List[FeedbackLog]] = {}

        for fb in feedbacks:
            agent = fb.context_data.get("agent_type", "unknown") if fb.context_data else "unknown"
            if agent not in agent_counts:
                agent_counts[agent] = []
            agent_counts[agent].append(fb)

        patterns = []
        for agent, fbs in agent_counts.items():
            if len(fbs) >= min_frequency:
                patterns.append(FeedbackPattern(
                    pattern_type="agent_issue",
                    description=f"{agent} 에이전트에서 반복적인 부정적 피드백 발생",
                    frequency=len(fbs),
                    sample_feedbacks=[self._feedback_to_summary(fb) for fb in fbs[:3]],
                    suggested_action=f"{agent} 에이전트 프롬프트 또는 로직 개선 검토",
                    confidence=min(0.9, 0.5 + len(fbs) * 0.1),
                ))

        return patterns

    def _analyze_by_reason(
        self,
        feedbacks: List[FeedbackLog],
        min_frequency: int,
    ) -> List[FeedbackPattern]:
        """피드백 이유별 분석"""
        reason_counts: Dict[str, List[FeedbackLog]] = {}

        for fb in feedbacks:
            reason = None
            if fb.context_data:
                reason = fb.context_data.get("reason")
            if not reason:
                reason = "unspecified"

            if reason not in reason_counts:
                reason_counts[reason] = []
            reason_counts[reason].append(fb)

        patterns = []
        for reason, fbs in reason_counts.items():
            if len(fbs) >= min_frequency and reason != "unspecified":
                reason_desc = self.FEEDBACK_REASONS.get(reason, reason)
                patterns.append(FeedbackPattern(
                    pattern_type="reason_pattern",
                    description=f"'{reason_desc}' 이유의 피드백이 반복됨",
                    frequency=len(fbs),
                    sample_feedbacks=[self._feedback_to_summary(fb) for fb in fbs[:3]],
                    suggested_action=self._suggest_action_for_reason(reason),
                    confidence=min(0.85, 0.4 + len(fbs) * 0.15),
                ))

        return patterns

    def _analyze_corrections(
        self,
        feedbacks: List[FeedbackLog],
    ) -> List[FeedbackPattern]:
        """수정 제안 피드백 분석"""
        corrections = [fb for fb in feedbacks if fb.feedback_type == "correction" and fb.corrected_output]

        if not corrections:
            return []

        patterns = []

        # 수정 제안에서 임계값 관련 패턴 탐지
        threshold_corrections = []
        for fb in corrections:
            corrected = fb.corrected_output
            if isinstance(corrected, dict):
                text = corrected.get("text", "")
            else:
                text = str(corrected)

            # 숫자 + 단위 패턴 탐지 (임계값 수정 가능성)
            if any(unit in text.lower() for unit in ["°c", "bar", "%", "mm/s"]):
                threshold_corrections.append(fb)

        if threshold_corrections:
            patterns.append(FeedbackPattern(
                pattern_type="threshold_adjustment",
                description="사용자가 임계값 관련 수정을 제안함",
                frequency=len(threshold_corrections),
                sample_feedbacks=[self._feedback_to_summary(fb) for fb in threshold_corrections[:3]],
                suggested_action="현재 룰셋의 임계값 검토 및 조정 필요",
                confidence=0.75,
            ))

        return patterns

    def _feedback_to_summary(self, fb: FeedbackLog) -> dict:
        """피드백을 요약 딕셔너리로 변환"""
        return {
            "feedback_id": str(fb.feedback_id),
            "type": fb.feedback_type,
            "text": fb.feedback_text[:100] if fb.feedback_text else None,
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
        }

    def _suggest_action_for_reason(self, reason: str) -> str:
        """이유별 개선 액션 제안"""
        suggestions = {
            "incorrect": "데이터 소스 검증 및 응답 정확도 개선",
            "incomplete": "응답에 더 상세한 정보 포함하도록 프롬프트 개선",
            "irrelevant": "의도 분류 로직 개선 및 라우팅 정확도 향상",
            "unclear": "응답 형식을 더 명확하고 구조화된 형태로 개선",
            "slow": "응답 시간 최적화 (캐싱, 쿼리 최적화)",
        }
        return suggestions.get(reason, "피드백 내용 검토 후 개선 방안 수립")

    def generate_rule_proposals(
        self,
        patterns: List[FeedbackPattern],
        tenant_id: UUID,
    ) -> List[ProposedRule]:
        """
        분석된 패턴을 기반으로 규칙 제안 생성

        Args:
            patterns: 분석된 패턴 목록
            tenant_id: 테넌트 ID

        Returns:
            생성된 ProposedRule 목록
        """
        proposals = []

        for pattern in patterns:
            # 임계값 조정 패턴인 경우 새 룰셋 제안
            if pattern.pattern_type == "threshold_adjustment":
                proposal = self._create_threshold_proposal(pattern, tenant_id)
                if proposal:
                    proposals.append(proposal)

            # 에이전트 이슈 패턴인 경우 개선 규칙 제안
            elif pattern.pattern_type == "agent_issue":
                proposal = self._create_agent_improvement_proposal(pattern, tenant_id)
                if proposal:
                    proposals.append(proposal)

        return proposals

    def _create_threshold_proposal(
        self,
        pattern: FeedbackPattern,
        tenant_id: UUID,
    ) -> Optional[ProposedRule]:
        """임계값 조정 규칙 제안 생성"""
        # 샘플 피드백에서 센서 타입 추출 시도
        sensor_type = "temperature"  # 기본값

        for sample in pattern.sample_feedbacks:
            text = sample.get("text", "") or ""
            for stype in self.SENSOR_THRESHOLDS.keys():
                if stype in text.lower():
                    sensor_type = stype
                    break

        thresholds = self.SENSOR_THRESHOLDS.get(sensor_type, self.SENSOR_THRESHOLDS["temperature"])

        # Rhai 스크립트 생성
        rhai_script = f'''// 피드백 기반 자동 생성 규칙
// 생성일: {datetime.utcnow().isoformat()}
// 근거: 사용자 피드백 {pattern.frequency}건 분석

let sensor_type = "{sensor_type}";
let warning_threshold = {thresholds["warning"]};
let critical_threshold = {thresholds["critical"]};

if input.sensor_type == sensor_type {{
    if input.value >= critical_threshold {{
        #{{"level": "critical", "action": "stop_line", "message": sensor_type + " 위험 수준 도달"}}
    }} else if input.value >= warning_threshold {{
        #{{"level": "warning", "action": "notification", "message": sensor_type + " 경고 수준"}}
    }} else {{
        #{{"level": "normal", "action": "log", "message": sensor_type + " 정상"}}
    }}
}} else {{
    #{{"level": "skip", "action": "none", "message": "해당 없음"}}
}}
'''

        proposal = ProposedRule(
            proposal_id=uuid4(),
            tenant_id=tenant_id,
            rule_name=f"{sensor_type}_threshold_adjusted",
            rule_description=f"피드백 분석 기반 {sensor_type} 임계값 조정 규칙 (피드백 {pattern.frequency}건 분석)",
            rhai_script=rhai_script,
            source_type="feedback_analysis",
            source_data=pattern.to_dict(),
            confidence=pattern.confidence,
            status="pending",
        )

        return proposal

    def _create_agent_improvement_proposal(
        self,
        pattern: FeedbackPattern,
        tenant_id: UUID,
    ) -> Optional[ProposedRule]:
        """에이전트 개선 규칙 제안 생성"""
        agent_type = "unknown"
        for sample in pattern.sample_feedbacks:
            # context에서 agent_type 추출 시도
            pass  # 실제로는 원본 피드백에서 추출

        rhai_script = f'''// 에이전트 응답 품질 개선 규칙
// 생성일: {datetime.utcnow().isoformat()}
// 근거: 부정적 피드백 {pattern.frequency}건

// 이 규칙은 에이전트 응답 전에 입력을 검증합니다
let requires_validation = true;

if requires_validation {{
    // 입력 데이터 완전성 검사
    if input.data == () || input.data == "" {{
        #{{"action": "request_more_info", "message": "추가 정보 필요"}}
    }} else {{
        #{{"action": "proceed", "message": "처리 진행"}}
    }}
}} else {{
    #{{"action": "proceed", "message": "검증 스킵"}}
}}
'''

        proposal = ProposedRule(
            proposal_id=uuid4(),
            tenant_id=tenant_id,
            rule_name="agent_quality_check",
            rule_description=f"에이전트 응답 품질 검증 규칙 (피드백 {pattern.frequency}건 분석)",
            rhai_script=rhai_script,
            source_type="feedback_analysis",
            source_data=pattern.to_dict(),
            confidence=pattern.confidence * 0.8,  # 에이전트 개선은 좀 더 낮은 신뢰도
            status="pending",
        )

        return proposal

    def save_proposals(self, proposals: List[ProposedRule]) -> List[ProposedRule]:
        """제안된 규칙을 DB에 저장"""
        saved = []
        for proposal in proposals:
            # 중복 체크 (같은 이름의 pending 제안이 있는지)
            existing = self.db.query(ProposedRule).filter(
                ProposedRule.rule_name == proposal.rule_name,
                ProposedRule.status == "pending",
            ).first()

            if not existing:
                self.db.add(proposal)
                saved.append(proposal)
                logger.info(f"New rule proposal saved: {proposal.rule_name}")
            else:
                logger.info(f"Skipped duplicate proposal: {proposal.rule_name}")

        if saved:
            self.db.commit()
            for p in saved:
                self.db.refresh(p)

        return saved

    def approve_proposal(
        self,
        proposal_id: UUID,
        user_id: Optional[UUID] = None,
        comment: Optional[str] = None,
    ) -> Optional[Ruleset]:
        """
        제안된 규칙을 승인하고 실제 룰셋으로 변환

        Args:
            proposal_id: 제안 ID
            user_id: 승인자 ID
            comment: 승인 코멘트

        Returns:
            생성된 Ruleset 또는 None
        """
        try:
            proposal = self.db.query(ProposedRule).filter(
                ProposedRule.proposal_id == proposal_id
            ).first()

            if not proposal:
                logger.error(f"Proposal not found: {proposal_id}")
                return None

            if proposal.status != "pending":
                logger.warning(f"Proposal already processed: {proposal_id}")
                return None

            # 동일한 이름의 룰셋이 이미 존재하는지 확인
            existing_ruleset = self.db.query(Ruleset).filter(
                Ruleset.tenant_id == proposal.tenant_id,
                Ruleset.name == proposal.rule_name,
            ).first()

            # 이름 중복 시 타임스탬프 추가
            ruleset_name = proposal.rule_name
            if existing_ruleset:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                ruleset_name = f"{proposal.rule_name}_{timestamp}"
                logger.info(f"Ruleset name conflict, using: {ruleset_name}")

            # 새 룰셋 생성
            ruleset = Ruleset(
                ruleset_id=uuid4(),
                tenant_id=proposal.tenant_id,
                name=ruleset_name,
                description=f"[자동 생성] {proposal.rule_description}",
                rhai_script=proposal.rhai_script,
                version="1.0.0",
                is_active=True,
                created_by=user_id,
                ruleset_metadata={"source": "proposal", "proposal_id": str(proposal_id)},
            )

            self.db.add(ruleset)

            # 제안 상태 업데이트
            proposal.status = "deployed"
            proposal.reviewed_by = user_id
            proposal.reviewed_at = datetime.utcnow()
            proposal.review_comment = comment or "자동 승인 및 배포"

            self.db.commit()
            self.db.refresh(ruleset)

            logger.info(f"Proposal {proposal_id} approved and deployed as ruleset {ruleset.ruleset_id}")

            return ruleset

        except Exception as e:
            logger.error(f"Failed to approve proposal {proposal_id}: {e}")
            self.db.rollback()
            raise

    def reject_proposal(
        self,
        proposal_id: UUID,
        user_id: Optional[UUID] = None,
        comment: Optional[str] = None,
    ) -> bool:
        """제안된 규칙 거절"""
        proposal = self.db.query(ProposedRule).filter(
            ProposedRule.proposal_id == proposal_id
        ).first()

        if not proposal:
            return False

        proposal.status = "rejected"
        proposal.reviewed_by = user_id
        proposal.reviewed_at = datetime.utcnow()
        proposal.review_comment = comment or "거절됨"

        self.db.commit()

        logger.info(f"Proposal {proposal_id} rejected")

        return True


def run_feedback_analysis(db: Session) -> Dict[str, Any]:
    """
    피드백 분석 실행 (스케줄러나 수동 호출용)

    Returns:
        분석 결과 요약
    """
    analyzer = FeedbackAnalyzer(db)

    # 패턴 분석
    patterns = analyzer.analyze_feedback_patterns(days=7, min_frequency=2)

    if not patterns:
        return {
            "status": "no_patterns",
            "message": "분석할 피드백 패턴이 없습니다",
            "patterns_found": 0,
            "proposals_created": 0,
        }

    # 테넌트 조회
    tenant = db.query(Tenant).first()
    if not tenant:
        return {
            "status": "error",
            "message": "테넌트를 찾을 수 없습니다",
            "patterns_found": len(patterns),
            "proposals_created": 0,
        }

    # 규칙 제안 생성
    proposals = analyzer.generate_rule_proposals(patterns, tenant.tenant_id)

    # 저장
    saved = analyzer.save_proposals(proposals)

    return {
        "status": "success",
        "message": f"{len(patterns)}개 패턴 발견, {len(saved)}개 규칙 제안 생성",
        "patterns_found": len(patterns),
        "proposals_created": len(saved),
        "patterns": [p.to_dict() for p in patterns],
        "proposal_ids": [str(p.proposal_id) for p in saved],
    }
