"""
Agent API Router
에이전트 실행 엔드포인트 - AgentOrchestrator 사용
"""
import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status, Request, Header
from fastapi.responses import StreamingResponse, JSONResponse

from app.services.agent_orchestrator import orchestrator
from app.schemas.agent import AgentRequest, AgentResponse, JudgmentRequest
from app.utils.errors import classify_error, format_error_response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=AgentResponse)
async def chat_with_agent(request: AgentRequest):
    """
    Meta Router를 통한 채팅
    사용자 메시지를 분석하여 적절한 Sub-Agent로 라우팅

    Args:
        request: AgentRequest (message, context, tenant_id)

    Returns:
        AgentResponse
    """
    try:
        logger.info(f"Chat request: {request.message[:100]}...")

        # AgentOrchestrator를 통한 자동 라우팅 및 실행
        result = orchestrator.process(
            message=request.message,
            context=request.context,
            tenant_id=request.tenant_id,
        )

        return AgentResponse(
            response=result["response"],
            agent_name=result["agent_name"],
            tool_calls=result["tool_calls"],
            iterations=result["iterations"],
            routing_info=result.get("routing_info"),
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)

        # 사용자 친화적 에러 응답 생성
        user_error = classify_error(e)
        error_response = format_error_response(user_error, lang="ko")

        return JSONResponse(
            status_code=user_error.http_status,
            content=error_response,
        )


@router.post("/judgment", response_model=AgentResponse)
async def run_judgment_agent(request: JudgmentRequest):
    """
    Judgment Agent 직접 실행
    Meta Router를 거치지 않고 Judgment Agent를 바로 호출

    Args:
        request: JudgmentRequest

    Returns:
        AgentResponse
    """
    try:
        logger.info(f"Direct judgment request: {request.message[:100]}...")

        # Context 구성
        context = {}
        if request.sensor_data:
            context["sensor_data"] = request.sensor_data
        if request.ruleset_id:
            context["ruleset_id"] = request.ruleset_id
        if request.tenant_id:
            context["tenant_id"] = request.tenant_id

        # AgentOrchestrator를 통한 직접 실행 (MetaRouter 우회)
        result = orchestrator.execute_direct(
            agent_name="judgment",
            message=request.message,
            context=context,
        )

        return AgentResponse(
            response=result["response"],
            agent_name=result["agent_name"],
            tool_calls=result["tool_calls"],
            iterations=result["iterations"],
        )

    except ValueError as e:
        # 알 수 없는 에이전트
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except Exception as e:
        logger.error(f"Judgment error: {e}", exc_info=True)

        # 사용자 친화적 에러 응답 생성
        user_error = classify_error(e)
        error_response = format_error_response(user_error, lang="ko")

        return JSONResponse(
            status_code=user_error.http_status,
            content=error_response,
        )


@router.get("/status")
async def agent_status():
    """
    Agent 시스템 상태 확인

    Returns:
        Agent 시스템 정보
    """
    return {
        "status": "ok",
        "agents": orchestrator.get_agent_status(),
    }


# ============ Streaming Chat Endpoint ============

async def stream_chat_response(
    message: str,
    context: dict,
    tenant_id: str = None,
) -> AsyncGenerator[str, None]:
    """
    채팅 응답을 스트리밍으로 생성

    SSE (Server-Sent Events) 형식으로 응답을 스트리밍합니다.
    각 이벤트는 JSON 형식으로 전송됩니다.
    """
    try:
        # Step 1: 시작 이벤트
        yield f"data: {json.dumps({'type': 'start', 'message': 'Processing request...'})}\n\n"
        await asyncio.sleep(0.1)

        # Step 2: Meta Router로 Intent 분류
        yield f"data: {json.dumps({'type': 'routing', 'message': 'Classifying intent...'})}\n\n"

        # orchestrator.process()를 동기 호출하고 결과 스트리밍
        result = orchestrator.process(
            message=message,
            context=context,
            tenant_id=tenant_id,
        )

        target_agent_name = result.get("agent_name", "MetaRouterAgent")
        routing_info = result.get("routing_info", {})
        target_type = routing_info.get("target_agent", "general") if routing_info else "general"

        yield f"data: {json.dumps({'type': 'routed', 'agent': target_type, 'message': f'Routed to {target_type} agent'})}\n\n"
        await asyncio.sleep(0.1)

        # Step 3: 에이전트 실행 완료 알림
        yield f"data: {json.dumps({'type': 'processing', 'message': f'Executed {target_agent_name}...'})}\n\n"

        # Step 4: 응답 텍스트를 청크로 스트리밍
        response_text = result.get("response", "")
        chunk_size = 20  # 글자 수

        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i + chunk_size]
            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            await asyncio.sleep(0.05)  # 스트리밍 효과

        # Step 5: 도구 호출 정보
        tool_calls = result.get("tool_calls", [])
        if tool_calls:
            yield f"data: {json.dumps({'type': 'tools', 'tool_calls': [{'tool': tc['tool'], 'input': tc['input']} for tc in tool_calls]})}\n\n"

        # Step 6: 완료 이벤트
        yield f"data: {json.dumps({'type': 'done', 'agent_name': target_agent_name, 'iterations': result.get('iterations', 1)})}\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)

        # 사용자 친화적 에러 메시지 생성
        user_error = classify_error(e)
        error_response = format_error_response(user_error, lang="ko")

        yield f"data: {json.dumps({'type': 'error', 'message': error_response['message'], 'suggestion': error_response.get('suggestion'), 'retryable': user_error.retryable})}\n\n"


@router.post("/chat/stream")
async def chat_stream(request: AgentRequest):
    """
    스트리밍 채팅 엔드포인트 (SSE)

    Server-Sent Events를 사용하여 AI 응답을 실시간으로 스트리밍합니다.

    Event Types:
        - start: 처리 시작
        - routing: 의도 분류 중
        - routed: 에이전트 라우팅 완료
        - processing: 에이전트 실행 중
        - content: 응답 텍스트 청크
        - tools: 도구 호출 정보
        - done: 처리 완료
        - error: 오류 발생

    Usage (JavaScript):
        const eventSource = new EventSource('/api/v1/agents/chat/stream');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'content') {
                console.log(data.content);
            }
        };
    """
    return StreamingResponse(
        stream_chat_response(
            message=request.message,
            context=request.context or {},
            tenant_id=request.tenant_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
        },
    )
