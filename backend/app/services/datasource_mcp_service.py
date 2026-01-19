"""
DataSource 기반 MCP 도구 관리 서비스

DataSource에 등록된 연결 정보를 기반으로 MES/ERP MCP 도구를 동적으로 생성하고 호출합니다.

사용 흐름:
1. 관리자가 DataSource 등록 (URL, 인증 정보)
2. 시스템이 source_type에 맞는 MCP 도구 자동 생성
3. 워크플로우/챗에서 도구 사용

관련 파일:
- mcp_wrappers/mes_wrapper.py: MES 도구 정의
- mcp_wrappers/erp_wrapper.py: ERP 도구 정의
- models/core.py: DataSource 모델
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.core import DataSource
from app.mcp_wrappers.base_wrapper import MCPToolDefinition
from app.mcp_wrappers.mes_wrapper import MESWrapper
from app.mcp_wrappers.erp_wrapper import ERPWrapper

logger = logging.getLogger(__name__)


class DataSourceMCPService:
    """
    DataSource 기반 동적 MCP 도구 관리

    - DataSource 등록 정보를 기반으로 MES/ERP 래퍼 인스턴스 생성
    - 도구 호출 시 해당 래퍼 사용
    - 캐싱으로 래퍼 재사용 (성능 최적화)
    """

    def __init__(self, db: Session):
        self.db = db
        self._wrapper_cache: Dict[UUID, Any] = {}  # source_id -> wrapper instance

    def get_source(self, source_id: UUID, tenant_id: UUID) -> Optional[DataSource]:
        """DataSource 조회"""
        return self.db.query(DataSource).filter(
            DataSource.source_id == source_id,
            DataSource.tenant_id == tenant_id,
            DataSource.is_active is True
        ).first()

    def get_active_sources(self, tenant_id: UUID, source_type: Optional[str] = None) -> List[DataSource]:
        """활성화된 DataSource 목록 조회"""
        query = self.db.query(DataSource).filter(
            DataSource.tenant_id == tenant_id,
            DataSource.is_active is True
        )
        if source_type:
            query = query.filter(DataSource.source_type == source_type)
        return query.all()

    def get_tools_for_source_type(self, source_type: str) -> List[MCPToolDefinition]:
        """source_type에 해당하는 도구 목록 반환 (정적)"""
        if source_type == "mes":
            # MESWrapper의 도구 정의 가져오기 (인스턴스 없이)
            dummy_wrapper = MESWrapper.__new__(MESWrapper)
            dummy_wrapper.name = "MES"
            dummy_wrapper._tools_cache = None
            return dummy_wrapper.get_tools()
        elif source_type == "erp":
            dummy_wrapper = ERPWrapper.__new__(ERPWrapper)
            dummy_wrapper.name = "ERP"
            dummy_wrapper._tools_cache = None
            return dummy_wrapper.get_tools()
        return []

    def get_all_tools_for_tenant(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """
        테넌트의 모든 DataSource에 대한 도구 목록 반환

        Returns:
            [
                {
                    "source_id": "...",
                    "source_name": "A공장 MES",
                    "source_type": "mes",
                    "tools": [MCPToolDefinition, ...]
                },
                ...
            ]
        """
        sources = self.get_active_sources(tenant_id)
        result = []

        for source in sources:
            tools = self.get_tools_for_source_type(source.source_type)
            result.append({
                "source_id": str(source.source_id),
                "source_name": source.name,
                "source_type": source.source_type,
                "source_system": source.source_system,
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "input_schema": t.input_schema,
                        # 전체 도구 이름: {source_type}_{source_name}_{tool_name}
                        "full_name": f"{source.source_type}_{source.name}_{t.name}"
                    }
                    for t in tools
                ]
            })

        return result

    def _get_or_create_wrapper(self, source: DataSource) -> Any:
        """래퍼 인스턴스 가져오기 또는 생성 (캐시 사용)"""
        if source.source_id in self._wrapper_cache:
            return self._wrapper_cache[source.source_id]

        config = source.connection_config or {}
        base_url = config.get("base_url", "")
        api_key = config.get("api_key")
        timeout = config.get("timeout", 30.0)

        if not base_url:
            raise ValueError(f"DataSource '{source.name}'에 base_url이 설정되지 않았습니다.")

        if source.source_type == "mes":
            wrapper = MESWrapper(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout
            )
        elif source.source_type == "erp":
            wrapper = ERPWrapper(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout
            )
        else:
            raise ValueError(f"지원하지 않는 source_type: {source.source_type}")

        self._wrapper_cache[source.source_id] = wrapper
        logger.info(f"Created wrapper for DataSource: {source.name} ({source.source_type})")
        return wrapper

    def invalidate_cache(self, source_id: UUID):
        """래퍼 캐시 무효화 (설정 변경 시)"""
        if source_id in self._wrapper_cache:
            self._wrapper_cache.pop(source_id)
            # 비동기 클라이언트 정리는 별도 처리 필요
            logger.info(f"Invalidated wrapper cache for source_id: {source_id}")

    async def call_tool(
        self,
        source_id: UUID,
        tenant_id: UUID,
        tool_name: str,
        args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        DataSource 설정을 사용해 MCP 도구 실행

        Args:
            source_id: DataSource ID
            tenant_id: 테넌트 ID (권한 검증용)
            tool_name: 도구 이름 (예: "get_production_status")
            args: 도구 인자

        Returns:
            도구 실행 결과
        """
        # 1. DataSource 조회
        source = self.get_source(source_id, tenant_id)
        if not source:
            return {
                "success": False,
                "error": f"DataSource not found: {source_id}"
            }

        # 2. 래퍼 인스턴스 가져오기
        try:
            wrapper = self._get_or_create_wrapper(source)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }

        # 3. 도구 유효성 검사
        if not wrapper.validate_tool_name(tool_name):
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name} for source_type: {source.source_type}"
            }

        # 4. 도구 실행
        try:
            logger.info(
                f"Calling tool: {tool_name} on DataSource: {source.name} "
                f"(type: {source.source_type}) with args: {args}"
            )

            start_time = datetime.utcnow()
            result = await wrapper.call_tool(tool_name, args)
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # 동기화 상태 업데이트
            source.last_sync_at = datetime.utcnow()
            source.last_sync_status = "success"
            source.last_sync_error = None
            self.db.commit()

            return {
                "success": True,
                "data": result,
                "latency_ms": latency_ms,
                "source_name": source.name
            }

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {e}")

            # 에러 상태 업데이트
            source.last_sync_at = datetime.utcnow()
            source.last_sync_status = "error"
            source.last_sync_error = str(e)
            self.db.commit()

            return {
                "success": False,
                "error": str(e),
                "source_name": source.name
            }

    async def health_check(
        self,
        source_id: UUID,
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """
        DataSource 연결 상태 확인

        Returns:
            {
                "status": "healthy" | "unhealthy",
                "latency_ms": int,
                "error": str (optional)
            }
        """
        source = self.get_source(source_id, tenant_id)
        if not source:
            return {
                "status": "unhealthy",
                "error": f"DataSource not found: {source_id}"
            }

        try:
            wrapper = self._get_or_create_wrapper(source)

            start_time = datetime.utcnow()
            result = await wrapper.health_check()
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            return {
                "status": result.get("status", "unknown"),
                "latency_ms": latency_ms,
                "target_url": source.connection_config.get("base_url"),
                "source_name": source.name,
                "source_type": source.source_type
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "source_name": source.name
            }

    async def close_all(self):
        """모든 래퍼의 HTTP 클라이언트 종료"""
        for source_id, wrapper in self._wrapper_cache.items():
            try:
                await wrapper.close()
            except Exception as e:
                logger.warning(f"Failed to close wrapper {source_id}: {e}")
        self._wrapper_cache.clear()
