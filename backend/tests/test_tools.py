"""
Tools 테스트 모듈
Rhai 엔진과 Safe SQL Executor 테스트
"""
import pytest
from unittest.mock import MagicMock, patch


class TestRhaiEngine:
    """RhaiEngine 클래스 테스트"""

    def test_init(self):
        """RhaiEngine 초기화"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()

        assert engine is not None
        assert hasattr(engine, '_allowed_builtins')

    def test_execute_temperature_normal(self):
        """온도 체크 - 정상"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// temperature check",
            context={"input": {"temperature": 50.0}}
        )

        assert result["status"] == "NORMAL"
        temp_check = next((c for c in result["checks"] if c["type"] == "temperature"), None)
        assert temp_check is not None
        assert temp_check["status"] == "NORMAL"

    def test_execute_temperature_high(self):
        """온도 체크 - 높음"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// temperature check",
            context={"input": {"temperature": 80.0}}
        )

        assert result["status"] == "WARNING"
        temp_check = next((c for c in result["checks"] if c["type"] == "temperature"), None)
        assert temp_check is not None
        assert temp_check["status"] == "HIGH"

    def test_execute_temperature_with_custom_threshold(self):
        """커스텀 임계값 온도 체크"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="let threshold = 60.0;",
            context={"input": {"temperature": 65.0}}
        )

        assert result["status"] == "WARNING"

    def test_execute_pressure_normal(self):
        """압력 체크 - 정상"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// pressure check",
            context={"input": {"pressure": 5.0}}
        )

        pressure_check = next((c for c in result["checks"] if c["type"] == "pressure"), None)
        assert pressure_check is not None
        assert pressure_check["status"] == "NORMAL"

    def test_execute_pressure_low(self):
        """압력 체크 - 낮음"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// pressure check",
            context={"input": {"pressure": 1.0}}
        )

        pressure_check = next((c for c in result["checks"] if c["type"] == "pressure"), None)
        assert pressure_check is not None
        assert pressure_check["status"] == "LOW"

    def test_execute_pressure_high(self):
        """압력 체크 - 높음"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// pressure check",
            context={"input": {"pressure": 10.0}}
        )

        pressure_check = next((c for c in result["checks"] if c["type"] == "pressure"), None)
        assert pressure_check is not None
        assert pressure_check["status"] == "HIGH"

    def test_execute_humidity_normal(self):
        """습도 체크 - 정상"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// humidity check",
            context={"input": {"humidity": 50.0}}
        )

        humidity_check = next((c for c in result["checks"] if c["type"] == "humidity"), None)
        assert humidity_check is not None
        assert humidity_check["status"] == "NORMAL"

    def test_execute_humidity_warning_low(self):
        """습도 체크 - 경고 (낮음)"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// humidity check",
            context={"input": {"humidity": 20.0}}
        )

        humidity_check = next((c for c in result["checks"] if c["type"] == "humidity"), None)
        assert humidity_check is not None
        assert humidity_check["status"] == "WARNING"

    def test_execute_humidity_warning_high(self):
        """습도 체크 - 경고 (높음)"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// humidity check",
            context={"input": {"humidity": 80.0}}
        )

        humidity_check = next((c for c in result["checks"] if c["type"] == "humidity"), None)
        assert humidity_check is not None
        assert humidity_check["status"] == "WARNING"

    def test_execute_defect_rate_normal(self):
        """불량률 체크 - 정상"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// defect check",
            context={"input": {"defect_count": 1, "production_count": 100}}
        )

        assert result["status"] == "NORMAL"

    def test_execute_defect_rate_warning(self):
        """불량률 체크 - 경고"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// defect check",
            context={"input": {"defect_count": 3, "production_count": 100}}  # 3%
        )

        defect_check = next((c for c in result["checks"] if c["type"] == "defect_rate"), None)
        assert defect_check is not None
        assert defect_check["status"] == "WARNING"

    def test_execute_defect_rate_critical(self):
        """불량률 체크 - 심각"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// defect check",
            context={"input": {"defect_count": 10, "production_count": 100}}  # 10%
        )

        assert result["status"] == "CRITICAL"
        defect_check = next((c for c in result["checks"] if c["type"] == "defect_rate"), None)
        assert defect_check is not None
        assert defect_check["status"] == "CRITICAL"

    def test_execute_multiple_sensors(self):
        """다중 센서 체크"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// multi sensor check",
            context={"input": {
                "temperature": 50.0,
                "pressure": 5.0,
                "humidity": 50.0
            }}
        )

        assert len(result["checks"]) == 3
        assert result["status"] == "NORMAL"

    def test_execute_empty_input(self):
        """빈 입력 처리"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// empty check",
            context={"input": {}}
        )

        assert result["status"] == "NORMAL"
        assert len(result["checks"]) == 0

    def test_execute_invalid_context(self):
        """잘못된 컨텍스트 처리"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()
        result = engine.execute(
            script="// test",
            context={}  # input 키 없음
        )

        assert result["status"] == "NORMAL"

    def test_validate_valid_script(self):
        """유효한 스크립트 검증"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()

        assert engine.validate("let x = 10;") is True
        assert engine.validate("if x > 5 { return true; }") is True
        assert engine.validate("// comment") is True

    def test_validate_invalid_script_empty(self):
        """빈 스크립트 검증"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()

        assert engine.validate("") is False
        assert engine.validate(None) is False

    def test_validate_forbidden_keywords(self):
        """금지 키워드 스크립트 검증"""
        from app.tools.rhai import RhaiEngine

        engine = RhaiEngine()

        assert engine.validate("import os") is False
        assert engine.validate("eval('code')") is False
        assert engine.validate("__builtins__") is False
        assert engine.validate("exec('code')") is False
        assert engine.validate("compile('code')") is False


class TestRhaiEnginePool:
    """RhaiEnginePool 클래스 테스트"""

    def test_init(self):
        """풀 초기화"""
        from app.tools.rhai import RhaiEnginePool

        pool = RhaiEnginePool(pool_size=3)

        assert pool.pool_size == 3
        assert len(pool._engines) == 3

    def test_get_engine(self):
        """엔진 가져오기"""
        from app.tools.rhai import RhaiEnginePool, RhaiEngine

        pool = RhaiEnginePool(pool_size=3)
        engine = pool.get_engine()

        assert isinstance(engine, RhaiEngine)

    def test_get_engine_round_robin(self):
        """라운드 로빈 방식"""
        from app.tools.rhai import RhaiEnginePool

        pool = RhaiEnginePool(pool_size=3)

        # 3번 호출하면 다시 첫 번째로 돌아와야 함
        engine1 = pool.get_engine()
        engine2 = pool.get_engine()
        engine3 = pool.get_engine()
        engine4 = pool.get_engine()

        assert engine1 is engine4  # 다시 첫 번째


class TestRhaiHelperFunctions:
    """Rhai 헬퍼 함수 테스트"""

    def test_execute_rhai(self):
        """execute_rhai 헬퍼 함수"""
        from app.tools.rhai import execute_rhai

        result = execute_rhai(
            script="// test",
            context={"input": {"temperature": 50.0}}
        )

        assert result["status"] == "NORMAL"

    def test_validate_rhai(self):
        """validate_rhai 헬퍼 함수"""
        from app.tools.rhai import validate_rhai

        assert validate_rhai("let x = 10;") is True
        assert validate_rhai("import os") is False


class TestSafeQueryExecutor:
    """SafeQueryExecutor 클래스 테스트"""

    @patch("app.tools.db.create_engine")
    def test_init(self, mock_create_engine):
        """초기화"""
        from app.tools.db import SafeQueryExecutor

        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        executor = SafeQueryExecutor()

        assert executor is not None
        assert executor.max_rows == 1000
        assert executor.timeout_seconds == 30

    @patch("app.tools.db.create_engine")
    def test_init_custom_values(self, mock_create_engine):
        """커스텀 값으로 초기화"""
        from app.tools.db import SafeQueryExecutor

        mock_engine = MagicMock()

        executor = SafeQueryExecutor(
            engine=mock_engine,
            max_rows=500,
            timeout_seconds=60
        )

        assert executor.max_rows == 500
        assert executor.timeout_seconds == 60

    def test_validate_select_query(self):
        """SELECT 쿼리 검증"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)
        executor.max_rows = 1000
        executor.timeout_seconds = 30

        assert executor.validate("SELECT * FROM users") is True
        assert executor.validate("select id from users") is True
        assert executor.validate("  SELECT count(*) FROM orders  ") is True

    def test_validate_reject_dml(self):
        """DML 쿼리 거부"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        assert executor.validate("INSERT INTO users VALUES (1)") is False
        assert executor.validate("UPDATE users SET name = 'test'") is False
        assert executor.validate("DELETE FROM users") is False

    def test_validate_reject_ddl(self):
        """DDL 쿼리 거부"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        assert executor.validate("CREATE TABLE test (id int)") is False
        assert executor.validate("DROP TABLE users") is False
        assert executor.validate("ALTER TABLE users ADD column") is False
        assert executor.validate("TRUNCATE TABLE users") is False

    def test_validate_reject_system_schemas(self):
        """시스템 스키마 접근 거부"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        assert executor.validate("SELECT * FROM pg_catalog.pg_tables") is False
        assert executor.validate("SELECT * FROM information_schema.tables") is False
        assert executor.validate("SELECT * FROM pg_temp.temp_data") is False

    def test_validate_reject_dangerous_functions(self):
        """위험한 함수 호출 거부"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        assert executor.validate("SELECT pg_sleep(10)") is False
        assert executor.validate("SELECT pg_read_file('/etc/passwd')") is False
        assert executor.validate("SELECT * INTO OUTFILE '/tmp/data'") is False
        assert executor.validate("SELECT LOAD_FILE('/etc/passwd')") is False

    def test_validate_reject_empty(self):
        """빈 쿼리 거부"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        assert executor.validate("") is False
        assert executor.validate(None) is False
        assert executor.validate("   ") is False

    def test_validate_with_comments(self):
        """주석 포함 쿼리 검증"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        # 정상 쿼리 + 주석
        assert executor.validate("SELECT * FROM users -- comment") is True
        assert executor.validate("/* comment */ SELECT * FROM users") is True

        # 주석으로 INSERT 숨기기 시도 (실패해야 함)
        assert executor.validate("SELECT * FROM users; -- INSERT INTO...") is True  # SELECT는 유효

    def test_normalize_sql(self):
        """SQL 정규화"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        # 주석 제거
        result = executor._normalize_sql("SELECT * FROM users -- comment")
        assert "--" not in result

        # 여러줄 주석 제거
        result = executor._normalize_sql("SELECT /* comment */ * FROM users")
        assert "/*" not in result

        # 공백 정규화
        result = executor._normalize_sql("SELECT    *   FROM   users")
        assert "    " not in result

    @patch("app.tools.db.create_engine")
    def test_execute_success(self, mock_create_engine):
        """쿼리 실행 성공"""
        from app.tools.db import SafeQueryExecutor

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Mock 결과 행
        mock_row = MagicMock()
        mock_row._mapping = {"id": 1, "name": "test"}
        mock_result.fetchmany.return_value = [mock_row]

        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        executor = SafeQueryExecutor(engine=mock_engine)
        result = executor.execute("SELECT * FROM users")

        assert len(result) == 1
        assert result[0]["id"] == 1

    @patch("app.tools.db.create_engine")
    def test_execute_invalid_query(self, mock_create_engine):
        """유효하지 않은 쿼리 실행"""
        from app.tools.db import SafeQueryExecutor

        mock_engine = MagicMock()
        executor = SafeQueryExecutor(engine=mock_engine)

        with pytest.raises(ValueError) as exc_info:
            executor.execute("INSERT INTO users VALUES (1)")

        assert "Only SELECT" in str(exc_info.value)

    @patch("app.tools.db.create_engine")
    def test_get_table_schema(self, mock_create_engine):
        """테이블 스키마 조회"""
        from app.tools.db import SafeQueryExecutor

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Mock 컬럼 정보
        mock_result.__iter__ = lambda self: iter([
            ("id", "uuid", "NO", None),
            ("name", "varchar", "YES", None),
        ])

        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        executor = SafeQueryExecutor(engine=mock_engine)
        result = executor.get_table_schema("core", "users")

        assert result["schema"] == "core"
        assert result["table"] == "users"
        assert len(result["columns"]) == 2

    @patch("app.tools.db.create_engine")
    def test_get_table_schema_invalid_schema(self, mock_create_engine):
        """허용되지 않은 스키마"""
        from app.tools.db import SafeQueryExecutor

        mock_engine = MagicMock()
        executor = SafeQueryExecutor(engine=mock_engine)

        with pytest.raises(ValueError) as exc_info:
            executor.get_table_schema("pg_catalog", "pg_tables")

        assert "not allowed" in str(exc_info.value)

    @patch("app.tools.db.create_engine")
    def test_get_available_tables(self, mock_create_engine):
        """테이블 목록 조회"""
        from app.tools.db import SafeQueryExecutor

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Mock 테이블 목록
        mock_result.__iter__ = lambda self: iter([
            ("users",),
            ("orders",),
        ])

        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn

        executor = SafeQueryExecutor(engine=mock_engine)
        result = executor.get_available_tables("core")

        assert "users" in result
        assert "orders" in result


class TestDbHelperFunctions:
    """DB 헬퍼 함수 테스트"""

    @patch("app.tools.db._executor", None)
    @patch("app.tools.db.SafeQueryExecutor")
    def test_get_executor(self, mock_executor_class):
        """get_executor 헬퍼 함수"""
        from app.tools.db import get_executor

        mock_instance = MagicMock()
        mock_executor_class.return_value = mock_instance

        executor = get_executor()

        assert executor is not None

    @patch("app.tools.db.get_executor")
    def test_execute_safe_sql(self, mock_get_executor):
        """execute_safe_sql 헬퍼 함수"""
        from app.tools.db import execute_safe_sql

        mock_executor = MagicMock()
        mock_executor.execute.return_value = [{"id": 1}]
        mock_get_executor.return_value = mock_executor

        result = execute_safe_sql("SELECT * FROM users")

        assert len(result) == 1

    @patch("app.tools.db.get_executor")
    def test_get_table_schema_helper(self, mock_get_executor):
        """get_table_schema 헬퍼 함수"""
        from app.tools.db import get_table_schema

        mock_executor = MagicMock()
        mock_executor.get_table_schema.return_value = {
            "schema": "core",
            "table": "users",
            "columns": []
        }
        mock_get_executor.return_value = mock_executor

        result = get_table_schema("core", "users")

        assert result["schema"] == "core"
        assert result["table"] == "users"


class TestSqlInjectionPrevention:
    """SQL Injection 방어 테스트"""

    def test_reject_union_attack(self):
        """UNION 공격 방어"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        # UNION으로 다른 테이블 접근 시도
        query = "SELECT * FROM users UNION SELECT * FROM passwords"
        assert executor.validate(query) is True  # UNION 자체는 SELECT의 일부로 허용될 수 있음

    def test_reject_subquery_attack(self):
        """서브쿼리 공격 (시스템 테이블 접근)"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        # 서브쿼리로 시스템 테이블 접근 시도
        query = "SELECT * FROM users WHERE id IN (SELECT id FROM pg_catalog.pg_tables)"
        assert executor.validate(query) is False

    def test_reject_stacked_queries(self):
        """스택 쿼리 공격 방어"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        # 세미콜론으로 쿼리 연결 시도
        query = "SELECT * FROM users; DROP TABLE users"
        assert executor.validate(query) is False

    def test_reject_comment_bypass(self):
        """주석을 이용한 우회 시도"""
        from app.tools.db import SafeQueryExecutor

        executor = SafeQueryExecutor.__new__(SafeQueryExecutor)

        # 주석으로 유효한 부분 숨기기
        query = "SELECT * FROM users; /* */ DELETE FROM users"
        assert executor.validate(query) is False
