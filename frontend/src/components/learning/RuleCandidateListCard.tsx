/**
 * RuleCandidateListCard - 규칙 후보 목록 카드
 * 후보 테이블, 상태 뱃지, 메트릭 미리보기
 */

import { useState, useEffect, useCallback } from 'react';
import {
  List,
  Filter,
  CheckCircle,
  XCircle,
  Eye,
  ChevronLeft,
  ChevronRight,
  FlaskConical,
  Clock,
} from 'lucide-react';
import { ruleExtractionService, RuleCandidate, ApprovalStatus } from '@/services/ruleExtractionService';

interface RuleCandidateListCardProps {
  onSelectCandidate?: (candidate: RuleCandidate) => void;
  onRefresh?: () => void;
}

const STATUS_LABELS: Record<ApprovalStatus, string> = {
  pending: '대기',
  approved: '승인',
  rejected: '거부',
  testing: '테스트 중',
};

const STATUS_COLORS: Record<ApprovalStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  approved: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  testing: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

const STATUS_ICONS: Record<ApprovalStatus, React.ElementType> = {
  pending: Clock,
  approved: CheckCircle,
  rejected: XCircle,
  testing: FlaskConical,
};

export function RuleCandidateListCard({ onSelectCandidate, onRefresh }: RuleCandidateListCardProps) {
  const [candidates, setCandidates] = useState<RuleCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 10;

  // Filters
  const [statusFilter, setStatusFilter] = useState<ApprovalStatus | ''>('');
  const [showFilters, setShowFilters] = useState(false);

  const loadCandidates = useCallback(async () => {
    try {
      setLoading(true);
      const response = await ruleExtractionService.listCandidates({
        status: statusFilter || undefined,
        page,
        page_size: pageSize,
      });
      setCandidates(response.items);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to load candidates:', err);
      // 데모 데이터
      setCandidates([
        {
          candidate_id: '1',
          tenant_id: 't1',
          generated_rule: `fn check_threshold(ctx) {
  if ctx.temperature > 85.0 && ctx.pressure > 100.0 {
    return #{ action: "adjust", threshold: 90 };
  }
  return #{ action: "none" };
}`,
          generation_method: 'pattern_mining',
          coverage: 0.82,
          precision: 0.91,
          recall: 0.85,
          f1_score: 0.88,
          approval_status: 'pending',
          created_at: new Date().toISOString(),
        },
        {
          candidate_id: '2',
          tenant_id: 't1',
          generated_rule: `fn validate_field(ctx) {
  if ctx.field_a.len() > 10 {
    return #{ valid: false, error: "Too long" };
  }
  return #{ valid: true };
}`,
          generation_method: 'llm',
          coverage: 0.75,
          precision: 0.88,
          recall: 0.79,
          f1_score: 0.83,
          approval_status: 'approved',
          created_at: new Date().toISOString(),
        },
      ]);
      setTotal(2);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  const handleApprove = async (candidateId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await ruleExtractionService.approveCandidate(candidateId);
      await loadCandidates();
      onRefresh?.();
    } catch (err) {
      console.error('Failed to approve candidate:', err);
    }
  };

  const handleReject = async (candidateId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const reason = prompt('거부 사유를 입력하세요:');
    if (!reason) return;

    try {
      await ruleExtractionService.rejectCandidate(candidateId, reason);
      await loadCandidates();
      onRefresh?.();
    } catch (err) {
      console.error('Failed to reject candidate:', err);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  const MetricBar = ({ label, value }: { label: string; value: number }) => (
    <div className="flex items-center gap-1">
      <span className="text-xs text-gray-500 dark:text-gray-400 w-8">{label}</span>
      <div className="flex-1 w-12 bg-gray-200 dark:bg-gray-600 rounded-full h-1">
        <div
          className={`h-1 rounded-full ${
            value >= 0.8 ? 'bg-green-500' : value >= 0.6 ? 'bg-yellow-500' : 'bg-red-500'
          }`}
          style={{ width: `${value * 100}%` }}
        />
      </div>
      <span className="text-xs text-gray-600 dark:text-gray-300 w-8">
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <List className="w-5 h-5 text-purple-500" />
          <h3 className="font-semibold text-gray-900 dark:text-white">규칙 후보</h3>
          <span className="text-sm text-gray-500 dark:text-gray-400">({total}개)</span>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`p-2 rounded-lg transition-colors ${
            showFilters
              ? 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400'
              : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
          }`}
        >
          <Filter className="w-4 h-4" />
        </button>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">상태</label>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as ApprovalStatus | '');
                setPage(1);
              }}
              className="px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
            >
              <option value="">전체</option>
              <option value="pending">대기</option>
              <option value="testing">테스트 중</option>
              <option value="approved">승인</option>
              <option value="rejected">거부</option>
            </select>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        {loading ? (
          <div className="p-8 text-center">
            <div className="animate-spin w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full mx-auto" />
          </div>
        ) : candidates.length > 0 ? (
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  상태
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  생성 방식
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  메트릭
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  생성일
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  작업
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {candidates.map((candidate) => {
                const StatusIcon = STATUS_ICONS[candidate.approval_status];
                return (
                  <tr
                    key={candidate.candidate_id}
                    onClick={() => onSelectCandidate?.(candidate)}
                    className="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full ${
                          STATUS_COLORS[candidate.approval_status]
                        }`}
                      >
                        <StatusIcon className="w-3 h-3" />
                        {STATUS_LABELS[candidate.approval_status]}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-900 dark:text-white capitalize">
                        {candidate.generation_method.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="space-y-1 w-32">
                        <MetricBar label="F1" value={candidate.f1_score} />
                        <MetricBar label="Cov" value={candidate.coverage} />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {new Date(candidate.created_at).toLocaleDateString('ko-KR')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectCandidate?.(candidate);
                          }}
                          className="p-1.5 text-gray-400 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/20 rounded transition-colors"
                          title="상세 보기"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {candidate.approval_status === 'pending' && (
                          <>
                            <button
                              onClick={(e) => handleApprove(candidate.candidate_id, e)}
                              className="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors"
                              title="승인"
                            >
                              <CheckCircle className="w-4 h-4" />
                            </button>
                            <button
                              onClick={(e) => handleReject(candidate.candidate_id, e)}
                              className="p-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                              title="거부"
                            >
                              <XCircle className="w-4 h-4" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="p-8 text-center">
            <List className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400">규칙 후보가 없습니다</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {total}개 중 {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-50"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="text-sm text-gray-600 dark:text-gray-300">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-50"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default RuleCandidateListCard;
