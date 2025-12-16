# E-4. 성능 테스트 계획서

## 문서 정보
- **문서 ID**: E-4
- **버전**: 2.0 (V7 Intent + Orchestrator)
- **최종 수정일**: 2025-12-16
- **상태**: Active Testing
- **관련 문서**:
  - B-3-3 V7 Intent Router 설계
  - B-3-4 Orchestrator 설계
  - C-4 Performance Capacity Enhanced
  - E-2 LLMOps Test Environment Design
  - E-3 Intent Router Prototype

---

## 1. 개요

### 1.1 목적
LLMOps 컴포넌트(Intent Router, RAG Pipeline)의 성능 특성을 파악하고, 프로덕션 환경에서의 SLO 준수 가능성을 검증합니다.

### 1.2 테스트 범위

```
┌─────────────────────────────────────────────────────────────────┐
│                    성능 테스트 대상                              │
├─────────────────────────────────────────────────────────────────┤
│  컴포넌트별 테스트                                               │
│  ├── Intent Router: 분류 지연, 처리량, 토큰 효율성               │
│  ├── RAG Pipeline: 검색 지연, Rerank 오버헤드                   │
│  └── E2E Flow: Intent → RAG → 응답 전체 지연                    │
├─────────────────────────────────────────────────────────────────┤
│  환경별 테스트                                                   │
│  ├── 기능 검증: 정확도, 품질 위주                               │
│  ├── 부하 테스트: 동시 사용자, 지속 부하                        │
│  └── 스트레스 테스트: 한계점 파악, 장애 복구                     │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 성능 목표 (SLO)

| 메트릭 | 목표 | 경고 | 위험 |
|--------|------|------|------|
| **Intent Router** |
| P50 Latency | ≤ 500ms | > 700ms | > 1000ms |
| P95 Latency | ≤ 1.5s | > 2.0s | > 3.0s |
| P99 Latency | ≤ 3.0s | > 4.0s | > 5.0s |
| Throughput | ≥ 20 req/s | < 15 req/s | < 10 req/s |
| Error Rate | < 0.5% | > 1% | > 2% |
| **RAG Pipeline** |
| Vector Search | ≤ 200ms | > 300ms | > 500ms |
| Rerank | ≤ 300ms | > 400ms | > 600ms |
| Total Retrieval | ≤ 500ms | > 700ms | > 1000ms |
| **E2E** |
| Total Latency | ≤ 3s | > 4s | > 5s |
| Concurrent Users | ≥ 50 | < 30 | < 20 |

---

## 2. 테스트 환경

### 2.1 인프라 구성

```yaml
# 테스트 환경 (AWS 기준)
test_environment:
  compute:
    - name: test-controller
      type: t3.large  # 2 vCPU, 8 GB
      purpose: 테스트 실행, 메트릭 수집

    - name: intent-router
      type: t3.medium  # 2 vCPU, 4 GB
      replicas: 2
      purpose: Intent Router 서비스

    - name: rag-service
      type: t3.large  # 2 vCPU, 8 GB
      purpose: RAG Pipeline

  database:
    - name: postgres
      type: db.t3.medium
      storage: 100 GB SSD
      purpose: pgvector, 테스트 데이터

    - name: redis
      type: cache.t3.micro
      purpose: 응답 캐싱

  external_apis:
    - OpenAI API (gpt-4.1-mini)
    - Cohere Rerank API (rerank-v3.5)
```

### 2.2 테스트 도구

```yaml
testing_tools:
  load_testing:
    - locust: Python 기반 부하 테스트
    - k6: JavaScript 기반 성능 테스트

  monitoring:
    - prometheus: 메트릭 수집
    - grafana: 대시보드
    - cloudwatch: AWS 통합 모니터링

  profiling:
    - py-spy: Python 프로파일링
    - opentelemetry: 분산 추적

  reporting:
    - allure: 테스트 리포트
    - custom: Python 리포트 생성기
```

---

## 3. 테스트 시나리오

### 3.1 Intent Router 성능 테스트

#### 3.1.1 기본 지연 시간 테스트

```python
# tests/performance/test_intent_latency.py
import pytest
import asyncio
import statistics
from src.intent_router import IntentRouter

class TestIntentLatency:
    """Intent Router 지연 시간 테스트"""

    @pytest.fixture
    def router(self):
        return IntentRouter(config={"model": "gpt-4.1-mini"})

    @pytest.fixture
    def test_queries(self):
        """다양한 복잡도의 테스트 쿼리"""
        return {
            "simple": [
                "안녕",
                "도움말",
                "품질 상태 어때?"
            ],
            "medium": [
                "L01 불량률 확인해줘",
                "지난주 생산량 요약",
                "설비 E001 상태"
            ],
            "complex": [
                "L01 야간 불량률 왜 올랐는지 분석해주고 차트도 보여줘",
                "온도 60도 넘으면 슬랙으로 알려주고 라인도 정지시켜줘",
                "전주 대비 라인별 OEE 비교해서 개선점 알려줘"
            ]
        }

    async def test_simple_query_latency(self, router, test_queries):
        """간단한 쿼리 지연 시간: P95 < 1s"""
        latencies = []

        for query in test_queries["simple"] * 10:  # 30회 반복
            result = await router.classify({"message": query})
            latencies.append(result.processing_time_ms)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        assert p50 < 500, f"Simple query P50 > 500ms: {p50:.0f}ms"
        assert p95 < 1000, f"Simple query P95 > 1s: {p95:.0f}ms"

        print(f"Simple queries - P50: {p50:.0f}ms, P95: {p95:.0f}ms")

    async def test_complex_query_latency(self, router, test_queries):
        """복잡한 쿼리 지연 시간: P95 < 2s"""
        latencies = []

        for query in test_queries["complex"] * 10:  # 30회 반복
            result = await router.classify({"message": query})
            latencies.append(result.processing_time_ms)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        assert p50 < 1000, f"Complex query P50 > 1s: {p50:.0f}ms"
        assert p95 < 2000, f"Complex query P95 > 2s: {p95:.0f}ms"

        print(f"Complex queries - P50: {p50:.0f}ms, P95: {p95:.0f}ms")

    async def test_cache_hit_latency(self, router, test_queries):
        """캐시 히트 시 지연 시간: P95 < 50ms"""
        query = test_queries["simple"][0]

        # 첫 번째 호출 (캐시 미스)
        await router.classify({"message": query})

        # 두 번째 호출부터 캐시 히트
        latencies = []
        for _ in range(20):
            result = await router.classify({"message": query})
            if result.method == "cache":
                latencies.append(result.processing_time_ms)

        if latencies:
            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            assert p95 < 50, f"Cache hit P95 > 50ms: {p95:.0f}ms"
            print(f"Cache hit - P95: {p95:.0f}ms")
```

#### 3.1.2 부하 테스트 (Locust)

```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between, events
import json
import random

# 테스트 데이터
TEST_QUERIES = [
    # Simple
    {"message": "안녕", "expected_latency_ms": 1000},
    {"message": "품질 상태 어때?", "expected_latency_ms": 1500},
    {"message": "도움말", "expected_latency_ms": 1000},
    # Medium
    {"message": "L01 불량률 확인해줘", "expected_latency_ms": 1500},
    {"message": "지난주 생산량 요약", "expected_latency_ms": 1500},
    {"message": "설비 E001 상태", "expected_latency_ms": 1500},
    # Complex
    {"message": "L01 야간 불량률 왜 올랐어?", "expected_latency_ms": 2000},
]


class IntentRouterUser(HttpUser):
    """Intent Router 부하 테스트 사용자"""

    wait_time = between(0.5, 2.0)  # 요청 간 대기 시간
    host = "http://localhost:8000"

    @task(10)
    def classify_simple(self):
        """간단한 쿼리 (가중치: 10)"""
        query = random.choice(TEST_QUERIES[:3])
        self._classify(query)

    @task(5)
    def classify_medium(self):
        """중간 복잡도 쿼리 (가중치: 5)"""
        query = random.choice(TEST_QUERIES[3:6])
        self._classify(query)

    @task(2)
    def classify_complex(self):
        """복잡한 쿼리 (가중치: 2)"""
        query = random.choice(TEST_QUERIES[6:])
        self._classify(query)

    def _classify(self, query: dict):
        """분류 요청 실행"""
        with self.client.post(
            "/api/v1/intent/classify",
            json={"message": query["message"]},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()

                # 지연 시간 검증
                if data["processing_time_ms"] > query["expected_latency_ms"] * 2:
                    response.failure(
                        f"Latency too high: {data['processing_time_ms']:.0f}ms"
                    )
                else:
                    response.success()
            else:
                response.failure(f"Status code: {response.status_code}")


# 커스텀 메트릭 수집
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, **kwargs):
    """요청 완료 시 커스텀 메트릭 기록"""
    pass  # Prometheus로 전송 등


# 실행: locust -f locustfile.py --users 50 --spawn-rate 5 --run-time 5m
```

#### 3.1.3 K6 부하 테스트

```javascript
// tests/performance/k6_intent_test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// 커스텀 메트릭
const errorRate = new Rate('errors');
const intentLatency = new Trend('intent_latency');
const cacheHitRate = new Rate('cache_hits');

// 테스트 설정
export const options = {
    scenarios: {
        // 시나리오 1: 정상 부하
        normal_load: {
            executor: 'constant-arrival-rate',
            rate: 20,  // 20 req/s
            duration: '5m',
            preAllocatedVUs: 50,
            maxVUs: 100,
        },
        // 시나리오 2: 피크 부하
        peak_load: {
            executor: 'ramping-arrival-rate',
            startRate: 20,
            stages: [
                { duration: '2m', target: 50 },   // 2분간 50 req/s로 증가
                { duration: '3m', target: 50 },   // 3분간 유지
                { duration: '2m', target: 20 },   // 2분간 감소
            ],
            preAllocatedVUs: 100,
            maxVUs: 200,
            startTime: '5m',  // 정상 부하 후 시작
        },
    },
    thresholds: {
        'http_req_duration{scenario:normal_load}': ['p(95)<1500'],
        'http_req_duration{scenario:peak_load}': ['p(95)<3000'],
        'errors': ['rate<0.01'],  // 에러율 1% 미만
    },
};

// 테스트 쿼리
const queries = [
    '안녕',
    '품질 상태 어때?',
    'L01 불량률 확인해줘',
    '지난주 생산량 요약',
    'L01 야간 불량률 왜 올랐어?',
];

export default function () {
    const query = queries[Math.floor(Math.random() * queries.length)];

    const payload = JSON.stringify({
        message: query,
        session_id: `sess_${__VU}_${__ITER}`,
    });

    const params = {
        headers: { 'Content-Type': 'application/json' },
        timeout: '10s',
    };

    const response = http.post(
        'http://localhost:8000/api/v1/intent/classify',
        payload,
        params
    );

    // 응답 검증
    const success = check(response, {
        'status is 200': (r) => r.status === 200,
        'has intent': (r) => JSON.parse(r.body).intent !== undefined,
        'latency < 3s': (r) => r.timings.duration < 3000,
    });

    // 메트릭 기록
    errorRate.add(!success);

    if (response.status === 200) {
        const data = JSON.parse(response.body);
        intentLatency.add(data.processing_time_ms);
        cacheHitRate.add(data.method === 'cache');
    }

    sleep(Math.random() * 0.5);  // 0-0.5초 대기
}

// 실행: k6 run k6_intent_test.js
```

### 3.2 RAG Pipeline 성능 테스트

#### 3.2.1 검색 지연 시간 테스트

```python
# tests/performance/test_rag_latency.py
import pytest
import asyncio
import statistics
from src.rag_pipeline import RAGPipeline

class TestRAGLatency:
    """RAG Pipeline 지연 시간 테스트"""

    @pytest.fixture
    def rag(self):
        return RAGPipeline(config={
            "embedding_model": "text-embedding-3-small",
            "rerank_model": "rerank-v3.5",
            "vector_top_k": 20,
            "final_top_k": 5
        })

    @pytest.fixture
    def test_queries(self):
        return [
            "불량률 3% 초과 시 조치 절차",
            "설비 진동 이상 판단 기준",
            "CCP 온도 관리 방법",
            "LOT 추적 프로세스",
            "품질 검사 샘플링 기준"
        ]

    async def test_vector_search_latency(self, rag, test_queries):
        """Vector Search 지연: P95 < 200ms"""
        latencies = []

        for query in test_queries * 10:  # 50회
            start = time.time()
            _ = await rag.vector_search(query, top_k=20)
            latencies.append((time.time() - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        assert p95 < 200, f"Vector search P95 > 200ms: {p95:.0f}ms"
        print(f"Vector search - P50: {p50:.0f}ms, P95: {p95:.0f}ms")

    async def test_rerank_latency(self, rag, test_queries):
        """Rerank 지연: P95 < 300ms"""
        latencies = []

        for query in test_queries * 10:  # 50회
            # 먼저 검색
            docs = await rag.vector_search(query, top_k=20)

            # Rerank 측정
            start = time.time()
            _ = await rag.rerank(query, docs, top_k=5)
            latencies.append((time.time() - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        assert p95 < 300, f"Rerank P95 > 300ms: {p95:.0f}ms"
        print(f"Rerank - P50: {p50:.0f}ms, P95: {p95:.0f}ms")

    async def test_full_retrieval_latency(self, rag, test_queries):
        """전체 검색 지연: P95 < 500ms"""
        latencies = []

        for query in test_queries * 10:  # 50회
            start = time.time()
            _ = await rag.retrieve(query)  # Vector + Rerank
            latencies.append((time.time() - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        assert p95 < 500, f"Full retrieval P95 > 500ms: {p95:.0f}ms"
        print(f"Full retrieval - P50: {p50:.0f}ms, P95: {p95:.0f}ms")


class TestRAGThroughput:
    """RAG 처리량 테스트"""

    async def test_concurrent_searches(self, rag, test_queries):
        """동시 검색 처리량 테스트"""
        concurrent_levels = [5, 10, 20, 50]

        for concurrent in concurrent_levels:
            tasks = [
                rag.retrieve(random.choice(test_queries))
                for _ in range(concurrent)
            ]

            start = time.time()
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start

            throughput = concurrent / elapsed
            avg_latency = elapsed * 1000 / concurrent

            print(f"Concurrent {concurrent}: {throughput:.1f} req/s, "
                  f"avg latency: {avg_latency:.0f}ms")

            # 동시 10 이상에서도 처리량 유지
            if concurrent >= 10:
                assert throughput >= 5, \
                    f"Throughput too low at {concurrent} concurrent"
```

### 3.3 E2E 성능 테스트

```python
# tests/performance/test_e2e_latency.py
import pytest
import asyncio
import time

class TestE2ELatency:
    """E2E (Intent → RAG → Response) 지연 시간 테스트"""

    @pytest.fixture
    def e2e_pipeline(self):
        """전체 파이프라인 구성"""
        return E2EPipeline(
            intent_router=IntentRouter(config={}),
            rag_pipeline=RAGPipeline(config={}),
            response_generator=ResponseGenerator(config={})
        )

    async def test_e2e_latency(self, e2e_pipeline):
        """E2E 지연: P95 < 3s"""
        test_cases = [
            "L01 불량률 왜 올랐어?",  # Intent → RAG → 분석
            "지난주 품질 요약해줘",     # Intent → RAG → BI
            "설비 진동 이상 없어?",     # Intent → RAG → 판단
        ]

        latencies = []

        for query in test_cases * 10:  # 30회
            start = time.time()
            result = await e2e_pipeline.process(query)
            latencies.append((time.time() - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]

        assert p95 < 3000, f"E2E P95 > 3s: {p95:.0f}ms"

        print(f"""
        E2E Latency Results:
        - P50: {p50:.0f}ms
        - P95: {p95:.0f}ms
        - P99: {p99:.0f}ms
        """)

    async def test_latency_breakdown(self, e2e_pipeline):
        """지연 시간 구간별 분석"""
        query = "L01 불량률 왜 올랐어?"

        # 각 단계별 측정
        timings = {
            "preprocessing": [],
            "intent_classification": [],
            "rag_retrieval": [],
            "response_generation": [],
            "total": []
        }

        for _ in range(20):
            breakdown = await e2e_pipeline.process_with_timing(query)
            for key, value in breakdown.items():
                timings[key].append(value)

        print("\nLatency Breakdown (P50 / P95):")
        for stage, values in timings.items():
            p50 = statistics.median(values)
            p95 = sorted(values)[int(len(values) * 0.95)]
            print(f"  {stage}: {p50:.0f}ms / {p95:.0f}ms")
```

---

## 4. 스트레스 테스트

### 4.1 한계점 파악 테스트

```python
# tests/performance/test_stress.py
import asyncio
from dataclasses import dataclass
from typing import List

@dataclass
class StressTestResult:
    max_concurrent_users: int
    breaking_point_rps: float
    error_threshold_rps: float
    recovery_time_seconds: float
    bottlenecks: List[str]

class StressTester:
    """스트레스 테스트 실행기"""

    async def find_breaking_point(self, router) -> StressTestResult:
        """시스템 한계점 탐색"""
        rps_levels = [10, 20, 30, 50, 75, 100, 150, 200]
        results = []

        for target_rps in rps_levels:
            print(f"\nTesting at {target_rps} req/s...")

            # 1분간 부하 생성
            result = await self._run_load(router, target_rps, duration=60)
            results.append(result)

            # 에러율 체크
            if result["error_rate"] > 0.05:  # 5% 초과
                print(f"Breaking point reached at {target_rps} req/s")
                break

            # P95 체크
            if result["p95_latency_ms"] > 5000:  # 5초 초과
                print(f"Latency threshold exceeded at {target_rps} req/s")
                break

            # 복구 대기
            await asyncio.sleep(10)

        # 결과 분석
        breaking_rps = self._find_breaking_rps(results)
        error_rps = self._find_error_threshold(results)
        recovery_time = await self._measure_recovery_time(router)
        bottlenecks = self._identify_bottlenecks(results)

        return StressTestResult(
            max_concurrent_users=int(breaking_rps * 0.8),  # 80% 안전마진
            breaking_point_rps=breaking_rps,
            error_threshold_rps=error_rps,
            recovery_time_seconds=recovery_time,
            bottlenecks=bottlenecks
        )

    async def _run_load(self, router, target_rps: int, duration: int) -> dict:
        """부하 생성 및 측정"""
        latencies = []
        errors = 0
        start_time = time.time()

        interval = 1.0 / target_rps
        tasks = []

        while time.time() - start_time < duration:
            task = asyncio.create_task(self._single_request(router))
            tasks.append(task)
            await asyncio.sleep(interval)

        # 모든 요청 완료 대기
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                errors += 1
            else:
                latencies.append(result)

        return {
            "target_rps": target_rps,
            "actual_rps": len(results) / duration,
            "total_requests": len(results),
            "errors": errors,
            "error_rate": errors / len(results) if results else 1.0,
            "p50_latency_ms": statistics.median(latencies) if latencies else 0,
            "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            "p99_latency_ms": sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0,
        }

    async def _single_request(self, router) -> float:
        """단일 요청 및 지연 측정"""
        query = random.choice(TEST_QUERIES)
        start = time.time()
        await router.classify({"message": query["message"]})
        return (time.time() - start) * 1000

    async def _measure_recovery_time(self, router) -> float:
        """장애 후 복구 시간 측정"""
        # 과부하 유발
        await self._run_load(router, target_rps=200, duration=30)

        # 복구 시간 측정
        start = time.time()
        while True:
            result = await router.classify({"message": "테스트"})
            if result.processing_time_ms < 1500:  # 정상 범위
                break
            await asyncio.sleep(1)
            if time.time() - start > 60:  # 최대 60초
                break

        return time.time() - start

    def _identify_bottlenecks(self, results: List[dict]) -> List[str]:
        """병목 지점 식별"""
        bottlenecks = []

        # 지연 시간 급증 패턴 분석
        for i in range(1, len(results)):
            prev = results[i-1]
            curr = results[i]

            # P95 지연 2배 이상 증가
            if curr["p95_latency_ms"] > prev["p95_latency_ms"] * 2:
                bottlenecks.append(
                    f"Latency spike at {curr['target_rps']} req/s"
                )

            # 에러율 급증
            if curr["error_rate"] > prev["error_rate"] * 3:
                bottlenecks.append(
                    f"Error spike at {curr['target_rps']} req/s"
                )

        return bottlenecks
```

### 4.2 장애 복구 테스트

```python
# tests/performance/test_resilience.py
import pytest
import asyncio

class TestResilience:
    """복원력 테스트"""

    async def test_api_timeout_recovery(self, router):
        """API 타임아웃 후 복구"""
        # 정상 요청
        result1 = await router.classify({"message": "테스트"})
        assert result1.intent != "unknown"

        # 타임아웃 유발 (매우 긴 쿼리)
        long_query = "테스트 " * 100
        try:
            await router.classify({"message": long_query})
        except:
            pass

        # 복구 확인
        result2 = await router.classify({"message": "테스트"})
        assert result2.intent != "unknown"

    async def test_redis_failure_recovery(self, router):
        """Redis 장애 시 graceful degradation"""
        # Redis 중지 시뮬레이션
        router.cache.enabled = False

        # 캐시 없이도 동작해야 함
        result = await router.classify({"message": "품질 상태 어때?"})
        assert result.intent == "quality_check"
        assert result.method == "llm"  # 캐시 아님

        # Redis 복구
        router.cache.enabled = True

    async def test_rate_limit_handling(self, router):
        """Rate Limit 대응"""
        # 빠른 연속 요청
        results = await asyncio.gather(*[
            router.classify({"message": f"테스트 {i}"})
            for i in range(10)
        ])

        # 일부는 성공해야 함
        success_count = sum(1 for r in results if r.intent != "unknown")
        assert success_count >= 5

    async def test_graceful_shutdown(self, router):
        """Graceful shutdown 테스트"""
        # 진행 중인 요청 시작
        task = asyncio.create_task(
            router.classify({"message": "긴 처리가 필요한 복잡한 쿼리"})
        )

        # 짧은 대기 후 종료 신호
        await asyncio.sleep(0.1)
        router.shutdown()

        # 진행 중인 요청은 완료되어야 함
        result = await task
        assert result is not None
```

---

## 5. 비용 테스트

### 5.1 API 비용 분석

```python
# tests/performance/test_cost.py
import pytest
from dataclasses import dataclass
from typing import Dict

@dataclass
class CostAnalysis:
    avg_tokens_per_request: float
    cost_per_request_usd: float
    daily_cost_estimate_usd: float
    monthly_cost_estimate_usd: float
    breakdown: Dict[str, float]

class CostAnalyzer:
    """API 비용 분석기"""

    # 가격 (2024년 기준, USD)
    PRICING = {
        "gpt-4.1-mini": {
            "input": 0.15 / 1_000_000,   # per token
            "output": 0.60 / 1_000_000,
        },
        "gpt-4.1": {
            "input": 2.00 / 1_000_000,
            "output": 8.00 / 1_000_000,
        },
        "text-embedding-3-small": {
            "input": 0.02 / 1_000_000,
        },
        "cohere-rerank-v3.5": {
            "per_search": 0.002,  # per search (1000 docs)
        }
    }

    def analyze_intent_router(self, samples: list) -> CostAnalysis:
        """Intent Router 비용 분석"""
        total_input_tokens = sum(s["input_tokens"] for s in samples)
        total_output_tokens = sum(s["output_tokens"] for s in samples)
        num_requests = len(samples)

        avg_input = total_input_tokens / num_requests
        avg_output = total_output_tokens / num_requests

        # GPT-4.1-mini 기준
        pricing = self.PRICING["gpt-4.1-mini"]
        cost_per_request = (
            avg_input * pricing["input"] +
            avg_output * pricing["output"]
        )

        # 일일 추정 (10,000 요청 기준)
        daily_requests = 10_000
        daily_cost = cost_per_request * daily_requests

        return CostAnalysis(
            avg_tokens_per_request=avg_input + avg_output,
            cost_per_request_usd=cost_per_request,
            daily_cost_estimate_usd=daily_cost,
            monthly_cost_estimate_usd=daily_cost * 30,
            breakdown={
                "input_tokens_avg": avg_input,
                "output_tokens_avg": avg_output,
                "input_cost_ratio": avg_input * pricing["input"] / cost_per_request,
                "output_cost_ratio": avg_output * pricing["output"] / cost_per_request,
            }
        )

    def analyze_rag_pipeline(self, samples: list) -> CostAnalysis:
        """RAG Pipeline 비용 분석"""
        # Embedding 비용
        total_embed_tokens = sum(s["embed_tokens"] for s in samples)
        avg_embed = total_embed_tokens / len(samples)
        embed_cost = avg_embed * self.PRICING["text-embedding-3-small"]["input"]

        # Rerank 비용
        rerank_cost = self.PRICING["cohere-rerank-v3.5"]["per_search"]

        cost_per_request = embed_cost + rerank_cost

        daily_requests = 10_000
        daily_cost = cost_per_request * daily_requests

        return CostAnalysis(
            avg_tokens_per_request=avg_embed,
            cost_per_request_usd=cost_per_request,
            daily_cost_estimate_usd=daily_cost,
            monthly_cost_estimate_usd=daily_cost * 30,
            breakdown={
                "embedding_cost_ratio": embed_cost / cost_per_request,
                "rerank_cost_ratio": rerank_cost / cost_per_request,
            }
        )


class TestCost:
    """비용 테스트"""

    def test_intent_router_daily_budget(self, cost_analyzer):
        """Intent Router 일일 예산: $50 이하"""
        # 실제 요청 샘플 수집
        samples = self._collect_samples(100)
        analysis = cost_analyzer.analyze_intent_router(samples)

        assert analysis.daily_cost_estimate_usd <= 50, \
            f"Daily cost exceeds budget: ${analysis.daily_cost_estimate_usd:.2f}"

        print(f"""
        Intent Router Cost Analysis:
        - Avg tokens: {analysis.avg_tokens_per_request:.0f}
        - Cost per request: ${analysis.cost_per_request_usd:.6f}
        - Daily estimate: ${analysis.daily_cost_estimate_usd:.2f}
        - Monthly estimate: ${analysis.monthly_cost_estimate_usd:.2f}
        """)

    def test_token_efficiency(self, router):
        """토큰 효율성: 평균 < 1000 토큰"""
        samples = []

        for query in TEST_QUERIES:
            result = router.classify({"message": query["message"]})
            samples.append(result.tokens_used)

        avg_tokens = sum(samples) / len(samples)
        assert avg_tokens < 1000, f"Avg tokens too high: {avg_tokens:.0f}"

    def test_cache_cost_savings(self, router):
        """캐시 비용 절감 효과"""
        # 캐시 없이
        router.cache.enabled = False
        no_cache_tokens = []
        for query in TEST_QUERIES[:5]:
            for _ in range(10):
                result = router.classify({"message": query["message"]})
                no_cache_tokens.append(result.tokens_used or 500)

        # 캐시 사용
        router.cache.enabled = True
        with_cache_tokens = []
        for query in TEST_QUERIES[:5]:
            for _ in range(10):
                result = router.classify({"message": query["message"]})
                with_cache_tokens.append(result.tokens_used or 0)

        no_cache_cost = sum(no_cache_tokens) * 0.15 / 1_000_000
        with_cache_cost = sum(with_cache_tokens) * 0.15 / 1_000_000
        savings_pct = (1 - with_cache_cost / no_cache_cost) * 100

        print(f"Cache savings: {savings_pct:.1f}%")
        assert savings_pct >= 30, f"Cache savings too low: {savings_pct:.1f}%"
```

---

## 6. 테스트 실행 일정

### 6.1 테스트 단계

```
Week 1: 기본 성능 측정
├── Day 1-2: 환경 구축 및 검증
├── Day 3-4: Intent Router 지연 시간 테스트
└── Day 5: RAG Pipeline 지연 시간 테스트

Week 2: 부하 및 스트레스 테스트
├── Day 1-2: Locust/K6 부하 테스트
├── Day 3-4: 스트레스 테스트 및 한계점 파악
└── Day 5: 장애 복구 테스트

Week 3: 최적화 및 보고서
├── Day 1-2: 병목 지점 분석 및 최적화
├── Day 3-4: 비용 분석 및 최적화
└── Day 5: 최종 리포트 작성
```

### 6.2 테스트 자동화

```yaml
# .github/workflows/performance-test.yml
name: Performance Tests

on:
  schedule:
    - cron: '0 2 * * 1'  # 매주 월요일 02:00 UTC
  workflow_dispatch:

jobs:
  performance-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Start test environment
        run: docker-compose -f docker-compose.test.yml up -d

      - name: Wait for services
        run: sleep 60

      - name: Run latency tests
        run: pytest tests/performance/test_intent_latency.py -v

      - name: Run load tests (k6)
        run: k6 run tests/performance/k6_intent_test.js

      - name: Run cost analysis
        run: pytest tests/performance/test_cost.py -v

      - name: Generate report
        run: python scripts/generate_perf_report.py

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: performance-report
          path: reports/performance/
```

---

## 7. 리포트 템플릿

### 7.1 성능 테스트 결과 리포트

```markdown
# LLMOps 성능 테스트 리포트

**테스트 일시**: YYYY-MM-DD HH:MM
**테스트 환경**: AWS t3.medium x 2
**테스트 버전**: v0.1.0

## 1. 요약

| 컴포넌트 | 상태 | P50 | P95 | 처리량 |
|---------|------|-----|-----|--------|
| Intent Router | ✅ PASS | 523ms | 1,234ms | 25 req/s |
| RAG Pipeline | ✅ PASS | 312ms | 478ms | 40 req/s |
| E2E | ✅ PASS | 1,245ms | 2,567ms | 15 req/s |

## 2. Intent Router

### 지연 시간
- P50: 523ms (목표: 500ms) ⚠️
- P95: 1,234ms (목표: 1,500ms) ✅
- P99: 2,156ms (목표: 3,000ms) ✅

### 처리량
- 정상 부하: 25 req/s (목표: 20 req/s) ✅
- 피크 부하: 45 req/s (최대)
- 에러율: 0.3% (목표: <0.5%) ✅

### 캐시 효과
- 캐시 히트율: 65%
- 캐시 히트 시 지연: 12ms (P95)
- 비용 절감: 42%

## 3. RAG Pipeline

### 검색 지연
- Vector Search: 156ms (P95)
- Rerank: 245ms (P95)
- Total: 478ms (P95)

### Rerank 효과
- MRR 개선: +0.15
- Recall@5 개선: +12%

## 4. 비용 분석

| 항목 | 일일 추정 | 월간 추정 |
|------|----------|----------|
| Intent Router | $32.50 | $975 |
| RAG Pipeline | $18.20 | $546 |
| **합계** | **$50.70** | **$1,521** |

## 5. 권장사항

1. **P50 지연 개선**: 프롬프트 최적화로 토큰 절감
2. **캐시 TTL 조정**: 1시간 → 2시간 (히트율 개선)
3. **배치 처리**: 동시 요청 시 배치 API 활용

## 6. 다음 단계

- [ ] 프롬프트 최적화 (Week 3)
- [ ] 캐시 전략 개선 (Week 3)
- [ ] E2E 지연 목표 달성 (Week 4)
```

---

## 8. 관련 문서

- [E-2_LLMOps_Test_Environment_Design.md](E-2_LLMOps_Test_Environment_Design.md)
- [E-3_Intent_Router_Prototype.md](E-3_Intent_Router_Prototype.md)
- [B-6_AI_Agent_Architecture_Prompt_Spec.md](B-6_AI_Agent_Architecture_Prompt_Spec.md)

---

## 문서 이력

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 1.0 | 2025-12-14 | QA Team | 초기 성능 테스트 계획 수립 |
| 2.0 | 2025-12-16 | QA Team | V7 Intent + Orchestrator 성능 테스트 확장: V7 Intent 14개 분류 정확도/지연시간 벤치마크, Orchestrator Plan 생성 성능 (Sonnet 1500토큰 SLO), 15노드 타입별 실행 성능 프로파일링, Claude 모델 계열 (Haiku/Sonnet/Opus) 비용-성능 트레이드오프 분석 |
