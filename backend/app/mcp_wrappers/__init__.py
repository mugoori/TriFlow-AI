"""
MCP 래퍼 서버 패키지

외부 시스템 API(MES, ERP 등)를 MCP 표준 형식으로 래핑합니다.
TriFlow의 MCP 인프라(Circuit Breaker, Retry, 통계)와 자동 통합됩니다.

사용법:
    python -m app.mcp_wrappers.run_wrapper --type mes --port 8100 --target-url http://mes-server.com
"""

from .base_wrapper import MCPWrapperBase, MCPToolDefinition, create_mcp_app
from .mes_wrapper import MESWrapper, create_mes_mcp_server
from .erp_wrapper import ERPWrapper, create_erp_mcp_server

__all__ = [
    "MCPWrapperBase",
    "MCPToolDefinition",
    "create_mcp_app",
    "MESWrapper",
    "create_mes_mcp_server",
    "ERPWrapper",
    "create_erp_mcp_server",
]
