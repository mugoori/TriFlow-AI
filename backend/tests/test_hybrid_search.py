"""
Hybrid Search + Reranking 테스트 (E-1 스펙)
===========================================
- 벡터 검색, 키워드 검색, RRF 병합 테스트
- Cohere Reranking 테스트 (Mock)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.search_service import (
    SearchStrategy,
    SearchResult,
    CohereReranker,
    HybridSearchService,
)


class TestSearchResult:
    """SearchResult 데이터클래스 테스트"""

    def test_search_result_creation(self):
        """SearchResult 생성"""
        result = SearchResult(
            document_id="doc-1",
            title="테스트 문서",
            text="테스트 내용입니다.",
            chunk_index=0,
            source_type="manual",
            vector_score=0.85,
            keyword_score=0.5,
            found_by="both",
        )

        assert result.document_id == "doc-1"
        assert result.vector_score == 0.85
        assert result.keyword_score == 0.5
        assert result.found_by == "both"

    def test_search_result_defaults(self):
        """SearchResult 기본값"""
        result = SearchResult(
            document_id="doc-1",
            title="테스트",
            text="내용",
            chunk_index=0,
            source_type="manual",
        )

        assert result.vector_score == 0.0
        assert result.keyword_score == 0.0
        assert result.rrf_score == 0.0
        assert result.rerank_score == 0.0
        assert result.final_score == 0.0
        assert result.found_by == "unknown"


class TestCohereReranker:
    """Cohere Reranker 테스트"""

    def test_reranker_without_api_key(self):
        """API 키 없이 Reranker 생성"""
        reranker = CohereReranker(api_key=None)
        assert not reranker.available

    @pytest.mark.asyncio
    async def test_rerank_without_client(self):
        """클라이언트 없이 rerank 호출"""
        reranker = CohereReranker(api_key=None)
        docs = [
            SearchResult(
                document_id="doc-1",
                title="문서1",
                text="내용1",
                chunk_index=0,
                source_type="manual",
            )
        ]

        result = await reranker.rerank("쿼리", docs, top_n=1)

        # API 없으면 원본 반환
        assert len(result) == 1
        assert result[0].document_id == "doc-1"

    @pytest.mark.asyncio
    async def test_rerank_with_mock_client(self):
        """Mock Cohere 클라이언트로 rerank"""
        reranker = CohereReranker(api_key="test-key")

        # Mock 클라이언트 설정
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(index=1, relevance_score=0.95),
            MagicMock(index=0, relevance_score=0.80),
        ]
        mock_client.rerank.return_value = mock_result

        with patch.object(reranker, '_get_client', return_value=mock_client):
            reranker.available = True

            docs = [
                SearchResult(
                    document_id="doc-1",
                    title="문서1",
                    text="내용1",
                    chunk_index=0,
                    source_type="manual",
                ),
                SearchResult(
                    document_id="doc-2",
                    title="문서2",
                    text="내용2",
                    chunk_index=0,
                    source_type="manual",
                ),
            ]

            result = await reranker.rerank("검색 쿼리", docs, top_n=2)

            # 순서 변경 확인 (doc-2가 더 높은 점수)
            assert len(result) == 2
            assert result[0].rerank_score == 0.95
            assert result[1].rerank_score == 0.80


class TestRRFMerge:
    """RRF (Reciprocal Rank Fusion) 병합 테스트"""

    @pytest.fixture
    def search_service(self):
        return HybridSearchService(rrf_k=60)

    def test_rrf_merge_basic(self, search_service):
        """기본 RRF 병합"""
        vector_results = [
            SearchResult(
                document_id="doc-1",
                title="문서1",
                text="벡터로 찾은 문서1",
                chunk_index=0,
                source_type="manual",
                vector_score=0.9,
                found_by="vector",
            ),
            SearchResult(
                document_id="doc-2",
                title="문서2",
                text="벡터로 찾은 문서2",
                chunk_index=0,
                source_type="manual",
                vector_score=0.8,
                found_by="vector",
            ),
        ]

        keyword_results = [
            SearchResult(
                document_id="doc-2",  # 중복
                title="문서2",
                text="키워드로 찾은 문서2",
                chunk_index=0,
                source_type="manual",
                keyword_score=0.7,
                found_by="keyword",
            ),
            SearchResult(
                document_id="doc-3",
                title="문서3",
                text="키워드로 찾은 문서3",
                chunk_index=0,
                source_type="manual",
                keyword_score=0.6,
                found_by="keyword",
            ),
        ]

        merged = search_service._rrf_merge(
            vector_results, keyword_results,
            vector_weight=0.7, keyword_weight=0.3
        )

        # 3개 문서 (doc-2 중복 제거)
        assert len(merged) == 3

        # doc-2는 둘 다에서 찾음
        doc2 = next(d for d in merged if d.document_id == "doc-2")
        assert doc2.found_by == "both"
        assert doc2.vector_score == 0.8
        assert doc2.keyword_score == 0.7

        # RRF 점수 설정 확인
        assert all(d.rrf_score > 0 for d in merged)
        assert all(d.final_score > 0 for d in merged)

    def test_rrf_merge_vector_only(self, search_service):
        """벡터 결과만 있을 때"""
        vector_results = [
            SearchResult(
                document_id="doc-1",
                title="문서1",
                text="벡터로 찾은 문서",
                chunk_index=0,
                source_type="manual",
                vector_score=0.9,
                found_by="vector",
            ),
        ]

        merged = search_service._rrf_merge(vector_results, [])

        assert len(merged) == 1
        assert merged[0].found_by == "vector"

    def test_rrf_merge_keyword_only(self, search_service):
        """키워드 결과만 있을 때"""
        keyword_results = [
            SearchResult(
                document_id="doc-1",
                title="문서1",
                text="키워드로 찾은 문서",
                chunk_index=0,
                source_type="manual",
                keyword_score=0.8,
                found_by="keyword",
            ),
        ]

        merged = search_service._rrf_merge([], keyword_results)

        assert len(merged) == 1
        assert merged[0].found_by == "keyword"


class TestHybridSearchService:
    """HybridSearchService 통합 테스트"""

    @pytest.fixture
    def mock_embedding_provider(self):
        """Mock 임베딩 프로바이더"""
        provider = MagicMock()
        provider.embed_query = AsyncMock(return_value=[0.1] * 384)
        return provider

    @pytest.fixture
    def search_service(self, mock_embedding_provider):
        return HybridSearchService(
            embedding_provider=mock_embedding_provider,
            reranker=CohereReranker(api_key=None),  # API 키 없음
        )

    @pytest.mark.asyncio
    async def test_search_vector_only(self, search_service):
        """벡터만 검색"""
        tenant_id = uuid4()

        with patch.object(
            search_service, '_vector_search',
            new_callable=AsyncMock
        ) as mock_vector:
            mock_vector.return_value = [
                SearchResult(
                    document_id="doc-1",
                    title="문서1",
                    text="벡터 검색 결과",
                    chunk_index=0,
                    source_type="manual",
                    vector_score=0.9,
                    found_by="vector",
                )
            ]

            response = await search_service.search(
                tenant_id=tenant_id,
                query="테스트 쿼리",
                strategy=SearchStrategy.VECTOR_ONLY,
                top_k=5,
            )

            assert response.success
            assert response.strategy == SearchStrategy.VECTOR_ONLY
            assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_search_keyword_only(self, search_service):
        """키워드만 검색"""
        tenant_id = uuid4()

        with patch.object(
            search_service, '_keyword_search',
            new_callable=AsyncMock
        ) as mock_keyword:
            mock_keyword.return_value = [
                SearchResult(
                    document_id="doc-1",
                    title="문서1",
                    text="키워드 검색 결과",
                    chunk_index=0,
                    source_type="manual",
                    keyword_score=0.8,
                    found_by="keyword",
                )
            ]

            response = await search_service.search(
                tenant_id=tenant_id,
                query="테스트 쿼리",
                strategy=SearchStrategy.KEYWORD_ONLY,
                top_k=5,
            )

            assert response.success
            assert response.strategy == SearchStrategy.KEYWORD_ONLY
            assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_search_hybrid(self, search_service):
        """하이브리드 검색"""
        tenant_id = uuid4()

        with patch.object(
            search_service, '_vector_search',
            new_callable=AsyncMock
        ) as mock_vector, patch.object(
            search_service, '_keyword_search',
            new_callable=AsyncMock
        ) as mock_keyword:
            mock_vector.return_value = [
                SearchResult(
                    document_id="doc-1",
                    title="문서1",
                    text="벡터 검색 결과",
                    chunk_index=0,
                    source_type="manual",
                    vector_score=0.9,
                    found_by="vector",
                ),
                SearchResult(
                    document_id="doc-2",
                    title="문서2",
                    text="벡터 검색 결과2",
                    chunk_index=0,
                    source_type="manual",
                    vector_score=0.8,
                    found_by="vector",
                ),
            ]

            mock_keyword.return_value = [
                SearchResult(
                    document_id="doc-2",
                    title="문서2",
                    text="키워드 검색 결과",
                    chunk_index=0,
                    source_type="manual",
                    keyword_score=0.85,
                    found_by="keyword",
                ),
                SearchResult(
                    document_id="doc-3",
                    title="문서3",
                    text="키워드 검색 결과2",
                    chunk_index=0,
                    source_type="manual",
                    keyword_score=0.7,
                    found_by="keyword",
                ),
            ]

            response = await search_service.search(
                tenant_id=tenant_id,
                query="테스트 쿼리",
                strategy=SearchStrategy.HYBRID,
                top_k=5,
            )

            assert response.success
            assert response.strategy == SearchStrategy.HYBRID
            assert len(response.results) == 3  # 3개 문서 (중복 제거)

            # RRF 메타데이터 확인
            assert response.metadata is not None
            assert "rrf_k" in response.metadata

    @pytest.mark.asyncio
    async def test_search_hybrid_rerank(self, search_service):
        """하이브리드 + Rerank 검색"""
        tenant_id = uuid4()

        with patch.object(
            search_service, '_vector_search',
            new_callable=AsyncMock
        ) as mock_vector, patch.object(
            search_service, '_keyword_search',
            new_callable=AsyncMock
        ) as mock_keyword:
            mock_vector.return_value = [
                SearchResult(
                    document_id="doc-1",
                    title="문서1",
                    text="벡터 검색 결과",
                    chunk_index=0,
                    source_type="manual",
                    vector_score=0.9,
                    found_by="vector",
                ),
            ]

            mock_keyword.return_value = [
                SearchResult(
                    document_id="doc-2",
                    title="문서2",
                    text="키워드 검색 결과",
                    chunk_index=0,
                    source_type="manual",
                    keyword_score=0.85,
                    found_by="keyword",
                ),
            ]

            response = await search_service.search(
                tenant_id=tenant_id,
                query="테스트 쿼리",
                strategy=SearchStrategy.HYBRID_RERANK,
                top_k=5,
            )

            assert response.success
            assert response.strategy == SearchStrategy.HYBRID_RERANK
            # Cohere API 키 없으므로 rerank 비활성화, 원본 반환
            assert len(response.results) == 2

    @pytest.mark.asyncio
    async def test_search_error_handling(self, search_service):
        """검색 오류 처리"""
        tenant_id = uuid4()

        with patch.object(
            search_service, '_vector_search',
            new_callable=AsyncMock
        ) as mock_vector:
            mock_vector.side_effect = Exception("DB 연결 오류")

            response = await search_service.search(
                tenant_id=tenant_id,
                query="테스트 쿼리",
                strategy=SearchStrategy.HYBRID,
                top_k=5,
            )

            assert not response.success
            assert response.error is not None
            assert "DB 연결 오류" in response.error


class TestSearchStrategy:
    """SearchStrategy 열거형 테스트"""

    def test_strategy_values(self):
        """검색 전략 값 확인"""
        assert SearchStrategy.VECTOR_ONLY.value == "vector_only"
        assert SearchStrategy.KEYWORD_ONLY.value == "keyword_only"
        assert SearchStrategy.HYBRID.value == "hybrid"
        assert SearchStrategy.HYBRID_RERANK.value == "hybrid_rerank"

    def test_strategy_comparison(self):
        """전략 비교"""
        assert SearchStrategy.HYBRID == SearchStrategy.HYBRID
        assert SearchStrategy.HYBRID != SearchStrategy.VECTOR_ONLY
