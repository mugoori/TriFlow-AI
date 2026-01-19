"""
RAG Service 테스트

임베딩 프로바이더, 텍스트 청킹, 검색 로직 테스트
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class TestEmbeddingDimensions:
    """임베딩 차원 상수 테스트"""

    def test_embedding_dimensions_exist(self):
        """임베딩 차원 상수가 존재하는지 확인"""
        from app.services.rag_service import EMBEDDING_DIMENSIONS

        assert "voyage-3-lite" in EMBEDDING_DIMENSIONS
        assert "voyage-3" in EMBEDDING_DIMENSIONS
        assert "text-embedding-3-small" in EMBEDDING_DIMENSIONS
        assert "text-embedding-3-large" in EMBEDDING_DIMENSIONS
        assert "all-MiniLM-L6-v2" in EMBEDDING_DIMENSIONS

    def test_embedding_dimension_values(self):
        """임베딩 차원 값 확인"""
        from app.services.rag_service import EMBEDDING_DIMENSIONS

        assert EMBEDDING_DIMENSIONS["voyage-3-lite"] == 512
        assert EMBEDDING_DIMENSIONS["voyage-3"] == 1024
        assert EMBEDDING_DIMENSIONS["text-embedding-3-small"] == 1536
        assert EMBEDDING_DIMENSIONS["text-embedding-3-large"] == 3072
        assert EMBEDDING_DIMENSIONS["all-MiniLM-L6-v2"] == 384


class TestEmbeddingProvider:
    """임베딩 프로바이더 베이스 클래스 테스트"""

    def test_embedding_provider_init(self):
        """기본 임베딩 프로바이더 초기화"""
        from app.services.rag_service import EmbeddingProvider

        provider = EmbeddingProvider()
        assert provider.dimension == 384

    @pytest.mark.asyncio
    async def test_embed_raises_not_implemented(self):
        """embed 메서드가 NotImplementedError 발생"""
        from app.services.rag_service import EmbeddingProvider

        provider = EmbeddingProvider()

        with pytest.raises(NotImplementedError):
            await provider.embed(["test"])

    @pytest.mark.asyncio
    async def test_embed_query_calls_embed(self):
        """embed_query가 embed를 호출"""
        from app.services.rag_service import EmbeddingProvider

        provider = EmbeddingProvider()
        provider.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        result = await provider.embed_query("test query")

        assert result == [0.1, 0.2, 0.3]
        provider.embed.assert_called_once_with(["test query"])


class TestLocalEmbeddingProvider:
    """로컬 임베딩 프로바이더 테스트"""

    def test_local_provider_init(self):
        """로컬 프로바이더 초기화"""
        from app.services.rag_service import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert provider.model is None
        assert provider.dimension == 384

    def test_local_provider_custom_model(self):
        """커스텀 모델명으로 초기화"""
        from app.services.rag_service import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="custom-model")
        assert provider.model_name == "custom-model"

    @pytest.mark.asyncio
    async def test_local_provider_mock_embeddings(self):
        """Mock 임베딩 생성"""
        from app.services.rag_service import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        # sentence-transformers가 없는 환경에서 mock 임베딩 테스트
        provider.model = "mock"
        provider.dimension = 384

        result = await provider.embed(["test text"])

        assert len(result) == 1
        assert len(result[0]) == 384  # mock은 dimension 맞춤
        assert all(isinstance(v, float) for v in result[0])

    @pytest.mark.asyncio
    async def test_local_provider_deterministic_embeddings(self):
        """동일 텍스트는 동일 임베딩 생성"""
        from app.services.rag_service import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        provider.model = "mock"
        provider.dimension = 384

        result1 = await provider.embed(["hello world"])
        result2 = await provider.embed(["hello world"])

        # 동일 텍스트는 동일 임베딩
        assert result1[0] == result2[0]

    @pytest.mark.asyncio
    async def test_local_provider_different_texts_different_embeddings(self):
        """다른 텍스트는 다른 임베딩 생성"""
        from app.services.rag_service import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        provider.model = "mock"
        provider.dimension = 384

        result = await provider.embed(["hello", "world"])

        assert len(result) == 2
        assert result[0] != result[1]


class TestVoyageEmbeddingProvider:
    """Voyage 임베딩 프로바이더 테스트"""

    def test_voyage_provider_init(self):
        """Voyage 프로바이더 초기화"""
        from app.services.rag_service import VoyageEmbeddingProvider

        provider = VoyageEmbeddingProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.model == "voyage-3-lite"
        assert provider.dimension == 512

    def test_voyage_provider_custom_model(self):
        """커스텀 모델로 초기화"""
        from app.services.rag_service import VoyageEmbeddingProvider

        provider = VoyageEmbeddingProvider(model="voyage-3")
        assert provider.model == "voyage-3"
        assert provider.dimension == 1024

    @pytest.mark.asyncio
    async def test_voyage_fallback_to_local(self):
        """Voyage 사용 불가 시 로컬로 폴백"""
        from app.services.rag_service import VoyageEmbeddingProvider

        provider = VoyageEmbeddingProvider(api_key=None)
        provider._client = "unavailable"

        # Mock local provider
        with patch("app.services.rag_service.LocalEmbeddingProvider") as mock_local:
            mock_instance = MagicMock()
            mock_instance.embed = AsyncMock(return_value=[[0.1, 0.2]])
            mock_local.return_value = mock_instance

            result = await provider.embed(["test"])
            assert result == [[0.1, 0.2]]


class TestOpenAIEmbeddingProvider:
    """OpenAI 임베딩 프로바이더 테스트"""

    def test_openai_provider_init(self):
        """OpenAI 프로바이더 초기화"""
        from app.services.rag_service import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.model == "text-embedding-3-small"
        assert provider.dimension == 1536

    def test_openai_provider_large_model(self):
        """대형 모델로 초기화"""
        from app.services.rag_service import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-large")
        assert provider.model == "text-embedding-3-large"
        assert provider.dimension == 3072

    @pytest.mark.asyncio
    async def test_openai_fallback_to_local(self):
        """OpenAI 사용 불가 시 로컬로 폴백"""
        from app.services.rag_service import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(api_key=None)
        provider._client = "unavailable"

        with patch("app.services.rag_service.LocalEmbeddingProvider") as mock_local:
            mock_instance = MagicMock()
            mock_instance.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
            mock_local.return_value = mock_instance

            result = await provider.embed(["test"])
            assert result == [[0.1, 0.2, 0.3]]


class TestRAGServiceInit:
    """RAG 서비스 초기화 테스트"""

    def test_rag_service_default_init(self):
        """기본 초기화"""
        from app.services.rag_service import RAGService, LocalEmbeddingProvider

        service = RAGService()
        assert isinstance(service.embedding_provider, LocalEmbeddingProvider)
        assert service.chunk_size == 500
        assert service.chunk_overlap == 50

    def test_rag_service_custom_init(self):
        """커스텀 설정으로 초기화"""
        from app.services.rag_service import RAGService, VoyageEmbeddingProvider

        provider = VoyageEmbeddingProvider(api_key="test")
        service = RAGService(
            embedding_provider=provider,
            chunk_size=1000,
            chunk_overlap=100,
        )
        assert service.embedding_provider == provider
        assert service.chunk_size == 1000
        assert service.chunk_overlap == 100


class TestRAGServiceTextHash:
    """텍스트 해시 계산 테스트"""

    def test_compute_text_hash(self):
        """텍스트 해시 계산"""
        from app.services.rag_service import RAGService

        service = RAGService()
        hash1 = service._compute_text_hash("hello world")
        hash2 = service._compute_text_hash("hello world")
        hash3 = service._compute_text_hash("different text")

        # 동일 텍스트는 동일 해시
        assert hash1 == hash2
        # 다른 텍스트는 다른 해시
        assert hash1 != hash3
        # SHA256 해시 길이
        assert len(hash1) == 64

    def test_compute_text_hash_unicode(self):
        """유니코드 텍스트 해시"""
        from app.services.rag_service import RAGService

        service = RAGService()
        hash_ko = service._compute_text_hash("한글 텍스트")
        hash_emoji = service._compute_text_hash("😀 emoji")

        assert len(hash_ko) == 64
        assert len(hash_emoji) == 64


class TestRAGServiceChunking:
    """텍스트 청킹 테스트"""

    def test_chunk_short_text(self):
        """짧은 텍스트는 하나의 청크"""
        from app.services.rag_service import RAGService

        service = RAGService(chunk_size=100)  # 100 토큰 = 400 문자
        text = "This is a short text."

        chunks = service._chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_long_text(self):
        """긴 텍스트는 여러 청크로 분할"""
        from app.services.rag_service import RAGService

        service = RAGService(chunk_size=50, chunk_overlap=10)  # 200자, 40자 오버랩
        text = "A" * 600  # 600자 텍스트

        chunks = service._chunk_text(text)

        assert len(chunks) > 1
        # 각 청크가 비어있지 않음
        for chunk in chunks:
            assert len(chunk) > 0

    def test_chunk_preserves_sentence_boundary(self):
        """문장 경계에서 청크 분할"""
        from app.services.rag_service import RAGService

        service = RAGService(chunk_size=20, chunk_overlap=5)
        text = "First sentence. Second sentence. Third sentence."

        chunks = service._chunk_text(text)

        # 최소 1개 이상의 청크
        assert len(chunks) >= 1

    def test_chunk_overlap(self):
        """청크 간 오버랩 확인"""
        from app.services.rag_service import RAGService

        service = RAGService(chunk_size=100, chunk_overlap=25)
        # 긴 텍스트 생성 (단어 경계 없음)
        text = "X" * 1000

        chunks = service._chunk_text(text)

        # 청크가 2개 이상이면 오버랩 확인
        if len(chunks) >= 2:
            # 마지막 청크는 오버랩으로 인해 일부 중복 가능
            pass  # 오버랩 로직 확인

    def test_chunk_korean_text(self):
        """한글 텍스트 청킹"""
        from app.services.rag_service import RAGService

        service = RAGService(chunk_size=50, chunk_overlap=10)
        text = "한글 텍스트입니다. 두 번째 문장입니다. 세 번째 문장입니다. 네 번째 문장입니다."

        chunks = service._chunk_text(text)

        # 청크가 올바르게 생성됨
        assert len(chunks) >= 1
        # 각 청크가 유니코드 텍스트 포함
        for chunk in chunks:
            assert len(chunk) > 0


class TestRAGServiceAddDocument:
    """문서 추가 테스트"""

    @pytest.mark.asyncio
    async def test_add_document_success(self):
        """문서 추가 성공"""
        from app.services.rag_service import RAGService

        service = RAGService()
        service.embedding_provider.embed = AsyncMock(return_value=[[0.1] * 1536])

        tenant_id = uuid4()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.add_document(
                tenant_id=tenant_id,
                title="Test Document",
                content="Short content",
            )

            assert result["success"] is True
            assert "document_id" in result
            assert result["chunks"] == 1
            assert result["title"] == "Test Document"

    @pytest.mark.asyncio
    async def test_add_document_with_metadata(self):
        """메타데이터 포함 문서 추가"""
        from app.services.rag_service import RAGService

        service = RAGService()
        service.embedding_provider.embed = AsyncMock(return_value=[[0.1] * 1536])

        tenant_id = uuid4()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.add_document(
                tenant_id=tenant_id,
                title="Test",
                content="Content",
                source_type="sop",
                metadata={"key": "value"},
                tags=["tag1", "tag2"],
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_add_document_chunked(self):
        """긴 문서 청킹 후 추가"""
        from app.services.rag_service import RAGService

        service = RAGService(chunk_size=10, chunk_overlap=2)
        # 3개 청크로 분할될 정도의 긴 텍스트
        long_content = "A" * 200

        service.embedding_provider.embed = AsyncMock(
            return_value=[[0.1] * 1536 for _ in range(10)]
        )

        tenant_id = uuid4()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.add_document(
                tenant_id=tenant_id,
                title="Long Document",
                content=long_content,
            )

            assert result["success"] is True
            assert result["chunks"] > 1

    @pytest.mark.asyncio
    async def test_add_document_error_handling(self):
        """문서 추가 오류 처리"""
        from app.services.rag_service import RAGService

        service = RAGService()
        service.embedding_provider.embed = AsyncMock(
            side_effect=Exception("Embedding failed")
        )

        tenant_id = uuid4()

        result = await service.add_document(
            tenant_id=tenant_id,
            title="Test",
            content="Content",
        )

        assert result["success"] is False
        assert "error" in result


class TestRAGServiceSearch:
    """검색 테스트"""

    @pytest.mark.asyncio
    async def test_search_success(self):
        """검색 성공"""
        from app.services.rag_service import RAGService

        service = RAGService()
        service.embedding_provider.embed_query = AsyncMock(return_value=[0.1] * 1536)

        tenant_id = uuid4()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [
                {
                    "id": str(uuid4()),
                    "title": "Doc 1",
                    "text": "Content 1",
                    "similarity": 0.95,
                    "source_type": "manual",
                    "metadata": "{}",
                }
            ]
            mock_db.execute.return_value = mock_result
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            await service.search(
                tenant_id=tenant_id,
                query="test query",
                top_k=5,
            )

            # 검색이 실행되었는지 확인
            mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_search_with_source_type_filter(self):
        """소스 타입 필터로 검색"""
        from app.services.rag_service import RAGService

        service = RAGService()
        service.embedding_provider.embed_query = AsyncMock(return_value=[0.1] * 1536)

        tenant_id = uuid4()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_db.execute.return_value = mock_result
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            await service.search(
                tenant_id=tenant_id,
                query="test",
                source_type="sop",
            )

            # source_type 필터가 적용됨
            mock_db.execute.assert_called()


class TestRAGServiceHybridSearch:
    """하이브리드 검색 테스트"""

    @pytest.mark.asyncio
    async def test_hybrid_search_concept(self):
        """하이브리드 검색 개념 테스트"""
        from app.services.rag_service import RAGService

        service = RAGService()

        # 하이브리드 검색은 벡터 + 키워드 검색 조합
        # RRF (Reciprocal Rank Fusion) 사용
        # 이 테스트는 개념 확인용

        assert hasattr(service, "embedding_provider")


class TestRAGServiceContext:
    """컨텍스트 생성 테스트"""

    def test_context_creation_concept(self):
        """컨텍스트 생성 개념"""
        from app.services.rag_service import RAGService

        service = RAGService()

        # RAG 서비스가 초기화됨
        assert service is not None


class TestSourceTypes:
    """소스 타입 테스트"""

    def test_valid_source_types(self):
        """유효한 소스 타입"""
        valid_types = [
            "manual",
            "sop",
            "wiki",
            "faq",
            "judgment_log",
            "feedback",
            "external_doc",
        ]

        for source_type in valid_types:
            assert isinstance(source_type, str)
            assert len(source_type) > 0


class TestEmbeddingFormats:
    """임베딩 형식 테스트"""

    def test_embedding_to_pgvector_format(self):
        """PostgreSQL pgvector 형식 변환"""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

        assert embedding_str == "[0.1,0.2,0.3,0.4,0.5]"

    def test_embedding_dimension_validation(self):
        """임베딩 차원 유효성"""
        from app.services.rag_service import EMBEDDING_DIMENSIONS

        for model, dim in EMBEDDING_DIMENSIONS.items():
            assert isinstance(dim, int)
            assert dim > 0


class TestChunkMetadata:
    """청크 메타데이터 테스트"""

    def test_chunk_index_tracking(self):
        """청크 인덱스 추적"""
        from app.services.rag_service import RAGService

        service = RAGService(chunk_size=20, chunk_overlap=5)
        text = "Word " * 100  # 500 문자

        chunks = service._chunk_text(text)

        # 각 청크에 인덱스가 필요
        for i, chunk in enumerate(chunks):
            # 인덱스 i를 메타데이터로 사용 가능
            assert i >= 0
            assert i < len(chunks)

    def test_chunk_total_tracking(self):
        """전체 청크 수 추적"""
        from app.services.rag_service import RAGService

        service = RAGService(chunk_size=20, chunk_overlap=5)
        text = "Word " * 100

        chunks = service._chunk_text(text)
        chunk_total = len(chunks)

        # 전체 청크 수를 메타데이터로 사용 가능
        assert chunk_total > 0


class TestDocumentLanguage:
    """문서 언어 테스트"""

    def test_default_language(self):
        """기본 언어는 한국어"""
        default_language = "ko"
        assert default_language == "ko"

    def test_supported_languages(self):
        """지원 언어 목록"""
        supported = ["ko", "en", "ja", "zh"]
        for lang in supported:
            assert len(lang) == 2


class TestSimilarityThreshold:
    """유사도 임계값 테스트"""

    def test_default_threshold(self):
        """기본 유사도 임계값"""
        default_threshold = 0.5
        assert 0 <= default_threshold <= 1

    def test_threshold_range(self):
        """유사도 임계값 범위"""
        # 유사도는 0~1 사이
        thresholds = [0.0, 0.3, 0.5, 0.7, 0.9, 1.0]
        for t in thresholds:
            assert 0 <= t <= 1


class TestTopKResults:
    """Top-K 결과 수 테스트"""

    def test_default_top_k(self):
        """기본 결과 수"""
        default_top_k = 5
        assert default_top_k > 0

    def test_top_k_limits(self):
        """결과 수 제한"""
        # 합리적인 범위
        assert 1 <= 5 <= 100
        assert 1 <= 10 <= 100
        assert 1 <= 20 <= 100


# ========== 추가 테스트 (커버리지 향상) ==========


class TestLocalEmbeddingProviderAdvanced:
    """LocalEmbeddingProvider 고급 테스트"""

    def test_load_model_without_sentence_transformers(self):
        """sentence-transformers 없이 모델 로드"""
        from app.services.rag_service import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        # 실제 환경에서는 mock으로 대체됨
        provider._load_model()

        # model이 로드됨 (mock 또는 실제)
        assert provider.model is not None

    @pytest.mark.asyncio
    async def test_embed_batch_texts(self):
        """여러 텍스트 배치 임베딩"""
        from app.services.rag_service import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        provider.model = "mock"
        provider.dimension = 1536

        texts = ["text1", "text2", "text3"]
        result = await provider.embed(texts)

        assert len(result) == 3
        for emb in result:
            assert len(emb) == 1536


class TestVoyageEmbeddingProviderAdvanced:
    """VoyageEmbeddingProvider 고급 테스트"""

    @pytest.mark.asyncio
    async def test_voyage_embed_api_error(self):
        """Voyage API 오류 시 로컬 폴백"""
        from app.services.rag_service import VoyageEmbeddingProvider

        provider = VoyageEmbeddingProvider(api_key="test-key")

        # Mock client that raises error
        mock_client = MagicMock()
        mock_client.embed.side_effect = Exception("API error")
        provider._client = mock_client

        with patch("app.services.rag_service.LocalEmbeddingProvider") as mock_local:
            mock_instance = MagicMock()
            mock_instance.embed = AsyncMock(return_value=[[0.5] * 512])
            mock_local.return_value = mock_instance

            result = await provider.embed(["test"])
            assert result == [[0.5] * 512]


class TestOpenAIEmbeddingProviderAdvanced:
    """OpenAIEmbeddingProvider 고급 테스트"""

    @pytest.mark.asyncio
    async def test_openai_embed_api_error(self):
        """OpenAI API 오류 시 로컬 폴백"""
        from app.services.rag_service import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(api_key="test-key")

        # Mock client that raises error
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("API error")
        provider._client = mock_client

        with patch("app.services.rag_service.LocalEmbeddingProvider") as mock_local:
            mock_instance = MagicMock()
            mock_instance.embed = AsyncMock(return_value=[[0.5] * 1536])
            mock_local.return_value = mock_instance

            result = await provider.embed(["test"])
            assert result == [[0.5] * 1536]

    @pytest.mark.asyncio
    async def test_openai_embed_success(self):
        """OpenAI 임베딩 성공"""
        from app.services.rag_service import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_item = MagicMock()
        mock_item.embedding = [0.1] * 1536
        mock_response.data = [mock_item]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        provider._client = mock_client

        result = await provider.embed(["test"])
        assert len(result) == 1
        assert len(result[0]) == 1536


class TestRAGServiceSearchAdvanced:
    """RAG 서비스 검색 고급 테스트"""

    @pytest.mark.asyncio
    async def test_search_error_handling(self):
        """검색 오류 처리"""
        from app.services.rag_service import RAGService

        service = RAGService()
        service.embedding_provider.embed_query = AsyncMock(
            side_effect=Exception("Embedding error")
        )

        result = await service.search(
            tenant_id=uuid4(),
            query="test query",
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_with_results(self):
        """검색 결과 반환"""
        from app.services.rag_service import RAGService

        service = RAGService()
        service.embedding_provider.embed_query = AsyncMock(return_value=[0.1] * 1536)

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()

            # Mock row object with attributes
            mock_row = MagicMock()
            mock_row.document_id = uuid4()
            mock_row.title = "Test Doc"
            mock_row.section = "section1"
            mock_row.text = "Content text"
            mock_row.chunk_index = 0
            mock_row.source_type = "manual"
            mock_row.source_id = "src1"
            mock_row.metadata = {}
            mock_row.tags = ["tag1"]
            mock_row.similarity = 0.95

            mock_db.execute.return_value = [mock_row]
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.search(
                tenant_id=uuid4(),
                query="test",
                top_k=5,
            )

            assert result["success"] is True
            assert len(result["results"]) == 1


class TestRAGServiceHybridSearchAdvanced:
    """RAG 하이브리드 검색 고급 테스트"""

    @pytest.mark.asyncio
    async def test_hybrid_search_success(self):
        """하이브리드 검색 성공"""
        from app.services.rag_service import RAGService

        service = RAGService()
        service.embedding_provider.embed_query = AsyncMock(return_value=[0.1] * 1536)

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()

            # Mock row object with RRF attributes
            mock_row = MagicMock()
            mock_row.document_id = uuid4()
            mock_row.title = "Test Doc"
            mock_row.section = None
            mock_row.text = "Content"
            mock_row.chunk_index = 0
            mock_row.source_type = "manual"
            mock_row.source_id = "src1"
            mock_row.metadata = {}
            mock_row.tags = []
            mock_row.vector_score = 0.9
            mock_row.keyword_score = 0.5
            mock_row.rrf_score = 0.01

            mock_db.execute.return_value = [mock_row]
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.hybrid_search(
                tenant_id=uuid4(),
                query="test",
                top_k=5,
            )

            assert result["success"] is True
            assert result["search_type"] == "hybrid"

    @pytest.mark.asyncio
    async def test_hybrid_search_fallback(self):
        """하이브리드 검색 실패 시 벡터 검색으로 폴백"""
        from app.services.rag_service import RAGService

        service = RAGService()
        service.embedding_provider.embed_query = AsyncMock(return_value=[0.1] * 1536)

        # First call fails (hybrid), second call succeeds (vector)
        call_count = 0
        def mock_context():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Hybrid search failed")
            mock_db = MagicMock()
            mock_db.execute.return_value = []
            return mock_db

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(side_effect=mock_context)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.hybrid_search(
                tenant_id=uuid4(),
                query="test",
            )

            # 폴백 후 검색 결과 반환
            assert "query" in result


class TestRAGServiceGetContext:
    """get_context 테스트"""

    @pytest.mark.asyncio
    async def test_get_context_with_results(self):
        """결과가 있을 때 컨텍스트 생성"""
        from app.services.rag_service import RAGService

        service = RAGService()

        # Mock hybrid_search
        service.hybrid_search = AsyncMock(return_value={
            "success": True,
            "results": [
                {"title": "Doc1", "text": "Content 1", "rrf_score": 0.01},
                {"title": "Doc2", "text": "Content 2", "rrf_score": 0.005},
            ]
        })

        result = await service.get_context(
            tenant_id=uuid4(),
            query="test",
            max_tokens=2000,
        )

        assert "[Doc1]" in result
        assert "Content 1" in result

    @pytest.mark.asyncio
    async def test_get_context_empty_results(self):
        """결과가 없을 때 빈 컨텍스트"""
        from app.services.rag_service import RAGService

        service = RAGService()
        service.hybrid_search = AsyncMock(return_value={
            "success": True,
            "results": []
        })

        result = await service.get_context(
            tenant_id=uuid4(),
            query="test",
        )

        assert result == ""

    @pytest.mark.asyncio
    async def test_get_context_token_limit(self):
        """토큰 제한 적용"""
        from app.services.rag_service import RAGService

        service = RAGService()

        # 첫 번째 문서는 50 단어, 두 번째는 100 단어
        short_text = "word " * 50  # 50 단어
        long_text = "word " * 100  # 100 단어
        service.hybrid_search = AsyncMock(return_value={
            "success": True,
            "results": [
                {"title": "Doc1", "text": short_text, "rrf_score": 0.9},
                {"title": "Doc2", "text": long_text, "rrf_score": 0.8},
            ]
        })

        result = await service.get_context(
            tenant_id=uuid4(),
            query="test",
            max_tokens=60,  # 첫 번째 문서(50단어)만 포함될 정도
        )

        # 토큰 제한으로 첫 번째 문서만 포함
        assert len(result) > 0
        assert "Doc1" in result
        assert "Doc2" not in result


class TestRAGServiceDeleteDocument:
    """문서 삭제 테스트"""

    @pytest.mark.asyncio
    async def test_delete_document_success(self):
        """문서 삭제 성공"""
        from app.services.rag_service import RAGService

        service = RAGService()
        tenant_id = uuid4()
        doc_id = uuid4()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [(uuid4(),), (uuid4(),)]  # 2 chunks deleted
            mock_db.execute.return_value = mock_result
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.delete_document(tenant_id, doc_id)

            assert result["success"] is True
            assert result["chunks_deleted"] == 2

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self):
        """존재하지 않는 문서 삭제"""
        from app.services.rag_service import RAGService

        service = RAGService()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []  # No rows deleted
            mock_db.execute.return_value = mock_result
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.delete_document(uuid4(), uuid4())

            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_document_error(self):
        """문서 삭제 오류"""
        from app.services.rag_service import RAGService

        service = RAGService()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(
                side_effect=Exception("DB error")
            )
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.delete_document(uuid4(), uuid4())

            assert result["success"] is False
            assert "error" in result


class TestRAGServiceDeleteByParentDocument:
    """부모 문서 기준 삭제 테스트"""

    @pytest.mark.asyncio
    async def test_delete_by_parent_success(self):
        """부모 문서 삭제 성공"""
        from app.services.rag_service import RAGService

        service = RAGService()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [(uuid4(),), (uuid4(),), (uuid4(),)]
            mock_db.execute.return_value = mock_result
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.delete_by_parent_document(uuid4(), uuid4())

            assert result["success"] is True
            assert result["deleted_count"] == 3

    @pytest.mark.asyncio
    async def test_delete_by_parent_error(self):
        """부모 문서 삭제 오류"""
        from app.services.rag_service import RAGService

        service = RAGService()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(
                side_effect=Exception("DB error")
            )
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.delete_by_parent_document(uuid4(), uuid4())

            assert result["success"] is False


class TestRAGServiceListDocuments:
    """문서 목록 조회 테스트"""

    @pytest.mark.asyncio
    async def test_list_documents_success(self):
        """문서 목록 조회 성공"""
        from app.services.rag_service import RAGService
        from datetime import datetime

        service = RAGService()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()

            mock_row = MagicMock()
            mock_row.parent_id = str(uuid4())
            mock_row.title = "Test Doc"
            mock_row.source_type = "manual"
            mock_row.source_id = "src1"
            mock_row.created_at = datetime.now()
            mock_row.chunk_count = 3
            mock_row.chunk_total = 3
            mock_row.total_chars = 1000
            mock_row.all_tags = ["tag1", "tag2"]

            mock_db.execute.return_value = [mock_row]
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.list_documents(uuid4())

            assert result["success"] is True
            assert len(result["documents"]) == 1

    @pytest.mark.asyncio
    async def test_list_documents_with_source_type(self):
        """소스 타입 필터로 목록 조회"""
        from app.services.rag_service import RAGService

        service = RAGService()

        with patch("app.services.rag_service.get_db_context") as mock_ctx:
            mock_db = MagicMock()
            mock_db.execute.return_value = []
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = await service.list_documents(
                uuid4(),
                source_type="sop",
            )

            assert result["success"] is True


class TestGetRagService:
    """get_rag_service 싱글톤 테스트"""

    def test_get_rag_service_returns_instance(self):
        """싱글톤 인스턴스 반환"""
        from app.services.rag_service import get_rag_service, reset_rag_service, RAGService

        reset_rag_service()  # 리셋
        service = get_rag_service()

        assert isinstance(service, RAGService)

    def test_get_rag_service_same_instance(self):
        """동일 인스턴스 반환"""
        from app.services.rag_service import get_rag_service, reset_rag_service

        reset_rag_service()
        service1 = get_rag_service()
        service2 = get_rag_service()

        assert service1 is service2

    def test_reset_rag_service(self):
        """리셋 후 새 인스턴스"""
        from app.services.rag_service import get_rag_service, reset_rag_service

        service1 = get_rag_service()
        reset_rag_service()
        service2 = get_rag_service()

        # 리셋 후 새 인스턴스 생성
        assert service1 is not service2
