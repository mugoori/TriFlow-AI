"""
Story Service 테스트
story_service.py의 StoryService 클래스 테스트
"""
import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.bi_story import (
    StoryCreateRequest,
    StorySectionCreateRequest,
    StorySectionChart,
)


# ========== STORY_SYSTEM_PROMPT 테스트 ==========


class TestStorySystemPrompt:
    """시스템 프롬프트 테스트"""

    def test_prompt_import(self):
        """프롬프트 임포트 확인"""
        from app.services.story_service import STORY_SYSTEM_PROMPT
        assert isinstance(STORY_SYSTEM_PROMPT, str)
        assert len(STORY_SYSTEM_PROMPT) > 0

    def test_prompt_contains_sections(self):
        """프롬프트에 섹션 정의 포함"""
        from app.services.story_service import STORY_SYSTEM_PROMPT
        assert "Introduction" in STORY_SYSTEM_PROMPT
        assert "Analysis" in STORY_SYSTEM_PROMPT
        assert "Finding" in STORY_SYSTEM_PROMPT
        assert "Conclusion" in STORY_SYSTEM_PROMPT

    def test_prompt_contains_json_format(self):
        """프롬프트에 JSON 형식 포함"""
        from app.services.story_service import STORY_SYSTEM_PROMPT
        assert "json" in STORY_SYSTEM_PROMPT.lower()
        assert "sections" in STORY_SYSTEM_PROMPT


# ========== StoryService 초기화 테스트 ==========


class TestStoryServiceInit:
    """StoryService 초기화 테스트"""

    @patch("app.services.story_service.Anthropic")
    def test_service_init(self, mock_anthropic):
        """서비스 초기화"""
        from app.services.story_service import StoryService

        service = StoryService()

        assert service.client is not None
        assert service.model == "claude-sonnet-4-5-20250929"
        mock_anthropic.assert_called_once()


# ========== get_story_service 싱글톤 테스트 ==========


class TestGetStoryService:
    """싱글톤 패턴 테스트"""

    @patch("app.services.story_service.Anthropic")
    def test_get_story_service_singleton(self, mock_anthropic):
        """싱글톤 인스턴스 반환"""
        # Reset the singleton
        import app.services.story_service as module
        module._story_service = None

        from app.services.story_service import get_story_service

        service1 = get_story_service()
        service2 = get_story_service()

        # 동일 인스턴스여야 함
        assert service1 is service2


# ========== _parse_story_response 테스트 ==========


class TestParseStoryResponse:
    """_parse_story_response 메서드 테스트"""

    @patch("app.services.story_service.Anthropic")
    def test_parse_valid_json(self, mock_anthropic):
        """유효한 JSON 파싱"""
        from app.services.story_service import StoryService

        service = StoryService()

        content = '''Here is the story:
        {
            "sections": [
                {"section_type": "introduction", "title": "Intro", "narrative": "Hello"}
            ]
        }
        '''

        result = service._parse_story_response(content)

        assert "sections" in result
        assert len(result["sections"]) == 1
        assert result["sections"][0]["section_type"] == "introduction"

    @patch("app.services.story_service.Anthropic")
    def test_parse_json_with_markdown(self, mock_anthropic):
        """마크다운 블록 내 JSON 파싱"""
        from app.services.story_service import StoryService

        service = StoryService()

        content = '''```json
        {
            "sections": [
                {"section_type": "analysis", "title": "분석", "narrative": "데이터 분석"}
            ]
        }
        ```'''

        result = service._parse_story_response(content)

        assert "sections" in result
        assert result["sections"][0]["section_type"] == "analysis"

    @patch("app.services.story_service.Anthropic")
    def test_parse_no_json(self, mock_anthropic):
        """JSON 없는 경우 예외 발생"""
        from app.services.story_service import StoryService

        service = StoryService()

        content = "This is just plain text without any JSON"

        with pytest.raises(ValueError) as exc_info:
            service._parse_story_response(content)

        assert "No JSON found" in str(exc_info.value)

    @patch("app.services.story_service.Anthropic")
    def test_parse_invalid_json(self, mock_anthropic):
        """유효하지 않은 JSON 파싱 시 기본값 반환"""
        from app.services.story_service import StoryService

        service = StoryService()

        # JSON 구조가 있지만 불완전한 경우
        content = '{"sections": [{"section_type": "intro", "title": "Test"}]}'

        result = service._parse_story_response(content)

        # 파싱 가능하면 결과 반환
        assert "sections" in result


# ========== _build_story_prompt 테스트 ==========


class TestBuildStoryPrompt:
    """_build_story_prompt 메서드 테스트"""

    @patch("app.services.story_service.Anthropic")
    def test_build_prompt_with_focus_topic(self, mock_anthropic):
        """포커스 주제가 있는 프롬프트"""
        from app.services.story_service import StoryService

        service = StoryService()

        data_context = {
            "summary_data": [{"line_code": "L1", "total_readings": 100}],
            "time_range": "24h"
        }

        prompt = service._build_story_prompt(data_context, "불량률 분석")

        assert "불량률 분석" in prompt
        assert "L1" in prompt
        assert "24h" in prompt

    @patch("app.services.story_service.Anthropic")
    def test_build_prompt_without_focus_topic(self, mock_anthropic):
        """포커스 주제가 없는 프롬프트"""
        from app.services.story_service import StoryService

        service = StoryService()

        data_context = {
            "summary_data": [],
            "time_range": "7d"
        }

        prompt = service._build_story_prompt(data_context, None)

        assert "제조 현황 종합 분석" in prompt

    @patch("app.services.story_service.Anthropic")
    def test_build_prompt_truncates_data(self, mock_anthropic):
        """긴 데이터 절삭"""
        from app.services.story_service import StoryService

        service = StoryService()

        # 긴 데이터
        data_context = {
            "summary_data": [{"line_code": f"L{i}", "data": "x" * 100} for i in range(100)],
            "time_range": "24h"
        }

        prompt = service._build_story_prompt(data_context, "분석")

        # 5000자 제한
        assert len(prompt) < 10000


# ========== create_story 테스트 ==========


class TestCreateStory:
    """create_story 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_create_story_basic(self, mock_db_context, mock_anthropic):
        """기본 스토리 생성"""
        from app.services.story_service import StoryService

        # DB Mock
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        request = StoryCreateRequest(
            title="테스트 스토리",
            description="테스트 설명",
            auto_generate=False
        )

        tenant_id = uuid4()
        user_id = uuid4()

        result = await service.create_story(tenant_id, user_id, request)

        assert result.title == "테스트 스토리"
        assert result.description == "테스트 설명"
        assert result.tenant_id == tenant_id
        assert result.created_by == user_id
        assert result.is_public is False
        assert len(result.sections) == 0


# ========== get_stories 테스트 ==========


class TestGetStories:
    """get_stories 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_get_stories_empty(self, mock_db_context, mock_anthropic):
        """스토리 없을 때"""
        from app.services.story_service import StoryService

        # DB Mock
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.get_stories(uuid4())

        assert result == []

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_get_stories_with_data(self, mock_db_context, mock_anthropic):
        """스토리 조회"""
        from app.services.story_service import StoryService

        tenant_id = uuid4()
        story_id = uuid4()
        user_id = uuid4()
        now = datetime.utcnow()

        # DB Mock
        mock_db = MagicMock()

        # 스토리 목록 결과
        mock_story_row = MagicMock()
        mock_story_row.story_id = str(story_id)
        mock_story_row.tenant_id = str(tenant_id)
        mock_story_row.title = "테스트 스토리"
        mock_story_row.description = "설명"
        mock_story_row.is_public = False
        mock_story_row.created_by = str(user_id)
        mock_story_row.created_at = now
        mock_story_row.updated_at = now
        mock_story_row.published_at = None

        # 섹션 결과 (빈 배열)
        mock_section_result = MagicMock()
        mock_section_result.fetchall.return_value = []

        mock_story_result = MagicMock()
        mock_story_result.fetchall.return_value = [mock_story_row]

        # execute 호출에 따라 다른 결과 반환
        mock_db.execute.side_effect = [mock_story_result, mock_section_result]

        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.get_stories(tenant_id)

        assert len(result) == 1
        assert result[0].title == "테스트 스토리"


# ========== get_story 테스트 ==========


class TestGetStory:
    """get_story 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_get_story_not_found(self, mock_db_context, mock_anthropic):
        """스토리 없을 때"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.get_story(uuid4(), uuid4())

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_get_story_found(self, mock_db_context, mock_anthropic):
        """스토리 조회 성공"""
        from app.services.story_service import StoryService

        tenant_id = uuid4()
        story_id = uuid4()
        user_id = uuid4()
        now = datetime.utcnow()

        mock_db = MagicMock()

        # 스토리 결과
        mock_story_row = MagicMock()
        mock_story_row.story_id = str(story_id)
        mock_story_row.tenant_id = str(tenant_id)
        mock_story_row.title = "테스트 스토리"
        mock_story_row.description = "설명"
        mock_story_row.is_public = False
        mock_story_row.created_by = str(user_id)
        mock_story_row.created_at = now
        mock_story_row.updated_at = now
        mock_story_row.published_at = None

        mock_story_result = MagicMock()
        mock_story_result.fetchone.return_value = mock_story_row

        # 섹션 결과
        mock_section_result = MagicMock()
        mock_section_result.fetchall.return_value = []

        mock_db.execute.side_effect = [mock_story_result, mock_section_result]
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.get_story(tenant_id, story_id)

        assert result is not None
        assert result.title == "테스트 스토리"


# ========== update_story 테스트 ==========


class TestUpdateStory:
    """update_story 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_update_story_no_changes(self, mock_db_context, mock_anthropic):
        """변경 없는 경우"""
        from app.services.story_service import StoryService

        service = StoryService()

        result = await service.update_story(uuid4(), uuid4())

        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_update_story_title(self, mock_db_context, mock_anthropic):
        """제목 업데이트"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.update_story(
            uuid4(), uuid4(),
            title="새 제목"
        )

        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_update_story_all_fields(self, mock_db_context, mock_anthropic):
        """모든 필드 업데이트"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.update_story(
            uuid4(), uuid4(),
            title="새 제목",
            description="새 설명",
            is_public=True
        )

        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_update_story_not_found(self, mock_db_context, mock_anthropic):
        """스토리 없을 때"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.update_story(
            uuid4(), uuid4(),
            title="새 제목"
        )

        assert result is False


# ========== delete_story 테스트 ==========


class TestDeleteStory:
    """delete_story 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_delete_story_success(self, mock_db_context, mock_anthropic):
        """삭제 성공"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.delete_story(uuid4(), uuid4())

        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_delete_story_not_found(self, mock_db_context, mock_anthropic):
        """스토리 없을 때"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.delete_story(uuid4(), uuid4())

        assert result is False


# ========== add_section 테스트 ==========


class TestAddSection:
    """add_section 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_add_section_with_order(self, mock_db_context, mock_anthropic):
        """순서 지정하여 섹션 추가"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        request = StorySectionCreateRequest(
            section_type="analysis",
            title="분석 섹션",
            narrative="내용",
            order=0
        )

        result = await service.add_section(uuid4(), uuid4(), request)

        assert result.section_type == "analysis"
        assert result.title == "분석 섹션"
        assert result.order == 0
        assert result.ai_generated is False

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_add_section_auto_order(self, mock_db_context, mock_anthropic):
        """자동 순서로 섹션 추가"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()

        # 순서 조회 결과
        mock_order_row = MagicMock()
        mock_order_row.next_order = 3
        mock_order_result = MagicMock()
        mock_order_result.fetchone.return_value = mock_order_row

        mock_db.execute.return_value = mock_order_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        request = StorySectionCreateRequest(
            section_type="conclusion",
            title="결론",
            narrative="마무리",
            order=None  # 자동 순서
        )

        result = await service.add_section(uuid4(), uuid4(), request)

        assert result.order == 3

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_add_section_with_charts(self, mock_db_context, mock_anthropic):
        """차트와 함께 섹션 추가"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        chart = StorySectionChart(
            chart_config={"type": "bar", "data": []},
            caption="테스트 차트",
            order=0
        )

        request = StorySectionCreateRequest(
            section_type="analysis",
            title="분석",
            narrative="내용",
            order=0,
            charts=[chart]
        )

        result = await service.add_section(uuid4(), uuid4(), request)

        assert len(result.charts) == 1


# ========== delete_section 테스트 ==========


class TestDeleteSection:
    """delete_section 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_delete_section_success(self, mock_db_context, mock_anthropic):
        """섹션 삭제 성공"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()

        # 스토리 확인 결과
        mock_check_result = MagicMock()
        mock_check_result.fetchone.return_value = MagicMock()  # 스토리 존재

        # 삭제 결과
        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 1

        mock_db.execute.side_effect = [mock_check_result, mock_delete_result]
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.delete_section(uuid4(), uuid4(), uuid4())

        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_delete_section_story_not_found(self, mock_db_context, mock_anthropic):
        """스토리 없을 때"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()

        # 스토리 확인 결과
        mock_check_result = MagicMock()
        mock_check_result.fetchone.return_value = None  # 스토리 없음

        mock_db.execute.return_value = mock_check_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.delete_section(uuid4(), uuid4(), uuid4())

        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_delete_section_not_found(self, mock_db_context, mock_anthropic):
        """섹션 없을 때"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()

        # 스토리 확인 결과
        mock_check_result = MagicMock()
        mock_check_result.fetchone.return_value = MagicMock()

        # 삭제 결과
        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 0

        mock_db.execute.side_effect = [mock_check_result, mock_delete_result]
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service.delete_section(uuid4(), uuid4(), uuid4())

        assert result is False


# ========== _get_story_sections 테스트 ==========


class TestGetStorySections:
    """_get_story_sections 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_get_sections_empty(self, mock_db_context, mock_anthropic):
        """섹션 없을 때"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service._get_story_sections(uuid4())

        assert result == []

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_get_sections_with_data(self, mock_db_context, mock_anthropic):
        """섹션 조회"""
        from app.services.story_service import StoryService

        section_id = uuid4()
        now = datetime.utcnow()

        mock_db = MagicMock()

        mock_row = MagicMock()
        mock_row.section_id = str(section_id)
        mock_row.section_type = "analysis"
        mock_row.order = 0
        mock_row.title = "분석"
        mock_row.narrative = "내용"
        mock_row.charts = "[]"
        mock_row.ai_generated = False
        mock_row.created_at = now

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service._get_story_sections(uuid4())

        assert len(result) == 1
        assert result[0].section_type == "analysis"
        assert result[0].title == "분석"

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_get_sections_with_charts(self, mock_db_context, mock_anthropic):
        """차트가 있는 섹션 조회"""
        from app.services.story_service import StoryService

        section_id = uuid4()
        now = datetime.utcnow()

        mock_db = MagicMock()

        mock_row = MagicMock()
        mock_row.section_id = str(section_id)
        mock_row.section_type = "analysis"
        mock_row.order = 0
        mock_row.title = "분석"
        mock_row.narrative = "내용"
        mock_row.charts = json.dumps([{
            "chart_config": {"type": "bar", "data": []},
            "caption": "테스트 차트",
            "order": 0
        }])
        mock_row.ai_generated = True
        mock_row.created_at = now

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service._get_story_sections(uuid4())

        assert len(result) == 1
        assert result[0].ai_generated is True
        assert len(result[0].charts) == 1


# ========== _collect_story_data 테스트 ==========


class TestCollectStoryData:
    """_collect_story_data 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_collect_data_empty(self, mock_db_context, mock_anthropic):
        """데이터 없을 때"""
        from app.services.story_service import StoryService

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service._collect_story_data(uuid4(), None, None, None)

        assert result["summary_data"] == []
        assert result["charts"] == []

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_collect_data_with_sensors(self, mock_db_context, mock_anthropic):
        """센서 데이터 수집"""
        from app.services.story_service import StoryService
        from decimal import Decimal

        mock_db = MagicMock()

        mock_row = MagicMock()
        mock_row.line_code = "L1"
        mock_row.total_readings = 100
        mock_row.avg_temp = Decimal("25.5")
        mock_row.avg_pressure = Decimal("1.2")
        mock_row.avg_humidity = Decimal("60.0")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service._collect_story_data(uuid4(), "온도 분석", "24h", None)

        assert len(result["summary_data"]) == 1
        assert result["summary_data"][0]["line_code"] == "L1"
        assert result["summary_data"][0]["avg_temp"] == 25.5

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_collect_data_with_charts(self, mock_db_context, mock_anthropic):
        """차트 데이터 수집"""
        from app.services.story_service import StoryService

        chart_id = uuid4()

        mock_db = MagicMock()

        # 센서 결과
        mock_sensor_result = MagicMock()
        mock_sensor_result.fetchall.return_value = []

        # 차트 결과
        mock_chart_row = MagicMock()
        mock_chart_row.chart_id = chart_id
        mock_chart_row.title = "테스트 차트"
        mock_chart_row.chart_config = {"type": "bar"}

        mock_chart_result = MagicMock()
        mock_chart_result.fetchall.return_value = [mock_chart_row]

        mock_db.execute.side_effect = [mock_sensor_result, mock_chart_result]
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        service = StoryService()

        result = await service._collect_story_data(
            uuid4(), None, None, [chart_id]
        )

        assert len(result["charts"]) == 1
        assert result["charts"][0]["title"] == "테스트 차트"


# ========== _generate_story_sections 테스트 ==========


class TestGenerateStorySections:
    """_generate_story_sections 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("app.services.story_service.Anthropic")
    @patch("app.services.story_service.get_db_context")
    async def test_generate_sections(self, mock_db_context, mock_anthropic):
        """섹션 자동 생성"""
        from app.services.story_service import StoryService
        from anthropic.types import Message, TextBlock

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db_context.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_context.return_value.__exit__ = MagicMock(return_value=None)

        # LLM 응답 모킹
        mock_response = MagicMock(spec=Message)
        mock_response.content = [
            TextBlock(type="text", text=json.dumps({
                "sections": [
                    {"section_type": "introduction", "title": "소개", "narrative": "시작"},
                    {"section_type": "analysis", "title": "분석", "narrative": "분석 내용"},
                ]
            }))
        ]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        service = StoryService()

        result = await service._generate_story_sections(
            uuid4(), uuid4(), "불량률", "24h", None
        )

        assert len(result) == 2
        assert result[0].section_type == "introduction"
        assert result[1].section_type == "analysis"
