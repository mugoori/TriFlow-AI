/**
 * InsightPanel - AI Executive Summary 컴포넌트
 * AWS QuickSight GenBI Executive Summary 기능 구현
 *
 * 구조:
 * - Fact: 객관적 사실 (메트릭, 트렌드)
 * - Reasoning: 원인 분석
 * - Action: 권장 조치 (우선순위별)
 */

import { useState, useEffect } from 'react';
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  Loader2,
  AlertCircle,
  AlertTriangle,
  Lightbulb,
  Target,
  CheckCircle,
  Clock,
  Pin,
  PinOff,
  Table2,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type {
  AIInsight,
  InsightFact,
  InsightReasoning,
  InsightAction,
  TableData,
  AutoAnalysis,
  ComparisonData,
  InsightChart,
  InsightStatus,
} from '@/types/bi';
import { biService } from '@/services/biService';
import { PRIORITY_COLORS } from '@/types/bi';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts';

// =====================================================
// Status Badge 헬퍼
// =====================================================

const STATUS_CONFIG: Record<InsightStatus, { label: string; icon: React.ReactNode; bgColor: string; textColor: string }> = {
  normal: {
    label: '정상',
    icon: <CheckCircle className="w-4 h-4" />,
    bgColor: 'bg-green-100 dark:bg-green-900/50',
    textColor: 'text-green-600 dark:text-green-400',
  },
  warning: {
    label: '주의',
    icon: <AlertTriangle className="w-4 h-4" />,
    bgColor: 'bg-yellow-100 dark:bg-yellow-900/50',
    textColor: 'text-yellow-600 dark:text-yellow-400',
  },
  critical: {
    label: '위험',
    icon: <AlertCircle className="w-4 h-4" />,
    bgColor: 'bg-red-100 dark:bg-red-900/50',
    textColor: 'text-red-600 dark:text-red-400',
  },
};

function StatusBadge({ status }: { status?: InsightStatus }) {
  if (!status) return null;
  const config = STATUS_CONFIG[status];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${config.bgColor} ${config.textColor}`}>
      {config.icon}
      {config.label}
    </span>
  );
}

// =====================================================
// Facts 섹션
// =====================================================

function FactsSection({ facts }: { facts?: InsightFact[] }) {
  if (!facts || facts.length === 0) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Target className="w-4 h-4 text-blue-500" />
        <h5 className="font-medium text-slate-900 dark:text-slate-50">Facts</h5>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {facts.map((fact, index) => (
          <FactCard key={index} fact={fact} />
        ))}
      </div>
    </div>
  );
}

function FactCard({ fact }: { fact: InsightFact }) {
  const TrendIcon = fact.trend === 'up' ? TrendingUp : fact.trend === 'down' ? TrendingDown : Minus;
  const trendColor =
    fact.trend === 'up'
      ? 'text-green-500'
      : fact.trend === 'down'
      ? 'text-red-500'
      : 'text-slate-400';

  return (
    <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-slate-600 dark:text-slate-400">{fact.metric_name}</span>
        <TrendIcon className={`w-4 h-4 ${trendColor}`} />
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-xl font-bold text-slate-900 dark:text-slate-50">
          {typeof fact.current_value === 'number'
            ? fact.current_value.toLocaleString()
            : fact.current_value}
        </span>
        {fact.unit && <span className="text-sm text-slate-500">{fact.unit}</span>}
      </div>
      {fact.change_percent !== undefined && fact.change_percent !== null && (
        <div className={`text-sm mt-1 ${trendColor}`}>
          {fact.change_percent > 0 ? '+' : ''}
          {fact.change_percent.toFixed(1)}%
        </div>
      )}
      <div className="text-xs text-slate-400 mt-1">{fact.period}</div>
    </div>
  );
}

// =====================================================
// v2: Table Data 섹션
// =====================================================

function TableDataSection({ tableData }: { tableData?: TableData }) {
  if (!tableData || !tableData.headers || tableData.headers.length === 0) return null;

  const getHighlightClass = (value: string | number | boolean, header: string): string => {
    if (!tableData.highlight_rules) return '';

    // 간단한 하이라이트 규칙 파싱 (예: "달성률 < 80" -> "critical")
    for (const [rule, status] of Object.entries(tableData.highlight_rules)) {
      if (rule.includes(header)) {
        const numValue = typeof value === 'number' ? value : parseFloat(String(value));
        if (rule.includes('<')) {
          const threshold = parseFloat(rule.split('<')[1]);
          if (numValue < threshold) {
            return status === 'critical' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300' :
                   status === 'warning' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' : '';
          }
        } else if (rule.includes('>')) {
          const threshold = parseFloat(rule.split('>')[1]);
          if (numValue > threshold) {
            return status === 'critical' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300' :
                   status === 'warning' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' : '';
          }
        }
      }
    }
    return '';
  };

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Table2 className="w-4 h-4 text-blue-500" />
        <h5 className="font-medium text-slate-900 dark:text-slate-50">데이터 현황</h5>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b dark:border-slate-700">
              {tableData.headers.map((header, idx) => (
                <th key={idx} className="px-3 py-2 text-left font-medium text-slate-700 dark:text-slate-300">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tableData.rows.map((row, rowIdx) => (
              <tr key={rowIdx} className="border-b dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                {row.map((cell, cellIdx) => {
                  const highlightClass = getHighlightClass(cell, tableData.headers[cellIdx]);
                  return (
                    <td key={cellIdx} className={`px-3 py-2 ${highlightClass}`}>
                      {typeof cell === 'boolean' ? (cell ? '✓' : '✗') : String(cell)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =====================================================
// v2: Auto Analysis 섹션
// =====================================================

function AutoAnalysisSection({ autoAnalysis }: { autoAnalysis?: AutoAnalysis }) {
  if (!autoAnalysis || !autoAnalysis.has_issues) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Activity className="w-4 h-4 text-orange-500" />
        <h5 className="font-medium text-slate-900 dark:text-slate-50">자동 연관 분석</h5>
      </div>
      <div className="p-4 bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800/50 rounded-lg space-y-4">
        {/* Summary */}
        {autoAnalysis.summary && (
          <p className="text-sm text-slate-700 dark:text-slate-300">{autoAnalysis.summary}</p>
        )}

        {/* Triggers */}
        {autoAnalysis.triggers && autoAnalysis.triggers.length > 0 && (
          <div>
            <p className="text-xs font-medium text-orange-700 dark:text-orange-300 mb-2">감지된 이상</p>
            <div className="space-y-2">
              {autoAnalysis.triggers.map((trigger, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm">
                  <AlertTriangle className="w-4 h-4 text-orange-500" />
                  <span className="font-medium">{trigger.line_code}</span>
                  <span className="text-slate-600 dark:text-slate-400">
                    {trigger.type}: {trigger.value.toFixed(1)} (기준: {trigger.threshold})
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Downtime Causes */}
        {autoAnalysis.downtime_causes && autoAnalysis.downtime_causes.length > 0 && (
          <div>
            <p className="text-xs font-medium text-orange-700 dark:text-orange-300 mb-2">비가동 원인</p>
            <div className="space-y-1">
              {autoAnalysis.downtime_causes.map((cause, idx) => (
                <div key={idx} className="flex items-center justify-between text-sm">
                  <span>{cause.reason}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500">{cause.duration_min}분</span>
                    <span className="text-orange-600 dark:text-orange-400 font-medium">
                      {cause.percentage.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Defect Causes */}
        {autoAnalysis.defect_causes && autoAnalysis.defect_causes.length > 0 && (
          <div>
            <p className="text-xs font-medium text-orange-700 dark:text-orange-300 mb-2">불량 원인</p>
            <div className="space-y-1">
              {autoAnalysis.defect_causes.map((cause, idx) => (
                <div key={idx} className="text-sm">
                  <div className="flex items-center justify-between">
                    <span>{cause.defect_type}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500">{cause.qty}건</span>
                      <span className="text-orange-600 dark:text-orange-400 font-medium">
                        {cause.percentage.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  {cause.root_causes && cause.root_causes.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {cause.root_causes.map((root, rIdx) => (
                        <span key={rIdx} className="px-1.5 py-0.5 text-xs bg-orange-100 dark:bg-orange-800/50 text-orange-700 dark:text-orange-300 rounded">
                          {root}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// =====================================================
// v2: Comparison 섹션
// =====================================================

function ComparisonSection({ comparison }: { comparison?: ComparisonData }) {
  if (!comparison) return null;

  const hasYesterday = comparison.vs_yesterday && Object.keys(comparison.vs_yesterday).length > 0;
  const hasLastWeek = comparison.vs_last_week && Object.keys(comparison.vs_last_week).length > 0;

  if (!hasYesterday && !hasLastWeek) return null;

  const renderComparison = (data: Record<string, number | string>, label: string) => (
    <div className="flex-1">
      <p className="text-xs font-medium text-slate-500 mb-2">{label}</p>
      <div className="space-y-1">
        {Object.entries(data).map(([key, value]) => {
          const numValue = typeof value === 'number' ? value : parseFloat(String(value));
          const isPositive = numValue > 0;
          const isNegative = numValue < 0;

          return (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-slate-600 dark:text-slate-400">{key}</span>
              <div className={`flex items-center gap-1 font-medium ${
                isPositive ? 'text-green-600 dark:text-green-400' :
                isNegative ? 'text-red-600 dark:text-red-400' :
                'text-slate-500'
              }`}>
                {isPositive ? <ArrowUpRight className="w-3 h-3" /> :
                 isNegative ? <ArrowDownRight className="w-3 h-3" /> : null}
                {typeof value === 'number' ? `${value > 0 ? '+' : ''}${value.toFixed(1)}%` : value}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp className="w-4 h-4 text-indigo-500" />
        <h5 className="font-medium text-slate-900 dark:text-slate-50">비교 분석</h5>
      </div>
      <div className="flex gap-4 p-4 bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800/50 rounded-lg">
        {hasYesterday && renderComparison(comparison.vs_yesterday!, '전일 대비')}
        {hasYesterday && hasLastWeek && <div className="w-px bg-indigo-200 dark:bg-indigo-800" />}
        {hasLastWeek && renderComparison(comparison.vs_last_week!, '전주 대비')}
      </div>
    </div>
  );
}

// =====================================================
// v2: Charts 섹션
// =====================================================

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

function InsightChartRenderer({ chart }: { chart: InsightChart }) {
  const xKey = chart.x_key || 'name';
  const yKey = chart.y_key || 'value';

  if (chart.chart_type === 'bar') {
    return (
      <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">{chart.title}</p>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chart.data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-slate-700" />
            <XAxis dataKey={xKey} tick={{ fontSize: 12 }} className="text-slate-500" />
            <YAxis tick={{ fontSize: 12 }} className="text-slate-500" />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--tooltip-bg, #fff)',
                borderColor: 'var(--tooltip-border, #e2e8f0)',
                borderRadius: '8px',
              }}
            />
            <Bar dataKey={yKey} radius={[4, 4, 0, 0]}>
              {chart.data.map((_, index) => (
                <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
              ))}
            </Bar>
            {/* Threshold Lines */}
            {chart.threshold_lines?.map((line, idx) => (
              <ReferenceLine
                key={idx}
                y={line.value}
                stroke={line.color || '#ef4444'}
                strokeDasharray="5 5"
                label={{ value: line.label, position: 'right', fontSize: 10 }}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart.chart_type === 'line') {
    return (
      <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">{chart.title}</p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chart.data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-slate-700" />
            <XAxis dataKey={xKey} tick={{ fontSize: 12 }} className="text-slate-500" />
            <YAxis tick={{ fontSize: 12 }} className="text-slate-500" />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--tooltip-bg, #fff)',
                borderColor: 'var(--tooltip-border, #e2e8f0)',
                borderRadius: '8px',
              }}
            />
            <Line
              type="monotone"
              dataKey={yKey}
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ fill: '#3b82f6', r: 4 }}
            />
            {/* Threshold Lines */}
            {chart.threshold_lines?.map((line, idx) => (
              <ReferenceLine
                key={idx}
                y={line.value}
                stroke={line.color || '#ef4444'}
                strokeDasharray="5 5"
                label={{ value: line.label, position: 'right', fontSize: 10 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Fallback for other chart types - just show data as a simple table
  return (
    <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
      <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">{chart.title}</p>
      <p className="text-xs text-slate-500">차트 유형: {chart.chart_type}</p>
      <div className="mt-2 text-xs text-slate-400">
        데이터 항목: {chart.data.length}개
      </div>
    </div>
  );
}

function ChartsSection({ charts }: { charts?: InsightChart[] }) {
  if (!charts || charts.length === 0) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 className="w-4 h-4 text-purple-500" />
        <h5 className="font-medium text-slate-900 dark:text-slate-50">시각화</h5>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {charts.map((chart, idx) => (
          <InsightChartRenderer key={idx} chart={chart} />
        ))}
      </div>
    </div>
  );
}

// =====================================================
// Reasoning 섹션
// =====================================================

function ReasoningSection({ reasoning }: { reasoning?: InsightReasoning }) {
  if (!reasoning) return null;

  const confidence = reasoning.confidence ?? 0;
  const factors = reasoning.contributing_factors ?? [];

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb className="w-4 h-4 text-yellow-500" />
        <h5 className="font-medium text-slate-900 dark:text-slate-50">Reasoning</h5>
        <span className="text-xs text-slate-400">
          (신뢰도: {(confidence * 100).toFixed(0)}%)
        </span>
      </div>
      <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/50 rounded-lg">
        <p className="text-sm text-slate-700 dark:text-slate-300 mb-3">
          {reasoning.analysis || '분석 정보가 없습니다.'}
        </p>
        {factors.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {factors.map((factor, index) => (
              <span
                key={index}
                className="px-2 py-1 text-xs bg-yellow-100 dark:bg-yellow-800/50 text-yellow-700 dark:text-yellow-300 rounded-full"
              >
                {factor}
              </span>
            ))}
          </div>
        )}
        {reasoning.data_quality_notes && (
          <p className="text-xs text-slate-500 mt-2 italic">
            * {reasoning.data_quality_notes}
          </p>
        )}
      </div>
    </div>
  );
}

// =====================================================
// Actions 섹션
// =====================================================

function ActionCard({ action }: { action: InsightAction }) {
  const priorityColor = PRIORITY_COLORS[action.priority];
  const priorityLabel = {
    high: '높음',
    medium: '보통',
    low: '낮음',
  }[action.priority];

  return (
    <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg border-l-4" style={{ borderLeftColor: priorityColor }}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="px-2 py-0.5 text-xs font-medium rounded"
              style={{
                backgroundColor: `${priorityColor}20`,
                color: priorityColor,
              }}
            >
              {priorityLabel}
            </span>
            {action.responsible_team && (
              <span className="text-xs text-slate-400">{action.responsible_team}</span>
            )}
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-300">{action.action}</p>
          {action.expected_impact && (
            <p className="text-xs text-slate-500 mt-1">
              예상 효과: {action.expected_impact}
            </p>
          )}
        </div>
        {action.deadline_suggestion && (
          <div className="flex items-center gap-1 text-xs text-slate-400">
            <Clock className="w-3 h-3" />
            {action.deadline_suggestion}
          </div>
        )}
      </div>
    </div>
  );
}

function ActionsSection({ actions }: { actions?: InsightAction[] }) {
  if (!actions || actions.length === 0) return null;

  // 우선순위별 정렬
  const sortedActions = [...actions].sort((a, b) => {
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    return priorityOrder[a.priority] - priorityOrder[b.priority];
  });

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <CheckCircle className="w-4 h-4 text-green-500" />
        <h5 className="font-medium text-slate-900 dark:text-slate-50">Recommended Actions</h5>
      </div>
      <div className="space-y-3">
        {sortedActions.map((action, index) => (
          <ActionCard key={index} action={action} />
        ))}
      </div>
    </div>
  );
}

// =====================================================
// Feedback 섹션
// =====================================================

function FeedbackSection({
  currentScore,
  onFeedback,
}: {
  currentScore?: number;
  onFeedback: (score: number) => void;
}) {
  return (
    <div className="flex items-center justify-end gap-3 pt-2 border-t dark:border-slate-700">
      <span className="text-sm text-slate-500">이 인사이트가 도움이 되었나요?</span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onFeedback(1)}
          className={`p-2 rounded-lg transition-colors ${
            currentScore === 1
              ? 'bg-green-100 dark:bg-green-900/50 text-green-600'
              : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400'
          }`}
          title="도움됨"
        >
          <ThumbsUp className="w-4 h-4" />
        </button>
        <button
          onClick={() => onFeedback(-1)}
          className={`p-2 rounded-lg transition-colors ${
            currentScore === -1
              ? 'bg-red-100 dark:bg-red-900/50 text-red-600'
              : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400'
          }`}
          title="도움안됨"
        >
          <ThumbsDown className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

// =====================================================
// InsightCard 컴포넌트
// =====================================================

interface InsightCardProps {
  insight: AIInsight;
  isExpanded: boolean;
  onToggle: () => void;
  onFeedback: (score: number) => void;
  isPinned?: boolean;
  onPin?: (insightId: string) => Promise<void>;
  onUnpin?: (insightId: string) => Promise<void>;
}

function InsightCard({
  insight,
  isExpanded,
  onToggle,
  onFeedback,
  isPinned = false,
  onPin,
  onUnpin,
}: InsightCardProps) {
  const [isPinning, setIsPinning] = useState(false);

  const handlePinToggle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isPinning) return;
    setIsPinning(true);
    try {
      if (isPinned && onUnpin) {
        await onUnpin(insight.insight_id);
      } else if (!isPinned && onPin) {
        await onPin(insight.insight_id);
      }
    } finally {
      setIsPinning(false);
    }
  };

  return (
    <Card className={`overflow-hidden ${isPinned ? 'ring-2 ring-purple-500' : ''}`}>
      {/* Header (클릭 가능) */}
      <div
        onClick={onToggle}
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
      >
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="font-semibold text-slate-900 dark:text-slate-50">
              {insight.title}
            </h4>
            <StatusBadge status={insight.status} />
            {isPinned && (
              <span className="px-2 py-0.5 text-xs bg-purple-100 dark:bg-purple-900/50 text-purple-600 dark:text-purple-400 rounded-full">
                고정됨
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 mt-1 line-clamp-2">{insight.summary}</p>
        </div>
        <div className="flex items-center gap-2 ml-4">
          {/* Pin 버튼 */}
          {(onPin || onUnpin) && (
            <button
              onClick={handlePinToggle}
              disabled={isPinning}
              className={`p-2 rounded-lg transition-colors ${
                isPinned
                  ? 'bg-purple-100 dark:bg-purple-900/50 text-purple-600 hover:bg-purple-200'
                  : 'hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-purple-600'
              }`}
              title={isPinned ? '대시보드에서 제거' : '대시보드에 고정'}
            >
              {isPinning ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : isPinned ? (
                <PinOff className="w-4 h-4" />
              ) : (
                <Pin className="w-4 h-4" />
              )}
            </button>
          )}
          <span className="text-xs text-slate-400">
            {new Date(insight.generated_at).toLocaleDateString('ko-KR')}
          </span>
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-slate-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-slate-400" />
          )}
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <CardContent className="border-t dark:border-slate-800 pt-4 space-y-6">
          {/* v2: Table Data Section */}
          <TableDataSection tableData={insight.table_data} />

          {/* Facts Section */}
          <FactsSection facts={insight.facts} />

          {/* v2: Auto Analysis Section */}
          <AutoAnalysisSection autoAnalysis={insight.auto_analysis} />

          {/* Reasoning Section */}
          <ReasoningSection reasoning={insight.reasoning} />

          {/* Actions Section */}
          <ActionsSection actions={insight.actions} />

          {/* v2: Comparison Section */}
          <ComparisonSection comparison={insight.comparison} />

          {/* v2: Charts Section */}
          <ChartsSection charts={insight.charts} />

          {/* Feedback */}
          <FeedbackSection
            currentScore={insight.feedback_score}
            onFeedback={onFeedback}
          />
        </CardContent>
      )}
    </Card>
  );
}

// =====================================================
// InsightPanel 메인 컴포넌트
// =====================================================

interface InsightPanelProps {
  sourceType?: 'chart' | 'dashboard' | 'dataset';
  sourceId?: string;
  onClose?: () => void;
  className?: string;
  pinnedInsightIds?: string[]; // 이미 Pin된 인사이트 ID 목록
  onPinInsight?: (insightId: string) => Promise<void>;
  onUnpinInsight?: (insightId: string) => Promise<void>;
}

export function InsightPanel({
  sourceType = 'dashboard',
  sourceId,
  className = '',
  pinnedInsightIds = [],
  onPinInsight,
  onUnpinInsight,
}: InsightPanelProps) {
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedInsightId, setExpandedInsightId] = useState<string | null>(null);

  // 인사이트 목록 로드
  useEffect(() => {
    loadInsights();
  }, [sourceType, sourceId]);

  const loadInsights = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await biService.getInsights({
        source_type: sourceType,
        source_id: sourceId,
        page_size: 10,
      });
      setInsights(response.insights);
      // 첫 번째 인사이트 자동 확장
      if (response.insights.length > 0) {
        setExpandedInsightId(response.insights[0].insight_id);
      }
    } catch (err) {
      console.error('Failed to load insights:', err);
      setError(err instanceof Error ? err.message : 'Failed to load insights');
    } finally {
      setIsLoading(false);
    }
  };

  const generateNewInsight = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const response = await biService.generateInsight({
        source_type: sourceType,
        source_id: sourceId,
      });
      setInsights((prev) => [response.insight, ...prev]);
      setExpandedInsightId(response.insight.insight_id);
    } catch (err) {
      console.error('Failed to generate insight:', err);
      setError(err instanceof Error ? err.message : 'Failed to generate insight');
    } finally {
      setIsGenerating(false);
    }
  };

  const submitFeedback = async (insightId: string, score: number) => {
    try {
      const updated = await biService.submitInsightFeedback(insightId, { score });
      setInsights((prev) =>
        prev.map((i) => (i.insight_id === insightId ? updated : i))
      );
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    }
  };

  const toggleExpand = (insightId: string) => {
    setExpandedInsightId((prev) => (prev === insightId ? null : insightId));
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-purple-500" />
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
            AI Executive Summary
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={generateNewInsight}
            disabled={isGenerating}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
          >
            {isGenerating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            새 인사이트 생성
          </button>
          <button
            onClick={loadInsights}
            disabled={isLoading}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="새로고침"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-sm">
            <AlertCircle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Loading */}
      {isLoading && insights.length === 0 && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
        </div>
      )}

      {/* Empty State */}
      {!isLoading && insights.length === 0 && (
        <Card>
          <CardContent className="py-12">
            <div className="text-center text-slate-500">
              <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium mb-2">인사이트가 없습니다</p>
              <p className="text-sm mb-4">
                "새 인사이트 생성" 버튼을 클릭하여 AI 분석을 시작하세요
              </p>
              <button
                onClick={generateNewInsight}
                disabled={isGenerating}
                className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
              >
                {isGenerating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                인사이트 생성
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Insight Cards */}
      {insights.map((insight) => (
        <InsightCard
          key={insight.insight_id}
          insight={insight}
          isExpanded={expandedInsightId === insight.insight_id}
          onToggle={() => toggleExpand(insight.insight_id)}
          onFeedback={(score) => submitFeedback(insight.insight_id, score)}
          isPinned={pinnedInsightIds.includes(insight.insight_id)}
          onPin={onPinInsight}
          onUnpin={onUnpinInsight}
        />
      ))}
    </div>
  );
}

export default InsightPanel;
