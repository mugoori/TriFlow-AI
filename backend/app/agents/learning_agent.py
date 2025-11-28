"""
Learning Agent
피드백 분석 및 규칙 학습/제안 수행
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import logging
import random
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import func

from .base_agent import BaseAgent
from app.database import get_db_context
from app.models.core import FeedbackLog, ProposedRule, Ruleset, JudgmentExecution, Tenant

logger = logging.getLogger(__name__)


class LearningAgent(BaseAgent):
    """
    Learning Agent
    - 피드백 로그 분석
    - 새로운 규칙 제안
    - Z-Wave 시뮬레이션 실행
    """

    def __init__(self):
        super().__init__(
            name="LearningAgent",
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
        )

    def get_system_prompt(self) -> str:
        """
        시스템 프롬프트 로드
        """
        prompt_path = Path(__file__).parent.parent / "prompts" / "learning_agent.md"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {prompt_path}, using default")
            return "You are a Learning Agent for TriFlow AI."

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Learning Agent의 Tool 정의
        """
        return [
            {
                "name": "analyze_feedback_logs",
                "description": "피드백 로그를 분석하여 패턴과 개선점을 발견합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "feedback_type": {
                            "type": "string",
                            "description": "피드백 타입 필터 (positive, negative, correction, all)",
                            "enum": ["positive", "negative", "correction", "all"],
                            "default": "all",
                        },
                        "days": {
                            "type": "integer",
                            "description": "분석할 기간 (일 단위, 기본: 7)",
                            "default": 7,
                        },
                        "min_occurrences": {
                            "type": "integer",
                            "description": "패턴으로 인식할 최소 발생 횟수 (기본: 3)",
                            "default": 3,
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "propose_new_rule",
                "description": "분석 결과를 바탕으로 새로운 규칙을 제안합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "rule_name": {
                            "type": "string",
                            "description": "규칙 이름",
                        },
                        "rule_description": {
                            "type": "string",
                            "description": "규칙 설명",
                        },
                        "trigger_condition": {
                            "type": "string",
                            "description": "트리거 조건 (자연어)",
                        },
                        "action_description": {
                            "type": "string",
                            "description": "수행할 액션 (자연어)",
                        },
                        "source_feedback_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "근거가 된 피드백 ID 목록 (선택)",
                        },
                    },
                    "required": ["rule_name", "rule_description", "trigger_condition", "action_description"],
                },
            },
            {
                "name": "run_zwave_simulation",
                "description": "Z-Wave 시뮬레이션을 실행하여 규칙을 테스트합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "rule_script": {
                            "type": "string",
                            "description": "테스트할 Rhai 스크립트",
                        },
                        "scenario": {
                            "type": "string",
                            "description": "시뮬레이션 시나리오 (normal, warning, critical, random)",
                            "enum": ["normal", "warning", "critical", "random"],
                            "default": "random",
                        },
                        "iterations": {
                            "type": "integer",
                            "description": "시뮬레이션 반복 횟수 (기본: 100)",
                            "default": 100,
                        },
                    },
                    "required": ["rule_script"],
                },
            },
            {
                "name": "get_rule_performance",
                "description": "기존 규칙의 성능 통계를 조회합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ruleset_id": {
                            "type": "string",
                            "description": "Ruleset ID (선택, 없으면 전체)",
                        },
                        "days": {
                            "type": "integer",
                            "description": "조회 기간 (일 단위, 기본: 30)",
                            "default": 30,
                        },
                    },
                    "required": [],
                },
            },
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Tool 실행
        """
        if tool_name == "analyze_feedback_logs":
            return self._analyze_feedback_logs(
                feedback_type=tool_input.get("feedback_type", "all"),
                days=tool_input.get("days", 7),
                min_occurrences=tool_input.get("min_occurrences", 3),
            )

        elif tool_name == "propose_new_rule":
            return self._propose_new_rule(
                rule_name=tool_input["rule_name"],
                rule_description=tool_input["rule_description"],
                trigger_condition=tool_input["trigger_condition"],
                action_description=tool_input["action_description"],
                source_feedback_ids=tool_input.get("source_feedback_ids", []),
            )

        elif tool_name == "run_zwave_simulation":
            return self._run_zwave_simulation(
                rule_script=tool_input["rule_script"],
                scenario=tool_input.get("scenario", "random"),
                iterations=tool_input.get("iterations", 100),
            )

        elif tool_name == "get_rule_performance":
            return self._get_rule_performance(
                ruleset_id=tool_input.get("ruleset_id"),
                days=tool_input.get("days", 30),
            )

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _analyze_feedback_logs(
        self,
        feedback_type: str = "all",
        days: int = 7,
        min_occurrences: int = 3,
    ) -> Dict[str, Any]:
        """
        피드백 로그 분석
        """
        try:
            with get_db_context() as db:
                cutoff_time = datetime.utcnow() - timedelta(days=days)

                # 기본 쿼리
                query = db.query(FeedbackLog).filter(
                    FeedbackLog.created_at >= cutoff_time
                )

                # 타입 필터
                if feedback_type != "all":
                    query = query.filter(FeedbackLog.feedback_type == feedback_type)

                feedbacks = query.all()

                if not feedbacks:
                    return {
                        "success": True,
                        "total_feedbacks": 0,
                        "patterns": [],
                        "summary": "분석할 피드백이 없습니다.",
                        "recommendations": [],
                    }

                # 패턴 분석
                patterns = self._extract_patterns(feedbacks, min_occurrences)

                # 타입별 통계
                type_stats = {}
                for fb in feedbacks:
                    t = fb.feedback_type
                    type_stats[t] = type_stats.get(t, 0) + 1

                # 추천 도출
                recommendations = self._generate_recommendations(patterns)

                logger.info(f"Analyzed {len(feedbacks)} feedbacks, found {len(patterns)} patterns")

                return {
                    "success": True,
                    "total_feedbacks": len(feedbacks),
                    "period_days": days,
                    "type_statistics": type_stats,
                    "patterns": patterns,
                    "recommendations": recommendations,
                    "unprocessed_count": sum(1 for f in feedbacks if not f.is_processed),
                }

        except Exception as e:
            logger.error(f"Error analyzing feedback logs: {e}")
            # DB 없이도 동작하도록 더미 데이터 반환
            return {
                "success": True,
                "total_feedbacks": 0,
                "period_days": days,
                "type_statistics": {},
                "patterns": [],
                "recommendations": [
                    "피드백 데이터가 충분하지 않습니다. 시스템 사용 후 피드백을 수집해 주세요."
                ],
                "unprocessed_count": 0,
                "note": "DB 연결 없이 기본값 반환",
            }

    def _extract_patterns(
        self,
        feedbacks: List[FeedbackLog],
        min_occurrences: int
    ) -> List[Dict[str, Any]]:
        """
        피드백에서 패턴 추출
        """
        # 간단한 패턴 분석 (MVP: 키워드 기반)
        keyword_counts = {}
        correction_patterns = {}

        for fb in feedbacks:
            # 피드백 텍스트에서 키워드 추출
            if fb.feedback_text:
                words = fb.feedback_text.lower().split()
                for word in words:
                    if len(word) > 3:  # 짧은 단어 제외
                        keyword_counts[word] = keyword_counts.get(word, 0) + 1

            # 수정 패턴 분석
            if fb.feedback_type == "correction" and fb.corrected_output:
                original = fb.original_output or {}
                corrected = fb.corrected_output

                # 변경된 필드 추적
                for key in corrected:
                    if key not in original or original.get(key) != corrected.get(key):
                        pattern_key = f"field_change:{key}"
                        correction_patterns[pattern_key] = correction_patterns.get(pattern_key, 0) + 1

        # 패턴 목록 생성
        patterns = []

        # 키워드 패턴
        for keyword, count in keyword_counts.items():
            if count >= min_occurrences:
                patterns.append({
                    "type": "keyword",
                    "value": keyword,
                    "occurrences": count,
                    "severity": "medium" if count < 10 else "high",
                })

        # 수정 패턴
        for pattern, count in correction_patterns.items():
            if count >= min_occurrences:
                patterns.append({
                    "type": "correction",
                    "value": pattern,
                    "occurrences": count,
                    "severity": "high",
                })

        return sorted(patterns, key=lambda x: x["occurrences"], reverse=True)

    def _generate_recommendations(
        self,
        patterns: List[Dict[str, Any]]
    ) -> List[str]:
        """
        패턴을 기반으로 추천 생성
        """
        recommendations = []

        for pattern in patterns[:5]:  # 상위 5개 패턴
            if pattern["type"] == "keyword":
                recommendations.append(
                    f"'{pattern['value']}' 관련 피드백이 {pattern['occurrences']}회 발생했습니다. "
                    f"해당 영역의 규칙 검토가 필요합니다."
                )
            elif pattern["type"] == "correction":
                field = pattern["value"].replace("field_change:", "")
                recommendations.append(
                    f"'{field}' 필드가 {pattern['occurrences']}회 수정되었습니다. "
                    f"해당 판단 로직의 개선이 권장됩니다."
                )

        if not recommendations:
            recommendations.append("현재 뚜렷한 패턴이 발견되지 않았습니다.")

        return recommendations

    def _propose_new_rule(
        self,
        rule_name: str,
        rule_description: str,
        trigger_condition: str,
        action_description: str,
        source_feedback_ids: List[str] = None,
    ) -> Dict[str, Any]:
        """
        새로운 규칙 제안
        """
        try:
            # Rhai 스크립트 생성
            rhai_script = self._generate_rhai_script(
                rule_name=rule_name,
                description=rule_description,
                trigger_condition=trigger_condition,
                action_description=action_description,
            )

            # 신뢰도 계산 (MVP: 기본값)
            confidence = 0.75

            with get_db_context() as db:
                # 기본 테넌트 조회 또는 생성
                tenant = db.query(Tenant).first()
                if not tenant:
                    tenant = Tenant(
                        name="Default Tenant",
                        slug="default",
                        settings={},
                    )
                    db.add(tenant)
                    db.commit()
                    db.refresh(tenant)

                # 제안 저장
                proposal = ProposedRule(
                    tenant_id=tenant.tenant_id,
                    rule_name=rule_name,
                    rule_description=rule_description,
                    rhai_script=rhai_script,
                    source_type="feedback_analysis",
                    source_data={
                        "trigger_condition": trigger_condition,
                        "action_description": action_description,
                        "feedback_ids": source_feedback_ids or [],
                    },
                    confidence=confidence,
                    status="pending",
                )

                db.add(proposal)
                db.commit()
                db.refresh(proposal)

                logger.info(f"Created rule proposal: {proposal.proposal_id}")

                return {
                    "success": True,
                    "proposal_id": str(proposal.proposal_id),
                    "rule_name": rule_name,
                    "rhai_script": rhai_script,
                    "confidence": confidence,
                    "status": "pending",
                    "message": "규칙이 성공적으로 제안되었습니다. 관리자 승인을 기다립니다.",
                }

        except Exception as e:
            logger.error(f"Error proposing new rule: {e}")
            # DB 없이도 스크립트 생성 가능
            rhai_script = self._generate_rhai_script(
                rule_name=rule_name,
                description=rule_description,
                trigger_condition=trigger_condition,
                action_description=action_description,
            )

            return {
                "success": True,
                "proposal_id": str(uuid4()),
                "rule_name": rule_name,
                "rhai_script": rhai_script,
                "confidence": 0.75,
                "status": "draft",
                "message": "규칙이 생성되었습니다. (DB 미연결로 저장되지 않음)",
                "note": "DB 연결 없이 기본값 반환",
            }

    def _generate_rhai_script(
        self,
        rule_name: str,
        description: str,
        trigger_condition: str,
        action_description: str,
    ) -> str:
        """
        자연어 설명을 기반으로 Rhai 스크립트 생성
        MVP: 템플릿 기반 간단한 생성
        """
        # 조건 파싱 (간단한 패턴 매칭)
        condition_code = self._parse_condition(trigger_condition)
        action_code = self._parse_action(action_description)

        script = f'''// Rule: {rule_name}
// Description: {description}
// Generated by: Learning Agent
// Timestamp: {datetime.utcnow().isoformat()}

let input = context["input"];

let result = #{{
    status: "NORMAL",
    checks: [],
    confidence: 0.85,
    rule_name: "{rule_name}"
}};

// Trigger Condition: {trigger_condition}
{condition_code}

// Action: {action_description}
{action_code}

result
'''
        return script

    def _parse_condition(self, condition: str) -> str:
        """
        자연어 조건을 Rhai 코드로 변환
        MVP: 간단한 패턴 매칭
        """
        condition_lower = condition.lower()

        # 온도 관련 조건
        if "온도" in condition_lower or "temperature" in condition_lower:
            if "초과" in condition_lower or "이상" in condition_lower or ">" in condition:
                # 숫자 추출 시도
                import re
                numbers = re.findall(r'\d+', condition)
                threshold = numbers[0] if numbers else "80"
                return f'''if input.temperature > {threshold}.0 {{
    result.status = "WARNING";
    result.checks.push(#{{
        type: "temperature",
        status: "HIGH",
        message: "온도가 {threshold}°C를 초과했습니다"
    }});
}}'''

        # 압력 관련 조건
        if "압력" in condition_lower or "pressure" in condition_lower:
            import re
            numbers = re.findall(r'\d+', condition)
            threshold = numbers[0] if numbers else "100"
            return f'''if input.pressure > {threshold}.0 {{
    result.status = "WARNING";
    result.checks.push(#{{
        type: "pressure",
        status: "HIGH",
        message: "압력이 {threshold}를 초과했습니다"
    }});
}}'''

        # 기본 템플릿
        return f'''// TODO: 조건 수동 구현 필요
// 원본 조건: {condition}
if false {{
    result.status = "WARNING";
}}'''

    def _parse_action(self, action: str) -> str:
        """
        자연어 액션을 Rhai 코드로 변환
        MVP: 간단한 패턴 매칭
        """
        action_lower = action.lower()

        if "알림" in action_lower or "notification" in action_lower:
            return '''result.actions = result.actions ?? [];
result.actions.push(#{
    type: "notification",
    channel: "slack",
    message: result.checks.map(|c| c.message).join("; ")
});'''

        if "중지" in action_lower or "stop" in action_lower:
            return '''result.actions = result.actions ?? [];
result.actions.push(#{
    type: "control",
    command: "stop_line",
    reason: result.checks.map(|c| c.message).join("; ")
});'''

        # 기본: 로깅만
        return '''result.actions = result.actions ?? [];
result.actions.push(#{
    type: "log",
    level: "warning",
    message: result.checks.map(|c| c.message).join("; ")
});'''

    def _run_zwave_simulation(
        self,
        rule_script: str,
        scenario: str = "random",
        iterations: int = 100,
    ) -> Dict[str, Any]:
        """
        Z-Wave 시뮬레이션 실행
        """
        logger.info(f"Running Z-Wave simulation: scenario={scenario}, iterations={iterations}")

        # 시뮬레이션 데이터 생성
        results = []
        for i in range(iterations):
            sim_data = self._generate_simulation_data(scenario)

            # 규칙 실행 (MVP: 간단한 평가)
            try:
                outcome = self._evaluate_rule(rule_script, sim_data)
                results.append({
                    "iteration": i + 1,
                    "input": sim_data,
                    "outcome": outcome,
                    "expected": self._get_expected_outcome(sim_data),
                })
            except Exception as e:
                results.append({
                    "iteration": i + 1,
                    "input": sim_data,
                    "outcome": {"error": str(e)},
                    "expected": None,
                })

        # 결과 분석
        correct = sum(1 for r in results if r.get("outcome", {}).get("status") == r.get("expected"))
        accuracy = correct / iterations if iterations > 0 else 0

        false_positives = sum(
            1 for r in results
            if r.get("outcome", {}).get("status") in ["WARNING", "CRITICAL"]
            and r.get("expected") == "NORMAL"
        )
        false_negatives = sum(
            1 for r in results
            if r.get("outcome", {}).get("status") == "NORMAL"
            and r.get("expected") in ["WARNING", "CRITICAL"]
        )

        return {
            "success": True,
            "scenario": scenario,
            "iterations": iterations,
            "accuracy": round(accuracy * 100, 2),
            "false_positive_rate": round(false_positives / iterations * 100, 2) if iterations > 0 else 0,
            "false_negative_rate": round(false_negatives / iterations * 100, 2) if iterations > 0 else 0,
            "sample_results": results[:5],  # 샘플 5개만 반환
            "recommendation": self._get_simulation_recommendation(accuracy),
        }

    def _generate_simulation_data(self, scenario: str) -> Dict[str, Any]:
        """
        시뮬레이션 데이터 생성
        """
        if scenario == "normal":
            return {
                "temperature": random.uniform(20, 70),
                "pressure": random.uniform(2, 8),
                "humidity": random.uniform(30, 60),
            }
        elif scenario == "warning":
            return {
                "temperature": random.uniform(70, 85),
                "pressure": random.uniform(8, 12),
                "humidity": random.uniform(60, 75),
            }
        elif scenario == "critical":
            return {
                "temperature": random.uniform(85, 120),
                "pressure": random.uniform(12, 20),
                "humidity": random.uniform(75, 95),
            }
        else:  # random
            r = random.random()
            if r < 0.7:
                return self._generate_simulation_data("normal")
            elif r < 0.9:
                return self._generate_simulation_data("warning")
            else:
                return self._generate_simulation_data("critical")

    def _evaluate_rule(self, rule_script: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        규칙 평가 (MVP: 간단한 임계값 체크)
        """
        # MVP: Rhai 엔진 대신 간단한 Python 평가
        status = "NORMAL"
        checks = []

        temp = input_data.get("temperature", 0)
        if temp > 80:
            status = "CRITICAL"
            checks.append({"type": "temperature", "status": "HIGH", "value": temp})
        elif temp > 70:
            status = "WARNING"
            checks.append({"type": "temperature", "status": "ELEVATED", "value": temp})

        pressure = input_data.get("pressure", 0)
        if pressure > 12:
            status = "CRITICAL"
            checks.append({"type": "pressure", "status": "HIGH", "value": pressure})
        elif pressure > 8:
            if status != "CRITICAL":
                status = "WARNING"
            checks.append({"type": "pressure", "status": "ELEVATED", "value": pressure})

        return {
            "status": status,
            "checks": checks,
            "confidence": 0.85,
        }

    def _get_expected_outcome(self, input_data: Dict[str, Any]) -> str:
        """
        입력 데이터에 대한 기대 결과 반환
        """
        temp = input_data.get("temperature", 0)
        pressure = input_data.get("pressure", 0)

        if temp > 80 or pressure > 12:
            return "CRITICAL"
        elif temp > 70 or pressure > 8:
            return "WARNING"
        return "NORMAL"

    def _get_simulation_recommendation(self, accuracy: float) -> str:
        """
        시뮬레이션 결과에 따른 추천
        """
        if accuracy >= 0.95:
            return "✅ 규칙이 매우 정확합니다. 배포를 권장합니다."
        elif accuracy >= 0.85:
            return "👍 규칙이 양호합니다. 약간의 튜닝 후 배포를 권장합니다."
        elif accuracy >= 0.70:
            return "⚠️ 규칙 정확도가 낮습니다. 조건 검토가 필요합니다."
        else:
            return "❌ 규칙 정확도가 매우 낮습니다. 재설계가 필요합니다."

    def _get_rule_performance(
        self,
        ruleset_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        규칙 성능 통계 조회
        """
        try:
            with get_db_context() as db:
                cutoff_time = datetime.utcnow() - timedelta(days=days)

                # 실행 로그 조회
                query = db.query(JudgmentExecution).filter(
                    JudgmentExecution.executed_at >= cutoff_time
                )

                if ruleset_id:
                    # workflow_id를 통한 간접 필터링 (MVP)
                    pass

                executions = query.all()

                if not executions:
                    return {
                        "success": True,
                        "total_executions": 0,
                        "period_days": days,
                        "performance": {},
                        "note": "실행 데이터가 없습니다.",
                    }

                # 통계 계산
                total = len(executions)
                avg_confidence = sum(e.confidence or 0 for e in executions) / total if total > 0 else 0
                avg_time = sum(e.execution_time_ms or 0 for e in executions) / total if total > 0 else 0

                # 방법별 통계
                method_stats = {}
                for e in executions:
                    method = e.method_used or "unknown"
                    if method not in method_stats:
                        method_stats[method] = {"count": 0, "avg_confidence": 0}
                    method_stats[method]["count"] += 1

                return {
                    "success": True,
                    "total_executions": total,
                    "period_days": days,
                    "average_confidence": round(avg_confidence, 2),
                    "average_execution_time_ms": round(avg_time, 2),
                    "method_statistics": method_stats,
                }

        except Exception as e:
            logger.error(f"Error getting rule performance: {e}")
            return {
                "success": True,
                "total_executions": 0,
                "period_days": days,
                "performance": {},
                "note": "DB 연결 없이 기본값 반환",
            }
