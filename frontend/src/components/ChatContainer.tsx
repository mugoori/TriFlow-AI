/**
 * ChatContainer Component
 * 채팅 UI 메인 컨테이너
 */

import { useState, useRef, useEffect } from 'react';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { agentService } from '../services/agentService';
import type { ChatMessage as ChatMessageType } from '../types/agent';

export function ChatContainer() {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 메시지 목록 자동 스크롤
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 메시지 전송 핸들러
  const handleSendMessage = async (content: string) => {
    // 사용자 메시지 추가
    const userMessage: ChatMessageType = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Agent API 호출
    setLoading(true);
    try {
      const response = await agentService.chat({
        message: content,
      });

      // Agent 응답 추가
      const assistantMessage: ChatMessageType = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        agent_name: response.agent_name,
        tool_calls: response.tool_calls,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      // 에러 메시지 추가
      const errorMessage: ChatMessageType = {
        role: 'assistant',
        content: `오류가 발생했습니다: ${error instanceof Error ? error.message : '알 수 없는 오류'}`,
        timestamp: new Date().toISOString(),
        agent_name: 'System',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* 채팅 헤더 */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-4">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-50">
          AI Agent Chat
        </h2>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
          Meta Router를 통해 적절한 Agent와 대화합니다
        </p>
      </div>

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
              <ChatMessage key={index} message={message} />
            ))}
            {loading && (
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

      {/* 메시지 입력 */}
      <ChatInput onSendMessage={handleSendMessage} disabled={loading} />
    </div>
  );
}
