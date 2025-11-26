# B-2-2. Module/Service Design - BI & Learning Services

## 문서 정보
- **문서 ID**: B-2-2
- **버전**: 1.0
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **선행 문서**: B-2-1

## 목차
1. [BI Service 상세 설계](#1-bi-service-상세-설계)
2. [Learning Service 상세 설계](#2-learning-service-상세-설계)

---

## 1. BI Service 상세 설계

### 1.1 서비스 개요
BI Service는 자연어 질의를 받아 분석 계획(analysis_plan)으로 변환하고, SQL을 생성하여 데이터를 조회한 후 차트 설정을 생성하는 LLM 기반 BI 플래너다.

**책임**:
- 자연어 → analysis_plan 변환 (LLM)
- analysis_plan → SQL 생성
- SQL 실행 (Fact/Dim/Pre-agg)
- 차트 설정 생성
- 쿼리 캐싱
- BI 카탈로그 관리

### 1.2 클래스 다이어그램

```
┌──────────────────────────────────────────────────────────┐
│                      BIService                           │
├──────────────────────────────────────────────────────────┤
│ - planner: IBIPlanner                                    │
│ - query_generator: ISQLGenerator                         │
│ - query_executor: IQueryExecutor                         │
│ - chart_builder: IChartBuilder                           │
│ - cache_manager: ICacheManager                           │
│ - catalog_repository: ICatalogRepository                 │
├──────────────────────────────────────────────────────────┤
│ + plan(query: str) → AnalysisPlan                        │
│ + execute(plan: AnalysisPlan) → QueryResult              │
│ + render_chart(result: QueryResult) → ChartConfig        │
│ + get_catalog() → BICatalog                              │
└──────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│IBIPlanner    │  │ISQLGenerator │  │IChartBuilder │
│              │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│LLMBIPlanner  │  │PostgreSQL    │  │ChartJsBuilder│
│              │  │SQLGenerator  │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 1.3 주요 컴포넌트

#### 1.3.1 BIService (Main Orchestrator)

```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class AnalysisPlan:
    query_text: str
    intent: str
    metrics: list
    dimensions: list
    filters: list
    time_range: dict
    granularity: str
    chart_type: str
    confidence: float

@dataclass
class QueryResult:
    query_id: str
    sql: str
    columns: list
    rows: list
    row_count: int
    execution_time_ms: int

class BIService:
    def __init__(
        self,
        planner: IBIPlanner,
        query_generator: ISQLGenerator,
        query_executor: IQueryExecutor,
        chart_builder: IChartBuilder,
        cache_manager: ICacheManager,
        catalog_repository: ICatalogRepository
    ):
        self.planner = planner
        self.query_generator = query_generator
        self.query_executor = query_executor
        self.chart_builder = chart_builder
        self.cache_manager = cache_manager
        self.catalog_repository = catalog_repository

    async def execute_nl_query(self, query_text: str, tenant_id: str) -> dict:
        """자연어 쿼리 실행 (E2E)"""
        start_time = time.time()

        # 1. analysis_plan 생성
        plan = await self.plan(query_text, tenant_id)

        # 2. 캐시 조회
        cache_key = self._get_cache_key(tenant_id, plan)
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            return {**cached_result, 'from_cache': True}

        # 3. SQL 생성 및 실행
        sql = self.query_generator.generate(plan)
        query_result = await self.query_executor.execute(sql, tenant_id)

        # 4. 차트 설정 생성
        chart_config = self.chart_builder.build(plan, query_result)

        # 5. 결과 구성
        result = {
            'query_id': query_result.query_id,
            'analysis_plan': plan,
            'data': {
                'columns': query_result.columns,
                'rows': query_result.rows,
                'row_count': query_result.row_count
            },
            'chart': chart_config,
            'execution_time_ms': int((time.time() - start_time) * 1000)
        }

        # 6. 캐시 저장 (TTL 600초)
        await self.cache_manager.set(cache_key, result, ttl=600)

        return result

    async def plan(self, query_text: str, tenant_id: str) -> AnalysisPlan:
        """자연어 → analysis_plan 변환"""
        # 1. BI 카탈로그 조회 (컨텍스트)
        catalog = await self.catalog_repository.get_catalog(tenant_id)

        # 2. LLM 호출
        plan = await self.planner.create_plan(
            query_text=query_text,
            catalog=catalog
        )

        return plan

    def _get_cache_key(self, tenant_id: str, plan: AnalysisPlan) -> str:
        """캐시 키 생성"""
        import hashlib
        import json
        plan_dict = {
            'metrics': plan.metrics,
            'dimensions': plan.dimensions,
            'filters': plan.filters,
            'time_range': plan.time_range
        }
        plan_hash = hashlib.sha256(
            json.dumps(plan_dict, sort_keys=True).encode()
        ).hexdigest()
        return f"bi:cache:{tenant_id}:{plan_hash}"
```

#### 1.3.2 LLMBIPlanner

**책임**: LLM 호출하여 analysis_plan 생성

```python
from openai import OpenAI

class LLMBIPlanner(IBIPlanner):
    def __init__(self, openai_client: OpenAI, prompt_repository: IPromptRepository):
        self.client = openai_client
        self.prompt_repository = prompt_repository

    async def create_plan(self, query_text: str, catalog: dict) -> AnalysisPlan:
        """자연어 → analysis_plan"""
        # 1. 프롬프트 템플릿 조회
        prompt_template = await self.prompt_repository.get_template('bi_planner')

        # 2. 프롬프트 렌더링
        system_prompt = self._build_system_prompt(catalog)
        user_prompt = f"Generate analysis plan for: {query_text}"

        # 3. LLM 호출
        response = self.client.chat.completions.create(
            model="gpt-4o",  # 중간 복잡도, 빠른 응답
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            response_format={"type": "json_object"}
        )

        # 4. 응답 파싱
        plan_json = json.loads(response.choices[0].message.content)

        # 5. AnalysisPlan 객체 생성
        plan = AnalysisPlan(
            query_text=query_text,
            intent=plan_json['intent'],
            metrics=plan_json['metrics'],
            dimensions=plan_json['dimensions'],
            filters=plan_json.get('filters', []),
            time_range=plan_json.get('time_range', {}),
            granularity=plan_json.get('granularity', 'day'),
            chart_type=plan_json.get('chart_type', 'line'),
            confidence=plan_json.get('confidence', 0.8)
        )

        return plan

    def _build_system_prompt(self, catalog: dict) -> str:
        """시스템 프롬프트 구성"""
        datasets_desc = '\n'.join([
            f"- {ds['name']}: {ds['description']}"
            for ds in catalog['datasets']
        ])

        metrics_desc = '\n'.join([
            f"- {m['name']}: {m['description']} (aggregation: {m['aggregation']})"
            for m in catalog['metrics']
        ])

        prompt = f"""
You are a BI analyst assistant. Generate analysis plan for manufacturing data queries.

Available Datasets:
{datasets_desc}

Available Metrics:
{metrics_desc}

Respond in JSON format:
{{
  "intent": "time_series_analysis | comparison | trend_analysis",
  "metrics": [{{ "name": "production_count", "aggregation": "sum" }}],
  "dimensions": [{{ "name": "date" }}],
  "filters": [{{ "field": "line_code", "operator": "=", "value": "LINE-A" }}],
  "time_range": {{ "type": "relative", "value": "last_7_days" }},
  "granularity": "day",
  "chart_type": "line",
  "confidence": 0.0-1.0
}}
"""
        return prompt
```

#### 1.3.3 PostgreSQLGenerator (SQL Generator)

**책임**: analysis_plan → SQL 변환

```python
from sqlalchemy import text

class PostgreSQLGenerator(ISQLGenerator):
    def generate(self, plan: AnalysisPlan) -> str:
        """analysis_plan → SQL"""
        # 1. SELECT 절 (metrics)
        select_clauses = self._build_select_clauses(plan.metrics, plan.granularity)

        # 2. FROM 절 (dataset)
        from_clause = self._build_from_clause(plan)

        # 3. WHERE 절 (filters + time_range)
        where_clauses = self._build_where_clauses(plan.filters, plan.time_range)

        # 4. GROUP BY 절 (dimensions)
        group_by_clause = self._build_group_by_clause(plan.dimensions, plan.granularity)

        # 5. ORDER BY 절
        order_by_clause = self._build_order_by_clause(plan.dimensions)

        # 6. SQL 조합
        sql_parts = [
            f"SELECT {select_clauses}",
            f"FROM {from_clause}",
            f"WHERE {where_clauses}",
        ]

        if group_by_clause:
            sql_parts.append(f"GROUP BY {group_by_clause}")

        if order_by_clause:
            sql_parts.append(f"ORDER BY {order_by_clause}")

        sql_parts.append("LIMIT 10000")

        sql = '\n'.join(sql_parts) + ';'
        return sql

    def _build_select_clauses(self, metrics: list, granularity: str) -> str:
        """SELECT 절 생성"""
        clauses = []

        # Dimensions (시간 차원 처리)
        if granularity:
            clauses.append(f"DATE_TRUNC('{granularity}', date) AS date")

        # Metrics (집계 함수)
        for metric in metrics:
            agg_func = metric['aggregation'].upper()
            metric_name = metric['name']
            clauses.append(f"{agg_func}({metric_name}) AS {metric_name}")

        return ', '.join(clauses)

    def _build_where_clauses(self, filters: list, time_range: dict) -> str:
        """WHERE 절 생성"""
        clauses = ['tenant_id = :tenant_id']  # 항상 포함

        # 필터 조건
        for f in filters:
            field = f['field']
            operator = f['operator']
            value = f['value']
            clauses.append(f"{field} {operator} :{field}")

        # 시간 범위
        if time_range.get('type') == 'relative':
            value = time_range['value']
            if value == 'last_7_days':
                clauses.append("date >= CURRENT_DATE - INTERVAL '7 days'")
            elif value == 'last_30_days':
                clauses.append("date >= CURRENT_DATE - INTERVAL '30 days'")

        return ' AND '.join(clauses)
```

### 1.4 시퀀스 다이어그램: BI 자연어 쿼리

```
Client      BIService    LLMPlanner   SQLGenerator   QueryExecutor   ChartBuilder
  │             │            │              │               │              │
  │ nl_query()  │            │              │               │              │
  ├────────────>│            │              │               │              │
  │             │            │              │               │              │
  │             │ create_plan()            │               │              │
  │             ├───────────>│              │               │              │
  │             │            │              │               │              │
  │             │            │ LLM API      │               │              │
  │             │            ├─────────────────────────────────────────────┐
  │             │            │              │               │              │
  │             │<───────────┤              │               │              │
  │             │ (plan)     │              │               │              │
  │             │            │              │               │              │
  │             │ generate_sql()            │               │              │
  │             ├───────────────────────────>               │              │
  │             │<───────────────────────────               │              │
  │             │ (sql)      │              │               │              │
  │             │            │              │               │              │
  │             │ execute_sql()             │               │              │
  │             ├──────────────────────────────────────────>│              │
  │             │<──────────────────────────────────────────┤              │
  │             │ (result)   │              │               │              │
  │             │            │              │               │              │
  │             │ build_chart()             │               │              │
  │             ├─────────────────────────────────────────────────────────>│
  │             │<─────────────────────────────────────────────────────────┤
  │             │ (chart_config)            │               │              │
  │             │            │              │               │              │
  │<────────────┤            │              │               │              │
  │ (result)    │            │              │               │              │
  │             │            │              │               │              │
```

---

## 2. Learning Service 상세 설계

### 2.1 서비스 개요
Learning Service는 피드백/샘플/로그를 수집하여 Rule·Prompt를 자동/반자동 개선하고 배포/롤백을 관리하는 학습 파이프라인이다.

**책임**:
- 피드백 수집
- 샘플 큐레이션 (Positive/Negative)
- Rule 자동 추출 (Decision Tree)
- Prompt Few-shot 튜닝
- Canary 배포 (트래픽 라우팅, 메트릭 모니터링, 자동 롤백)

### 2.2 클래스 다이어그램

```
┌──────────────────────────────────────────────────────────────┐
│                    LearningService                           │
├──────────────────────────────────────────────────────────────┤
│ - feedback_collector: IFeedbackCollector                     │
│ - sample_curator: ISampleCurator                             │
│ - rule_extractor: IRuleExtractor                             │
│ - prompt_tuner: IPromptTuner                                 │
│ - deployer: IDeployer                                        │
│ - repository: ILearningRepository                            │
├──────────────────────────────────────────────────────────────┤
│ + collect_feedback(feedback: Feedback) → void                │
│ + extract_rules(workflow_id: str) → RuleCandidate            │
│ + deploy_canary(candidate_id: str, config: dict) → Deployment│
│ + rollback(deployment_id: str) → void                        │
└──────────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ISampleCurator│  │IRuleExtractor│  │IDeployer     │
└──────────────┘  └──────────────┘  └──────────────┘
         │                │                │
         ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│DBSampleCurator│  │DecisionTree  │  │CanaryDeployer│
│              │  │RuleExtractor │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 2.3 주요 컴포넌트

#### 2.3.1 DecisionTreeRuleExtractor

**책임**: Decision Tree 학습 및 Rhai 코드 변환

```python
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score

class DecisionTreeRuleExtractor(IRuleExtractor):
    async def extract(self, workflow_id: str) -> RuleCandidate:
        """Rule 자동 추출"""
        # 1. 학습 샘플 조회
        samples = await self.repository.get_learning_samples(workflow_id)

        if len(samples) < 50:
            raise InsufficientDataError("Need at least 50 samples for rule extraction")

        # 2. Feature Engineering
        X, y, feature_names = self._prepare_data(samples)

        # 3. Train/Test 분할 (70/30)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42
        )

        # 4. Decision Tree 학습
        clf = DecisionTreeClassifier(
            max_depth=5,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42
        )
        clf.fit(X_train, y_train)

        # 5. 예측 및 평가
        y_pred = clf.predict(X_test)
        precision = precision_score(y_test, y_pred, average='weighted')
        recall = recall_score(y_test, y_pred, average='weighted')
        f1 = f1_score(y_test, y_pred, average='weighted')

        # 6. Decision Tree → Rhai 코드 변환
        tree_rules = export_text(clf, feature_names=feature_names)
        rhai_code = self._convert_tree_to_rhai(tree_rules, clf, feature_names)

        # 7. RuleCandidate 저장
        candidate = await self.repository.save_rule_candidate(
            workflow_id=workflow_id,
            rule_name=f"Auto Rule {datetime.now().strftime('%Y%m%d_%H%M')}",
            rule_script=rhai_code,
            extraction_method='decision_tree',
            quality_metrics={
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'sample_count': len(samples),
                'test_sample_count': len(X_test)
            },
            feature_importance=dict(zip(feature_names, clf.feature_importances_))
        )

        return candidate

    def _prepare_data(self, samples: list) -> tuple:
        """Feature Engineering"""
        import pandas as pd

        # 1. DataFrame 변환
        df = pd.DataFrame([{
            **s['input_data'],
            'label': s['expected_output']['status']
        } for s in samples])

        # 2. Feature 생성
        df['defect_rate'] = df['defect_count'] / df['production_count']
        df['is_line_a'] = (df['line_code'] == 'LINE-A').astype(int)
        df['is_day_shift'] = (df['shift'] == 'day').astype(int)

        # 3. X, y 분리
        feature_columns = ['defect_rate', 'is_line_a', 'is_day_shift']
        X = df[feature_columns].values
        y = df['label'].values

        return X, y, feature_columns

    def _convert_tree_to_rhai(self, tree_rules: str, clf: DecisionTreeClassifier, feature_names: list) -> str:
        """Decision Tree → Rhai 코드 변환"""
        # sklearn export_text 출력을 Rhai로 변환
        # 예시 출력:
        # |--- feature_0 <= 0.05
        # |   |--- class: NORMAL
        # |--- feature_0 >  0.05
        # |   |--- class: HIGH_DEFECT

        rhai_code = "// Auto-generated Rule\n"
        rhai_code += f"// Precision: {clf.score(X_test, y_test):.2f}\n\n"

        # 간단한 if-else 변환 (실제로는 더 정교한 변환 필요)
        rhai_code += """
let defect_rate = input.defect_count / input.production_count;
let is_line_a = input.line_code == "LINE-A";

if defect_rate > 0.05 && is_line_a {
    #{
        status: "HIGH_DEFECT",
        severity: "critical",
        confidence: 0.90
    }
} else if defect_rate > 0.02 {
    #{
        status: "MODERATE_DEFECT",
        severity: "warning",
        confidence: 0.85
    }
} else {
    #{
        status: "NORMAL",
        severity: "info",
        confidence: 0.80
    }
}
"""
        return rhai_code
```

#### 2.3.2 CanaryDeployer

**책임**: Canary 배포 관리, 트래픽 라우팅, 메트릭 모니터링, 자동 롤백

```python
from dataclasses import dataclass
import asyncio

@dataclass
class CanaryConfig:
    traffic_percentage: int  # 10
    duration_minutes: int  # 60
    success_criteria: dict  # {'error_rate_max': 0.01, 'accuracy_min': 0.85}
    auto_rollback: bool  # True

class CanaryDeployer(IDeployer):
    def __init__(
        self,
        repository: IDeploymentRepository,
        metrics_collector: IMetricsCollector,
        traffic_router: ITrafficRouter
    ):
        self.repository = repository
        self.metrics_collector = metrics_collector
        self.traffic_router = traffic_router

    async def deploy(
        self,
        ruleset_id: str,
        new_version: str,
        old_version: str,
        config: CanaryConfig
    ) -> str:
        """Canary 배포 시작"""
        # 1. Deployment 레코드 생성
        deployment = await self.repository.create_deployment(
            target_type='ruleset',
            target_id=ruleset_id,
            old_version=old_version,
            new_version=new_version,
            strategy='canary',
            config=config,
            status='in_progress'
        )

        # 2. 트래픽 라우팅 설정 (10%)
        await self.traffic_router.set_routing_rule(
            ruleset_id=ruleset_id,
            version_weights={
                old_version: 90,
                new_version: 10
            }
        )

        # 3. 백그라운드 모니터링 시작
        asyncio.create_task(
            self._monitor_canary(deployment.id, config)
        )

        return deployment.id

    async def _monitor_canary(self, deployment_id: str, config: CanaryConfig):
        """Canary 모니터링 (백그라운드)"""
        deployment = await self.repository.get_deployment(deployment_id)
        start_time = time.time()
        duration_seconds = config.duration_minutes * 60

        while time.time() - start_time < duration_seconds:
            # 1. 메트릭 수집 (신규 버전만)
            metrics = await self.metrics_collector.collect(
                ruleset_id=deployment.target_id,
                version=deployment.new_version
            )

            # 2. 성공 기준 확인
            error_rate = metrics['error_rate']
            accuracy = metrics.get('accuracy', 1.0)

            if error_rate > config.success_criteria['error_rate_max']:
                # 에러율 초과 → 자동 롤백
                if config.auto_rollback:
                    await self.rollback(deployment_id, reason='error_rate_exceeded')
                    return
                else:
                    await self._send_alert(deployment_id, 'error_rate_high', metrics)

            if accuracy < config.success_criteria.get('accuracy_min', 0.0):
                # 정확도 미달 → 자동 롤백
                if config.auto_rollback:
                    await self.rollback(deployment_id, reason='accuracy_low')
                    return

            # 3. 10초 대기
            await asyncio.sleep(10)

        # 4. 지속 시간 완료 → 성공 기준 만족 → 100% 배포
        await self._promote_to_full(deployment_id)

    async def _promote_to_full(self, deployment_id: str):
        """트래픽 100%로 증가"""
        deployment = await self.repository.get_deployment(deployment_id)

        # 1. 트래픽 100%
        await self.traffic_router.set_routing_rule(
            ruleset_id=deployment.target_id,
            version_weights={
                deployment.new_version: 100
            }
        )

        # 2. Deployment 상태 업데이트
        await self.repository.update_deployment(
            deployment_id=deployment_id,
            status='completed'
        )

        # 3. 알림 발송
        await self._send_notification(deployment_id, 'canary_success')

    async def rollback(self, deployment_id: str, reason: str):
        """롤백"""
        deployment = await self.repository.get_deployment(deployment_id)

        # 1. 트래픽 구버전으로 복원
        await self.traffic_router.set_routing_rule(
            ruleset_id=deployment.target_id,
            version_weights={
                deployment.old_version: 100
            }
        )

        # 2. Deployment 상태 업데이트
        await self.repository.update_deployment(
            deployment_id=deployment_id,
            status='rolled_back',
            rollback_reason=reason
        )

        # 3. 알림 발송
        await self._send_notification(deployment_id, 'rollback_occurred', reason)
```

#### 2.3.3 TrafficRouter (트래픽 라우팅)

**책임**: 버전별 트래픽 비율 라우팅

```python
import random

class TrafficRouter(ITrafficRouter):
    def __init__(self, redis_client):
        self.redis_client = redis_client

    async def set_routing_rule(self, ruleset_id: str, version_weights: dict):
        """라우팅 규칙 저장 (Redis)"""
        key = f"traffic:routing:{ruleset_id}"
        await self.redis_client.hset(key, mapping=version_weights)

    async def get_version_for_request(self, ruleset_id: str) -> str:
        """요청별 버전 선택"""
        key = f"traffic:routing:{ruleset_id}"
        weights = await self.redis_client.hgetall(key)

        if not weights:
            # 라우팅 규칙 없음 → 최신 버전
            return await self._get_latest_version(ruleset_id)

        # 가중치 기반 랜덤 선택
        versions = list(weights.keys())
        weights_list = [int(w) for w in weights.values()]

        # Weighted Random
        selected_version = random.choices(versions, weights=weights_list, k=1)[0]
        return selected_version

    async def _get_latest_version(self, ruleset_id: str) -> str:
        """최신 활성 버전 조회"""
        # DB에서 조회
        ruleset = await get_active_ruleset(ruleset_id)
        return ruleset.version
```

**Judgment Service에서 트래픽 라우팅 적용**:
```python
class JudgmentService:
    async def execute(self, request: JudgmentRequest) -> JudgmentResult:
        # 1. 트래픽 라우팅으로 버전 선택
        ruleset_version = await self.traffic_router.get_version_for_request(
            ruleset_id=request.workflow_id
        )

        # 2. 해당 버전의 Ruleset 조회
        ruleset = await self.repository.get_ruleset_by_version(
            workflow_id=request.workflow_id,
            version=ruleset_version
        )

        # 3. Rule 실행
        rule_result = await self.rule_engine.execute_with_version(
            ruleset=ruleset,
            input_data=request.input_data
        )

        # ...
```

### 2.4 알고리즘: Rule 자동 추출

#### 2.4.1 Decision Tree 학습 및 변환

**입력**: Learning Samples (450개)

**출력**: Rhai Rule 코드, 품질 지표

**프로세스**:
```python
async def extract_rules(workflow_id: str) -> RuleCandidate:
    # 1. 샘플 조회
    samples = await get_learning_samples(workflow_id)
    # [
    #   {'input': {'defect_count': 5, 'production_count': 100, 'line_code': 'LINE-A'},
    #    'output': {'status': 'HIGH_DEFECT'}},
    #   ...
    # ]

    # 2. Feature Engineering
    features = []
    labels = []
    for s in samples:
        # Feature 계산
        defect_rate = s['input']['defect_count'] / s['input']['production_count']
        is_line_a = 1 if s['input']['line_code'] == 'LINE-A' else 0

        features.append([defect_rate, is_line_a])
        labels.append(s['output']['status'])

    X = np.array(features)
    y = np.array(labels)

    # 3. Decision Tree 학습
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3)
    clf = DecisionTreeClassifier(max_depth=5)
    clf.fit(X_train, y_train)

    # 4. 평가
    y_pred = clf.predict(X_test)
    precision = precision_score(y_test, y_pred, average='weighted')
    recall = recall_score(y_test, y_pred, average='weighted')
    f1 = f1_score(y_test, y_pred, average='weighted')

    # 5. Rhai 코드 생성
    rhai_code = """
// Auto-generated Rule
// Precision: {precision:.2f}, Recall: {recall:.2f}, F1: {f1:.2f}

let defect_rate = input.defect_count / input.production_count;
let is_line_a = input.line_code == "LINE-A";

if defect_rate > 0.05 && is_line_a {{
    #{{
        status: "HIGH_DEFECT",
        severity: "critical",
        confidence: 0.90
    }}
}} else if defect_rate > 0.02 {{
    #{{
        status: "MODERATE_DEFECT",
        severity: "warning",
        confidence: 0.85
    }}
}} else {{
    #{{
        status: "NORMAL",
        severity: "info",
        confidence: 0.80
    }}
}}
""".format(precision=precision, recall=recall, f1=f1)

    # 6. RuleCandidate 객체 반환
    return RuleCandidate(
        workflow_id=workflow_id,
        rule_script=rhai_code,
        precision=precision,
        recall=recall,
        f1_score=f1,
        sample_count=len(samples)
    )
```

### 2.5 메트릭 수집 (CanaryDeployer용)

```python
class PrometheusMetricsCollector(IMetricsCollector):
    def __init__(self, prometheus_url: str):
        self.prometheus_url = prometheus_url

    async def collect(self, ruleset_id: str, version: str) -> dict:
        """Canary 배포 메트릭 수집"""
        import httpx

        # 1. Prometheus 쿼리 (최근 5분)
        queries = {
            'error_rate': f'rate(judgment_executions_total{{ruleset_id="{ruleset_id}",version="{version}",status="error"}}[5m])',
            'latency_p95': f'histogram_quantile(0.95, judgment_execution_duration_seconds{{ruleset_id="{ruleset_id}",version="{version}"}})',
            'request_count': f'sum(judgment_executions_total{{ruleset_id="{ruleset_id}",version="{version}"}})',
        }

        metrics = {}
        async with httpx.AsyncClient() as client:
            for metric_name, query in queries.items():
                response = await client.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={'query': query}
                )
                data = response.json()
                value = float(data['data']['result'][0]['value'][1]) if data['data']['result'] else 0.0
                metrics[metric_name] = value

        # 2. 정확도 계산 (피드백 기반)
        accuracy = await self._calculate_accuracy(ruleset_id, version)
        metrics['accuracy'] = accuracy

        return metrics

    async def _calculate_accuracy(self, ruleset_id: str, version: str) -> float:
        """정확도 계산 (최근 피드백 기반)"""
        # 최근 100개 Judgment 조회
        judgments = await get_recent_judgments(ruleset_id, version, limit=100)

        # 피드백 있는 것만 필터링
        with_feedback = [j for j in judgments if j.feedback is not None]

        if len(with_feedback) < 10:
            return 1.0  # 피드백 부족, 기본값

        # 긍정 피드백 비율
        positive = sum(1 for j in with_feedback if j.feedback.feedback_value == 'thumbs_up')
        accuracy = positive / len(with_feedback)

        return accuracy
```

---

## 다음 파일로 계속

본 문서는 B-2-2로, BI Service와 Learning Service의 상세 설계를 포함한다.

**다음 파일**:
- **B-2-3**: MCP ToolHub, Data Hub, Chat Service 상세 설계

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-11-26 | AI Factory Team | 초안 작성 |
