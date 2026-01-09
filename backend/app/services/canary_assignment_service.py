# -*- coding: utf-8 -*-
"""Canary Assignment Service

Sticky Session 기반 Canary 버전 할당 서비스.

3계층 캐싱 전략:
1. JWT 클레임 (로그인 사용자) - 가장 빠름
2. Redis (세션/비로그인) - 24시간 TTL
3. DB (최종 fallback)

3단계 Sticky 우선순위:
1. workflow_instance - 워크플로우 실행 중 버전 고정 (만료 없음)
2. session - 브라우저 세션 내 일관성 (24시간 TTL)
3. user - 로그인 사용자 (24시간 TTL)
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import RuleDeployment
from app.models.canary import CanaryAssignment
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

# 타입 정의
CanaryVersion = Literal["v1", "v2"]
IdentifierType = Literal["user", "session", "workflow_instance"]
ResolutionSource = Literal["jwt_cache", "redis_cache", "db", "new_assignment"]

# 캐시 설정
CANARY_CACHE_TTL = 86400  # 24시간
CANARY_CACHE_PREFIX = "canary:assignment"


class CanaryAssignmentService:
    """Canary 버전 할당 서비스"""

    def __init__(self, db: Session):
        self.db = db

    # ============================================
    # 버전 결정 (3계층 캐싱)
    # ============================================

    def resolve_version(
        self,
        deployment_id: UUID,
        tenant_id: UUID,
        *,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        workflow_instance_id: Optional[UUID] = None,
        jwt_cached_version: Optional[CanaryVersion] = None,
    ) -> tuple[CanaryVersion, ResolutionSource, str, IdentifierType]:
        """
        Canary 버전 결정 (3계층 캐싱).

        Returns:
            (version, source, identifier, identifier_type)
        """
        # 1. JWT 캐시 확인 (가장 빠름)
        if jwt_cached_version:
            identifier = str(user_id) if user_id else session_id or "unknown"
            identifier_type: IdentifierType = "user" if user_id else "session"
            logger.debug(f"Using JWT cached version: {jwt_cached_version}")
            return jwt_cached_version, "jwt_cache", identifier, identifier_type

        # 2. 우선순위에 따른 식별자 결정
        identifier, identifier_type = self._determine_identifier(
            user_id=user_id,
            session_id=session_id,
            workflow_instance_id=workflow_instance_id,
        )

        # 3. Redis 캐시 확인
        cached = self._get_from_redis(deployment_id, identifier)
        if cached:
            logger.debug(f"Using Redis cached version: {cached}")
            return cached, "redis_cache", identifier, identifier_type

        # 4. DB 확인
        assignment = self._get_from_db(deployment_id, identifier)
        if assignment and not assignment.is_expired:
            # Redis에 캐싱
            self._set_to_redis(deployment_id, identifier, assignment.assigned_version)
            logger.debug(f"Using DB assignment: {assignment.assigned_version}")
            return assignment.assigned_version, "db", identifier, identifier_type

        # 5. 신규 할당
        deployment = self._get_deployment(deployment_id)
        if not deployment or not deployment.is_canary_active:
            return "v1", "new_assignment", identifier, identifier_type

        version = self._calculate_version(deployment, identifier)

        # DB에 저장
        self._create_assignment(
            tenant_id=tenant_id,
            deployment_id=deployment_id,
            identifier=identifier,
            identifier_type=identifier_type,
            version=version,
        )

        # Redis에 캐싱
        self._set_to_redis(deployment_id, identifier, version)

        logger.info(
            f"New canary assignment: deployment={deployment_id}, "
            f"identifier={identifier}, version={version}"
        )
        return version, "new_assignment", identifier, identifier_type

    def resolve_version_for_jwt(
        self,
        tenant_id: UUID,
        user_id: UUID,
    ) -> dict[str, CanaryVersion]:
        """
        JWT 생성 시 활성 Canary 배포의 버전 정보 반환.

        Returns:
            {deployment_id: version} 딕셔너리
        """
        assignments: dict[str, CanaryVersion] = {}

        # 활성 Canary 배포 조회
        active_deployments = self.db.query(RuleDeployment).filter(
            RuleDeployment.tenant_id == tenant_id,
            RuleDeployment.status == "canary",
        ).all()

        for deployment in active_deployments:
            version, _, _, _ = self.resolve_version(
                deployment_id=deployment.deployment_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            assignments[str(deployment.deployment_id)] = version

        return assignments

    # ============================================
    # 내부 메서드
    # ============================================

    def _determine_identifier(
        self,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        workflow_instance_id: Optional[UUID] = None,
    ) -> tuple[str, IdentifierType]:
        """우선순위에 따른 식별자 결정"""
        # 우선순위: workflow_instance > session > user
        if workflow_instance_id:
            return str(workflow_instance_id), "workflow_instance"
        if session_id:
            return session_id, "session"
        if user_id:
            return str(user_id), "user"
        raise ValueError("user_id, session_id, 또는 workflow_instance_id 중 하나는 필수입니다")

    def _get_deployment(self, deployment_id: UUID) -> Optional[RuleDeployment]:
        """배포 조회"""
        return self.db.query(RuleDeployment).filter(
            RuleDeployment.deployment_id == deployment_id
        ).first()

    def _calculate_version(
        self,
        deployment: RuleDeployment,
        identifier: str,
    ) -> CanaryVersion:
        """결정론적 해싱으로 버전 계산"""
        # MD5 해시로 0-99 범위의 버킷 결정
        hash_input = f"{deployment.deployment_id}:{identifier}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16) % 100

        canary_pct_int = int((deployment.canary_pct or 0) * 100)

        if hash_value < canary_pct_int:
            return "v2"  # Canary
        return "v1"  # Stable

    # ============================================
    # Redis 캐싱
    # ============================================

    def _get_redis_key(self, deployment_id: UUID, identifier: str) -> str:
        """Redis 캐시 키 생성"""
        return f"{CANARY_CACHE_PREFIX}:{deployment_id}:{identifier}"

    def _get_from_redis(
        self,
        deployment_id: UUID,
        identifier: str,
    ) -> Optional[CanaryVersion]:
        """Redis에서 버전 조회"""
        if not CacheService.is_available():
            return None

        key = self._get_redis_key(deployment_id, identifier)
        try:
            value = CacheService.get(key)
            if value and value in ("v1", "v2"):
                return value
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
        return None

    def _set_to_redis(
        self,
        deployment_id: UUID,
        identifier: str,
        version: CanaryVersion,
    ) -> bool:
        """Redis에 버전 저장"""
        if not CacheService.is_available():
            return False

        key = self._get_redis_key(deployment_id, identifier)
        try:
            CacheService.set(key, version, ttl=CANARY_CACHE_TTL)
            return True
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
            return False

    def _delete_from_redis(
        self,
        deployment_id: UUID,
        identifier: str,
    ) -> bool:
        """Redis에서 삭제"""
        if not CacheService.is_available():
            return False

        key = self._get_redis_key(deployment_id, identifier)
        try:
            CacheService.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")
            return False

    # ============================================
    # DB 조회/저장
    # ============================================

    def _get_from_db(
        self,
        deployment_id: UUID,
        identifier: str,
    ) -> Optional[CanaryAssignment]:
        """DB에서 할당 조회"""
        return self.db.query(CanaryAssignment).filter(
            CanaryAssignment.deployment_id == deployment_id,
            CanaryAssignment.identifier == identifier,
        ).first()

    def _create_assignment(
        self,
        tenant_id: UUID,
        deployment_id: UUID,
        identifier: str,
        identifier_type: IdentifierType,
        version: CanaryVersion,
    ) -> CanaryAssignment:
        """할당 생성"""
        # 만료 시간 설정
        expires_at = None
        if identifier_type in ("user", "session"):
            expires_at = datetime.utcnow() + timedelta(hours=24)
        # workflow_instance는 만료 없음

        assignment = CanaryAssignment(
            tenant_id=tenant_id,
            deployment_id=deployment_id,
            identifier=identifier,
            identifier_type=identifier_type,
            assigned_version=version,
            expires_at=expires_at,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    # ============================================
    # 할당 관리
    # ============================================

    def get_assignment(
        self,
        deployment_id: UUID,
        identifier: str,
    ) -> Optional[CanaryAssignment]:
        """할당 조회"""
        return self._get_from_db(deployment_id, identifier)

    def list_assignments(
        self,
        deployment_id: UUID,
        *,
        identifier_type: Optional[IdentifierType] = None,
        version: Optional[CanaryVersion] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[CanaryAssignment], int]:
        """할당 목록 조회"""
        query = self.db.query(CanaryAssignment).filter(
            CanaryAssignment.deployment_id == deployment_id
        )

        if identifier_type:
            query = query.filter(CanaryAssignment.identifier_type == identifier_type)
        if version:
            query = query.filter(CanaryAssignment.assigned_version == version)

        total = query.count()
        assignments = query.order_by(
            CanaryAssignment.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()

        return assignments, total

    def delete_assignment(
        self,
        deployment_id: UUID,
        identifier: str,
    ) -> bool:
        """할당 삭제 (재할당 허용)"""
        assignment = self._get_from_db(deployment_id, identifier)
        if not assignment:
            return False

        self.db.delete(assignment)
        self.db.commit()

        # Redis 캐시도 삭제
        self._delete_from_redis(deployment_id, identifier)

        return True

    def delete_all_assignments(self, deployment_id: UUID) -> int:
        """배포의 모든 할당 삭제"""
        # 먼저 모든 할당 조회 (Redis 캐시 삭제용)
        assignments = self.db.query(CanaryAssignment).filter(
            CanaryAssignment.deployment_id == deployment_id
        ).all()

        count = len(assignments)

        # Redis 캐시 삭제
        for assignment in assignments:
            self._delete_from_redis(deployment_id, assignment.identifier)

        # DB 삭제
        self.db.query(CanaryAssignment).filter(
            CanaryAssignment.deployment_id == deployment_id
        ).delete()
        self.db.commit()

        logger.info(f"Deleted {count} assignments for deployment {deployment_id}")
        return count

    def cleanup_expired(self) -> int:
        """만료된 할당 정리"""
        now = datetime.utcnow()
        result = self.db.query(CanaryAssignment).filter(
            CanaryAssignment.expires_at.isnot(None),
            CanaryAssignment.expires_at < now,
        ).delete()
        self.db.commit()
        logger.info(f"Cleaned up {result} expired assignments")
        return result

    # ============================================
    # 캐시 무효화
    # ============================================

    def invalidate_deployment_cache(self, deployment_id: UUID) -> None:
        """배포의 모든 Redis 캐시 무효화"""
        if not CacheService.is_available():
            return

        try:
            client = CacheService.get_client()
            if client:
                pattern = f"{CANARY_CACHE_PREFIX}:{deployment_id}:*"
                keys = list(client.scan_iter(match=pattern))
                if keys:
                    client.delete(*keys)
                    logger.info(f"Invalidated {len(keys)} cache keys for deployment {deployment_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

    def invalidate_user_cache(
        self,
        deployment_id: UUID,
        user_id: UUID,
    ) -> None:
        """특정 사용자의 캐시 무효화"""
        self._delete_from_redis(deployment_id, str(user_id))

    # ============================================
    # 통계
    # ============================================

    def get_assignment_stats(
        self,
        deployment_id: UUID,
    ) -> dict:
        """할당 통계"""
        from sqlalchemy import func

        stats = self.db.query(
            CanaryAssignment.assigned_version,
            func.count(CanaryAssignment.assignment_id).label("count"),
        ).filter(
            CanaryAssignment.deployment_id == deployment_id
        ).group_by(
            CanaryAssignment.assigned_version
        ).all()

        result = {"v1": 0, "v2": 0, "total": 0}
        for version, count in stats:
            result[version] = count
            result["total"] += count

        return result
