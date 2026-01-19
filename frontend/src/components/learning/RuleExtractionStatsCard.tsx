/**
 * RuleExtractionStatsCard - 규칙 추출 통계 카드
 * 상태별 후보 수, 추출 성공률, 규칙 추출 트리거
 */

import { useState, useEffect, useCallback } from 'react';
import {
  GitBranch,
  Clock,
  CheckCircle,
  XCircle,
  FlaskConical,
  TrendingUp,
  RefreshCw,
  Play,
  Settings,
} from 'lucide-react';
import {
  ruleExtractionService,
  ExtractionStats,
  RuleExtractionRequest,
  RuleExtractionResponse,
} from '@/services/ruleExtractionService';

interface RuleExtractionStatsCardProps {
  onRefresh?: () => void;
}

export function RuleExtractionStatsCard({ onRefresh }: RuleExtractionStatsCardProps) {
  const [stats, setStats] = useState<ExtractionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [extractResult, setExtractResult] = useState<RuleExtractionResponse | null>(null);
  const [showConfig, setShowConfig] = useState(false);

  // Extraction Config
  const [config, setConfig] = useState<RuleExtractionRequest>({
    min_samples: 20,
    max_depth: 5,
    min_quality_score: 0.7,
  });

  const loadStats = useCallback(async () => {
    try {
      setLoading(true);
      const data = await ruleExtractionService.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load extraction stats:', err);
      // 데모 데이터
      setStats({
        total_candidates: 45,
        pending_count: 12,
        approved_count: 28,
        rejected_count: 3,
        testing_count: 2,
        avg_f1_score: 0.85,
        avg_coverage: 0.72,
        recent_extractions: 8,
        by_category: {
          threshold_adjustment: 18,
          field_correction: 15,
          validation_failure: 8,
          general: 4,
        },
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const handleExtract = async () => {
    try {
      setExtracting(true);
      setExtractResult(null);
      const result = await ruleExtractionService.extractRules(config);
      setExtractResult(result);
      await loadStats();
      onRefresh?.();
    } catch (err) {
      console.error('Failed to extract rules:', err);
    } finally {
      setExtracting(false);
      setShowConfig(false);
    }
  };

  const StatItem = ({
    label,
    value,
    icon: Icon,
    color,
  }: {
    label: string;
    value: number | string;
    icon: React.ElementType;
    color: string;
  }) => (
    <div className="flex items-center gap-3">
      <div className={`p-2 rounded-lg ${color}`}>
        <Icon className="w-4 h-4 text-white" />
      </div>
      <div>
        <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
        <p className="text-lg font-semibold text-gray-900 dark:text-white">{value}</p>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3" />
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-purple-500" />
          <h3 className="font-semibold text-gray-900 dark:text-white">규칙 추출</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadStats}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            title="새로고침"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowConfig(!showConfig)}
            className={`p-2 rounded-lg transition-colors ${
              showConfig
                ? 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400'
                : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
            title="설정"
          >
            <Settings className="w-4 h-4" />
          </button>
          <button
            onClick={handleExtract}
            disabled={extracting}
            className="flex items-center gap-2 px-3 py-1.5 bg-purple-500 text-white text-sm rounded-lg hover:bg-purple-600 disabled:bg-purple-300 transition-colors"
          >
            <Play className="w-4 h-4" />
            {extracting ? '추출 중...' : '규칙 추출'}
          </button>
        </div>
      </div>

      {/* Config Panel */}
      {showConfig && (
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                최소 샘플 수
              </label>
              <input
                type="number"
                value={config.min_samples}
                onChange={(e) =>
                  setConfig({ ...config, min_samples: parseInt(e.target.value) || 20 })
                }
                min={10}
                max={10000}
                className="w-full px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                트리 최대 깊이
              </label>
              <input
                type="number"
                value={config.max_depth}
                onChange={(e) =>
                  setConfig({ ...config, max_depth: parseInt(e.target.value) || 5 })
                }
                min={2}
                max={10}
                className="w-full px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                최소 품질 점수
              </label>
              <input
                type="number"
                value={config.min_quality_score}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    min_quality_score: parseFloat(e.target.value) || 0.7,
                  })
                }
                min={0}
                max={1}
                step={0.1}
                className="w-full px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
              />
            </div>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
          <StatItem
            label="전체"
            value={stats?.total_candidates || 0}
            icon={GitBranch}
            color="bg-purple-500"
          />
          <StatItem
            label="대기 중"
            value={stats?.pending_count || 0}
            icon={Clock}
            color="bg-yellow-500"
          />
          <StatItem
            label="승인됨"
            value={stats?.approved_count || 0}
            icon={CheckCircle}
            color="bg-green-500"
          />
          <StatItem
            label="거부됨"
            value={stats?.rejected_count || 0}
            icon={XCircle}
            color="bg-red-500"
          />
          <StatItem
            label="테스트 중"
            value={stats?.testing_count || 0}
            icon={FlaskConical}
            color="bg-blue-500"
          />
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400 flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                평균 F1 점수
              </span>
              <span className="text-lg font-semibold text-gray-900 dark:text-white">
                {((stats?.avg_f1_score || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
              <div
                className="bg-purple-500 h-2 rounded-full transition-all"
                style={{ width: `${(stats?.avg_f1_score || 0) * 100}%` }}
              />
            </div>
          </div>
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400 flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                평균 커버리지
              </span>
              <span className="text-lg font-semibold text-gray-900 dark:text-white">
                {((stats?.avg_coverage || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all"
                style={{ width: `${(stats?.avg_coverage || 0) * 100}%` }}
              />
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500 dark:text-gray-400">최근 7일 추출</span>
          <span className="font-medium text-gray-900 dark:text-white">
            {stats?.recent_extractions || 0}회
          </span>
        </div>

        {/* Extract Result */}
        {extractResult && (
          <div className="mt-4 p-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
            <p className="text-sm text-purple-700 dark:text-purple-300 font-medium mb-2">
              규칙 추출 완료
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div>
                <span className="text-gray-500 dark:text-gray-400">사용 샘플</span>
                <p className="font-semibold text-gray-900 dark:text-white">
                  {extractResult.samples_used}
                </p>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">트리 깊이</span>
                <p className="font-semibold text-gray-900 dark:text-white">
                  {extractResult.tree_depth}
                </p>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">F1 점수</span>
                <p className="font-semibold text-gray-900 dark:text-white">
                  {(extractResult.metrics.f1_score * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">정확도</span>
                <p className="font-semibold text-gray-900 dark:text-white">
                  {(extractResult.metrics.accuracy * 100).toFixed(1)}%
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default RuleExtractionStatsCard;
