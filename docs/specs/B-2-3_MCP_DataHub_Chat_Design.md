# B-2-3. Module/Service Design - MCP ToolHub, Data Hub, Chat Service

## 문서 정보
- **문서 ID**: B-2-3
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **선행 문서**: B-2-1, B-2-2

## 목차
1. [MCP ToolHub 상세 설계](#1-mcp-toolhub-상세-설계)
2. [Data Hub 상세 설계](#2-data-hub-상세-설계)
3. [Chat Service 상세 설계](#3-chat-service-상세-설계)

---

## 1. MCP ToolHub 상세 설계

### 1.1 서비스 개요
MCP ToolHub는 외부 MCP 서버(Excel, GDrive, Jira, 로봇 등) 호출을 표준화하는 게이트웨이다.

**책임**:
- MCP 서버 레지스트리 관리
- 도구 메타데이터 저장
- 도구 호출 프록시 (인증, 타임아웃, 재시도)
- Circuit Breaker
- 커넥터 헬스 체크
- Drift 감지

### 1.2 클래스 다이어그램

```
┌──────────────────────────────────────────────────────────┐
│                    MCPToolHubService                     │
├──────────────────────────────────────────────────────────┤
│ - registry: IMCPRegistry                                 │
│ - proxy: IMCPProxy                                       │
│ - circuit_breaker: ICircuitBreaker                       │
│ - connector_manager: IConnectorManager                   │
│ - drift_detector: IDriftDetector                         │
├──────────────────────────────────────────────────────────┤
│ + register_server(server: MCPServer) → void              │
│ + call_tool(server_id: str, tool_name: str, args: dict)  │
│ + health_check(connector_id: str) → HealthStatus         │
│ + detect_drift(connector_id: str) → DriftReport          │
└──────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│IMCPProxy     │  │ICircuit      │  │IDrift        │
│              │  │Breaker       │  │Detector      │
└──────────────┘  └──────────────┘  └──────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│HTTPMCPProxy  │  │CircuitBreaker│  │SchemaDrift   │
│              │  │              │  │Detector      │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 1.3 주요 컴포넌트

#### 1.3.1 MCPProxy

**책임**: MCP 서버 호출 프록시

```python
import httpx
from typing import Dict, Any

class HTTPMCPProxy(IMCPProxy):
    def __init__(self, circuit_breaker: ICircuitBreaker):
        self.circuit_breaker = circuit_breaker
        self.client = httpx.AsyncClient()

    async def call_tool(
        self,
        server: MCPServer,
        tool_name: str,
        args: dict
    ) -> Dict[str, Any]:
        """MCP 도구 호출"""
        # 1. Circuit Breaker 통과 확인
        if self.circuit_breaker.is_open(server.id):
            raise CircuitBreakerOpenError(f"Circuit breaker OPEN for server {server.id}")

        # 2. 인증 헤더 구성
        headers = self._build_auth_headers(server)

        # 3. MCP Protocol 요청 구성
        payload = {
            "jsonrpc": "2.0",
            "method": f"tools/{tool_name}",
            "params": args,
            "id": str(uuid.uuid4())
        }

        # 4. HTTP 요청 (타임아웃 적용)
        try:
            response = await self.client.post(
                f"{server.base_url}/mcp",
                json=payload,
                headers=headers,
                timeout=server.timeout_ms / 1000
            )
            response.raise_for_status()

            # 5. 응답 파싱
            result = response.json()

            # 6. 성공 기록
            self.circuit_breaker.record_success(server.id)

            return result.get('result', {})

        except httpx.TimeoutException:
            self.circuit_breaker.record_failure(server.id)
            raise MCPTimeoutError(f"MCP server timeout (> {server.timeout_ms}ms)")

        except httpx.HTTPStatusError as e:
            self.circuit_breaker.record_failure(server.id)
            raise MCPHTTPError(f"MCP server error: {e.response.status_code}")

    def _build_auth_headers(self, server: MCPServer) -> dict:
        """인증 헤더 구성"""
        if server.auth_type == 'api_key':
            return {'Authorization': f'Bearer {server.api_key}'}
        elif server.auth_type == 'oauth2':
            token = self._get_oauth_token(server)
            return {'Authorization': f'Bearer {token}'}
        else:
            return {}

    def _get_oauth_token(self, server: MCPServer) -> str:
        """OAuth 토큰 조회 (캐시 또는 재발급)"""
        # OAuth 토큰 캐시 조회
        cache_key = f"oauth:token:{server.id}"
        token = redis_client.get(cache_key)

        if token:
            return token

        # 토큰 재발급
        response = requests.post(
            server.oauth_config['token_url'],
            data={
                'grant_type': 'client_credentials',
                'client_id': server.oauth_config['client_id'],
                'client_secret': server.oauth_config['client_secret']
            }
        )

        token_data = response.json()
        access_token = token_data['access_token']
        expires_in = token_data['expires_in']

        # 캐시 저장 (만료 시간 - 60초 여유)
        redis_client.setex(cache_key, expires_in - 60, access_token)

        return access_token
```

#### 1.3.2 SchemaDriftDetector

**책임**: 외부 데이터 소스 스키마 변경 감지

```python
from typing import List, Dict

class SchemaDriftDetector(IDriftDetector):
    async def detect_drift(self, connector: DataConnector) -> DriftReport:
        """스키마 변경 감지"""
        # 1. 현재 스키마 조회
        current_schema = await self._get_current_schema(connector)

        # 2. 스냅샷 스키마 조회 (마지막 저장본)
        snapshot = await self.repository.get_latest_snapshot(connector.id)

        if not snapshot:
            # 최초 실행 → 스냅샷 저장
            await self.repository.save_snapshot(connector.id, current_schema)
            return DriftReport(changes=[], has_changes=False)

        # 3. 비교
        changes = self._compare_schemas(snapshot.schema, current_schema)

        # 4. 변경 있으면 저장
        if changes:
            await self.repository.save_drift_detection(
                connector_id=connector.id,
                changes=changes
            )

            # 5. 알람 발송
            await self._send_drift_alert(connector, changes)

        return DriftReport(changes=changes, has_changes=len(changes) > 0)

    async def _get_current_schema(self, connector: DataConnector) -> dict:
        """현재 스키마 조회 (DB 타입별)"""
        if connector.type == 'postgresql':
            return await self._get_postgres_schema(connector)
        elif connector.type == 'mysql':
            return await self._get_mysql_schema(connector)
        else:
            raise UnsupportedConnectorType(f"Unsupported type: {connector.type}")

    async def _get_postgres_schema(self, connector: DataConnector) -> dict:
        """PostgreSQL 스키마 조회"""
        engine = create_engine(connector.connection_url)

        # 테이블 목록
        tables_query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """
        tables = [row[0] for row in engine.execute(tables_query)]

        schema = {}
        for table_name in tables:
            # 컬럼 정보
            columns_query = f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
            """
            columns = [dict(row) for row in engine.execute(columns_query)]
            schema[table_name] = {'columns': columns}

        return schema

    def _compare_schemas(self, old_schema: dict, new_schema: dict) -> List[Dict]:
        """스키마 비교"""
        changes = []

        # 테이블별 비교
        for table_name, old_table in old_schema.items():
            if table_name not in new_schema:
                # 테이블 삭제
                changes.append({
                    'type': 'table_deleted',
                    'table_name': table_name
                })
                continue

            new_table = new_schema[table_name]

            # 컬럼별 비교
            old_columns = {c['column_name']: c for c in old_table['columns']}
            new_columns = {c['column_name']: c for c in new_table['columns']}

            for col_name, old_col in old_columns.items():
                if col_name not in new_columns:
                    # 컬럼 삭제
                    changes.append({
                        'type': 'column_deleted',
                        'table_name': table_name,
                        'column_name': col_name
                    })
                elif old_col['data_type'] != new_columns[col_name]['data_type']:
                    # 타입 변경
                    changes.append({
                        'type': 'type_changed',
                        'table_name': table_name,
                        'column_name': col_name,
                        'old_type': old_col['data_type'],
                        'new_type': new_columns[col_name]['data_type']
                    })

            for col_name, new_col in new_columns.items():
                if col_name not in old_columns:
                    # 컬럼 추가
                    changes.append({
                        'type': 'column_added',
                        'table_name': table_name,
                        'column_name': col_name,
                        'details': new_col
                    })

        return changes
```

---

## 2. Data Hub 상세 설계

### 2.1 서비스 개요
Data Hub는 외부 데이터 소스에서 데이터를 수집하고, ETL 파이프라인을 실행하며, 벡터 임베딩을 생성하는 데이터 처리 엔진이다.

**책임**:
- ETL 작업 관리 (RAW → DIM → FACT)
- 데이터 품질 검사
- 벡터 임베딩 생성
- Materialized View 리프레시
- 파티션 관리

### 2.2 클래스 다이어그램

```
┌──────────────────────────────────────────────────────────┐
│                      DataHubService                      │
├──────────────────────────────────────────────────────────┤
│ - etl_manager: IETLManager                               │
│ - quality_checker: IDataQualityChecker                   │
│ - vectorizer: IVectorizer                                │
│ - partition_manager: IPartitionManager                   │
│ - repository: IDataHubRepository                         │
├──────────────────────────────────────────────────────────┤
│ + run_etl_job(job_id: str) → ETLExecution                │
│ + check_quality(table: str) → QualityReport              │
│ + vectorize_documents(doc_ids: list) → void              │
│ + refresh_views() → void                                 │
└──────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│IETLManager   │  │IVectorizer   │  │IPartition    │
│              │  │              │  │Manager       │
└──────────────┘  └──────────────┘  └──────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ETLPipeline   │  │OpenAI        │  │PostgreSQL    │
│(RAW→DIM→FACT)│  │Embeddings    │  │Partition     │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 1.3 주요 컴포넌트

#### 1.3.1 ETLManager

**책임**: ETL 작업 실행 및 관리

```python
from dataclasses import dataclass
from enum import Enum

class ETLStage(Enum):
    RAW = "RAW"
    DIM = "DIM"
    FACT = "FACT"
    PRE_AGG = "PRE_AGG"

@dataclass
class ETLJob:
    job_id: str
    name: str
    source_connector_id: str
    target_table: str
    schedule: str  # cron 표현식
    stages: List[ETLStage]
    transform_script: str

class ETLManager(IETLManager):
    async def run_etl_job(self, job_id: str) -> ETLExecution:
        """ETL 작업 실행"""
        # 1. ETL Job 조회
        job = await self.repository.get_etl_job(job_id)

        # 2. Execution 레코드 생성
        execution = await self.repository.create_execution(
            job_id=job_id,
            status='running'
        )

        try:
            # 3. 단계별 실행
            for stage in job.stages:
                if stage == ETLStage.RAW:
                    await self._execute_raw_stage(job, execution)
                elif stage == ETLStage.DIM:
                    await self._execute_dim_stage(job, execution)
                elif stage == ETLStage.FACT:
                    await self._execute_fact_stage(job, execution)
                elif stage == ETLStage.PRE_AGG:
                    await self._execute_pre_agg_stage(job, execution)

            # 4. 완료
            await self.repository.update_execution(
                execution.id,
                status='completed'
            )

            # 5. 이벤트 발행 (캐시 무효화)
            await self._publish_event('etl.completed', {
                'job_id': job_id,
                'target_table': job.target_table
            })

        except Exception as e:
            # 에러 처리
            await self.repository.update_execution(
                execution.id,
                status='failed',
                error_message=str(e)
            )
            raise

        return execution

    async def _execute_raw_stage(self, job: ETLJob, execution: ETLExecution):
        """RAW 단계: 외부 데이터 수집"""
        # 1. 커넥터 조회
        connector = await self.repository.get_connector(job.source_connector_id)

        # 2. 데이터 추출
        if connector.type == 'postgresql':
            data = await self._extract_from_postgres(connector, job.source_query)
        elif connector.type == 'rest_api':
            data = await self._extract_from_rest_api(connector, job.api_endpoint)
        elif connector.type == 'mqtt':
            data = await self._extract_from_mqtt(connector, job.topic)

        # 3. RAW 테이블 적재
        await self._load_to_raw_table(job.target_table, data)

        # 4. 통계 기록
        await self.repository.update_execution_stats(
            execution.id,
            stage='RAW',
            rows_extracted=len(data)
        )

    async def _execute_fact_stage(self, job: ETLJob, execution: ETLExecution):
        """FACT 단계: 집계 및 적재"""
        # 1. Transform 스크립트 실행 (SQL)
        transform_sql = job.transform_script

        # 예시 Transform SQL
        # INSERT INTO fact_daily_production (tenant_id, date, line_code, ...)
        # SELECT
        #   tenant_id,
        #   DATE(timestamp) AS date,
        #   line_code,
        #   SUM(production_count) AS production_count,
        #   SUM(defect_count) AS defect_count
        # FROM raw_mes_production
        # WHERE DATE(timestamp) = CURRENT_DATE - INTERVAL '1 day'
        # GROUP BY tenant_id, DATE(timestamp), line_code

        # 2. SQL 실행
        result = await self.db_session.execute(text(transform_sql))
        rows_inserted = result.rowcount

        # 3. 통계 기록
        await self.repository.update_execution_stats(
            execution.id,
            stage='FACT',
            rows_inserted=rows_inserted
        )
```

#### 1.3.2 OpenAIVectorizer

**책임**: 문서 벡터 임베딩 생성

```python
from openai import OpenAI
import numpy as np

class OpenAIVectorizer(IVectorizer):
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
        self.model = "text-embedding-3-small"
        self.dimension = 1536

    async def vectorize_documents(self, doc_ids: List[str], batch_size: int = 100):
        """문서 벡터화 (배치 처리)"""
        # 1. 문서 조회
        documents = await self.repository.get_documents(doc_ids)

        # 2. 배치별 임베딩 생성
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]
            texts = [doc['text'] for doc in batch]

            # OpenAI Embeddings API 호출
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
                encoding_format="float"
            )

            # 3. 임베딩 저장
            for doc, embedding_data in zip(batch, response.data):
                embedding = embedding_data.embedding

                await self.repository.save_embedding(
                    doc_id=doc['id'],
                    embedding=embedding,
                    model=self.model
                )

    async def search_similar(
        self,
        query_text: str,
        tenant_id: str,
        limit: int = 5
    ) -> List[Dict]:
        """유사 문서 검색"""
        # 1. 쿼리 벡터화
        response = self.client.embeddings.create(
            model=self.model,
            input=query_text
        )
        query_embedding = response.data[0].embedding

        # 2. pgvector 유사도 검색
        results = await self.repository.search_by_vector(
            tenant_id=tenant_id,
            query_embedding=query_embedding,
            limit=limit
        )

        return results
```

---

## 3. Chat Service 상세 설계

### 3.1 서비스 개요
Chat Service는 사용자 메시지를 수집하고, Intent를 분류하며, 세션을 관리하고, 응답을 구성하는 챗봇 엔진이다.

**책임**:
- 메시지 수집 및 저장
- 세션 관리
- Intent Router 호출
- 응답 구성 (텍스트, 카드, 버튼)
- 컨텍스트 유지 (Multi-turn dialog)

### 3.2 클래스 다이어그램

```
┌──────────────────────────────────────────────────────────┐
│                      ChatService                         │
├──────────────────────────────────────────────────────────┤
│ - session_manager: ISessionManager                       │
│ - intent_router: IIntentRouter                           │
│ - response_builder: IResponseBuilder                     │
│ - repository: IChatRepository                            │
├──────────────────────────────────────────────────────────┤
│ + process_message(session_id: str, message: str) → Response│
│ + get_session(session_id: str) → ChatSession             │
└──────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ISession      │  │IIntent       │  │IResponse     │
│Manager       │  │Router        │  │Builder       │
└──────────────┘  └──────────────┘  └──────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│RedisSession  │  │LLMIntent     │  │SlackBlock    │
│Manager       │  │Router        │  │Builder       │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 3.3 주요 컴포넌트

#### 3.3.1 ChatService (Main Orchestrator)

```python
from typing import Optional

@dataclass
class ChatMessage:
    session_id: str
    user_id: str
    message: str
    timestamp: datetime

@dataclass
class ChatResponse:
    session_id: str
    response_text: str
    response_blocks: Optional[list]  # Slack Block Kit
    intent: str
    slots: dict
    confidence: float

class ChatService:
    def __init__(
        self,
        session_manager: ISessionManager,
        intent_router: IIntentRouter,
        response_builder: IResponseBuilder,
        repository: IChatRepository
    ):
        self.session_manager = session_manager
        self.intent_router = intent_router
        self.response_builder = response_builder
        self.repository = repository

    async def process_message(
        self,
        session_id: str,
        user_id: str,
        message: str
    ) -> ChatResponse:
        """메시지 처리"""
        # 1. 세션 조회 또는 생성
        session = await self.session_manager.get_or_create(session_id, user_id)

        # 2. 메시지 저장
        await self.repository.save_message(
            session_id=session_id,
            user_id=user_id,
            message=message,
            direction='incoming'
        )

        # 3. Intent 분류 (컨텍스트 포함)
        intent_result = await self.intent_router.classify(
            message=message,
            context=session.context
        )

        # 4. Slot 추출
        slots = await self.intent_router.extract_slots(
            message=message,
            intent=intent_result.intent,
            context=session.context
        )

        # 5. 컨텍스트 업데이트
        await self.session_manager.update_context(
            session_id=session_id,
            intent=intent_result.intent,
            slots=slots
        )

        # 6. 응답 생성
        if slots.get('all_slots_filled'):
            # 모든 Slot 채워짐 → 액션 실행 (Workflow 등)
            response = await self._execute_action(intent_result.intent, slots)
        else:
            # Slot 누락 → 되묻기
            response = await self._generate_clarification(intent_result.intent, slots)

        # 7. 응답 저장
        await self.repository.save_message(
            session_id=session_id,
            user_id='system',
            message=response.response_text,
            direction='outgoing'
        )

        return response

    async def _execute_action(self, intent: str, slots: dict) -> ChatResponse:
        """Intent 기반 액션 실행"""
        if intent == 'production_inquiry':
            # Workflow 실행 또는 BI 쿼리
            result = await self._query_production_data(slots)
            return ChatResponse(
                response_text=f"LINE {slots['line_code']}의 생산량은 {result['production_count']}개입니다.",
                intent=intent,
                slots=slots,
                confidence=0.9
            )

        elif intent == 'workflow_execution':
            # Workflow 실행
            instance = await self._execute_workflow(slots['workflow_id'], slots)
            return ChatResponse(
                response_text=f"워크플로우 {slots['workflow_id']}를 실행했습니다. (Instance: {instance.id})",
                intent=intent,
                slots=slots,
                confidence=0.9
            )

    async def _generate_clarification(self, intent: str, slots: dict) -> ChatResponse:
        """되묻기 생성"""
        missing_slots = slots.get('missing_required_slots', [])

        if 'line_code' in missing_slots:
            response_text = "어떤 라인의 생산량을 조회할까요? (예: LINE-A, LINE-B, LINE-C)"
        elif 'date_range' in missing_slots:
            response_text = "조회 기간을 알려주세요 (예: 어제, 지난주, 11월 20일)"
        else:
            response_text = f"필요한 정보가 부족합니다: {', '.join(missing_slots)}"

        return ChatResponse(
            response_text=response_text,
            intent=intent,
            slots=slots,
            confidence=0.7
        )
```

#### 3.3.2 LLMIntentRouter

**책임**: LLM 기반 Intent 분류 및 Slot 추출

```python
from openai import OpenAI

class LLMIntentRouter(IIntentRouter):
    def __init__(self, openai_client: OpenAI, intent_repository: IIntentRepository):
        self.client = openai_client
        self.intent_repository = intent_repository

    async def classify(self, message: str, context: dict) -> IntentResult:
        """Intent 분류"""
        # 1. Intent 정의 조회
        intents = await self.intent_repository.get_all_intents()

        # 2. 프롬프트 구성
        system_prompt = self._build_intent_prompt(intents)
        user_prompt = f"User: {message}"

        # 3. LLM 호출
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",  # 저비용
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        # 4. 응답 파싱
        result = json.loads(response.choices[0].message.content)

        return IntentResult(
            intent=result['intent'],
            confidence=result['confidence'],
            reasoning=result.get('reasoning', '')
        )

    async def extract_slots(
        self,
        message: str,
        intent: str,
        context: dict
    ) -> Dict[str, Any]:
        """Slot 추출"""
        # 1. Intent 정의 조회 (required_slots)
        intent_def = await self.intent_repository.get_intent(intent)

        # 2. 프롬프트 구성
        system_prompt = f"""
Extract the following slots from user message:

Required Slots:
{self._format_slots(intent_def.required_slots)}

Optional Slots:
{self._format_slots(intent_def.optional_slots)}

Respond in JSON:
{{
  "slots": {{"line_code": "LINE-A", "date_range": "yesterday"}},
  "missing_required_slots": []
}}
"""

        user_prompt = f"User: {message}"

        # 3. LLM 호출
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        # 4. 응답 파싱
        result = json.loads(response.choices[0].message.content)

        # 5. 날짜 정규화
        result['slots'] = self._normalize_slots(result['slots'])

        # 6. all_slots_filled 플래그
        result['all_slots_filled'] = len(result['missing_required_slots']) == 0

        return result

    def _normalize_slots(self, slots: dict) -> dict:
        """Slot 정규화 (상대 날짜 → 절대 날짜)"""
        if 'date_range' in slots:
            date_value = slots['date_range']

            if date_value == 'yesterday':
                slots['date_range'] = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            elif date_value == 'last_week':
                end_date = datetime.now() - timedelta(days=1)
                start_date = end_date - timedelta(days=7)
                slots['date_range'] = {
                    'start': start_date.strftime('%Y-%m-%d'),
                    'end': end_date.strftime('%Y-%m-%d')
                }

        return slots
```

#### 3.3.3 SlackBlockBuilder

**책임**: Slack Block Kit 응답 생성

```python
class SlackBlockBuilder(IResponseBuilder):
    def build_judgment_response(self, judgment: JudgmentResult) -> dict:
        """Judgment 결과 → Slack Blocks"""
        severity_emoji = {
            'critical': '🚨',
            'warning': '⚠️',
            'info': 'ℹ️'
        }

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji.get(judgment.result['severity'], '')} {judgment.result['status']}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence:*\n{judgment.confidence:.2f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Method:*\n{judgment.method_used}"
                    }
                ]
            }
        ]

        # Explanation 추가
        if judgment.explanation:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Explanation:*\n{judgment.explanation['summary']}"
                }
            })

        # Recommended Actions 추가
        if judgment.result.get('recommended_actions'):
            actions_text = '\n'.join([
                f"• {action}" for action in judgment.result['recommended_actions']
            ])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recommended Actions:*\n{actions_text}"
                }
            })

        # 피드백 버튼
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "👍 Helpful"},
                    "value": f"feedback_up:{judgment.execution_id}",
                    "action_id": "feedback_up"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "👎 Not Helpful"},
                    "value": f"feedback_down:{judgment.execution_id}",
                    "action_id": "feedback_down"
                }
            ]
        })

        return {"blocks": blocks}
```

### 3.4 시퀀스 다이어그램: Chat 메시지 처리

```
Slack       ChatService   SessionMgr   IntentRouter   WorkflowService   SlackBlockBuilder
  │             │            │               │                │                │
  │ message     │            │               │                │                │
  ├────────────>│            │               │                │                │
  │             │            │               │                │                │
  │             │ get_or_create_session()    │                │                │
  │             ├───────────>│               │                │                │
  │             │<───────────┤               │                │                │
  │             │ (session)  │               │                │                │
  │             │            │               │                │                │
  │             │ classify()                 │                │                │
  │             ├────────────────────────────>                │                │
  │             │<────────────────────────────                │                │
  │             │ (intent, slots)            │                │                │
  │             │            │               │                │                │
  │             │ execute_workflow()         │                │                │
  │             ├────────────────────────────────────────────>│                │
  │             │<────────────────────────────────────────────┤                │
  │             │ (workflow_result)          │                │                │
  │             │            │               │                │                │
  │             │ build_response()           │                │                │
  │             ├────────────────────────────────────────────────────────────>│
  │             │<────────────────────────────────────────────────────────────┤
  │             │ (slack_blocks)             │                │                │
  │             │            │               │                │                │
  │<────────────┤            │               │                │                │
  │ (response)  │            │               │                │                │
  │             │            │               │                │                │
```

---

## 결론

본 문서(B-2)는 **제조업 AI 플랫폼 (AI Factory Decision Engine)** 의 모듈/서비스 상세 설계를 포괄적으로 명세하였다.

### 문서 구성 요약
- **B-2-1**: Judgment Service, Workflow Service 상세 설계
- **B-2-2**: BI Service, Learning Service 상세 설계
- **B-2-3**: MCP ToolHub, Data Hub, Chat Service 상세 설계

### 주요 성과
1. **7개 서비스 상세 설계**: 클래스 다이어그램, 시퀀스 다이어그램, 인터페이스 정의
2. **핵심 알고리즘 구현**: Hybrid Aggregation, Rule 자동 추출, Canary 배포, Drift 감지
3. **에러 처리 전략**: Retry with Backoff, Circuit Breaker, Fallback
4. **성능 최적화**: Connection Pool, Cache Hierarchy, Batch Processing

### 다음 단계
1. 프로토타입 개발 (핵심 서비스)
2. 단위 테스트 작성 (커버리지 > 80%)
3. 통합 테스트 (서비스 간 연동)
4. 성능 테스트 (부하 테스트, 벤치마크)

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 (B-2-1~B-2-3 통합) |

---

**문서 끝**
