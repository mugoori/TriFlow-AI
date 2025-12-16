"""
TriFlow AI - RAG (Retrieval-Augmented Generation) Service
==========================================================
pgvector 기반 벡터 검색 + 문서 관리

스펙 참조:
- B-3-3_RAG_AAS_Schema.md
- E-1_Advanced_RAG_Technology_Roadmap.md (Hybrid Search + Reranking)

기능:
- pgvector + IVFFlat 인덱싱
- 문서 청킹 (500토큰, 50 오버랩)
- 하이브리드 검색 (벡터 + 키워드 + RRF)
- Cohere Reranking (rerank-multilingual-v3.0)
- OpenAI text-embedding-3-small (1536차원)
"""
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text

from app.config import settings
from app.database import get_db_context

logger = logging.getLogger(__name__)

# 임베딩 차원 (모델에 따라 다름)
EMBEDDING_DIMENSIONS = {
    "voyage-3-lite": 512,
    "voyage-3": 1024,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "all-MiniLM-L6-v2": 384,
    "multilingual-e5-base": 768,
}


class EmbeddingProvider:
    """임베딩 제공자 추상 클래스"""

    def __init__(self):
        self.dimension = 384  # 기본값

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """텍스트를 벡터로 변환"""
        raise NotImplementedError

    async def embed_query(self, query: str) -> List[float]:
        """단일 쿼리 임베딩"""
        result = await self.embed([query])
        return result[0]


class LocalEmbeddingProvider(EmbeddingProvider):
    """
    로컬 Sentence Transformers 기반 임베딩
    - 무료, 오프라인 사용 가능
    - CPU에서도 동작 (느림)
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        super().__init__()
        self.model_name = model_name
        self.model = None
        self.dimension = EMBEDDING_DIMENSIONS.get("all-MiniLM-L6-v2", 384)

    def _load_model(self):
        """모델 지연 로딩"""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name)
                logger.info(f"Loaded embedding model: {self.model_name}")
            except ImportError:
                logger.warning("sentence-transformers not installed. Using mock embeddings.")
                self.model = "mock"
                self.dimension = 1536  # DB 스키마와 일치 (vector(1536))

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """텍스트 배치 임베딩"""
        self._load_model()

        if self.model == "mock":
            # Mock 임베딩 (테스트용)
            import hashlib
            embeddings = []
            for text in texts:
                # 텍스트 해시 기반 결정적 임베딩 생성
                hash_val = hashlib.sha256(text.encode()).hexdigest()
                embedding = [
                    (int(hash_val[i:i+2], 16) / 255.0 - 0.5) * 2
                    for i in range(0, min(len(hash_val), self.dimension * 2), 2)
                ]
                # 차원 맞추기
                while len(embedding) < self.dimension:
                    embedding.append(0.0)
                embeddings.append(embedding[:self.dimension])
            return embeddings

        # 실제 임베딩
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


class VoyageEmbeddingProvider(EmbeddingProvider):
    """
    Voyage AI 임베딩 (Anthropic 파트너)
    - 고품질 임베딩
    - API 키 필요
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "voyage-3-lite"):
        super().__init__()
        self.api_key = api_key or getattr(settings, 'voyage_api_key', None)
        self.model = model
        self.dimension = EMBEDDING_DIMENSIONS.get(model, 512)
        self._client = None

    def _get_client(self):
        """Voyage 클라이언트 생성"""
        if self._client is None:
            try:
                import voyageai
                self._client = voyageai.Client(api_key=self.api_key)
            except ImportError:
                logger.warning("voyageai not installed")
                self._client = "unavailable"
        return self._client

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Voyage API로 임베딩"""
        client = self._get_client()

        if client == "unavailable" or not self.api_key:
            # Fallback to local
            logger.warning("Voyage unavailable, falling back to local embeddings")
            local = LocalEmbeddingProvider()
            return await local.embed(texts)

        try:
            result = client.embed(texts, model=self.model)
            return result.embeddings
        except Exception as e:
            logger.error(f"Voyage embedding error: {e}")
            local = LocalEmbeddingProvider()
            return await local.embed(texts)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI 임베딩 (스펙 B-3-3 권장)
    - text-embedding-3-small: 1536차원, 저렴
    - text-embedding-3-large: 3072차원, 고성능
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
    ):
        super().__init__()
        self.api_key = api_key or getattr(settings, 'openai_api_key', None)
        self.model = model
        self.dimension = EMBEDDING_DIMENSIONS.get(model, 1536)
        self._client = None

    def _get_client(self):
        """OpenAI 클라이언트 생성"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("openai not installed")
                self._client = "unavailable"
        return self._client

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """OpenAI API로 임베딩"""
        client = self._get_client()

        if client == "unavailable" or not self.api_key:
            logger.warning("OpenAI unavailable, falling back to local embeddings")
            local = LocalEmbeddingProvider()
            return await local.embed(texts)

        try:
            # OpenAI는 배치 처리 지원 (최대 2048개)
            response = client.embeddings.create(
                input=texts,
                model=self.model,
            )
            embeddings = [item.embedding for item in response.data]
            return embeddings
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            local = LocalEmbeddingProvider()
            return await local.embed(texts)


class RAGService:
    """
    RAG 서비스 (스펙 B-3-3 + E-1 구현)
    - 문서 저장/검색
    - 벡터 유사도 검색 (pgvector cosine)
    - 하이브리드 검색 (벡터 + 키워드 + RRF)
    - Cohere Reranking
    - 컨텍스트 생성
    """

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.embedding_provider = embedding_provider or LocalEmbeddingProvider()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._search_service = None  # 지연 로딩

    def _compute_text_hash(self, text: str) -> str:
        """텍스트 해시 계산 (중복 검사용)"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def _chunk_text(self, text: str) -> List[str]:
        """
        텍스트를 청크로 분할 (스펙: 500토큰, 50 오버랩)
        토큰 대신 문자 수 사용 (평균 4자 = 1토큰 가정)
        """
        char_size = self.chunk_size * 4  # 토큰 → 문자 변환
        char_overlap = self.chunk_overlap * 4

        if len(text) <= char_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + char_size

            # 문장 경계에서 자르기 시도
            if end < len(text):
                # 마지막 마침표, 느낌표, 물음표 찾기
                for sep in ['. ', '! ', '? ', '\n\n', '\n', ' ']:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start:
                        end = last_sep + len(sep)
                        break

            chunks.append(text[start:end].strip())
            start = end - char_overlap

        return [c for c in chunks if c]

    async def add_document(
        self,
        tenant_id: UUID,
        title: str,
        content: str,
        source_type: str = "manual",  # manual, sop, wiki, faq, judgment_log, feedback, external_doc
        source_id: Optional[str] = None,
        section: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        language: str = "ko",
    ) -> Dict[str, Any]:
        """
        문서 추가 및 임베딩 생성 (스펙 B-3-3 rag_documents 테이블)

        새 스키마 (Migration 012):
        - rag.rag_documents: 문서 메타데이터 + 텍스트
        - rag.rag_embeddings: 청크별 임베딩 (doc_id가 PK)
        """
        try:
            # 청크 분할
            chunks = self._chunk_text(content)
            chunk_total = len(chunks)
            logger.info(f"Document split into {chunk_total} chunks")

            # 임베딩 생성
            embeddings = await self.embedding_provider.embed(chunks)

            parent_document_id = uuid4()
            model_name = getattr(self.embedding_provider, 'model', 'unknown')
            doc_source_id = source_id or str(parent_document_id)

            with get_db_context() as db:
                # 각 청크를 별도 문서로 저장 (rag_documents 스키마에 맞춤)
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk_doc_id = uuid4()
                    text_hash = self._compute_text_hash(chunk)
                    word_count = len(chunk.split())

                    # embedding을 PostgreSQL vector 형식의 문자열로 변환
                    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

                    # 문서 (청크) 저장 - rag_documents 스키마 (Migration 012)
                    metadata_json = json.dumps({
                        **(metadata or {}),
                        "parent_document_id": str(parent_document_id),
                    }, ensure_ascii=False)

                    tags_array = tags or []

                    db.execute(
                        text("""
                            INSERT INTO rag.rag_documents
                            (id, tenant_id, source_type, source_id, parent_id, title, section,
                             chunk_index, chunk_total, text, text_hash, word_count, char_count,
                             language, metadata, tags, is_active, version)
                            VALUES (:doc_id, :tenant_id, :source_type, :source_id, :parent_id, :title, :section,
                                    :chunk_index, :chunk_total, :text, :text_hash, :word_count, :char_count,
                                    :language, CAST(:metadata AS jsonb), :tags, true, 1)
                        """),
                        {
                            "doc_id": chunk_doc_id,
                            "tenant_id": tenant_id,
                            "source_type": source_type,
                            "source_id": doc_source_id,
                            "parent_id": None,  # 청크는 parent_id 없음 (동일 문서의 다른 청크 아님)
                            "title": title,
                            "section": section,
                            "chunk_index": i,
                            "chunk_total": chunk_total,
                            "text": chunk,
                            "text_hash": text_hash,
                            "word_count": word_count,
                            "char_count": len(chunk),
                            "language": language,
                            "metadata": metadata_json,
                            "tags": tags_array,
                        }
                    )

                    # 임베딩 저장 - rag_embeddings 스키마 (doc_id가 PK)
                    db.execute(
                        text("""
                            INSERT INTO rag.rag_embeddings
                            (doc_id, embedding, model)
                            VALUES (:doc_id, CAST(:embedding AS vector), :model)
                        """),
                        {
                            "doc_id": chunk_doc_id,
                            "model": model_name,
                            "embedding": embedding_str,
                        }
                    )

                db.commit()

            logger.info(f"Document added: {parent_document_id} with {chunk_total} embeddings")

            return {
                "success": True,
                "document_id": str(parent_document_id),
                "chunks": chunk_total,
                "title": title,
                "model": model_name,
            }

        except Exception as e:
            import traceback
            logger.error(f"Error adding document: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
            }

    async def search(
        self,
        tenant_id: UUID,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.5,
        source_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        벡터 유사도 검색 (새 스키마 Migration 012: rag_documents + rag_embeddings)
        """
        try:
            # 쿼리 임베딩
            query_embedding = await self.embedding_provider.embed_query(query)
            # pgvector 형식으로 변환
            query_embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

            with get_db_context() as db:
                # 필터 조건
                filter_clause = ""
                params = {
                    "tenant_id": tenant_id,
                    "query_embedding": query_embedding_str,
                    "threshold": similarity_threshold,
                    "top_k": top_k,
                }

                if source_type:
                    filter_clause = "AND d.source_type = :source_type"
                    params["source_type"] = source_type

                # pgvector 코사인 유사도 검색 (새 스키마 Migration 012)
                # e.doc_id = d.id (rag_embeddings.doc_id가 PK이자 FK)
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
                        AND 1 - (e.embedding <=> CAST(:query_embedding AS vector)) >= :threshold
                        {filter_clause}
                        ORDER BY e.embedding <=> CAST(:query_embedding AS vector)
                        LIMIT :top_k
                    """),
                    params
                )

                documents = []
                for row in result:
                    documents.append({
                        "document_id": str(row.document_id),
                        "title": row.title or "Untitled",
                        "section": row.section,
                        "source_type": row.source_type,
                        "source_id": row.source_id,
                        "text": row.text,
                        "chunk_index": row.chunk_index,
                        "similarity": round(row.similarity, 4),
                        "tags": row.tags or [],
                    })

            logger.info(f"RAG search found {len(documents)} results for query: {query[:50]}...")

            return {
                "success": True,
                "query": query,
                "results": documents,
                "count": len(documents),
            }

        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return {
                "success": False,
                "query": query,
                "results": [],
                "error": str(e),
            }

    async def hybrid_search(
        self,
        tenant_id: UUID,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        source_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        하이브리드 검색 (벡터 + 키워드) - 스펙 B-3-3, Migration 012

        RRF (Reciprocal Rank Fusion) 알고리즘 사용:
        score = sum(1 / (k + rank)) for each method

        Args:
            vector_weight: 벡터 검색 가중치 (기본 0.7)
            keyword_weight: 키워드 검색 가중치 (기본 0.3)
        """
        try:
            # 쿼리 임베딩
            query_embedding = await self.embedding_provider.embed_query(query)
            query_embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

            with get_db_context() as db:
                # 필터 조건
                filter_clause = ""
                params = {
                    "tenant_id": tenant_id,
                    "query_embedding": query_embedding_str,
                    "query_text": query,
                    "top_k": top_k * 2,  # 더 많이 가져와서 RRF 적용
                    "vector_weight": vector_weight,
                    "keyword_weight": keyword_weight,
                }

                if source_type:
                    filter_clause = "AND d.source_type = :source_type"
                    params["source_type"] = source_type

                # RRF 기반 하이브리드 검색 (새 스키마 Migration 012)
                result = db.execute(
                    text(f"""
                        WITH vector_search AS (
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
                                1 - (e.embedding <=> CAST(:query_embedding AS vector)) as vector_score,
                                ROW_NUMBER() OVER (ORDER BY e.embedding <=> CAST(:query_embedding AS vector)) as vector_rank
                            FROM rag.rag_embeddings e
                            JOIN rag.rag_documents d ON e.doc_id = d.id
                            WHERE d.tenant_id = :tenant_id
                            AND d.is_active = true
                            {filter_clause}
                            ORDER BY e.embedding <=> CAST(:query_embedding AS vector)
                            LIMIT :top_k
                        ),
                        keyword_search AS (
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
                                ts_rank(to_tsvector('simple', d.text), plainto_tsquery('simple', :query_text)) as keyword_score,
                                ROW_NUMBER() OVER (ORDER BY ts_rank(to_tsvector('simple', d.text), plainto_tsquery('simple', :query_text)) DESC) as keyword_rank
                            FROM rag.rag_documents d
                            WHERE d.tenant_id = :tenant_id
                            AND d.is_active = true
                            AND d.text ILIKE '%' || :query_text || '%'
                            {filter_clause}
                            ORDER BY keyword_score DESC
                            LIMIT :top_k
                        )
                        SELECT
                            COALESCE(v.document_id, k.document_id) as document_id,
                            COALESCE(v.title, k.title) as title,
                            COALESCE(v.section, k.section) as section,
                            COALESCE(v.text, k.text) as text,
                            COALESCE(v.chunk_index, k.chunk_index) as chunk_index,
                            COALESCE(v.source_type, k.source_type) as source_type,
                            COALESCE(v.source_id, k.source_id) as source_id,
                            COALESCE(v.metadata, k.metadata) as metadata,
                            COALESCE(v.tags, k.tags) as tags,
                            COALESCE(v.vector_score, 0) as vector_score,
                            COALESCE(k.keyword_score, 0) as keyword_score,
                            (
                                COALESCE(:vector_weight / (60 + v.vector_rank), 0) +
                                COALESCE(:keyword_weight / (60 + k.keyword_rank), 0)
                            ) as rrf_score
                        FROM vector_search v
                        FULL OUTER JOIN keyword_search k ON v.document_id = k.document_id
                        ORDER BY rrf_score DESC
                        LIMIT :top_k
                    """),
                    params
                )

                documents = []
                for row in result:
                    documents.append({
                        "document_id": str(row.document_id),
                        "title": row.title or "Untitled",
                        "section": row.section,
                        "source_type": row.source_type,
                        "source_id": row.source_id,
                        "text": row.text,
                        "chunk_index": row.chunk_index,
                        "tags": row.tags or [],
                        "vector_score": round(row.vector_score, 4) if row.vector_score else 0,
                        "keyword_score": round(row.keyword_score, 4) if row.keyword_score else 0,
                        "rrf_score": round(row.rrf_score, 6) if row.rrf_score else 0,
                    })

            logger.info(f"Hybrid search found {len(documents)} results for query: {query[:50]}...")

            return {
                "success": True,
                "query": query,
                "search_type": "hybrid",
                "results": documents,
                "count": len(documents),
            }

        except Exception as e:
            logger.error(f"Hybrid search error: {e}")
            # 하이브리드 검색 실패 시 벡터 검색으로 폴백
            logger.info("Falling back to vector search")
            return await self.search(tenant_id, query, top_k, source_type=source_type)

    async def get_context(
        self,
        tenant_id: UUID,
        query: str,
        max_tokens: int = 2000,
        top_k: int = 5,
        use_hybrid: bool = True,
    ) -> str:
        """
        RAG 컨텍스트 생성 (에이전트용)
        검색 결과를 하나의 컨텍스트 문자열로 조합
        """
        if use_hybrid:
            search_result = await self.hybrid_search(tenant_id, query, top_k=top_k)
        else:
            search_result = await self.search(tenant_id, query, top_k=top_k)

        if not search_result["success"] or not search_result["results"]:
            return ""

        context_parts = []
        current_tokens = 0

        for doc in search_result["results"]:
            # 새 스키마: text 컬럼 사용
            chunk = doc.get("text", "")
            # 간단한 토큰 추정 (공백 기준)
            estimated_tokens = len(chunk.split())

            if current_tokens + estimated_tokens > max_tokens:
                break

            # 스코어 표시 (하이브리드 vs 벡터)
            if "rrf_score" in doc:
                score_info = f"RRF: {doc['rrf_score']:.4f}"
            else:
                score_info = f"유사도: {doc.get('similarity', 0):.2f}"

            context_parts.append(
                f"[{doc['title']}] ({score_info})\n{chunk}"
            )
            current_tokens += estimated_tokens

        return "\n\n---\n\n".join(context_parts)

    def _get_search_service(self):
        """검색 서비스 지연 로딩"""
        if self._search_service is None:
            from app.services.search_service import HybridSearchService, CohereReranker
            self._search_service = HybridSearchService(
                embedding_provider=self.embedding_provider,
                reranker=CohereReranker(),
            )
        return self._search_service

    async def advanced_search(
        self,
        tenant_id: UUID,
        query: str,
        top_k: int = 5,
        use_rerank: bool = True,
        source_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        고급 검색 (E-1 스펙: Hybrid Search + Reranking)

        검색 흐름:
        1. 벡터 검색 (pgvector) → TOP 20
        2. 키워드 검색 (PostgreSQL FTS) → TOP 20
        3. RRF 병합 → TOP 20
        4. Cohere Rerank → TOP 5

        Args:
            tenant_id: 테넌트 ID
            query: 검색 쿼리
            top_k: 최종 반환 개수
            use_rerank: Cohere Reranking 사용 여부
            source_type: 소스 타입 필터

        Returns:
            검색 결과 딕셔너리
        """
        from app.services.search_service import SearchStrategy

        search_service = self._get_search_service()

        strategy = SearchStrategy.HYBRID_RERANK if use_rerank else SearchStrategy.HYBRID
        response = await search_service.search(
            tenant_id=tenant_id,
            query=query,
            strategy=strategy,
            top_k=top_k,
            source_type=source_type,
            use_rerank=use_rerank,
        )

        if not response.success:
            return {
                "success": False,
                "query": query,
                "results": [],
                "error": response.error,
            }

        # SearchResult를 딕셔너리로 변환
        results = []
        for r in response.results:
            results.append({
                "document_id": r.document_id,
                "title": r.title,
                "text": r.text,
                "section": r.section,
                "chunk_index": r.chunk_index,
                "source_type": r.source_type,
                "source_id": r.source_id,
                "tags": r.tags,
                "vector_score": round(r.vector_score, 4),
                "keyword_score": round(r.keyword_score, 4),
                "rrf_score": round(r.rrf_score, 6),
                "rerank_score": round(r.rerank_score, 4) if r.rerank_score else None,
                "final_score": round(r.final_score, 4),
                "found_by": r.found_by,
            })

        return {
            "success": True,
            "query": query,
            "search_type": "hybrid_rerank" if use_rerank else "hybrid",
            "results": results,
            "count": len(results),
            "metadata": response.metadata,
        }

    async def get_context_advanced(
        self,
        tenant_id: UUID,
        query: str,
        max_tokens: int = 2000,
        top_k: int = 5,
        use_rerank: bool = True,
    ) -> str:
        """
        고급 RAG 컨텍스트 생성 (E-1 스펙)

        Hybrid Search + Reranking을 사용하여 더 정확한 컨텍스트 생성
        """
        search_result = await self.advanced_search(
            tenant_id, query, top_k=top_k, use_rerank=use_rerank
        )

        if not search_result["success"] or not search_result["results"]:
            # 폴백: 기존 hybrid_search 시도
            return await self.get_context(tenant_id, query, max_tokens, top_k, use_hybrid=True)

        context_parts = []
        current_tokens = 0

        for doc in search_result["results"]:
            chunk = doc.get("text", "")
            estimated_tokens = len(chunk.split())

            if current_tokens + estimated_tokens > max_tokens:
                break

            # 점수 표시 (rerank vs RRF)
            if doc.get("rerank_score"):
                score_info = f"Rerank: {doc['rerank_score']:.2f}"
            else:
                score_info = f"RRF: {doc['rrf_score']:.4f}"

            context_parts.append(
                f"[{doc['title']}] ({score_info}, {doc['found_by']})\n{chunk}"
            )
            current_tokens += estimated_tokens

        return "\n\n---\n\n".join(context_parts)

    async def delete_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
    ) -> Dict[str, Any]:
        """문서 삭제 (임베딩 포함) - 새 스키마

        document_id는 source_id (parent_document_id)를 의미합니다.
        list_documents에서 반환되는 document_id와 일치합니다.
        """
        try:
            with get_db_context() as db:
                # source_id로 삭제 (list_documents에서 반환하는 document_id와 일치)
                # CASCADE로 embeddings도 삭제됨 (rag_embeddings.doc_id -> rag_documents.id)
                result = db.execute(
                    text("""
                        DELETE FROM rag.rag_documents
                        WHERE source_id = :doc_id AND tenant_id = :tenant_id
                        RETURNING id
                    """),
                    {"doc_id": str(document_id), "tenant_id": tenant_id}
                )
                deleted_rows = result.fetchall()
                db.commit()

            if deleted_rows:
                logger.info(f"Document deleted: {document_id} ({len(deleted_rows)} chunks)")
                return {"success": True, "deleted": str(document_id), "chunks_deleted": len(deleted_rows)}
            else:
                return {"success": False, "error": "Document not found"}

        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return {"success": False, "error": str(e)}

    async def delete_by_parent_document(
        self,
        tenant_id: UUID,
        parent_document_id: UUID,
    ) -> Dict[str, Any]:
        """부모 문서 ID로 모든 청크 삭제"""
        try:
            with get_db_context() as db:
                result = db.execute(
                    text("""
                        DELETE FROM rag.rag_documents
                        WHERE tenant_id = :tenant_id
                        AND metadata->>'parent_document_id' = :parent_id
                        RETURNING id
                    """),
                    {"tenant_id": tenant_id, "parent_id": str(parent_document_id)}
                )
                deleted_rows = result.fetchall()
                db.commit()

            count = len(deleted_rows)
            logger.info(f"Deleted {count} chunks for parent document: {parent_document_id}")
            return {"success": True, "deleted_count": count}

        except Exception as e:
            logger.error(f"Error deleting by parent document: {e}")
            return {"success": False, "error": str(e)}

    async def list_documents(
        self,
        tenant_id: UUID,
        source_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """문서 목록 조회 (부모 문서 기준 그룹핑) - Migration 012 스키마"""
        try:
            with get_db_context() as db:
                filter_clause = ""
                params = {"tenant_id": tenant_id, "limit": limit, "offset": offset}

                if source_type:
                    filter_clause = "AND source_type = :source_type"
                    params["source_type"] = source_type

                # 부모 문서 기준으로 그룹핑 (새 스키마: source_id, title 컬럼 사용)
                result = db.execute(
                    text(f"""
                        SELECT
                            metadata->>'parent_document_id' as parent_id,
                            title,
                            source_type,
                            source_id,
                            MIN(created_at) as created_at,
                            COUNT(*) as chunk_count,
                            SUM(char_count) as total_chars,
                            MAX(chunk_total) as chunk_total,
                            COALESCE(array_agg(DISTINCT t.tag) FILTER (WHERE t.tag IS NOT NULL), ARRAY[]::text[]) as all_tags
                        FROM rag.rag_documents d
                        LEFT JOIN LATERAL unnest(d.tags) as t(tag) ON true
                        WHERE d.tenant_id = :tenant_id
                        AND d.is_active = true
                        {filter_clause}
                        GROUP BY metadata->>'parent_document_id', title, source_type, source_id
                        ORDER BY MIN(created_at) DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    params
                )

                documents = []
                for row in result:
                    documents.append({
                        "document_id": row.parent_id,
                        "title": row.title or "Untitled",
                        "source_type": row.source_type,
                        "source_id": row.source_id,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "chunk_count": row.chunk_count,
                        "chunk_total": row.chunk_total,
                        "total_chars": row.total_chars,
                        "tags": row.all_tags if row.all_tags else [],
                    })

            return {
                "success": True,
                "documents": documents,
                "count": len(documents),
            }

        except Exception as e:
            # 쿼리 실패 시 간단한 버전으로 폴백
            logger.warning(f"Complex list query failed, trying simple version: {e}")
            try:
                with get_db_context() as db:
                    result = db.execute(
                        text(f"""
                            SELECT
                                metadata->>'parent_document_id' as parent_id,
                                title,
                                source_type,
                                source_id,
                                MIN(created_at) as created_at,
                                COUNT(*) as chunk_count,
                                SUM(char_count) as total_chars
                            FROM rag.rag_documents
                            WHERE tenant_id = :tenant_id
                            AND is_active = true
                            {filter_clause}
                            GROUP BY metadata->>'parent_document_id', title, source_type, source_id
                            ORDER BY MIN(created_at) DESC
                            LIMIT :limit OFFSET :offset
                        """),
                        params
                    )

                    documents = []
                    for row in result:
                        documents.append({
                            "document_id": row.parent_id,
                            "title": row.title or "Untitled",
                            "source_type": row.source_type,
                            "source_id": row.source_id,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                            "chunk_count": row.chunk_count,
                            "total_chars": row.total_chars,
                        })

                return {
                    "success": True,
                    "documents": documents,
                    "count": len(documents),
                }
            except Exception as e2:
                logger.error(f"Error listing documents: {e2}")
                return {"success": False, "documents": [], "error": str(e2)}


# 싱글톤 인스턴스
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """
    RAG 서비스 싱글톤 반환

    임베딩 프로바이더 우선순위:
    1. OpenAI (스펙 B-3-3 권장, OPENAI_API_KEY 필요)
    2. Voyage (VOYAGE_API_KEY 필요)
    3. 로컬 (Sentence Transformers, 무료)
    """
    global _rag_service
    if _rag_service is None:
        provider = None

        # 1. OpenAI 시도 (스펙 권장)
        if hasattr(settings, 'openai_api_key') and settings.openai_api_key:
            provider = OpenAIEmbeddingProvider(
                api_key=settings.openai_api_key,
                model="text-embedding-3-small"
            )
            logger.info("Using OpenAI embedding provider (text-embedding-3-small)")
        # 2. Voyage 시도
        elif hasattr(settings, 'voyage_api_key') and settings.voyage_api_key:
            provider = VoyageEmbeddingProvider(api_key=settings.voyage_api_key)
            logger.info("Using Voyage embedding provider")
        # 3. 로컬 폴백
        else:
            provider = LocalEmbeddingProvider()
            logger.info("Using local embedding provider (sentence-transformers)")

        _rag_service = RAGService(embedding_provider=provider)
    return _rag_service


def reset_rag_service():
    """테스트용: RAG 서비스 인스턴스 리셋"""
    global _rag_service
    _rag_service = None
