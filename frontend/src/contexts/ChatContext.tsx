/**
 * ChatContext
 * 채팅 상태를 전역으로 관리하여 탭 이동 시에도 유지
 * SSE 스트리밍 지원
 * 워크플로우 프리뷰 패널 상태 관리
 */

import { createContext, useContext, useState, useCallback, useRef, useEffect, ReactNode } from 'react';
import type { ChatMessage, SSEEvent, StreamingState, ConversationMessage } from '../types/agent';
import { agentService } from '../services/agentService';
import type { WorkflowDSL } from '../components/workflow/WorkflowPreviewPanel';

// localStorage 키
const CHAT_STORAGE_KEY = 'triflow_chat_messages';

// localStorage에서 메시지 불러오기
function loadMessagesFromStorage(): ChatMessage[] {
  try {
    const stored = localStorage.getItem(CHAT_STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.error('Failed to load chat messages from storage:', e);
  }
  return [];
}

// 워크플로우 프리뷰 상태
interface PendingWorkflow {
  dsl: WorkflowDSL;
  workflowId?: string;
  workflowName?: string;
}

interface ChatContextType {
  messages: ChatMessage[];
  loading: boolean;
  streaming: StreamingState;
  sendMessage: (content: string) => Promise<void>;
  sendMessageStream: (content: string, currentView?: string) => void;
  cancelStream: () => void;
  clearMessages: () => void;
  // 워크플로우 프리뷰 관련
  pendingWorkflow: PendingWorkflow | null;
  isWorkflowPanelOpen: boolean;
  setPendingWorkflow: (
    workflow: PendingWorkflow | null | ((prev: PendingWorkflow | null) => PendingWorkflow | null)
  ) => void;
  setWorkflowPanelOpen: (open: boolean) => void;
  clearPendingWorkflow: () => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessagesFromStorage);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState<StreamingState>({
    isStreaming: false,
  });
  const abortControllerRef = useRef<AbortController | null>(null);

  // 메시지 변경 시 localStorage에 저장
  useEffect(() => {
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
    } catch (e) {
      console.error('Failed to save chat messages to storage:', e);
    }
  }, [messages]);

  // 워크플로우 프리뷰 상태
  const [pendingWorkflow, setPendingWorkflowState] = useState<PendingWorkflow | null>(null);
  const [isWorkflowPanelOpen, setWorkflowPanelOpenState] = useState(false);

  // 워크플로우 상태 설정 함수 (functional updater 지원)
  const setPendingWorkflow = useCallback((
    workflowOrUpdater: PendingWorkflow | null | ((prev: PendingWorkflow | null) => PendingWorkflow | null)
  ) => {
    if (typeof workflowOrUpdater === 'function') {
      setPendingWorkflowState((prev) => {
        const result = workflowOrUpdater(prev);
        // 새로운 워크플로우가 설정되면 패널 열기
        if (result && !prev) {
          setWorkflowPanelOpenState(true);
        }
        return result;
      });
    } else {
      setPendingWorkflowState(workflowOrUpdater);
      if (workflowOrUpdater) {
        setWorkflowPanelOpenState(true);
      }
    }
  }, []);

  const setWorkflowPanelOpen = useCallback((open: boolean) => {
    setWorkflowPanelOpenState(open);
  }, []);

  const clearPendingWorkflow = useCallback(() => {
    setPendingWorkflowState(null);
    setWorkflowPanelOpenState(false);
  }, []);

  // 대화 이력을 API 형식으로 변환하는 헬퍼 함수
  const getConversationHistory = useCallback((currentMessages: ChatMessage[]): ConversationMessage[] => {
    return currentMessages.map(msg => ({
      role: msg.role,
      content: msg.content,
    }));
  }, []);

  // 일반 채팅 (비스트리밍)
  const sendMessage = useCallback(async (content: string) => {
    // 현재 대화 이력을 API 전송 전에 저장
    const conversationHistory = getConversationHistory(messages);

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
        conversation_history: conversationHistory,
      });

      // 개발자 콘솔에 모델 정보 출력
      console.log(`[AI Response] Agent: ${response.agent_name}, Model: ${response.model || 'unknown'}`);

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
  }, [messages, getConversationHistory]);

  // 스트리밍 채팅 (SSE)
  const sendMessageStream = useCallback((content: string, currentView?: string) => {
    // 현재 대화 이력을 API 전송 전에 저장
    const conversationHistory = getConversationHistory(messages);

    // 컨텍스트 메타데이터 구성
    const contextMetadata: Record<string, any> = {};
    if (currentView) {
      contextMetadata.current_tab = currentView;
      // 한국바이오팜 탭이면 스키마 힌트 추가
      if (currentView === 'korea_biopharm') {
        contextMetadata.schema_hint = 'korea_biopharm';
        contextMetadata.domain = 'pharmaceutical';
      }
    }

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
          // 개발자 콘솔에 모델 정보 출력
          console.log(`[AI Response] Agent: ${agentName}, Model: ${event.model || 'unknown'}`);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, agent_name: agentName }
                : msg
            )
          );
          setStreaming({ isStreaming: false });
          break;

        case 'workflow':
          // 워크플로우 생성 이벤트 처리
          if (event.workflow?.dsl) {
            setPendingWorkflow({
              dsl: event.workflow.dsl as WorkflowDSL,
              workflowId: event.workflow.workflowId,
              workflowName: event.workflow.workflowName,
            });
          }
          break;

        case 'response_data':
          // BI 인사이트, 차트, 테이블 등 구조화된 데이터
          if (event.data) {
            console.log('[ChatContext] Received response_data:', Object.keys(event.data));
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, response_data: event.data }
                  : msg
              )
            );
          }
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

    // SSE 스트림 시작 (대화 이력 및 컨텍스트 포함)
    abortControllerRef.current = agentService.chatStream(
      {
        message: content,
        conversation_history: conversationHistory,
        context: contextMetadata,  // 현재 탭 정보 포함
      },
      handleEvent,
      handleError
    );
  }, [messages, getConversationHistory]);

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
    // localStorage에서도 삭제
    localStorage.removeItem(CHAT_STORAGE_KEY);
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
        // 워크플로우 프리뷰 관련
        pendingWorkflow,
        isWorkflowPanelOpen,
        setPendingWorkflow,
        setWorkflowPanelOpen,
        clearPendingWorkflow,
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
