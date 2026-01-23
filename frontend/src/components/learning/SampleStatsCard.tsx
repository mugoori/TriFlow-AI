/**
 * SampleStatsCard - 샘플 통계 카드
 * 상태별 샘플 수, 카테고리별 분포, 피드백 추출 버튼 표시
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Database,
  Clock,
  CheckCircle,
  XCircle,
  Archive,
  TrendingUp,
  RefreshCw,
  Download,
} from 'lucide-react';
import { sampleService, SampleStats, SampleExtractResponse } from '@/services/sampleService';
import { StatItem } from '@/components/ui/StatItem';

interface SampleStatsCardProps {
  onRefresh?: () => void;
}

export function SampleStatsCard({ onRefresh }: SampleStatsCardProps) {
  const [stats, setStats] = useState<SampleStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [extractResult, setExtractResult] = useState<SampleExtractResponse | null>(null);

  const loadStats = useCallback(async () => {
    try {
      setLoading(true);
      const data = await sampleService.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load sample stats:', err);
      // 데모 데이터
      setStats({
        total_count: 256,
        pending_count: 42,
        approved_count: 180,
        rejected_count: 24,
        archived_count: 10,
        by_category: {
          threshold_adjustment: 95,
          field_correction: 78,
          validation_failure: 45,
          general: 38,
        },
        by_source_type: {
          feedback: 180,
          validation: 56,
          manual: 20,
        },
        avg_quality_score: 0.82,
        min_quality_score: 0.45,
        max_quality_score: 0.98,
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
      const result = await sampleService.extractFromFeedback({ days: 7 });
      setExtractResult(result);
      await loadStats();
      onRefresh?.();
    } catch (err) {
      console.error('Failed to extract samples:', err);
    } finally {
      setExtracting(false);
    }
  };

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
          <Database className="w-5 h-5 text-blue-500" />
          <h3 className="font-semibold text-gray-900 dark:text-white">학습 샘플</h3>
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
            onClick={handleExtract}
            disabled={extracting}
            className="flex items-center gap-2 px-3 py-1.5 bg-blue-500 text-white text-sm rounded-lg hover:bg-blue-600 disabled:bg-blue-300 transition-colors"
          >
            <Download className="w-4 h-4" />
            {extracting ? '추출 중...' : '피드백 추출'}
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
          <StatItem
            label="전체"
            value={stats?.total_count || 0}
            icon={Database}
            color="bg-blue-500"
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
            label="보관됨"
            value={stats?.archived_count || 0}
            icon={Archive}
            color="bg-gray-500"
          />
        </div>

        {/* Quality Score */}
        <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600 dark:text-gray-400 flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              평균 품질 점수
            </span>
            <span className="text-lg font-semibold text-gray-900 dark:text-white">
              {((stats?.avg_quality_score || 0) * 100).toFixed(1)}%
            </span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all"
              style={{ width: `${(stats?.avg_quality_score || 0) * 100}%` }}
            />
          </div>
          <div className="flex justify-between mt-1 text-xs text-gray-400">
            <span>최소: {((stats?.min_quality_score || 0) * 100).toFixed(0)}%</span>
            <span>최대: {((stats?.max_quality_score || 0) * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* Category Distribution */}
        {stats?.by_category && Object.keys(stats.by_category).length > 0 && (
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">카테고리별 분포</p>
            <div className="space-y-2">
              {Object.entries(stats.by_category).map(([category, count]) => (
                <div key={category} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700 dark:text-gray-300 capitalize">
                    {category.replace(/_/g, ' ')}
                  </span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                      <div
                        className="bg-blue-400 h-1.5 rounded-full"
                        style={{
                          width: `${(count / (stats.total_count || 1)) * 100}%`,
                        }}
                      />
                    </div>
                    <span className="text-sm text-gray-500 dark:text-gray-400 w-10 text-right">
                      {count}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Extract Result */}
        {extractResult && (
          <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
            <p className="text-sm text-green-700 dark:text-green-300">
              <span className="font-semibold">{extractResult.extracted_count}</span>개 샘플 추출 완료
              {extractResult.skipped_duplicates > 0 && (
                <span className="text-gray-500 dark:text-gray-400 ml-2">
                  (중복 제외: {extractResult.skipped_duplicates})
                </span>
              )}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default SampleStatsCard;
