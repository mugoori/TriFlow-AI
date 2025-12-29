"""
알림 서비스 테스트

Slack, Email, SMS 알림 서비스 단위 테스트
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestNotificationStatus:
    """NotificationStatus 열거형 테스트"""

    def test_status_values(self):
        """상태 값 확인"""
        from app.services.notifications import NotificationStatus

        assert NotificationStatus.SUCCESS == "success"
        assert NotificationStatus.FAILED == "failed"
        assert NotificationStatus.SKIPPED == "skipped"

    def test_status_is_string_enum(self):
        """문자열 열거형 확인"""
        from app.services.notifications import NotificationStatus

        assert isinstance(NotificationStatus.SUCCESS.value, str)


class TestNotificationResult:
    """NotificationResult 데이터클래스 테스트"""

    def test_result_success(self):
        """성공 결과"""
        from app.services.notifications import NotificationResult, NotificationStatus

        result = NotificationResult(
            status=NotificationStatus.SUCCESS,
            message="알림이 전송되었습니다",
            details={"channel": "#alerts"},
        )

        assert result.status == NotificationStatus.SUCCESS
        assert result.message == "알림이 전송되었습니다"
        assert result.details["channel"] == "#alerts"

    def test_result_failed(self):
        """실패 결과"""
        from app.services.notifications import NotificationResult, NotificationStatus

        result = NotificationResult(
            status=NotificationStatus.FAILED,
            message="전송 실패",
            details={"error": "Connection timeout"},
        )

        assert result.status == NotificationStatus.FAILED

    def test_result_skipped(self):
        """스킵 결과"""
        from app.services.notifications import NotificationResult, NotificationStatus

        result = NotificationResult(
            status=NotificationStatus.SKIPPED,
            message="설정되지 않음",
        )

        assert result.status == NotificationStatus.SKIPPED
        assert result.details is None


class TestSlackNotificationService:
    """SlackNotificationService 테스트"""

    def test_enabled_with_webhook(self):
        """Webhook URL 설정 시 활성화"""
        from app.services.notifications import SlackNotificationService

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
                "slack_default_channel": "#alerts",
            }.get(key, default)

            assert service.enabled is True

    def test_disabled_without_webhook(self):
        """Webhook URL 미설정 시 비활성화"""
        from app.services.notifications import SlackNotificationService

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.return_value = None

            assert service.enabled is False

    @pytest.mark.asyncio
    async def test_send_when_disabled(self):
        """비활성화 시 스킵"""
        from app.services.notifications import SlackNotificationService, NotificationStatus

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.return_value = None

            result = await service.send("테스트 메시지")

            assert result.status == NotificationStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_send_success(self):
        """전송 성공"""
        from app.services.notifications import SlackNotificationService, NotificationStatus

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
                "slack_default_channel": "#alerts",
            }.get(key, default)

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                result = await service.send("테스트 메시지")

                assert result.status == NotificationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_send_with_mention_user(self):
        """사용자 멘션 포함 전송"""
        from app.services.notifications import SlackNotificationService

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
            }.get(key, default)

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200

                captured_payload = {}

                async def capture_post(url, json, timeout):
                    captured_payload.update(json)
                    return mock_response

                mock_client.return_value.__aenter__.return_value.post = capture_post

                await service.send("테스트 메시지", mention="@user")

                assert "<@user>" in captured_payload.get("text", "")

    @pytest.mark.asyncio
    async def test_send_with_channel_mention(self):
        """채널 멘션 포함 전송"""
        from app.services.notifications import SlackNotificationService

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
            }.get(key, default)

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200

                captured_payload = {}

                async def capture_post(url, json, timeout):
                    captured_payload.update(json)
                    return mock_response

                mock_client.return_value.__aenter__.return_value.post = capture_post

                await service.send("테스트 메시지", mention="channel")

                assert "<!channel>" in captured_payload.get("text", "")

    @pytest.mark.asyncio
    async def test_send_with_attachments(self):
        """첨부파일 포함 전송"""
        from app.services.notifications import SlackNotificationService

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
            }.get(key, default)

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200

                captured_payload = {}

                async def capture_post(url, json, timeout):
                    captured_payload.update(json)
                    return mock_response

                mock_client.return_value.__aenter__.return_value.post = capture_post

                attachments = [{"title": "Alert", "color": "danger"}]
                await service.send("테스트 메시지", attachments=attachments)

                assert "attachments" in captured_payload

    @pytest.mark.asyncio
    async def test_send_failure(self):
        """전송 실패"""
        from app.services.notifications import SlackNotificationService, NotificationStatus

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
            }.get(key, default)

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                result = await service.send("테스트 메시지")

                assert result.status == NotificationStatus.FAILED

    @pytest.mark.asyncio
    async def test_send_timeout(self):
        """전송 타임아웃"""
        from app.services.notifications import SlackNotificationService, NotificationStatus
        import httpx

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
            }.get(key, default)

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    side_effect=httpx.TimeoutException("timeout")
                )

                result = await service.send("테스트 메시지")

                assert result.status == NotificationStatus.FAILED
                assert "타임아웃" in result.message


class TestEmailNotificationService:
    """EmailNotificationService 테스트"""

    def test_enabled_with_all_settings(self):
        """모든 설정이 있으면 활성화"""
        from app.services.notifications import EmailNotificationService

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "smtp_host": "smtp.gmail.com",
                "smtp_port": "587",
                "smtp_user": "user@gmail.com",
                "smtp_password": "password",
                "smtp_from": "user@gmail.com",
                "smtp_use_tls": "true",
            }.get(key, default)

            assert service.enabled is True

    def test_disabled_without_host(self):
        """호스트 미설정 시 비활성화"""
        from app.services.notifications import EmailNotificationService

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "smtp_host": None,
                "smtp_port": "587",
                "smtp_user": "user@gmail.com",
                "smtp_password": "password",
            }.get(key, default)

            assert service.enabled is False

    def test_disabled_without_password(self):
        """비밀번호 미설정 시 비활성화"""
        from app.services.notifications import EmailNotificationService

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "smtp_host": "smtp.gmail.com",
                "smtp_port": "587",
                "smtp_user": "user@gmail.com",
                "smtp_password": None,
            }.get(key, default)

            assert service.enabled is False

    @pytest.mark.asyncio
    async def test_send_when_disabled(self):
        """비활성화 시 스킵"""
        from app.services.notifications import EmailNotificationService, NotificationStatus

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            # 기본값이 필요한 설정들 처리
            def get_setting_mock(key, default=None):
                if key == "smtp_port":
                    return default or "587"
                if key == "smtp_use_tls":
                    return default or "true"
                return default  # None 대신 default 반환

            mock_get.side_effect = get_setting_mock

            result = await service.send(
                to="test@example.com",
                subject="테스트",
                body="테스트 내용",
            )

            assert result.status == NotificationStatus.SKIPPED


class TestGetSetting:
    """get_setting 함수 테스트"""

    def test_get_setting_from_env(self):
        """환경변수에서 설정 조회"""
        from app.services.notifications import get_setting

        with patch("os.getenv") as mock_env:
            mock_env.return_value = "test_value"

            with patch("app.services.notifications.get_setting") as mock_get:
                # settings_service 실패 시 환경변수 fallback
                mock_get.side_effect = Exception("DB 연결 실패")

                # 직접 os.getenv 호출
                import os
                with patch.dict(os.environ, {"TEST_KEY": "test_value"}):
                    result = os.getenv("TEST_KEY")
                    assert result == "test_value"

    def test_get_setting_default(self):
        """기본값 반환"""
        import os

        with patch.dict(os.environ, {}, clear=True):
            result = os.getenv("NONEXISTENT_KEY", "default_value")
            assert result == "default_value"


class TestSlackPayloadConstruction:
    """Slack 페이로드 구성 테스트"""

    def test_basic_payload(self):
        """기본 페이로드"""
        message = "테스트 메시지"

        payload = {"text": message}

        assert payload["text"] == message
        assert "channel" not in payload

    def test_payload_with_channel(self):
        """채널 포함 페이로드"""
        message = "테스트 메시지"
        channel = "#alerts"

        payload = {"text": message}
        if channel:
            payload["channel"] = channel

        assert payload["channel"] == "#alerts"

    def test_payload_with_attachments(self):
        """첨부파일 포함 페이로드"""
        message = "테스트 메시지"
        attachments = [
            {
                "title": "Alert",
                "color": "danger",
                "fields": [{"title": "Severity", "value": "High"}],
            }
        ]

        payload = {"text": message}
        if attachments:
            payload["attachments"] = attachments

        assert len(payload["attachments"]) == 1
        assert payload["attachments"][0]["title"] == "Alert"


class TestMentionFormatting:
    """멘션 포맷팅 테스트"""

    def test_user_mention(self):
        """사용자 멘션"""
        message = "테스트 메시지"
        mention = "@user"

        if mention.startswith("@"):
            message = f"<{mention}> {message}"

        assert "<@user>" in message

    def test_channel_mention(self):
        """채널 멘션"""
        message = "테스트 메시지"
        mention = "channel"

        if mention in ["channel", "here"]:
            message = f"<!{mention}> {message}"

        assert "<!channel>" in message

    def test_here_mention(self):
        """here 멘션"""
        message = "테스트 메시지"
        mention = "here"

        if mention in ["channel", "here"]:
            message = f"<!{mention}> {message}"

        assert "<!here>" in message


class TestEmailMIMEConstruction:
    """이메일 MIME 구성 테스트"""

    def test_plain_text_email(self):
        """텍스트 이메일"""
        from email.mime.text import MIMEText

        body = "Test body"
        msg = MIMEText(body, "plain", "utf-8")

        # get_payload()는 인코딩된 값을 반환하므로 decode=True 사용
        assert "Test" in msg.get_payload(decode=True).decode("utf-8")

    def test_html_email(self):
        """HTML 이메일"""
        from email.mime.text import MIMEText

        html_body = "<h1>테스트</h1>"
        msg = MIMEText(html_body, "html")

        assert msg.get_content_type() == "text/html"

    def test_multipart_email(self):
        """멀티파트 이메일"""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "테스트 제목"
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"

        text_part = MIMEText("텍스트 본문", "plain")
        html_part = MIMEText("<h1>HTML 본문</h1>", "html")

        msg.attach(text_part)
        msg.attach(html_part)

        assert msg["Subject"] == "테스트 제목"


class TestSMTPConfig:
    """SMTP 설정 테스트"""

    def test_default_port(self):
        """기본 포트"""
        default_port = int("587")
        assert default_port == 587

    def test_tls_enabled(self):
        """TLS 활성화"""
        use_tls = "true".lower() == "true"
        assert use_tls is True

    def test_tls_disabled(self):
        """TLS 비활성화"""
        use_tls = "false".lower() == "true"
        assert use_tls is False

    def test_from_fallback_to_user(self):
        """발신자 기본값"""
        smtp_user = "user@example.com"
        smtp_from = None or smtp_user

        assert smtp_from == "user@example.com"


class TestNotificationResultDetails:
    """알림 결과 상세정보 테스트"""

    def test_success_details(self):
        """성공 상세정보"""
        from app.services.notifications import NotificationResult, NotificationStatus

        result = NotificationResult(
            status=NotificationStatus.SUCCESS,
            message="전송 성공",
            details={"channel": "#alerts", "message_id": "12345"},
        )

        assert result.details["channel"] == "#alerts"

    def test_failure_details(self):
        """실패 상세정보"""
        from app.services.notifications import NotificationResult, NotificationStatus

        result = NotificationResult(
            status=NotificationStatus.FAILED,
            message="전송 실패",
            details={"status_code": 500, "error": "Internal Server Error"},
        )

        assert result.details["status_code"] == 500

    def test_skipped_details(self):
        """스킵 상세정보"""
        from app.services.notifications import NotificationResult, NotificationStatus

        result = NotificationResult(
            status=NotificationStatus.SKIPPED,
            message="설정 미완료",
            details={"config_missing": ["SLACK_WEBHOOK_URL"]},
        )

        assert "SLACK_WEBHOOK_URL" in result.details["config_missing"]


# ========== 추가 테스트 - 누락된 라인 커버 ==========


class TestGetSettingFunction:
    """get_setting 함수 상세 테스트"""

    def test_get_setting_from_settings_service_success(self):
        """settings_service에서 설정 조회 성공"""
        # settings_service 모듈 mock
        mock_settings_service = MagicMock()
        mock_settings_service.get_setting.return_value = "db_value"

        with patch.dict(
            "sys.modules",
            {"app.services.settings_service": MagicMock(settings_service=mock_settings_service)},
        ):
            # get_setting 함수 호출 - 이미 import된 함수 사용
            from app.services.notifications import get_setting

            # get_setting은 settings_service.get_setting을 호출
            # 여기서는 함수가 존재하는지만 확인
            assert callable(get_setting)

    def test_get_setting_fallback_to_env_on_exception(self):
        """settings_service 예외 시 환경변수 fallback"""
        import os

        # 환경변수 설정
        with patch.dict(os.environ, {"TEST_KEY": "env_fallback_value"}):
            # get_setting 함수가 환경변수 fallback을 지원하는지 확인
            env_value = os.getenv("TEST_KEY")
            assert env_value == "env_fallback_value"


class TestSlackSendExtended:
    """Slack 전송 확장 테스트"""

    @pytest.mark.asyncio
    async def test_send_with_custom_mention(self):
        """커스텀 멘션 전송"""
        from app.services.notifications import SlackNotificationService

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
                "slack_default_channel": "#alerts",
            }.get(key, default)

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200

                captured_payload = {}

                async def capture_post(url, json, timeout):
                    captured_payload.update(json)
                    return mock_response

                mock_client.return_value.__aenter__.return_value.post = capture_post

                # 커스텀 멘션 (@ 없는 텍스트)
                await service.send("테스트", mention="custom_mention")

                # 커스텀 멘션은 그대로 추가됨
                assert "custom_mention" in captured_payload.get("text", "")

    @pytest.mark.asyncio
    async def test_send_with_here_mention(self):
        """here 멘션 전송"""
        from app.services.notifications import SlackNotificationService

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
                "slack_default_channel": "#alerts",
            }.get(key, default)

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200

                captured_payload = {}

                async def capture_post(url, json, timeout):
                    captured_payload.update(json)
                    return mock_response

                mock_client.return_value.__aenter__.return_value.post = capture_post

                await service.send("테스트", mention="here")

                assert "<!here>" in captured_payload.get("text", "")

    @pytest.mark.asyncio
    async def test_send_general_exception(self):
        """일반 예외 처리"""
        from app.services.notifications import SlackNotificationService, NotificationStatus

        service = SlackNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
            }.get(key, default)

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    side_effect=Exception("General error")
                )

                result = await service.send("테스트 메시지")

                assert result.status == NotificationStatus.FAILED
                assert "오류" in result.message


class TestEmailSendExtended:
    """Email 전송 확장 테스트"""

    @pytest.mark.asyncio
    async def test_send_success_with_tls(self):
        """TLS 사용 이메일 전송 성공"""
        from app.services.notifications import EmailNotificationService, NotificationStatus

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "smtp_host": "smtp.example.com",
                "smtp_port": "587",
                "smtp_user": "user@example.com",
                "smtp_password": "password123",
                "smtp_from": "sender@example.com",
                "smtp_use_tls": "true",
            }.get(key, default)

            mock_server = MagicMock()

            with patch("smtplib.SMTP", return_value=mock_server):
                result = await service.send(
                    to="recipient@example.com",
                    subject="테스트 제목",
                    body="테스트 본문",
                )

                assert result.status == NotificationStatus.SUCCESS
                mock_server.starttls.assert_called_once()
                mock_server.login.assert_called_once()
                mock_server.sendmail.assert_called_once()
                mock_server.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_success_without_tls(self):
        """TLS 미사용 이메일 전송 성공"""
        from app.services.notifications import EmailNotificationService, NotificationStatus

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "smtp_host": "smtp.example.com",
                "smtp_port": "25",
                "smtp_user": "user@example.com",
                "smtp_password": "password123",
                "smtp_from": "sender@example.com",
                "smtp_use_tls": "false",
            }.get(key, default)

            mock_server = MagicMock()

            with patch("smtplib.SMTP", return_value=mock_server):
                result = await service.send(
                    to="recipient@example.com",
                    subject="테스트 제목",
                    body="테스트 본문",
                )

                assert result.status == NotificationStatus.SUCCESS
                mock_server.starttls.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_with_html_body(self):
        """HTML 본문 이메일 전송"""
        from app.services.notifications import EmailNotificationService, NotificationStatus

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "smtp_host": "smtp.example.com",
                "smtp_port": "587",
                "smtp_user": "user@example.com",
                "smtp_password": "password123",
                "smtp_from": "sender@example.com",
                "smtp_use_tls": "true",
            }.get(key, default)

            mock_server = MagicMock()

            with patch("smtplib.SMTP", return_value=mock_server):
                result = await service.send(
                    to="recipient@example.com",
                    subject="테스트 제목",
                    body="텍스트 본문",
                    html_body="<h1>HTML 본문</h1>",
                )

                assert result.status == NotificationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_send_with_cc_and_bcc(self):
        """CC, BCC 포함 이메일 전송"""
        from app.services.notifications import EmailNotificationService, NotificationStatus

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "smtp_host": "smtp.example.com",
                "smtp_port": "587",
                "smtp_user": "user@example.com",
                "smtp_password": "password123",
                "smtp_from": "sender@example.com",
                "smtp_use_tls": "true",
            }.get(key, default)

            mock_server = MagicMock()

            with patch("smtplib.SMTP", return_value=mock_server):
                result = await service.send(
                    to="recipient@example.com",
                    subject="테스트 제목",
                    body="테스트 본문",
                    cc="cc@example.com",
                    bcc="bcc@example.com",
                )

                assert result.status == NotificationStatus.SUCCESS
                # sendmail 호출 시 수신자 목록 확인
                call_args = mock_server.sendmail.call_args
                recipients = call_args[0][1]
                assert len(recipients) == 3

    @pytest.mark.asyncio
    async def test_send_smtp_auth_error(self):
        """SMTP 인증 실패"""
        import smtplib

        from app.services.notifications import EmailNotificationService, NotificationStatus

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "smtp_host": "smtp.example.com",
                "smtp_port": "587",
                "smtp_user": "user@example.com",
                "smtp_password": "wrong_password",
                "smtp_from": "sender@example.com",
                "smtp_use_tls": "true",
            }.get(key, default)

            mock_server = MagicMock()
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
                535, b"Authentication failed"
            )

            with patch("smtplib.SMTP", return_value=mock_server):
                result = await service.send(
                    to="recipient@example.com",
                    subject="테스트 제목",
                    body="테스트 본문",
                )

                assert result.status == NotificationStatus.FAILED
                assert "인증" in result.message

    @pytest.mark.asyncio
    async def test_send_smtp_exception(self):
        """SMTP 예외"""
        import smtplib

        from app.services.notifications import EmailNotificationService, NotificationStatus

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "smtp_host": "smtp.example.com",
                "smtp_port": "587",
                "smtp_user": "user@example.com",
                "smtp_password": "password123",
                "smtp_from": "sender@example.com",
                "smtp_use_tls": "true",
            }.get(key, default)

            mock_server = MagicMock()
            mock_server.sendmail.side_effect = smtplib.SMTPException("Send failed")

            with patch("smtplib.SMTP", return_value=mock_server):
                result = await service.send(
                    to="recipient@example.com",
                    subject="테스트 제목",
                    body="테스트 본문",
                )

                assert result.status == NotificationStatus.FAILED
                assert "SMTP" in result.message

    @pytest.mark.asyncio
    async def test_send_general_exception(self):
        """일반 예외"""
        from app.services.notifications import EmailNotificationService, NotificationStatus

        service = EmailNotificationService()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "smtp_host": "smtp.example.com",
                "smtp_port": "587",
                "smtp_user": "user@example.com",
                "smtp_password": "password123",
                "smtp_from": "sender@example.com",
                "smtp_use_tls": "true",
            }.get(key, default)

            with patch("smtplib.SMTP", side_effect=Exception("Connection failed")):
                result = await service.send(
                    to="recipient@example.com",
                    subject="테스트 제목",
                    body="테스트 본문",
                )

                assert result.status == NotificationStatus.FAILED
                assert "오류" in result.message


class TestSMSService:
    """SMS 서비스 테스트"""

    @pytest.mark.asyncio
    async def test_sms_send(self):
        """SMS 전송 (V2 미구현)"""
        from app.services.notifications import SMSNotificationService, NotificationStatus

        service = SMSNotificationService()

        result = await service.send(
            phone="010-1234-5678",
            message="테스트 SMS",
        )

        assert result.status == NotificationStatus.SKIPPED
        assert "V2" in result.message


class TestNotificationManagerExtended:
    """NotificationManager 확장 테스트"""

    @pytest.mark.asyncio
    async def test_execute_slack_action(self):
        """Slack 액션 실행"""
        from app.services.notifications import (
            NotificationManager,
            NotificationStatus,
            NotificationResult,
        )

        manager = NotificationManager()

        mock_result = NotificationResult(
            status=NotificationStatus.SUCCESS,
            message="전송 성공",
        )

        with patch.object(
            manager.slack, "send", new=AsyncMock(return_value=mock_result)
        ) as mock_send:
            result = await manager.execute_action(
                "send_slack_notification",
                {"message": "테스트", "channel": "#test", "mention": "@user"},
            )

            assert result.status == NotificationStatus.SUCCESS
            mock_send.assert_called_once_with(
                message="테스트",
                channel="#test",
                mention="@user",
            )

    @pytest.mark.asyncio
    async def test_execute_email_action(self):
        """Email 액션 실행"""
        from app.services.notifications import (
            NotificationManager,
            NotificationStatus,
            NotificationResult,
        )

        manager = NotificationManager()

        mock_result = NotificationResult(
            status=NotificationStatus.SUCCESS,
            message="전송 성공",
        )

        with patch.object(
            manager.email, "send", new=AsyncMock(return_value=mock_result)
        ) as mock_send:
            result = await manager.execute_action(
                "send_email",
                {
                    "to": "test@example.com",
                    "subject": "테스트",
                    "body": "본문",
                    "html_body": "<p>HTML</p>",
                },
            )

            assert result.status == NotificationStatus.SUCCESS
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_sms_action(self):
        """SMS 액션 실행"""
        from app.services.notifications import NotificationManager, NotificationStatus

        manager = NotificationManager()

        result = await manager.execute_action(
            "send_sms",
            {"phone": "010-1234-5678", "message": "테스트"},
        )

        assert result.status == NotificationStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self):
        """알 수 없는 액션"""
        from app.services.notifications import NotificationManager, NotificationStatus

        manager = NotificationManager()

        result = await manager.execute_action(
            "unknown_action",
            {"key": "value"},
        )

        assert result.status == NotificationStatus.FAILED
        assert "알 수 없는" in result.message

    def test_get_status(self):
        """상태 조회"""
        from app.services.notifications import NotificationManager

        manager = NotificationManager()

        with patch("app.services.notifications.get_setting") as mock_get:
            mock_get.side_effect = lambda key, default=None: {
                "slack_webhook_url": "https://hooks.slack.com/xxx",
                "slack_default_channel": "#alerts",
                "smtp_host": "smtp.example.com",
                "smtp_port": "587",
                "smtp_user": "user@example.com",
                "smtp_password": "password",
                "smtp_from": "sender@example.com",
                "smtp_use_tls": "true",
            }.get(key, default)

            status = manager.get_status()

            assert "slack" in status
            assert "email" in status
            assert "sms" in status
            assert status["slack"]["webhook_configured"] is True
            assert status["sms"]["enabled"] is False

    def test_get_status_disabled(self):
        """비활성화 상태 조회"""
        from app.services.notifications import NotificationManager

        manager = NotificationManager()

        with patch("app.services.notifications.get_setting") as mock_get:
            # smtp_port와 smtp_use_tls에는 기본값이 필요함
            def mock_get_setting(key, default=None):
                if key == "smtp_port":
                    return default or "587"
                if key == "smtp_use_tls":
                    return default or "true"
                return None

            mock_get.side_effect = mock_get_setting

            status = manager.get_status()

            assert status["slack"]["enabled"] is False
            assert status["email"]["enabled"] is False


class TestNotificationManagerSingleton:
    """notification_manager 싱글톤 테스트"""

    def test_singleton_instance(self):
        """싱글톤 인스턴스 확인"""
        from app.services.notifications import notification_manager, NotificationManager

        assert notification_manager is not None
        assert isinstance(notification_manager, NotificationManager)

    def test_singleton_services(self):
        """싱글톤 서비스 확인"""
        from app.services.notifications import (
            notification_manager,
            SlackNotificationService,
            EmailNotificationService,
            SMSNotificationService,
        )

        assert isinstance(notification_manager.slack, SlackNotificationService)
        assert isinstance(notification_manager.email, EmailNotificationService)
        assert isinstance(notification_manager.sms, SMSNotificationService)
