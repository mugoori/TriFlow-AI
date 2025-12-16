"""
TriFlow AI - Advanced Search Service (E-1 스펙)
==============================================
Hybrid Search + Cohere Reranking + CRAG 구현

스펙 참조: E-1_Advanced_RAG_Technology_Roadmap.md
- 벡터 검색 (pgvector) + 키워드 검색 (PostgreSQL FTS/ILIKE)
- RRF (Reciprocal Rank Fusion) 병합
- Cohere Rerank v3.0 (다국어 지원)
- CRAG (Corrective RAG): 검색 결과 검증 및 재검색
"""
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text

from app.config import settings
from app.database import get_db_context

logger = logging.getLogger(__name__)


class SearchStrategy(str, Enum):
    """검색 전략"""
    VECTOR_ONLY = "vector_only"
    KEYWORD_ONLY = "keyword_only"
    HYBRID = "hybrid"
    HYBRID_RERANK = "hybrid_rerank"


class RelevanceGrade(str, Enum):
    """CRAG 관련성 등급"""
    RELEVANT = "relevant"        # 관련성 높음 (0.7+)
    AMBIGUOUS = "ambiguous"      # 애매함 (0.5-0.7)
    NOT_RELEVANT = "not_relevant"  # 관련 없음 (<0.5)


@dataclass
class CRAGResult:
    """
    CRAG (Corrective RAG) 결과

    검색 결과 검증 및 재검색 결과를 담는 데이터 클래스
    """
    # 검색 결과
    results: List["SearchResult"]

    # 관련성 평가
    relevance_grade: RelevanceGrade
    avg_relevance_score: float

    # CRAG 처리 정보
    was_corrected: bool = False
    correction_method: Optional[str] = None  # "query_rewrite", "web_search", "none"
    original_query: Optional[str] = None
    rewritten_query: Optional[str] = None

    # 판단 보류 여부
    should_abstain: bool = False
    abstain_reason: Optional[str] = None

    # 메타데이터
    search_attempts: int = 1
    total_candidates: int = 0

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            "relevance_grade": self.relevance_grade.value,
            "avg_relevance_score": round(self.avg_relevance_score, 4),
            "was_corrected": self.was_corrected,
            "correction_method": self.correction_method,
            "original_query": self.original_query,
            "rewritten_query": self.rewritten_query,
            "should_abstain": self.should_abstain,
            "abstain_reason": self.abstain_reason,
            "search_attempts": self.search_attempts,
            "total_candidates": self.total_candidates,
            "result_count": len(self.results),
        }


@dataclass
class SearchResult:
    """검색 결과 단일 항목"""
    document_id: str
    title: str
    text: str
    chunk_index: int
    source_type: str
    source_id: Optional[str] = None
    section: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Optional[Dict] = None

    # 점수들
    vector_score: float = 0.0
    keyword_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0

    # 검색 소스
    found_by: str = "unknown"  # vector, keyword, both


@dataclass
class SearchResponse:
    """검색 응답"""
    success: bool
    query: str
    strategy: SearchStrategy
    results: List[SearchResult]
    count: int
    error: Optional[str] = None
    metadata: Optional[Dict] = None


class CohereReranker:
    """
    Cohere Rerank API 클라이언트
    모델: rerank-multilingual-v3.0 (다국어 지원)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'cohere_api_key', None)
        self._client = None
        self.model = "rerank-multilingual-v3.0"
        self.available = False

    def _get_client(self):
        """Cohere 클라이언트 지연 로딩"""
        if self._client is None:
            if not self.api_key:
                logger.warning("Cohere API key not configured")
                self._client = "unavailable"
                return self._client

            try:
                import cohere
                self._client = cohere.Client(api_key=self.api_key)
                self.available = True
                logger.info("Cohere Rerank client initialized")
            except ImportError:
                logger.warning("cohere package not installed. Run: pip install cohere")
                self._client = "unavailable"
            except Exception as e:
                logger.error(f"Cohere client init error: {e}")
                self._client = "unavailable"

        return self._client

    async def rerank(
        self,
        query: str,
        documents: List[SearchResult],
        top_n: int = 5,
    ) -> List[SearchResult]:
        """
        Cohere Rerank 실행

        Args:
            query: 검색 쿼리
            documents: 검색 결과 목록
            top_n: 반환할 상위 N개

        Returns:
            rerank_score가 설정된 정렬된 결과 목록
        """
        client = self._get_client()

        if client == "unavailable" or not documents:
            # Rerank 불가 시 원본 반환
            return documents[:top_n]

        try:
            # 문서 텍스트 추출
            doc_texts = [doc.text for doc in documents]

            # Cohere Rerank 호출
            response = client.rerank(
                model=self.model,
                query=query,
                documents=doc_texts,
                top_n=min(top_n, len(documents)),
            )

            # 결과 매핑
            reranked = []
            for result in response.results:
                doc = documents[result.index]
                doc.rerank_score = result.relevance_score
                doc.final_score = result.relevance_score
                doc.found_by = f"{doc.found_by}+rerank"
                reranked.append(doc)

            logger.info(f"Cohere rerank: {len(documents)} -> {len(reranked)} documents")
            return reranked

        except Exception as e:
            logger.error(f"Cohere rerank error: {e}")
            # 오류 시 원본 반환 (RRF 점수 기준)
            return sorted(documents, key=lambda x: x.rrf_score, reverse=True)[:top_n]


class HybridSearchService:
    """
    고급 하이브리드 검색 서비스 (E-1 스펙)

    검색 흐름:
    1. 벡터 검색 (pgvector) → TOP 20
    2. 키워드 검색 (PostgreSQL FTS/ILIKE) → TOP 20
    3. RRF 병합 → TOP 20
    4. Cohere Rerank → TOP 5
    """

    def __init__(
        self,
        embedding_provider=None,
        reranker: Optional[CohereReranker] = None,
        rrf_k: int = 60,
    ):
        """
        Args:
            embedding_provider: 임베딩 제공자 (RAGService와 공유)
            reranker: Cohere Reranker 인스턴스
            rrf_k: RRF 상수 (기본 60)
        """
        self.embedding_provider = embedding_provider
        self.reranker = reranker or CohereReranker()
        self.rrf_k = rrf_k

    async def _vector_search(
        self,
        tenant_id: UUID,
        query_embedding: List[float],
        limit: int = 20,
        source_type: Optional[str] = None,
    ) -> List[SearchResult]:
        """pgvector 벡터 검색"""
        query_embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        with get_db_context() as db:
            filter_clause = ""
            params = {
                "tenant_id": tenant_id,
                "query_embedding": query_embedding_str,
                "limit": limit,
            }

            if source_type:
                filter_clause = "AND d.source_type = :source_type"
                params["source_type"] = source_type

            result = db.execute(
                text(f"""
                    SELECT
                        d.id as document_id,
                        d.title,
                        d.section,
                        d.text,
                        d.chunk_index,
                        d.source_type,
                        d.source_id,
                        d.metadata,
                        d.tags,
                        1 - (e.embedding <=> CAST(:query_embedding AS vector)) as similarity
                    FROM rag.rag_embeddings e
                    JOIN rag.rag_documents d ON e.doc_id = d.id
                    WHERE d.tenant_id = :tenant_id
                    AND d.is_active = true
                    {filter_clause}
                    ORDER BY e.embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :limit
                """),
                params
            )

            results = []
            for row in result:
                results.append(SearchResult(
                    document_id=str(row.document_id),
                    title=row.title or "Untitled",
                    section=row.section,
                    text=row.text,
                    chunk_index=row.chunk_index,
                    source_type=row.source_type,
                    source_id=row.source_id,
                    tags=row.tags or [],
                    metadata=row.metadata,
                    vector_score=float(row.similarity) if row.similarity else 0.0,
                    found_by="vector",
                ))

        return results

    async def _keyword_search(
        self,
        tenant_id: UUID,
        query: str,
        limit: int = 20,
        source_type: Optional[str] = None,
    ) -> List[SearchResult]:
        """PostgreSQL 키워드 검색 (ILIKE + ts_rank)"""
        with get_db_context() as db:
            filter_clause = ""
            params = {
                "tenant_id": tenant_id,
                "query_text": query,
                "query_like": f"%{query}%",
                "limit": limit,
            }

            if source_type:
                filter_clause = "AND d.source_type = :source_type"
                params["source_type"] = source_type

            # ts_rank와 ILIKE 조합
            result = db.execute(
                text(f"""
                    SELECT
                        d.id as document_id,
                        d.title,
                        d.section,
                        d.text,
                        d.chunk_index,
                        d.source_type,
                        d.source_id,
                        d.metadata,
                        d.tags,
                        ts_rank(
                            to_tsvector('simple', COALESCE(d.text, '')),
                            plainto_tsquery('simple', :query_text)
                        ) as keyword_score
                    FROM rag.rag_documents d
                    WHERE d.tenant_id = :tenant_id
                    AND d.is_active = true
                    AND (
                        d.text ILIKE :query_like
                        OR d.title ILIKE :query_like
                    )
                    {filter_clause}
                    ORDER BY keyword_score DESC, d.created_at DESC
                    LIMIT :limit
                """),
                params
            )

            results = []
            for row in result:
                results.append(SearchResult(
                    document_id=str(row.document_id),
                    title=row.title or "Untitled",
                    section=row.section,
                    text=row.text,
                    chunk_index=row.chunk_index,
                    source_type=row.source_type,
                    source_id=row.source_id,
                    tags=row.tags or [],
                    metadata=row.metadata,
                    keyword_score=float(row.keyword_score) if row.keyword_score else 0.0,
                    found_by="keyword",
                ))

        return results

    def _rrf_merge(
        self,
        vector_results: List[SearchResult],
        keyword_results: List[SearchResult],
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> List[SearchResult]:
        """
        RRF (Reciprocal Rank Fusion) 병합

        score = weight * (1 / (k + rank))
        """
        scores: Dict[str, float] = {}
        docs: Dict[str, SearchResult] = {}

        # 벡터 검색 결과 점수 계산
        for rank, doc in enumerate(vector_results):
            doc_id = doc.document_id
            rrf_score = vector_weight / (self.rrf_k + rank + 1)
            scores[doc_id] = scores.get(doc_id, 0) + rrf_score

            if doc_id not in docs:
                docs[doc_id] = doc
            else:
                # 이미 존재하면 벡터 점수만 업데이트
                docs[doc_id].vector_score = doc.vector_score

        # 키워드 검색 결과 점수 계산
        for rank, doc in enumerate(keyword_results):
            doc_id = doc.document_id
            rrf_score = keyword_weight / (self.rrf_k + rank + 1)
            scores[doc_id] = scores.get(doc_id, 0) + rrf_score

            if doc_id not in docs:
                docs[doc_id] = doc
            else:
                # 이미 존재하면 키워드 점수 업데이트 및 found_by 변경
                docs[doc_id].keyword_score = doc.keyword_score
                docs[doc_id].found_by = "both"

        # RRF 점수 설정 및 정렬
        merged = []
        for doc_id, doc in docs.items():
            doc.rrf_score = scores[doc_id]
            doc.final_score = scores[doc_id]  # rerank 전까지는 RRF가 final
            merged.append(doc)

        merged.sort(key=lambda x: x.rrf_score, reverse=True)

        return merged

    async def search(
        self,
        tenant_id: UUID,
        query: str,
        strategy: SearchStrategy = SearchStrategy.HYBRID_RERANK,
        top_k: int = 5,
        fetch_k: int = 20,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        source_type: Optional[str] = None,
        use_rerank: bool = True,
    ) -> SearchResponse:
        """
        통합 검색 메서드

        Args:
            tenant_id: 테넌트 ID
            query: 검색 쿼리
            strategy: 검색 전략
            top_k: 최종 반환 개수
            fetch_k: 각 검색에서 가져올 개수
            vector_weight: 벡터 검색 가중치
            keyword_weight: 키워드 검색 가중치
            source_type: 소스 타입 필터
            use_rerank: Cohere Rerank 사용 여부

        Returns:
            SearchResponse
        """
        try:
            results: List[SearchResult] = []

            if strategy == SearchStrategy.VECTOR_ONLY:
                # 벡터만
                if not self.embedding_provider:
                    return SearchResponse(
                        success=False,
                        query=query,
                        strategy=strategy,
                        results=[],
                        count=0,
                        error="Embedding provider not configured",
                    )

                query_embedding = await self.embedding_provider.embed_query(query)
                results = await self._vector_search(
                    tenant_id, query_embedding, limit=top_k, source_type=source_type
                )

            elif strategy == SearchStrategy.KEYWORD_ONLY:
                # 키워드만
                results = await self._keyword_search(
                    tenant_id, query, limit=top_k, source_type=source_type
                )

            elif strategy in (SearchStrategy.HYBRID, SearchStrategy.HYBRID_RERANK):
                # 하이브리드
                if not self.embedding_provider:
                    # 임베딩 없으면 키워드만
                    logger.warning("No embedding provider, falling back to keyword search")
                    results = await self._keyword_search(
                        tenant_id, query, limit=top_k, source_type=source_type
                    )
                else:
                    # 병렬 검색 실행
                    query_embedding = await self.embedding_provider.embed_query(query)

                    vector_task = self._vector_search(
                        tenant_id, query_embedding, limit=fetch_k, source_type=source_type
                    )
                    keyword_task = self._keyword_search(
                        tenant_id, query, limit=fetch_k, source_type=source_type
                    )

                    vector_results, keyword_results = await asyncio.gather(
                        vector_task, keyword_task
                    )

                    logger.info(
                        f"Vector: {len(vector_results)}, Keyword: {len(keyword_results)}"
                    )

                    # RRF 병합
                    results = self._rrf_merge(
                        vector_results,
                        keyword_results,
                        vector_weight=vector_weight,
                        keyword_weight=keyword_weight,
                    )

                    # Rerank 적용
                    if strategy == SearchStrategy.HYBRID_RERANK and use_rerank and results:
                        results = await self.reranker.rerank(
                            query=query,
                            documents=results[:fetch_k],
                            top_n=top_k,
                        )
                    else:
                        results = results[:top_k]

            # 최종 점수로 정렬
            results.sort(key=lambda x: x.final_score, reverse=True)

            return SearchResponse(
                success=True,
                query=query,
                strategy=strategy,
                results=results,
                count=len(results),
                metadata={
                    "vector_weight": vector_weight,
                    "keyword_weight": keyword_weight,
                    "rrf_k": self.rrf_k,
                    "rerank_enabled": strategy == SearchStrategy.HYBRID_RERANK and use_rerank,
                },
            )

        except Exception as e:
            logger.error(f"Search error: {e}")
            import traceback
            logger.error(traceback.format_exc())

            return SearchResponse(
                success=False,
                query=query,
                strategy=strategy,
                results=[],
                count=0,
                error=str(e),
            )

    # =========================================
    # CRAG (Corrective RAG) Methods
    # =========================================

    def _evaluate_relevance(
        self,
        results: List[SearchResult],
        high_threshold: float = 0.7,
        low_threshold: float = 0.5,
    ) -> Tuple[RelevanceGrade, float]:
        """
        검색 결과의 관련성 평가

        Args:
            results: 검색 결과 목록
            high_threshold: 높은 관련성 임계값 (기본 0.7)
            low_threshold: 낮은 관련성 임계값 (기본 0.5)

        Returns:
            (관련성 등급, 평균 점수)
        """
        if not results:
            return RelevanceGrade.NOT_RELEVANT, 0.0

        # final_score 기준으로 평가 (rerank_score > rrf_score > vector_score)
        scores = []
        for r in results:
            if r.rerank_score > 0:
                scores.append(r.rerank_score)
            elif r.rrf_score > 0:
                # RRF 점수는 0~0.03 범위이므로 정규화
                normalized = min(r.rrf_score * 30, 1.0)
                scores.append(normalized)
            else:
                scores.append(r.vector_score)

        avg_score = sum(scores) / len(scores) if scores else 0.0

        # 상위 결과 점수도 고려 (첫 번째 결과가 중요)
        top_score = scores[0] if scores else 0.0

        # 가중 평균: 상위 결과 50%, 전체 평균 50%
        weighted_score = (top_score * 0.5) + (avg_score * 0.5)

        if weighted_score >= high_threshold:
            return RelevanceGrade.RELEVANT, weighted_score
        elif weighted_score >= low_threshold:
            return RelevanceGrade.AMBIGUOUS, weighted_score
        else:
            return RelevanceGrade.NOT_RELEVANT, weighted_score

    async def _rewrite_query(self, query: str, context: Optional[str] = None) -> str:
        """
        쿼리 재작성 (Query Rewrite)

        간단한 규칙 기반 재작성 + 동의어 확장
        (향후 LLM 기반 재작성으로 확장 가능)

        Args:
            query: 원본 쿼리
            context: 추가 컨텍스트 (선택)

        Returns:
            재작성된 쿼리
        """
        # 한국어 동의어/유의어 매핑
        synonyms = {
            # 제조/생산 관련
            "불량": "결함 품질 이상 defect",
            "불량률": "불량율 결함률 defect rate",
            "생산량": "생산수량 output 산출량",
            "온도": "temperature 열 기온",
            "설비": "장비 기계 machine equipment",
            "라인": "생산라인 line 공정",
            # 분석 관련
            "원인": "이유 reason cause 요인",
            "추세": "추이 트렌드 trend 경향",
            "이상": "비정상 anomaly abnormal",
            # 시간 관련
            "오늘": "당일 today 금일",
            "이번주": "금주 this week",
            "이번달": "금월 this month",
        }

        # 쿼리에서 키워드 확장
        expanded_terms = []
        query_lower = query.lower()

        for keyword, expansions in synonyms.items():
            if keyword in query_lower:
                expanded_terms.append(expansions)

        if expanded_terms:
            # 원본 쿼리 + 확장 키워드
            rewritten = f"{query} {' '.join(expanded_terms)}"
            logger.info(f"Query rewritten: '{query}' -> '{rewritten[:100]}...'")
            return rewritten

        # 확장할 키워드가 없으면 원본 반환
        return query

    async def corrective_search(
        self,
        tenant_id: UUID,
        query: str,
        top_k: int = 5,
        max_attempts: int = 2,
        relevance_threshold: float = 0.5,
        source_type: Optional[str] = None,
        use_rerank: bool = True,
    ) -> CRAGResult:
        """
        CRAG (Corrective RAG) 검색

        검색 결과를 검증하고, 관련성이 낮으면 쿼리를 재작성하여 재검색

        흐름:
        1. 초기 검색 (Hybrid + Rerank)
        2. 관련성 평가
        3. 관련성 낮으면 → Query Rewrite → 재검색
        4. 여전히 낮으면 → 판단 보류 (should_abstain=True)

        Args:
            tenant_id: 테넌트 ID
            query: 검색 쿼리
            top_k: 반환할 결과 수
            max_attempts: 최대 검색 시도 횟수
            relevance_threshold: 관련성 임계값
            source_type: 소스 타입 필터
            use_rerank: Cohere Rerank 사용 여부

        Returns:
            CRAGResult
        """
        original_query = query
        current_query = query
        all_candidates = []
        attempt = 0

        while attempt < max_attempts:
            attempt += 1

            # 검색 실행
            response = await self.search(
                tenant_id=tenant_id,
                query=current_query,
                strategy=SearchStrategy.HYBRID_RERANK if use_rerank else SearchStrategy.HYBRID,
                top_k=top_k * 2,  # 더 많이 가져와서 필터링
                source_type=source_type,
                use_rerank=use_rerank,
            )

            if not response.success:
                logger.warning(f"CRAG search failed: {response.error}")
                return CRAGResult(
                    results=[],
                    relevance_grade=RelevanceGrade.NOT_RELEVANT,
                    avg_relevance_score=0.0,
                    should_abstain=True,
                    abstain_reason=f"검색 실패: {response.error}",
                    search_attempts=attempt,
                )

            all_candidates.extend(response.results)

            # 관련성 평가
            grade, avg_score = self._evaluate_relevance(
                response.results,
                high_threshold=0.7,
                low_threshold=relevance_threshold,
            )

            logger.info(
                f"CRAG attempt {attempt}: query='{current_query[:30]}...', "
                f"grade={grade.value}, avg_score={avg_score:.3f}, "
                f"results={len(response.results)}"
            )

            # 관련성 높음 → 즉시 반환
            if grade == RelevanceGrade.RELEVANT:
                return CRAGResult(
                    results=response.results[:top_k],
                    relevance_grade=grade,
                    avg_relevance_score=avg_score,
                    was_corrected=(attempt > 1),
                    correction_method="query_rewrite" if attempt > 1 else None,
                    original_query=original_query,
                    rewritten_query=current_query if attempt > 1 else None,
                    search_attempts=attempt,
                    total_candidates=len(all_candidates),
                )

            # 마지막 시도면 현재 결과로 반환
            if attempt >= max_attempts:
                break

            # 관련성 낮음/애매함 → Query Rewrite 후 재시도
            current_query = await self._rewrite_query(query)

            # 쿼리가 변경되지 않았으면 재시도 의미 없음
            if current_query == query:
                break

        # 최종 결과 반환 (재시도 후에도 관련성 낮음)
        final_grade, final_score = self._evaluate_relevance(all_candidates[:top_k])

        # 판단 보류 여부 결정
        should_abstain = final_grade == RelevanceGrade.NOT_RELEVANT
        abstain_reason = None
        if should_abstain:
            abstain_reason = (
                f"검색 결과의 관련성이 낮습니다 (점수: {final_score:.2f}). "
                "질문을 더 구체적으로 해주시거나, 관련 문서를 먼저 등록해주세요."
            )

        return CRAGResult(
            results=all_candidates[:top_k],
            relevance_grade=final_grade,
            avg_relevance_score=final_score,
            was_corrected=(attempt > 1),
            correction_method="query_rewrite" if attempt > 1 else None,
            original_query=original_query,
            rewritten_query=current_query if current_query != original_query else None,
            should_abstain=should_abstain,
            abstain_reason=abstain_reason,
            search_attempts=attempt,
            total_candidates=len(all_candidates),
        )


# 싱글톤
_search_service: Optional[HybridSearchService] = None


def get_search_service(embedding_provider=None) -> HybridSearchService:
    """검색 서비스 싱글톤 반환"""
    global _search_service
    if _search_service is None:
        _search_service = HybridSearchService(
            embedding_provider=embedding_provider,
            reranker=CohereReranker(),
        )
    elif embedding_provider and _search_service.embedding_provider is None:
        _search_service.embedding_provider = embedding_provider
    return _search_service


def reset_search_service():
    """테스트용: 검색 서비스 리셋"""
    global _search_service
    _search_service = None
