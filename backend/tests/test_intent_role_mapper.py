# -*- coding: utf-8 -*-
"""
Intent-Role Mapper Tests

V7 Intent와 5-tier RBAC 매핑 테스트
"""
import pytest

from app.services.intent_role_mapper import (
    check_intent_permission,
    get_required_role,
    get_intents_for_role,
    INTENT_ROLE_MATRIX,
)
from app.services.rbac_service import Role


class TestCheckIntentPermission:
    """check_intent_permission 함수 테스트"""

    def test_viewer_can_check(self):
        """VIEWER는 CHECK Intent 실행 가능"""
        assert check_intent_permission("CHECK", Role.VIEWER) is True

    def test_viewer_can_trend(self):
        """VIEWER는 TREND Intent 실행 가능"""
        assert check_intent_permission("TREND", Role.VIEWER) is True

    def test_viewer_can_compare(self):
        """VIEWER는 COMPARE Intent 실행 가능"""
        assert check_intent_permission("COMPARE", Role.VIEWER) is True

    def test_viewer_can_continue(self):
        """VIEWER는 CONTINUE Intent 실행 가능"""
        assert check_intent_permission("CONTINUE", Role.VIEWER) is True

    def test_viewer_cannot_notify(self):
        """VIEWER는 NOTIFY Intent 실행 불가 (APPROVER 필요)"""
        assert check_intent_permission("NOTIFY", Role.VIEWER) is False

    def test_viewer_cannot_predict(self):
        """VIEWER는 PREDICT Intent 실행 불가 (OPERATOR 필요)"""
        assert check_intent_permission("PREDICT", Role.VIEWER) is False

    def test_viewer_cannot_system(self):
        """VIEWER는 SYSTEM Intent 실행 불가 (ADMIN 필요)"""
        assert check_intent_permission("SYSTEM", Role.VIEWER) is False

    def test_user_can_rank(self):
        """USER는 RANK Intent 실행 가능"""
        assert check_intent_permission("RANK", Role.USER) is True

    def test_user_can_find_cause(self):
        """USER는 FIND_CAUSE Intent 실행 가능"""
        assert check_intent_permission("FIND_CAUSE", Role.USER) is True

    def test_user_can_check(self):
        """USER는 CHECK Intent 실행 가능 (하위 권한 포함)"""
        assert check_intent_permission("CHECK", Role.USER) is True

    def test_user_cannot_predict(self):
        """USER는 PREDICT Intent 실행 불가 (OPERATOR 필요)"""
        assert check_intent_permission("PREDICT", Role.USER) is False

    def test_operator_can_predict(self):
        """OPERATOR는 PREDICT Intent 실행 가능"""
        assert check_intent_permission("PREDICT", Role.OPERATOR) is True

    def test_operator_can_detect_anomaly(self):
        """OPERATOR는 DETECT_ANOMALY Intent 실행 가능"""
        assert check_intent_permission("DETECT_ANOMALY", Role.OPERATOR) is True

    def test_operator_can_what_if(self):
        """OPERATOR는 WHAT_IF Intent 실행 가능"""
        assert check_intent_permission("WHAT_IF", Role.OPERATOR) is True

    def test_operator_cannot_notify(self):
        """OPERATOR는 NOTIFY Intent 실행 불가 (APPROVER 필요)"""
        assert check_intent_permission("NOTIFY", Role.OPERATOR) is False

    def test_approver_can_notify(self):
        """APPROVER는 NOTIFY Intent 실행 가능"""
        assert check_intent_permission("NOTIFY", Role.APPROVER) is True

    def test_approver_can_report(self):
        """APPROVER는 REPORT Intent 실행 가능"""
        assert check_intent_permission("REPORT", Role.APPROVER) is True

    def test_approver_can_predict(self):
        """APPROVER는 PREDICT Intent 실행 가능 (하위 권한 포함)"""
        assert check_intent_permission("PREDICT", Role.APPROVER) is True

    def test_approver_cannot_system(self):
        """APPROVER는 SYSTEM Intent 실행 불가 (ADMIN 필요)"""
        assert check_intent_permission("SYSTEM", Role.APPROVER) is False

    def test_admin_can_do_everything(self):
        """ADMIN은 모든 Intent 실행 가능"""
        for intent in INTENT_ROLE_MATRIX.keys():
            assert check_intent_permission(intent, Role.ADMIN) is True, f"Admin should be able to execute {intent}"

    def test_unknown_intent_requires_admin(self):
        """정의되지 않은 Intent는 ADMIN 권한 필요 (안전한 기본값)"""
        assert check_intent_permission("UNKNOWN_INTENT", Role.VIEWER) is False
        assert check_intent_permission("UNKNOWN_INTENT", Role.OPERATOR) is False
        assert check_intent_permission("UNKNOWN_INTENT", Role.APPROVER) is False
        assert check_intent_permission("UNKNOWN_INTENT", Role.ADMIN) is True


class TestGetRequiredRole:
    """get_required_role 함수 테스트"""

    def test_check_requires_viewer(self):
        """CHECK Intent는 VIEWER 권한 필요"""
        assert get_required_role("CHECK") == Role.VIEWER

    def test_rank_requires_user(self):
        """RANK Intent는 USER 권한 필요"""
        assert get_required_role("RANK") == Role.USER

    def test_predict_requires_operator(self):
        """PREDICT Intent는 OPERATOR 권한 필요"""
        assert get_required_role("PREDICT") == Role.OPERATOR

    def test_notify_requires_approver(self):
        """NOTIFY Intent는 APPROVER 권한 필요"""
        assert get_required_role("NOTIFY") == Role.APPROVER

    def test_system_requires_admin(self):
        """SYSTEM Intent는 ADMIN 권한 필요"""
        assert get_required_role("SYSTEM") == Role.ADMIN

    def test_unknown_intent_defaults_to_admin(self):
        """정의되지 않은 Intent는 ADMIN 권한 필요 (안전한 기본값)"""
        assert get_required_role("UNKNOWN_INTENT") == Role.ADMIN


class TestGetIntentsForRole:
    """get_intents_for_role 함수 테스트"""

    def test_viewer_intents(self):
        """VIEWER가 실행 가능한 Intent 목록"""
        viewer_intents = get_intents_for_role(Role.VIEWER)

        # VIEWER가 실행 가능한 Intent
        assert "CHECK" in viewer_intents
        assert "TREND" in viewer_intents
        assert "COMPARE" in viewer_intents
        assert "CONTINUE" in viewer_intents
        assert "CLARIFY" in viewer_intents
        assert "STOP" in viewer_intents

        # VIEWER가 실행 불가한 Intent
        assert "RANK" not in viewer_intents
        assert "NOTIFY" not in viewer_intents
        assert "PREDICT" not in viewer_intents
        assert "SYSTEM" not in viewer_intents

    def test_user_intents(self):
        """USER가 실행 가능한 Intent 목록"""
        user_intents = get_intents_for_role(Role.USER)

        # USER가 실행 가능한 Intent (VIEWER 포함)
        assert "CHECK" in user_intents
        assert "TREND" in user_intents
        assert "RANK" in user_intents
        assert "FIND_CAUSE" in user_intents

        # USER가 실행 불가한 Intent
        assert "PREDICT" not in user_intents
        assert "NOTIFY" not in user_intents
        assert "SYSTEM" not in user_intents

    def test_operator_intents(self):
        """OPERATOR가 실행 가능한 Intent 목록"""
        operator_intents = get_intents_for_role(Role.OPERATOR)

        # OPERATOR가 실행 가능한 Intent (VIEWER + USER 포함)
        assert "CHECK" in operator_intents
        assert "RANK" in operator_intents
        assert "PREDICT" in operator_intents
        assert "DETECT_ANOMALY" in operator_intents
        assert "WHAT_IF" in operator_intents

        # OPERATOR가 실행 불가한 Intent
        assert "NOTIFY" not in operator_intents
        assert "REPORT" not in operator_intents
        assert "SYSTEM" not in operator_intents

    def test_approver_intents(self):
        """APPROVER가 실행 가능한 Intent 목록"""
        approver_intents = get_intents_for_role(Role.APPROVER)

        # APPROVER가 실행 가능한 Intent (VIEWER + USER + OPERATOR 포함)
        assert "CHECK" in approver_intents
        assert "PREDICT" in approver_intents
        assert "NOTIFY" in approver_intents
        assert "REPORT" in approver_intents

        # APPROVER가 실행 불가한 Intent
        assert "SYSTEM" not in approver_intents

    def test_admin_intents(self):
        """ADMIN이 실행 가능한 Intent 목록"""
        admin_intents = get_intents_for_role(Role.ADMIN)

        # ADMIN은 모든 Intent 실행 가능
        for intent in INTENT_ROLE_MATRIX.keys():
            assert intent in admin_intents, f"Admin should be able to execute {intent}"

    def test_role_hierarchy_correctness(self):
        """역할 계층이 올바르게 작동하는지 확인"""
        viewer_count = len(get_intents_for_role(Role.VIEWER))
        user_count = len(get_intents_for_role(Role.USER))
        operator_count = len(get_intents_for_role(Role.OPERATOR))
        approver_count = len(get_intents_for_role(Role.APPROVER))
        admin_count = len(get_intents_for_role(Role.ADMIN))

        # 상위 역할은 하위 역할의 모든 권한을 포함하므로 개수가 같거나 많아야 함
        assert viewer_count <= user_count <= operator_count <= approver_count <= admin_count
        assert admin_count == len(INTENT_ROLE_MATRIX)  # ADMIN은 모든 Intent 실행 가능


class TestIntentRoleMatrix:
    """INTENT_ROLE_MATRIX 정의 검증"""

    def test_all_v7_intents_defined(self):
        """V7 Intent 14개가 모두 매핑되어 있는지 확인"""
        expected_intents = {
            "CHECK", "TREND", "COMPARE", "RANK", "FIND_CAUSE",
            "DETECT_ANOMALY", "PREDICT", "WHAT_IF",
            "REPORT", "NOTIFY",
            "CONTINUE", "CLARIFY", "STOP",
            "SYSTEM",
        }

        actual_intents = set(INTENT_ROLE_MATRIX.keys())

        assert actual_intents == expected_intents, (
            f"Missing intents: {expected_intents - actual_intents}, "
            f"Extra intents: {actual_intents - expected_intents}"
        )

    def test_matrix_values_are_roles(self):
        """매트릭스의 모든 값이 유효한 Role인지 확인"""
        valid_roles = {Role.VIEWER, Role.USER, Role.OPERATOR, Role.APPROVER, Role.ADMIN}

        for intent, role in INTENT_ROLE_MATRIX.items():
            assert role in valid_roles, f"Intent {intent} has invalid role: {role}"

    def test_logical_role_assignment(self):
        """역할 할당이 논리적으로 타당한지 확인"""
        # 조회성 Intent는 낮은 권한
        assert INTENT_ROLE_MATRIX["CHECK"] in [Role.VIEWER, Role.USER]
        assert INTENT_ROLE_MATRIX["TREND"] in [Role.VIEWER, Role.USER]

        # 고급 분석은 높은 권한
        assert INTENT_ROLE_MATRIX["PREDICT"] in [Role.OPERATOR, Role.APPROVER, Role.ADMIN]
        assert INTENT_ROLE_MATRIX["WHAT_IF"] in [Role.OPERATOR, Role.APPROVER, Role.ADMIN]

        # 관리 기능은 승인자 이상
        assert INTENT_ROLE_MATRIX["NOTIFY"] in [Role.APPROVER, Role.ADMIN]
        assert INTENT_ROLE_MATRIX["REPORT"] in [Role.APPROVER, Role.ADMIN]

        # 시스템 명령은 관리자 전용
        assert INTENT_ROLE_MATRIX["SYSTEM"] == Role.ADMIN
