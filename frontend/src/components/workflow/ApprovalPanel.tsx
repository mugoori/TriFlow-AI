/**
 * Approval Panel Component
 * 워크플로우 승인 대기 목록 및 승인/거부 UI
 */

import { useState, useEffect, useCallback } from 'react';
import {
  CheckCircle,
  XCircle,
  Clock,
  User,
  MessageSquare,
  AlertCircle,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Send,
} from 'lucide-react';
import { workflowService, ApprovalRequest } from '../../services/workflowService';

interface ApprovalPanelProps {
  className?: string;
}

export function ApprovalPanel({ className = '' }: ApprovalPanelProps) {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [comment, setComment] = useState<string>('');
  const [processing, setProcessing] = useState<string | null>(null);

  const fetchApprovals = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await workflowService.getPendingApprovals();
      setApprovals(response.approvals);
    } catch (err) {
      console.error('Failed to fetch approvals:', err);
      setError('승인 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApprovals();
    // 30초마다 자동 새로고침
    const interval = setInterval(fetchApprovals, 30000);
    return () => clearInterval(interval);
  }, [fetchApprovals]);

  const handleApprove = async (approvalId: string) => {
    try {
      setProcessing(approvalId);
      await workflowService.approve(approvalId, comment || undefined);
      setComment('');
      setExpandedId(null);
      await fetchApprovals();
    } catch (err) {
      console.error('Failed to approve:', err);
      setError('승인 처리에 실패했습니다.');
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (approvalId: string) => {
    try {
      setProcessing(approvalId);
      await workflowService.reject(approvalId, comment || undefined);
      setComment('');
      setExpandedId(null);
      await fetchApprovals();
    } catch (err) {
      console.error('Failed to reject:', err);
      setError('거부 처리에 실패했습니다.');
    } finally {
      setProcessing(null);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'approved':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'rejected':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'timeout':
        return <AlertCircle className="w-4 h-4 text-gray-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending':
        return '대기 중';
      case 'approved':
        return '승인됨';
      case 'rejected':
        return '거부됨';
      case 'timeout':
        return '만료됨';
      case 'cancelled':
        return '취소됨';
      default:
        return status;
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getTimeRemaining = (timeoutAt: string | undefined) => {
    if (!timeoutAt) return null;

    const timeout = new Date(timeoutAt);
    const now = new Date();
    const diff = timeout.getTime() - now.getTime();

    if (diff <= 0) return '만료됨';

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 0) {
      return `${hours}시간 ${minutes}분 남음`;
    }
    return `${minutes}분 남음`;
  };

  if (loading && approvals.length === 0) {
    return (
      <div className={`bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 ${className}`}>
        <div className="p-4 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
          <span className="ml-2 text-sm text-slate-600 dark:text-slate-400">로딩 중...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-amber-500" />
          <h3 className="font-semibold">승인 대기</h3>
          {approvals.length > 0 && (
            <span className="bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-xs font-medium px-2 py-0.5 rounded-full">
              {approvals.length}
            </span>
          )}
        </div>
        <button
          onClick={fetchApprovals}
          disabled={loading}
          className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
          title="새로고침"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="m-3 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Approval List */}
      <div className="max-h-[400px] overflow-y-auto">
        {approvals.length === 0 ? (
          <div className="p-6 text-center text-slate-500 dark:text-slate-400">
            <Clock className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">승인 대기 중인 항목이 없습니다.</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-200 dark:divide-slate-700">
            {approvals.map((approval) => (
              <li key={approval.approval_id} className="p-3">
                {/* Summary Row */}
                <div
                  className="flex items-start justify-between cursor-pointer"
                  onClick={() => setExpandedId(expandedId === approval.approval_id ? null : approval.approval_id)}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(approval.status)}
                      <span className="font-medium text-sm truncate">{approval.title}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        approval.status === 'pending' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300' :
                        approval.status === 'approved' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                        approval.status === 'rejected' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
                        'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-300'
                      }`}>
                        {getStatusText(approval.status)}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                      <span className="truncate">{approval.workflow_name}</span>
                      <span>•</span>
                      <span>{formatDate(approval.requested_at)}</span>
                    </div>
                    {approval.timeout_at && approval.status === 'pending' && (
                      <div className="mt-1 text-xs text-orange-500">
                        {getTimeRemaining(approval.timeout_at)}
                      </div>
                    )}
                  </div>
                  <button className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                    {expandedId === approval.approval_id ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </button>
                </div>

                {/* Expanded Detail */}
                {expandedId === approval.approval_id && (
                  <div className="mt-3 space-y-3">
                    {/* Description */}
                    {approval.description && (
                      <div className="p-2 bg-slate-50 dark:bg-slate-900 rounded text-sm">
                        {approval.description}
                      </div>
                    )}

                    {/* Approvers */}
                    <div>
                      <p className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">승인자</p>
                      <div className="flex flex-wrap gap-1">
                        {approval.approvers.map((approver, idx) => (
                          <span
                            key={idx}
                            className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full ${
                              approver.status === 'approved'
                                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                                : approver.status === 'rejected'
                                ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                                : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300'
                            }`}
                          >
                            <User className="w-3 h-3" />
                            {approver.email || approver.user_id}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Decision Comment (if already decided) */}
                    {approval.decision_comment && (
                      <div className="p-2 bg-slate-50 dark:bg-slate-900 rounded">
                        <p className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-1 flex items-center gap-1">
                          <MessageSquare className="w-3 h-3" />
                          결정 코멘트
                        </p>
                        <p className="text-sm">{approval.decision_comment}</p>
                      </div>
                    )}

                    {/* Action Buttons (only for pending) */}
                    {approval.status === 'pending' && (
                      <div className="space-y-2">
                        <div className="relative">
                          <input
                            type="text"
                            placeholder="코멘트 (선택)"
                            value={comment}
                            onChange={(e) => setComment(e.target.value)}
                            className="w-full px-3 py-2 pr-10 text-sm border rounded dark:bg-slate-700 dark:border-slate-600 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                          <Send className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleApprove(approval.approval_id)}
                            disabled={processing === approval.approval_id}
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded transition-colors disabled:opacity-50"
                          >
                            {processing === approval.approval_id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <CheckCircle className="w-4 h-4" />
                            )}
                            승인
                          </button>
                          <button
                            onClick={() => handleReject(approval.approval_id)}
                            disabled={processing === approval.approval_id}
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded transition-colors disabled:opacity-50"
                          >
                            {processing === approval.approval_id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <XCircle className="w-4 h-4" />
                            )}
                            거부
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Decision Info (if decided) */}
                    {approval.decided_at && (
                      <div className="text-xs text-slate-500 dark:text-slate-400">
                        {approval.decided_by && <span>결정자: {approval.decided_by} • </span>}
                        {formatDate(approval.decided_at)}
                      </div>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default ApprovalPanel;
