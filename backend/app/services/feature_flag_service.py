# -*- coding: utf-8 -*-
"""
TriFlow AI - Feature Flag Service
V2.0 기능을 점진적으로 롤아웃하기 위한 Feature Flag 관리

주요 기능:
- V2 기능별 활성화/비활성화
- 테넌트별 또는 글로벌 설정
- 점진적 롤아웃 (percentage-based)
- Redis 장애 시 안전한 기본값 (False)
"""

import hashlib
import logging
from enum import Enum
from typing import Dict, Optional

from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class V2Feature(str, Enum):
    """V2 기능 플래그 정의"""

    # Phase 1: Foundation
    PROGRESSIVE_TRUST = "v2_progressive_trust"

    # Phase 2: Data Source Trust
    DATA_SOURCE_TRUST = "v2_data_source_trust"

    # Phase 3: Knowledge Capitalization
    KNOWLEDGE_CAPTURE = "v2_knowledge_capture"

    # Phase 4: Auto Execution
    AUTO_EXECUTION = "v2_auto_execution"

    # UI Features
    TRUST_DASHBOARD = "v2_trust_dashboard"

    # Enterprise Features
    MULTI_TENANT_CONFIG = "v2_multi_tenant_config"


class FeatureFlagService:
    """
    Feature Flag 관리 서비스

    Redis 키 구조:
    - 글로벌: feature_flag:{feature}:global -> "1" or "0"
    - 테넌트별: feature_flag:{feature}:tenant:{tenant_id} -> "1" or "0"
    - 롤아웃: feature_flag:{feature}:rollout -> 0-100
    """

    PREFIX = "feature_flag"

    # 기본 롤아웃 비율 (새 기능은 0%로 시작)
    DEFAULT_ROLLOUT = 0

    @classmethod
    def _get_global_key(cls, feature: V2Feature) -> str:
        """글로벌 설정 키 생성"""
        return f"{cls.PREFIX}:{feature.value}:global"

    @classmethod
    def _get_tenant_key(cls, feature: V2Feature, tenant_id: str) -> str:
        """테넌트별 설정 키 생성"""
        return f"{cls.PREFIX}:{feature.value}:tenant:{tenant_id}"

    @classmethod
    def _get_rollout_key(cls, feature: V2Feature) -> str:
        """롤아웃 비율 키 생성"""
        return f"{cls.PREFIX}:{feature.value}:rollout"

    @classmethod
    def _is_in_rollout(cls, feature: V2Feature, tenant_id: str) -> bool:
        """
        테넌트가 롤아웃 대상인지 확인 (일관된 해시 기반)

        동일한 tenant_id는 항상 같은 결과를 반환
        """
        percentage = cls.get_rollout_percentage(feature)
        if percentage == 0:
            return False
        if percentage == 100:
            return True

        # tenant_id + feature를 해시하여 0-99 사이 값 생성
        hash_input = f"{tenant_id}:{feature.value}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100

        return bucket < percentage

    @classmethod
    def is_enabled(
        cls,
        feature: V2Feature,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Feature Flag 활성화 여부 확인

        우선순위:
        1. 테넌트별 명시적 설정 (있는 경우)
        2. 글로벌 활성화 설정
        3. 롤아웃 비율 기반 (tenant_id 필요)

        Redis 장애 시 False 반환 (안전한 기본값)

        Args:
            feature: 확인할 V2 기능
            tenant_id: 테넌트 ID (선택)

        Returns:
            bool: 활성화 여부
        """
        try:
            client = CacheService.get_client()
            if client is None:
                logger.debug(f"Redis unavailable, feature {feature.value} disabled")
                return False

            # 1. 테넌트별 명시적 설정 확인
            if tenant_id:
                tenant_key = cls._get_tenant_key(feature, tenant_id)
                tenant_val = client.get(tenant_key)
                if tenant_val is not None:
                    return tenant_val == "1"

            # 2. 글로벌 활성화 설정 확인
            global_key = cls._get_global_key(feature)
            global_val = client.get(global_key)
            if global_val == "1":
                return True

            # 3. 롤아웃 비율 기반 (tenant_id 필요)
            if tenant_id:
                return cls._is_in_rollout(feature, tenant_id)

            return False

        except Exception as e:
            logger.warning(f"Feature flag check error for {feature.value}: {e}")
            return False

    @classmethod
    def enable(
        cls,
        feature: V2Feature,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Feature Flag 활성화

        Args:
            feature: 활성화할 V2 기능
            tenant_id: 테넌트 ID (None이면 글로벌)

        Returns:
            bool: 성공 여부
        """
        try:
            client = CacheService.get_client()
            if client is None:
                logger.error("Redis unavailable, cannot enable feature flag")
                return False

            if tenant_id:
                key = cls._get_tenant_key(feature, tenant_id)
                client.set(key, "1")
                logger.info(f"Feature {feature.value} enabled for tenant {tenant_id}")
            else:
                key = cls._get_global_key(feature)
                client.set(key, "1")
                logger.info(f"Feature {feature.value} enabled globally")

            return True

        except Exception as e:
            logger.error(f"Failed to enable feature {feature.value}: {e}")
            return False

    @classmethod
    def disable(
        cls,
        feature: V2Feature,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Feature Flag 비활성화

        Args:
            feature: 비활성화할 V2 기능
            tenant_id: 테넌트 ID (None이면 글로벌)

        Returns:
            bool: 성공 여부
        """
        try:
            client = CacheService.get_client()
            if client is None:
                logger.error("Redis unavailable, cannot disable feature flag")
                return False

            if tenant_id:
                key = cls._get_tenant_key(feature, tenant_id)
                client.set(key, "0")
                logger.info(f"Feature {feature.value} disabled for tenant {tenant_id}")
            else:
                key = cls._get_global_key(feature)
                client.set(key, "0")
                logger.info(f"Feature {feature.value} disabled globally")

            return True

        except Exception as e:
            logger.error(f"Failed to disable feature {feature.value}: {e}")
            return False

    @classmethod
    def remove_override(
        cls,
        feature: V2Feature,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Feature Flag 오버라이드 제거 (롤아웃 비율 따름)

        Args:
            feature: 오버라이드 제거할 V2 기능
            tenant_id: 테넌트 ID (None이면 글로벌)

        Returns:
            bool: 성공 여부
        """
        try:
            client = CacheService.get_client()
            if client is None:
                logger.error("Redis unavailable, cannot remove override")
                return False

            if tenant_id:
                key = cls._get_tenant_key(feature, tenant_id)
            else:
                key = cls._get_global_key(feature)

            client.delete(key)
            logger.info(f"Feature {feature.value} override removed")
            return True

        except Exception as e:
            logger.error(f"Failed to remove override for {feature.value}: {e}")
            return False

    @classmethod
    def get_rollout_percentage(cls, feature: V2Feature) -> int:
        """
        롤아웃 비율 조회

        Args:
            feature: 조회할 V2 기능

        Returns:
            int: 롤아웃 비율 (0-100)
        """
        try:
            client = CacheService.get_client()
            if client is None:
                return cls.DEFAULT_ROLLOUT

            key = cls._get_rollout_key(feature)
            value = client.get(key)

            if value is None:
                return cls.DEFAULT_ROLLOUT

            return max(0, min(100, int(value)))

        except Exception as e:
            logger.warning(f"Failed to get rollout percentage for {feature.value}: {e}")
            return cls.DEFAULT_ROLLOUT

    @classmethod
    def set_rollout_percentage(
        cls,
        feature: V2Feature,
        percentage: int,
    ) -> bool:
        """
        롤아웃 비율 설정

        Args:
            feature: 설정할 V2 기능
            percentage: 롤아웃 비율 (0-100)

        Returns:
            bool: 성공 여부
        """
        if not 0 <= percentage <= 100:
            logger.error(f"Invalid rollout percentage: {percentage}")
            return False

        try:
            client = CacheService.get_client()
            if client is None:
                logger.error("Redis unavailable, cannot set rollout percentage")
                return False

            key = cls._get_rollout_key(feature)
            client.set(key, str(percentage))
            logger.info(f"Feature {feature.value} rollout set to {percentage}%")
            return True

        except Exception as e:
            logger.error(f"Failed to set rollout percentage for {feature.value}: {e}")
            return False

    @classmethod
    def get_all_flags(
        cls,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Dict]:
        """
        모든 Feature Flag 상태 조회

        Args:
            tenant_id: 테넌트 ID (선택)

        Returns:
            Dict: 각 기능의 상태 정보
        """
        result = {}

        for feature in V2Feature:
            is_active = cls.is_enabled(feature, tenant_id)
            rollout = cls.get_rollout_percentage(feature)

            # 오버라이드 상태 확인
            override_status = cls._get_override_status(feature, tenant_id)

            result[feature.value] = {
                "enabled": is_active,
                "rollout_percentage": rollout,
                "override": override_status,
                "description": cls._get_feature_description(feature),
            }

        return result

    @classmethod
    def _get_override_status(
        cls,
        feature: V2Feature,
        tenant_id: Optional[str] = None,
    ) -> Optional[str]:
        """오버라이드 상태 확인"""
        try:
            client = CacheService.get_client()
            if client is None:
                return None

            # 테넌트별 오버라이드
            if tenant_id:
                tenant_key = cls._get_tenant_key(feature, tenant_id)
                tenant_val = client.get(tenant_key)
                if tenant_val is not None:
                    return "tenant_enabled" if tenant_val == "1" else "tenant_disabled"

            # 글로벌 오버라이드
            global_key = cls._get_global_key(feature)
            global_val = client.get(global_key)
            if global_val is not None:
                return "global_enabled" if global_val == "1" else "global_disabled"

            return None

        except Exception:
            return None

    @classmethod
    def _get_feature_description(cls, feature: V2Feature) -> str:
        """기능 설명 반환"""
        descriptions = {
            V2Feature.PROGRESSIVE_TRUST: "Progressive Trust Model - 4단계 신뢰도 기반 자동화",
            V2Feature.DATA_SOURCE_TRUST: "Data Source Trust - 데이터 소스 품질 평가",
            V2Feature.KNOWLEDGE_CAPTURE: "Knowledge Capture - 지식 자동 캡처 및 학습",
            V2Feature.AUTO_EXECUTION: "Auto Execution - 신뢰도 기반 자동 실행 엔진",
            V2Feature.TRUST_DASHBOARD: "Trust Dashboard - V2 기능 시각화 대시보드",
            V2Feature.MULTI_TENANT_CONFIG: "Multi-Tenant Config - 테넌트별 모듈 설정",
        }
        return descriptions.get(feature, "")


# 편의 함수들
def is_feature_enabled(
    feature: V2Feature,
    tenant_id: Optional[str] = None,
) -> bool:
    """Feature Flag 활성화 여부 확인 (편의 함수)"""
    return FeatureFlagService.is_enabled(feature, tenant_id)


def require_feature(feature: V2Feature):
    """
    FastAPI Dependency - 기능이 활성화되지 않으면 404 반환

    Usage:
        @router.get("/v2/feature")
        async def v2_feature(
            _: None = Depends(require_feature(V2Feature.PROGRESSIVE_TRUST))
        ):
            ...
    """
    from fastapi import HTTPException, Request

    def dependency(request: Request):
        # tenant_id 추출 (헤더 또는 경로에서)
        tenant_id = request.headers.get("X-Tenant-ID")

        if not FeatureFlagService.is_enabled(feature, tenant_id):
            raise HTTPException(
                status_code=404,
                detail={
                    "error": True,
                    "message": f"Feature '{feature.value}' is not available",
                    "code": "FEATURE_NOT_ENABLED",
                }
            )
        return None

    return dependency
