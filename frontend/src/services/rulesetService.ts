/**
 * Ruleset Service
 * 룰셋 API 통신 서비스
 */

import { apiClient } from './api';

// ============ Types ============

export interface Ruleset {
  ruleset_id: string;
  name: string;
  description: string | null;
  rhai_script: string;
  version: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RulesetListResponse {
  rulesets: Ruleset[];
  total: number;
}

export interface RulesetCreateParams {
  name: string;
  description?: string;
  rhai_script: string;
}

export interface RulesetUpdateParams {
  name?: string;
  description?: string;
  rhai_script?: string;
  is_active?: boolean;
}

export interface RulesetExecuteParams {
  input_data: Record<string, unknown>;
}

export interface RulesetExecuteResponse {
  execution_id: string;
  ruleset_id: string;
  ruleset_name: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  confidence_score: number | null;
  execution_time_ms: number;
  executed_at: string;
}

export interface ExecutionHistoryResponse {
  executions: RulesetExecuteResponse[];
  total: number;
}

export interface SampleScript {
  name: string;
  description: string;
  script: string;
}

export interface SampleScriptsResponse {
  samples: SampleScript[];
  total: number;
}

export interface RulesetListParams {
  is_active?: boolean;
  search?: string;
}

// ============ Service ============

export const rulesetService = {
  /**
   * 룰셋 목록 조회
   */
  async list(params: RulesetListParams = {}): Promise<RulesetListResponse> {
    const searchParams = new URLSearchParams();

    if (params.is_active !== undefined) {
      searchParams.append('is_active', params.is_active.toString());
    }
    if (params.search) {
      searchParams.append('search', params.search);
    }

    const query = searchParams.toString();
    const endpoint = `/api/v1/rulesets${query ? `?${query}` : ''}`;

    return await apiClient.get<RulesetListResponse>(endpoint);
  },

  /**
   * 룰셋 상세 조회
   */
  async get(rulesetId: string): Promise<Ruleset> {
    return await apiClient.get<Ruleset>(`/api/v1/rulesets/${rulesetId}`);
  },

  /**
   * 룰셋 생성
   */
  async create(params: RulesetCreateParams): Promise<Ruleset> {
    return await apiClient.post<Ruleset>('/api/v1/rulesets', params);
  },

  /**
   * 룰셋 수정
   */
  async update(rulesetId: string, params: RulesetUpdateParams): Promise<Ruleset> {
    return await apiClient.patch<Ruleset>(`/api/v1/rulesets/${rulesetId}`, params);
  },

  /**
   * 룰셋 삭제
   */
  async delete(rulesetId: string): Promise<void> {
    await apiClient.delete(`/api/v1/rulesets/${rulesetId}`);
  },

  /**
   * 룰셋 실행
   */
  async execute(rulesetId: string, params: RulesetExecuteParams): Promise<RulesetExecuteResponse> {
    return await apiClient.post<RulesetExecuteResponse>(
      `/api/v1/rulesets/${rulesetId}/execute`,
      params
    );
  },

  /**
   * 실행 이력 조회
   */
  async getExecutions(rulesetId: string, limit?: number): Promise<ExecutionHistoryResponse> {
    const endpoint = limit
      ? `/api/v1/rulesets/${rulesetId}/executions?limit=${limit}`
      : `/api/v1/rulesets/${rulesetId}/executions`;

    return await apiClient.get<ExecutionHistoryResponse>(endpoint);
  },

  /**
   * 샘플 스크립트 목록 조회
   */
  async getSamples(): Promise<SampleScriptsResponse> {
    return await apiClient.get<SampleScriptsResponse>('/api/v1/rulesets/samples');
  },
};
