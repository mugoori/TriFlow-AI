"""
Audit Service 테스트
audit_service.py의 감사 로그 기능 테스트
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.audit_service import (
    mask_sensitive_data,
    extract_resource_from_path,
    method_to_action,
    create_audit_log,
    get_audit_logs,
    get_audit_stats,
)


class TestMaskSensitiveData:
    """민감 정보 마스킹 테스트"""

    def test_mask_password_field(self):
        """비밀번호 필드 마스킹"""
        data = {"email": "test@test.com", "password": "secret123"}
        result = mask_sensitive_data(data)

        assert result["email"] == "test@test.com"
        assert result["password"] == "***MASKED***"

    def test_mask_token_field(self):
        """토큰 필드 마스킹"""
        data = {"access_token": "abc123", "refresh_token": "xyz789"}
        result = mask_sensitive_data(data)

        assert result["access_token"] == "***MASKED***"
        assert result["refresh_token"] == "***MASKED***"

    def test_mask_api_key_field(self):
        """API 키 필드 마스킹"""
        data = {"api_key": "sk-secret-key", "name": "test"}
        result = mask_sensitive_data(data)

        assert result["api_key"] == "***MASKED***"
        assert result["name"] == "test"

    def test_mask_nested_data(self):
        """중첩 데이터 마스킹"""
        data = {
            "user": {
                "email": "test@test.com",
                "password": "secret",
                "profile": {
                    "token": "abc123"
                }
            }
        }
        result = mask_sensitive_data(data)

        assert result["user"]["email"] == "test@test.com"
        assert result["user"]["password"] == "***MASKED***"
        assert result["user"]["profile"]["token"] == "***MASKED***"

    def test_mask_list_data(self):
        """리스트 데이터 마스킹"""
        data = [
            {"password": "secret1"},
            {"password": "secret2"},
        ]
        result = mask_sensitive_data(data)

        assert result[0]["password"] == "***MASKED***"
        assert result[1]["password"] == "***MASKED***"

    def test_mask_long_string(self):
        """긴 문자열 자르기"""
        long_string = "a" * 2000
        result = mask_sensitive_data(long_string)

        assert len(result) < 2000
        assert "...[TRUNCATED]..." in result

    def test_mask_depth_limit(self):
        """깊이 제한 테스트"""
        # 깊이 11 이상의 중첩 데이터
        deep_data = {"level": 0}
        current = deep_data
        for i in range(12):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        result = mask_sensitive_data(deep_data)
        # 깊이 10 초과 시 TRUNCATED
        assert "[TRUNCATED]" in str(result)

    def test_mask_empty_data(self):
        """빈 데이터 처리"""
        assert mask_sensitive_data({}) == {}
        assert mask_sensitive_data([]) == []
        assert mask_sensitive_data(None) is None

    def test_mask_case_insensitive(self):
        """대소문자 무관 마스킹"""
        data = {
            "PASSWORD": "secret1",
            "Password": "secret2",
            "passWORD": "secret3",
        }
        result = mask_sensitive_data(data)

        assert result["PASSWORD"] == "***MASKED***"
        assert result["Password"] == "***MASKED***"
        assert result["passWORD"] == "***MASKED***"

    def test_mask_partial_field_name(self):
        """부분 일치 필드명 마스킹"""
        data = {
            "user_password": "secret",
            "password_hash": "hash123",
            "authorization_header": "Bearer token",
        }
        result = mask_sensitive_data(data)

        assert result["user_password"] == "***MASKED***"
        assert result["password_hash"] == "***MASKED***"
        assert result["authorization_header"] == "***MASKED***"


class TestExtractResourceFromPath:
    """경로에서 리소스 추출 테스트"""

    def test_extract_workflows(self):
        """워크플로우 경로"""
        resource, resource_id = extract_resource_from_path("/api/v1/workflows")
        assert resource == "workflows"
        assert resource_id is None

    def test_extract_workflows_with_id(self):
        """워크플로우 + ID 경로"""
        resource, resource_id = extract_resource_from_path(
            "/api/v1/workflows/abc-123"
        )
        assert resource == "workflows"
        assert resource_id == "abc-123"

    def test_extract_sensors(self):
        """센서 경로"""
        resource, resource_id = extract_resource_from_path("/api/v1/sensors/data")
        assert resource == "sensors"
        assert resource_id == "data"

    def test_extract_rulesets(self):
        """룰셋 경로"""
        resource, resource_id = extract_resource_from_path("/api/v1/rulesets")
        assert resource == "rulesets"
        assert resource_id is None

    def test_extract_auth(self):
        """인증 경로"""
        resource, resource_id = extract_resource_from_path("/api/v1/auth/login")
        assert resource == "auth"
        assert resource_id == "login"

    def test_extract_unknown_path(self):
        """알 수 없는 경로"""
        resource, resource_id = extract_resource_from_path("/unknown/path")
        assert resource == "unknown"
        assert resource_id is None

    def test_extract_nested_path(self):
        """중첩 경로"""
        resource, resource_id = extract_resource_from_path(
            "/api/v1/workflows/123/execute"
        )
        assert resource == "workflows"
        assert resource_id == "123"


class TestMethodToAction:
    """HTTP 메서드 → 액션 변환 테스트"""

    def test_get_to_read(self):
        """GET → read"""
        assert method_to_action("GET", "/api/v1/workflows") == "read"

    def test_post_to_create(self):
        """POST → create"""
        assert method_to_action("POST", "/api/v1/workflows") == "create"

    def test_put_to_update(self):
        """PUT → update"""
        assert method_to_action("PUT", "/api/v1/workflows/123") == "update"

    def test_patch_to_update(self):
        """PATCH → update"""
        assert method_to_action("PATCH", "/api/v1/workflows/123") == "update"

    def test_delete_to_delete(self):
        """DELETE → delete"""
        assert method_to_action("DELETE", "/api/v1/workflows/123") == "delete"

    def test_login_path(self):
        """로그인 경로"""
        assert method_to_action("POST", "/api/v1/auth/login") == "login"

    def test_logout_path(self):
        """로그아웃 경로"""
        assert method_to_action("POST", "/api/v1/auth/logout") == "logout"

    def test_execute_path(self):
        """실행 경로"""
        assert method_to_action("POST", "/api/v1/workflows/123/execute") == "execute"

    def test_run_path(self):
        """실행(run) 경로"""
        assert method_to_action("POST", "/api/v1/rulesets/123/run") == "execute"

    def test_test_path(self):
        """테스트 경로"""
        assert method_to_action("POST", "/api/v1/rulesets/test") == "test"

    def test_unknown_method(self):
        """알 수 없는 메서드"""
        assert method_to_action("OPTIONS", "/api/v1/workflows") == "unknown"

    def test_case_insensitive(self):
        """대소문자 무관"""
        assert method_to_action("get", "/api/v1/workflows") == "read"
        assert method_to_action("Get", "/api/v1/workflows") == "read"


class TestAuditLogDatabase:
    """감사 로그 데이터베이스 테스트 (DB 연동)"""

    @pytest.fixture
    def sample_log_data(self):
        """샘플 로그 데이터"""
        return {
            "user_id": uuid4(),
            "tenant_id": uuid4(),
            "action": "create",
            "resource": "workflows",
            "resource_id": str(uuid4()),
            "method": "POST",
            "path": "/api/v1/workflows",
            "status_code": 201,
            "ip_address": "127.0.0.1",
            "user_agent": "pytest",
            "request_body": {"name": "Test Workflow"},
            "response_summary": "HTTP 201",
            "duration_ms": 50,
        }

    @pytest.mark.asyncio
    async def test_create_audit_log(self, db_session, sample_log_data):
        """감사 로그 생성 테스트"""
        log_id = await create_audit_log(
            db=db_session,
            **sample_log_data
        )

        # 로그 ID가 반환되어야 함
        assert log_id is not None

    @pytest.mark.asyncio
    async def test_create_audit_log_with_masking(self, db_session):
        """민감 정보 마스킹 후 로그 생성"""
        log_id = await create_audit_log(
            db=db_session,
            user_id=uuid4(),
            tenant_id=uuid4(),
            action="login",
            resource="auth",
            resource_id=None,
            method="POST",
            path="/api/v1/auth/login",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="pytest",
            request_body={"email": "test@test.com", "password": "secret123"},
            response_summary="HTTP 200",
            duration_ms=100,
        )

        # 로그가 생성되어야 함
        assert log_id is not None

    @pytest.mark.asyncio
    async def test_create_audit_log_without_user(self, db_session):
        """사용자 정보 없이 로그 생성 (비인증 요청)"""
        log_id = await create_audit_log(
            db=db_session,
            user_id=None,
            tenant_id=None,
            action="read",
            resource="health",
            resource_id=None,
            method="GET",
            path="/health",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent=None,
            request_body=None,
            response_summary="HTTP 200",
            duration_ms=10,
        )

        assert log_id is not None

    @pytest.mark.asyncio
    async def test_get_audit_logs(self, db_session, sample_log_data):
        """감사 로그 조회 테스트"""
        # 먼저 로그 생성
        await create_audit_log(db=db_session, **sample_log_data)

        # 로그 조회
        logs = await get_audit_logs(
            db=db_session,
            tenant_id=sample_log_data["tenant_id"],
            limit=10,
        )

        assert isinstance(logs, list)

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_filters(self, db_session, sample_log_data):
        """필터 적용 로그 조회"""
        user_id = uuid4()
        tenant_id = uuid4()

        # 여러 로그 생성
        for action in ["create", "read", "update", "delete"]:
            await create_audit_log(
                db=db_session,
                user_id=user_id,
                tenant_id=tenant_id,
                action=action,
                resource="workflows",
                resource_id=str(uuid4()),
                method="POST",
                path="/api/v1/workflows",
                status_code=200,
            )

        # 특정 액션 필터
        logs = await get_audit_logs(
            db=db_session,
            tenant_id=tenant_id,
            action="create",
        )

        assert isinstance(logs, list)

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_date_range(self, db_session, sample_log_data):
        """날짜 범위 필터 로그 조회"""
        await create_audit_log(db=db_session, **sample_log_data)

        now = datetime.utcnow()
        logs = await get_audit_logs(
            db=db_session,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
        )

        assert isinstance(logs, list)

    @pytest.mark.asyncio
    async def test_get_audit_stats(self, db_session, sample_log_data):
        """감사 로그 통계 조회"""
        tenant_id = uuid4()

        # 여러 로그 생성
        for i in range(5):
            await create_audit_log(
                db=db_session,
                user_id=uuid4(),
                tenant_id=tenant_id,
                action="read" if i % 2 == 0 else "create",
                resource="workflows" if i % 3 == 0 else "sensors",
                resource_id=str(uuid4()),
                method="GET" if i % 2 == 0 else "POST",
                path="/api/v1/test",
                status_code=200 if i % 4 != 0 else 400,
            )

        stats = await get_audit_stats(db=db_session, tenant_id=tenant_id)

        assert "total" in stats
        assert "by_resource" in stats
        assert "by_action" in stats
        assert "by_status" in stats

    @pytest.mark.asyncio
    async def test_get_audit_stats_empty(self, db_session):
        """빈 통계 조회"""
        stats = await get_audit_stats(
            db=db_session,
            tenant_id=uuid4(),  # 존재하지 않는 테넌트
        )

        assert stats["total"] == 0
        assert stats["by_resource"] == {}
        assert stats["by_action"] == {}
        assert stats["by_status"] == {}


class TestAuditLogEdgeCases:
    """감사 로그 엣지 케이스"""

    @pytest.mark.asyncio
    async def test_long_path(self, db_session):
        """긴 경로 처리"""
        long_path = "/api/v1/workflows/" + "a" * 600  # 500자 초과

        log_id = await create_audit_log(
            db=db_session,
            user_id=uuid4(),
            tenant_id=uuid4(),
            action="read",
            resource="workflows",
            resource_id=None,
            method="GET",
            path=long_path,
            status_code=200,
        )

        # 잘려서 저장되어야 함
        assert log_id is not None

    @pytest.mark.asyncio
    async def test_long_user_agent(self, db_session):
        """긴 User-Agent 처리"""
        long_ua = "Mozilla/5.0 " + "a" * 600

        log_id = await create_audit_log(
            db=db_session,
            user_id=uuid4(),
            tenant_id=uuid4(),
            action="read",
            resource="workflows",
            resource_id=None,
            method="GET",
            path="/api/v1/workflows",
            status_code=200,
            user_agent=long_ua,
        )

        assert log_id is not None

    @pytest.mark.asyncio
    async def test_large_request_body(self, db_session):
        """큰 요청 본문 처리"""
        large_body = {"data": ["item"] * 200}  # 큰 리스트

        log_id = await create_audit_log(
            db=db_session,
            user_id=uuid4(),
            tenant_id=uuid4(),
            action="create",
            resource="workflows",
            resource_id=None,
            method="POST",
            path="/api/v1/workflows",
            status_code=201,
            request_body=large_body,
        )

        assert log_id is not None

    @pytest.mark.asyncio
    async def test_invalid_json_body(self, db_session):
        """유효하지 않은 본문은 None 처리"""
        log_id = await create_audit_log(
            db=db_session,
            user_id=uuid4(),
            tenant_id=uuid4(),
            action="create",
            resource="workflows",
            resource_id=None,
            method="POST",
            path="/api/v1/workflows",
            status_code=201,
            request_body=None,  # None 본문
        )

        assert log_id is not None


# ========== Mock 기반 테스트 (DB 불필요) ==========
from unittest.mock import MagicMock, patch


class TestCreateAuditLogMock:
    """create_audit_log Mock 테스트"""

    @pytest.mark.asyncio
    async def test_create_log_success(self):
        """로그 생성 성공 (Mock)"""
        mock_db = MagicMock()

        user_id = uuid4()
        tenant_id = uuid4()

        log_id = await create_audit_log(
            db=mock_db,
            user_id=user_id,
            tenant_id=tenant_id,
            action="create",
            resource="workflows",
            resource_id="123",
            method="POST",
            path="/api/v1/workflows",
            status_code=201,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            request_body={"name": "Test Workflow"},
            response_summary="Created",
            duration_ms=100,
        )

        assert log_id is not None
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_log_with_sensitive_data_masked(self):
        """민감 정보가 마스킹되어 저장"""
        mock_db = MagicMock()

        log_id = await create_audit_log(
            db=mock_db,
            user_id=uuid4(),
            tenant_id=uuid4(),
            action="login",
            resource="auth",
            resource_id=None,
            method="POST",
            path="/api/v1/auth/login",
            status_code=200,
            request_body={"username": "user1", "password": "secret123"},
        )

        assert log_id is not None
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        if params.get("request_body"):
            assert "***MASKED***" in params["request_body"]

    @pytest.mark.asyncio
    async def test_create_log_failure_rollback(self):
        """로그 생성 실패 시 롤백"""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database error")

        log_id = await create_audit_log(
            db=mock_db,
            user_id=uuid4(),
            tenant_id=uuid4(),
            action="create",
            resource="workflows",
            resource_id="123",
            method="POST",
            path="/api/v1/workflows",
            status_code=201,
        )

        assert log_id is None
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_log_truncates_long_path(self):
        """긴 경로 잘림"""
        mock_db = MagicMock()

        long_path = "/api/v1/" + "a" * 600

        log_id = await create_audit_log(
            db=mock_db,
            user_id=uuid4(),
            tenant_id=uuid4(),
            action="read",
            resource="test",
            resource_id=None,
            method="GET",
            path=long_path,
            status_code=200,
        )

        assert log_id is not None
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert len(params["path"]) <= 500

    @pytest.mark.asyncio
    async def test_create_log_truncates_user_agent(self):
        """긴 User-Agent 잘림"""
        mock_db = MagicMock()

        long_ua = "Mozilla/5.0 " + "x" * 600

        log_id = await create_audit_log(
            db=mock_db,
            user_id=uuid4(),
            tenant_id=uuid4(),
            action="read",
            resource="test",
            resource_id=None,
            method="GET",
            path="/api/v1/test",
            status_code=200,
            user_agent=long_ua,
        )

        assert log_id is not None
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert len(params["user_agent"]) <= 500

    @pytest.mark.asyncio
    async def test_create_log_truncates_response_summary(self):
        """긴 response_summary 잘림"""
        mock_db = MagicMock()

        long_summary = "Success: " + "x" * 600

        log_id = await create_audit_log(
            db=mock_db,
            user_id=uuid4(),
            tenant_id=uuid4(),
            action="read",
            resource="test",
            resource_id=None,
            method="GET",
            path="/api/v1/test",
            status_code=200,
            response_summary=long_summary,
        )

        assert log_id is not None
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert len(params["response_summary"]) <= 500

    @pytest.mark.asyncio
    async def test_create_log_without_optional_fields(self):
        """선택 필드 없이 로그 생성"""
        mock_db = MagicMock()

        log_id = await create_audit_log(
            db=mock_db,
            user_id=None,
            tenant_id=None,
            action="read",
            resource="test",
            resource_id=None,
            method="GET",
            path="/api/v1/test",
            status_code=200,
        )

        assert log_id is not None
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["user_id"] is None
        assert params["tenant_id"] is None
        assert params["request_body"] is None


class TestGetAuditLogsMock:
    """get_audit_logs Mock 테스트"""

    @pytest.mark.asyncio
    async def test_get_logs_success(self):
        """로그 조회 성공"""
        mock_db = MagicMock()

        mock_row = (
            uuid4(), uuid4(), uuid4(),
            "create", "workflows", "123",
            "POST", "/api/v1/workflows", 201,
            "192.168.1.1", "Mozilla/5.0",
            '{"name": "test"}', "Created", 100,
            datetime.now(),
        )
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        logs = await get_audit_logs(db=mock_db, limit=10, offset=0)

        assert len(logs) == 1
        assert logs[0]["action"] == "create"
        assert logs[0]["resource"] == "workflows"

    @pytest.mark.asyncio
    async def test_get_logs_with_all_filters(self):
        """모든 필터 적용 로그 조회"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        user_id = uuid4()
        tenant_id = uuid4()

        logs = await get_audit_logs(
            db=mock_db,
            user_id=user_id,
            tenant_id=tenant_id,
            resource="workflows",
            action="create",
            status_code=201,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            limit=50,
            offset=10,
        )

        assert logs == []
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_logs_failure(self):
        """로그 조회 실패"""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database error")

        logs = await get_audit_logs(db=mock_db)

        assert logs == []

    @pytest.mark.asyncio
    async def test_get_logs_with_null_values(self):
        """NULL 값이 있는 로그 조회"""
        mock_db = MagicMock()

        mock_row = (
            uuid4(), None, None,
            "read", "public", None,
            "GET", "/health", 200,
            None, None, None, None, None, None,
        )
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        logs = await get_audit_logs(db=mock_db)

        assert len(logs) == 1
        assert logs[0]["user_id"] is None
        assert logs[0]["tenant_id"] is None
        assert logs[0]["created_at"] is None


class TestGetAuditStatsMock:
    """get_audit_stats Mock 테스트"""

    @pytest.mark.asyncio
    async def test_get_stats_success(self):
        """통계 조회 성공"""
        mock_db = MagicMock()

        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 100

        mock_resource_result = MagicMock()
        mock_resource_result.fetchall.return_value = [
            ("workflows", 50), ("tenants", 30), ("users", 20),
        ]

        mock_action_result = MagicMock()
        mock_action_result.fetchall.return_value = [
            ("create", 40), ("read", 35), ("update", 15), ("delete", 10),
        ]

        mock_status_result = MagicMock()
        mock_status_result.fetchall.return_value = [
            ("success", 80), ("client_error", 15), ("server_error", 5),
        ]

        mock_db.execute.side_effect = [
            mock_total_result,
            mock_resource_result,
            mock_action_result,
            mock_status_result,
        ]

        stats = await get_audit_stats(db=mock_db)

        assert stats["total"] == 100
        assert stats["by_resource"]["workflows"] == 50
        assert stats["by_action"]["create"] == 40
        assert stats["by_status"]["success"] == 80

    @pytest.mark.asyncio
    async def test_get_stats_with_all_filters(self):
        """모든 필터 적용 통계 조회"""
        mock_db = MagicMock()

        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 50

        mock_resource_result = MagicMock()
        mock_resource_result.fetchall.return_value = []

        mock_action_result = MagicMock()
        mock_action_result.fetchall.return_value = []

        mock_status_result = MagicMock()
        mock_status_result.fetchall.return_value = []

        mock_db.execute.side_effect = [
            mock_total_result,
            mock_resource_result,
            mock_action_result,
            mock_status_result,
        ]

        tenant_id = uuid4()
        stats = await get_audit_stats(
            db=mock_db,
            tenant_id=tenant_id,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        assert stats["total"] == 50
        assert mock_db.execute.call_count == 4

    @pytest.mark.asyncio
    async def test_get_stats_failure(self):
        """통계 조회 실패"""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database error")

        stats = await get_audit_stats(db=mock_db)

        assert stats == {"total": 0, "by_resource": {}, "by_action": {}, "by_status": {}}
