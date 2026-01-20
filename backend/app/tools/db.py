"""
Safe SQL Query Executor
안전한 SQL 쿼리 실행 도구

BI Planner Agent가 생성한 SQL을 안전하게 실행합니다.
"""
from typing import Any, Dict, List, Optional
import re
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings


class SafeQueryExecutor:
    """
    안전한 SQL 쿼리 실행기

    특징:
    - SELECT 문만 허용 (DML/DDL 차단)
    - SQL Injection 방어
    - 타임아웃 설정
    - 결과 행 수 제한
    - 동적 스키마 허용 (DomainRegistry 통합)
    """

    def __init__(
        self,
        engine: Optional[Engine] = None,
        max_rows: int = 1000,
        timeout_seconds: int = 30,
    ):
        """
        Args:
            engine: SQLAlchemy 엔진 (None이면 기본 엔진 생성)
            max_rows: 최대 반환 행 수
            timeout_seconds: 쿼리 타임아웃 (초)
        """
        self.engine = engine or create_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={"options": f"-c statement_timeout={timeout_seconds * 1000}"},
        )
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds

        # 도메인 레지스트리 (동적 스키마 허용)
        from app.services.domain_registry import get_domain_registry
        self.domain_registry = get_domain_registry()

    def execute(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        SQL 쿼리 실행

        Args:
            sql: 실행할 SQL 쿼리 (SELECT만 허용)
            params: 쿼리 파라미터 (선택)

        Returns:
            쿼리 결과 (딕셔너리 리스트)

        Raises:
            ValueError: 허용되지 않는 SQL 문 실행 시도
            SQLAlchemyError: 쿼리 실행 실패
        """
        # 쿼리 검증
        if not self.validate(sql):
            raise ValueError("Only SELECT queries are allowed")

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), params or {})

                # 결과를 딕셔너리 리스트로 변환
                rows = []
                for row in result.fetchmany(self.max_rows):
                    rows.append(dict(row._mapping))

                return rows

        except SQLAlchemyError as e:
            raise SQLAlchemyError(f"Query execution failed: {str(e)}")

    def validate(self, sql: str) -> bool:
        """
        SQL 쿼리 검증

        Args:
            sql: 검증할 SQL 쿼리

        Returns:
            안전하면 True

        검증 규칙:
        - SELECT 문만 허용
        - DML (INSERT, UPDATE, DELETE) 차단
        - DDL (CREATE, ALTER, DROP) 차단
        - 시스템 테이블 접근 차단
        """
        if not sql or not isinstance(sql, str):
            return False

        # 정규화 (주석 제거, 공백 정리)
        normalized = self._normalize_sql(sql)

        # SELECT 문인지 확인
        if not normalized.strip().upper().startswith('SELECT'):
            return False

        # 금지된 키워드 체크
        forbidden_keywords = [
            r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b',
            r'\bDROP\b', r'\bCREATE\b', r'\bALTER\b',
            r'\bTRUNCATE\b', r'\bGRANT\b', r'\bREVOKE\b',
            r'\bEXEC\b', r'\bEXECUTE\b',
            r'INTO\s+OUTFILE', r'LOAD_FILE',
            r'pg_sleep', r'pg_read_file',
        ]

        for pattern in forbidden_keywords:
            if re.search(pattern, normalized, re.IGNORECASE):
                return False

        # 시스템 스키마 접근 체크
        system_schemas = ['pg_catalog', 'information_schema', 'pg_temp']
        for schema in system_schemas:
            if re.search(rf'\b{schema}\b', normalized, re.IGNORECASE):
                return False

        return True

    def _normalize_sql(self, sql: str) -> str:
        """
        SQL 쿼리 정규화

        - 주석 제거 (-- 및 /* */)
        - 여러 공백을 하나로 압축
        """
        # 한줄 주석 제거 (-- ...)
        sql = re.sub(r'--[^\n]*', '', sql)

        # 여러줄 주석 제거 (/* ... */)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

        # 여러 공백을 하나로
        sql = re.sub(r'\s+', ' ', sql)

        return sql.strip()

    def get_table_schema(self, schema: str, table: str) -> Dict[str, Any]:
        """
        테이블 스키마 정보 조회 (동적 스키마 허용)

        Args:
            schema: 스키마 이름 (e.g., 'core', 'bi', 'korea_biopharm')
            table: 테이블 이름

        Returns:
            테이블 스키마 정보 (컬럼명, 타입 등)
        """
        # 동적으로 허용된 스키마 목록 생성
        allowed_schemas = self.domain_registry.get_all_schemas()

        if schema not in allowed_schemas:
            raise ValueError(
                f"Schema '{schema}' is not allowed. "
                f"Allowed: {', '.join(allowed_schemas)}"
            )

        query = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
            ORDER BY ordinal_position
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(query),
                    {"schema": schema, "table": table}
                )

                columns = []
                for row in result:
                    columns.append({
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2] == 'YES',
                        "default": row[3],
                    })

                return {
                    "schema": schema,
                    "table": table,
                    "columns": columns,
                }

        except SQLAlchemyError as e:
            raise SQLAlchemyError(f"Failed to fetch table schema: {str(e)}")

    def get_available_tables(self, schema: str) -> List[str]:
        """
        스키마 내 사용 가능한 테이블 목록 조회 (동적 허용)

        Args:
            schema: 스키마 이름

        Returns:
            테이블 이름 리스트
        """
        # 동적으로 허용된 스키마 목록 생성
        allowed_schemas = self.domain_registry.get_all_schemas()

        if schema not in allowed_schemas:
            raise ValueError(f"Schema '{schema}' is not allowed")

        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {"schema": schema})
                return [row[0] for row in result]

        except SQLAlchemyError as e:
            raise SQLAlchemyError(f"Failed to fetch tables: {str(e)}")


# 전역 쿼리 실행기 인스턴스
_executor = None


def get_executor() -> SafeQueryExecutor:
    """전역 SafeQueryExecutor 인스턴스 반환"""
    global _executor
    if _executor is None:
        _executor = SafeQueryExecutor()
    return _executor


def execute_safe_sql(sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    안전한 SQL 쿼리 실행 헬퍼 함수

    Args:
        sql: SELECT 쿼리
        params: 쿼리 파라미터

    Returns:
        쿼리 결과
    """
    executor = get_executor()
    return executor.execute(sql, params)


def get_table_schema(schema: str, table: str) -> Dict[str, Any]:
    """
    테이블 스키마 조회 헬퍼 함수

    Args:
        schema: 스키마 이름
        table: 테이블 이름

    Returns:
        스키마 정보
    """
    executor = get_executor()
    return executor.get_table_schema(schema, table)
