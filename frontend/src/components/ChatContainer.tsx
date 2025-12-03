/**
 * ChatContainer Component
 * 채팅 UI 메인 컨테이너 (SSE 스트리밍 지원)
 */

import { useRef, useEffect, useState } from 'react';
import { Trash2, StopCircle } from 'lucide-react';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { useChat } from '../contexts/ChatContext';

export function ChatContainer() {
  const { messages, loading, streaming, sendMessageStream, cancelStream, clearMessages } = useChat();
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 - 대화 지우기 버튼 */}
      {messages.length > 0 && (
        <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          {/* 스트리밍 상태 표시 */}
          <div className="flex items-center gap-2">
            {streaming.isStreaming && (
              <>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
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
  );
}
