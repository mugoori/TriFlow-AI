/**
 * SampleDetailModal - 샘플 상세 모달
 * 입력/예상 출력 비교, 컨텍스트 정보, 승인/거부 액션
 */

import { useState } from 'react';
import {
  X,
  CheckCircle,
  XCircle,
  Database,
  ArrowRight,
  Info,
  User,
  Calendar,
} from 'lucide-react';
import { Sample, sampleService } from '@/services/sampleService';
import { STATUS_LABELS, STATUS_COLORS } from '@/lib/statusConfig';

interface SampleDetailModalProps {
  sample: Sample;
  onClose: () => void;
  onUpdate?: () => void;
}

export function SampleDetailModal({ sample, onClose, onUpdate }: SampleDetailModalProps) {
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [processing, setProcessing] = useState(false);

  const handleApprove = async () => {
    try {
      setProcessing(true);
      await sampleService.approveSample(sample.sample_id);
      onUpdate?.();
      onClose();
    } catch (err) {
      console.error('Failed to approve sample:', err);
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) return;

    try {
      setProcessing(true);
      await sampleService.rejectSample(sample.sample_id, rejectReason);
      onUpdate?.();
      onClose();
    } catch (err) {
      console.error('Failed to reject sample:', err);
    } finally {
      setProcessing(false);
    }
  };

  const JsonView = ({ data, title }: { data: Record<string, unknown>; title: string }) => (
    <div className="flex-1">
      <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{title}</h4>
      <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 font-mono text-sm overflow-auto max-h-64">
        <pre className="text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
          {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Database className="w-5 h-5 text-blue-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              샘플 상세
            </h2>
            <span className={`px-2 py-0.5 text-xs rounded-full ${STATUS_COLORS[sample.status]}`}>
              {STATUS_LABELS[sample.status]}
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
              <Info className="w-4 h-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">카테고리</p>
                <p className="text-sm text-gray-900 dark:text-white capitalize">
                  {sample.category.replace(/_/g, ' ')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">소스</p>
                <p className="text-sm text-gray-900 dark:text-white capitalize">
                  {sample.source_type}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">생성일</p>
                <p className="text-sm text-gray-900 dark:text-white">
                  {new Date(sample.created_at).toLocaleDateString('ko-KR')}
                </p>
              </div>
            </div>
            {sample.approved_by && (
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-gray-400" />
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">승인자</p>
                  <p className="text-sm text-gray-900 dark:text-white">
                    {sample.approved_by}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Quality Score */}
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">품질 점수</span>
              <span className="text-lg font-semibold text-gray-900 dark:text-white">
                {(sample.quality_score * 100).toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  sample.quality_score >= 0.8
                    ? 'bg-green-500'
                    : sample.quality_score >= 0.6
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
                }`}
                style={{ width: `${sample.quality_score * 100}%` }}
              />
            </div>
            <div className="flex justify-between mt-2 text-xs text-gray-500 dark:text-gray-400">
              <span>신뢰도: {(sample.confidence * 100).toFixed(1)}%</span>
            </div>
          </div>

          {/* Input / Output Comparison */}
          <div>
            <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <ArrowRight className="w-4 h-4" />
              입력 / 예상 출력
            </h3>
            <div className="flex gap-4">
              <JsonView data={sample.input_data} title="입력 데이터" />
              <JsonView data={sample.expected_output} title="예상 출력" />
            </div>
          </div>

          {/* Context */}
          {sample.context && Object.keys(sample.context).length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
                컨텍스트 정보
              </h3>
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 font-mono text-sm overflow-auto max-h-48">
                <pre className="text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                  {JSON.stringify(sample.context, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* Rejection Reason (if rejected) */}
          {sample.status === 'rejected' && sample.rejection_reason && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <h4 className="text-sm font-medium text-red-700 dark:text-red-300 mb-2">거부 사유</h4>
              <p className="text-sm text-red-600 dark:text-red-400">{sample.rejection_reason}</p>
            </div>
          )}

          {/* Reject Form */}
          {sample.status === 'pending' && rejecting && (
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
        {sample.status === 'pending' && (
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
                  onClick={handleApprove}
                  disabled={processing}
                  className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:bg-green-300 transition-colors"
                >
                  <CheckCircle className="w-4 h-4" />
                  {processing ? '처리 중...' : '승인'}
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default SampleDetailModal;
