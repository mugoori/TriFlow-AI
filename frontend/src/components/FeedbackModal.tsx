/**
 * Feedback Modal Component
 * 상세 피드백을 작성하는 모달
 */

import { useState } from 'react';
import { X, Send, AlertCircle } from 'lucide-react';
import { sendDetailedFeedback, FeedbackType } from '../services/feedbackService';

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: () => void;
  messageId: string;
  agentType?: string;
  originalOutput?: Record<string, unknown>;
}

const FEEDBACK_REASONS = [
  { value: 'incorrect', label: '정보가 틀렸어요' },
  { value: 'incomplete', label: '정보가 부족해요' },
  { value: 'irrelevant', label: '질문과 관련 없는 답변이에요' },
  { value: 'unclear', label: '이해하기 어려워요' },
  { value: 'slow', label: '응답이 너무 느려요' },
  { value: 'other', label: '기타' },
];

export function FeedbackModal({
  isOpen,
  onClose,
  onSubmit,
  messageId,
  agentType,
  originalOutput,
}: FeedbackModalProps) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType>('negative');
  const [selectedReason, setSelectedReason] = useState<string>('');
  const [feedbackText, setFeedbackText] = useState('');
  const [correctedAnswer, setCorrectedAnswer] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!selectedReason && !feedbackText) {
      setError('피드백 이유를 선택하거나 내용을 입력해주세요.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      // 피드백 텍스트 조합
      const reasonLabel = FEEDBACK_REASONS.find(r => r.value === selectedReason)?.label || '';
      const fullFeedbackText = [
        reasonLabel ? `[${reasonLabel}]` : '',
        feedbackText,
      ].filter(Boolean).join(' ');

      await sendDetailedFeedback(
        feedbackType,
        messageId,
        fullFeedbackText,
        {
          agentType,
          originalOutput,
          correctedOutput: correctedAnswer ? { suggested_answer: correctedAnswer } : undefined,
        }
      );

      onSubmit();
      resetForm();
    } catch (err) {
      console.error('Failed to submit feedback:', err);
      setError('피드백 전송에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setSelectedReason('');
    setFeedbackText('');
    setCorrectedAnswer('');
    setError(null);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            피드백 작성
          </h2>
          <button
            onClick={handleClose}
            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          {/* 피드백 유형 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              피드백 유형
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => setFeedbackType('negative')}
                className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
                  feedbackType === 'negative'
                    ? 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300 border-2 border-red-500'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border-2 border-transparent'
                }`}
              >
                개선이 필요해요
              </button>
              <button
                onClick={() => setFeedbackType('correction')}
                className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
                  feedbackType === 'correction'
                    ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300 border-2 border-amber-500'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border-2 border-transparent'
                }`}
              >
                수정 제안
              </button>
            </div>
          </div>

          {/* 피드백 이유 선택 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              이유 선택
            </label>
            <div className="grid grid-cols-2 gap-2">
              {FEEDBACK_REASONS.map((reason) => (
                <button
                  key={reason.value}
                  onClick={() => setSelectedReason(reason.value)}
                  className={`py-2 px-3 rounded-lg text-sm text-left transition-colors ${
                    selectedReason === reason.value
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300 border border-blue-500'
                      : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border border-transparent hover:border-slate-300 dark:hover:border-slate-600'
                  }`}
                >
                  {reason.label}
                </button>
              ))}
            </div>
          </div>

          {/* 상세 피드백 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              상세 내용 (선택)
            </label>
            <textarea
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              placeholder="더 자세한 피드백을 작성해주세요..."
              className="w-full px-4 py-3 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              rows={3}
            />
          </div>

          {/* 수정 제안 (correction 타입일 때만) */}
          {feedbackType === 'correction' && (
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                원하는 답변 (선택)
              </label>
              <textarea
                value={correctedAnswer}
                onChange={(e) => setCorrectedAnswer(e.target.value)}
                placeholder="어떤 답변을 원하셨는지 알려주세요..."
                className="w-full px-4 py-3 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                rows={3}
              />
            </div>
          )}

          {/* 에러 메시지 */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-lg text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                전송 중...
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                피드백 전송
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
