/**
 * ProposalsPanel
 * 제안된 규칙 관리 패널
 */

import { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Sparkles,
  Search,
  Check,
  X,
  Code,
  ChevronDown,
  ChevronUp,
  Percent,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  listProposals,
  getProposalStats,
  reviewProposal,
  runAnalysis,
  deleteProposal,
  type Proposal,
  type ProposalStats,
} from '@/services/proposalService';

interface ProposalsPanelProps {
  onRulesetCreated?: (rulesetId: string) => void;
}

export function ProposalsPanel({ onRulesetCreated }: ProposalsPanelProps) {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [stats, setStats] = useState<ProposalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);

  // Analysis state
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);

  // Review state
  const [reviewing, setReviewing] = useState(false);
  const [reviewComment, setReviewComment] = useState('');

  // Expanded script view
  const [expandedScript, setExpandedScript] = useState(false);

  // Load proposals
  const loadProposals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [proposalRes, statsRes] = await Promise.all([
        listProposals({ status: statusFilter || undefined }),
        getProposalStats(),
      ]);
      setProposals(proposalRes.proposals);
      setStats(statsRes);
    } catch (err) {
      console.error('Failed to load proposals:', err);
      setError('제안 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadProposals();
  }, [loadProposals]);

  // Run feedback analysis
  const handleRunAnalysis = async () => {
    setAnalyzing(true);
    setAnalysisResult(null);
    try {
      const result = await runAnalysis({ days: 7, min_frequency: 2 });
      setAnalysisResult(result.message);
      if (result.proposals_created > 0) {
        loadProposals();
      }
    } catch (err) {
      console.error('Analysis failed:', err);
      setAnalysisResult('분석 실행에 실패했습니다.');
    } finally {
      setAnalyzing(false);
    }
  };

  // Review proposal
  const handleReview = async (action: 'approve' | 'reject') => {
    if (!selectedProposal) return;

    setReviewing(true);
    try {
      const result = await reviewProposal(selectedProposal.proposal_id, action, reviewComment);

      if (action === 'approve' && result.ruleset_id && onRulesetCreated) {
        onRulesetCreated(result.ruleset_id);
      }

      setSelectedProposal(null);
      setReviewComment('');
      loadProposals();
    } catch (err) {
      console.error('Review failed:', err);
      alert('검토 처리에 실패했습니다.');
    } finally {
      setReviewing(false);
    }
  };

  // Delete proposal
  const handleDelete = async (proposal: Proposal) => {
    if (!confirm(`"${proposal.rule_name}" 제안을 삭제하시겠습니까?`)) return;

    try {
      await deleteProposal(proposal.proposal_id);
      if (selectedProposal?.proposal_id === proposal.proposal_id) {
        setSelectedProposal(null);
      }
      loadProposals();
    } catch (err) {
      console.error('Delete failed:', err);
      alert('삭제에 실패했습니다.');
    }
  };

  // Format date
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('ko-KR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Status badge
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 text-xs bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 rounded-full">
            <Clock className="w-3 h-3" />
            대기 중
          </span>
        );
      case 'approved':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded-full">
            <Check className="w-3 h-3" />
            승인됨
          </span>
        );
      case 'deployed':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded-full">
            <CheckCircle className="w-3 h-3" />
            배포됨
          </span>
        );
      case 'rejected':
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 text-xs bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 rounded-full">
            <XCircle className="w-3 h-3" />
            거절됨
          </span>
        );
      default:
        return null;
    }
  };

  // Confidence bar
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'bg-green-500';
    if (confidence >= 0.6) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="flex-1 flex overflow-hidden bg-slate-50 dark:bg-slate-950">
      {/* Left Panel - Proposal List */}
      <div className="w-96 border-r border-slate-200 dark:border-slate-800 flex flex-col bg-white dark:bg-slate-900">
        {/* Header */}
        <div className="p-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-500" />
              AI 규칙 제안
            </h2>
            <button
              onClick={handleRunAnalysis}
              disabled={analyzing}
              className="flex items-center gap-2 px-3 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              {analyzing ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
              분석 실행
            </button>
          </div>

          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-4 gap-2 mb-3">
              <div className="text-center p-2 bg-slate-100 dark:bg-slate-800 rounded-lg">
                <div className="text-lg font-bold text-slate-900 dark:text-white">{stats.total}</div>
                <div className="text-xs text-slate-500">전체</div>
              </div>
              <div className="text-center p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                <div className="text-lg font-bold text-yellow-600 dark:text-yellow-400">{stats.pending}</div>
                <div className="text-xs text-slate-500">대기</div>
              </div>
              <div className="text-center p-2 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="text-lg font-bold text-green-600 dark:text-green-400">{stats.deployed}</div>
                <div className="text-xs text-slate-500">배포</div>
              </div>
              <div className="text-center p-2 bg-red-50 dark:bg-red-900/20 rounded-lg">
                <div className="text-lg font-bold text-red-600 dark:text-red-400">{stats.rejected}</div>
                <div className="text-xs text-slate-500">거절</div>
              </div>
            </div>
          )}

          {/* Analysis Result */}
          {analysisResult && (
            <div className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded-lg text-sm text-purple-700 dark:text-purple-300">
              {analysisResult}
            </div>
          )}

          {/* Filter */}
          <div className="flex gap-2 mt-3">
            {['', 'pending', 'deployed', 'rejected'].map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  statusFilter === status
                    ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                }`}
              >
                {status === '' ? '전체' : status === 'pending' ? '대기' : status === 'deployed' ? '배포' : '거절'}
              </button>
            ))}
            <button
              onClick={loadProposals}
              className="ml-auto p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title="새로고침"
            >
              <RefreshCw className="w-4 h-4 text-slate-500" />
            </button>
          </div>
        </div>

        {/* Proposal List */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <RefreshCw className="w-6 h-6 text-slate-400 animate-spin" />
            </div>
          ) : error ? (
            <div className="p-4 text-center text-red-500">{error}</div>
          ) : proposals.length === 0 ? (
            <div className="p-8 text-center">
              <Sparkles className="w-12 h-12 mx-auto mb-3 text-slate-300 dark:text-slate-600" />
              <p className="text-slate-500 dark:text-slate-400">제안이 없습니다</p>
              <p className="text-sm text-slate-400 dark:text-slate-500 mt-2">
                "분석 실행" 버튼을 클릭하여<br />피드백 기반 규칙을 생성하세요
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200 dark:divide-slate-700">
              {proposals.map((proposal) => (
                <div
                  key={proposal.proposal_id}
                  onClick={() => setSelectedProposal(proposal)}
                  className={`p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                    selectedProposal?.proposal_id === proposal.proposal_id
                      ? 'bg-purple-50 dark:bg-purple-900/20 border-l-4 border-purple-500'
                      : ''
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-900 dark:text-white truncate">
                          {proposal.rule_name}
                        </span>
                        {getStatusBadge(proposal.status)}
                      </div>
                      {proposal.rule_description && (
                        <p className="text-sm text-slate-500 dark:text-slate-400 truncate mt-1">
                          {proposal.rule_description}
                        </p>
                      )}
                      <div className="flex items-center gap-3 mt-2">
                        <div className="flex items-center gap-1 text-xs text-slate-400">
                          <Percent className="w-3 h-3" />
                          <span>{Math.round(proposal.confidence * 100)}%</span>
                        </div>
                        <span className="text-xs text-slate-400">
                          {formatDate(proposal.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right Panel - Detail View */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedProposal ? (
          <>
            {/* Detail Header */}
            <div className="p-4 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                    {selectedProposal.rule_name}
                  </h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    {selectedProposal.rule_description || '설명 없음'}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusBadge(selectedProposal.status)}
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-auto p-4">
              <div className="space-y-4">
                {/* Confidence */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">신뢰도</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-3 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${getConfidenceColor(selectedProposal.confidence)} transition-all`}
                          style={{ width: `${selectedProposal.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-lg font-bold text-slate-900 dark:text-white">
                        {Math.round(selectedProposal.confidence * 100)}%
                      </span>
                    </div>
                  </CardContent>
                </Card>

                {/* Script */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <Code className="w-4 h-4" />
                        제안된 Rhai 스크립트
                      </span>
                      <button
                        onClick={() => setExpandedScript(!expandedScript)}
                        className="text-slate-400 hover:text-slate-600"
                      >
                        {expandedScript ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre
                      className={`text-sm font-mono bg-slate-900 text-slate-100 p-4 rounded-lg overflow-auto ${
                        expandedScript ? 'max-h-none' : 'max-h-48'
                      }`}
                    >
                      {selectedProposal.rhai_script}
                    </pre>
                  </CardContent>
                </Card>

                {/* Source Info */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">생성 정보</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-500">출처</span>
                      <span className="text-slate-900 dark:text-white">
                        {selectedProposal.source_type === 'feedback_analysis' ? '피드백 분석' : selectedProposal.source_type}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">생성일</span>
                      <span className="text-slate-900 dark:text-white">
                        {formatDate(selectedProposal.created_at)}
                      </span>
                    </div>
                    {selectedProposal.reviewed_at && (
                      <>
                        <div className="flex justify-between">
                          <span className="text-slate-500">검토일</span>
                          <span className="text-slate-900 dark:text-white">
                            {formatDate(selectedProposal.reviewed_at)}
                          </span>
                        </div>
                        {selectedProposal.review_comment && (
                          <div className="pt-2 border-t border-slate-200 dark:border-slate-700">
                            <span className="text-slate-500">검토 코멘트:</span>
                            <p className="text-slate-900 dark:text-white mt-1">
                              {selectedProposal.review_comment}
                            </p>
                          </div>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>

                {/* Review Actions (only for pending) */}
                {selectedProposal.status === 'pending' && (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">검토</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <textarea
                        value={reviewComment}
                        onChange={(e) => setReviewComment(e.target.value)}
                        placeholder="검토 코멘트 (선택)"
                        className="w-full h-20 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleReview('approve')}
                          disabled={reviewing}
                          className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
                        >
                          {reviewing ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                          ) : (
                            <Check className="w-4 h-4" />
                          )}
                          승인 (룰셋 생성)
                        </button>
                        <button
                          onClick={() => handleReview('reject')}
                          disabled={reviewing}
                          className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
                        >
                          <X className="w-4 h-4" />
                          거절
                        </button>
                      </div>
                      <button
                        onClick={() => handleDelete(selectedProposal)}
                        className="w-full text-sm text-slate-500 hover:text-red-500 transition-colors"
                      >
                        제안 삭제
                      </button>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-slate-50 dark:bg-slate-950">
            <div className="text-center">
              <Sparkles className="w-16 h-16 mx-auto mb-4 text-slate-300 dark:text-slate-600" />
              <p className="text-lg text-slate-500 dark:text-slate-400">
                제안을 선택하여 상세 정보를 확인하세요
              </p>
              <p className="text-sm text-slate-400 dark:text-slate-500 mt-2">
                승인하면 자동으로 룰셋이 생성됩니다
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
