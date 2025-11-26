# B-2-1. Module/Service Design - Judgment & Workflow Services

## 문서 정보
- **문서 ID**: B-2-1
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **관련 문서**:
  - A-2 System Requirements Spec
  - B-1 System Architecture
  - B-3 Data/DB Schema
  - B-4 API Interface Spec
  - B-5 Workflow/State Machine Spec
  - B-6 AI/Agent/Prompt Spec

## 목차
1. [Judgment Service 상세 설계](#1-judgment-service-상세-설계)
2. [Workflow Service 상세 설계](#2-workflow-service-상세-설계)

---

## 1. Judgment Service 상세 설계

### 1.1 서비스 개요
Judgment Service는 입력 데이터를 받아 Rule과 LLM을 조합하여 판단 결과를 반환하는 핵심 엔진이다.

**책임**:
- 입력 검증
- Rule 실행 (Rhai)
- LLM 호출 (OpenAI/Anthropic)
- Hybrid 결합 (가중 평균, Gate 조건)
- 캐시 관리
- Explanation 생성
- 시뮬레이션 (Replay)

### 1.2 클래스 다이어그램

```
┌──────────────────────────────────────────────────────────┐
│                   JudgmentService                        │
├──────────────────────────────────────────────────────────┤
│ - validator: IInputValidator                             │
│ - rule_engine: IRuleEngine                               │
│ - llm_client: ILLMClient                                 │
│ - aggregator: IResultAggregator                          │
│ - cache_manager: ICacheManager                           │
│ - repository: IJudgmentRepository                        │
├──────────────────────────────────────────────────────────┤
│ + execute(input: JudgmentRequest) → JudgmentResult      │
│ + simulate(execution_id: str) → SimulationResult        │
│ - should_call_llm(rule_result: RuleResult) → bool       │
│ - calculate_final_result(...) → JudgmentResult          │
└──────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│IInputValidator│  │IRuleEngine   │  │ILLMClient    │
└──────────────┘  └──────────────┘  └──────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│JSONSchema    │  │RhaiEngine    │  │OpenAIClient  │
│Validator     │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 1.3 주요 컴포넌트

#### 1.3.1 JudgmentService (Main Orchestrator)

**책임**: 판단 실행 오케스트레이션

```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class JudgmentRequest:
    workflow_id: str
    input_data: dict
    policy: str = "HYBRID_WEIGHTED"
    need_explanation: bool = False
    context: Optional[dict] = None

@dataclass
class JudgmentResult:
    execution_id: str
    result: dict
    confidence: float
    method_used: str
    explanation: Optional[dict] = None
    execution_time_ms: int

class JudgmentService:
    def __init__(
        self,
        validator: IInputValidator,
        rule_engine: IRuleEngine,
        llm_client: ILLMClient,
        aggregator: IResultAggregator,
        cache_manager: ICacheManager,
        repository: IJudgmentRepository
    ):
        self.validator = validator
        self.rule_engine = rule_engine
        self.llm_client = llm_client
        self.aggregator = aggregator
        self.cache_manager = cache_manager
        self.repository = repository

    async def execute(self, request: JudgmentRequest) -> JudgmentResult:
        """판단 실행 메인 로직"""
        start_time = time.time()

        # 1. 입력 검증
        self.validator.validate(request.workflow_id, request.input_data)

        # 2. 캐시 조회
        cache_key = self._get_cache_key(request.workflow_id, request.input_data)
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            cached_result['from_cache'] = True
            return cached_result

        # 3. Rule 실행
        rule_result = await self.rule_engine.execute(
            workflow_id=request.workflow_id,
            input_data=request.input_data
        )

        # 4. LLM 호출 결정
        llm_result = None
        if self._should_call_llm(request.policy, rule_result):
            llm_result = await self.llm_client.call(
                workflow_id=request.workflow_id,
                input_data=request.input_data,
                rule_result=rule_result
            )

        # 5. Hybrid 결합
        final_result = self.aggregator.combine(
            rule_result=rule_result,
            llm_result=llm_result,
            policy=request.policy
        )

        # 6. Explanation 생성 (선택적)
        if request.need_explanation:
            final_result.explanation = self._generate_explanation(
                rule_result, llm_result, final_result
            )

        # 7. 저장
        execution = await self.repository.save(
            workflow_id=request.workflow_id,
            input_data=request.input_data,
            rule_result=rule_result,
            llm_result=llm_result,
            final_result=final_result
        )

        # 8. 캐시 저장
        execution_time_ms = int((time.time() - start_time) * 1000)
        result = JudgmentResult(
            execution_id=execution.id,
            result=final_result,
            confidence=final_result['confidence'],
            method_used=self._get_method_used(request.policy, rule_result, llm_result),
            execution_time_ms=execution_time_ms
        )

        await self.cache_manager.set(cache_key, result, ttl=300)

        # 9. 이벤트 발행
        await self._publish_event('judgment.executed', {
            'execution_id': execution.id,
            'workflow_id': request.workflow_id,
            'result': result
        })

        return result

    def _should_call_llm(self, policy: str, rule_result: dict) -> bool:
        """LLM 호출 여부 결정"""
        if policy == "RULE_ONLY":
            return False
        elif policy == "LLM_ONLY":
            return True
        elif policy == "RULE_FALLBACK":
            return rule_result['confidence'] < 0.7
        elif policy == "HYBRID_WEIGHTED":
            return True
        else:
            return False

    def _get_cache_key(self, workflow_id: str, input_data: dict) -> str:
        """캐시 키 생성"""
        import hashlib
        import json
        input_hash = hashlib.sha256(
            json.dumps(input_data, sort_keys=True).encode()
        ).hexdigest()
        return f"judgment:cache:{workflow_id}:{input_hash}"
```

#### 1.3.2 RhaiEngine (Rule Engine)

**책임**: Rhai 스크립트 실행, 신뢰도 계산

```python
from rhai import Engine
from typing import Dict, Any

class RhaiEngine(IRuleEngine):
    def __init__(self, repository: IRuleRepository):
        self.repository = repository
        self.engine_pool = {}  # workflow별 엔진 캐시

    async def execute(self, workflow_id: str, input_data: dict) -> Dict[str, Any]:
        """Rule 실행"""
        # 1. Ruleset 조회 (활성 버전)
        ruleset = await self.repository.get_active_ruleset(workflow_id)
        if not ruleset:
            raise ValueError(f"No active ruleset for workflow {workflow_id}")

        # 2. Rhai 엔진 생성 또는 캐시에서 조회
        engine = self._get_or_create_engine(ruleset.id)

        # 3. 입력 데이터 주입
        engine.set_global("input", input_data)

        # 4. 스크립트 실행
        try:
            result = engine.eval(ruleset.script_content)
        except Exception as e:
            raise RuleExecutionError(f"Rule execution failed: {str(e)}")

        # 5. 신뢰도 계산 (Rule 자체 신뢰도 또는 기본값)
        confidence = result.get('confidence', 0.8)

        # 6. 결과 반환
        return {
            'result': result,
            'confidence': confidence,
            'matched_rules': result.get('matched_rules', []),
            'ruleset_version': ruleset.version
        }

    def _get_or_create_engine(self, ruleset_id: str) -> Engine:
        """Rhai 엔진 캐시 (성능 최적화)"""
        if ruleset_id not in self.engine_pool:
            self.engine_pool[ruleset_id] = Engine()
        return self.engine_pool[ruleset_id]
```

#### 1.3.3 OpenAIClient (LLM Client)

**책임**: LLM API 호출, 응답 파싱, 재시도

```python
from openai import OpenAI
import json
from typing import Dict, Any

class OpenAIClient(ILLMClient):
    def __init__(self, api_key: str, prompt_repository: IPromptRepository):
        self.client = OpenAI(api_key=api_key)
        self.prompt_repository = prompt_repository

    async def call(
        self,
        workflow_id: str,
        input_data: dict,
        rule_result: Optional[dict] = None
    ) -> Dict[str, Any]:
        """LLM 호출"""
        # 1. Prompt 템플릿 조회
        prompt_template = await self.prompt_repository.get_active_template(workflow_id)

        # 2. Prompt 렌더링
        system_prompt = prompt_template.system_prompt
        user_prompt = self._render_prompt(
            template=prompt_template.user_prompt,
            input_data=input_data,
            rule_result=rule_result
        )

        # 3. LLM 호출 (재시도 3회)
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=prompt_template.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500,
                    response_format={"type": "json_object"}
                )

                # 4. 응답 파싱
                result = json.loads(response.choices[0].message.content)

                # 5. 스키마 검증
                self._validate_response(result, prompt_template.output_schema)

                # 6. 로그 저장
                await self._save_llm_call_log(
                    workflow_id=workflow_id,
                    model=prompt_template.model,
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    response=result
                )

                return result

            except json.JSONDecodeError as e:
                if attempt < 2:
                    continue  # 재시도
                else:
                    raise LLMParsingError(f"Failed to parse LLM response: {str(e)}")

            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # 지수 백오프
                    continue
                else:
                    raise LLMCallError(f"LLM call failed: {str(e)}")

    def _render_prompt(self, template: str, input_data: dict, rule_result: Optional[dict]) -> str:
        """프롬프트 템플릿 렌더링 (Jinja2)"""
        from jinja2 import Template
        t = Template(template)
        return t.render(input=input_data, rule_result=rule_result)
```

### 1.4 시퀀스 다이어그램: Judgment 실행

```
Client          JudgmentService   CacheManager   RuleEngine   LLMClient   Repository
  │                  │                  │              │            │           │
  │ execute(request) │                  │              │            │           │
  ├─────────────────>│                  │              │            │           │
  │                  │                  │              │            │           │
  │                  │ validate()       │              │            │           │
  │                  │─────────────────────────────────┐            │           │
  │                  │                  │              │            │           │
  │                  │ get_cache()      │              │            │           │
  │                  ├─────────────────>│              │            │           │
  │                  │<─────────────────┤              │            │           │
  │                  │ (Cache MISS)     │              │            │           │
  │                  │                  │              │            │           │
  │                  │ execute_rule()   │              │            │           │
  │                  ├─────────────────────────────────>            │           │
  │                  │<─────────────────────────────────            │           │
  │                  │ (rule_result)    │              │            │           │
  │                  │                  │              │            │           │
  │                  │ should_call_llm()│              │            │           │
  │                  │─────────────────────────────────┐            │           │
  │                  │ (confidence < 0.7 → true)       │            │           │
  │                  │                  │              │            │           │
  │                  │ call_llm()       │              │            │           │
  │                  ├──────────────────────────────────────────────>           │
  │                  │<──────────────────────────────────────────────           │
  │                  │ (llm_result)     │              │            │           │
  │                  │                  │              │            │           │
  │                  │ combine()        │              │            │           │
  │                  │─────────────────────────────────┐            │           │
  │                  │ (final_result)   │              │            │           │
  │                  │                  │              │            │           │
  │                  │ save()           │              │            │           │
  │                  ├────────────────────────────────────────────────────────>│
  │                  │<────────────────────────────────────────────────────────┤
  │                  │                  │              │            │           │
  │                  │ set_cache()      │              │            │           │
  │                  ├─────────────────>│              │            │           │
  │                  │                  │              │            │           │
  │<─────────────────┤                  │              │            │           │
  │ (JudgmentResult) │                  │              │            │           │
  │                  │                  │              │            │           │
```

### 1.5 인터페이스 정의

#### 1.5.1 IRuleEngine

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class IRuleEngine(ABC):
    @abstractmethod
    async def execute(self, workflow_id: str, input_data: dict) -> Dict[str, Any]:
        """
        Rule 실행

        Args:
            workflow_id: Workflow ID
            input_data: 입력 데이터

        Returns:
            {
                'result': {...},
                'confidence': 0.0~1.0,
                'matched_rules': [...],
                'ruleset_version': 'v1.3.0'
            }

        Raises:
            RuleExecutionError: Rule 실행 실패
        """
        pass
```

#### 1.5.2 ILLMClient

```python
class ILLMClient(ABC):
    @abstractmethod
    async def call(
        self,
        workflow_id: str,
        input_data: dict,
        rule_result: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        LLM 호출

        Args:
            workflow_id: Workflow ID
            input_data: 입력 데이터
            rule_result: Rule 실행 결과 (선택적)

        Returns:
            {
                'result': {...},
                'confidence': 0.0~1.0,
                'explanation': '...',
                'model': 'gpt-4'
            }

        Raises:
            LLMCallError: LLM 호출 실패
            LLMParsingError: JSON 파싱 실패
        """
        pass
```

#### 1.5.3 IResultAggregator

```python
class IResultAggregator(ABC):
    @abstractmethod
    def combine(
        self,
        rule_result: dict,
        llm_result: Optional[dict],
        policy: str
    ) -> dict:
        """
        Rule + LLM 결과 병합

        Args:
            rule_result: Rule 실행 결과
            llm_result: LLM 호출 결과 (None 가능)
            policy: HYBRID_WEIGHTED | HYBRID_GATE

        Returns:
            {
                'status': '...',
                'severity': '...',
                'confidence': 0.0~1.0,
                'recommended_actions': [...],
                'components': {
                    'rule_confidence': 0.0~1.0,
                    'llm_confidence': 0.0~1.0
                }
            }
        """
        pass
```

### 1.6 알고리즘: Hybrid Aggregation

#### 1.6.1 HYBRID_WEIGHTED (가중 평균)

```python
class HybridWeightedAggregator(IResultAggregator):
    def combine(self, rule_result: dict, llm_result: Optional[dict], policy: str) -> dict:
        if llm_result is None:
            return rule_result['result']

        rule_conf = rule_result['confidence']
        llm_conf = llm_result['confidence']

        # 가중치 (설정 가능)
        rule_weight = 0.6
        llm_weight = 0.4

        # 가중 평균
        final_confidence = rule_conf * rule_weight + llm_conf * llm_weight

        # Status 선택 (높은 신뢰도 우선)
        if rule_conf > llm_conf:
            final_status = rule_result['result']['status']
        else:
            final_status = llm_result['result']['status']

        # Recommended Actions 합집합
        rule_actions = rule_result['result'].get('recommended_actions', [])
        llm_actions = llm_result['result'].get('recommended_actions', [])
        final_actions = list(set(rule_actions + llm_actions))

        return {
            'status': final_status,
            'severity': self._merge_severity(rule_result, llm_result),
            'confidence': final_confidence,
            'recommended_actions': final_actions,
            'components': {
                'rule_confidence': rule_conf,
                'llm_confidence': llm_conf,
                'rule_weight': rule_weight,
                'llm_weight': llm_weight
            }
        }

    def _merge_severity(self, rule_result: dict, llm_result: dict) -> str:
        """Severity 병합 (더 높은 심각도 우선)"""
        severity_order = {'info': 0, 'warning': 1, 'critical': 2}
        rule_severity = rule_result['result'].get('severity', 'info')
        llm_severity = llm_result['result'].get('severity', 'info')

        if severity_order[rule_severity] > severity_order[llm_severity]:
            return rule_severity
        else:
            return llm_severity
```

---

## 2. Workflow Service 상세 설계

### 2.1 서비스 개요
Workflow Service는 DSL로 정의된 다단계 워크플로우를 실행하는 엔진이다.

**책임**:
- DSL 파싱 및 검증
- Workflow 인스턴스 생성
- 노드 실행 (12가지 타입)
- 상태 관리 (PENDING, RUNNING, WAITING, COMPLETED, FAILED)
- 흐름 제어 (SWITCH, PARALLEL, WAIT)
- Circuit Breaker
- 보상 트랜잭션

### 2.2 클래스 다이어그램

```
┌──────────────────────────────────────────────────────────────┐
│                    WorkflowService                           │
├──────────────────────────────────────────────────────────────┤
│ - parser: IDSLParser                                         │
│ - validator: IDSLValidator                                   │
│ - executor: IWorkflowExecutor                                │
│ - state_manager: IStateManager                               │
│ - repository: IWorkflowRepository                            │
├──────────────────────────────────────────────────────────────┤
│ + create_workflow(dsl: dict) → Workflow                      │
│ + validate_dsl(dsl: dict) → ValidationResult                 │
│ + execute_workflow(workflow_id: str, input: dict) → Instance │
│ + get_instance(instance_id: str) → WorkflowInstance          │
└──────────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│IDSLParser    │  │IWorkflow     │  │IStateManager │
│              │  │Executor      │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
         │                │
         ▼                ▼
┌──────────────┐  ┌──────────────────────────────────┐
│DSLParser     │  │  Node Executors (Strategy)       │
│              │  │  - DataNodeExecutor              │
│              │  │  - JudgmentNodeExecutor          │
│              │  │  - MCPNodeExecutor               │
│              │  │  - ActionNodeExecutor            │
│              │  │  - SwitchNodeExecutor            │
│              │  │  - ParallelNodeExecutor          │
└──────────────┘  └──────────────────────────────────┘
```

### 2.3 주요 컴포넌트

#### 2.3.1 WorkflowExecutor (Main Orchestrator)

```python
from typing import List, Dict, Any
from enum import Enum

class WorkflowStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class WorkflowExecutor(IWorkflowExecutor):
    def __init__(
        self,
        state_manager: IStateManager,
        node_executors: Dict[str, INodeExecutor],
        repository: IWorkflowRepository
    ):
        self.state_manager = state_manager
        self.node_executors = node_executors
        self.repository = repository

    async def execute(
        self,
        workflow_id: str,
        input_data: dict
    ) -> WorkflowInstance:
        """워크플로우 실행"""
        # 1. Workflow DSL 조회
        workflow = await self.repository.get_workflow(workflow_id)

        # 2. 인스턴스 생성
        instance = await self.repository.create_instance(
            workflow_id=workflow_id,
            input_data=input_data,
            status=WorkflowStatus.PENDING
        )

        # 3. 상태 → RUNNING
        await self.state_manager.update_status(instance.id, WorkflowStatus.RUNNING)

        # 4. 시작 노드 찾기
        start_node = self._find_start_node(workflow.nodes)

        # 5. 노드 실행 (재귀 또는 루프)
        try:
            await self._execute_node(instance, start_node, workflow)
            await self.state_manager.update_status(instance.id, WorkflowStatus.COMPLETED)
        except Exception as e:
            await self.state_manager.update_status(instance.id, WorkflowStatus.FAILED)
            await self.state_manager.set_error(instance.id, str(e))
            raise

        return instance

    async def _execute_node(
        self,
        instance: WorkflowInstance,
        node: Node,
        workflow: Workflow
    ) -> Any:
        """단일 노드 실행"""
        # 1. 노드별 Executor 선택
        node_executor = self.node_executors[node.type]

        # 2. 노드 실행
        result = await node_executor.execute(
            instance=instance,
            node=node,
            context=instance.context
        )

        # 3. 컨텍스트 업데이트
        await self.state_manager.update_context(
            instance.id,
            node.id,
            result
        )

        # 4. 다음 노드 찾기
        next_nodes = self._get_next_nodes(workflow, node, result)

        # 5. 다음 노드 실행 (재귀)
        for next_node in next_nodes:
            await self._execute_node(instance, next_node, workflow)

        return result

    def _get_next_nodes(self, workflow: Workflow, current_node: Node, result: Any) -> List[Node]:
        """다음 노드 결정 (Edge 기반)"""
        edges = [e for e in workflow.edges if e.source == current_node.id]

        next_nodes = []
        for edge in edges:
            # 조건 평가 (있으면)
            if edge.condition:
                if self._evaluate_condition(edge.condition, result):
                    next_node = workflow.get_node(edge.target)
                    next_nodes.append(next_node)
            else:
                # 조건 없으면 무조건 실행
                next_node = workflow.get_node(edge.target)
                next_nodes.append(next_node)

        return next_nodes
```

#### 2.3.2 DataNodeExecutor

**책임**: DATA 노드 실행 (DB 쿼리)

```python
class DataNodeExecutor(INodeExecutor):
    def __init__(self, db_session: Session):
        self.db_session = db_session

    async def execute(self, instance: WorkflowInstance, node: Node, context: dict) -> Any:
        """DATA 노드 실행"""
        config = node.config

        # 1. 템플릿 변수 치환
        table = config['table']
        columns = config.get('columns', ['*'])
        filters = self._render_filters(config.get('filters', {}), context)

        # 2. SQL 생성
        sql = self._build_sql(table, columns, filters)

        # 3. SQL 실행 (Prepared Statement)
        result = await self.db_session.execute(sql, filters)
        rows = result.fetchall()

        # 4. 결과 반환
        return {
            'table': table,
            'rows': [dict(row) for row in rows],
            'row_count': len(rows)
        }

    def _build_sql(self, table: str, columns: List[str], filters: dict) -> str:
        """SQL 쿼리 생성 (SQL Injection 방지)"""
        from sqlalchemy import text

        columns_str = ', '.join(columns)
        where_clauses = []
        params = {}

        for field, value in filters.items():
            where_clauses.append(f"{field} = :{field}")
            params[field] = value

        where_str = ' AND '.join(where_clauses) if where_clauses else '1=1'

        sql = f"SELECT {columns_str} FROM {table} WHERE {where_str}"
        return text(sql).bindparams(**params)

    def _render_filters(self, filters: dict, context: dict) -> dict:
        """필터 템플릿 변수 치환"""
        from jinja2 import Template

        rendered = {}
        for key, value in filters.items():
            if isinstance(value, str) and '{{' in value:
                t = Template(value)
                rendered[key] = t.render(input=context['input'], nodes=context['nodes'])
            else:
                rendered[key] = value

        return rendered
```

#### 2.3.3 JudgmentNodeExecutor

**책임**: JUDGMENT 노드 실행 (Judgment Service 호출)

```python
import httpx

class JudgmentNodeExecutor(INodeExecutor):
    def __init__(self, judgment_service_url: str):
        self.judgment_service_url = judgment_service_url
        self.client = httpx.AsyncClient(timeout=10.0)

    async def execute(self, instance: WorkflowInstance, node: Node, context: dict) -> Any:
        """JUDGMENT 노드 실행"""
        config = node.config

        # 1. 입력 매핑
        input_data = self._map_input(config.get('input_mapping', {}), context)

        # 2. Judgment Service 호출
        try:
            response = await self.client.post(
                f"{self.judgment_service_url}/api/v1/judgment/execute",
                json={
                    'workflow_id': config['judgment_workflow_id'],
                    'input_data': input_data,
                    'policy': config.get('policy', 'HYBRID_WEIGHTED'),
                    'need_explanation': config.get('need_explanation', True)
                },
                headers={'Authorization': f'Bearer {get_internal_token()}'}
            )
            response.raise_for_status()
            judgment_result = response.json()

        except httpx.TimeoutException:
            raise NodeExecutionError(f"Judgment service timeout (> 10s)")
        except httpx.HTTPStatusError as e:
            raise NodeExecutionError(f"Judgment service error: {e.response.status_code}")

        # 3. 결과 반환
        return judgment_result

    def _map_input(self, input_mapping: dict, context: dict) -> dict:
        """입력 매핑 (템플릿 변수 치환)"""
        from jinja2 import Template

        mapped = {}
        for key, template in input_mapping.items():
            if isinstance(template, str) and '{{' in template:
                t = Template(template)
                mapped[key] = t.render(input=context['input'], nodes=context['nodes'])
            else:
                mapped[key] = template

        return mapped
```

#### 2.3.4 SwitchNodeExecutor

**책임**: SWITCH 노드 실행 (조건 분기)

```python
class SwitchNodeExecutor(INodeExecutor):
    async def execute(self, instance: WorkflowInstance, node: Node, context: dict) -> Any:
        """SWITCH 노드 실행"""
        config = node.config
        branches = config['branches']

        # 각 분기의 조건 평가
        for branch in branches:
            condition = branch.get('condition')

            # default 분기
            if condition == 'default':
                return {'selected_branch': branch['target']}

            # 조건 평가
            if self._evaluate_condition(condition, context):
                return {'selected_branch': branch['target']}

        # 조건 만족하는 분기 없음
        raise NodeExecutionError("No branch condition satisfied")

    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """조건 평가 (Jinja2 표현식)"""
        from jinja2 import Template

        # 보안: eval() 사용 금지, Jinja2 표현식만 허용
        t = Template("{{ " + condition + " }}")
        result = t.render(input=context['input'], nodes=context['nodes'])

        # 문자열 → 불린 변환
        return result.lower() in ['true', '1', 'yes']
```

### 2.4 상태 관리 (State Manager)

```python
class StateManager(IStateManager):
    def __init__(self, repository: IWorkflowRepository):
        self.repository = repository

    async def update_status(self, instance_id: str, status: WorkflowStatus):
        """인스턴스 상태 업데이트"""
        await self.repository.update_instance(
            instance_id=instance_id,
            status=status.value,
            updated_at=datetime.utcnow()
        )

    async def update_context(self, instance_id: str, node_id: str, result: Any):
        """노드 실행 결과를 컨텍스트에 저장"""
        instance = await self.repository.get_instance(instance_id)

        # 컨텍스트 업데이트
        if 'nodes' not in instance.context:
            instance.context['nodes'] = {}

        instance.context['nodes'][node_id] = {
            'status': 'completed',
            'output': result,
            'completed_at': datetime.utcnow().isoformat()
        }

        # DB 저장
        await self.repository.update_instance(
            instance_id=instance_id,
            context=instance.context,
            current_node_id=node_id
        )

    async def set_error(self, instance_id: str, error_message: str):
        """에러 메시지 저장"""
        await self.repository.update_instance(
            instance_id=instance_id,
            error_message=error_message
        )
```

### 2.5 시퀀스 다이어그램: Workflow 실행

```
Client      WorkflowService   Executor   DataExecutor   JudgmentExecutor   StateManager
  │              │               │              │                │               │
  │ execute()    │               │              │                │               │
  ├─────────────>│               │              │                │               │
  │              │               │              │                │               │
  │              │ create_instance()            │                │               │
  │              ├──────────────────────────────────────────────────────────────>│
  │              │<──────────────────────────────────────────────────────────────┤
  │              │ (instance: PENDING)          │                │               │
  │              │               │              │                │               │
  │              │ update_status(RUNNING)       │                │               │
  │              ├──────────────────────────────────────────────────────────────>│
  │              │               │              │                │               │
  │              │ execute_node(start)          │                │               │
  │              ├──────────────>│              │                │               │
  │              │               │              │                │               │
  │              │               │ execute(DATA)│                │               │
  │              │               ├─────────────>│                │               │
  │              │               │<─────────────┤                │               │
  │              │               │ (data_result)│                │               │
  │              │               │              │                │               │
  │              │               │ update_context(node_id, result)               │
  │              │               ├──────────────────────────────────────────────>│
  │              │               │              │                │               │
  │              │               │ execute(JUDGMENT)            │               │
  │              │               ├────────────────────────────────>              │
  │              │               │<────────────────────────────────              │
  │              │               │ (judgment_result)            │               │
  │              │               │              │                │               │
  │              │<──────────────┤              │                │               │
  │              │ (completed)   │              │                │               │
  │              │               │              │                │               │
  │              │ update_status(COMPLETED)     │                │               │
  │              ├──────────────────────────────────────────────────────────────>│
  │              │               │              │                │               │
  │<─────────────┤               │              │                │               │
  │ (instance)   │               │              │                │               │
  │              │               │              │                │               │
```

### 2.6 에러 처리 전략

#### 2.6.1 노드 실행 에러

**전략**: Retry with Exponential Backoff

```python
async def execute_node_with_retry(
    executor: INodeExecutor,
    instance: WorkflowInstance,
    node: Node,
    context: dict,
    max_retries: int = 3
) -> Any:
    """노드 실행 (재시도 포함)"""
    for attempt in range(max_retries):
        try:
            result = await executor.execute(instance, node, context)
            return result

        except TransientError as e:  # 일시적 에러 (네트워크, 타임아웃)
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 지수 백오프 (1s, 2s, 4s)
                await asyncio.sleep(wait_time)
                continue
            else:
                raise NodeExecutionError(f"Node {node.id} failed after {max_retries} attempts: {str(e)}")

        except PermanentError as e:  # 영구적 에러 (입력 오류, 권한 없음)
            raise NodeExecutionError(f"Node {node.id} failed: {str(e)}")
```

#### 2.6.2 Circuit Breaker

**구현**:
```python
from enum import Enum
import time

class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: float = 0.5,
        window_size: int = 10,
        cooldown_seconds: int = 30
    ):
        self.failure_threshold = failure_threshold
        self.window_size = window_size
        self.cooldown_seconds = cooldown_seconds

        self.state = CircuitBreakerState.CLOSED
        self.failures = []
        self.successes = []
        self.opened_at = None

    async def call(self, func, *args, **kwargs):
        """회로 차단기를 통한 호출"""
        # OPEN 상태: 즉시 실패
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.opened_at > self.cooldown_seconds:
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")

        # 호출 시도
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result

        except Exception as e:
            self._record_failure()
            raise

    def _record_success(self):
        """성공 기록"""
        self.successes.append(time.time())
        self._trim_window()

        # HALF_OPEN → CLOSED
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED

    def _record_failure(self):
        """실패 기록"""
        self.failures.append(time.time())
        self._trim_window()

        # 실패율 계산
        failure_rate = self._calculate_failure_rate()

        # 임계 초과 → OPEN
        if failure_rate > self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.opened_at = time.time()

    def _calculate_failure_rate(self) -> float:
        """실패율 계산 (최근 window_size 기준)"""
        total = len(self.failures) + len(self.successes)
        if total == 0:
            return 0.0
        return len(self.failures) / total

    def _trim_window(self):
        """윈도우 크기 유지 (FIFO)"""
        while len(self.failures) > self.window_size:
            self.failures.pop(0)
        while len(self.successes) > self.window_size:
            self.successes.pop(0)
```

**Circuit Breaker 사용 예시**:
```python
# MCP 도구 호출에 Circuit Breaker 적용
mcp_circuit_breaker = CircuitBreaker(
    failure_threshold=0.5,
    window_size=10,
    cooldown_seconds=30
)

async def call_mcp_tool(server_id: str, tool_name: str, args: dict):
    try:
        result = await mcp_circuit_breaker.call(
            _call_mcp_tool_internal,
            server_id,
            tool_name,
            args
        )
        return result
    except CircuitBreakerOpenError:
        # Fallback 응답 반환
        return {'status': 'unavailable', 'message': 'Service temporarily unavailable'}
```

---

## 다음 파일로 계속

본 문서는 B-2-1로, Judgment Service와 Workflow Service의 상세 설계를 포함한다.

**다음 파일**:
- **B-2-2**: BI Service, Learning Service 상세 설계
- **B-2-3**: MCP ToolHub, Data Hub, Chat Service 상세 설계

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 |
