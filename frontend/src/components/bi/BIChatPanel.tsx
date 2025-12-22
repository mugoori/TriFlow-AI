/**
 * BIChatPanel - 대화형 GenBI 채팅 인터페이스
 * AWS QuickSight GenBI Chat 기능 구현
 *
 * 기능:
 * - 자연어로 인사이트 요청
 * - 대화 히스토리 관리
 * - 인사이트 Pin 기능
 * - 세션 관리
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageSquare,
  Send,
  Loader2,
  Pin,
  PinOff,
  Trash2,
  Plus,
  ChevronLeft,
  Sparkles,
  AlertCircle,
  User,
  Bot,
  X,
  Edit3,
  Check,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type {
  ChatSession,
  ChatMessage,
  AIInsight,
  ChatContextType,
} from '@/types/bi';
import { biService } from '@/services/biService';

interface BIChatPanelProps {
  contextType?: ChatContextType;
  contextId?: string;
  onInsightGenerated?: (insight: AIInsight) => void;
  className?: string;
}

export function BIChatPanel({
  contextType = 'general',
  contextId,
  onInsightGenerated,
  className = '',
}: BIChatPanelProps) {
  // State
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [showSessions, setShowSessions] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 세션 목록 로드
  const loadSessions = useCallback(async () => {
    try {
      const response = await biService.getChatSessions();
      setSessions(response.sessions);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  }, []);

  // 세션 메시지 로드
  const loadMessages = useCallback(async (sessionId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await biService.getSessionMessages(sessionId, { page_size: 100 });
      setMessages(response.messages);
    } catch (err) {
      console.error('Failed to load messages:', err);
      setError(err instanceof Error ? err.message : 'Failed to load messages');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 초기 로드
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // 세션 변경 시 메시지 로드
  useEffect(() => {
    if (currentSessionId) {
      loadMessages(currentSessionId);
    } else {
      setMessages([]);
    }
  }, [currentSessionId, loadMessages]);

  // 메시지 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 메시지 전송
  const sendMessage = async () => {
    if (!inputValue.trim() || isSending) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setIsSending(true);
    setError(null);

    // Optimistic UI: 사용자 메시지 즉시 표시
    const tempUserMessage: ChatMessage = {
      message_id: `temp-${Date.now()}`,
      session_id: currentSessionId || '',
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, tempUserMessage]);

    try {
      const response = await biService.chat({
        message: userMessage,
        session_id: currentSessionId || undefined,
        context_type: contextType,
        context_id: contextId,
      });

      // 새 세션인 경우 세션 ID 설정
      if (!currentSessionId) {
        setCurrentSessionId(response.session_id);
        loadSessions(); // 세션 목록 갱신
      }

      // 응답 메시지 추가 (임시 메시지 교체)
      setMessages(prev => {
        const filtered = prev.filter(m => m.message_id !== tempUserMessage.message_id);
        // 실제 사용자 메시지 + AI 응답 추가
        const aiMessage: ChatMessage = {
          message_id: response.message_id,
          session_id: response.session_id,
          role: 'assistant',
          content: response.content,
          response_type: response.response_type,
          response_data: response.response_data as ChatMessage['response_data'],
          linked_insight_id: response.linked_insight_id || undefined,
          linked_chart_id: response.linked_chart_id || undefined,
          created_at: new Date().toISOString(),
        };
        return [
          ...filtered,
          { ...tempUserMessage, message_id: `user-${Date.now()}` },
          aiMessage,
        ];
      });

      // 인사이트 생성 시 콜백 호출
      if (response.insight && onInsightGenerated) {
        onInsightGenerated(response.insight);
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      setError(err instanceof Error ? err.message : 'Failed to send message');
      // 임시 메시지 제거
      setMessages(prev => prev.filter(m => m.message_id !== tempUserMessage.message_id));
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  // 새 채팅 시작
  const startNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setShowSessions(false);
    setError(null);
  };

  // 세션 선택
  const selectSession = (session: ChatSession) => {
    setCurrentSessionId(session.session_id);
    setShowSessions(false);
  };

  // 세션 삭제
  const deleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await biService.deleteChatSession(sessionId);
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
      if (currentSessionId === sessionId) {
        startNewChat();
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  // 세션 제목 수정
  const startEditingTitle = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(session.session_id);
    setEditingTitle(session.title);
  };

  const saveTitle = async (sessionId: string) => {
    if (!editingTitle.trim()) return;
    try {
      await biService.updateChatSession(sessionId, editingTitle.trim());
      setSessions(prev =>
        prev.map(s =>
          s.session_id === sessionId ? { ...s, title: editingTitle.trim() } : s
        )
      );
    } catch (err) {
      console.error('Failed to update title:', err);
    }
    setEditingSessionId(null);
  };

  // 인사이트 Pin
  const pinInsight = async (insightId: string) => {
    try {
      await biService.pinInsight(insightId);
      // 메시지 업데이트 (핀 상태 표시용)
      setMessages(prev =>
        prev.map(m =>
          m.linked_insight_id === insightId
            ? { ...m, response_data: { ...m.response_data, pinned: true } }
            : m
        )
      );
    } catch (err) {
      console.error('Failed to pin insight:', err);
    }
  };

  // 인사이트 Unpin
  const unpinInsight = async (insightId: string) => {
    try {
      await biService.unpinInsight(insightId);
      setMessages(prev =>
        prev.map(m =>
          m.linked_insight_id === insightId
            ? { ...m, response_data: { ...m.response_data, pinned: false } }
            : m
        )
      );
    } catch (err) {
      console.error('Failed to unpin insight:', err);
    }
  };

  // Enter 키 핸들러
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className={`flex flex-col h-full bg-white dark:bg-slate-900 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b dark:border-slate-800">
        <div className="flex items-center gap-3">
          {showSessions && (
            <button
              onClick={() => setShowSessions(false)}
              className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
          )}
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-purple-500" />
            <h3 className="font-semibold text-slate-900 dark:text-slate-50">
              {showSessions ? '대화 기록' : 'AI 인사이트 채팅'}
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSessions(!showSessions)}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400"
            title="대화 기록"
          >
            <MessageSquare className="w-4 h-4" />
          </button>
          <button
            onClick={startNewChat}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            새 대화
          </button>
        </div>
      </div>

      {/* Content */}
      {showSessions ? (
        // Sessions List
        <SessionsList
          sessions={sessions}
          currentSessionId={currentSessionId}
          editingSessionId={editingSessionId}
          editingTitle={editingTitle}
          onSelectSession={selectSession}
          onDeleteSession={deleteSession}
          onStartEditing={startEditingTitle}
          onSaveTitle={saveTitle}
          onCancelEditing={() => setEditingSessionId(null)}
          onEditingTitleChange={setEditingTitle}
        />
      ) : (
        // Chat View
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {isLoading && messages.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
              </div>
            ) : messages.length === 0 ? (
              <WelcomeMessage />
            ) : (
              messages.map((message) => (
                <MessageBubble
                  key={message.message_id}
                  message={message}
                  onPin={pinInsight}
                  onUnpin={unpinInsight}
                />
              ))
            )}
            {isSending && (
              <div className="flex items-center gap-2 text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">AI가 분석 중...</span>
              </div>
            )}
            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-sm">
                  <AlertCircle className="w-4 h-4" />
                  <span>{error}</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t dark:border-slate-800">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="데이터에 대해 물어보세요... (예: 이번 주 생산량 트렌드를 분석해줘)"
                className="flex-1 resize-none p-3 border rounded-lg bg-white dark:bg-slate-800 dark:border-slate-700 text-slate-900 dark:text-slate-50 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                rows={1}
                disabled={isSending}
              />
              <button
                onClick={sendMessage}
                disabled={!inputValue.trim() || isSending}
                className="p-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isSending ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-2">
              Shift + Enter로 줄바꿈, Enter로 전송
            </p>
          </div>
        </>
      )}
    </div>
  );
}

// =====================================================
// Welcome Message
// =====================================================

function WelcomeMessage() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <Sparkles className="w-12 h-12 text-purple-500 mb-4" />
      <h4 className="text-lg font-semibold text-slate-900 dark:text-slate-50 mb-2">
        AI 인사이트 채팅
      </h4>
      <p className="text-slate-500 mb-6 max-w-md">
        자연어로 데이터에 대해 질문하세요. AI가 분석하여 인사이트를 제공합니다.
      </p>
      <div className="space-y-2 text-sm text-slate-400">
        <p className="font-medium">예시 질문:</p>
        <ul className="space-y-1">
          <li>"이번 주 생산량 트렌드를 분석해줘"</li>
          <li>"온도 이상이 발생한 라인을 알려줘"</li>
          <li>"최근 품질 불량 원인을 분석해줘"</li>
        </ul>
      </div>
    </div>
  );
}

// =====================================================
// Sessions List
// =====================================================

interface SessionsListProps {
  sessions: ChatSession[];
  currentSessionId: string | null;
  editingSessionId: string | null;
  editingTitle: string;
  onSelectSession: (session: ChatSession) => void;
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void;
  onStartEditing: (session: ChatSession, e: React.MouseEvent) => void;
  onSaveTitle: (sessionId: string) => void;
  onCancelEditing: () => void;
  onEditingTitleChange: (title: string) => void;
}

function SessionsList({
  sessions,
  currentSessionId,
  editingSessionId,
  editingTitle,
  onSelectSession,
  onDeleteSession,
  onStartEditing,
  onSaveTitle,
  onCancelEditing,
  onEditingTitleChange,
}: SessionsListProps) {
  if (sessions.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500">
        <p>대화 기록이 없습니다</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {sessions.map((session) => (
        <div
          key={session.session_id}
          onClick={() => onSelectSession(session)}
          className={`flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 border-b dark:border-slate-800 ${
            currentSessionId === session.session_id
              ? 'bg-purple-50 dark:bg-purple-900/20'
              : ''
          }`}
        >
          <div className="flex-1 min-w-0">
            {editingSessionId === session.session_id ? (
              <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                <input
                  type="text"
                  value={editingTitle}
                  onChange={(e) => onEditingTitleChange(e.target.value)}
                  className="flex-1 px-2 py-1 text-sm border rounded bg-white dark:bg-slate-800 dark:border-slate-700"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') onSaveTitle(session.session_id);
                    if (e.key === 'Escape') onCancelEditing();
                  }}
                />
                <button
                  onClick={() => onSaveTitle(session.session_id)}
                  className="p-1 text-green-600 hover:bg-green-100 rounded"
                >
                  <Check className="w-4 h-4" />
                </button>
                <button
                  onClick={onCancelEditing}
                  className="p-1 text-slate-400 hover:bg-slate-100 rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <>
                <p className="font-medium text-slate-900 dark:text-slate-50 truncate">
                  {session.title}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {new Date(session.updated_at).toLocaleDateString('ko-KR', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </>
            )}
          </div>
          {editingSessionId !== session.session_id && (
            <div className="flex items-center gap-1 ml-2">
              <button
                onClick={(e) => onStartEditing(session, e)}
                className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700 rounded"
                title="제목 수정"
              >
                <Edit3 className="w-4 h-4" />
              </button>
              <button
                onClick={(e) => onDeleteSession(session.session_id, e)}
                className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                title="삭제"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// =====================================================
// Message Bubble
// =====================================================

interface MessageBubbleProps {
  message: ChatMessage;
  onPin: (insightId: string) => void;
  onUnpin: (insightId: string) => void;
}

function MessageBubble({ message, onPin, onUnpin }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  // v2: response_data에 인사이트 데이터가 직접 포함됨 (insight 키 또는 직접)
  const responseData = message.response_data;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const insightData: any = responseData?.insight || ((responseData as any)?.title ? responseData : null);
  const hasInsight = message.response_type === 'insight' && insightData;
  const isPinned = responseData?.pinned;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser
            ? 'bg-blue-100 dark:bg-blue-900/50'
            : 'bg-purple-100 dark:bg-purple-900/50'
        }`}
      >
        {isUser ? (
          <User className="w-4 h-4 text-blue-600 dark:text-blue-400" />
        ) : (
          <Bot className="w-4 h-4 text-purple-600 dark:text-purple-400" />
        )}
      </div>

      {/* Content */}
      <div className={`flex-1 max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        <div
          className={`inline-block p-3 rounded-lg ${
            isUser
              ? 'bg-blue-600 text-white rounded-br-none'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 rounded-bl-none'
          }`}
        >
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Insight Card (v2: 표, 차트, 상태 포함) */}
        {isAssistant && hasInsight && insightData && (
          <Card className="mt-2 border-purple-200 dark:border-purple-800">
            <CardContent className="p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-purple-500" />
                  <span className="text-sm font-medium text-slate-900 dark:text-slate-50">
                    {insightData.title}
                  </span>
                  {/* v2: 상태 배지 */}
                  {insightData.status && (
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        insightData.status === 'critical'
                          ? 'bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-400'
                          : insightData.status === 'warning'
                          ? 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/50 dark:text-yellow-400'
                          : 'bg-green-100 text-green-600 dark:bg-green-900/50 dark:text-green-400'
                      }`}
                    >
                      {insightData.status === 'critical'
                        ? '🚨 위험'
                        : insightData.status === 'warning'
                        ? '⚠️ 주의'
                        : '✅ 정상'}
                    </span>
                  )}
                </div>
                {message.linked_insight_id && (
                  <button
                    onClick={() =>
                      isPinned
                        ? onUnpin(message.linked_insight_id!)
                        : onPin(message.linked_insight_id!)
                    }
                    className={`p-1.5 rounded-lg transition-colors ${
                      isPinned
                        ? 'bg-purple-100 dark:bg-purple-900/50 text-purple-600'
                        : 'hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400'
                    }`}
                    title={isPinned ? '대시보드에서 제거' : '대시보드에 고정'}
                  >
                    {isPinned ? <PinOff className="w-4 h-4" /> : <Pin className="w-4 h-4" />}
                  </button>
                )}
              </div>

              {/* Summary */}
              <p className="text-sm text-slate-600 dark:text-slate-300 mb-3">
                {insightData.summary}
              </p>

              {/* v2: Table Data */}
              {insightData.table_data && insightData.table_data.headers && (
                <div className="mb-3 overflow-x-auto">
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr className="border-b dark:border-slate-700">
                        {insightData.table_data.headers.map((h: string, i: number) => (
                          <th
                            key={i}
                            className="px-2 py-1 text-left font-medium text-slate-700 dark:text-slate-300"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {insightData.table_data.rows?.map((row: (string | number | boolean)[], ri: number) => (
                        <tr key={ri} className="border-b dark:border-slate-800">
                          {row.map((cell, ci) => (
                            <td key={ci} className="px-2 py-1 text-slate-600 dark:text-slate-400">
                              {String(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* v2: Auto Analysis Summary */}
              {insightData.auto_analysis?.has_issues && insightData.auto_analysis?.summary && (
                <div className="mb-3 p-2 bg-orange-50 dark:bg-orange-900/20 rounded text-xs text-orange-700 dark:text-orange-300">
                  ⚠️ {insightData.auto_analysis.summary}
                </div>
              )}

              {/* Actions Preview */}
              {insightData.actions && insightData.actions.length > 0 && (
                <div className="text-xs text-slate-500">
                  <span className="font-medium">권장 조치:</span>{' '}
                  {(insightData.actions[0] as { action?: string })?.action || insightData.actions[0]}
                  {insightData.actions.length > 1 && ` 외 ${insightData.actions.length - 1}건`}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Timestamp */}
        <p className="text-xs text-slate-400 mt-1">
          {new Date(message.created_at).toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
    </div>
  );
}

export default BIChatPanel;
