/**
 * ChatMessage Component
 * 채팅 메시지를 렌더링하는 컴포넌트
 */

import { useState, useMemo, memo } from 'react';
import { ChevronDown, ChevronRight, Pin, Check, FileCode, ExternalLink, ThumbsUp, ThumbsDown, MessageSquare } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import type { ChatMessage as ChatMessageType } from '../types/agent';
import type { ChartConfig } from '../types/chart';
import { Card, CardContent } from './ui/card';
import { ChartRenderer } from './charts';
import { useDashboard } from '../contexts/DashboardContext';
import { sendQuickFeedback } from '../services/feedbackService';
import { FeedbackModal } from './FeedbackModal';

// Ruleset 생성 결과 타입
interface RulesetCreationResult {
  success: boolean;
  ruleset_id: string;
  name: string;
  description?: string;
  rhai_script?: string;
  message?: string;
}

interface ChatMessageProps {
  message: ChatMessageType;
}

export const ChatMessage = memo(function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const [showDetails, setShowDetails] = useState(false);
  const [feedbackState, setFeedbackState] = useState<'none' | 'positive' | 'negative'>('none');
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [isSendingFeedback, setIsSendingFeedback] = useState(false);
  const { addChart, hasChart } = useDashboard();

  // Memoize expensive extractions to avoid recalculation on every render
  const chartConfig = useMemo(() => extractChartConfig(message), [message]);
  const reasoningSummary = useMemo(() => extractReasoningSummary(message), [message]);
  const rulesetResult = useMemo(() => extractRulesetCreationResult(message), [message]);

  // 차트가 이미 대시보드에 고정되어 있는지 확인
  const isChartPinned = chartConfig ? hasChart(chartConfig) : false;

  // 대시보드에 차트 고정
  const handlePinChart = () => {
    if (chartConfig && !isChartPinned) {
      addChart(chartConfig, chartConfig.title);
    }
  };

  // 빠른 피드백 전송 (수정 가능)
  const handleQuickFeedback = async (type: 'positive' | 'negative') => {
    if (isSendingFeedback) return;

    // 같은 타입 클릭 시 취소 (none으로 복원)
    if (feedbackState === type) {
      setFeedbackState('none');
      return;
    }

    setIsSendingFeedback(true);
    try {
      await sendQuickFeedback(
        type,
        message.id || `msg-${message.timestamp}`,
        message.agent_name,
        { content: message.content, tool_calls: message.tool_calls }
      );
      setFeedbackState(type);
    } catch (error) {
      console.error('Failed to send feedback:', error);
    } finally {
      setIsSendingFeedback(false);
    }
  };

  // 상세 피드백 모달 열기
  const handleOpenFeedbackModal = () => {
    setShowFeedbackModal(true);
  };

  // 상세 피드백 제출 완료
  const handleFeedbackSubmit = () => {
    setFeedbackState('negative'); // 상세 피드백은 보통 부정적일 때 사용
    setShowFeedbackModal(false);
  };

  // 탭 네비게이션 링크를 처리하는 커스텀 마크다운 컴포넌트
  const markdownComponents: Components = {
    a: ({ href, children }) => {
      // #tab- 으로 시작하는 링크는 탭 네비게이션으로 처리
      if (href && href.startsWith('#tab-')) {
        const tabName = href.replace('#tab-', '');
        return (
          <button
            onClick={() => {
              window.dispatchEvent(new CustomEvent('navigate-to-tab', {
                detail: { tab: tabName }
              }));
            }}
            className="text-blue-600 dark:text-blue-400 hover:underline cursor-pointer font-medium"
          >
            {children}
          </button>
        );
      }
      // 일반 링크는 새 탭에서 열기
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">
          {children}
        </a>
      );
    }
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`${chartConfig ? 'max-w-[95%]' : 'max-w-[80%]'} ${isUser ? 'ml-auto' : 'mr-auto'}`}>
        <Card className={isUser ? 'bg-blue-50 dark:bg-blue-950' : 'bg-slate-50 dark:bg-slate-900'}>
          <CardContent className="p-4">
            {/* 메시지 헤더 */}
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                {isUser ? '사용자' : 'TriFlow Agent'}
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-500">
                {new Date(message.timestamp).toLocaleTimeString('ko-KR', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>

            {/* 메시지 내용 */}
            <div className="text-sm text-slate-900 dark:text-slate-100 prose-chat">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {message.content}
              </ReactMarkdown>
            </div>

            {/* Chart Visualization */}
            {chartConfig && (
              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {chartConfig.title || '차트'}
                  </span>
                  <button
                    onClick={handlePinChart}
                    disabled={isChartPinned}
                    className={`flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors ${
                      isChartPinned
                        ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 cursor-default'
                        : 'bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-300 dark:hover:bg-blue-800'
                    }`}
                  >
                    {isChartPinned ? (
                      <>
                        <Check className="w-3 h-3" />
                        고정됨
                      </>
                    ) : (
                      <>
                        <Pin className="w-3 h-3" />
                        대시보드에 고정
                      </>
                    )}
                  </button>
                </div>
                <ChartRenderer config={chartConfig} />
              </div>
            )}

            {/* Ruleset Creation Result */}
            {rulesetResult && rulesetResult.success && (
              <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <FileCode className="w-4 h-4 text-green-600 dark:text-green-400" />
                  <span className="text-sm font-medium text-green-700 dark:text-green-300">
                    규칙이 생성되었습니다
                  </span>
                </div>
                <div className="text-sm text-green-800 dark:text-green-200">
                  <div className="font-medium">{rulesetResult.name}</div>
                  {rulesetResult.description && (
                    <div className="text-xs text-green-600 dark:text-green-400 mt-1">
                      {rulesetResult.description}
                    </div>
                  )}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <span className="text-xs text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/50 px-2 py-0.5 rounded">
                    비활성 (테스트 필요)
                  </span>
                  <button
                    onClick={() => {
                      // Rulesets 탭으로 이동하는 이벤트 발행
                      window.dispatchEvent(new CustomEvent('navigate-to-rulesets', {
                        detail: { rulesetId: rulesetResult.ruleset_id }
                      }));
                    }}
                    className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Rulesets에서 확인
                  </button>
                </div>
              </div>
            )}

            {/* 간단한 근거 표시 (사용자 메시지가 아닐 때만) */}
            {!isUser && reasoningSummary && (
              <div className="mt-3 pt-2 border-t border-slate-200 dark:border-slate-700">
                <div className="text-xs text-slate-500 dark:text-slate-400 italic">
                  {reasoningSummary}
                </div>

                {/* 상세 정보 토글 (개발 모드용) */}
                {message.tool_calls && message.tool_calls.length > 0 && (
                  <button
                    onClick={() => setShowDetails(!showDetails)}
                    className="flex items-center gap-1 mt-2 text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                  >
                    {showDetails ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    상세 정보
                  </button>
                )}

                {/* 상세 Tool 호출 정보 (접힌 상태) */}
                {showDetails && message.tool_calls && message.tool_calls.length > 0 && (
                  <div className="mt-2 space-y-2">
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
              </div>
            )}

            {/* 처리 에이전트 정보 + 피드백 버튼 (AI 응답에만 표시) */}
            {!isUser && (
              <div className="mt-3 pt-2 border-t border-slate-200 dark:border-slate-700 flex items-center gap-2">
                {/* 처리 에이전트 표시 */}
                {message.agent_name && (
                  <span className="text-xs text-slate-400 dark:text-slate-500 mr-2">
                    <span className="font-medium">처리:</span> {message.agent_name}
                  </span>
                )}
                <span className="text-xs text-slate-400 dark:text-slate-500 mr-1">도움이 되었나요?</span>

                {/* 좋아요 버튼 */}
                <button
                  onClick={() => handleQuickFeedback('positive')}
                  disabled={isSendingFeedback}
                  className={`p-1.5 rounded transition-colors ${
                    feedbackState === 'positive'
                      ? 'bg-green-100 text-green-600 dark:bg-green-900/50 dark:text-green-400'
                      : 'hover:bg-green-50 text-slate-400 hover:text-green-600 dark:hover:bg-green-900/30 dark:hover:text-green-400'
                  }`}
                  title={feedbackState === 'positive' ? '클릭하여 취소' : '도움이 되었어요'}
                >
                  <ThumbsUp className={`w-4 h-4 ${feedbackState === 'positive' ? 'fill-current' : ''}`} />
                </button>

                {/* 싫어요 버튼 */}
                <button
                  onClick={() => handleQuickFeedback('negative')}
                  disabled={isSendingFeedback}
                  className={`p-1.5 rounded transition-colors ${
                    feedbackState === 'negative'
                      ? 'bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-400'
                      : 'hover:bg-red-50 text-slate-400 hover:text-red-600 dark:hover:bg-red-900/30 dark:hover:text-red-400'
                  }`}
                  title={feedbackState === 'negative' ? '클릭하여 취소' : '도움이 안 되었어요'}
                >
                  <ThumbsDown className={`w-4 h-4 ${feedbackState === 'negative' ? 'fill-current' : ''}`} />
                </button>

                {/* 상세 피드백 버튼 */}
                <button
                  onClick={handleOpenFeedbackModal}
                  disabled={isSendingFeedback}
                  className="p-1.5 rounded transition-colors hover:bg-blue-50 text-slate-400 hover:text-blue-600 dark:hover:bg-blue-900/30 dark:hover:text-blue-400"
                  title="상세 피드백 작성"
                >
                  <MessageSquare className="w-4 h-4" />
                </button>

                {/* 피드백 상태 표시 */}
                {feedbackState !== 'none' && (
                  <span className="text-xs text-slate-400 dark:text-slate-500 ml-2">
                    {feedbackState === 'positive' ? '좋아요' : '개선 필요'} · 클릭하여 변경
                  </span>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 피드백 모달 */}
        <FeedbackModal
          isOpen={showFeedbackModal}
          onClose={() => setShowFeedbackModal(false)}
          onSubmit={handleFeedbackSubmit}
          messageId={message.id || `msg-${message.timestamp}`}
          agentType={message.agent_name}
          originalOutput={{ content: message.content, tool_calls: message.tool_calls }}
        />
      </div>
    </div>
  );
});

/**
 * Extract a brief reasoning summary from tool calls
 */
function extractReasoningSummary(message: ChatMessageType): string | null {
  if (!message.tool_calls || message.tool_calls.length === 0) {
    return null;
  }

  // Try to find classify_intent or route_request for reasoning
  const classifyTool = message.tool_calls.find(tc => tc.tool === 'classify_intent');
  const routeTool = message.tool_calls.find(tc => tc.tool === 'route_request');

  // Extract reason from classify_intent
  if (classifyTool?.input) {
    const input = classifyTool.input as { intent?: string; confidence?: number; reason?: string };
    if (input.reason) {
      const confidence = input.confidence ? ` (${Math.round(input.confidence * 100)}%)` : '';
      return `${input.reason}${confidence}`;
    }
  }

  // Extract from route_request
  if (routeTool?.input) {
    const input = routeTool.input as { target_agent?: string; processed_request?: string };
    if (input.target_agent) {
      const agentNames: Record<string, string> = {
        'general': '일반 응답',
        'judgment': '판단 에이전트',
        'workflow': '워크플로우 에이전트',
        'bi': 'BI 에이전트',
      };
      return `→ ${agentNames[input.target_agent] || input.target_agent}`;
    }
  }

  return null;
}

/**
 * Extract chart configuration from BI Agent's tool calls or response_data
 *
 * In streaming mode (SSE), tool_calls.result is null, so we check response_data.charts as fallback
 */
function extractChartConfig(message: ChatMessageType): ChartConfig | null {
  // Method 1: Check response_data.charts (SSE streaming mode)
  // This is the primary source in streaming mode where tool results are not included
  if (message.response_data?.charts && Array.isArray(message.response_data.charts) && message.response_data.charts.length > 0) {
    const chartConfig = message.response_data.charts[0];
    if (chartConfig && typeof chartConfig === 'object' && 'type' in chartConfig && 'data' in chartConfig) {
      return chartConfig as ChartConfig;
    }
  }

  // Method 2: Check tool_calls (non-streaming mode)
  if (!message.tool_calls || message.tool_calls.length === 0) {
    return null;
  }

  // Find generate_chart_config tool call
  const chartTool = message.tool_calls.find(
    (tc) => tc.tool === 'generate_chart_config'
  );

  if (!chartTool || !chartTool.result) {
    return null;
  }

  // Extract chart config from result
  try {
    const result = chartTool.result;

    // Backend returns: { success: true, config: { type, data, ... } }
    // Or directly: { type, data, ... }
    let config = result;

    // Check if result is wrapped in { success, config } structure
    if (result && typeof result === 'object' && 'success' in result && 'config' in result) {
      if (!result.success) {
        console.warn('Chart config generation failed:', result.error);
        return null;
      }
      config = result.config;
    }

    // Check if config has the expected structure
    if (
      config &&
      typeof config === 'object' &&
      'type' in config &&
      'data' in config
    ) {
      return config as ChartConfig;
    }

    return null;
  } catch (error) {
    console.error('Failed to extract chart config:', error);
    return null;
  }
}

/**
 * Extract ruleset creation result from create_ruleset tool call
 */
function extractRulesetCreationResult(message: ChatMessageType): RulesetCreationResult | null {
  if (!message.tool_calls || message.tool_calls.length === 0) {
    return null;
  }

  // Find create_ruleset tool call
  const rulesetTool = message.tool_calls.find(
    (tc) => tc.tool === 'create_ruleset'
  );

  if (!rulesetTool || !rulesetTool.result) {
    return null;
  }

  try {
    const result = rulesetTool.result;

    // Check if it has the expected structure
    if (
      result &&
      typeof result === 'object' &&
      'success' in result &&
      'ruleset_id' in result
    ) {
      return result as RulesetCreationResult;
    }

    return null;
  } catch (error) {
    console.error('Failed to extract ruleset creation result:', error);
    return null;
  }
}
