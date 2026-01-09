"""
MCP 래퍼 서버 실행 스크립트

외부 시스템 API를 MCP 표준으로 래핑하는 서버를 실행합니다.

사용법:
    # MES 래퍼 서버 실행
    python -m app.mcp_wrappers.run_wrapper \\
        --type mes \\
        --port 8100 \\
        --target-url http://mes-server.company.com \\
        --api-key YOUR_API_KEY

    # ERP 래퍼 서버 실행
    python -m app.mcp_wrappers.run_wrapper \\
        --type erp \\
        --port 8101 \\
        --target-url http://erp-server.company.com

TriFlow에 등록:
    래퍼 서버 실행 후 TriFlow API로 MCP 서버 등록:

    curl -X POST http://localhost:8000/api/v1/mcp/servers \\
        -H "Authorization: Bearer $TOKEN" \\
        -H "Content-Type: application/json" \\
        -d '{
            "name": "MES Server",
            "base_url": "http://localhost:8100",
            "auth_type": "NONE",
            "timeout_ms": 30000,
            "retry_count": 3
        }'
"""

import argparse
import logging
import sys
from typing import Optional

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app(wrapper_type: str, target_url: str, api_key: Optional[str] = None):
    """
    래퍼 타입에 따른 FastAPI 앱 생성

    Args:
        wrapper_type: 래퍼 타입 (mes, erp)
        target_url: 래핑할 API 서버 URL
        api_key: API 인증 키

    Returns:
        FastAPI 앱
    """
    if wrapper_type == "mes":
        from .mes_wrapper import create_mes_mcp_server
        app, wrapper = create_mes_mcp_server(target_url, api_key)
        logger.info(f"MES MCP Wrapper created for {target_url}")
        return app

    elif wrapper_type == "erp":
        from .erp_wrapper import create_erp_mcp_server
        app, wrapper = create_erp_mcp_server(target_url, api_key)
        logger.info(f"ERP MCP Wrapper created for {target_url}")
        return app

    else:
        raise ValueError(f"Unknown wrapper type: {wrapper_type}")


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(
        description="MCP 래퍼 서버 실행",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # MES 래퍼 서버 실행
  python -m app.mcp_wrappers.run_wrapper --type mes --port 8100 --target-url http://mes-server:8080

  # ERP 래퍼 서버 실행 (API 키 사용)
  python -m app.mcp_wrappers.run_wrapper --type erp --port 8101 --target-url http://erp-server:8080 --api-key SECRET

지원 래퍼 타입:
  mes   - MES (Manufacturing Execution System) 래퍼
  erp   - ERP (Enterprise Resource Planning) 래퍼
        """
    )

    parser.add_argument(
        "--type",
        choices=["mes", "erp"],
        required=True,
        help="래퍼 타입 (mes 또는 erp)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8100,
        help="서버 포트 (기본값: 8100)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="서버 호스트 (기본값: 0.0.0.0)"
    )
    parser.add_argument(
        "--target-url",
        required=True,
        help="래핑할 API 서버 URL (예: http://mes-server.company.com)"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API 인증 키 (선택)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="개발 모드: 코드 변경 시 자동 재시작"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="워커 프로세스 수 (기본값: 1)"
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="로그 레벨 (기본값: info)"
    )

    args = parser.parse_args()

    # 앱 생성
    try:
        app = create_app(args.type, args.target_url, args.api_key)
    except Exception as e:
        logger.error(f"Failed to create app: {e}")
        sys.exit(1)

    # 서버 시작 정보 출력
    logger.info("=" * 60)
    logger.info("MCP Wrapper Server Starting")
    logger.info(f"  Type: {args.type.upper()}")
    logger.info(f"  Host: {args.host}")
    logger.info(f"  Port: {args.port}")
    logger.info(f"  Target URL: {args.target_url}")
    logger.info(f"  API Key: {'*****' if args.api_key else 'None'}")
    logger.info("=" * 60)
    logger.info("MCP Endpoints:")
    logger.info(f"  POST http://{args.host}:{args.port}/tools/list")
    logger.info(f"  POST http://{args.host}:{args.port}/tools/call")
    logger.info(f"  GET  http://{args.host}:{args.port}/health")
    logger.info("=" * 60)

    # 서버 실행
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level
    )


if __name__ == "__main__":
    main()
