# -*- coding: utf-8 -*-
"""
Intent-Role Permission Mapper

V7 Intent 체계와 5-tier RBAC를 연결합니다.
각 Intent별로 필요한 최소 역할 레벨을 정의합니다.

참조:
- AI_GUIDELINES.md: V7 Intent 체계 14개 카테고리
- rbac_service.py: 5-tier RBAC (ADMIN, APPROVER, OPERATOR, USER, VIEWER)
"""

import logging
from typing import Optional

from app.services.rbac_service import Role

logger = logging.getLogger(__name__)


# Intent별 최소 필요 역할 매트릭스
INTENT_ROLE_MATRIX = {
    # 조회 관련 (최소 권한)
    "CHECK": Role.VIEWER,       # 현재 상태 확인
    "TREND": Role.VIEWER,       # 추세 분석
    "COMPARE": Role.VIEWER,     # 비교 분석

    # 분석 관련 (일반 사용자)
    "RANK": Role.USER,          # 순위/Top-N
    "FIND_CAUSE": Role.USER,    # 원인 분석

    # 고급 분석 (운영자)
    "DETECT_ANOMALY": Role.OPERATOR,  # 이상 탐지
    "PREDICT": Role.OPERATOR,         # 예측
    "WHAT_IF": Role.OPERATOR,         # 시뮬레이션

    # 관리/설정 (승인자)
    "REPORT": Role.APPROVER,    # 보고서 생성
    "NOTIFY": Role.APPROVER,    # 알림 설정

    # 대화 관련 (최소 권한)
    "CONTINUE": Role.VIEWER,    # 대화 연속
    "CLARIFY": Role.VIEWER,     # 명확화 요청
    "STOP": Role.VIEWER,        # 중단

    # 시스템 관련 (관리자)
    "SYSTEM": Role.ADMIN,       # 시스템 명령
}


def check_intent_permission(intent: str, user_role: Role) -> bool:
    """
    Intent 실행에 필요한 권한이 있는지 확인

    Args:
        intent: V7 Intent 카테고리 (CHECK, TREND, ...)
        user_role: 사용자 역할 (VIEWER, USER, OPERATOR, APPROVER, ADMIN)

    Returns:
        bool: 권한이 있으면 True, 없으면 False

    Example:
        >>> check_intent_permission("CHECK", Role.VIEWER)
        True
        >>> check_intent_permission("NOTIFY", Role.VIEWER)
        False
    """
    required_role = INTENT_ROLE_MATRIX.get(intent, Role.ADMIN)

    # Role enum의 value는 숫자 (VIEWER=1, USER=2, ..., ADMIN=5)
    # 사용자 역할 값이 필요 역할 값 이상이면 권한 있음
    has_permission = user_role.value >= required_role.value

    if not has_permission:
        logger.warning(
            f"Permission denied: intent={intent} requires {required_role.name}, "
            f"user has {user_role.name}"
        )

    return has_permission


def get_required_role(intent: str) -> Role:
    """
    Intent에 필요한 최소 역할 반환

    Args:
        intent: V7 Intent 카테고리

    Returns:
        Role: 필요한 최소 역할 (기본값: ADMIN)
    """
    return INTENT_ROLE_MATRIX.get(intent, Role.ADMIN)


def get_intents_for_role(user_role: Role) -> list[str]:
    """
    특정 역할이 실행 가능한 모든 Intent 목록 반환

    Args:
        user_role: 사용자 역할

    Returns:
        list[str]: 실행 가능한 Intent 목록

    Example:
        >>> get_intents_for_role(Role.VIEWER)
        ['CHECK', 'TREND', 'COMPARE', 'CONTINUE', 'CLARIFY', 'STOP']
    """
    allowed_intents = []

    for intent, required_role in INTENT_ROLE_MATRIX.items():
        if user_role.value >= required_role.value:
            allowed_intents.append(intent)

    return allowed_intents
