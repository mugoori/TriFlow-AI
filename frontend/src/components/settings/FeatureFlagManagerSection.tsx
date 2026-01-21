/**
 * Feature Flag Manager Section
 * V2 기능 플래그 관리 UI (Admin 전용)
 */

import { useState, useEffect, useCallback } from 'react';
import { Flag, ToggleLeft, ToggleRight, RefreshCw, Info } from 'lucide-react';
import { featureFlagService, FeatureFlag } from '@/services/featureFlagService';

const FEATURE_DESCRIPTIONS: Record<string, { name: string; description: string; category: string }> = {
  v2_progressive_trust: {
    name: 'Progressive Trust',
    description: 'Trust 점수 기반 의사결정 시스템 (Phase 1)',
    category: 'Foundation',
  },
  v2_data_source_trust: {
    name: 'Data Source Trust',
    description: '데이터 소스별 신뢰도 평가 (Phase 2)',
    category: 'Data Quality',
  },
  v2_knowledge_capture: {
    name: 'Knowledge Capture',
    description: '자동 지식 캡처 및 문서화 (Phase 3)',
    category: 'Learning',
  },
  v2_auto_execution: {
    name: 'Auto Execution',
    description: 'Trust 기반 자동 실행 (Phase 4)',
    category: 'Automation',
  },
  v2_trust_dashboard: {
    name: 'Trust Dashboard',
    description: 'Trust 메트릭 대시보드 UI',
    category: 'UI',
  },
  v2_multi_tenant_config: {
    name: 'Multi-Tenant Config',
    description: '테넌트별 설정 및 격리',
    category: 'Enterprise',
  },
};

export function FeatureFlagManagerSection() {
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);

  const loadFlags = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await featureFlagService.listFlags();
      // Ensure data is an array
      setFlags(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load feature flags:', err);
      setError('기능 플래그를 불러오는데 실패했습니다.');
      setFlags([]); // Set empty array on error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFlags();
  }, [loadFlags]);

  const toggleFlag = async (feature: string, currentlyEnabled: boolean) => {
    try {
      setToggling(feature);
      if (currentlyEnabled) {
        await featureFlagService.disableFlag(feature);
      } else {
        await featureFlagService.enableFlag(feature);
      }
      await loadFlags(); // Reload to get updated state
    } catch (err) {
      console.error(`Failed to toggle ${feature}:`, err);
      setError(`기능 플래그 변경에 실패했습니다: ${feature}`);
    } finally {
      setToggling(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3" />
          <div className="space-y-3">
            {[...Array(6)].map((_, i) => (
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
          <Flag className="w-5 h-5 text-blue-500" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Feature Flags</h3>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            (V2 기능 관리)
          </span>
        </div>
        <button
          onClick={loadFlags}
          disabled={loading}
          className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
          title="새로고침"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Content */}
      <div className="p-4">
        {error && (
          <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 text-sm">
            {error}
          </div>
        )}

        {flags.length === 0 && !loading && (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <Flag className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>사용 가능한 Feature Flag가 없습니다.</p>
          </div>
        )}

        {/* Feature Flags List */}
        <div className="space-y-3">
          {Array.isArray(flags) && flags.map((flag) => {
            const meta = FEATURE_DESCRIPTIONS[flag.feature] || {
              name: flag.feature,
              description: flag.description || 'No description',
              category: 'Other',
            };

            return (
              <div
                key={flag.feature}
                className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-600 transition-colors"
              >
                <div className="flex items-start justify-between">
                  {/* Flag Info */}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-gray-900 dark:text-white">
                        {meta.name}
                      </h4>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                        {meta.category}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                      {meta.description}
                    </p>
                    <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                      <span className="flex items-center gap-1">
                        <Info className="w-3 h-3" />
                        Code: <code className="px-1 py-0.5 bg-gray-200 dark:bg-gray-600 rounded">{flag.feature}</code>
                      </span>
                      {flag.rollout_percentage !== undefined && flag.rollout_percentage < 100 && (
                        <span className="text-orange-600 dark:text-orange-400">
                          Rollout: {flag.rollout_percentage}%
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Toggle Button */}
                  <button
                    onClick={() => toggleFlag(flag.feature, flag.enabled)}
                    disabled={toggling === flag.feature}
                    className={`ml-4 p-2 rounded-lg transition-all ${
                      flag.enabled
                        ? 'bg-green-100 text-green-600 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-900/50'
                        : 'bg-gray-200 text-gray-400 hover:bg-gray-300 dark:bg-gray-600 dark:text-gray-500 dark:hover:bg-gray-500'
                    } ${toggling === flag.feature ? 'opacity-50 cursor-wait' : ''}`}
                    title={flag.enabled ? 'Disable feature' : 'Enable feature'}
                  >
                    {flag.enabled ? (
                      <ToggleRight className="w-6 h-6" />
                    ) : (
                      <ToggleLeft className="w-6 h-6" />
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default FeatureFlagManagerSection;
