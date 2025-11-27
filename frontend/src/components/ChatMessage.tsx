/**
 * ChatMessage Component
 * 채팅 메시지를 렌더링하는 컴포넌트
 */

import type { ChatMessage as ChatMessageType } from '../types/agent';
import { Card, CardContent } from './ui/card';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[80%] ${isUser ? 'ml-auto' : 'mr-auto'}`}>
        <Card className={isUser ? 'bg-blue-50 dark:bg-blue-950' : 'bg-slate-50 dark:bg-slate-900'}>
          <CardContent className="p-4">
            {/* 메시지 헤더 */}
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                {isUser ? '사용자' : message.agent_name || 'Agent'}
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-500">
                {new Date(message.timestamp).toLocaleTimeString('ko-KR', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>

            {/* 메시지 내용 */}
            <div className="text-sm text-slate-900 dark:text-slate-100 whitespace-pre-wrap">
              {message.content}
            </div>

            {/* Tool 호출 정보 */}
            {message.tool_calls && message.tool_calls.length > 0 && (
              <div className="mt-3 space-y-2">
                <div className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                  Tool 호출:
                </div>
                {message.tool_calls.map((tool, index) => (
                  <div
                    key={index}
                    className="text-xs bg-slate-100 dark:bg-slate-800 rounded p-2"
                  >
                    <div className="font-mono text-blue-600 dark:text-blue-400">
                      {tool.tool}
                    </div>
                    <div className="text-slate-600 dark:text-slate-400 mt-1">
                      {Object.keys(tool.input).length > 0 && (
                        <pre className="text-[10px] overflow-x-auto">
                          {JSON.stringify(tool.input, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
