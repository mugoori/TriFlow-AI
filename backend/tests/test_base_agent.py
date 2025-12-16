"""
Base Agent 테스트
base_agent.py의 BaseAgent 클래스 테스트
"""
import pytest
from unittest.mock import MagicMock, patch
from typing import Any, Dict, List

from anthropic.types import Message, TextBlock, ToolUseBlock

from app.agents.base_agent import BaseAgent


class ConcreteAgent(BaseAgent):
    """테스트용 구체 에이전트"""

    def get_system_prompt(self) -> str:
        return "You are a test agent."

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "test_tool",
                "description": "A test tool",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Test message"
                        }
                    },
                    "required": ["message"]
                }
            },
            {
                "name": "error_tool",
                "description": "A tool that raises an error",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        if tool_name == "test_tool":
            return {"success": True, "message": tool_input.get("message", "")}
        elif tool_name == "error_tool":
            raise ValueError("Tool execution failed")
        else:
            raise ValueError(f"Unknown tool: {tool_name}")


class TestBaseAgentInit:
    """BaseAgent 초기화 테스트"""

    @patch("app.agents.base_agent.Anthropic")
    def test_init_with_defaults(self, mock_anthropic):
        """기본값으로 초기화"""
        agent = ConcreteAgent(name="TestAgent")

        assert agent.name == "TestAgent"
        assert agent.model == "claude-sonnet-4-5-20250929"
        assert agent.max_tokens == 4096

    @patch("app.agents.base_agent.Anthropic")
    def test_init_with_custom_values(self, mock_anthropic):
        """커스텀 값으로 초기화"""
        agent = ConcreteAgent(
            name="CustomAgent",
            model="claude-opus-4-20250514",
            max_tokens=8192
        )

        assert agent.name == "CustomAgent"
        assert agent.model == "claude-opus-4-20250514"
        assert agent.max_tokens == 8192

    @patch("app.agents.base_agent.Anthropic")
    def test_client_initialized(self, mock_anthropic):
        """Anthropic 클라이언트 초기화 확인"""
        agent = ConcreteAgent(name="TestAgent")

        mock_anthropic.assert_called_once()
        assert agent.client is not None


class TestBaseAgentAbstractMethods:
    """추상 메서드 테스트"""

    @patch("app.agents.base_agent.Anthropic")
    def test_get_system_prompt(self, mock_anthropic):
        """시스템 프롬프트 반환"""
        agent = ConcreteAgent(name="TestAgent")
        prompt = agent.get_system_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @patch("app.agents.base_agent.Anthropic")
    def test_get_tools(self, mock_anthropic):
        """도구 정의 반환"""
        agent = ConcreteAgent(name="TestAgent")
        tools = agent.get_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0
        assert "name" in tools[0]
        assert "description" in tools[0]
        assert "input_schema" in tools[0]

    @patch("app.agents.base_agent.Anthropic")
    def test_execute_tool_success(self, mock_anthropic):
        """도구 실행 성공"""
        agent = ConcreteAgent(name="TestAgent")
        result = agent.execute_tool("test_tool", {"message": "Hello"})

        assert result["success"] is True
        assert result["message"] == "Hello"

    @patch("app.agents.base_agent.Anthropic")
    def test_execute_tool_error(self, mock_anthropic):
        """도구 실행 에러"""
        agent = ConcreteAgent(name="TestAgent")

        with pytest.raises(ValueError) as exc_info:
            agent.execute_tool("error_tool", {})

        assert "Tool execution failed" in str(exc_info.value)

    @patch("app.agents.base_agent.Anthropic")
    def test_execute_unknown_tool(self, mock_anthropic):
        """알 수 없는 도구 실행"""
        agent = ConcreteAgent(name="TestAgent")

        with pytest.raises(ValueError) as exc_info:
            agent.execute_tool("unknown_tool", {})

        assert "Unknown tool" in str(exc_info.value)


class TestBaseAgentRun:
    """run() 메서드 테스트"""

    @patch("app.agents.base_agent.Anthropic")
    def test_run_end_turn(self, mock_anthropic):
        """end_turn으로 종료하는 경우"""
        # Mock 응답 생성
        mock_response = MagicMock(spec=Message)
        mock_response.stop_reason = "end_turn"
        mock_response.content = [TextBlock(type="text", text="Hello, world!")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = ConcreteAgent(name="TestAgent")
        result = agent.run("Hello")

        assert result["response"] == "Hello, world!"
        assert result["tool_calls"] == []
        assert result["iterations"] == 1

    @patch("app.agents.base_agent.Anthropic")
    def test_run_with_tool_use(self, mock_anthropic):
        """도구 사용 후 응답"""
        # 첫 번째 응답: tool_use
        mock_tool_response = MagicMock(spec=Message)
        mock_tool_response.stop_reason = "tool_use"
        mock_tool_response.content = [
            ToolUseBlock(
                type="tool_use",
                id="tool_123",
                name="test_tool",
                input={"message": "test"}
            )
        ]

        # 두 번째 응답: end_turn
        mock_final_response = MagicMock(spec=Message)
        mock_final_response.stop_reason = "end_turn"
        mock_final_response.content = [TextBlock(type="text", text="Tool executed successfully")]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [mock_tool_response, mock_final_response]
        mock_anthropic.return_value = mock_client

        agent = ConcreteAgent(name="TestAgent")
        result = agent.run("Use the tool")

        assert result["response"] == "Tool executed successfully"
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool"] == "test_tool"
        assert result["iterations"] == 2

    @patch("app.agents.base_agent.Anthropic")
    def test_run_tool_execution_error(self, mock_anthropic):
        """도구 실행 중 에러"""
        # tool_use 응답
        mock_tool_response = MagicMock(spec=Message)
        mock_tool_response.stop_reason = "tool_use"
        mock_tool_response.content = [
            ToolUseBlock(
                type="tool_use",
                id="tool_123",
                name="error_tool",
                input={}
            )
        ]

        # end_turn 응답 (에러 후)
        mock_final_response = MagicMock(spec=Message)
        mock_final_response.stop_reason = "end_turn"
        mock_final_response.content = [TextBlock(type="text", text="Error handled")]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [mock_tool_response, mock_final_response]
        mock_anthropic.return_value = mock_client

        agent = ConcreteAgent(name="TestAgent")
        result = agent.run("Use the error tool")

        # 에러가 발생해도 계속 진행
        assert result["response"] == "Error handled"
        assert result["iterations"] == 2

    @patch("app.agents.base_agent.Anthropic")
    def test_run_max_iterations(self, mock_anthropic):
        """최대 반복 횟수 초과"""
        # 계속 tool_use만 반환
        mock_tool_response = MagicMock(spec=Message)
        mock_tool_response.stop_reason = "tool_use"
        mock_tool_response.content = [
            ToolUseBlock(
                type="tool_use",
                id="tool_123",
                name="test_tool",
                input={"message": "loop"}
            )
        ]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_tool_response
        mock_anthropic.return_value = mock_client

        agent = ConcreteAgent(name="TestAgent")
        result = agent.run("Loop forever", max_iterations=3)

        assert "최대 반복 횟수" in result["response"]
        assert len(result["tool_calls"]) == 3
        assert result["iterations"] == 3

    @patch("app.agents.base_agent.Anthropic")
    def test_run_with_context(self, mock_anthropic):
        """컨텍스트와 함께 실행"""
        mock_response = MagicMock(spec=Message)
        mock_response.stop_reason = "end_turn"
        mock_response.content = [TextBlock(type="text", text="Response with context")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = ConcreteAgent(name="TestAgent")
        result = agent.run("Hello", context={"user_id": "123", "tenant_id": "456"})

        assert result["response"] == "Response with context"

    @patch("app.agents.base_agent.Anthropic")
    def test_run_with_tool_choice(self, mock_anthropic):
        """tool_choice 옵션 사용"""
        mock_tool_response = MagicMock(spec=Message)
        mock_tool_response.stop_reason = "tool_use"
        mock_tool_response.content = [
            ToolUseBlock(
                type="tool_use",
                id="tool_123",
                name="test_tool",
                input={"message": "forced"}
            )
        ]

        mock_final_response = MagicMock(spec=Message)
        mock_final_response.stop_reason = "end_turn"
        mock_final_response.content = [TextBlock(type="text", text="Forced tool used")]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [mock_tool_response, mock_final_response]
        mock_anthropic.return_value = mock_client

        agent = ConcreteAgent(name="TestAgent")
        result = agent.run(
            "Force tool",
            tool_choice={"type": "tool", "name": "test_tool"}
        )

        # 첫 번째 호출에 tool_choice가 포함되었는지 확인
        first_call = mock_client.messages.create.call_args_list[0]
        assert "tool_choice" in first_call.kwargs

        assert result["response"] == "Forced tool used"

    @patch("app.agents.base_agent.Anthropic")
    def test_run_unexpected_stop_reason(self, mock_anthropic):
        """예상치 못한 stop_reason"""
        mock_response = MagicMock(spec=Message)
        mock_response.stop_reason = "max_tokens"
        mock_response.content = [TextBlock(type="text", text="Truncated response")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = ConcreteAgent(name="TestAgent")
        result = agent.run("Long message")

        assert result["response"] == "Truncated response"
        assert result["iterations"] == 1

    @patch("app.agents.base_agent.Anthropic")
    def test_run_api_error(self, mock_anthropic):
        """API 호출 에러"""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic.return_value = mock_client

        agent = ConcreteAgent(name="TestAgent")

        with pytest.raises(Exception) as exc_info:
            agent.run("Hello")

        assert "API Error" in str(exc_info.value)


class TestExtractTextContent:
    """_extract_text_content() 메서드 테스트"""

    @patch("app.agents.base_agent.Anthropic")
    def test_extract_single_text_block(self, mock_anthropic):
        """단일 텍스트 블록 추출"""
        agent = ConcreteAgent(name="TestAgent")

        mock_response = MagicMock(spec=Message)
        mock_response.content = [TextBlock(type="text", text="Hello")]

        result = agent._extract_text_content(mock_response)
        assert result == "Hello"

    @patch("app.agents.base_agent.Anthropic")
    def test_extract_multiple_text_blocks(self, mock_anthropic):
        """다중 텍스트 블록 추출"""
        agent = ConcreteAgent(name="TestAgent")

        mock_response = MagicMock(spec=Message)
        mock_response.content = [
            TextBlock(type="text", text="First"),
            TextBlock(type="text", text="Second"),
        ]

        result = agent._extract_text_content(mock_response)
        assert result == "First\nSecond"

    @patch("app.agents.base_agent.Anthropic")
    def test_extract_mixed_content(self, mock_anthropic):
        """혼합 컨텐츠에서 텍스트만 추출"""
        agent = ConcreteAgent(name="TestAgent")

        mock_response = MagicMock(spec=Message)
        mock_response.content = [
            TextBlock(type="text", text="Text"),
            ToolUseBlock(type="tool_use", id="123", name="tool", input={}),
            TextBlock(type="text", text="More text"),
        ]

        result = agent._extract_text_content(mock_response)
        assert result == "Text\nMore text"

    @patch("app.agents.base_agent.Anthropic")
    def test_extract_empty_content(self, mock_anthropic):
        """빈 컨텐츠"""
        agent = ConcreteAgent(name="TestAgent")

        mock_response = MagicMock(spec=Message)
        mock_response.content = []

        result = agent._extract_text_content(mock_response)
        assert result == ""


class TestAgentIntegration:
    """에이전트 통합 테스트"""

    @patch("app.agents.base_agent.Anthropic")
    def test_multiple_tool_calls_in_single_iteration(self, mock_anthropic):
        """단일 반복에서 여러 도구 호출"""
        mock_tool_response = MagicMock(spec=Message)
        mock_tool_response.stop_reason = "tool_use"
        mock_tool_response.content = [
            ToolUseBlock(
                type="tool_use",
                id="tool_1",
                name="test_tool",
                input={"message": "first"}
            ),
            ToolUseBlock(
                type="tool_use",
                id="tool_2",
                name="test_tool",
                input={"message": "second"}
            ),
        ]

        mock_final_response = MagicMock(spec=Message)
        mock_final_response.stop_reason = "end_turn"
        mock_final_response.content = [TextBlock(type="text", text="Both tools executed")]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [mock_tool_response, mock_final_response]
        mock_anthropic.return_value = mock_client

        agent = ConcreteAgent(name="TestAgent")
        result = agent.run("Use multiple tools")

        assert len(result["tool_calls"]) == 2
        assert result["tool_calls"][0]["input"]["message"] == "first"
        assert result["tool_calls"][1]["input"]["message"] == "second"

    @patch("app.agents.base_agent.Anthropic")
    def test_tool_chain(self, mock_anthropic):
        """도구 체인 (연속 도구 호출)"""
        # 첫 번째 tool_use
        mock_response_1 = MagicMock(spec=Message)
        mock_response_1.stop_reason = "tool_use"
        mock_response_1.content = [
            ToolUseBlock(
                type="tool_use",
                id="tool_1",
                name="test_tool",
                input={"message": "step1"}
            )
        ]

        # 두 번째 tool_use
        mock_response_2 = MagicMock(spec=Message)
        mock_response_2.stop_reason = "tool_use"
        mock_response_2.content = [
            ToolUseBlock(
                type="tool_use",
                id="tool_2",
                name="test_tool",
                input={"message": "step2"}
            )
        ]

        # 최종 응답
        mock_final_response = MagicMock(spec=Message)
        mock_final_response.stop_reason = "end_turn"
        mock_final_response.content = [TextBlock(type="text", text="Chain completed")]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            mock_response_1,
            mock_response_2,
            mock_final_response
        ]
        mock_anthropic.return_value = mock_client

        agent = ConcreteAgent(name="TestAgent")
        result = agent.run("Chain tools")

        assert len(result["tool_calls"]) == 2
        assert result["iterations"] == 3
        assert result["response"] == "Chain completed"
