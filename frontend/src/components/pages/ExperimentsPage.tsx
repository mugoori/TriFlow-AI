/**
 * Experiments Page
 * A/B 테스트 실험 관리 페이지
 */
import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
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
  Plus,
  X,
  Loader2,
} from 'lucide-react';
import {
  Experiment,
  ExperimentStats,
  ExperimentCreate,
  VariantCreate,
  listExperiments,
  getExperimentStats,
  createExperiment,
  startExperiment,
  pauseExperiment,
  resumeExperiment,
  completeExperiment,
  cancelExperiment,
  deleteExperiment,
} from '../../services/experimentService';
import { rulesetService, Ruleset } from '../../services/rulesetService';
import { useToast } from '@/components/ui/Toast';

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
  const { isAuthenticated } = useAuth();
  const toast = useToast();
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null);
  const [stats, setStats] = useState<ExperimentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [showCreateModal, setShowCreateModal] = useState(false);

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
    if (!isAuthenticated) return;
    loadExperiments();
  }, [isAuthenticated, loadExperiments]);

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
      toast.success(`"${exp.name}" 실험이 시작되었습니다.`);
    } catch (err: any) {
      toast.error(err.message || '실험 시작 실패');
    }
  };

  const handlePause = async (exp: Experiment) => {
    try {
      const updated = await pauseExperiment(exp.experiment_id);
      setExperiments(prev => prev.map(e => e.experiment_id === updated.experiment_id ? updated : e));
      if (selectedExperiment?.experiment_id === updated.experiment_id) {
        setSelectedExperiment(updated);
      }
      toast.info(`"${exp.name}" 실험이 일시정지되었습니다.`);
    } catch (err: any) {
      toast.error(err.message || '실험 일시정지 실패');
    }
  };

  const handleResume = async (exp: Experiment) => {
    try {
      const updated = await resumeExperiment(exp.experiment_id);
      setExperiments(prev => prev.map(e => e.experiment_id === updated.experiment_id ? updated : e));
      if (selectedExperiment?.experiment_id === updated.experiment_id) {
        setSelectedExperiment(updated);
      }
      toast.success(`"${exp.name}" 실험이 재개되었습니다.`);
    } catch (err: any) {
      toast.error(err.message || '실험 재개 실패');
    }
  };

  const handleComplete = async (exp: Experiment) => {
    const confirmed = await toast.confirm({
      title: '실험 완료',
      message: `"${exp.name}" 실험을 완료하시겠습니까?`,
      confirmText: '완료',
      cancelText: '취소',
      variant: 'info',
    });
    if (!confirmed) return;
    try {
      const updated = await completeExperiment(exp.experiment_id);
      setExperiments(prev => prev.map(e => e.experiment_id === updated.experiment_id ? updated : e));
      if (selectedExperiment?.experiment_id === updated.experiment_id) {
        setSelectedExperiment(updated);
      }
      toast.success(`"${exp.name}" 실험이 완료되었습니다.`);
    } catch (err: any) {
      toast.error(err.message || '실험 완료 실패');
    }
  };

  const handleCancel = async (exp: Experiment) => {
    const confirmed = await toast.confirm({
      title: '실험 취소',
      message: `"${exp.name}" 실험을 취소하시겠습니까?`,
      confirmText: '취소하기',
      cancelText: '돌아가기',
      variant: 'warning',
    });
    if (!confirmed) return;
    try {
      const updated = await cancelExperiment(exp.experiment_id);
      setExperiments(prev => prev.map(e => e.experiment_id === updated.experiment_id ? updated : e));
      if (selectedExperiment?.experiment_id === updated.experiment_id) {
        setSelectedExperiment(updated);
      }
      toast.warning(`"${exp.name}" 실험이 취소되었습니다.`);
    } catch (err: any) {
      toast.error(err.message || '실험 취소 실패');
    }
  };

  const handleDelete = async (exp: Experiment) => {
    const confirmed = await toast.confirm({
      title: '실험 삭제',
      message: `"${exp.name}" 실험을 삭제하시겠습니까?`,
      confirmText: '삭제',
      cancelText: '취소',
      variant: 'danger',
    });
    if (!confirmed) return;
    try {
      await deleteExperiment(exp.experiment_id);
      setExperiments(prev => prev.filter(e => e.experiment_id !== exp.experiment_id));
      if (selectedExperiment?.experiment_id === exp.experiment_id) {
        setSelectedExperiment(null);
      }
      toast.success(`"${exp.name}" 실험이 삭제되었습니다.`);
    } catch (err: any) {
      toast.error(err.message || '실험 삭제 실패');
    }
  };

  const handleCreateExperiment = async (data: ExperimentCreate) => {
    try {
      const newExperiment = await createExperiment(data);
      setExperiments(prev => [newExperiment, ...prev]);
      setSelectedExperiment(newExperiment);
      setShowCreateModal(false);
      toast.success(`"${newExperiment.name}" 실험이 생성되었습니다.`);
    } catch (err: any) {
      toast.error(err.message || '실험 생성 실패');
      throw err;
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
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowCreateModal(true)}
                className="flex items-center gap-1 px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm"
              >
                <Plus className="w-4 h-4" />
                새 실험
              </button>
              <button
                onClick={loadExperiments}
                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                title="새로고침"
              >
                <RefreshCw className={`w-4 h-4 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
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

      {/* Create Experiment Modal */}
      {showCreateModal && (
        <CreateExperimentModal
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreateExperiment}
        />
      )}
    </div>
  );
}

// =====================================================
// CreateExperimentModal 컴포넌트
// =====================================================

interface CreateExperimentModalProps {
  onClose: () => void;
  onCreate: (data: ExperimentCreate) => Promise<void>;
}

function CreateExperimentModal({ onClose, onCreate }: CreateExperimentModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [hypothesis, setHypothesis] = useState('');
  const [trafficPercentage, setTrafficPercentage] = useState(100);
  const [minSampleSize, setMinSampleSize] = useState(100);
  const [confidenceLevel, setConfidenceLevel] = useState(0.95);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Variants
  const [rulesets, setRulesets] = useState<Ruleset[]>([]);
  const [controlRulesetId, setControlRulesetId] = useState<string>('');
  const [treatmentRulesetId, setTreatmentRulesetId] = useState<string>('');
  const [controlWeight, setControlWeight] = useState(50);

  // Load rulesets for variant selection
  useEffect(() => {
    const loadRulesets = async () => {
      try {
        const response = await rulesetService.list();
        setRulesets(response.rulesets);
      } catch (err) {
        console.error('Failed to load rulesets:', err);
      }
    };
    loadRulesets();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const variants: VariantCreate[] = [];

      // Control variant
      variants.push({
        name: 'Control',
        description: '기존 규칙 (대조군)',
        is_control: true,
        ruleset_id: controlRulesetId || undefined,
        traffic_weight: controlWeight,
      });

      // Treatment variant
      variants.push({
        name: 'Treatment',
        description: '새 규칙 (실험군)',
        is_control: false,
        ruleset_id: treatmentRulesetId || undefined,
        traffic_weight: 100 - controlWeight,
      });

      const data: ExperimentCreate = {
        name: name.trim(),
        description: description.trim() || undefined,
        hypothesis: hypothesis.trim() || undefined,
        traffic_percentage: trafficPercentage,
        min_sample_size: minSampleSize,
        confidence_level: confidenceLevel,
        variants,
      };

      await onCreate(data);
    } catch (err: any) {
      setError(err.message || '실험 생성에 실패했습니다');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50 flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-purple-500" />
              새 실험 만들기
            </h3>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <X className="w-5 h-5 text-slate-500" />
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                실험 이름 *
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="예: 온도 규칙 A/B 테스트"
                className="w-full px-3 py-2 border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 focus:outline-none focus:ring-2 focus:ring-purple-500"
                required
              />
            </div>

            {/* Hypothesis */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                가설
              </label>
              <input
                type="text"
                value={hypothesis}
                onChange={(e) => setHypothesis(e.target.value)}
                placeholder="예: 버전 B가 더 정확한 경고를 생성할 것이다"
                className="w-full px-3 py-2 border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                설명
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="실험에 대한 상세 설명"
                rows={2}
                className="w-full px-3 py-2 border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
              />
            </div>

            {/* Settings Row */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  트래픽 비율 (%)
                </label>
                <input
                  type="number"
                  value={trafficPercentage}
                  onChange={(e) => setTrafficPercentage(Number(e.target.value))}
                  min={1}
                  max={100}
                  className="w-full px-3 py-2 border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  최소 샘플
                </label>
                <input
                  type="number"
                  value={minSampleSize}
                  onChange={(e) => setMinSampleSize(Number(e.target.value))}
                  min={10}
                  className="w-full px-3 py-2 border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  신뢰도 (%)
                </label>
                <input
                  type="number"
                  value={Math.round(confidenceLevel * 100)}
                  onChange={(e) => setConfidenceLevel(Number(e.target.value) / 100)}
                  min={80}
                  max={99}
                  className="w-full px-3 py-2 border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>

            {/* Variants Section */}
            <div className="border-t dark:border-slate-700 pt-4">
              <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-2">
                <Beaker className="w-4 h-4" />
                변형 설정
              </h4>

              <div className="space-y-3">
                {/* Control Variant */}
                <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                      Control (대조군)
                    </span>
                    <span className="text-xs text-blue-600 dark:text-blue-400">
                      {controlWeight}%
                    </span>
                  </div>
                  <select
                    value={controlRulesetId}
                    onChange={(e) => setControlRulesetId(e.target.value)}
                    className="w-full px-3 py-2 text-sm border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50"
                  >
                    <option value="">룰셋 선택 (선택사항)</option>
                    {rulesets.map((rs) => (
                      <option key={rs.ruleset_id} value={rs.ruleset_id}>
                        {rs.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Treatment Variant */}
                <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-purple-700 dark:text-purple-300">
                      Treatment (실험군)
                    </span>
                    <span className="text-xs text-purple-600 dark:text-purple-400">
                      {100 - controlWeight}%
                    </span>
                  </div>
                  <select
                    value={treatmentRulesetId}
                    onChange={(e) => setTreatmentRulesetId(e.target.value)}
                    className="w-full px-3 py-2 text-sm border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50"
                  >
                    <option value="">룰셋 선택 (선택사항)</option>
                    {rulesets.map((rs) => (
                      <option key={rs.ruleset_id} value={rs.ruleset_id}>
                        {rs.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Weight Slider */}
                <div>
                  <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                    트래픽 분배: Control {controlWeight}% / Treatment {100 - controlWeight}%
                  </label>
                  <input
                    type="range"
                    value={controlWeight}
                    onChange={(e) => setControlWeight(Number(e.target.value))}
                    min={10}
                    max={90}
                    step={5}
                    className="w-full"
                  />
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t dark:border-slate-700">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={isLoading || !name.trim()}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    생성 중...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    만들기
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
