/**
 * Sample Curation Service
 * 학습 샘플 관리 API 클라이언트
 */

import { apiClient } from './api';
import { appendQueryParams } from '@/utils/apiUtils';

// ============ Types ============

export type SourceType = 'feedback' | 'validation' | 'manual';
export type SampleStatus = 'pending' | 'approved' | 'rejected' | 'archived';
export type SampleCategory = 'threshold_adjustment' | 'field_correction' | 'validation_failure' | 'general';

export interface Sample {
  sample_id: string;
  tenant_id: string;
  feedback_id?: string;
  execution_id?: string;
  source_type: SourceType;
  category: string;
  input_data: Record<string, unknown>;
  expected_output: Record<string, unknown>;
  context: Record<string, unknown>;
  quality_score: number;
  confidence: number;
  content_hash: string;
  status: SampleStatus;
  rejection_reason?: string;
  created_at: string;
  updated_at: string;
  approved_at?: string;
  approved_by?: string;
}

export interface SampleListResponse {
  samples: Sample[];
  total: number;
  page: number;
  page_size: number;
}

export interface SampleStats {
  total_count: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  archived_count: number;
  by_category: Record<string, number>;
  by_source_type: Record<string, number>;
  avg_quality_score: number;
  min_quality_score: number;
  max_quality_score: number;
}

export interface SampleCreateRequest {
  category: string;
  input_data: Record<string, unknown>;
  expected_output: Record<string, unknown>;
  context?: Record<string, unknown>;
  source_type?: SourceType;
  quality_score?: number;
  confidence?: number;
}

export interface SampleExtractRequest {
  days?: number;
  min_confidence?: number;
  categories?: string[];
  dry_run?: boolean;
}

export interface SampleExtractResponse {
  extracted_count: number;
  skipped_duplicates: number;
  samples: Sample[];
  dry_run: boolean;
}

export interface SampleListParams {
  category?: string;
  status?: SampleStatus;
  source_type?: SourceType;
  min_quality?: number;
  page?: number;
  page_size?: number;
}

// ============ API Functions ============

const BASE_PATH = '/api/v1/samples';

export const sampleService = {
  /**
   * 샘플 목록 조회
   */
  async listSamples(params?: SampleListParams): Promise<SampleListResponse> {
    const url = appendQueryParams(BASE_PATH, params);
    return apiClient.get<SampleListResponse>(url);
  },

  /**
   * 샘플 상세 조회
   */
  async getSample(sampleId: string): Promise<Sample> {
    return apiClient.get<Sample>(`${BASE_PATH}/${sampleId}`);
  },

  /**
   * 샘플 생성 (수동)
   */
  async createSample(data: SampleCreateRequest): Promise<Sample> {
    return apiClient.post<Sample>(BASE_PATH, data);
  },

  /**
   * 샘플 승인
   */
  async approveSample(sampleId: string): Promise<Sample> {
    return apiClient.post<Sample>(`${BASE_PATH}/${sampleId}/approve`, {});
  },

  /**
   * 샘플 거부
   */
  async rejectSample(sampleId: string, reason: string): Promise<Sample> {
    return apiClient.post<Sample>(`${BASE_PATH}/${sampleId}/reject`, { reason });
  },

  /**
   * 샘플 삭제
   */
  async deleteSample(sampleId: string): Promise<void> {
    await apiClient.delete(`${BASE_PATH}/${sampleId}`);
  },

  /**
   * 피드백에서 샘플 자동 추출
   */
  async extractFromFeedback(params?: SampleExtractRequest): Promise<SampleExtractResponse> {
    return apiClient.post<SampleExtractResponse>(`${BASE_PATH}/extract`, params || {});
  },

  /**
   * 샘플 통계 조회
   */
  async getStats(): Promise<SampleStats> {
    return apiClient.get<SampleStats>(`${BASE_PATH}/stats`);
  },
};
