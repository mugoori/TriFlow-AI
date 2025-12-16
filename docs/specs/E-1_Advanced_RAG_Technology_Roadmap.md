# E-1. Advanced RAG 기술 로드맵

## 문서 정보
- **문서 ID**: E-1
- **버전**: 2.0 (V7 Intent + Orchestrator)
- **최종 수정일**: 2025-12-16
- **상태**: Active Development
- **관련 문서**:
  - B-6 AI/Agent Architecture
  - B-3-3 V7 Intent Router 설계
  - B-3-4 Orchestrator 설계
  - B-3-3 RAG/AAS Schema
  - B-2-3 Data Hub

---

## 1. 개요

### 1.1 목적
본 문서는 AI Factory Decision Engine의 RAG(Retrieval-Augmented Generation) 시스템을 고도화하기 위한 기술 로드맵을 정의한다.

### 1.2 적용 대상 기술
| 기술 | 목적 | 우선순위 |
|------|------|:---:|
| Hybrid Search + Reranking | 검색 정확도 향상 | 1 |
| CRAG/Self-RAG | 검색 품질 자가 검증 | 2 |
| Multi-Agent 동적 협업 | Agent 파이프라인 구축 | 3 |
| GraphRAG + Neo4j | 관계 기반 추론 강화 | 4 |
| Live Intelligence | 실시간 자율 판단 (아키텍처만) | 5 |

---

## 2. 우선순위 매트릭스

| 순위 | 기술 | 비즈니스 임팩트 | 구현 난이도 | 의존성 |
|:---:|------|:---:|:---:|------|
| 1 | **Hybrid Search + Reranking** | 높음 | 낮음 | 없음 (기존 RAG 개선) |
| 2 | **CRAG/Self-RAG** | 높음 | 중간 | Hybrid Search 완료 후 |
| 3 | **Agent 동적 협업 (Multi-Agent)** | 매우 높음 | 중간 | 기존 Agent 아키텍처 확장 |
| 4 | **GraphRAG + Neo4j** | 높음 | 높음 | AAS 스키마 확정, Neo4j 구축 |
| 5 | **Live Intelligence** | 중간 | 높음 | 아키텍처만 설계 (구현 보류) |

---

## 3. Phase 1: Hybrid Search + Cohere Reranking

### 3.1 아키텍처 변경점

```
기존: Query → 벡터 검색(pgvector) → Top-K → LLM

개선: Query → [벡터 검색 + 키워드 검색] → RRF 병합 → Cohere Rerank → Top-K → LLM
```

### 3.2 키워드 검색 엔진 비교

| 항목 | PostgreSQL FTS | Elasticsearch |
|------|---------------|---------------|
| **추가 인프라** | 불필요 (기존 DB 활용) | 별도 클러스터 필요 |
| **한국어 지원** | 제한적 (pg_bigm 확장 필요) | 우수 (nori 분석기) |
| **확장성** | 단일 노드 한계 | 수평 확장 용이 |
| **운영 비용** | 낮음 | 중간~높음 |
| **추천** | MVP 단계 | 데이터 TB 이상 시 |

**결정**: MVP에서는 **PostgreSQL + pg_bigm**으로 시작 → 데이터 증가 시 Elasticsearch 마이그레이션

### 3.3 Cohere Rerank 통합 설계

```python
# Data Hub의 RAGPipeline 확장
class EnhancedRAGPipeline:
    def __init__(self, cohere_client, vector_db, text_search):
        self.cohere = cohere_client
        self.vector_db = vector_db
        self.text_search = text_search

    async def retrieve(self, query: str, tenant_id: str, top_k: int = 5) -> list:
        # 1. 병렬 검색 실행
        vector_results, keyword_results = await asyncio.gather(
            self.vector_db.search(query, tenant_id, limit=20),
            self.text_search.search(query, tenant_id, limit=20)
        )

        # 2. RRF(Reciprocal Rank Fusion) 병합
        merged = self._rrf_merge(vector_results, keyword_results, k=60)

        # 3. Cohere Rerank
        reranked = self.cohere.rerank(
            model="rerank-multilingual-v3.0",
            query=query,
            documents=[doc.content for doc in merged[:20]],
            top_n=top_k
        )

        return [merged[r.index] for r in reranked.results]

    def _rrf_merge(self, list1: list, list2: list, k: int = 60) -> list:
        """Reciprocal Rank Fusion 알고리즘"""
        scores = {}

        for rank, doc in enumerate(list1):
            scores[doc.id] = scores.get(doc.id, 0) + 1 / (k + rank + 1)

        for rank, doc in enumerate(list2):
            scores[doc.id] = scores.get(doc.id, 0) + 1 / (k + rank + 1)

        # 점수 기준 정렬
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        # 문서 객체 반환
        all_docs = {doc.id: doc for doc in list1 + list2}
        return [all_docs[doc_id] for doc_id in sorted_ids if doc_id in all_docs]
```

### 3.4 PostgreSQL pg_bigm 설정

```sql
-- pg_bigm 확장 설치
CREATE EXTENSION IF NOT EXISTS pg_bigm;

-- 텍스트 검색 인덱스 생성
CREATE INDEX idx_rag_documents_content_bigm
ON rag_documents USING gin (content gin_bigm_ops);

-- 검색 함수
CREATE OR REPLACE FUNCTION search_keyword_docs(
    search_query TEXT,
    p_tenant_id UUID,
    limit_count INTEGER DEFAULT 20
)
RETURNS TABLE (
    doc_id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.content,
        d.metadata,
        bigm_similarity(d.content, search_query) AS similarity
    FROM rag_documents d
    WHERE d.tenant_id = p_tenant_id
      AND d.is_active = true
      AND d.content LIKE '%' || search_query || '%'
    ORDER BY bigm_similarity(d.content, search_query) DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;
```

---

## 4. Phase 2: CRAG/Self-RAG

### 4.1 적용 위치 결정

| 위치 | 장점 | 단점 | 적합한 경우 |
|------|------|------|------------|
| **Intent Router** | 초기 필터링으로 불필요한 Judgment 호출 방지 | Intent 분류 지연 증가 | 검색 품질이 Intent 분류에 영향 |
| **Judgment LLM** | 판단 정확도 직접 향상 | Judgment마다 검증 비용 발생 | 고신뢰도 판단 필요 시 |

**결정**: 2단계 적용
1. **1단계**: Judgment Engine에 CRAG 적용 (판단 품질 직접 향상)
2. **2단계**: Intent Router에도 적용 (모호한 Intent 처리 개선)

### 4.2 Judgment Engine CRAG 흐름

```
Input → RAG 검색 → [검증 LLM: 관련성 평가]
                         ↓
              관련성 낮음? → 재검색 또는 "판단 보류" 반환
                         ↓
              관련성 높음 → Rule + LLM Hybrid 판단 실행
```

### 4.3 CRAG 검증 프롬프트

```
[SYSTEM]
당신은 검색 결과의 품질을 평가하는 검증자입니다.
사용자 질의와 검색된 문서의 관련성을 평가하세요.

## 출력 형식
{
  "relevance_score": 0.0~1.0,
  "is_sufficient": true|false,
  "reasoning": "평가 근거",
  "action": "proceed|retry_search|escalate"
}

## 평가 기준
- 0.8 이상: 높은 관련성 → proceed
- 0.5~0.8: 중간 관련성 → 추가 검색 고려
- 0.5 미만: 낮은 관련성 → retry_search 또는 escalate

[USER]
질의: {query}
검색 결과:
{retrieved_documents}
```

### 4.4 외부 검색 Fallback

```python
class CRAGPipeline:
    async def retrieve_with_validation(self, query: str, context: dict) -> RAGResult:
        # 1차: 내부 RAG 검색
        internal_results = await self.rag_pipeline.retrieve(query, context['tenant_id'])

        # 2차: 관련성 검증
        validation = await self.validate_relevance(query, internal_results)

        if validation['is_sufficient']:
            return RAGResult(documents=internal_results, source='internal')

        # 3차: 재검색 (쿼리 확장)
        if validation['action'] == 'retry_search':
            expanded_query = await self.expand_query(query)
            retry_results = await self.rag_pipeline.retrieve(expanded_query, context['tenant_id'])

            retry_validation = await self.validate_relevance(query, retry_results)
            if retry_validation['is_sufficient']:
                return RAGResult(documents=retry_results, source='internal_retry')

        # 4차: 판단 보류 반환 (외부 검색은 현재 비활성화)
        return RAGResult(
            documents=[],
            source='none',
            action='defer',
            message='충분한 정보를 찾지 못했습니다. 추가 정보가 필요합니다.'
        )
```

---

## 5. Phase 3: Multi-Agent 동적 협업

### 5.1 Agent 파이프라인 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestrator (Meta Agent)                     │
│  - Agent 라우팅 및 파이프라인 구성                                  │
│  - 결과 병합 및 충돌 해결                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Data Collector│    │ Data Refiner  │    │ Judgment Agent│
│    Agent      │    │    Agent      │    │   (LLM Core)  │
├───────────────┤    ├───────────────┤    ├───────────────┤
│ - MCP 호출    │    │ - 이상치 제거  │    │ - Rule 평가   │
│ - 센서 수집   │ →  │ - 정규화      │ →  │ - LLM 보완    │
│ - DB 쿼리     │    │ - 특성 추출   │    │ - 설명 생성   │
│ - 외부 API    │    │ - 유효성 검증  │    │ - 조치 제안   │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Action Agent    │
                    │ - 알림 발송       │
                    │ - 티켓 생성       │
                    │ - Workflow 트리거 │
                    └───────────────────┘
```

### 5.2 Agent 간 핸드오프 프로토콜

```json
{
  "message_id": "msg_uuid",
  "pipeline_id": "pipe_001",
  "stage": 2,
  "total_stages": 4,
  "from": "data_collector",
  "to": "data_refiner",
  "type": "handoff",
  "payload": {
    "raw_data": {},
    "source_metadata": {},
    "quality_score": 0.85
  },
  "context": {
    "trace_id": "trace_xyz",
    "session_id": "sess_001",
    "accumulated_context": {}
  }
}
```

### 5.3 Tool Search Tool

```python
class ToolSearchTool:
    """Agent가 사용할 도구를 동적으로 검색"""

    async def search_tools(self, task_description: str, context: dict) -> list[Tool]:
        # 1. 작업 설명을 임베딩
        task_embedding = await self.embed(task_description)

        # 2. Tool Registry에서 유사도 검색
        matching_tools = await self.tool_registry.search(
            embedding=task_embedding,
            filters={"tenant_id": context["tenant_id"]},
            top_k=5
        )

        # 3. 권한 및 가용성 필터링
        available_tools = [
            tool for tool in matching_tools
            if self._check_permission(tool, context["user_role"])
            and self._check_availability(tool)
        ]

        return available_tools
```

---

## 6. Phase 4: GraphRAG + Neo4j

### 6.1 AAS 표준 관계 타입 (IEC 63278-1 기반)

| 관계 타입 | 설명 | 예시 |
|----------|------|------|
| `HasSubmodel` | Asset이 Submodel 보유 | Line → QualitySubmodel |
| `HasPart` | 부품/구성요소 관계 | Equipment → Sensor |
| `IsPartOf` | 상위 구조 관계 | Sensor → Equipment |
| `IsDerivedFrom` | 파생 관계 | Product_v2 → Product_v1 |
| `SameAs` | 동일 개체 참조 | AAS_ID → ERP_ID |
| `HasProperty` | 속성 보유 | Equipment → Temperature |

### 6.2 제조 도메인 확장 관계

| 관계 타입 | 설명 | RCA 활용 |
|----------|------|---------|
| `ProducedBy` | 제품-설비 관계 | 불량 발생 설비 추적 |
| `UsedMaterial` | 제품-원료 관계 | 원료 LOT 문제 추적 |
| `CausedBy` | 원인-결과 관계 | 근본 원인 분석 |
| `OperatedBy` | 설비-작업자 관계 | 작업자 숙련도 분석 |
| `LocatedIn` | 위치 관계 | 라인/공정 영향 범위 |

### 6.3 Neo4j 스키마 설계

```cypher
// 노드 타입
(:Asset {aas_id, asset_type, name, tenant_id})
(:Submodel {submodel_id, semantic_id, name})
(:Property {property_id, value, unit, timestamp})
(:Product {product_id, lot_number, production_date})
(:Event {event_id, event_type, severity, timestamp})

// 관계 생성 예시
CREATE (line:Asset {aas_id: 'L01', asset_type: 'Line'})
CREATE (equip:Asset {aas_id: 'E001', asset_type: 'Equipment'})
CREATE (line)-[:HAS_PART {since: date()}]->(equip)

// RCA 쿼리 예시: 불량 발생 시 연관 요소 추적
MATCH path = (defect:Event {event_type: 'DEFECT'})
  -[:OCCURRED_AT]->(equip:Asset)
  -[:USED_MATERIAL]->(material:Product)
  -[:SUPPLIED_BY]->(supplier:Asset)
WHERE defect.timestamp > datetime() - duration('P7D')
RETURN path
```

### 6.4 LLM 기반 엔티티/관계 추출 프롬프트

```
[SYSTEM]
당신은 제조업 도메인의 지식 그래프 추출 전문가입니다.
문서에서 엔티티와 관계를 추출하여 JSON으로 반환합니다.

## 엔티티 타입
- Equipment: 설비, 장비, 기계
- Product: 제품, 반제품, 원료
- Process: 공정, 작업 단계
- Parameter: 온도, 압력, 속도 등 공정 변수
- Defect: 불량 유형, 결함
- Person: 작업자, 관리자

## 관계 타입
- HAS_PART, PRODUCES, USES_MATERIAL, CAUSES, LOCATED_IN, OPERATED_BY

## 출력 형식
{
  "entities": [
    {"id": "e1", "type": "Equipment", "name": "믹서기 M-01", "properties": {}}
  ],
  "relationships": [
    {"source": "e1", "target": "e2", "type": "PRODUCES", "properties": {}}
  ]
}
```

---

## 7. Phase 5: Live Intelligence (아키텍처만)

### 7.1 설계 목표
향후 확장을 위한 아키텍처 예약. 현재 버전에서는 구현하지 않음.

### 7.2 아키텍처 설계

```
┌────────────────────────────────────────────────────────────────┐
│                    Event Stream Layer                          │
│  Kafka/Kinesis (센서, 이벤트 실시간 스트림)                       │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Stream Processor │
                    │  (향후 구현 예약)   │
                    │  - 패턴 감지       │
                    │  - 이상 탐지       │
                    │  - 자동 트리거     │
                    └───────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        [Alert Agent]  [Auto Workflow]  [Dashboard Push]
```

### 7.3 현재 vs 향후 버전

| 구분 | 현재 버전 | 향후 버전 |
|------|----------|----------|
| 데이터 처리 | Batch 기반 (스케줄러) | Stream 기반 (실시간) |
| 트리거 방식 | 수동 또는 주기적 | 이벤트 기반 자동 |
| 반응 시간 | 분 단위 | 초 단위 |

---

## 8. 구현 로드맵

```
Phase 1 (Sprint 1-2): Hybrid Search + Reranking
├── PostgreSQL pg_bigm 설정
├── Cohere Rerank API 통합
└── RAGPipeline 성능 테스트

Phase 2 (Sprint 3-4): CRAG + Multi-Agent 기반
├── Judgment Engine에 CRAG 적용
├── Agent 파이프라인 프로토콜 구현
├── Tool Search Tool 개발
└── Data Collector/Refiner Agent 분리

Phase 3 (Sprint 5-6): GraphRAG 기반 구축
├── Neo4j 클러스터 구축 (AWS Neptune 또는 Neo4j Aura)
├── AAS → Neo4j 동기화 파이프라인
├── LLM 엔티티 추출 파이프라인
└── GraphRAG 검색 통합

Phase 4 (향후): Live Intelligence
├── Kafka/Kinesis 스트림 레이어
├── Stream Processor 개발
└── 실시간 Agent 트리거
```

---

## 9. 기술 결정 사항 요약

| 항목 | 결정 | 근거 |
|------|------|------|
| 그래프 DB | Neo4j (별도 도입) | 복잡한 관계 추론, Cypher 쿼리 강점 |
| 키워드 검색 | PostgreSQL pg_bigm (MVP) → Elasticsearch (확장) | 초기 비용 절감, 점진적 확장 |
| Reranker | Cohere Rerank API | API 기반, 다국어 지원, 운영 편의성 |
| CRAG 적용 위치 | Judgment Engine 우선 → Intent Router 확장 | 판단 품질 직접 개선 |
| SLM | 현재 미적용 | API 기반 솔루션 집중, Fine-tuning 리소스 부재 |
| Live Intelligence | 아키텍처만 설계 | 현재 버전 범위 외, 향후 확장 대비 |

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-12-07 | AI Factory Team | 초안 작성 |
| 2.0 | 2025-12-16 | AI Factory Team | V7 Intent + Orchestrator 통합: V7 Intent 기반 RAG 라우팅, Orchestrator Plan 내 RAG 노드 설계, Claude 모델 계열 (Haiku/Sonnet/Opus) 활용 전략, 15노드 타입 중 DATA 노드와 RAG 통합 |
