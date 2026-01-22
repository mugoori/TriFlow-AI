/**
 * JudgmentPage
 * Judgment 직접 실행 및 결과 분석 페이지
 */
import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Brain,
  Play,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  XCircle,
  TrendingUp,
  FileText,
  Zap,
  History,
} from 'lucide-react';
import { rulesetService, type Ruleset } from '@/services/rulesetService';
import {
  judgmentService,
  type JudgmentExecuteRequest,
  type JudgmentExecuteResponse,
} from '@/services/judgmentService';
import { useToast } from '@/components/ui/Toast';

const POLICY_OPTIONS = [
  { value: 'rule_only', label: 'Rule Only', desc: '룰만 사용 (빠름)' },
  { value: 'llm_only', label: 'LLM Only', desc: 'LLM만 사용 (유연)' },
  { value: 'hybrid_weighted', label: 'Hybrid Weighted', desc: 'Rule + LLM 가중 조합 (권장)' },
  { value: 'hybrid_gate', label: 'Hybrid Gate', desc: '룰 신뢰도 기반 게이트' },
  { value: 'rule_fallback', label: 'Rule Fallback', desc: '룰 우선, 실패 시 LLM' },
  { value: 'llm_fallback', label: 'LLM Fallback', desc: 'LLM 우선, 실패 시 룰' },
  { value: 'escalate', label: 'Escalate', desc: '룰 불확실 시 LLM' },
];

const DECISION_COLORS = {
  OK: 'text-green-600 bg-green-100 dark:bg-green-900/30',
  WARNING: 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30',
  CRITICAL: 'text-red-600 bg-red-100 dark:bg-red-900/30',
  UNKNOWN: 'text-gray-600 bg-gray-100 dark:bg-gray-700',
};

const DECISION_ICONS = {
  OK: CheckCircle,
  WARNING: AlertTriangle,
  CRITICAL: XCircle,
  UNKNOWN: FileText,
};

export default function JudgmentPage() {
  const { isAuthenticated } = useAuth();
  const toast = useToast();

  // Ruleset 목록
  const [rulesets, setRulesets] = useState<Ruleset[]>([]);
  const [loadingRulesets, setLoadingRulesets] = useState(true);

  // 실행 설정
  const [selectedRulesetId, setSelectedRulesetId] = useState<string>('');
  const [inputData, setInputData] = useState('{\n  "temperature": 75,\n  "pressure": 8.5,\n  "humidity": 65\n}');
  const [policy, setPolicy] = useState<string>('hybrid_weighted');
  const [needExplanation, setNeedExplanation] = useState(true);

  // 실행 상태
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<JudgmentExecuteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 최근 실행 이력
  const [recentExecutions, setRecentExecutions] = useState<any[]>([]);

  // Ruleset 목록 로드
  const loadRulesets = async () => {
    setLoadingRulesets(true);
    try {
      const response = await rulesetService.list({ is_active: true });
      setRulesets(response.rulesets);
      if (response.rulesets.length > 0 && !selectedRulesetId) {
        setSelectedRulesetId(response.rulesets[0].ruleset_id);
      }
    } catch (err) {
      console.error('Failed to load rulesets:', err);
      toast.error('Ruleset 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoadingRulesets(false);
    }
  };

  // 최근 실행 이력 로드
  const loadRecentExecutions = async () => {
    try {
      const response = await judgmentService.getRecentExecutions({ limit: 10 });
      setRecentExecutions(response.executions);
    } catch (err) {
      console.error('Failed to load recent executions:', err);
    }
  };

  useEffect(() => {
    if (!isAuthenticated) return;
    loadRulesets();
    loadRecentExecutions();
  }, [isAuthenticated]);

  // Judgment 실행
  const handleExecute = async () => {
    if (!selectedRulesetId) {
      toast.warning('Ruleset을 선택하세요.');
      return;
    }

    let parsedInput: Record<string, any>;
    try {
      parsedInput = JSON.parse(inputData);
    } catch {
      toast.error('입력 데이터가 유효한 JSON이 아닙니다.');
      return;
    }

    setExecuting(true);
    setError(null);
    setResult(null);

    try {
      const request: JudgmentExecuteRequest = {
        ruleset_id: selectedRulesetId,
        input_data: parsedInput,
        policy: policy as any,
        need_explanation: needExplanation,
      };

      const response = await judgmentService.executeJudgment(request);
      setResult(response);
      toast.success('Judgment 실행 완료');
      loadRecentExecutions();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Judgment 실행 실패';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setExecuting(false);
    }
  };

  const DecisionIcon = result ? DECISION_ICONS[result.decision as keyof typeof DECISION_ICONS] : FileText;

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-50 flex items-center gap-2">
              <Brain className="w-7 h-7" />
              Judgment Execution
            </h2>
            <p className="text-sm text-slate-500 mt-1">
              Rule + LLM 하이브리드 판단을 직접 실행하고 결과를 분석합니다
            </p>
          </div>
          <button
            onClick={() => {
              loadRulesets();
              loadRecentExecutions();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-800 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700"
          >
            <RefreshCw className="w-4 h-4" />
            새로고침
          </button>
        </div>

        {/* Main Content - 2 Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Input Panel */}
          <div className="space-y-6">
            {/* Ruleset Selection */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">1. Ruleset 선택</CardTitle>
                <CardDescription>실행할 Ruleset을 선택하세요</CardDescription>
              </CardHeader>
              <CardContent>
                {loadingRulesets ? (
                  <div className="text-center py-4">
                    <RefreshCw className="w-6 h-6 mx-auto animate-spin text-slate-400" />
                  </div>
                ) : rulesets.length === 0 ? (
                  <div className="text-sm text-slate-500 text-center py-4">
                    활성 Ruleset이 없습니다
                  </div>
                ) : (
                  <select
                    value={selectedRulesetId}
                    onChange={(e) => setSelectedRulesetId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800"
                  >
                    {rulesets.map((ruleset) => (
                      <option key={ruleset.ruleset_id} value={ruleset.ruleset_id}>
                        {ruleset.name} (v{ruleset.version})
                      </option>
                    ))}
                  </select>
                )}
              </CardContent>
            </Card>

            {/* Input Data */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">2. 입력 데이터</CardTitle>
                <CardDescription>센서 값, 생산 데이터 등 (JSON)</CardDescription>
              </CardHeader>
              <CardContent>
                <textarea
                  value={inputData}
                  onChange={(e) => setInputData(e.target.value)}
                  className="w-full h-48 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 font-mono text-sm"
                  placeholder='{"temperature": 75, "pressure": 8.5}'
                />
              </CardContent>
            </Card>

            {/* Policy Selection */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">3. 판단 정책</CardTitle>
                <CardDescription>Rule과 LLM 조합 방식</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {POLICY_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
                  >
                    <input
                      type="radio"
                      value={opt.value}
                      checked={policy === opt.value}
                      onChange={(e) => setPolicy(e.target.value)}
                      className="w-4 h-4"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-sm">{opt.label}</div>
                      <div className="text-xs text-slate-500">{opt.desc}</div>
                    </div>
                  </label>
                ))}

                <label className="flex items-center gap-2 mt-4 pt-4 border-t dark:border-slate-700">
                  <input
                    type="checkbox"
                    checked={needExplanation}
                    onChange={(e) => setNeedExplanation(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">상세 설명 생성 (Evidence, Feature Importance)</span>
                </label>
              </CardContent>
            </Card>

            {/* Execute Button */}
            <button
              onClick={handleExecute}
              disabled={executing || !selectedRulesetId}
              className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {executing ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  실행 중...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Judgment 실행
                </>
              )}
            </button>
          </div>

          {/* Right: Result Panel */}
          <div className="space-y-6">
            {error && (
              <Card className="border-red-200 dark:border-red-800">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2 text-red-600">
                    <XCircle className="w-5 h-5" />
                    <span>{error}</span>
                  </div>
                </CardContent>
              </Card>
            )}

            {result && (
              <>
                {/* Decision Summary */}
                <Card className={`border-2 ${result.decision === 'CRITICAL' ? 'border-red-500' : result.decision === 'WARNING' ? 'border-yellow-500' : 'border-green-500'}`}>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2">
                        <DecisionIcon className="w-6 h-6" />
                        판단 결과
                      </CardTitle>
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${DECISION_COLORS[result.decision]}`}>
                        {result.decision}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="text-xs text-slate-500">신뢰도</div>
                        <div className="text-2xl font-bold">{(result.confidence * 100).toFixed(1)}%</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-500">실행 시간</div>
                        <div className="text-2xl font-bold">{result.execution_time_ms}ms</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-500">소스</div>
                        <div className="text-sm font-medium capitalize">{result.source}</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-500">캐시</div>
                        <div className="text-sm font-medium">{result.cached ? '적중' : '미스'}</div>
                      </div>
                    </div>

                    {result.explanation && (
                      <div className="pt-4 border-t dark:border-slate-700">
                        <div className="text-sm font-medium mb-2">설명</div>
                        <p className="text-sm text-slate-600 dark:text-slate-400">
                          {result.explanation.summary}
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Feature Importance */}
                {result.feature_importance && Object.keys(result.feature_importance).length > 0 && (
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <TrendingUp className="w-5 h-5" />
                        Feature Importance
                      </CardTitle>
                      <CardDescription>판단에 영향을 준 요소</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {Object.entries(result.feature_importance)
                          .sort(([, a], [, b]) => b - a)
                          .map(([field, importance]) => (
                            <div key={field}>
                              <div className="flex items-center justify-between text-sm mb-1">
                                <span className="font-medium">{field}</span>
                                <span className="text-slate-500">{(importance * 100).toFixed(1)}%</span>
                              </div>
                              <div className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-blue-600 transition-all"
                                  style={{ width: `${importance * 100}%` }}
                                />
                              </div>
                            </div>
                          ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Recommended Actions */}
                {result.recommended_actions && result.recommended_actions.length > 0 && (
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Zap className="w-5 h-5" />
                        권장 조치
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {result.recommended_actions.map((action, idx) => (
                          <div
                            key={idx}
                            className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg"
                          >
                            <div className="flex items-start gap-3">
                              <span
                                className={`px-2 py-0.5 text-xs rounded ${
                                  action.priority === 'immediate'
                                    ? 'bg-red-500 text-white'
                                    : action.priority === 'high'
                                    ? 'bg-yellow-500 text-white'
                                    : action.priority === 'medium'
                                    ? 'bg-blue-500 text-white'
                                    : 'bg-gray-400 text-white'
                                }`}
                              >
                                {action.priority === 'immediate'
                                  ? '긴급'
                                  : action.priority === 'high'
                                  ? '높음'
                                  : action.priority === 'medium'
                                  ? '중간'
                                  : '낮음'}
                              </span>
                              <div className="flex-1">
                                <div className="text-sm font-medium">{action.action}</div>
                                <div className="text-xs text-slate-500 mt-1">{action.reason}</div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Evidence */}
                {result.evidence && (
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <FileText className="w-5 h-5" />
                        증거 데이터
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {/* Input Values */}
                      {result.evidence.input_values && Object.keys(result.evidence.input_values).length > 0 && (
                        <div>
                          <div className="text-xs font-medium text-slate-500 uppercase mb-2">입력 값</div>
                          <div className="grid grid-cols-2 gap-2">
                            {Object.entries(result.evidence.input_values).map(([key, value]) => (
                              <div key={key} className="text-sm">
                                <span className="text-slate-500">{key}:</span>{' '}
                                <span className="font-medium">{String(value)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Historical Average */}
                      {result.evidence.historical_avg && Object.keys(result.evidence.historical_avg).length > 0 && (
                        <div className="pt-3 border-t dark:border-slate-700">
                          <div className="text-xs font-medium text-slate-500 uppercase mb-2">
                            히스토리 평균 (7일)
                          </div>
                          <div className="space-y-1">
                            {Object.entries(result.evidence.historical_avg).map(([key, value]) => (
                              <div key={key} className="text-sm flex justify-between">
                                <span className="text-slate-500">{key}:</span>
                                <span className="font-medium font-mono">{value.toFixed(4)}</span>
                              </div>
                            ))}
                            {result.evidence.similar_cases_count > 0 && (
                              <div className="text-sm flex justify-between">
                                <span className="text-slate-500">유사 케이스:</span>
                                <span className="font-medium">{result.evidence.similar_cases_count}건</span>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Thresholds */}
                      {result.evidence.thresholds && Object.keys(result.evidence.thresholds).length > 0 && (
                        <div className="pt-3 border-t dark:border-slate-700">
                          <div className="text-xs font-medium text-slate-500 uppercase mb-2">임계값</div>
                          <div className="space-y-1">
                            {Object.entries(result.evidence.thresholds).map(([key, value]) => (
                              <div key={key} className="text-sm flex justify-between">
                                <span className="text-slate-500">{key}:</span>
                                <span className="font-medium font-mono">{String(value)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
              </>
            )}

            {!result && !error && (
              <Card>
                <CardContent className="py-16">
                  <div className="text-center text-slate-500">
                    <Brain className="w-16 h-16 mx-auto mb-4 opacity-30" />
                    <p className="text-lg font-medium">결과가 표시됩니다</p>
                    <p className="text-sm mt-2">Ruleset과 입력 데이터를 설정한 후 실행하세요</p>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Recent Executions */}
            {recentExecutions.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <History className="w-5 h-5" />
                    최근 실행 이력
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {recentExecutions.slice(0, 5).map((exec) => (
                      <div
                        key={exec.execution_id}
                        className="p-2 bg-slate-50 dark:bg-slate-800 rounded text-sm flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-xs ${
                              exec.result === 'critical'
                                ? 'bg-red-500 text-white'
                                : exec.result === 'warning'
                                ? 'bg-yellow-500 text-white'
                                : 'bg-green-500 text-white'
                            }`}
                          >
                            {exec.result}
                          </span>
                          <span className="text-xs text-slate-500">
                            {exec.confidence ? `${(exec.confidence * 100).toFixed(0)}%` : '-'}
                          </span>
                        </div>
                        <span className="text-xs text-slate-400">
                          {exec.executed_at ? new Date(exec.executed_at).toLocaleTimeString('ko-KR') : '-'}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
