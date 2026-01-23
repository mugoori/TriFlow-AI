/**
 * Proposal Service
 * 제안된 규칙 관리 API 클라이언트
 */
import { apiClient } from './api';
import { appendQueryParams } from '@/utils/apiUtils';

// ============ Types ============

export interface Proposal {
  proposal_id: string;
  rule_name: string;
  rule_description: string | null;
  rhai_script: string;
  source_type: string;
  source_data: Record<string, unknown>;
  confidence: number;
  status: 'pending' | 'approved' | 'rejected' | 'deployed';
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProposalListResponse {
  total: number;
  proposals: Proposal[];
}

export interface ProposalStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  deployed: number;
}

export interface AnalysisResponse {
  status: string;
  message: string;
  patterns_found: number;
  proposals_created: number;
  patterns?: Array<{
    pattern_type: string;
    description: string;
    frequency: number;
    suggested_action: string;
    confidence: number;
  }>;
  proposal_ids?: string[];
}

export interface ReviewResponse {
  status: string;
  message: string;
  proposal_id: string;
  ruleset_id?: string;
  ruleset_name?: string;
}

// ============ API Functions ============

/**
 * 제안 목록 조회
 */
export async function listProposals(params?: {
  status?: string;
  source_type?: string;
  limit?: number;
  offset?: number;
}): Promise<ProposalListResponse> {
  const url = appendQueryParams('/api/v1/proposals', params);
  return apiClient.get<ProposalListResponse>(url);
}

/**
 * 제안 통계 조회
 */
export async function getProposalStats(): Promise<ProposalStats> {
  return apiClient.get<ProposalStats>('/api/v1/proposals/stats');
}

/**
 * 제안 상세 조회
 */
export async function getProposal(proposalId: string): Promise<Proposal> {
  return apiClient.get<Proposal>(`/api/v1/proposals/${proposalId}`);
}

/**
 * 제안 검토 (승인/거절)
 */
export async function reviewProposal(
  proposalId: string,
  action: 'approve' | 'reject',
  comment?: string
): Promise<ReviewResponse> {
  return apiClient.post<ReviewResponse>(`/api/v1/proposals/${proposalId}/review`, { action, comment });
}

/**
 * 제안 삭제
 */
export async function deleteProposal(proposalId: string): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>(`/api/v1/proposals/${proposalId}`);
}

/**
 * 피드백 분석 실행
 */
export async function runAnalysis(params?: {
  days?: number;
  min_frequency?: number;
}): Promise<AnalysisResponse> {
  const url = appendQueryParams('/api/v1/proposals/analyze', params);
  return apiClient.post<AnalysisResponse>(url, {});
}
