/**
 * Experiments Page
 * A/B 테스트 실험 관리 페이지
 */
import { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical,
  Play,
  Pause,
  CheckCircle,
  XCircle,
  RefreshCw,
  Trash2,
  BarChart3,
  Users,
  Beaker,
} from 'lucide-react';
import {
  Experiment,
  ExperimentStats,
  listExperiments,
  getExperimentStats,
  startExperiment,
  pauseExperiment,
  resumeExperiment,
  completeExperiment,
  cancelExperiment,
  deleteExperiment,
} from '../../services/experimentService';

// Status badge colors
const statusColors: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  running: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  paused: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
  completed: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  cancelled: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
};

const statusLabels: Record<string, string> = {
  draft: '초안',
  running: '진행 중',
  paused: '일시정지',
  completed: '완료',
  cancelled: '취소됨',
};

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null);
  const [stats, setStats] = useState<ExperimentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');

  // Load experiments
  const loadExperiments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listExperiments({ status: statusFilter || undefined });
      setExperiments(response.experiments);
    } catch (err) {
      setError('실험 목록을 불러오는데 실패했습니다');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  // Load stats for selected experiment
  const loadStats = useCallback(async (experimentId: string) => {
    setStatsLoading(true);
    try {
      const response = await getExperimentStats(experimentId);
      setStats(response);
    } catch (err) {
      console.error('Failed to load stats:', err);
      setStats(null);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExperiments();
  }, [loadExperiments]);

  useEffect(() => {
    if (selectedExperiment) {
      loadStats(selectedExperiment.experiment_id);
    } else {
      setStats(null);
    }
  }, [selectedExperiment, loadStats]);

  // Lifecycle actions
  const handleStart = async (exp: Experiment) => {
    try {
      const updated = await startExperiment(exp.experiment_id);
      setExperiments(prev => prev.map(e => e.experiment_id === updated.experiment_id ? updated : e));
      if (selectedExperiment?.experiment_id === updated.experiment_id) {
        setSelectedExperiment(updated);
      }
    } catch (err: any) {
      alert(err.message || '실험 시작 실패');
    }
  };

  const handlePause = async (exp: Experiment) => {
    try {
      const updated = await pauseExperiment(exp.experiment_id);
      setExperiments(prev => prev.map(e => e.experiment_id === updated.experiment_id ? updated : e));
      if (selectedExperiment?.experiment_id === updated.experiment_id) {
        setSelectedExperiment(updated);
      }
    } catch (err: any) {
      alert(err.message || '실험 일시정지 실패');
    }
  };

  const handleResume = async (exp: Experiment) => {
    try {
      const updated = await resumeExperiment(exp.experiment_id);
      setExperiments(prev => prev.map(e => e.experiment_id === updated.experiment_id ? updated : e));
      if (selectedExperiment?.experiment_id === updated.experiment_id) {
        setSelectedExperiment(updated);
      }
    } catch (err: any) {
      alert(err.message || '실험 재개 실패');
    }
  };

  const handleComplete = async (exp: Experiment) => {
    if (!confirm('실험을 완료하시겠습니까?')) return;
    try {
      const updated = await completeExperiment(exp.experiment_id);
      setExperiments(prev => prev.map(e => e.experiment_id === updated.experiment_id ? updated : e));
      if (selectedExperiment?.experiment_id === updated.experiment_id) {
        setSelectedExperiment(updated);
      }
    } catch (err: any) {
      alert(err.message || '실험 완료 실패');
    }
  };

  const handleCancel = async (exp: Experiment) => {
    if (!confirm('실험을 취소하시겠습니까?')) return;
    try {
      const updated = await cancelExperiment(exp.experiment_id);
      setExperiments(prev => prev.map(e => e.experiment_id === updated.experiment_id ? updated : e));
      if (selectedExperiment?.experiment_id === updated.experiment_id) {
        setSelectedExperiment(updated);
      }
    } catch (err: any) {
      alert(err.message || '실험 취소 실패');
    }
  };

  const handleDelete = async (exp: Experiment) => {
    if (!confirm('실험을 삭제하시겠습니까?')) return;
    try {
      await deleteExperiment(exp.experiment_id);
      setExperiments(prev => prev.filter(e => e.experiment_id !== exp.experiment_id));
      if (selectedExperiment?.experiment_id === exp.experiment_id) {
        setSelectedExperiment(null);
      }
    } catch (err: any) {
      alert(err.message || '실험 삭제 실패');
    }
  };

  return (
    <div className="flex-1 flex overflow-hidden bg-slate-50 dark:bg-slate-950">
      {/* Left Panel - Experiment List */}
      <div className="w-96 border-r border-slate-200 dark:border-slate-800 flex flex-col bg-white dark:bg-slate-900">
        {/* Header */}
        <div className="p-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <FlaskConical className="w-5 h-5" />
              A/B 테스트
            </h1>
            <button
              onClick={loadExperiments}
              className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title="새로고침"
            >
              <RefreshCw className={`w-4 h-4 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
          >
            <option value="">모든 상태</option>
            <option value="draft">초안</option>
            <option value="running">진행 중</option>
            <option value="paused">일시정지</option>
            <option value="completed">완료</option>
            <option value="cancelled">취소됨</option>
          </select>
        </div>

        {/* Experiment List */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <RefreshCw className="w-6 h-6 text-slate-400 animate-spin" />
            </div>
          ) : error ? (
            <div className="p-4 text-center text-red-500">{error}</div>
          ) : experiments.length === 0 ? (
            <div className="p-8 text-center">
              <FlaskConical className="w-12 h-12 mx-auto mb-4 text-slate-300 dark:text-slate-600" />
              <p className="text-slate-500 dark:text-slate-400 mb-4">
                아직 실험이 없습니다
              </p>
              <p className="text-sm text-slate-400 dark:text-slate-500">
                채팅에서 "A/B 테스트 만들어줘"라고 요청하세요
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {experiments.map((exp) => (
                <div
                  key={exp.experiment_id}
                  onClick={() => setSelectedExperiment(exp)}
                  className={`p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                    selectedExperiment?.experiment_id === exp.experiment_id
                      ? 'bg-purple-50 dark:bg-purple-900/20 border-l-4 border-purple-500'
                      : ''
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-medium text-slate-900 dark:text-white truncate flex-1">
                      {exp.name}
                    </h3>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${statusColors[exp.status]}`}>
                      {statusLabels[exp.status]}
                    </span>
                  </div>
                  {exp.description && (
                    <p className="text-sm text-slate-500 dark:text-slate-400 line-clamp-2 mb-2">
                      {exp.description}
                    </p>
                  )}
                  <div className="flex items-center gap-3 text-xs text-slate-400">
                    <span className="flex items-center gap-1">
                      <Beaker className="w-3 h-3" />
                      {exp.variants.length}개 변형
                    </span>
                    <span>{exp.traffic_percentage}% 트래픽</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right Panel - Detail View */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedExperiment ? (
          <>
            {/* Detail Header */}
            <div className="p-4 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                  {selectedExperiment.name}
                </h2>
                <div className="flex items-center gap-2">
                  {/* Lifecycle Actions */}
                  {selectedExperiment.status === 'draft' && (
                    <>
                      <button
                        onClick={() => handleStart(selectedExperiment)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
                      >
                        <Play className="w-4 h-4" />
                        시작
                      </button>
                      <button
                        onClick={() => handleDelete(selectedExperiment)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm"
                      >
                        <Trash2 className="w-4 h-4" />
                        삭제
                      </button>
                    </>
                  )}
                  {selectedExperiment.status === 'running' && (
                    <>
                      <button
                        onClick={() => handlePause(selectedExperiment)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 text-sm"
                      >
                        <Pause className="w-4 h-4" />
                        일시정지
                      </button>
                      <button
                        onClick={() => handleComplete(selectedExperiment)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
                      >
                        <CheckCircle className="w-4 h-4" />
                        완료
                      </button>
                    </>
                  )}
                  {selectedExperiment.status === 'paused' && (
                    <>
                      <button
                        onClick={() => handleResume(selectedExperiment)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
                      >
                        <Play className="w-4 h-4" />
                        재개
                      </button>
                      <button
                        onClick={() => handleComplete(selectedExperiment)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
                      >
                        <CheckCircle className="w-4 h-4" />
                        완료
                      </button>
                    </>
                  )}
                  {selectedExperiment.status !== 'completed' && selectedExperiment.status !== 'cancelled' && selectedExperiment.status !== 'draft' && (
                    <button
                      onClick={() => handleCancel(selectedExperiment)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-slate-600 text-white rounded-lg hover:bg-slate-700 text-sm"
                    >
                      <XCircle className="w-4 h-4" />
                      취소
                    </button>
                  )}
                </div>
              </div>
              <span className={`px-2 py-0.5 text-xs rounded-full ${statusColors[selectedExperiment.status]}`}>
                {statusLabels[selectedExperiment.status]}
              </span>
            </div>

            {/* Detail Content */}
            <div className="flex-1 overflow-auto p-4 bg-slate-50 dark:bg-slate-950">
              {/* Hypothesis */}
              {selectedExperiment.hypothesis && (
                <div className="mb-6 p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
                  <h3 className="text-sm font-medium text-purple-700 dark:text-purple-300 mb-1">가설</h3>
                  <p className="text-slate-700 dark:text-slate-300">{selectedExperiment.hypothesis}</p>
                </div>
              )}

              {/* Info Cards */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="p-4 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                  <div className="text-2xl font-bold text-slate-900 dark:text-white">
                    {selectedExperiment.traffic_percentage}%
                  </div>
                  <div className="text-sm text-slate-500">트래픽 비율</div>
                </div>
                <div className="p-4 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                  <div className="text-2xl font-bold text-slate-900 dark:text-white">
                    {selectedExperiment.min_sample_size}
                  </div>
                  <div className="text-sm text-slate-500">최소 샘플 수</div>
                </div>
                <div className="p-4 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                  <div className="text-2xl font-bold text-slate-900 dark:text-white">
                    {(selectedExperiment.confidence_level * 100).toFixed(0)}%
                  </div>
                  <div className="text-sm text-slate-500">신뢰 수준</div>
                </div>
              </div>

              {/* Variants */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <Beaker className="w-5 h-5" />
                  변형
                  {statsLoading && (
                    <RefreshCw className="w-4 h-4 text-slate-400 animate-spin" />
                  )}
                </h3>
                <div className="grid gap-4">
                  {selectedExperiment.variants.map((variant) => {
                    const variantStats = stats?.variants.find(v => v.variant_id === variant.variant_id);
                    return (
                      <div
                        key={variant.variant_id}
                        className={`p-4 bg-white dark:bg-slate-900 rounded-lg border ${
                          variant.is_control
                            ? 'border-blue-300 dark:border-blue-700'
                            : 'border-slate-200 dark:border-slate-800'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-900 dark:text-white">
                              {variant.name}
                            </span>
                            {variant.is_control && (
                              <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 rounded-full">
                                Control
                              </span>
                            )}
                          </div>
                          <span className="text-sm text-slate-500">{variant.traffic_weight}%</span>
                        </div>
                        {variant.description && (
                          <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
                            {variant.description}
                          </p>
                        )}

                        {/* Stats for this variant */}
                        {variantStats && (
                          <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
                            <div className="flex items-center gap-4 text-sm">
                              <span className="flex items-center gap-1 text-slate-600 dark:text-slate-400">
                                <Users className="w-4 h-4" />
                                {variantStats.assignment_count}명 할당
                              </span>
                              {Object.entries(variantStats.metrics).map(([name, m]) => (
                                <span key={name} className="flex items-center gap-1 text-slate-600 dark:text-slate-400">
                                  <BarChart3 className="w-4 h-4" />
                                  {name}: {m.mean.toFixed(3)} (n={m.count})
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Stats Summary */}
              {stats && stats.total_assignments > 0 && (
                <div className="p-4 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                    <BarChart3 className="w-5 h-5" />
                    통계 요약
                  </h3>
                  <div className="text-sm text-slate-600 dark:text-slate-400">
                    총 {stats.total_assignments}명 할당
                  </div>
                </div>
              )}

              {/* Timestamps */}
              <div className="mt-6 text-xs text-slate-400 space-y-1">
                <div>생성: {new Date(selectedExperiment.created_at).toLocaleString()}</div>
                {selectedExperiment.start_date && (
                  <div>시작: {new Date(selectedExperiment.start_date).toLocaleString()}</div>
                )}
                {selectedExperiment.end_date && (
                  <div>종료: {new Date(selectedExperiment.end_date).toLocaleString()}</div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-slate-50 dark:bg-slate-950">
            <div className="text-center">
              <FlaskConical className="w-16 h-16 mx-auto mb-4 text-slate-300 dark:text-slate-600" />
              <p className="text-lg text-slate-500 dark:text-slate-400">
                실험을 선택하여 상세 정보를 확인하세요
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
