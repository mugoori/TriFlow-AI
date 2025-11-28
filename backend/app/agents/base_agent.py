"""
Base Agent 클래스
모든 에이전트의 기본이 되는 추상 클래스
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

from anthropic import Anthropic
from anthropic.types import Message, ToolUseBlock, TextBlock

from app.config import settings

logger = logging.getLogger(__name__)


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
    ):
        """
        Args:
            name: 에이전트 이름
            model: 사용할 Claude 모델
            max_tokens: 최대 토큰 수
        """
        self.name = name
        self.model = model
        self.max_tokens = max_tokens
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
            context: 추가 컨텍스트 정보
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
        messages = [{"role": "user", "content": user_message}]
        tool_calls = []
        iterations = 0
        force_tool_on_first = tool_choice is not None

        logger.info(f"[{self.name}] Starting agent run with message: {user_message[:100]}...")

        while iterations < max_iterations:
            iterations += 1
            logger.debug(f"[{self.name}] Iteration {iterations}/{max_iterations}")

            try:
                # Claude API 호출 파라미터
                api_params = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "system": self.get_system_prompt(),
                    "tools": self.get_tools(),
                    "messages": messages,
                }

                # 첫 번째 호출에만 tool_choice 적용
                if force_tool_on_first and iterations == 1 and tool_choice:
                    api_params["tool_choice"] = tool_choice
                    logger.info(f"[{self.name}] Forcing tool choice: {tool_choice}")

                # Claude API 호출
                response = self.client.messages.create(**api_params)

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
