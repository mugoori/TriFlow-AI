"""
MCP 래퍼 서버 실행 스크립트 테스트
app/mcp_wrappers/run_wrapper.py 테스트
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI


# ========== create_app 테스트 ==========


class TestCreateApp:
    """create_app 함수 테스트"""

    def test_create_app_mes(self):
        """MES 래퍼 앱 생성"""
        from app.mcp_wrappers.run_wrapper import create_app

        with patch("app.mcp_wrappers.mes_wrapper.create_mes_mcp_server") as mock_create:
            mock_app = FastAPI()
            mock_wrapper = MagicMock()
            mock_create.return_value = (mock_app, mock_wrapper)

            result = create_app("mes", "http://mes.example.com", "api-key")

            assert result == mock_app
            mock_create.assert_called_once_with("http://mes.example.com", "api-key")

    def test_create_app_erp(self):
        """ERP 래퍼 앱 생성"""
        from app.mcp_wrappers.run_wrapper import create_app

        with patch("app.mcp_wrappers.erp_wrapper.create_erp_mcp_server") as mock_create:
            mock_app = FastAPI()
            mock_wrapper = MagicMock()
            mock_create.return_value = (mock_app, mock_wrapper)

            result = create_app("erp", "http://erp.example.com", None)

            assert result == mock_app
            mock_create.assert_called_once_with("http://erp.example.com", None)

    def test_create_app_unknown_type(self):
        """알 수 없는 래퍼 타입"""
        from app.mcp_wrappers.run_wrapper import create_app

        with pytest.raises(ValueError, match="Unknown wrapper type"):
            create_app("unknown", "http://example.com", None)


# ========== main 함수 테스트 ==========


class TestMain:
    """main 함수 테스트"""

    def test_main_mes_wrapper(self):
        """main 함수 - MES 래퍼 실행"""
        from app.mcp_wrappers.run_wrapper import main

        test_args = [
            "run_wrapper.py",
            "--type", "mes",
            "--port", "8100",
            "--target-url", "http://mes.example.com",
            "--api-key", "test-key"
        ]

        with patch("sys.argv", test_args):
            with patch("app.mcp_wrappers.run_wrapper.create_app") as mock_create:
                with patch("uvicorn.run") as mock_uvicorn:
                    mock_app = FastAPI()
                    mock_create.return_value = mock_app

                    main()

                    mock_create.assert_called_once_with("mes", "http://mes.example.com", "test-key")
                    mock_uvicorn.assert_called_once()

    def test_main_erp_wrapper(self):
        """main 함수 - ERP 래퍼 실행"""
        from app.mcp_wrappers.run_wrapper import main

        test_args = [
            "run_wrapper.py",
            "--type", "erp",
            "--port", "8101",
            "--host", "127.0.0.1",
            "--target-url", "http://erp.example.com",
        ]

        with patch("sys.argv", test_args):
            with patch("app.mcp_wrappers.run_wrapper.create_app") as mock_create:
                with patch("uvicorn.run") as mock_uvicorn:
                    mock_app = FastAPI()
                    mock_create.return_value = mock_app

                    main()

                    mock_create.assert_called_once_with("erp", "http://erp.example.com", None)
                    call_kwargs = mock_uvicorn.call_args[1]
                    assert call_kwargs["host"] == "127.0.0.1"
                    assert call_kwargs["port"] == 8101

    def test_main_with_reload(self):
        """main 함수 - 개발 모드(reload)"""
        from app.mcp_wrappers.run_wrapper import main

        test_args = [
            "run_wrapper.py",
            "--type", "mes",
            "--target-url", "http://mes.example.com",
            "--reload",
        ]

        with patch("sys.argv", test_args):
            with patch("app.mcp_wrappers.run_wrapper.create_app") as mock_create:
                with patch("uvicorn.run") as mock_uvicorn:
                    mock_app = FastAPI()
                    mock_create.return_value = mock_app

                    main()

                    call_kwargs = mock_uvicorn.call_args[1]
                    assert call_kwargs["reload"] is True
                    # reload 모드일 때 workers는 1
                    assert call_kwargs["workers"] == 1

    def test_main_with_workers(self):
        """main 함수 - 워커 수 설정"""
        from app.mcp_wrappers.run_wrapper import main

        test_args = [
            "run_wrapper.py",
            "--type", "mes",
            "--target-url", "http://mes.example.com",
            "--workers", "4",
        ]

        with patch("sys.argv", test_args):
            with patch("app.mcp_wrappers.run_wrapper.create_app") as mock_create:
                with patch("uvicorn.run") as mock_uvicorn:
                    mock_app = FastAPI()
                    mock_create.return_value = mock_app

                    main()

                    call_kwargs = mock_uvicorn.call_args[1]
                    assert call_kwargs["workers"] == 4

    def test_main_with_log_level(self):
        """main 함수 - 로그 레벨 설정"""
        from app.mcp_wrappers.run_wrapper import main

        test_args = [
            "run_wrapper.py",
            "--type", "erp",
            "--target-url", "http://erp.example.com",
            "--log-level", "debug",
        ]

        with patch("sys.argv", test_args):
            with patch("app.mcp_wrappers.run_wrapper.create_app") as mock_create:
                with patch("uvicorn.run") as mock_uvicorn:
                    mock_app = FastAPI()
                    mock_create.return_value = mock_app

                    main()

                    call_kwargs = mock_uvicorn.call_args[1]
                    assert call_kwargs["log_level"] == "debug"

    def test_main_create_app_error(self):
        """main 함수 - 앱 생성 실패"""
        from app.mcp_wrappers.run_wrapper import main

        test_args = [
            "run_wrapper.py",
            "--type", "mes",
            "--target-url", "http://mes.example.com",
        ]

        with patch("sys.argv", test_args):
            with patch("app.mcp_wrappers.run_wrapper.create_app") as mock_create:
                mock_create.side_effect = Exception("Creation failed")
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1


# ========== argparse 테스트 ==========


class TestArgumentParser:
    """Argument Parser 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        import argparse
        from app.mcp_wrappers.run_wrapper import main

        test_args = [
            "run_wrapper.py",
            "--type", "mes",
            "--target-url", "http://mes.example.com",
        ]

        with patch("sys.argv", test_args):
            with patch("app.mcp_wrappers.run_wrapper.create_app") as mock_create:
                with patch("uvicorn.run") as mock_uvicorn:
                    mock_app = FastAPI()
                    mock_create.return_value = mock_app

                    main()

                    call_kwargs = mock_uvicorn.call_args[1]
                    # 기본값 확인
                    assert call_kwargs["host"] == "0.0.0.0"
                    assert call_kwargs["port"] == 8100
                    assert call_kwargs["reload"] is False
                    assert call_kwargs["log_level"] == "info"
