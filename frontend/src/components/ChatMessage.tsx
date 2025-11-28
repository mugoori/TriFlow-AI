/**
 * ChatMessage Component
 * 채팅 메시지를 렌더링하는 컴포넌트
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight, Pin, Check, FileCode, ExternalLink } from 'lucide-react';
import type { ChatMessage as ChatMessageType } from '../types/agent';
import type { ChartConfig } from '../types/chart';
import { Card, CardContent } from './ui/card';
import { ChartRenderer } from './charts';
import { useDashboard } from '../contexts/DashboardContext';

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

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const [showDetails, setShowDetails] = useState(false);
  const { addChart, hasChart } = useDashboard();

  // Check if this message contains chart data from BI Agent
  const chartConfig = extractChartConfig(message);

  // 차트가 이미 대시보드에 고정되어 있는지 확인
  const isChartPinned = chartConfig ? hasChart(chartConfig) : false;

  // Extract reasoning summary from tool calls
  const reasoningSummary = extractReasoningSummary(message);

  // Check if this message contains ruleset creation result
  const rulesetResult = extractRulesetCreationResult(message);

  // 대시보드에 차트 고정
  const handlePinChart = () => {
    if (chartConfig && !isChartPinned) {
      addChart(chartConfig, chartConfig.title);
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
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

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
 * Extract chart configuration from BI Agent's tool calls
 */
function extractChartConfig(message: ChatMessageType): ChartConfig | null {
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
