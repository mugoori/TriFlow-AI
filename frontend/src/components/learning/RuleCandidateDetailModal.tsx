/**
 * RuleCandidateDetailModal - 규칙 후보 상세 모달
 * Rhai 스크립트 뷰어, 메트릭 상세, 테스트 실행, 승인/거부
 */

import { useState } from 'react';
import {
  X,
  CheckCircle,
  XCircle,
  FlaskConical,
  Code,
  BarChart3,
  Play,
  Calendar,
  User,
  Clock,
} from 'lucide-react';
import { RuleCandidate, ruleExtractionService, TestSample, TestResponse } from '@/services/ruleExtractionService';

interface RuleCandidateDetailModalProps {
  candidate: RuleCandidate;
  onClose: () => void;
  onUpdate?: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  pending: '대기',
  approved: '승인',
  rejected: '거부',
  testing: '테스트 중',
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  approved: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  testing: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

export function RuleCandidateDetailModal({
  candidate,
  onClose,
  onUpdate,
}: RuleCandidateDetailModalProps) {
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [processing, setProcessing] = useState(false);

  // Test State
  const [showTest, setShowTest] = useState(false);
  const [testInput, setTestInput] = useState('{\n  "temperature": 85,\n  "pressure": 102\n}');
  const [testExpected, setTestExpected] = useState('{\n  "action": "adjust",\n  "threshold": 90\n}');
  const [testRunning, setTestRunning] = useState(false);
  const [testResult, setTestResult] = useState<TestResponse | null>(null);

  // Approve Request
  const [approving, setApproving] = useState(false);
  const [ruleName, setRuleName] = useState('');
  const [ruleDescription, setRuleDescription] = useState('');

  const handleApprove = async () => {
    try {
      setProcessing(true);
      await ruleExtractionService.approveCandidate(candidate.candidate_id, {
        rule_name: ruleName || undefined,
        description: ruleDescription || undefined,
      });
      onUpdate?.();
      onClose();
    } catch (err) {
      console.error('Failed to approve candidate:', err);
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) return;

    try {
      setProcessing(true);
      await ruleExtractionService.rejectCandidate(candidate.candidate_id, rejectReason);
      onUpdate?.();
      onClose();
    } catch (err) {
      console.error('Failed to reject candidate:', err);
    } finally {
      setProcessing(false);
    }
  };

  const handleRunTest = async () => {
    try {
      setTestRunning(true);
      setTestResult(null);

      const input = JSON.parse(testInput);
      const expected = JSON.parse(testExpected);

      const samples: TestSample[] = [{ input, expected }];
      const result = await ruleExtractionService.testCandidate(candidate.candidate_id, samples);
      setTestResult(result);
    } catch (err) {
      console.error('Failed to run test:', err);
      setTestResult({
        total: 1,
        passed: 0,
        failed: 1,
        accuracy: 0,
        execution_time_ms: 0,
        details: [
          {
            sample_index: 0,
            input: {},
            expected: {},
            actual: {},
            passed: false,
            error: err instanceof Error ? err.message : 'JSON 파싱 오류',
          },
        ],
      });
    } finally {
      setTestRunning(false);
    }
  };

  const MetricGauge = ({ label, value, color }: { label: string; value: number; color: string }) => (
    <div className="text-center">
      <div className="relative w-16 h-16 mx-auto">
        <svg className="w-16 h-16 transform -rotate-90" viewBox="0 0 64 64">
          <circle
            cx="32"
            cy="32"
            r="28"
            className="stroke-gray-200 dark:stroke-gray-600"
            strokeWidth="6"
            fill="none"
          />
          <circle
            cx="32"
            cy="32"
            r="28"
            className={color}
            strokeWidth="6"
            fill="none"
            strokeDasharray={`${value * 175.9} 175.9`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            {(value * 100).toFixed(0)}%
          </span>
        </div>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{label}</p>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Code className="w-5 h-5 text-purple-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              규칙 후보 상세
            </h2>
            <span className={`px-2 py-0.5 text-xs rounded-full ${STATUS_COLORS[candidate.approval_status]}`}>
              {STATUS_LABELS[candidate.approval_status]}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Meta Info */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex items-center gap-2">
              <Code className="w-4 h-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">생성 방식</p>
                <p className="text-sm text-gray-900 dark:text-white capitalize">
                  {candidate.generation_method.replace(/_/g, ' ')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">생성일</p>
                <p className="text-sm text-gray-900 dark:text-white">
                  {new Date(candidate.created_at).toLocaleDateString('ko-KR')}
                </p>
              </div>
            </div>
            {candidate.approved_by && (
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-gray-400" />
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">승인자</p>
                  <p className="text-sm text-gray-900 dark:text-white">{candidate.approved_by}</p>
                </div>
              </div>
            )}
            {candidate.approved_at && (
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-gray-400" />
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">승인일</p>
                  <p className="text-sm text-gray-900 dark:text-white">
                    {new Date(candidate.approved_at).toLocaleDateString('ko-KR')}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Metrics */}
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="w-4 h-4 text-purple-500" />
              <h3 className="font-medium text-gray-900 dark:text-white">성능 메트릭</h3>
            </div>
            <div className="flex justify-around">
              <MetricGauge label="정밀도" value={candidate.precision} color="stroke-blue-500" />
              <MetricGauge label="재현율" value={candidate.recall} color="stroke-green-500" />
              <MetricGauge label="F1 점수" value={candidate.f1_score} color="stroke-purple-500" />
              <MetricGauge label="커버리지" value={candidate.coverage} color="stroke-orange-500" />
            </div>
          </div>

          {/* Rhai Script */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium text-gray-900 dark:text-white flex items-center gap-2">
                <Code className="w-4 h-4" />
                Rhai 스크립트
              </h3>
              <button
                onClick={() => setShowTest(!showTest)}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  showTest
                    ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                <FlaskConical className="w-4 h-4" />
                테스트
              </button>
            </div>
            <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm overflow-auto max-h-64">
              <pre className="text-gray-100 whitespace-pre-wrap">{candidate.generated_rule}</pre>
            </div>
          </div>

          {/* Test Panel */}
          {showTest && (
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 space-y-4">
              <h4 className="font-medium text-gray-900 dark:text-white flex items-center gap-2">
                <FlaskConical className="w-4 h-4" />
                규칙 테스트
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                    입력 데이터 (JSON)
                  </label>
                  <textarea
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-mono"
                    rows={5}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                    예상 출력 (JSON)
                  </label>
                  <textarea
                    value={testExpected}
                    onChange={(e) => setTestExpected(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-mono"
                    rows={5}
                  />
                </div>
              </div>
              <button
                onClick={handleRunTest}
                disabled={testRunning}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-blue-300 transition-colors"
              >
                <Play className="w-4 h-4" />
                {testRunning ? '실행 중...' : '테스트 실행'}
              </button>

              {testResult && (
                <div
                  className={`p-3 rounded-lg border ${
                    testResult.passed === testResult.total
                      ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                      : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                  }`}
                >
                  <div className="flex items-center gap-4 text-sm">
                    {testResult.passed === testResult.total ? (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-500" />
                    )}
                    <span className="text-gray-900 dark:text-white">
                      {testResult.passed}/{testResult.total} 통과
                    </span>
                    <span className="text-gray-500 dark:text-gray-400">
                      정확도: {(testResult.accuracy * 100).toFixed(1)}%
                    </span>
                    <span className="text-gray-500 dark:text-gray-400">
                      {testResult.execution_time_ms.toFixed(1)}ms
                    </span>
                  </div>
                  {testResult.details[0]?.error && (
                    <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                      {testResult.details[0].error}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Rejection Reason (if rejected) */}
          {candidate.approval_status === 'rejected' && candidate.rejection_reason && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <h4 className="text-sm font-medium text-red-700 dark:text-red-300 mb-2">거부 사유</h4>
              <p className="text-sm text-red-600 dark:text-red-400">{candidate.rejection_reason}</p>
            </div>
          )}

          {/* Approval Form */}
          {candidate.approval_status === 'pending' && approving && (
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  규칙 이름 (선택)
                </label>
                <input
                  type="text"
                  value={ruleName}
                  onChange={(e) => setRuleName(e.target.value)}
                  placeholder="자동 생성됩니다"
                  className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  설명 (선택)
                </label>
                <textarea
                  value={ruleDescription}
                  onChange={(e) => setRuleDescription(e.target.value)}
                  placeholder="규칙에 대한 설명을 입력하세요"
                  className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
                  rows={2}
                />
              </div>
            </div>
          )}

          {/* Reject Form */}
          {candidate.approval_status === 'pending' && rejecting && (
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                거부 사유
              </label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="거부 사유를 입력하세요..."
                className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                rows={3}
              />
            </div>
          )}
        </div>

        {/* Footer - Actions */}
        {candidate.approval_status === 'pending' && (
          <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-end gap-3">
            {rejecting ? (
              <>
                <button
                  onClick={() => {
                    setRejecting(false);
                    setRejectReason('');
                  }}
                  className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  취소
                </button>
                <button
                  onClick={handleReject}
                  disabled={!rejectReason.trim() || processing}
                  className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:bg-red-300 transition-colors"
                >
                  <XCircle className="w-4 h-4" />
                  {processing ? '처리 중...' : '거부 확인'}
                </button>
              </>
            ) : approving ? (
              <>
                <button
                  onClick={() => setApproving(false)}
                  className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  취소
                </button>
                <button
                  onClick={handleApprove}
                  disabled={processing}
                  className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:bg-green-300 transition-colors"
                >
                  <CheckCircle className="w-4 h-4" />
                  {processing ? '처리 중...' : '승인 확인'}
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => setRejecting(true)}
                  className="flex items-center gap-2 px-4 py-2 text-red-600 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                >
                  <XCircle className="w-4 h-4" />
                  거부
                </button>
                <button
                  onClick={() => setApproving(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors"
                >
                  <CheckCircle className="w-4 h-4" />
                  승인
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default RuleCandidateDetailModal;
