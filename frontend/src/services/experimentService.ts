/**
 * Experiment Service
 * A/B 테스트 실험 관리 API 클라이언트
 */
import { apiClient } from './api';
import { appendQueryParams } from '@/utils/apiUtils';

// ============ Types ============

export interface ExperimentVariant {
  variant_id: string;
  experiment_id: string;
  name: string;
  description: string | null;
  is_control: boolean;
  ruleset_id: string | null;
  traffic_weight: number;
  created_at: string;
}

export interface Experiment {
  experiment_id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  hypothesis: string | null;
  status: 'draft' | 'running' | 'paused' | 'completed' | 'cancelled';
  start_date: string | null;
  end_date: string | null;
  traffic_percentage: number;
  min_sample_size: number;
  confidence_level: number;
  created_at: string;
  updated_at: string;
  variants: ExperimentVariant[];
}

export interface ExperimentListResponse {
  total: number;
  experiments: Experiment[];
}

export interface VariantCreate {
  name: string;
  description?: string;
  is_control: boolean;
  ruleset_id?: string;
  traffic_weight: number;
}

export interface ExperimentCreate {
  name: string;
  description?: string;
  hypothesis?: string;
  traffic_percentage?: number;
  min_sample_size?: number;
  confidence_level?: number;
  variants?: VariantCreate[];
}

export interface ExperimentUpdate {
  name?: string;
  description?: string;
  hypothesis?: string;
  traffic_percentage?: number;
  min_sample_size?: number;
  confidence_level?: number;
}

export interface AssignmentResponse {
  experiment_id: string;
  variant_id: string;
  variant_name: string;
  is_control: boolean;
  ruleset_id: string | null;
  assigned_at: string;
}

export interface MetricSummary {
  count: number;
  mean: number;
  stddev: number;
  min: number;
  max: number;
}

export interface VariantStats {
  variant_id: string;
  name: string;
  is_control: boolean;
  traffic_weight: number;
  assignment_count: number;
  metrics: Record<string, MetricSummary>;
}

export interface ExperimentStats {
  experiment_id: string;
  status: string;
  total_assignments: number;
  variants: VariantStats[];
}

export interface TreatmentSignificance {
  name: string;
  n: number;
  mean: number;
  std: number;
  z_score: number | null;
  p_value: number | null;
  is_significant: boolean;
  relative_diff_percent: number | null;
  has_enough_samples: boolean;
}

export interface SignificanceResponse {
  metric_name: string;
  control: {
    name: string;
    n: number;
    mean: number;
    std: number;
  };
  treatments: TreatmentSignificance[];
  confidence_level: number;
  min_sample_size: number;
}

// ============ API Functions ============

/**
 * 실험 목록 조회
 */
export async function listExperiments(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<ExperimentListResponse> {
  const url = appendQueryParams('/api/v1/experiments', params);
  return apiClient.get<ExperimentListResponse>(url);
}

/**
 * 실험 상세 조회
 */
export async function getExperiment(experimentId: string): Promise<Experiment> {
  return apiClient.get<Experiment>(`/api/v1/experiments/${experimentId}`);
}

/**
 * 실험 생성
 */
export async function createExperiment(data: ExperimentCreate): Promise<Experiment> {
  return apiClient.post<Experiment>('/api/v1/experiments', data);
}

/**
 * 실험 수정
 */
export async function updateExperiment(experimentId: string, data: ExperimentUpdate): Promise<Experiment> {
  return apiClient.put<Experiment>(`/api/v1/experiments/${experimentId}`, data);
}

/**
 * 실험 삭제
 */
export async function deleteExperiment(experimentId: string): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>(`/api/v1/experiments/${experimentId}`);
}

/**
 * 변형 추가
 */
export async function addVariant(experimentId: string, data: VariantCreate): Promise<ExperimentVariant> {
  return apiClient.post<ExperimentVariant>(`/api/v1/experiments/${experimentId}/variants`, data);
}

/**
 * 변형 삭제
 */
export async function deleteVariant(experimentId: string, variantId: string): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>(`/api/v1/experiments/${experimentId}/variants/${variantId}`);
}

/**
 * 실험 시작
 */
export async function startExperiment(experimentId: string): Promise<Experiment> {
  return apiClient.post<Experiment>(`/api/v1/experiments/${experimentId}/start`, {});
}

/**
 * 실험 일시정지
 */
export async function pauseExperiment(experimentId: string): Promise<Experiment> {
  return apiClient.post<Experiment>(`/api/v1/experiments/${experimentId}/pause`, {});
}

/**
 * 실험 재개
 */
export async function resumeExperiment(experimentId: string): Promise<Experiment> {
  return apiClient.post<Experiment>(`/api/v1/experiments/${experimentId}/resume`, {});
}

/**
 * 실험 완료
 */
export async function completeExperiment(experimentId: string): Promise<Experiment> {
  return apiClient.post<Experiment>(`/api/v1/experiments/${experimentId}/complete`, {});
}

/**
 * 실험 취소
 */
export async function cancelExperiment(experimentId: string): Promise<Experiment> {
  return apiClient.post<Experiment>(`/api/v1/experiments/${experimentId}/cancel`, {});
}

/**
 * 사용자 할당
 */
export async function assignToExperiment(
  experimentId: string,
  data: { user_id?: string; session_id?: string }
): Promise<AssignmentResponse> {
  return apiClient.post<AssignmentResponse>(`/api/v1/experiments/${experimentId}/assign`, data);
}

/**
 * 실험 통계 조회
 */
export async function getExperimentStats(experimentId: string): Promise<ExperimentStats> {
  return apiClient.get<ExperimentStats>(`/api/v1/experiments/${experimentId}/stats`);
}

/**
 * 유의성 검정
 */
export async function getSignificance(experimentId: string, metricName: string): Promise<SignificanceResponse> {
  return apiClient.get<SignificanceResponse>(`/api/v1/experiments/${experimentId}/significance/${metricName}`);
}

/**
 * 메트릭 기록
 */
export async function recordMetric(
  experimentId: string,
  data: {
    variant_id: string;
    metric_name: string;
    metric_value: number;
    execution_id?: string;
    context_data?: Record<string, unknown>;
  }
): Promise<{ metric_id: string }> {
  return apiClient.post<{ metric_id: string }>(`/api/v1/experiments/${experimentId}/metrics`, data);
}
