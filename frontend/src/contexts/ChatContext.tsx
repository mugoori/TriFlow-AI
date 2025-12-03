/**
 * ChatContext
 * 채팅 상태를 전역으로 관리하여 탭 이동 시에도 유지
 * SSE 스트리밍 지원
 */

import { createContext, useContext, useState, useCallback, useRef, ReactNode } from 'react';
import type { ChatMessage, SSEEvent, StreamingState } from '../types/agent';
import { agentService } from '../services/agentService';

interface ChatContextType {
  messages: ChatMessage[];
  loading: boolean;
  streaming: StreamingState;
  sendMessage: (content: string) => Promise<void>;
  sendMessageStream: (content: string) => void;
  cancelStream: () => void;
  clearMessages: () => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState<StreamingState>({
    isStreaming: false,
  });
  const abortControllerRef = useRef<AbortController | null>(null);

  // 일반 채팅 (비스트리밍)
  const sendMessage = useCallback(async (content: string) => {
    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    setLoading(true);
    try {
      const response = await agentService.chat({
        message: content,
      });

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        agent_name: response.agent_name,
        tool_calls: response.tool_calls,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `오류가 발생했습니다: ${error instanceof Error ? error.message : '알 수 없는 오류'}`,
        timestamp: new Date().toISOString(),
        agent_name: 'System',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  }, []);

  // 스트리밍 채팅 (SSE)
  const sendMessageStream = useCallback((content: string) => {
    // 사용자 메시지 추가
    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // 빈 assistant 메시지 추가 (스트리밍으로 채워짐)
    const assistantMessageId = `stream-${Date.now()}`;
    const initialAssistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, initialAssistantMessage]);

    setStreaming({ isStreaming: true, status: '처리 중...' });

    let accumulatedContent = '';
    let agentName = '';
    let toolCalls: Array<{ tool: string; input: Record<string, any> }> = [];

    const handleEvent = (event: SSEEvent) => {
      switch (event.type) {
        case 'start':
          setStreaming({ isStreaming: true, status: '시작...' });
          break;

        case 'routing':
          setStreaming({ isStreaming: true, status: '의도 분석 중...' });
          break;

        case 'routed':
          agentName = event.agent || 'Agent';
          setStreaming({
            isStreaming: true,
            currentAgent: agentName,
            status: `${agentName} 에이전트로 라우팅됨`,
          });
          break;

        case 'processing':
          setStreaming({
            isStreaming: true,
            currentAgent: agentName,
            status: '응답 생성 중...',
          });
          break;

        case 'content':
          // 콘텐츠 청크 누적
          accumulatedContent += event.content || '';
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: accumulatedContent, agent_name: agentName }
                : msg
            )
          );
          break;

        case 'tools':
          toolCalls = event.tool_calls || [];
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    tool_calls: toolCalls.map((tc) => ({
                      tool: tc.tool,
                      input: tc.input,
                      result: null,
                    })),
                  }
                : msg
            )
          );
          break;

        case 'done':
          agentName = event.agent_name || agentName;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, agent_name: agentName }
                : msg
            )
          );
          setStreaming({ isStreaming: false });
          break;

        case 'error':
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: `오류: ${event.message}`,
                    agent_name: 'System',
                  }
                : msg
            )
          );
          setStreaming({ isStreaming: false });
          break;
      }
    };

    const handleError = (error: Error) => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: `스트리밍 오류: ${error.message}`,
                agent_name: 'System',
              }
            : msg
        )
      );
      setStreaming({ isStreaming: false });
    };

    // SSE 스트림 시작
    abortControllerRef.current = agentService.chatStream(
      { message: content },
      handleEvent,
      handleError
    );
  }, []);

  // 스트림 취소
  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStreaming({ isStreaming: false });
  }, []);

  const clearMessages = useCallback(() => {
    cancelStream();
    setMessages([]);
  }, [cancelStream]);

  return (
    <ChatContext.Provider
      value={{
        messages,
        loading,
        streaming,
        sendMessage,
        sendMessageStream,
        cancelStream,
        clearMessages,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}
