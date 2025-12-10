"""
Agent API Pydantic Schemas
"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """채팅 메시지"""

    role: str = Field(..., description="메시지 역할 (user, assistant)")
    content: str = Field(..., description="메시지 내용")


class ConversationMessage(BaseModel):
    """대화 이력의 개별 메시지 (타입 검증 강화)"""

    role: Literal["user", "assistant"] = Field(..., description="메시지 역할")
    content: str = Field(..., description="메시지 내용")


class AgentRequest(BaseModel):
    """Agent 실행 요청"""

    message: str = Field(..., description="사용자 메시지")
    context: Optional[Dict[str, Any]] = Field(default=None, description="추가 컨텍스트")
    tenant_id: Optional[str] = Field(default=None, description="테넌트 ID")
    conversation_history: Optional[List[ConversationMessage]] = Field(
        default=None,
        description="대화 이력 (최근 대화 컨텍스트 유지용)"
    )


class ToolCall(BaseModel):
    """Tool 호출 정보"""

    tool: str = Field(..., description="Tool 이름")
    input: Dict[str, Any] = Field(..., description="Tool 입력")
    result: Any = Field(..., description="Tool 실행 결과")


class AgentResponse(BaseModel):
    """Agent 실행 응답"""

    response: str = Field(..., description="Agent 응답 메시지")
    agent_name: str = Field(..., description="실행된 Agent 이름")
    tool_calls: List[ToolCall] = Field(default_factory=list, description="Tool 호출 이력")
    iterations: int = Field(..., description="실행 반복 횟수")
    routing_info: Optional[Dict[str, Any]] = Field(
        default=None, description="Meta Router의 라우팅 정보"
    )

    class Config:
        from_attributes = True


class JudgmentRequest(BaseModel):
    """Judgment Agent 직접 호출 요청"""

    message: str = Field(..., description="판단 요청 메시지")
    sensor_data: Optional[Dict[str, Any]] = Field(
        default=None, description="센서 데이터"
    )
    ruleset_id: Optional[str] = Field(default=None, description="Ruleset ID")
    tenant_id: Optional[str] = Field(default=None, description="테넌트 ID")
