"""
Settings Service 테스트
EncryptionService 및 SystemSettingsService 테스트
"""
from unittest.mock import MagicMock, patch


# ========== EncryptionService 테스트 ==========


class TestEncryptionService:
    """EncryptionService 테스트"""

    def test_init(self):
        """암호화 서비스 초기화"""
        from app.services.settings_service import EncryptionService

        service = EncryptionService()

        assert service._fernet is not None

    def test_encrypt_empty_string(self):
        """빈 문자열 암호화"""
        from app.services.settings_service import EncryptionService

        service = EncryptionService()
        result = service.encrypt("")

        assert result == ""

    def test_encrypt_decrypt_roundtrip(self):
        """암호화 후 복호화"""
        from app.services.settings_service import EncryptionService

        service = EncryptionService()
        original = "my-secret-api-key-12345"

        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)

        assert encrypted != original
        assert decrypted == original

    def test_decrypt_empty_string(self):
        """빈 문자열 복호화"""
        from app.services.settings_service import EncryptionService

        service = EncryptionService()
        result = service.decrypt("")

        assert result == ""

    def test_decrypt_invalid_ciphertext(self):
        """잘못된 암호문 복호화"""
        from app.services.settings_service import EncryptionService

        service = EncryptionService()
        result = service.decrypt("invalid-ciphertext")

        assert result == ""

    def test_mask_value_short(self):
        """짧은 값 마스킹"""
        from app.services.settings_service import EncryptionService

        service = EncryptionService()
        result = service.mask_value("abc")

        assert result == "****"

    def test_mask_value_normal(self):
        """일반 값 마스킹"""
        from app.services.settings_service import EncryptionService

        service = EncryptionService()
        result = service.mask_value("sk-abc123xyz789")

        assert result.startswith("sk-a")
        assert result.endswith("z789")
        assert "..." in result

    def test_mask_value_empty(self):
        """빈 값 마스킹"""
        from app.services.settings_service import EncryptionService

        service = EncryptionService()
        result = service.mask_value("")

        assert result == "****"

    def test_mask_value_custom_visible_chars(self):
        """커스텀 visible_chars로 마스킹"""
        from app.services.settings_service import EncryptionService

        service = EncryptionService()
        result = service.mask_value("1234567890abcdef", visible_chars=6)

        assert result.startswith("123456")
        assert result.endswith("abcdef")


# ========== encryption_service 싱글톤 테스트 ==========


class TestEncryptionServiceSingleton:
    """encryption_service 싱글톤 테스트"""

    def test_singleton_exists(self):
        """싱글톤 인스턴스 존재"""
        from app.services.settings_service import encryption_service

        assert encryption_service is not None

    def test_singleton_works(self):
        """싱글톤 동작"""
        from app.services.settings_service import encryption_service

        original = "test-value"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)

        assert decrypted == original


# ========== SETTING_DEFINITIONS 테스트 ==========


class TestSettingDefinitions:
    """SETTING_DEFINITIONS 상수 테스트"""

    def test_definitions_exist(self):
        """설정 정의 존재"""
        from app.services.settings_service import SETTING_DEFINITIONS

        assert "slack_webhook_url" in SETTING_DEFINITIONS
        assert "anthropic_api_key" in SETTING_DEFINITIONS

    def test_definitions_structure(self):
        """설정 정의 구조"""
        from app.services.settings_service import SETTING_DEFINITIONS

        slack_def = SETTING_DEFINITIONS["slack_webhook_url"]

        assert "category" in slack_def
        assert "sensitive" in slack_def
        assert "label" in slack_def
        assert slack_def["category"] == "notification"
        assert slack_def["sensitive"] is True

    def test_sensitive_settings(self):
        """민감 설정 확인"""
        from app.services.settings_service import SETTING_DEFINITIONS

        sensitive_keys = [k for k, v in SETTING_DEFINITIONS.items() if v.get("sensitive")]

        assert "slack_webhook_url" in sensitive_keys
        assert "smtp_password" in sensitive_keys
        assert "aws_access_key_id" in sensitive_keys
        assert "anthropic_api_key" in sensitive_keys

    def test_categories(self):
        """카테고리 확인"""
        from app.services.settings_service import SETTING_DEFINITIONS

        categories = set(v.get("category") for v in SETTING_DEFINITIONS.values())

        assert "notification" in categories
        assert "storage" in categories
        assert "ai" in categories


# ========== SystemSettingsService 초기화 테스트 ==========


class TestSystemSettingsServiceInit:
    """SystemSettingsService 초기화 테스트"""

    def test_init(self):
        """서비스 초기화"""
        from app.services.settings_service import SystemSettingsService

        service = SystemSettingsService()

        assert service._cache == {}
        assert service._cache_loaded is False


# ========== SystemSettingsService get_setting 테스트 ==========


class TestSystemSettingsServiceGetSetting:
    """SystemSettingsService get_setting 테스트"""

    @patch("app.database.get_db_context")
    def test_get_setting_from_db(self, mock_db_context):
        """DB에서 설정 조회"""
        from app.services.settings_service import SystemSettingsService

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = ("test-value", False)
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.get_setting("test_key")

        assert result == "test-value"

    @patch("app.database.get_db_context")
    def test_get_setting_encrypted(self, mock_db_context):
        """암호화된 설정 조회"""
        from app.services.settings_service import SystemSettingsService, encryption_service

        encrypted_value = encryption_service.encrypt("secret-value")
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = (encrypted_value, True)
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.get_setting("secret_key")

        assert result == "secret-value"

    @patch("app.database.get_db_context")
    @patch.dict("os.environ", {"TEST_KEY": "env-value"})
    def test_get_setting_fallback_to_env(self, mock_db_context):
        """DB에 없을 때 환경변수 fallback"""
        from app.services.settings_service import SystemSettingsService

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.get_setting("test_key")

        assert result == "env-value"

    @patch("app.database.get_db_context")
    def test_get_setting_default(self, mock_db_context):
        """DB와 환경변수 모두 없을 때 기본값"""
        from app.services.settings_service import SystemSettingsService

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.get_setting("nonexistent_key", default="default-value")

        assert result == "default-value"

    @patch("app.database.get_db_context")
    def test_get_setting_db_error(self, mock_db_context):
        """DB 에러 시 환경변수 fallback"""
        from app.services.settings_service import SystemSettingsService

        mock_db_context.return_value.__enter__ = MagicMock(side_effect=Exception("DB Error"))
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.get_setting("test_key", default="default")

        assert result == "default"


# ========== SystemSettingsService set_setting 테스트 ==========


class TestSystemSettingsServiceSetSetting:
    """SystemSettingsService set_setting 테스트"""

    @patch("app.database.get_db_context")
    def test_set_setting_success(self, mock_db_context):
        """설정 저장 성공"""
        from app.services.settings_service import SystemSettingsService

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.set_setting("slack_default_channel", "#general")

        assert result is True
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()

    @patch("app.database.get_db_context")
    def test_set_setting_sensitive_encrypted(self, mock_db_context):
        """민감 정보는 암호화하여 저장"""
        from app.services.settings_service import SystemSettingsService

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.set_setting("slack_webhook_url", "https://hooks.slack.com/xxx")

        assert result is True
        # 저장된 값이 암호화되었는지 확인
        call_args = mock_db.execute.call_args_list[-1]
        params = call_args[0][1]
        assert params["is_encrypted"] is True
        assert params["value"] != "https://hooks.slack.com/xxx"

    @patch("app.database.get_db_context")
    def test_set_setting_db_error(self, mock_db_context):
        """DB 에러 시 False 반환"""
        from app.services.settings_service import SystemSettingsService

        mock_db_context.return_value.__enter__ = MagicMock(side_effect=Exception("DB Error"))
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.set_setting("test_key", "test_value")

        assert result is False


# ========== SystemSettingsService delete_setting 테스트 ==========


class TestSystemSettingsServiceDeleteSetting:
    """SystemSettingsService delete_setting 테스트"""

    @patch("app.database.get_db_context")
    def test_delete_setting_success(self, mock_db_context):
        """설정 삭제 성공"""
        from app.services.settings_service import SystemSettingsService

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.delete_setting("test_key")

        assert result is True
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()

    @patch("app.database.get_db_context")
    def test_delete_setting_db_error(self, mock_db_context):
        """DB 에러 시 False 반환"""
        from app.services.settings_service import SystemSettingsService

        mock_db_context.return_value.__enter__ = MagicMock(side_effect=Exception("DB Error"))
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.delete_setting("test_key")

        assert result is False


# ========== SystemSettingsService get_all_settings 테스트 ==========


class TestSystemSettingsServiceGetAllSettings:
    """SystemSettingsService get_all_settings 테스트"""

    @patch("app.database.get_db_context")
    def test_get_all_settings_empty(self, mock_db_context):
        """설정 없을 때"""
        from app.services.settings_service import SystemSettingsService, SETTING_DEFINITIONS

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        results = service.get_all_settings()

        # 정의된 설정 수만큼 반환
        assert len(results) == len(SETTING_DEFINITIONS)

    @patch("app.database.get_db_context")
    def test_get_all_settings_with_category(self, mock_db_context):
        """카테고리 필터링"""
        from app.services.settings_service import SystemSettingsService

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        results = service.get_all_settings(category="notification")

        # notification 카테고리만
        for r in results:
            assert r["category"] == "notification"


# ========== SystemSettingsService test_notification_settings 테스트 ==========


class TestSystemSettingsServiceTestNotification:
    """SystemSettingsService test_notification_settings 테스트"""

    @patch("app.database.get_db_context")
    def test_notification_settings_not_configured(self, mock_db_context):
        """알림 미설정 시"""
        from app.services.settings_service import SystemSettingsService

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        result = service.test_notification_settings()

        assert result["slack"]["configured"] is False
        assert result["email"]["configured"] is False

    @patch("app.database.get_db_context")
    def test_notification_settings_slack_configured(self, mock_db_context):
        """Slack 설정됨"""
        from app.services.settings_service import SystemSettingsService

        mock_db = MagicMock()

        def mock_fetchone(key_param):
            key = key_param.get("key") if isinstance(key_param, dict) else None
            if key == "slack_webhook_url":
                return ("https://hooks.slack.com/xxx", False)
            return None

        mock_db.execute.return_value.fetchone.side_effect = lambda: None
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=False)

        service = SystemSettingsService()
        # get_setting 직접 mock
        with patch.object(service, 'get_setting') as mock_get:
            mock_get.side_effect = lambda k, d=None: "https://hooks.slack.com" if k == "slack_webhook_url" else None
            result = service.test_notification_settings()

        assert result["slack"]["configured"] is True
        assert result["slack"]["webhook_url_set"] is True


# ========== settings_service 싱글톤 테스트 ==========


class TestSettingsServiceSingleton:
    """settings_service 싱글톤 테스트"""

    def test_singleton_exists(self):
        """싱글톤 인스턴스 존재"""
        from app.services.settings_service import settings_service

        assert settings_service is not None

    def test_singleton_type(self):
        """싱글톤 타입"""
        from app.services.settings_service import settings_service, SystemSettingsService

        assert isinstance(settings_service, SystemSettingsService)
