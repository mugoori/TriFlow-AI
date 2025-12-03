"""
Agent API Router
에이전트 실행 엔드포인트
"""
import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status, Request, Header
from fastapi.responses import StreamingResponse, JSONResponse

from app.agents import MetaRouterAgent, JudgmentAgent, WorkflowPlannerAgent, BIPlannerAgent, LearningAgent
from app.schemas.agent import AgentRequest, AgentResponse, JudgmentRequest
from app.utils.errors import classify_error, format_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

# Agent 인스턴스 (싱글톤 패턴)
meta_router = MetaRouterAgent()
judgment_agent = JudgmentAgent()
workflow_planner = WorkflowPlannerAgent()
bi_planner = BIPlannerAgent()
learning_agent = LearningAgent()


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

        # Step 1: Meta Router로 Intent 분류 및 라우팅
        routing_result = meta_router.run(
            user_message=request.message,
            context=request.context,
        )

        # Step 2: 라우팅 정보 추출
        routing_info = meta_router.parse_routing_result(routing_result)
        target_agent_name = routing_info.get("target_agent", "general")

        logger.info(f"Routed to agent: {target_agent_name}")

        # Step 3: 대상 Agent 실행
        if target_agent_name == "judgment":
            # Judgment Agent 실행
            agent_result = judgment_agent.run(
                user_message=routing_info.get("processed_request", request.message),
                context={
                    **(request.context or {}),
                    **routing_info.get("context", {}),
                },
            )

            return AgentResponse(
                response=agent_result["response"],
                agent_name="JudgmentAgent",
                tool_calls=[
                    {
                        "tool": tc["tool"],
                        "input": tc["input"],
                        "result": tc["result"],
                    }
                    for tc in agent_result.get("tool_calls", [])
                ],
                iterations=agent_result["iterations"],
                routing_info=routing_info,
            )

        elif target_agent_name == "workflow":
            # Workflow Planner Agent 실행
            # tool_choice로 create_workflow tool 호출 강제
            agent_result = workflow_planner.run(
                user_message=routing_info.get("processed_request", request.message),
                context={
                    **(request.context or {}),
                    **routing_info.get("context", {}),
                },
                max_iterations=5,
                tool_choice={"type": "tool", "name": "create_workflow"},
            )

            return AgentResponse(
                response=agent_result["response"],
                agent_name="WorkflowPlannerAgent",
                tool_calls=[
                    {
                        "tool": tc["tool"],
                        "input": tc["input"],
                        "result": tc["result"],
                    }
                    for tc in agent_result.get("tool_calls", [])
                ],
                iterations=agent_result["iterations"],
                routing_info=routing_info,
            )

        elif target_agent_name == "bi":
            # BI Planner Agent 실행
            agent_result = bi_planner.run(
                user_message=routing_info.get("processed_request", request.message),
                context={
                    **(request.context or {}),
                    **routing_info.get("context", {}),
                },
            )

            return AgentResponse(
                response=agent_result["response"],
                agent_name="BIPlannerAgent",
                tool_calls=[
                    {
                        "tool": tc["tool"],
                        "input": tc["input"],
                        "result": tc["result"],
                    }
                    for tc in agent_result.get("tool_calls", [])
                ],
                iterations=agent_result["iterations"],
                routing_info=routing_info,
            )

        elif target_agent_name == "learning":
            # Learning Agent 실행
            # 룰셋 생성 요청인지 확인
            msg_lower = request.message.lower()
            is_ruleset_creation = any(kw in msg_lower for kw in [
                "룰셋", "규칙 만들", "규칙 생성", "판단 규칙",
                "경고", "위험", "임계", "threshold",
                "ruleset", "create rule"
            ])

            agent_result = learning_agent.run(
                user_message=routing_info.get("processed_request", request.message),
                context={
                    **(request.context or {}),
                    **routing_info.get("context", {}),
                },
                max_iterations=5,
                tool_choice={"type": "tool", "name": "create_ruleset"} if is_ruleset_creation else None,
            )

            return AgentResponse(
                response=agent_result["response"],
                agent_name="LearningAgent",
                tool_calls=[
                    {
                        "tool": tc["tool"],
                        "input": tc["input"],
                        "result": tc["result"],
                    }
                    for tc in agent_result.get("tool_calls", [])
                ],
                iterations=agent_result["iterations"],
                routing_info=routing_info,
            )

        else:
            # General 응답
            return AgentResponse(
                response=routing_result["response"],
                agent_name="MetaRouterAgent",
                tool_calls=[
                    {
                        "tool": tc["tool"],
                        "input": tc["input"],
                        "result": tc["result"],
                    }
                    for tc in routing_result.get("tool_calls", [])
                ],
                iterations=routing_result["iterations"],
                routing_info=routing_info,
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

        # Judgment Agent 실행
        result = judgment_agent.run(
            user_message=request.message,
            context=context,
        )

        return AgentResponse(
            response=result["response"],
            agent_name="JudgmentAgent",
            tool_calls=[
                {
                    "tool": tc["tool"],
                    "input": tc["input"],
                    "result": tc["result"],
                }
                for tc in result.get("tool_calls", [])
            ],
            iterations=result["iterations"],
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
        "agents": {
            "meta_router": {
                "name": meta_router.name,
                "model": meta_router.model,
                "available": True,
            },
            "judgment": {
                "name": judgment_agent.name,
                "model": judgment_agent.model,
                "available": True,
            },
            "workflow": {
                "name": workflow_planner.name,
                "model": workflow_planner.model,
                "available": True,
            },
            "bi": {
                "name": bi_planner.name,
                "model": bi_planner.model,
                "available": True,
            },
            "learning": {
                "name": learning_agent.name,
                "model": learning_agent.model,
                "available": True,
            },
        },
    }


# ============ Streaming Chat Endpoint ============

async def stream_chat_response(
    message: str,
    context: dict,
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

        routing_result = meta_router.run(
            user_message=message,
            context=context,
        )

        routing_info = meta_router.parse_routing_result(routing_result)
        target_agent_name = routing_info.get("target_agent", "general")

        yield f"data: {json.dumps({'type': 'routed', 'agent': target_agent_name, 'message': f'Routed to {target_agent_name} agent'})}\n\n"
        await asyncio.sleep(0.1)

        # Step 3: 대상 에이전트 실행
        yield f"data: {json.dumps({'type': 'processing', 'message': f'Executing {target_agent_name} agent...'})}\n\n"

        if target_agent_name == "judgment":
            agent_result = judgment_agent.run(
                user_message=routing_info.get("processed_request", message),
                context={**(context or {}), **routing_info.get("context", {})},
            )
        elif target_agent_name == "workflow":
            agent_result = workflow_planner.run(
                user_message=routing_info.get("processed_request", message),
                context={**(context or {}), **routing_info.get("context", {})},
                max_iterations=5,
                tool_choice={"type": "tool", "name": "create_workflow"},
            )
        elif target_agent_name == "bi":
            agent_result = bi_planner.run(
                user_message=routing_info.get("processed_request", message),
                context={**(context or {}), **routing_info.get("context", {})},
            )
        elif target_agent_name == "learning":
            agent_result = learning_agent.run(
                user_message=routing_info.get("processed_request", message),
                context={**(context or {}), **routing_info.get("context", {})},
            )
        else:
            agent_result = routing_result

        # Step 4: 응답 텍스트를 청크로 스트리밍
        response_text = agent_result.get("response", "")
        chunk_size = 20  # 글자 수

        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i + chunk_size]
            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            await asyncio.sleep(0.05)  # 스트리밍 효과

        # Step 5: 도구 호출 정보
        tool_calls = agent_result.get("tool_calls", [])
        if tool_calls:
            yield f"data: {json.dumps({'type': 'tools', 'tool_calls': [{'tool': tc['tool'], 'input': tc['input']} for tc in tool_calls]})}\n\n"

        # Step 6: 완료 이벤트
        yield f"data: {json.dumps({'type': 'done', 'agent_name': target_agent_name, 'iterations': agent_result.get('iterations', 1)})}\n\n"

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
        stream_chat_response(request.message, request.context or {}),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
        },
    )
