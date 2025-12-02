/**
 * LearningPage - 학습 대시보드
 * 피드백 통계, AI 제안 목록, A/B 테스트 요약을 통합 표시
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
  CheckCircle,
  XCircle,
  Clock,
  FlaskConical,
  Lightbulb,
  MessageSquare,
  RefreshCw,
  Play,
  Pause,
} from 'lucide-react';
import {
  getFeedbackStats,
  listFeedback,
  FeedbackStats,
  FeedbackResponse,
} from '@/services/feedbackService';
import {
  getProposalStats,
  listProposals,
  reviewProposal,
  ProposalStats,
  Proposal,
} from '@/services/proposalService';
import {
  listExperiments,
  Experiment,
} from '@/services/experimentService';

export function LearningPage() {
  // Feedback State
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  const [recentFeedback, setRecentFeedback] = useState<FeedbackResponse[]>([]);
  const [feedbackLoading, setFeedbackLoading] = useState(true);

  // Proposal State
  const [proposalStats, setProposalStats] = useState<ProposalStats | null>(null);
  const [pendingProposals, setPendingProposals] = useState<Proposal[]>([]);
  const [proposalLoading, setProposalLoading] = useState(true);

  // Experiment State
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [experimentLoading, setExperimentLoading] = useState(true);

  // Error State
  const [error, setError] = useState<string | null>(null);

  // Load Feedback Data
  const loadFeedbackData = useCallback(async () => {
    try {
      setFeedbackLoading(true);
      const [stats, feedbackList] = await Promise.all([
        getFeedbackStats(),
        listFeedback({ limit: 5, is_processed: false }),
      ]);
      setFeedbackStats(stats);
      setRecentFeedback(feedbackList || []);
    } catch (err) {
      console.error('Failed to load feedback data:', err);
      // 데모 데이터로 폴백
      setFeedbackStats({
        total: 128,
        positive: 95,
        negative: 18,
        correction: 15,
        unprocessed: 12,
      });
      setRecentFeedback([]);
    } finally {
      setFeedbackLoading(false);
    }
  }, []);

  // Load Proposal Data
  const loadProposalData = useCallback(async () => {
    try {
      setProposalLoading(true);
      const [stats, proposalList] = await Promise.all([
        getProposalStats(),
        listProposals({ status: 'pending', limit: 5 }),
      ]);
      setProposalStats(stats);
      setPendingProposals(proposalList.proposals || []);
    } catch (err) {
      console.error('Failed to load proposal data:', err);
      // 데모 데이터로 폴백
      setProposalStats({
        total: 45,
        pending: 8,
        approved: 32,
        rejected: 3,
        deployed: 28,
      });
      setPendingProposals([]);
    } finally {
      setProposalLoading(false);
    }
  }, []);

  // Load Experiment Data
  const loadExperimentData = useCallback(async () => {
    try {
      setExperimentLoading(true);
      const response = await listExperiments({ limit: 5 });
      setExperiments(response.experiments || []);
    } catch (err) {
      console.error('Failed to load experiment data:', err);
      // 데모 데이터로 폴백
      setExperiments([]);
    } finally {
      setExperimentLoading(false);
    }
  }, []);

  // Load all data
  const loadAllData = useCallback(async () => {
    setError(null);
    await Promise.all([
      loadFeedbackData(),
      loadProposalData(),
      loadExperimentData(),
    ]);
  }, [loadFeedbackData, loadProposalData, loadExperimentData]);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  // Handle Proposal Review
  const handleProposalReview = async (proposalId: string, action: 'approve' | 'reject') => {
    try {
      await reviewProposal(proposalId, action, action === 'approve' ? '승인됨' : '거부됨');
      await loadProposalData();
    } catch (err) {
      console.error('Failed to review proposal:', err);
      setError('제안 검토 중 오류가 발생했습니다.');
    }
  };

  // Stats Card Component
  const StatsCard = ({
    title,
    value,
    icon: Icon,
    color,
    subtitle,
  }: {
    title: string;
    value: number | string;
    icon: React.ElementType;
    color: string;
    subtitle?: string;
  }) => (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  );

  return (
    <div className="p-6 space-y-6 overflow-auto h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            학습 대시보드
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            피드백 분석, AI 제안 검토, A/B 테스트 현황을 한눈에 확인
          </p>
        </div>
        <button
          onClick={loadAllData}
          className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          새로고침
        </button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className="text-red-700 dark:text-red-300">{error}</span>
        </div>
      )}

      {/* Feedback Section */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <MessageSquare className="w-5 h-5" />
          피드백 통계
        </h2>

        {feedbackLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="bg-gray-100 dark:bg-gray-700 rounded-lg h-24 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatsCard
              title="전체 피드백"
              value={feedbackStats?.total || 0}
              icon={MessageSquare}
              color="bg-blue-500"
            />
            <StatsCard
              title="긍정적"
              value={feedbackStats?.positive || 0}
              icon={ThumbsUp}
              color="bg-green-500"
              subtitle={`${feedbackStats && feedbackStats.total > 0 ? Math.round((feedbackStats.positive / feedbackStats.total) * 100) : 0}%`}
            />
            <StatsCard
              title="부정적"
              value={feedbackStats?.negative || 0}
              icon={ThumbsDown}
              color="bg-red-500"
              subtitle={`${feedbackStats && feedbackStats.total > 0 ? Math.round((feedbackStats.negative / feedbackStats.total) * 100) : 0}%`}
            />
            <StatsCard
              title="수정 제안"
              value={feedbackStats?.correction || 0}
              icon={AlertCircle}
              color="bg-yellow-500"
            />
            <StatsCard
              title="미처리"
              value={feedbackStats?.unprocessed || 0}
              icon={Clock}
              color="bg-gray-500"
            />
          </div>
        )}

        {/* Recent Feedback List */}
        {recentFeedback.length > 0 && (
          <div className="mt-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="font-medium text-gray-900 dark:text-white">최근 미처리 피드백</h3>
            </div>
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {recentFeedback.map((fb) => (
                <div key={fb.feedback_id} className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {fb.feedback_type === 'positive' && <ThumbsUp className="w-4 h-4 text-green-500" />}
                    {fb.feedback_type === 'negative' && <ThumbsDown className="w-4 h-4 text-red-500" />}
                    {fb.feedback_type === 'correction' && <AlertCircle className="w-4 h-4 text-yellow-500" />}
                    <span className="text-sm text-gray-700 dark:text-gray-300">{fb.feedback_text || '코멘트 없음'}</span>
                  </div>
                  <span className="text-xs text-gray-400">
                    {new Date(fb.created_at).toLocaleDateString('ko-KR')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Proposals Section */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Lightbulb className="w-5 h-5" />
          AI 제안 규칙
        </h2>

        {proposalLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="bg-gray-100 dark:bg-gray-700 rounded-lg h-24 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatsCard
              title="전체 제안"
              value={proposalStats?.total || 0}
              icon={Lightbulb}
              color="bg-purple-500"
            />
            <StatsCard
              title="검토 대기"
              value={proposalStats?.pending || 0}
              icon={Clock}
              color="bg-yellow-500"
            />
            <StatsCard
              title="승인됨"
              value={proposalStats?.approved || 0}
              icon={CheckCircle}
              color="bg-green-500"
            />
            <StatsCard
              title="거부됨"
              value={proposalStats?.rejected || 0}
              icon={XCircle}
              color="bg-red-500"
            />
            <StatsCard
              title="배포됨"
              value={proposalStats?.deployed || 0}
              icon={Play}
              color="bg-blue-500"
            />
          </div>
        )}

        {/* Pending Proposals List */}
        {pendingProposals.length > 0 && (
          <div className="mt-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="font-medium text-gray-900 dark:text-white">검토 대기 중인 제안</h3>
            </div>
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {pendingProposals.map((proposal) => (
                <div key={proposal.proposal_id} className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h4 className="font-medium text-gray-900 dark:text-white">
                        {proposal.rule_name}
                      </h4>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {proposal.rule_description || '설명 없음'}
                      </p>
                      <div className="flex items-center gap-4 mt-2">
                        <span className="text-xs text-gray-400">
                          신뢰도: {Math.round((proposal.confidence || 0) * 100)}%
                        </span>
                        <span className="text-xs text-gray-400">
                          {new Date(proposal.created_at).toLocaleDateString('ko-KR')}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <button
                        onClick={() => handleProposalReview(proposal.proposal_id, 'approve')}
                        className="p-2 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded-lg transition-colors"
                        title="승인"
                      >
                        <CheckCircle className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleProposalReview(proposal.proposal_id, 'reject')}
                        className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                        title="거부"
                      >
                        <XCircle className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {pendingProposals.length === 0 && !proposalLoading && (
          <div className="mt-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg p-8 text-center">
            <Lightbulb className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400">검토 대기 중인 제안이 없습니다</p>
          </div>
        )}
      </section>

      {/* A/B Test Section */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <FlaskConical className="w-5 h-5" />
          A/B 테스트 현황
        </h2>

        {experimentLoading ? (
          <div className="space-y-4">
            {[...Array(2)].map((_, i) => (
              <div key={i} className="bg-gray-100 dark:bg-gray-700 rounded-lg h-32 animate-pulse" />
            ))}
          </div>
        ) : experiments.length > 0 ? (
          <div className="space-y-4">
            {experiments.map((exp) => (
              <div
                key={exp.experiment_id}
                className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-gray-900 dark:text-white">{exp.name}</h3>
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full ${
                          exp.status === 'running'
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                            : exp.status === 'completed'
                            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                            : exp.status === 'paused'
                            ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                            : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-400'
                        }`}
                      >
                        {exp.status === 'running' && (
                          <span className="flex items-center gap-1">
                            <Play className="w-3 h-3" /> 실행 중
                          </span>
                        )}
                        {exp.status === 'completed' && '완료'}
                        {exp.status === 'paused' && (
                          <span className="flex items-center gap-1">
                            <Pause className="w-3 h-3" /> 일시정지
                          </span>
                        )}
                        {exp.status === 'draft' && '초안'}
                        {exp.status === 'cancelled' && '취소됨'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      {exp.description || exp.hypothesis || '설명 없음'}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 text-sm text-gray-400">
                    {exp.traffic_percentage}% 트래픽
                  </div>
                </div>

                {/* Variants */}
                {exp.variants && exp.variants.length > 0 && (
                  <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
                    {exp.variants.map((variant) => (
                      <div key={variant.variant_id} className="text-center p-2 bg-gray-50 dark:bg-gray-700/50 rounded">
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {variant.is_control ? 'Control' : variant.name}
                        </p>
                        <p className="text-lg font-semibold text-gray-900 dark:text-white">
                          {variant.traffic_weight}%
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Date Info */}
                <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
                  {exp.start_date && (
                    <span>시작: {new Date(exp.start_date).toLocaleDateString('ko-KR')}</span>
                  )}
                  {exp.end_date && (
                    <span>종료: {new Date(exp.end_date).toLocaleDateString('ko-KR')}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-8 text-center">
            <FlaskConical className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400">진행 중인 A/B 테스트가 없습니다</p>
          </div>
        )}
      </section>
    </div>
  );
}

export default LearningPage;
