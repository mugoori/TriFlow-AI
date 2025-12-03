"""
TriFlow AI - RAG (Retrieval-Augmented Generation) Service
==========================================================
pgvector 기반 벡터 검색 + 문서 관리
"""
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db_context

logger = logging.getLogger(__name__)

# 임베딩 차원 (모델에 따라 다름)
EMBEDDING_DIMENSIONS = {
    "voyage-3-lite": 512,
    "voyage-3": 1024,
    "text-embedding-3-small": 1536,
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


class RAGService:
    """
    RAG 서비스
    - 문서 저장/검색
    - 벡터 유사도 검색
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

    def _chunk_text(self, text: str) -> List[str]:
        """텍스트를 청크로 분할"""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # 문장 경계에서 자르기 시도
            if end < len(text):
                # 마지막 마침표, 느낌표, 물음표 찾기
                for sep in ['. ', '! ', '? ', '\n\n', '\n', ' ']:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start:
                        end = last_sep + len(sep)
                        break

            chunks.append(text[start:end].strip())
            start = end - self.chunk_overlap

        return [c for c in chunks if c]

    async def add_document(
        self,
        tenant_id: UUID,
        title: str,
        content: str,
        document_type: str = "MANUAL",
        source_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        문서 추가 및 임베딩 생성
        """
        try:
            # 청크 분할
            chunks = self._chunk_text(content)
            logger.info(f"Document split into {len(chunks)} chunks")

            # 임베딩 생성
            embeddings = await self.embedding_provider.embed(chunks)

            document_id = uuid4()

            with get_db_context() as db:
                # 문서 메타데이터 저장 (metadata를 JSON 문자열로 변환)
                metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
                db.execute(
                    text("""
                        INSERT INTO rag.documents
                        (document_id, tenant_id, title, content, document_type, source_url, metadata)
                        VALUES (:doc_id, :tenant_id, :title, :content, :doc_type, :source_url, CAST(:metadata AS jsonb))
                    """),
                    {
                        "doc_id": document_id,
                        "tenant_id": tenant_id,
                        "title": title,
                        "content": content,
                        "doc_type": document_type,
                        "source_url": source_url,
                        "metadata": metadata_json,
                    }
                )

                # 임베딩 저장 (embedding을 pgvector 형식으로 변환)
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    # embedding을 PostgreSQL vector 형식의 문자열로 변환
                    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
                    db.execute(
                        text("""
                            INSERT INTO rag.embeddings
                            (document_id, tenant_id, chunk_text, chunk_index, embedding)
                            VALUES (:doc_id, :tenant_id, :chunk_text, :chunk_index, CAST(:embedding AS vector))
                        """),
                        {
                            "doc_id": document_id,
                            "tenant_id": tenant_id,
                            "chunk_text": chunk,
                            "chunk_index": i,
                            "embedding": embedding_str,
                        }
                    )

                db.commit()

            logger.info(f"Document added: {document_id} with {len(chunks)} embeddings")

            return {
                "success": True,
                "document_id": str(document_id),
                "chunks": len(chunks),
                "title": title,
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
    ) -> Dict[str, Any]:
        """
        벡터 유사도 검색
        """
        try:
            # 쿼리 임베딩
            query_embedding = await self.embedding_provider.embed_query(query)
            # pgvector 형식으로 변환
            query_embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

            with get_db_context() as db:
                # pgvector 코사인 유사도 검색
                result = db.execute(
                    text("""
                        SELECT
                            e.embedding_id,
                            e.document_id,
                            e.chunk_text,
                            e.chunk_index,
                            d.title,
                            d.document_type,
                            1 - (e.embedding <=> CAST(:query_embedding AS vector)) as similarity
                        FROM rag.embeddings e
                        JOIN rag.documents d ON e.document_id = d.document_id
                        WHERE e.tenant_id = :tenant_id
                        AND 1 - (e.embedding <=> CAST(:query_embedding AS vector)) >= :threshold
                        ORDER BY e.embedding <=> CAST(:query_embedding AS vector)
                        LIMIT :top_k
                    """),
                    {
                        "tenant_id": tenant_id,
                        "query_embedding": query_embedding_str,
                        "threshold": similarity_threshold,
                        "top_k": top_k,
                    }
                )

                documents = []
                for row in result:
                    documents.append({
                        "document_id": str(row.document_id),
                        "title": row.title,
                        "document_type": row.document_type,
                        "chunk_text": row.chunk_text,
                        "chunk_index": row.chunk_index,
                        "similarity": round(row.similarity, 4),
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

    async def get_context(
        self,
        tenant_id: UUID,
        query: str,
        max_tokens: int = 2000,
        top_k: int = 5,
    ) -> str:
        """
        RAG 컨텍스트 생성 (에이전트용)
        검색 결과를 하나의 컨텍스트 문자열로 조합
        """
        search_result = await self.search(tenant_id, query, top_k=top_k)

        if not search_result["success"] or not search_result["results"]:
            return ""

        context_parts = []
        current_tokens = 0

        for doc in search_result["results"]:
            chunk = doc["chunk_text"]
            # 간단한 토큰 추정 (공백 기준)
            estimated_tokens = len(chunk.split())

            if current_tokens + estimated_tokens > max_tokens:
                break

            context_parts.append(
                f"[{doc['title']}] (유사도: {doc['similarity']:.2f})\n{chunk}"
            )
            current_tokens += estimated_tokens

        return "\n\n---\n\n".join(context_parts)

    async def delete_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
    ) -> Dict[str, Any]:
        """문서 삭제 (임베딩 포함)"""
        try:
            with get_db_context() as db:
                # CASCADE로 embeddings도 삭제됨
                result = db.execute(
                    text("""
                        DELETE FROM rag.documents
                        WHERE document_id = :doc_id AND tenant_id = :tenant_id
                        RETURNING document_id
                    """),
                    {"doc_id": document_id, "tenant_id": tenant_id}
                )
                deleted = result.fetchone()
                db.commit()

            if deleted:
                logger.info(f"Document deleted: {document_id}")
                return {"success": True, "deleted": str(document_id)}
            else:
                return {"success": False, "error": "Document not found"}

        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return {"success": False, "error": str(e)}

    async def list_documents(
        self,
        tenant_id: UUID,
        document_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """문서 목록 조회"""
        try:
            with get_db_context() as db:
                query = """
                    SELECT
                        d.document_id,
                        d.title,
                        d.document_type,
                        d.source_url,
                        d.created_at,
                        COUNT(e.embedding_id) as chunk_count
                    FROM rag.documents d
                    LEFT JOIN rag.embeddings e ON d.document_id = e.document_id
                    WHERE d.tenant_id = :tenant_id
                """
                params = {"tenant_id": tenant_id, "limit": limit, "offset": offset}

                if document_type:
                    query += " AND d.document_type = :doc_type"
                    params["doc_type"] = document_type

                query += """
                    GROUP BY d.document_id
                    ORDER BY d.created_at DESC
                    LIMIT :limit OFFSET :offset
                """

                result = db.execute(text(query), params)

                documents = []
                for row in result:
                    documents.append({
                        "document_id": str(row.document_id),
                        "title": row.title,
                        "document_type": row.document_type,
                        "source_url": row.source_url,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "chunk_count": row.chunk_count,
                    })

            return {
                "success": True,
                "documents": documents,
                "count": len(documents),
            }

        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return {"success": False, "documents": [], "error": str(e)}


# 싱글톤 인스턴스
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """RAG 서비스 싱글톤 반환"""
    global _rag_service
    if _rag_service is None:
        # Voyage API 키가 있으면 Voyage 사용, 없으면 로컬
        if hasattr(settings, 'voyage_api_key') and settings.voyage_api_key:
            provider = VoyageEmbeddingProvider(api_key=settings.voyage_api_key)
        else:
            provider = LocalEmbeddingProvider()
        _rag_service = RAGService(embedding_provider=provider)
    return _rag_service
