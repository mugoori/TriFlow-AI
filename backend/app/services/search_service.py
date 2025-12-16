"""
TriFlow AI - Advanced Search Service (E-1 스펙)
==============================================
Hybrid Search + Cohere Reranking 구현

스펙 참조: E-1_Advanced_RAG_Technology_Roadmap.md
- 벡터 검색 (pgvector) + 키워드 검색 (PostgreSQL FTS/ILIKE)
- RRF (Reciprocal Rank Fusion) 병합
- Cohere Rerank v3.0 (다국어 지원)
"""
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
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
