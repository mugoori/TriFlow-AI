"""
Base Agent 클래스
모든 에이전트의 기본이 되는 추상 클래스
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging
import time
import random

from anthropic import Anthropic
from anthropic.types import Message, ToolUseBlock, TextBlock

from app.config import settings

logger = logging.getLogger(__name__)

# Retry 설정
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0


def is_retryable_api_error(exception: Exception) -> bool:
    """API 호출 재시도 가능 에러 판별"""
    error_str = str(exception).lower()

    # Rate limit
    if "rate" in error_str and "limit" in error_str:
        return True
    # Overloaded
    if "overloaded" in error_str:
        return True
    # Temporary errors
    if "temporarily" in error_str or "temporarily_unavailable" in error_str:
        return True
    # Connection errors
    if isinstance(exception, (ConnectionError, TimeoutError)):
        return True

    return False


class BaseAgent(ABC):
    """
    모든 에이전트의 베이스 클래스
    Anthropic Claude API를 사용한 Tool Calling 패턴 구현
    """

    def __init__(
        self,
        name: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """
        Args:
            name: 에이전트 이름
            model: 사용할 Claude 모델
            max_tokens: 최대 토큰 수
            max_retries: API 호출 최대 재시도 횟수
        """
        self.name = name
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.client = Anthropic(api_key=settings.anthropic_api_key)

        logger.info(f"Initialized {self.name} with model {self.model}")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        에이전트의 시스템 프롬프트 반환
        각 에이전트가 구현해야 함
        """
        pass

    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        에이전트가 사용할 Tool 정의 반환
        Anthropic Tool Calling 형식
        """
        pass

    @abstractmethod
    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Tool 실행 로직
        각 에이전트가 구현해야 함

        Args:
            tool_name: 실행할 Tool 이름
            tool_input: Tool 입력 파라미터

        Returns:
            Tool 실행 결과
        """
        pass

    def run(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        max_iterations: int = 5,
        tool_choice: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        에이전트 실행 (Tool Calling Loop 포함)

        Args:
            user_message: 사용자 입력 메시지
            context: 추가 컨텍스트 정보 (conversation_history 포함 가능)
            max_iterations: 최대 반복 횟수 (무한 루프 방지)
            tool_choice: Tool 선택 강제 옵션
                - {"type": "auto"}: 자동 선택 (기본)
                - {"type": "any"}: 반드시 하나의 tool 호출
                - {"type": "tool", "name": "tool_name"}: 특정 tool 강제 호출

        Returns:
            {
                "response": "에이전트 최종 응답",
                "tool_calls": [...],
                "iterations": 실행 반복 횟수
            }
        """
        context = context or {}

        # 대화 이력이 있으면 messages에 포함
        messages = []
        conversation_history = context.get("conversation_history", [])

        if conversation_history:
            # 최근 10개 메시지만 포함 (토큰 제한)
            recent_history = conversation_history[-10:]
            for msg in recent_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            logger.info(f"[{self.name}] Loaded {len(recent_history)} messages from conversation history")

        # 현재 사용자 메시지 추가
        messages.append({"role": "user", "content": user_message})

        tool_calls = []
        iterations = 0
        force_tool_on_first = tool_choice is not None

        logger.info(f"[{self.name}] Starting agent run with message: {user_message[:100]}...")

        while iterations < max_iterations:
            iterations += 1
            logger.debug(f"[{self.name}] Iteration {iterations}/{max_iterations}")

            try:
                # Claude API 호출 파라미터
                # 컨텍스트 포함하여 시스템 프롬프트 생성 (BIPlannerAgent 등)
                try:
                    system_prompt = self.get_system_prompt(context)
                except TypeError:
                    # context 파라미터를 받지 않는 Agent는 기본 호출
                    system_prompt = self.get_system_prompt()

                api_params = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "system": system_prompt,
                    "tools": self.get_tools(),
                    "messages": messages,
                }

                # 첫 번째 호출에만 tool_choice 적용
                if force_tool_on_first and iterations == 1 and tool_choice:
                    api_params["tool_choice"] = tool_choice
                    logger.info(f"[{self.name}] Forcing tool choice: {tool_choice}")

                # Claude API 호출 (Retry 로직 포함)
                response = self._call_api_with_retry(api_params)

                # 응답 처리
                if response.stop_reason == "end_turn":
                    # 최종 응답 도달
                    final_text = self._extract_text_content(response)
                    logger.info(f"[{self.name}] Completed with end_turn")
                    return {
                        "response": final_text,
                        "tool_calls": tool_calls,
                        "iterations": iterations,
                    }

                elif response.stop_reason == "tool_use":
                    # Tool 호출 필요
                    assistant_message = {
                        "role": "assistant",
                        "content": response.content,
                    }
                    messages.append(assistant_message)

                    # Tool 실행
                    tool_results = []
                    for block in response.content:
                        if isinstance(block, ToolUseBlock):
                            tool_name = block.name
                            tool_input = block.input
                            tool_use_id = block.id

                            logger.info(f"[{self.name}] Executing tool: {tool_name}")
                            logger.debug(f"[{self.name}] Tool input: {tool_input}")

                            try:
                                result = self.execute_tool(tool_name, tool_input)
                                tool_calls.append({
                                    "tool": tool_name,
                                    "input": tool_input,
                                    "result": result,
                                })

                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": str(result),
                                })
                            except Exception as e:
                                logger.error(f"[{self.name}] Tool execution error: {e}")
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": f"Error: {str(e)}",
                                    "is_error": True,
                                })

                    # Tool 결과를 메시지에 추가
                    messages.append({
                        "role": "user",
                        "content": tool_results,
                    })

                else:
                    # 예상치 못한 stop_reason
                    logger.warning(f"[{self.name}] Unexpected stop_reason: {response.stop_reason}")
                    final_text = self._extract_text_content(response)
                    return {
                        "response": final_text,
                        "tool_calls": tool_calls,
                        "iterations": iterations,
                    }

            except Exception as e:
                logger.error(f"[{self.name}] Agent execution error: {e}")
                raise

        # 최대 반복 횟수 초과
        logger.warning(f"[{self.name}] Max iterations ({max_iterations}) reached")
        return {
            "response": "최대 반복 횟수에 도달했습니다.",
            "tool_calls": tool_calls,
            "iterations": iterations,
        }

    def _call_api_with_retry(self, api_params: Dict[str, Any]) -> Message:
        """
        Retry 로직이 포함된 API 호출

        Args:
            api_params: API 호출 파라미터

        Returns:
            Anthropic Message 객체

        Raises:
            Exception: 최대 재시도 후에도 실패한 경우
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return self.client.messages.create(**api_params)
            except Exception as e:
                last_exception = e

                # 재시도 가능한 에러가 아니면 즉시 raise
                if not is_retryable_api_error(e):
                    logger.warning(f"[{self.name}] Non-retryable error: {e}")
                    raise

                if attempt < self.max_retries:
                    # Exponential Backoff with Jitter
                    delay = min(
                        DEFAULT_BASE_DELAY * (2 ** attempt) * (0.5 + random.random()),
                        DEFAULT_MAX_DELAY
                    )
                    logger.warning(
                        f"[{self.name}] Retry {attempt + 1}/{self.max_retries} "
                        f"after {delay:.2f}s due to: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"[{self.name}] Max retries ({self.max_retries}) exceeded: {e}"
                    )
                    raise

        raise last_exception

    def _extract_text_content(self, response: Message) -> str:
        """
        Message에서 텍스트 콘텐츠 추출

        Args:
            response: Anthropic Message 객체

        Returns:
            추출된 텍스트
        """
        texts = []
        for block in response.content:
            if isinstance(block, TextBlock):
                texts.append(block.text)
        return "\n".join(texts)
