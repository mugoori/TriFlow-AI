/**
 * DynamicStatCard
 * DB 설정 기반 동적 StatCard 컴포넌트
 *
 * 특징:
 * - 3가지 소스 타입 지원 (KPI, DB Query, MCP Tool)
 * - 상태별 색상 표시 (green/yellow/red/gray)
 * - 변화율 및 추세 표시
 * - 편집/삭제 액션
 */

import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  MoreVertical,
  Edit2,
  Trash2,
  RefreshCw,
  Database,
  Plug,
  AlertTriangle,
  Activity,
  Clock,
  Factory,
  Gauge,
  Thermometer,
  Droplets,
  Zap,
  Target,
  Package,
  Settings,
  Loader2,
} from 'lucide-react';
import type { StatCardWithValue, StatusType, TrendType, SourceType } from '@/types/statcard';
import { SOURCE_TYPE_INFO } from '@/types/statcard';

// Lucide 아이콘 매핑
const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  Database,
  Plug,
  AlertTriangle,
  Activity,
  Clock,
  Factory,
  Gauge,
  Thermometer,
  Droplets,
  Zap,
  Target,
  Package,
  Settings,
};

// 상태별 배경색
const STATUS_BG_COLORS: Record<StatusType, string> = {
  green: 'bg-green-500/10',
  yellow: 'bg-yellow-500/10',
  red: 'bg-red-500/10',
  gray: 'bg-slate-500/10',
};

// 상태별 아이콘 색상
const STATUS_ICON_COLORS: Record<StatusType, string> = {
  green: 'text-green-500',
  yellow: 'text-yellow-500',
  red: 'text-red-500',
  gray: 'text-slate-500',
};

// 추세 아이콘 및 색상
const TREND_CONFIG: Record<TrendType, { icon: React.ComponentType<{ className?: string }>; color: string; label: string }> = {
  up: { icon: TrendingUp, color: 'text-green-500', label: '상승' },
  down: { icon: TrendingDown, color: 'text-red-500', label: '하락' },
  stable: { icon: Minus, color: 'text-slate-500', label: '유지' },
};

// 소스 타입별 뱃지 색상
const SOURCE_BADGE_COLORS: Record<SourceType, string> = {
  kpi: 'bg-blue-500/10 text-blue-500',
  db_query: 'bg-purple-500/10 text-purple-500',
  mcp_tool: 'bg-orange-500/10 text-orange-500',
};

interface DynamicStatCardProps {
  card: StatCardWithValue;
  onEdit?: (configId: string) => void;
  onDelete?: (configId: string) => void;
  onRefresh?: (configId: string) => void;
  showActions?: boolean;
  isRefreshing?: boolean;
}

export function DynamicStatCard({
  card,
  onEdit,
  onDelete,
  onRefresh,
  showActions = true,
  isRefreshing = false,
}: DynamicStatCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const { config, value } = card;

  // 아이콘 결정
  const iconName = value.icon || 'BarChart3';
  const IconComponent = ICON_MAP[iconName] || BarChart3;

  // 추세 아이콘
  const trendConfig = value.trend ? TREND_CONFIG[value.trend] : null;
  const TrendIcon = trendConfig?.icon;

  // 상태 색상
  const statusBgColor = STATUS_BG_COLORS[value.status];
  const statusIconColor = STATUS_ICON_COLORS[value.status];

  // 변화율 표시
  const changeText = value.change_percent !== undefined && value.change_percent !== null
    ? `${value.change_percent >= 0 ? '+' : ''}${value.change_percent.toFixed(1)}%`
    : null;

  return (
    <Card className="relative group">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            {/* 제목 */}
            <p className="text-sm text-slate-600 dark:text-slate-400 truncate">
              {value.title}
            </p>

            {/* 값 */}
            <div className="flex items-baseline gap-1 mt-1">
              {isRefreshing ? (
                <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
              ) : (
                <>
                  <span className="text-2xl font-bold">
                    {value.formatted_value ?? (value.value?.toLocaleString() ?? '-')}
                  </span>
                  {value.unit && (
                    <span className="text-sm text-slate-500">{value.unit}</span>
                  )}
                </>
              )}
            </div>

            {/* 변화율 및 추세 */}
            {(changeText || trendConfig) && (
              <div className="flex items-center gap-2 mt-1">
                {TrendIcon && (
                  <TrendIcon className={`w-3 h-3 ${trendConfig?.color}`} />
                )}
                {changeText && (
                  <span className={`text-xs ${trendConfig?.color || 'text-slate-500'}`}>
                    {changeText}
                  </span>
                )}
                <span className="text-xs text-slate-400">
                  {value.comparison_label || 'vs 이전'}
                </span>
              </div>
            )}

            {/* 소스 타입 뱃지 */}
            <div className="flex items-center gap-2 mt-2">
              <span className={`text-xs px-1.5 py-0.5 rounded ${SOURCE_BADGE_COLORS[config.source_type]}`}>
                {SOURCE_TYPE_INFO[config.source_type].label}
              </span>
              {value.is_cached && (
                <span className="text-xs text-slate-400">(캐시됨)</span>
              )}
            </div>
          </div>

          {/* 아이콘 */}
          <div className={`p-3 ${statusBgColor} rounded-lg flex-shrink-0`}>
            <IconComponent className={`w-6 h-6 ${statusIconColor}`} />
          </div>
        </div>

        {/* 액션 메뉴 */}
        {showActions && (
          <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <div className="relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <MoreVertical className="w-4 h-4 text-slate-400" />
              </button>

              {showMenu && (
                <>
                  {/* Backdrop */}
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setShowMenu(false)}
                  />
                  {/* Menu */}
                  <div className="absolute right-0 top-6 z-20 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 min-w-[120px]">
                    {onRefresh && (
                      <button
                        onClick={() => {
                          setShowMenu(false);
                          onRefresh(config.config_id);
                        }}
                        className="w-full px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2"
                      >
                        <RefreshCw className="w-4 h-4" />
                        새로고침
                      </button>
                    )}
                    {onEdit && (
                      <button
                        onClick={() => {
                          setShowMenu(false);
                          onEdit(config.config_id);
                        }}
                        className="w-full px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2"
                      >
                        <Edit2 className="w-4 h-4" />
                        편집
                      </button>
                    )}
                    {onDelete && (
                      <button
                        onClick={() => {
                          setShowMenu(false);
                          onDelete(config.config_id);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
                      >
                        <Trash2 className="w-4 h-4" />
                        삭제
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * 카드 추가 버튼 컴포넌트
 */
interface AddStatCardButtonProps {
  onClick: () => void;
}

export function AddStatCardButton({ onClick }: AddStatCardButtonProps) {
  return (
    <Card
      className="border-dashed border-2 border-slate-300 dark:border-slate-600 hover:border-blue-500 dark:hover:border-blue-400 cursor-pointer transition-colors"
      onClick={onClick}
    >
      <CardContent className="pt-6 flex items-center justify-center min-h-[120px]">
        <div className="text-center">
          <div className="w-10 h-10 mx-auto rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
            <span className="text-2xl text-slate-400">+</span>
          </div>
          <p className="text-sm text-slate-500 mt-2">카드 추가</p>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * 로딩 중인 카드 스켈레톤
 */
export function StatCardSkeleton() {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between animate-pulse">
          <div className="flex-1">
            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-20" />
            <div className="h-8 bg-slate-200 dark:bg-slate-700 rounded w-32 mt-2" />
            <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-16 mt-2" />
          </div>
          <div className="w-12 h-12 bg-slate-200 dark:bg-slate-700 rounded-lg" />
        </div>
      </CardContent>
    </Card>
  );
}
