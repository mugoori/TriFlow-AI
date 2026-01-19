# -*- coding: utf-8 -*-
"""
Intent Permission Integration Tests

End-to-end tests for Intent-Role based permission checking
Tests the flow: AgentOrchestrator → MetaRouter → Intent Permission Check
"""
import pytest

from app.services.agent_orchestrator import AgentOrchestrator
from app.services.rbac_service import Role


class TestIntentPermissionIntegration:
    """End-to-end Intent 권한 체크 통합 테스트"""

    @pytest.fixture
    def orchestrator(self):
        """AgentOrchestrator 인스턴스"""
        return AgentOrchestrator()

    def test_viewer_can_check_intent(self, orchestrator):
        """VIEWER는 CHECK Intent 실행 가능"""
        result = orchestrator.process(
            message="오늘 생산량 얼마야?",  # CHECK Intent
            user_role=Role.VIEWER.value,
        )

        # 권한 에러가 아니어야 함
        assert result["agent_name"] != "error"
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") != "error"
        assert "error" not in routing_info

    def test_viewer_cannot_predict_intent(self, orchestrator):
        """VIEWER는 PREDICT Intent 실행 불가 (OPERATOR 필요)"""
        result = orchestrator.process(
            message="내일 불량률 예측해줘",  # PREDICT Intent
            user_role=Role.VIEWER.value,
        )

        # 권한 에러 확인
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") == "error"
        assert "error" in routing_info
        assert "권한 부족" in routing_info["error"]
        assert "PREDICT" in routing_info["error"]
        assert routing_info.get("required_role") == Role.OPERATOR.value
        assert routing_info.get("user_role") == Role.VIEWER.value

    def test_viewer_cannot_notify_intent(self, orchestrator):
        """VIEWER는 NOTIFY Intent 실행 불가 (APPROVER 필요)"""
        result = orchestrator.process(
            message="불량 발생 시 알림 설정해줘",  # NOTIFY Intent
            user_role=Role.VIEWER.value,
        )

        # 권한 에러 확인
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") == "error"
        assert "error" in routing_info
        assert "권한 부족" in routing_info["error"]
        assert routing_info.get("required_role") == Role.APPROVER.value

    def test_user_can_rank_intent(self, orchestrator):
        """USER는 RANK Intent 실행 가능"""
        result = orchestrator.process(
            message="불량이 가장 많은 라인 TOP 5 알려줘",  # RANK Intent
            user_role=Role.USER.value,
        )

        # 권한 에러가 아니어야 함
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") != "error"
        assert "error" not in routing_info

    def test_user_can_check_intent(self, orchestrator):
        """USER는 CHECK Intent 실행 가능 (하위 권한 포함)"""
        result = orchestrator.process(
            message="LINE_A 온도 확인해줘",  # CHECK Intent
            user_role=Role.USER.value,
        )

        # 권한 에러가 아니어야 함
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") != "error"
        assert "error" not in routing_info

    def test_user_cannot_predict_intent(self, orchestrator):
        """USER는 PREDICT Intent 실행 불가 (OPERATOR 필요)"""
        result = orchestrator.process(
            message="다음 주 불량률 예측해줘",  # PREDICT Intent
            user_role=Role.USER.value,
        )

        # 권한 에러 확인
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") == "error"
        assert routing_info.get("required_role") == Role.OPERATOR.value
        assert routing_info.get("user_role") == Role.USER.value

    def test_operator_can_predict_intent(self, orchestrator):
        """OPERATOR는 PREDICT Intent 실행 가능"""
        result = orchestrator.process(
            message="내일 설비 고장 예측해줘",  # PREDICT Intent
            user_role=Role.OPERATOR.value,
        )

        # 권한 에러가 아니어야 함
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") != "error"
        assert "error" not in routing_info

    def test_operator_can_detect_anomaly_intent(self, orchestrator):
        """OPERATOR는 DETECT_ANOMALY Intent 실행 가능"""
        result = orchestrator.process(
            message="이상치 탐지해줘",  # DETECT_ANOMALY Intent
            user_role=Role.OPERATOR.value,
        )

        # 권한 에러가 아니어야 함
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") != "error"
        assert "error" not in routing_info

    def test_operator_cannot_notify_intent(self, orchestrator):
        """OPERATOR는 NOTIFY Intent 실행 불가 (APPROVER 필요)"""
        result = orchestrator.process(
            message="알림 규칙 설정해줘",  # NOTIFY Intent
            user_role=Role.OPERATOR.value,
        )

        # 권한 에러 확인
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") == "error"
        assert routing_info.get("required_role") == Role.APPROVER.value
        assert routing_info.get("user_role") == Role.OPERATOR.value

    def test_approver_can_notify_intent(self, orchestrator):
        """APPROVER는 NOTIFY Intent 실행 가능"""
        result = orchestrator.process(
            message="불량 임계치 초과 시 알림 보내줘",  # NOTIFY Intent
            user_role=Role.APPROVER.value,
        )

        # 권한 에러가 아니어야 함
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") != "error"
        assert "error" not in routing_info

    def test_approver_can_report_intent(self, orchestrator):
        """APPROVER는 REPORT Intent 실행 가능"""
        result = orchestrator.process(
            message="월간 생산 리포트 생성해줘",  # REPORT Intent
            user_role=Role.APPROVER.value,
        )

        # 권한 에러가 아니어야 함
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") != "error"
        assert "error" not in routing_info

    def test_approver_can_predict_intent(self, orchestrator):
        """APPROVER는 PREDICT Intent 실행 가능 (하위 권한 포함)"""
        result = orchestrator.process(
            message="내일 설비 예측해줘",  # PREDICT Intent
            user_role=Role.APPROVER.value,
        )

        # 권한 에러가 아니어야 함
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") != "error"
        assert "error" not in routing_info

    def test_approver_cannot_system_intent(self, orchestrator):
        """APPROVER는 SYSTEM Intent 실행 불가 (ADMIN 필요)"""
        result = orchestrator.process(
            message="시스템 재시작해줘",  # SYSTEM Intent
            user_role=Role.APPROVER.value,
        )

        # 권한 에러 확인
        routing_info = result.get("routing_info", {})
        assert routing_info.get("target_agent") == "error"
        assert routing_info.get("required_role") == Role.ADMIN.value
        assert routing_info.get("user_role") == Role.APPROVER.value

    def test_admin_can_execute_all_intents(self, orchestrator):
        """ADMIN은 모든 Intent 실행 가능"""
        test_cases = [
            ("오늘 생산량 얼마야?", "CHECK"),
            ("불량 예측해줘", "PREDICT"),
            ("알림 설정해줘", "NOTIFY"),
            ("시스템 재시작", "SYSTEM"),
        ]

        for message, expected_intent in test_cases:
            result = orchestrator.process(
                message=message,
                user_role=Role.ADMIN.value,
            )

            # 권한 에러가 아니어야 함
            routing_info = result.get("routing_info", {})
            assert routing_info.get("target_agent") != "error", f"Admin should be able to execute {expected_intent}"
            assert "error" not in routing_info, f"Admin should not get permission error for {expected_intent}"

    def test_no_auth_allows_all_intents(self, orchestrator):
        """인증 없이 요청 시 권한 체크 생략 (하위 호환성)"""
        result = orchestrator.process(
            message="불량 예측해줘",  # PREDICT Intent (OPERATOR 필요)
            user_role=None,  # 인증 없음
        )

        # 권한 에러가 없어야 함 (인증 없으면 체크 생략)
        routing_info = result.get("routing_info", {})
        # target_agent가 error가 아니거나, permission_denied가 False여야 함
        if routing_info.get("target_agent") == "error":
            assert not routing_info.get("context", {}).get("permission_denied")

    def test_invalid_role_defaults_to_no_check(self, orchestrator):
        """잘못된 역할 문자열은 권한 체크 생략"""
        result = orchestrator.process(
            message="불량 예측해줘",
            user_role="invalid_role",  # 잘못된 역할
        )

        # 권한 에러가 없어야 함 (잘못된 역할은 체크 생략)
        routing_info = result.get("routing_info", {})
        if routing_info.get("target_agent") == "error":
            assert not routing_info.get("context", {}).get("permission_denied")

    def test_permission_check_with_llm_fallback(self, orchestrator):
        """LLM 분류 fallback 시에도 권한 체크 작동"""
        # 규칙 매칭이 안되는 복잡한 요청
        result = orchestrator.process(
            message="혹시 내일 불량률이 올라갈 것 같은데, 어떻게 생각하시나요?",  # PREDICT Intent (LLM 분류)
            user_role=Role.VIEWER.value,
        )

        # VIEWER는 PREDICT 불가이므로 권한 에러 발생 (LLM 분류여도)
        routing_info = result.get("routing_info", {})
        # LLM이 PREDICT로 분류했다면 권한 에러여야 함
        if routing_info.get("v7_intent") == "PREDICT":
            assert routing_info.get("target_agent") == "error"
            assert "권한 부족" in routing_info.get("error", "")


class TestPermissionCheckLogging:
    """권한 체크 로깅 테스트"""

    @pytest.fixture
    def orchestrator(self):
        """AgentOrchestrator 인스턴스"""
        return AgentOrchestrator()

    def test_permission_denied_includes_details(self, orchestrator):
        """권한 거부 시 상세 정보 포함"""
        result = orchestrator.process(
            message="시스템 재시작해줘",
            user_role=Role.VIEWER.value,
        )

        routing_info = result.get("routing_info", {})

        # 필요한 정보가 모두 포함되어 있는지 확인
        assert "v7_intent" in routing_info
        assert "error" in routing_info
        assert "required_role" in routing_info
        assert "user_role" in routing_info
        assert routing_info["context"].get("permission_denied") is True

    def test_successful_permission_check_no_error(self, orchestrator):
        """권한 체크 성공 시 에러 정보 없음"""
        result = orchestrator.process(
            message="오늘 생산량 알려줘",
            user_role=Role.VIEWER.value,
        )

        routing_info = result.get("routing_info", {})

        # 에러 정보가 없어야 함
        assert routing_info.get("target_agent") != "error"
        assert "error" not in routing_info
        assert not routing_info.get("context", {}).get("permission_denied")
