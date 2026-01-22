"""
Judgment Replay Service
과거 판단 실행을 재실행하여 결과 비교 및 디버깅 지원

스펙 참조: A-2-1 JUD-FR-070
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models import JudgmentExecution, Ruleset
from app.agents.judgment_agent import JudgmentAgent

logger = logging.getLogger(__name__)


class JudgmentReplayService:
    """Judgment Replay 서비스"""

    def __init__(self, db: Session):
        self.db = db

    async def replay_execution(
        self,
        execution_id: UUID,
        use_current_ruleset: bool = True,
        ruleset_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        단일 Judgment Execution 재실행

        Args:
            execution_id: 재실행할 execution ID
            use_current_ruleset: True면 현재 활성 Ruleset 사용, False면 원본 Ruleset
            ruleset_version: 특정 룰셋 버전 지정 (선택)

        Returns:
            {
                "original": {...},  # 원본 실행 결과
                "replay": {...},    # 재실행 결과
                "comparison": {...}, # 비교 결과
            }
        """
        # 1. 원본 execution 조회
        original_execution = self.db.query(JudgmentExecution).get(execution_id)

        if not original_execution:
            raise ValueError(f"Execution {execution_id} not found")

        logger.info(
            f"Replaying execution: {execution_id} "
            f"(original result: {original_execution.result})"
        )

        # 2. 재실행할 Ruleset 결정
        if ruleset_version:
            # 특정 버전 사용
            ruleset = self.db.query(Ruleset).filter(
                and_(
                    Ruleset.ruleset_id == original_execution.ruleset_id,
                    Ruleset.version == ruleset_version
                )
            ).first()
        elif use_current_ruleset:
            # 현재 활성 Ruleset 사용
            ruleset = self.db.query(Ruleset).filter(
                and_(
                    Ruleset.ruleset_id == original_execution.ruleset_id,
                    Ruleset.is_active == True
                )
            ).first()
        else:
            # 원본과 동일한 Ruleset 사용
            ruleset = self.db.query(Ruleset).get(original_execution.ruleset_id)

        if not ruleset:
            raise ValueError(f"Ruleset not found")

        # 3. Judgment Agent로 재실행
        agent = JudgmentAgent()

        replay_result = await agent.execute_tool({
            "ruleset_id": str(ruleset.ruleset_id),
            "input_data": original_execution.input_data,
            "workflow_id": str(original_execution.workflow_id) if original_execution.workflow_id else None,
        })

        # 4. 결과 비교
        comparison = self._compare_results(
            original={
                "result": original_execution.result,
                "confidence": original_execution.confidence,
                "method_used": original_execution.method_used,
                "explanation": original_execution.explanation,
            },
            replay=replay_result,
            ruleset_changed=(ruleset.version != self._get_original_ruleset_version(original_execution))
        )

        # 5. 응답 구성
        return {
            "execution_id": str(execution_id),
            "original": {
                "execution_id": str(original_execution.execution_id),
                "result": original_execution.result,
                "confidence": original_execution.confidence,
                "method_used": original_execution.method_used,
                "explanation": original_execution.explanation,
                "executed_at": original_execution.created_at.isoformat() if original_execution.created_at else None,
                "ruleset_id": str(original_execution.ruleset_id) if original_execution.ruleset_id else None,
            },
            "replay": {
                "result": replay_result.get("result"),
                "confidence": replay_result.get("confidence"),
                "method_used": replay_result.get("method_used"),
                "explanation": replay_result.get("explanation"),
                "replayed_at": datetime.utcnow().isoformat(),
                "ruleset_id": str(ruleset.ruleset_id),
                "ruleset_version": ruleset.version,
            },
            "comparison": comparison,
        }

    async def replay_batch(
        self,
        execution_ids: List[UUID],
        use_current_ruleset: bool = True,
    ) -> Dict[str, Any]:
        """
        여러 Judgment Execution 일괄 재실행

        Args:
            execution_ids: 재실행할 execution ID 목록
            use_current_ruleset: 현재 활성 Ruleset 사용 여부

        Returns:
            {
                "total": int,
                "changed": int,  # 결과가 바뀐 개수
                "unchanged": int,
                "failed": int,
                "results": List[dict],
                "summary": {...}
            }
        """
        results = []
        changed_count = 0
        unchanged_count = 0
        failed_count = 0

        for execution_id in execution_ids:
            try:
                replay_result = await self.replay_execution(
                    execution_id=execution_id,
                    use_current_ruleset=use_current_ruleset
                )

                results.append(replay_result)

                if replay_result["comparison"]["result_changed"]:
                    changed_count += 1
                else:
                    unchanged_count += 1

            except Exception as e:
                logger.error(f"Failed to replay {execution_id}: {e}")
                failed_count += 1
                results.append({
                    "execution_id": str(execution_id),
                    "error": str(e),
                    "status": "failed"
                })

        # 통계 분석
        summary = self._analyze_batch_results(results)

        return {
            "total": len(execution_ids),
            "changed": changed_count,
            "unchanged": unchanged_count,
            "failed": failed_count,
            "change_rate": round(changed_count / len(execution_ids) * 100, 2) if execution_ids else 0,
            "results": results,
            "summary": summary,
        }

    async def what_if_analysis(
        self,
        execution_id: UUID,
        input_modifications: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        What-If 분석: 입력 데이터 변경 시 결과 예측

        Args:
            execution_id: 기준 execution ID
            input_modifications: 변경할 입력 값 {"temperature": 85, "pressure": 120}

        Returns:
            원본과 변경 후 결과 비교
        """
        # 1. 원본 execution 조회
        original = self.db.query(JudgmentExecution).get(execution_id)

        if not original:
            raise ValueError(f"Execution {execution_id} not found")

        # 2. 입력 데이터 변경
        modified_input = {**original.input_data, **input_modifications}

        # 3. 변경된 입력으로 재실행
        agent = JudgmentAgent()

        what_if_result = await agent.execute_tool({
            "ruleset_id": str(original.ruleset_id),
            "input_data": modified_input,
        })

        # 4. 결과 비교
        return {
            "execution_id": str(execution_id),
            "original_input": original.input_data,
            "modified_input": modified_input,
            "modifications": input_modifications,
            "original_result": {
                "result": original.result,
                "confidence": original.confidence,
            },
            "what_if_result": {
                "result": what_if_result.get("result"),
                "confidence": what_if_result.get("confidence"),
            },
            "impact": {
                "result_changed": original.result != what_if_result.get("result"),
                "confidence_change": (what_if_result.get("confidence", 0) - (original.confidence or 0)),
            }
        }

    def _compare_results(
        self,
        original: Dict[str, Any],
        replay: Dict[str, Any],
        ruleset_changed: bool
    ) -> Dict[str, Any]:
        """
        원본과 재실행 결과 비교

        Args:
            original: 원본 실행 결과
            replay: 재실행 결과
            ruleset_changed: Ruleset 버전 변경 여부

        Returns:
            비교 결과
        """
        result_changed = original.get("result") != replay.get("result")
        confidence_diff = (replay.get("confidence", 0) - (original.get("confidence") or 0))
        method_changed = original.get("method_used") != replay.get("method_used")

        # 변경 사유 분석
        change_reasons = []
        if ruleset_changed:
            change_reasons.append("ruleset_version_changed")
        if result_changed:
            change_reasons.append("result_different")
        if abs(confidence_diff) > 0.1:
            change_reasons.append("confidence_significantly_different")
        if method_changed:
            change_reasons.append("method_changed")

        return {
            "result_changed": result_changed,
            "result_change": {
                "from": original.get("result"),
                "to": replay.get("result"),
            } if result_changed else None,
            "confidence_changed": abs(confidence_diff) > 0.01,
            "confidence_diff": round(confidence_diff, 4),
            "method_changed": method_changed,
            "method_change": {
                "from": original.get("method_used"),
                "to": replay.get("method_used"),
            } if method_changed else None,
            "ruleset_changed": ruleset_changed,
            "change_reasons": change_reasons,
        }

    def _analyze_batch_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        일괄 재실행 결과 통계 분석

        Args:
            results: 재실행 결과 리스트

        Returns:
            통계 요약
        """
        total = len(results)
        if total == 0:
            return {}

        # 결과 변경 통계
        result_changes = {}
        confidence_changes = []
        method_changes = {}

        for result in results:
            if result.get("status") == "failed":
                continue

            comparison = result.get("comparison", {})

            # 결과 변경
            if comparison.get("result_changed"):
                change = comparison.get("result_change", {})
                key = f"{change.get('from')} → {change.get('to')}"
                result_changes[key] = result_changes.get(key, 0) + 1

            # 신뢰도 변경
            conf_diff = comparison.get("confidence_diff", 0)
            confidence_changes.append(conf_diff)

            # 방법 변경
            if comparison.get("method_changed"):
                change = comparison.get("method_change", {})
                key = f"{change.get('from')} → {change.get('to')}"
                method_changes[key] = method_changes.get(key, 0) + 1

        # 통계 계산
        avg_confidence_change = (
            sum(confidence_changes) / len(confidence_changes)
            if confidence_changes else 0
        )

        return {
            "total_analyzed": total,
            "result_changes": result_changes,
            "method_changes": method_changes,
            "avg_confidence_change": round(avg_confidence_change, 4),
            "confidence_increased": sum(1 for c in confidence_changes if c > 0.1),
            "confidence_decreased": sum(1 for c in confidence_changes if c < -0.1),
        }

    def _get_original_ruleset_version(self, execution: JudgmentExecution) -> Optional[int]:
        """원본 execution 시점의 Ruleset 버전 조회 (추정)"""
        # execution_metadata에 ruleset_version 저장되어 있으면 사용
        if execution.execution_metadata and "ruleset_version" in execution.execution_metadata:
            return execution.execution_metadata["ruleset_version"]

        # 없으면 현재 Ruleset 버전 반환
        ruleset = self.db.query(Ruleset).get(execution.ruleset_id)
        return ruleset.version if ruleset else None


# Singleton
def get_judgment_replay_service(db: Session) -> JudgmentReplayService:
    """
    Judgment Replay Service 인스턴스 반환

    Args:
        db: 데이터베이스 세션

    Returns:
        JudgmentReplayService 인스턴스
    """
    return JudgmentReplayService(db)
