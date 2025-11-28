"""
Agent API Router
에이전트 실행 엔드포인트
"""
import logging
from fastapi import APIRouter, HTTPException, status

from app.agents import MetaRouterAgent, JudgmentAgent, WorkflowPlannerAgent, BIPlannerAgent, LearningAgent
from app.schemas.agent import AgentRequest, AgentResponse, JudgmentRequest

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Judgment Agent failed: {str(e)}",
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
