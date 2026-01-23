"""
Agent API Router
에이전트 실행 엔드포인트 - AgentOrchestrator 사용
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from functools import partial
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse, JSONResponse

from app.services.agent_orchestrator import orchestrator
from app.schemas.agent import AgentRequest, AgentResponse, JudgmentRequest
from app.utils.errors import classify_error, format_error_response
from app.auth.dependencies import get_optional_user, get_db
from app.models import User
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

# ThreadPoolExecutor for running synchronous agent calls
_executor = ThreadPoolExecutor(max_workers=4)


@router.post("/chat", response_model=AgentResponse)
async def chat_with_agent(
    request: AgentRequest,
    current_user: User = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Meta Router를 통한 채팅
    사용자 메시지를 분석하여 적절한 Sub-Agent로 라우팅

    Args:
        request: AgentRequest (message, context, tenant_id, conversation_history)
        current_user: 인증된 사용자 (선택적)

    Returns:
        AgentResponse
    """
    try:
        logger.info(f"Chat request: {request.message[:100]}...")

        # Context 구성 (대화 이력 포함)
        context = request.context or {}
        if request.conversation_history:
            # 대화 이력을 context에 포함 (최근 10개 메시지만)
            context["conversation_history"] = [
                msg.model_dump() for msg in request.conversation_history[-10:]
            ]
            logger.info(f"Including {len(context['conversation_history'])} messages from conversation history")

        # 사용자 역할 정보 전달 (인증된 경우)
        user_role = None
        if current_user:
            user_role = current_user.role
            context["user_id"] = str(current_user.user_id)
            context["user_email"] = current_user.email
            logger.info(f"Authenticated user: {current_user.email} (role: {user_role})")

        # DB Session을 context에 추가 (DomainRegistry 필터링용)
        context["db"] = db

        # AgentOrchestrator를 통한 자동 라우팅 및 실행
        # run_in_executor로 동기 함수를 비동기로 실행 (이벤트 루프 블로킹 방지)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            partial(
                orchestrator.process,
                message=request.message,
                context=context,
                tenant_id=request.tenant_id,
                user_role=user_role,
            )
        )

        return AgentResponse(
            response=result["response"],
            agent_name=result["agent_name"],
            model=result.get("model"),
            tool_calls=result["tool_calls"],
            iterations=result["iterations"],
            routing_info=result.get("routing_info"),
            response_data=result.get("response_data"),
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
        # run_in_executor로 동기 함수를 비동기로 실행
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            partial(
                orchestrator.execute_direct,
                agent_name="judgment",
                message=request.message,
                context=context,
            )
        )

        return AgentResponse(
            response=result["response"],
            agent_name=result["agent_name"],
            model=result.get("model"),
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
    conversation_history: list = None,
    user_role: str = None,
) -> AsyncGenerator[str, None]:
    """
    채팅 응답을 스트리밍으로 생성

    SSE (Server-Sent Events) 형식으로 응답을 스트리밍합니다.
    각 이벤트는 JSON 형식으로 전송됩니다.
    """
    logger.info(f"[SSE] Stream started - message: '{message[:50]}...', tenant_id: {tenant_id}, user_role: {user_role}")
    try:
        # Step 1: 시작 이벤트
        logger.debug("[SSE] Yielding start event")
        yield f"data: {json.dumps({'type': 'start', 'message': 'Processing request...'})}\n\n"
        await asyncio.sleep(0.1)

        # Step 2: Meta Router로 Intent 분류
        logger.debug("[SSE] Yielding routing event")
        yield f"data: {json.dumps({'type': 'routing', 'message': 'Classifying intent...'})}\n\n"

        # 대화 이력을 context에 포함
        merged_context = dict(context)
        if conversation_history:
            merged_context["conversation_history"] = conversation_history[-10:]

        # orchestrator.process()를 run_in_executor로 비동기 실행
        logger.debug(f"[SSE] Calling orchestrator.process() with message: '{message[:50]}...'")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            partial(
                orchestrator.process,
                message=message,
                context=merged_context,
                tenant_id=tenant_id,
                user_role=user_role,
            )
        )
        logger.debug(f"[SSE] Orchestrator returned: agent={result.get('agent_name')}, response_length={len(result.get('response', ''))}")

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
        logger.info(f"[SSE Debug] tool_calls count: {len(tool_calls)}")
        if tool_calls:
            yield f"data: {json.dumps({'type': 'tools', 'tool_calls': [{'tool': tc['tool'], 'input': tc['input']} for tc in tool_calls]})}\n\n"

            # Step 5.5: 워크플로우 생성 이벤트 감지
            for tc in tool_calls:
                tool_name = tc.get("tool", "")
                tool_result = tc.get("result", {})
                logger.info(f"[SSE Debug] Tool: {tool_name}, result type: {type(tool_result)}, result keys: {tool_result.keys() if isinstance(tool_result, dict) else 'N/A'}")

                # create_workflow 또는 create_complex_workflow 도구 호출 시 workflow 이벤트 전송
                if tool_name in ["create_workflow", "create_complex_workflow"] and isinstance(tool_result, dict):
                    logger.info(f"[SSE Debug] Workflow tool detected! success={tool_result.get('success')}, has_dsl={bool(tool_result.get('dsl'))}")
                    if tool_result.get("success"):
                        workflow_dsl = tool_result.get("dsl")
                        if workflow_dsl:
                            workflow_event = {
                                "type": "workflow",
                                "workflow": {
                                    "dsl": workflow_dsl,
                                    "workflowId": tool_result.get("workflow_id"),
                                    "workflowName": tool_result.get("name"),
                                },
                            }
                            yield f"data: {json.dumps(workflow_event)}\n\n"
                            logger.info(f"[SSE Debug] Workflow event emitted: name={tool_result.get('name')}")

        # Step 6: response_data 이벤트 (BI 인사이트 등 구조화된 데이터)
        response_data = result.get("response_data")
        if response_data:
            yield f"data: {json.dumps({'type': 'response_data', 'data': response_data})}\n\n"
            logger.info(f"[SSE Debug] response_data event emitted: keys={list(response_data.keys())}")

        # Step 7: 완료 이벤트 (모델 정보 포함)
        used_model = result.get("model")
        yield f"data: {json.dumps({'type': 'done', 'agent_name': target_agent_name, 'model': used_model, 'iterations': result.get('iterations', 1)})}\n\n"

        # SSE 스트림 명시적 종료 (Tauri WebView 호환성)
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"[SSE] Streaming error: {e}", exc_info=True)
        logger.error(f"[SSE] Error type: {type(e).__name__}, Error details: {str(e)}")

        # 사용자 친화적 에러 메시지 생성
        try:
            user_error = classify_error(e)
            error_response = format_error_response(user_error, lang="ko")
            yield f"data: {json.dumps({'type': 'error', 'message': error_response['message'], 'suggestion': error_response.get('suggestion'), 'retryable': user_error.retryable})}\n\n"
        except Exception as inner_e:
            logger.error(f"[SSE] Error formatting error response: {inner_e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': f'Internal error: {str(e)}', 'retryable': False})}\n\n"


@router.post("/chat/stream")
async def chat_stream(
    request: AgentRequest,
    current_user: User = Depends(get_optional_user)
):
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
    logger.info(f"[SSE Endpoint] Received request - message: '{request.message[:50]}...', tenant_id: {request.tenant_id}")

    # 대화 이력 변환
    history = None
    if request.conversation_history:
        history = [msg.model_dump() for msg in request.conversation_history]

    # 사용자 역할 정보
    user_role = current_user.role if current_user else None
    if current_user:
        logger.info(f"[SSE Endpoint] Stream authenticated user: {current_user.email} (role: {user_role})")
    else:
        logger.warning("[SSE Endpoint] No authenticated user (anonymous request)")

    return StreamingResponse(
        stream_chat_response(
            message=request.message,
            context=request.context or {},
            tenant_id=request.tenant_id,
            conversation_history=history,
            user_role=user_role,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
            "Content-Type": "text/event-stream; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
        },
    )
