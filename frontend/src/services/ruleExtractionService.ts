/**
 * Rule Extraction Service
 * Decision Tree 기반 규칙 추출 API 클라이언트
 */

import { apiClient } from './api';

// ============ Types ============

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'testing';
export type GenerationMethod = 'pattern_mining' | 'llm' | 'ensemble' | 'hybrid';

export interface ExtractionMetrics {
  coverage: number;
  precision: number;
  recall: number;
  f1_score: number;
  accuracy: number;
}

export interface RuleExtractionRequest {
  category?: string;
  min_samples?: number;
  max_depth?: number;
  min_quality_score?: number;
  class_weight?: 'balanced' | null;
}

export interface RuleExtractionResponse {
  candidate_id: string;
  samples_used: number;
  tree_depth: number;
  feature_count: number;
  class_count: number;
  metrics: ExtractionMetrics;
  rhai_preview: string;
  feature_importance: Record<string, number>;
}

export interface RuleCandidate {
  candidate_id: string;
  tenant_id: string;
  ruleset_id?: string;
  generated_rule: string;
  generation_method: GenerationMethod;
  coverage: number;
  precision: number;
  recall: number;
  f1_score: number;
  approval_status: ApprovalStatus;
  test_results?: Record<string, unknown>;
  rejection_reason?: string;
  created_at: string;
  updated_at?: string;
  approved_at?: string;
  approved_by?: string;
}

export interface CandidateListResponse {
  items: RuleCandidate[];
  total: number;
  page: number;
  page_size: number;
}

export interface CandidateListParams {
  status?: ApprovalStatus;
  page?: number;
  page_size?: number;
}

export interface TestSample {
  input: Record<string, unknown>;
  expected: Record<string, unknown>;
}

export interface TestRequest {
  test_samples: TestSample[];
}

export interface TestResultDetail {
  sample_index: number;
  input: Record<string, unknown>;
  expected: Record<string, unknown>;
  actual: Record<string, unknown>;
  passed: boolean;
  error?: string;
}

export interface TestResponse {
  total: number;
  passed: number;
  failed: number;
  accuracy: number;
  execution_time_ms: number;
  details: TestResultDetail[];
}

export interface ApproveRequest {
  rule_name?: string;
  description?: string;
}

export interface ApproveResponse {
  proposal_id: string;
  rule_name: string;
  confidence: number;
  status: string;
}

export interface ExtractionStats {
  total_candidates: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  testing_count: number;
  avg_f1_score: number;
  avg_coverage: number;
  recent_extractions: number;
  by_category: Record<string, number>;
}

// ============ API Functions ============

const BASE_PATH = '/api/v1/rule-extraction';

export const ruleExtractionService = {
  /**
   * Decision Tree 학습 및 규칙 추출
   */
  async extractRules(request?: RuleExtractionRequest): Promise<RuleExtractionResponse> {
    return apiClient.post<RuleExtractionResponse>(`${BASE_PATH}/extract`, request || {});
  },

  /**
   * 규칙 후보 목록 조회
   */
  async listCandidates(params?: CandidateListParams): Promise<CandidateListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));

    const queryString = searchParams.toString();
    const url = queryString ? `${BASE_PATH}/candidates?${queryString}` : `${BASE_PATH}/candidates`;
    return apiClient.get<CandidateListResponse>(url);
  },

  /**
   * 규칙 후보 상세 조회
   */
  async getCandidate(candidateId: string): Promise<RuleCandidate> {
    return apiClient.get<RuleCandidate>(`${BASE_PATH}/candidates/${candidateId}`);
  },

  /**
   * 규칙 후보 삭제
   */
  async deleteCandidate(candidateId: string): Promise<void> {
    await apiClient.delete(`${BASE_PATH}/candidates/${candidateId}`);
  },

  /**
   * 규칙 후보 테스트 실행
   */
  async testCandidate(candidateId: string, testSamples: TestSample[]): Promise<TestResponse> {
    return apiClient.post<TestResponse>(`${BASE_PATH}/candidates/${candidateId}/test`, {
      test_samples: testSamples,
    } as TestRequest);
  },

  /**
   * 규칙 후보 승인 → ProposedRule 생성
   */
  async approveCandidate(candidateId: string, request?: ApproveRequest): Promise<ApproveResponse> {
    return apiClient.post<ApproveResponse>(
      `${BASE_PATH}/candidates/${candidateId}/approve`,
      request || {}
    );
  },

  /**
   * 규칙 후보 거부
   */
  async rejectCandidate(candidateId: string, reason: string): Promise<RuleCandidate> {
    return apiClient.post<RuleCandidate>(`${BASE_PATH}/candidates/${candidateId}/reject`, {
      reason,
    });
  },

  /**
   * 규칙 추출 통계 조회
   */
  async getStats(): Promise<ExtractionStats> {
    return apiClient.get<ExtractionStats>(`${BASE_PATH}/stats`);
  },
};
