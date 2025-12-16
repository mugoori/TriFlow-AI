"""
CRAG (Corrective RAG) 테스트
=============================
- 관련성 평가 테스트
- Query Rewrite 테스트
- CRAG 검색 흐름 테스트
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.search_service import (
    SearchStrategy,
    SearchResult,
    SearchResponse,
    RelevanceGrade,
    CRAGResult,
    HybridSearchService,
    CohereReranker,
)


class TestRelevanceGrade:
    """RelevanceGrade 열거형 테스트"""

    def test_grade_values(self):
        """등급 값 확인"""
        assert RelevanceGrade.RELEVANT.value == "relevant"
        assert RelevanceGrade.AMBIGUOUS.value == "ambiguous"
        assert RelevanceGrade.NOT_RELEVANT.value == "not_relevant"


class TestCRAGResult:
    """CRAGResult 데이터클래스 테스트"""

    def test_crag_result_creation(self):
        """CRAGResult 생성"""
        result = CRAGResult(
            results=[],
            relevance_grade=RelevanceGrade.RELEVANT,
            avg_relevance_score=0.85,
        )

        assert result.relevance_grade == RelevanceGrade.RELEVANT
        assert result.avg_relevance_score == 0.85
        assert result.was_corrected is False
        assert result.should_abstain is False

    def test_crag_result_with_correction(self):
        """Query Rewrite로 수정된 CRAGResult"""
        result = CRAGResult(
            results=[],
            relevance_grade=RelevanceGrade.AMBIGUOUS,
            avg_relevance_score=0.6,
            was_corrected=True,
            correction_method="query_rewrite",
            original_query="불량 원인",
            rewritten_query="불량 원인 결함 품질 이상 defect",
            search_attempts=2,
        )

        assert result.was_corrected is True
        assert result.correction_method == "query_rewrite"
        assert result.search_attempts == 2

    def test_crag_result_abstain(self):
        """판단 보류 CRAGResult"""
        result = CRAGResult(
            results=[],
            relevance_grade=RelevanceGrade.NOT_RELEVANT,
            avg_relevance_score=0.3,
            should_abstain=True,
            abstain_reason="관련 문서를 찾지 못했습니다.",
        )

        assert result.should_abstain is True
        assert result.abstain_reason is not None

    def test_crag_result_to_dict(self):
        """CRAGResult.to_dict() 테스트"""
        result = CRAGResult(
            results=[
                SearchResult(
                    document_id="doc-1",
                    title="테스트",
                    text="내용",
                    chunk_index=0,
                    source_type="manual",
                )
            ],
            relevance_grade=RelevanceGrade.RELEVANT,
            avg_relevance_score=0.85,
            was_corrected=False,
            search_attempts=1,
            total_candidates=5,
        )

        d = result.to_dict()

        assert d["relevance_grade"] == "relevant"
        assert d["avg_relevance_score"] == 0.85
        assert d["was_corrected"] is False
        assert d["search_attempts"] == 1
        assert d["result_count"] == 1


class TestRelevanceEvaluation:
    """관련성 평가 테스트"""

    @pytest.fixture
    def search_service(self):
        return HybridSearchService(rrf_k=60)

    def test_evaluate_empty_results(self, search_service):
        """빈 결과 평가"""
        grade, score = search_service._evaluate_relevance([])

        assert grade == RelevanceGrade.NOT_RELEVANT
        assert score == 0.0

    def test_evaluate_high_relevance_rerank(self, search_service):
        """높은 관련성 (rerank 점수)"""
        results = [
            SearchResult(
                document_id="doc-1",
                title="문서1",
                text="내용",
                chunk_index=0,
                source_type="manual",
                rerank_score=0.95,
            ),
            SearchResult(
                document_id="doc-2",
                title="문서2",
                text="내용",
                chunk_index=0,
                source_type="manual",
                rerank_score=0.85,
            ),
        ]

        grade, score = search_service._evaluate_relevance(results)

        assert grade == RelevanceGrade.RELEVANT
        assert score >= 0.7

    def test_evaluate_low_relevance_vector(self, search_service):
        """낮은 관련성 (vector 점수)"""
        results = [
            SearchResult(
                document_id="doc-1",
                title="문서1",
                text="내용",
                chunk_index=0,
                source_type="manual",
                vector_score=0.3,
            ),
            SearchResult(
                document_id="doc-2",
                title="문서2",
                text="내용",
                chunk_index=0,
                source_type="manual",
                vector_score=0.25,
            ),
        ]

        grade, score = search_service._evaluate_relevance(results)

        assert grade == RelevanceGrade.NOT_RELEVANT
        assert score < 0.5

    def test_evaluate_ambiguous_relevance(self, search_service):
        """애매한 관련성"""
        results = [
            SearchResult(
                document_id="doc-1",
                title="문서1",
                text="내용",
                chunk_index=0,
                source_type="manual",
                vector_score=0.6,
            ),
            SearchResult(
                document_id="doc-2",
                title="문서2",
                text="내용",
                chunk_index=0,
                source_type="manual",
                vector_score=0.55,
            ),
        ]

        grade, score = search_service._evaluate_relevance(results)

        assert grade == RelevanceGrade.AMBIGUOUS
        assert 0.5 <= score < 0.7

    def test_evaluate_rrf_score_normalization(self, search_service):
        """RRF 점수 정규화"""
        results = [
            SearchResult(
                document_id="doc-1",
                title="문서1",
                text="내용",
                chunk_index=0,
                source_type="manual",
                rrf_score=0.025,  # 0.025 * 30 = 0.75
            ),
        ]

        grade, score = search_service._evaluate_relevance(results)

        # 0.75 * 0.5 + 0.75 * 0.5 = 0.75 -> RELEVANT
        assert grade == RelevanceGrade.RELEVANT


class TestQueryRewrite:
    """Query Rewrite 테스트"""

    @pytest.fixture
    def search_service(self):
        return HybridSearchService(rrf_k=60)

    @pytest.mark.asyncio
    async def test_rewrite_with_synonyms(self, search_service):
        """동의어 확장"""
        original = "불량 원인 분석"
        rewritten = await search_service._rewrite_query(original)

        # 불량 → 결함 품질 이상 defect
        # 원인 → 이유 reason cause 요인
        assert "결함" in rewritten or "defect" in rewritten
        assert "reason" in rewritten or "이유" in rewritten
        assert len(rewritten) > len(original)

    @pytest.mark.asyncio
    async def test_rewrite_production_terms(self, search_service):
        """생산 관련 용어 확장"""
        original = "생산량 추세"
        rewritten = await search_service._rewrite_query(original)

        assert "output" in rewritten or "산출량" in rewritten
        assert "트렌드" in rewritten or "trend" in rewritten

    @pytest.mark.asyncio
    async def test_rewrite_no_match(self, search_service):
        """매칭 키워드 없음"""
        original = "안녕하세요"
        rewritten = await search_service._rewrite_query(original)

        # 확장 없이 원본 반환
        assert rewritten == original

    @pytest.mark.asyncio
    async def test_rewrite_time_terms(self, search_service):
        """시간 관련 용어 확장"""
        original = "오늘 설비 상태"
        rewritten = await search_service._rewrite_query(original)

        assert "today" in rewritten or "당일" in rewritten
        assert "장비" in rewritten or "machine" in rewritten


class TestCorrectiveSearch:
    """CRAG Corrective Search 테스트"""

    @pytest.fixture
    def mock_embedding_provider(self):
        provider = MagicMock()
        provider.embed_query = AsyncMock(return_value=[0.1] * 384)
        return provider

    @pytest.fixture
    def search_service(self, mock_embedding_provider):
        return HybridSearchService(
            embedding_provider=mock_embedding_provider,
            reranker=CohereReranker(api_key=None),
        )

    @pytest.mark.asyncio
    async def test_corrective_search_high_relevance(self, search_service):
        """높은 관련성 → 즉시 반환"""
        tenant_id = uuid4()

        with patch.object(
            search_service, 'search',
            new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = SearchResponse(
                success=True,
                query="테스트",
                strategy=SearchStrategy.HYBRID_RERANK,
                results=[
                    SearchResult(
                        document_id="doc-1",
                        title="문서1",
                        text="관련 내용",
                        chunk_index=0,
                        source_type="manual",
                        rerank_score=0.9,
                        final_score=0.9,
                    ),
                ],
                count=1,
            )

            result = await search_service.corrective_search(
                tenant_id=tenant_id,
                query="테스트 쿼리",
                top_k=5,
            )

            assert result.relevance_grade == RelevanceGrade.RELEVANT
            assert result.was_corrected is False
            assert result.search_attempts == 1
            assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_corrective_search_low_relevance_retry(self, search_service):
        """낮은 관련성 → Query Rewrite 후 재시도"""
        tenant_id = uuid4()

        call_count = 0

        async def mock_search_impl(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # 첫 번째: 낮은 관련성
                return SearchResponse(
                    success=True,
                    query=kwargs.get("query", ""),
                    strategy=SearchStrategy.HYBRID_RERANK,
                    results=[
                        SearchResult(
                            document_id="doc-1",
                            title="문서1",
                            text="불량 관련 내용",
                            chunk_index=0,
                            source_type="manual",
                            vector_score=0.3,
                            final_score=0.3,
                        ),
                    ],
                    count=1,
                )
            else:
                # 두 번째: 높은 관련성 (쿼리 확장 후)
                return SearchResponse(
                    success=True,
                    query=kwargs.get("query", ""),
                    strategy=SearchStrategy.HYBRID_RERANK,
                    results=[
                        SearchResult(
                            document_id="doc-2",
                            title="문서2",
                            text="품질 결함 분석",
                            chunk_index=0,
                            source_type="manual",
                            rerank_score=0.85,
                            final_score=0.85,
                        ),
                    ],
                    count=1,
                )

        with patch.object(
            search_service, 'search',
            new_callable=AsyncMock
        ) as mock_search:
            mock_search.side_effect = mock_search_impl

            result = await search_service.corrective_search(
                tenant_id=tenant_id,
                query="불량 원인",  # 동의어 확장 가능
                top_k=5,
                max_attempts=2,
            )

            # 재시도 발생
            assert result.search_attempts == 2
            assert result.was_corrected is True
            assert result.correction_method == "query_rewrite"

    @pytest.mark.asyncio
    async def test_corrective_search_abstain(self, search_service):
        """낮은 관련성 지속 → 판단 보류"""
        tenant_id = uuid4()

        with patch.object(
            search_service, 'search',
            new_callable=AsyncMock
        ) as mock_search:
            # 항상 낮은 관련성 반환
            mock_search.return_value = SearchResponse(
                success=True,
                query="xyz123",
                strategy=SearchStrategy.HYBRID_RERANK,
                results=[
                    SearchResult(
                        document_id="doc-1",
                        title="문서1",
                        text="무관한 내용",
                        chunk_index=0,
                        source_type="manual",
                        vector_score=0.2,
                        final_score=0.2,
                    ),
                ],
                count=1,
            )

            result = await search_service.corrective_search(
                tenant_id=tenant_id,
                query="xyz123",  # 동의어 확장 불가
                top_k=5,
                max_attempts=2,
            )

            assert result.relevance_grade == RelevanceGrade.NOT_RELEVANT
            assert result.should_abstain is True
            assert result.abstain_reason is not None
            assert "관련성이 낮습니다" in result.abstain_reason

    @pytest.mark.asyncio
    async def test_corrective_search_failure(self, search_service):
        """검색 실패 처리"""
        tenant_id = uuid4()

        with patch.object(
            search_service, 'search',
            new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = SearchResponse(
                success=False,
                query="테스트",
                strategy=SearchStrategy.HYBRID_RERANK,
                results=[],
                count=0,
                error="DB 연결 실패",
            )

            result = await search_service.corrective_search(
                tenant_id=tenant_id,
                query="테스트",
                top_k=5,
            )

            assert result.should_abstain is True
            assert "검색 실패" in result.abstain_reason


class TestCRAGIntegration:
    """CRAG 통합 테스트"""

    @pytest.mark.asyncio
    async def test_crag_result_serialization(self):
        """CRAGResult 직렬화 테스트"""
        result = CRAGResult(
            results=[
                SearchResult(
                    document_id="doc-1",
                    title="테스트 문서",
                    text="테스트 내용입니다.",
                    chunk_index=0,
                    source_type="manual",
                    vector_score=0.8,
                    keyword_score=0.6,
                    rrf_score=0.02,
                    rerank_score=0.85,
                    final_score=0.85,
                    found_by="both+rerank",
                )
            ],
            relevance_grade=RelevanceGrade.RELEVANT,
            avg_relevance_score=0.85,
            was_corrected=False,
            search_attempts=1,
            total_candidates=10,
        )

        d = result.to_dict()

        # JSON 직렬화 가능한지 확인
        import json
        json_str = json.dumps(d, ensure_ascii=False)
        assert "relevant" in json_str
        assert "0.85" in json_str

    @pytest.mark.asyncio
    async def test_crag_empty_results_handling(self):
        """빈 결과 처리"""
        result = CRAGResult(
            results=[],
            relevance_grade=RelevanceGrade.NOT_RELEVANT,
            avg_relevance_score=0.0,
            should_abstain=True,
            abstain_reason="검색 결과가 없습니다.",
        )

        d = result.to_dict()

        assert d["result_count"] == 0
        assert d["should_abstain"] is True
