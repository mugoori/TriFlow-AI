"""
Pydantic Schemas (Request/Response 모델)
"""

from .bi_insight import (
    AIInsight,
    InsightAction,
    InsightFact,
    InsightFeedbackRequest,
    InsightListResponse,
    InsightReasoning,
    InsightRequest,
    InsightResponse,
)
from .bi_story import (
    ChartRefineRequest,
    ChartRefineResponse,
    DataStory,
    StoryCreateRequest,
    StoryListResponse,
    StorySection,
    StorySectionChart,
    StorySectionCreateRequest,
    StorySectionUpdateRequest,
    StoryUpdateRequest,
)

__all__ = [
    # BI Insight
    "AIInsight",
    "InsightAction",
    "InsightFact",
    "InsightFeedbackRequest",
    "InsightListResponse",
    "InsightReasoning",
    "InsightRequest",
    "InsightResponse",
    # BI Story
    "ChartRefineRequest",
    "ChartRefineResponse",
    "DataStory",
    "StoryCreateRequest",
    "StoryListResponse",
    "StorySection",
    "StorySectionChart",
    "StorySectionCreateRequest",
    "StorySectionUpdateRequest",
    "StoryUpdateRequest",
]
