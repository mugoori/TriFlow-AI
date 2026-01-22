/**
 * ChatContainer Component
 * 채팅 UI 메인 컨테이너 (SSE 스트리밍 지원)
 * 워크플로우 미리보기 패널 통합
 */

import { useRef, useEffect, useState, useCallback } from 'react';
import { Trash2, StopCircle } from 'lucide-react';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { useChat } from '../contexts/ChatContext';
import { WorkflowPreviewPanel } from './workflow/WorkflowPreviewPanel';
import { workflowService } from '../services/workflowService';
import { WorkflowDSL } from '../types/agent';

interface ChatContainerProps {
  currentView?: string;
}

export function ChatContainer({ currentView = 'chat' }: ChatContainerProps) {
  const {
    messages,
    loading,
    streaming,
    sendMessageStream: originalSendMessageStream,
    cancelStream,
    clearMessages,
    pendingWorkflow,
    isWorkflowPanelOpen,
    setPendingWorkflow,
    setWorkflowPanelOpen,
  } = useChat();
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // currentView를 포함한 sendMessageStream 래퍼
  const sendMessageStream = useCallback((message: string) => {
    originalSendMessageStream(message, currentView);
  }, [originalSendMessageStream, currentView]);

  // pendingWorkflow의 최신 값을 추적하는 ref (클로저 문제 해결)
  const pendingWorkflowRef = useRef(pendingWorkflow);

  // pendingWorkflow가 변경될 때마다 ref 업데이트
  useEffect(() => {
    pendingWorkflowRef.current = pendingWorkflow;
  }, [pendingWorkflow]);

  // 스트리밍 또는 로딩 중인지 확인
  const isProcessing = loading || streaming.isStreaming;

  // 메시지 목록 자동 스크롤
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streaming.isStreaming]);

  // 대화 지우기 핸들러
  const handleClearChat = () => {
    clearMessages();
    setShowClearConfirm(false);
  };

  // 워크플로우 적용 핸들러
  // useRef를 사용하여 항상 최신 pendingWorkflow 값을 참조 (React 클로저 문제 해결)
  const handleApplyWorkflow = useCallback(async () => {
    // ref에서 최신 값 가져오기 (클로저가 아닌 최신 상태)
    const currentWorkflow = pendingWorkflowRef.current;
    if (!currentWorkflow?.dsl) return;

    // 디버그: 원본 DSL 확인
    console.log('[ChatContainer] 원본 currentWorkflow.dsl:', JSON.stringify(currentWorkflow.dsl, null, 2));

    try {
      // DSL을 workflowService의 형식에 맞게 변환
      // 깊은 복사로 중첩 노드 구조 보존
      const dslDefinition = JSON.parse(JSON.stringify({
        name: currentWorkflow.workflowName || currentWorkflow.dsl.name || '새 워크플로우',
        description: currentWorkflow.dsl.description,
        trigger: {
          type: currentWorkflow.dsl.trigger.type,
          config: currentWorkflow.dsl.trigger.config || {},
        },
        nodes: currentWorkflow.dsl.nodes,
      }));

      // 디버그: API로 전송할 데이터 확인
      console.log('[ChatContainer] API 전송 dslDefinition:', JSON.stringify(dslDefinition, null, 2));

      const newWorkflow = await workflowService.create({
        name: currentWorkflow.workflowName || currentWorkflow.dsl.name || '새 워크플로우',
        description: currentWorkflow.dsl.description || '',
        dsl_definition: dslDefinition,
      });

      // 디버그: 저장 결과 확인
      console.log('[ChatContainer] 저장된 워크플로우:', JSON.stringify(newWorkflow, null, 2));

      // 워크플로우 ID를 pendingWorkflow에 업데이트
      setPendingWorkflow({
        ...currentWorkflow,
        workflowId: newWorkflow.workflow_id,
        workflowName: newWorkflow.name,
      });

      // 저장 성공 메시지를 채팅에 추가할 수도 있음
      console.log('Workflow saved:', newWorkflow.workflow_id);
    } catch (error) {
      console.error('Failed to save workflow:', error);
    }
  }, [setPendingWorkflow]); // pendingWorkflow 의존성 제거 - ref 사용하므로 불필요

  // 워크플로우 수정 요청 핸들러
  const handleRequestModification = useCallback((feedback: string) => {
    // 피드백을 채팅 메시지로 전송
    sendMessageStream(`워크플로우 수정 요청: ${feedback}`);
  }, [sendMessageStream]);

  // 워크플로우 패널 닫기 핸들러
  const handleCloseWorkflowPanel = useCallback(() => {
    setWorkflowPanelOpen(false);
  }, [setWorkflowPanelOpen]);

  // DSL 업데이트 핸들러 - 미리보기에서 수정된 DSL을 pendingWorkflow에 반영
  // functional update 패턴으로 stale closure 문제 해결
  const handleDslUpdate = useCallback((updatedDsl: WorkflowDSL) => {
    setPendingWorkflow((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        dsl: updatedDsl,
      };
    });
  }, [setPendingWorkflow]);

  return (
    <div className="flex h-full">
      {/* 채팅 영역 */}
      <div className="flex-1 flex flex-col h-full min-w-0">
        {/* 헤더 - 대화 지우기 버튼 */}
        {messages.length > 0 && (
          <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
            {/* 스트리밍 상태 표시 */}
            <div className="flex items-center gap-2">
              {streaming.isStreaming && (
                <>
                  <div className="flex items-center gap-1.5">
                    {/* 회전 스피너 - 동작 중임을 명확하게 표시 */}
                    <svg className="w-4 h-4 animate-spin text-green-500" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                    </svg>
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {streaming.status || '처리 중...'}
                    </span>
                  </div>
                  {streaming.currentAgent && (
                    <span className="text-xs px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded">
                      {streaming.currentAgent}
                    </span>
                  )}
                </>
              )}
            </div>

            {/* 대화 지우기 / 중지 버튼 */}
            <div className="flex items-center gap-2">
              {streaming.isStreaming ? (
                <button
                  onClick={cancelStream}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/30 rounded transition-colors"
                  title="스트리밍 중지"
                >
                  <StopCircle className="w-3.5 h-3.5" />
                  <span>중지</span>
                </button>
              ) : showClearConfirm ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 dark:text-slate-400">대화를 지울까요?</span>
                  <button
                    onClick={handleClearChat}
                    className="px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/30 rounded transition-colors"
                  >
                    삭제
                  </button>
                  <button
                    onClick={() => setShowClearConfirm(false)}
                    className="px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 rounded transition-colors"
                  >
                    취소
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowClearConfirm(true)}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:text-red-600 hover:bg-red-50 dark:text-slate-400 dark:hover:text-red-400 dark:hover:bg-red-900/30 rounded transition-colors"
                  title="대화 지우기"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>대화 지우기</span>
                </button>
              )}
            </div>
          </div>
        )}

        {/* 메시지 목록 */}
        <div className="flex-1 overflow-y-auto p-4 bg-slate-50 dark:bg-slate-900">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-slate-600 dark:text-slate-400 mb-2">
                  대화를 시작해보세요
                </p>
                <p className="text-sm text-slate-500 dark:text-slate-500">
                  예: "온도 센서 데이터를 분석해줘"
                </p>
              </div>
            </div>
          ) : (
            <>
              {messages.map((message, index) => (
                <ChatMessage
                  key={message.id || index}
                  message={message}
                />
              ))}
              {/* 일반 로딩 인디케이터 (비스트리밍 모드용) */}
              {loading && !streaming.isStreaming && (
                <div className="flex justify-start mb-4">
                  <div className="bg-slate-100 dark:bg-slate-800 rounded-lg px-4 py-2">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* 메시지 입력 - 스트리밍 모드 사용 */}
        <ChatInput onSendMessage={sendMessageStream} disabled={isProcessing} />
      </div>

      {/* 워크플로우 미리보기 패널 */}
      {isWorkflowPanelOpen && pendingWorkflow && (
        <WorkflowPreviewPanel
          dsl={pendingWorkflow.dsl}
          workflowId={pendingWorkflow.workflowId}
          workflowName={pendingWorkflow.workflowName}
          isOpen={isWorkflowPanelOpen}
          onApply={handleApplyWorkflow}
          onRequestModification={handleRequestModification}
          onClose={handleCloseWorkflowPanel}
          onDslUpdate={handleDslUpdate}
        />
      )}
    </div>
  );
}
