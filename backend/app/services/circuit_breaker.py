"""
Circuit Breaker Service

스펙 참조: B-2-3_MCP_DataHub_Chat_Design.md

Circuit Breaker 패턴:
- CLOSED (정상): 모든 요청 통과
- OPEN (차단): 모든 요청 거부 (빠른 실패)
- HALF_OPEN (테스트): 일부 요청만 통과하여 상태 확인

상태 전이:
- CLOSED → OPEN: 연속 실패 >= failure_threshold
- OPEN → HALF_OPEN: timeout_seconds 경과 후
- HALF_OPEN → CLOSED: 연속 성공 >= success_threshold
- HALF_OPEN → OPEN: 실패 발생 시
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import (
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreakerStateEnum,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class CircuitBreakerOpenError(Exception):
    """Circuit Breaker가 OPEN 상태일 때 발생하는 예외"""

    def __init__(self, server_id: UUID, opened_at: datetime | None = None):
        self.server_id = server_id
        self.opened_at = opened_at
        super().__init__(f"Circuit breaker is OPEN for server {server_id}")


class CircuitBreaker:
    """
    Circuit Breaker 구현

    DB 기반 상태 저장 + Redis 캐싱 (선택적)
    """

    # 기본 설정
    DEFAULT_FAILURE_THRESHOLD = 5
    DEFAULT_SUCCESS_THRESHOLD = 2
    DEFAULT_TIMEOUT_SECONDS = 60

    # Redis 캐시 TTL (초)
    CACHE_TTL = 10

    def __init__(
        self,
        db: AsyncSession,
        redis: "Redis | None" = None,
        config: CircuitBreakerConfig | None = None,
    ):
        self.db = db
        self.redis = redis
        self.config = config or CircuitBreakerConfig()

    async def get_state(self, server_id: UUID) -> CircuitBreakerState | None:
        """Circuit Breaker 상태 조회"""
        # Redis 캐시 확인 (있으면)
        if self.redis:
            cached = await self._get_cached_state(server_id)
            if cached:
                return cached

        # DB 조회
        query = text("""
            SELECT server_id, state, failure_count, success_count,
                   consecutive_failures, consecutive_successes,
                   failure_threshold, success_threshold, timeout_seconds,
                   last_failure_at, last_success_at, opened_at, half_opened_at,
                   updated_at
            FROM core.circuit_breaker_states
            WHERE server_id = :server_id
        """)

        result = await self.db.execute(query, {"server_id": str(server_id)})
        row = result.fetchone()

        if not row:
            return None

        state = CircuitBreakerState(
            server_id=row.server_id,
            state=CircuitBreakerStateEnum(row.state),
            failure_count=row.failure_count,
            success_count=row.success_count,
            consecutive_failures=row.consecutive_failures,
            consecutive_successes=row.consecutive_successes,
            failure_threshold=row.failure_threshold,
            success_threshold=row.success_threshold,
            timeout_seconds=row.timeout_seconds,
            last_failure_at=row.last_failure_at,
            last_success_at=row.last_success_at,
            opened_at=row.opened_at,
            half_opened_at=row.half_opened_at,
            updated_at=row.updated_at,
        )

        # Redis 캐시 저장
        if self.redis:
            await self._cache_state(state)

        return state

    async def is_open(self, server_id: UUID) -> bool:
        """
        Circuit Breaker가 OPEN 상태인지 확인

        OPEN 상태이고 타임아웃이 경과했으면 HALF_OPEN으로 전환
        """
        state = await self.get_state(server_id)

        if not state:
            # 상태 없음 = CLOSED (첫 요청)
            return False

        if state.state == CircuitBreakerStateEnum.CLOSED:
            return False

        if state.state == CircuitBreakerStateEnum.HALF_OPEN:
            return False

        # OPEN 상태
        if state.state == CircuitBreakerStateEnum.OPEN:
            # 타임아웃 경과 확인
            if state.opened_at:
                timeout_at = state.opened_at + timedelta(seconds=state.timeout_seconds)
                now = datetime.now(timezone.utc)

                # opened_at에 timezone이 없으면 UTC로 가정
                if state.opened_at.tzinfo is None:
                    timeout_at = state.opened_at.replace(tzinfo=timezone.utc) + timedelta(
                        seconds=state.timeout_seconds
                    )

                if now >= timeout_at:
                    # HALF_OPEN으로 전환
                    await self._try_half_open(server_id)
                    return False

            return True

        return False

    async def record_success(self, server_id: UUID) -> None:
        """성공 기록"""
        # DB 함수 호출
        query = text("SELECT update_circuit_breaker_on_success(:server_id)")
        await self.db.execute(query, {"server_id": str(server_id)})
        await self.db.commit()

        # 캐시 무효화
        if self.redis:
            await self._invalidate_cache(server_id)

        logger.debug(f"Circuit breaker success recorded for server {server_id}")

    async def record_failure(self, server_id: UUID) -> None:
        """실패 기록"""
        # DB 함수 호출
        query = text("SELECT update_circuit_breaker_on_failure(:server_id)")
        await self.db.execute(query, {"server_id": str(server_id)})
        await self.db.commit()

        # 캐시 무효화
        if self.redis:
            await self._invalidate_cache(server_id)

        logger.debug(f"Circuit breaker failure recorded for server {server_id}")

    async def reset(self, server_id: UUID) -> None:
        """Circuit Breaker 상태 리셋 (CLOSED로)"""
        query = text("""
            UPDATE core.circuit_breaker_states
            SET state = 'CLOSED',
                consecutive_failures = 0,
                consecutive_successes = 0,
                opened_at = NULL,
                half_opened_at = NULL,
                updated_at = now()
            WHERE server_id = :server_id
        """)
        await self.db.execute(query, {"server_id": str(server_id)})
        await self.db.commit()

        # 캐시 무효화
        if self.redis:
            await self._invalidate_cache(server_id)

        logger.info(f"Circuit breaker reset for server {server_id}")

    async def initialize(
        self,
        server_id: UUID,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreakerState:
        """새 서버에 대한 Circuit Breaker 초기화"""
        cfg = config or self.config

        query = text("""
            INSERT INTO core.circuit_breaker_states (
                server_id, state, failure_threshold, success_threshold, timeout_seconds
            )
            VALUES (:server_id, 'CLOSED', :failure_threshold, :success_threshold, :timeout_seconds)
            ON CONFLICT (server_id) DO NOTHING
            RETURNING server_id, state, failure_count, success_count,
                      consecutive_failures, consecutive_successes,
                      failure_threshold, success_threshold, timeout_seconds,
                      last_failure_at, last_success_at, opened_at, half_opened_at,
                      updated_at
        """)

        result = await self.db.execute(
            query,
            {
                "server_id": str(server_id),
                "failure_threshold": cfg.failure_threshold,
                "success_threshold": cfg.success_threshold,
                "timeout_seconds": cfg.timeout_seconds,
            },
        )
        await self.db.commit()

        row = result.fetchone()
        if row:
            return CircuitBreakerState(
                server_id=row.server_id,
                state=CircuitBreakerStateEnum(row.state),
                failure_count=row.failure_count,
                success_count=row.success_count,
                consecutive_failures=row.consecutive_failures,
                consecutive_successes=row.consecutive_successes,
                failure_threshold=row.failure_threshold,
                success_threshold=row.success_threshold,
                timeout_seconds=row.timeout_seconds,
                last_failure_at=row.last_failure_at,
                last_success_at=row.last_success_at,
                opened_at=row.opened_at,
                half_opened_at=row.half_opened_at,
                updated_at=row.updated_at,
            )

        # ON CONFLICT DO NOTHING 이 발동되면 기존 상태 반환
        state = await self.get_state(server_id)
        if state:
            return state

        raise RuntimeError(f"Failed to initialize circuit breaker for server {server_id}")

    async def update_config(
        self,
        server_id: UUID,
        config: CircuitBreakerConfig,
    ) -> None:
        """Circuit Breaker 설정 업데이트"""
        query = text("""
            UPDATE core.circuit_breaker_states
            SET failure_threshold = :failure_threshold,
                success_threshold = :success_threshold,
                timeout_seconds = :timeout_seconds,
                updated_at = now()
            WHERE server_id = :server_id
        """)
        await self.db.execute(
            query,
            {
                "server_id": str(server_id),
                "failure_threshold": config.failure_threshold,
                "success_threshold": config.success_threshold,
                "timeout_seconds": config.timeout_seconds,
            },
        )
        await self.db.commit()

        # 캐시 무효화
        if self.redis:
            await self._invalidate_cache(server_id)

    async def _try_half_open(self, server_id: UUID) -> bool:
        """OPEN → HALF_OPEN 전환 시도"""
        query = text("SELECT try_half_open_circuit_breaker(:server_id)")
        result = await self.db.execute(query, {"server_id": str(server_id)})
        await self.db.commit()

        row = result.fetchone()
        success = row[0] if row else False

        if success:
            logger.info(f"Circuit breaker transitioned to HALF_OPEN for server {server_id}")

            # 캐시 무효화
            if self.redis:
                await self._invalidate_cache(server_id)

        return success

    # =========================================
    # Redis Cache Helpers
    # =========================================
    def _cache_key(self, server_id: UUID) -> str:
        return f"cb:state:{server_id}"

    async def _get_cached_state(self, server_id: UUID) -> CircuitBreakerState | None:
        """Redis에서 캐시된 상태 조회"""
        if not self.redis:
            return None

        try:
            import json

            key = self._cache_key(server_id)
            data = await self.redis.get(key)

            if data:
                parsed = json.loads(data)
                return CircuitBreakerState.model_validate(parsed)
        except Exception as e:
            logger.warning(f"Failed to get cached circuit breaker state: {e}")

        return None

    async def _cache_state(self, state: CircuitBreakerState) -> None:
        """Redis에 상태 캐싱"""
        if not self.redis:
            return

        try:
            import json

            key = self._cache_key(state.server_id)
            data = state.model_dump_json()
            await self.redis.setex(key, self.CACHE_TTL, data)
        except Exception as e:
            logger.warning(f"Failed to cache circuit breaker state: {e}")

    async def _invalidate_cache(self, server_id: UUID) -> None:
        """Redis 캐시 무효화"""
        if not self.redis:
            return

        try:
            key = self._cache_key(server_id)
            await self.redis.delete(key)
        except Exception as e:
            logger.warning(f"Failed to invalidate circuit breaker cache: {e}")


# =========================================
# In-Memory Circuit Breaker (테스트용)
# =========================================
class InMemoryCircuitBreaker:
    """
    인메모리 Circuit Breaker (테스트 및 단순 사용 케이스용)

    DB 없이 메모리에서 상태 관리
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        self.config = config or CircuitBreakerConfig()
        self._states: dict[UUID, dict] = {}

    def _get_or_create_state(self, server_id: UUID) -> dict:
        if server_id not in self._states:
            self._states[server_id] = {
                "state": CircuitBreakerStateEnum.CLOSED,
                "failure_count": 0,
                "success_count": 0,
                "consecutive_failures": 0,
                "consecutive_successes": 0,
                "opened_at": None,
                "half_opened_at": None,
                "last_failure_at": None,
                "last_success_at": None,
            }
        return self._states[server_id]

    async def is_open(self, server_id: UUID) -> bool:
        state = self._get_or_create_state(server_id)

        if state["state"] == CircuitBreakerStateEnum.CLOSED:
            return False

        if state["state"] == CircuitBreakerStateEnum.HALF_OPEN:
            return False

        if state["state"] == CircuitBreakerStateEnum.OPEN:
            # 타임아웃 확인
            if state["opened_at"]:
                timeout_at = state["opened_at"] + timedelta(seconds=self.config.timeout_seconds)
                if datetime.now(timezone.utc) >= timeout_at:
                    state["state"] = CircuitBreakerStateEnum.HALF_OPEN
                    state["half_opened_at"] = datetime.now(timezone.utc)
                    state["consecutive_successes"] = 0
                    return False
            return True

        return False

    async def record_success(self, server_id: UUID) -> None:
        state = self._get_or_create_state(server_id)
        state["success_count"] += 1
        state["consecutive_successes"] += 1
        state["consecutive_failures"] = 0
        state["last_success_at"] = datetime.now(timezone.utc)

        if state["state"] == CircuitBreakerStateEnum.HALF_OPEN:
            if state["consecutive_successes"] >= self.config.success_threshold:
                state["state"] = CircuitBreakerStateEnum.CLOSED
                state["consecutive_successes"] = 0

    async def record_failure(self, server_id: UUID) -> None:
        state = self._get_or_create_state(server_id)
        state["failure_count"] += 1
        state["consecutive_failures"] += 1
        state["consecutive_successes"] = 0
        state["last_failure_at"] = datetime.now(timezone.utc)

        if state["state"] == CircuitBreakerStateEnum.CLOSED:
            if state["consecutive_failures"] >= self.config.failure_threshold:
                state["state"] = CircuitBreakerStateEnum.OPEN
                state["opened_at"] = datetime.now(timezone.utc)

        elif state["state"] == CircuitBreakerStateEnum.HALF_OPEN:
            state["state"] = CircuitBreakerStateEnum.OPEN
            state["opened_at"] = datetime.now(timezone.utc)

    async def get_state(self, server_id: UUID) -> CircuitBreakerState:
        s = self._get_or_create_state(server_id)
        return CircuitBreakerState(
            server_id=server_id,
            state=s["state"],
            failure_count=s["failure_count"],
            success_count=s["success_count"],
            consecutive_failures=s["consecutive_failures"],
            consecutive_successes=s["consecutive_successes"],
            failure_threshold=self.config.failure_threshold,
            success_threshold=self.config.success_threshold,
            timeout_seconds=self.config.timeout_seconds,
            last_failure_at=s["last_failure_at"],
            last_success_at=s["last_success_at"],
            opened_at=s["opened_at"],
            half_opened_at=s["half_opened_at"],
            updated_at=datetime.now(timezone.utc),
        )

    async def reset(self, server_id: UUID) -> None:
        if server_id in self._states:
            del self._states[server_id]
