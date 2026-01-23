#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Intent-Role RBAC 통합 검증 스크립트

Intent-Role 매핑이 올바르게 통합되었는지 빠르게 검증합니다.
"""

import sys
from app.services.intent_role_mapper import (
    check_intent_permission,
    get_required_role,
    get_intents_for_role,
    INTENT_ROLE_MATRIX,
)
from app.services.rbac_service import Role


def print_header(text):
    """헤더 출력"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_success(text):
    """성공 메시지"""
    print(f"[OK] {text}")


def print_error(text):
    """에러 메시지"""
    print(f"[FAIL] {text}")


def verify_intent_role_matrix():
    """Intent-Role 매트릭스 검증"""
    print_header("1. Intent-Role Matrix 검증")

    # 14개 V7 Intent 확인
    expected_intents = [
        "CHECK", "TREND", "COMPARE", "RANK",
        "FIND_CAUSE", "DETECT_ANOMALY", "PREDICT", "WHAT_IF",
        "REPORT", "NOTIFY",
        "CONTINUE", "CLARIFY", "STOP", "SYSTEM"
    ]

    missing = [i for i in expected_intents if i not in INTENT_ROLE_MATRIX]
    if missing:
        print_error(f"Missing intents: {missing}")
        return False

    print_success(f"All 14 V7 Intents defined: {len(INTENT_ROLE_MATRIX)}")

    # 각 Intent의 Role이 유효한지 확인
    valid_roles = {Role.VIEWER, Role.USER, Role.OPERATOR, Role.APPROVER, Role.ADMIN}
    for intent, role in INTENT_ROLE_MATRIX.items():
        if role not in valid_roles:
            print_error(f"Invalid role for {intent}: {role}")
            return False

    print_success("All roles are valid")
    return True


def verify_permission_checks():
    """권한 체크 기능 검증"""
    print_header("2. 권한 체크 기능 검증")

    test_cases = [
        # (intent, role, expected_result, description)
        ("CHECK", Role.VIEWER, True, "VIEWER can CHECK"),
        ("PREDICT", Role.VIEWER, False, "VIEWER cannot PREDICT"),
        ("PREDICT", Role.OPERATOR, True, "OPERATOR can PREDICT"),
        ("NOTIFY", Role.OPERATOR, False, "OPERATOR cannot NOTIFY"),
        ("NOTIFY", Role.APPROVER, True, "APPROVER can NOTIFY"),
        ("SYSTEM", Role.APPROVER, False, "APPROVER cannot SYSTEM"),
        ("SYSTEM", Role.ADMIN, True, "ADMIN can SYSTEM"),
    ]

    failed = 0
    for intent, role, expected, description in test_cases:
        result = check_intent_permission(intent, role)
        if result == expected:
            print_success(description)
        else:
            print_error(f"{description} - Expected {expected}, got {result}")
            failed += 1

    return failed == 0


def verify_role_hierarchy():
    """역할 계층 검증"""
    print_header("3. 역할 계층 검증")

    viewer_intents = set(get_intents_for_role(Role.VIEWER))
    user_intents = set(get_intents_for_role(Role.USER))
    operator_intents = set(get_intents_for_role(Role.OPERATOR))
    approver_intents = set(get_intents_for_role(Role.APPROVER))
    admin_intents = set(get_intents_for_role(Role.ADMIN))

    # 상위 역할은 하위 역할의 모든 권한 포함
    checks = [
        (viewer_intents.issubset(user_intents), "USER includes all VIEWER permissions"),
        (user_intents.issubset(operator_intents), "OPERATOR includes all USER permissions"),
        (operator_intents.issubset(approver_intents), "APPROVER includes all OPERATOR permissions"),
        (approver_intents.issubset(admin_intents), "ADMIN includes all APPROVER permissions"),
        (len(admin_intents) == 14, "ADMIN has access to all 14 intents"),
    ]

    failed = 0
    for check_result, description in checks:
        if check_result:
            print_success(description)
        else:
            print_error(description)
            failed += 1

    # 각 역할별 Intent 개수 출력
    print(f"\n  VIEWER:   {len(viewer_intents)} intents")
    print(f"  USER:     {len(user_intents)} intents")
    print(f"  OPERATOR: {len(operator_intents)} intents")
    print(f"  APPROVER: {len(approver_intents)} intents")
    print(f"  ADMIN:    {len(admin_intents)} intents")

    return failed == 0


def verify_meta_router_integration():
    """Meta Router 통합 검증"""
    print_header("4. Meta Router 통합 검증")

    try:
        from app.agents.meta_router import MetaRouterAgent

        router = MetaRouterAgent()
        print_success("MetaRouterAgent 초기화 성공")

        # VIEWER로 PREDICT 시도 (권한 거부되어야 함)
        result = router.route_with_hybrid(
            user_input="다음 주 불량률 예측해줘",
            user_role=Role.VIEWER,
            context={}
        )

        # v7_intent가 PREDICT인 경우 검증
        if result.get("v7_intent") == "PREDICT":
            if result.get("target_agent") == "error" and "권한 부족" in result.get("error", ""):
                print_success("VIEWER의 PREDICT 시도가 올바르게 거부됨")
            else:
                print_error("VIEWER의 PREDICT 시도가 거부되지 않음")
                return False

        # OPERATOR로 PREDICT 시도 (허용되어야 함)
        result2 = router.route_with_hybrid(
            user_input="다음 주 불량률 예측해줘",
            user_role=Role.OPERATOR,
            context={}
        )

        if result2.get("v7_intent") == "PREDICT":
            if result2.get("target_agent") != "error":
                print_success("OPERATOR의 PREDICT 시도가 올바르게 허용됨")
            else:
                print_error("OPERATOR의 PREDICT 시도가 거부됨")
                return False

        return True

    except ImportError as e:
        print_error(f"Meta Router import 실패: {e}")
        return False
    except Exception as e:
        print_error(f"Meta Router 통합 테스트 실패: {e}")
        return False


def main():
    """메인 검증 함수"""
    print("\n" + "="*60)
    print("  Intent-Role RBAC 통합 검증")
    print("="*60)

    results = []

    # 1. Intent-Role Matrix 검증
    results.append(("Intent-Role Matrix", verify_intent_role_matrix()))

    # 2. 권한 체크 기능 검증
    results.append(("권한 체크 기능", verify_permission_checks()))

    # 3. 역할 계층 검증
    results.append(("역할 계층", verify_role_hierarchy()))

    # 4. Meta Router 통합 검증
    results.append(("Meta Router 통합", verify_meta_router_integration()))

    # 결과 요약
    print_header("검증 결과 요약")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}  {name}")

    print(f"\n  총 {passed}/{total} 검증 통과")

    if passed == total:
        print_success("\n모든 검증 통과! Intent-Role RBAC가 올바르게 통합되었습니다.")
        return 0
    else:
        print_error(f"\n{total - passed}개 검증 실패")
        return 1


if __name__ == "__main__":
    sys.exit(main())
