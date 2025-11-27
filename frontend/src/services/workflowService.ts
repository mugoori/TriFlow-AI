/**
 * Workflow Service
 * 워크플로우 API 통신 서비스
 */

import { apiClient } from './api';

// ============ Types ============

export interface WorkflowTrigger {
  type: 'event' | 'schedule' | 'manual';
  config: Record<string, unknown>;
}

export interface WorkflowNode {
  id: string;
  type: 'condition' | 'action';
  config: Record<string, unknown>;
  next: string[];
}

export interface WorkflowDSL {
  name: string;
  description?: string;
  trigger: WorkflowTrigger;
  nodes: WorkflowNode[];
}

export interface Workflow {
  workflow_id: string;
  name: string;
  description: string | null;
  dsl_definition: WorkflowDSL;
  version: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowListResponse {
  workflows: Workflow[];
  total: number;
}

export interface WorkflowInstance {
  instance_id: string;
  workflow_id: string;
  workflow_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface WorkflowInstanceListResponse {
  instances: WorkflowInstance[];
  total: number;
}

export interface ActionCatalogItem {
  name: string;
  description: string;
  category: string;
  parameters: Record<string, string>;
}

export interface ActionCatalogResponse {
  categories: string[];
  actions: ActionCatalogItem[];
  total: number;
}

export interface WorkflowCreateParams {
  name: string;
  description?: string;
  dsl_definition: WorkflowDSL;
}

export interface WorkflowListParams {
  is_active?: boolean;
  search?: string;
}

// ============ Service ============

export const workflowService = {
  /**
   * 워크플로우 목록 조회
   */
  async list(params: WorkflowListParams = {}): Promise<WorkflowListResponse> {
    const searchParams = new URLSearchParams();

    if (params.is_active !== undefined) {
      searchParams.append('is_active', params.is_active.toString());
    }
    if (params.search) {
      searchParams.append('search', params.search);
    }

    const query = searchParams.toString();
    const endpoint = `/api/v1/workflows${query ? `?${query}` : ''}`;

    return await apiClient.get<WorkflowListResponse>(endpoint);
  },

  /**
   * 워크플로우 상세 조회
   */
  async get(workflowId: string): Promise<Workflow> {
    return await apiClient.get<Workflow>(`/api/v1/workflows/${workflowId}`);
  },

  /**
   * 워크플로우 생성
   */
  async create(params: WorkflowCreateParams): Promise<Workflow> {
    return await apiClient.post<Workflow>('/api/v1/workflows', params);
  },

  /**
   * 워크플로우 수정
   */
  async update(
    workflowId: string,
    params: { name?: string; description?: string; is_active?: boolean }
  ): Promise<Workflow> {
    return await apiClient.patch<Workflow>(`/api/v1/workflows/${workflowId}`, params);
  },

  /**
   * 워크플로우 삭제
   */
  async delete(workflowId: string): Promise<void> {
    await apiClient.delete(`/api/v1/workflows/${workflowId}`);
  },

  /**
   * 워크플로우 실행
   */
  async run(workflowId: string, inputData?: Record<string, unknown>): Promise<WorkflowInstance> {
    return await apiClient.post<WorkflowInstance>(
      `/api/v1/workflows/${workflowId}/run`,
      inputData || {}
    );
  },

  /**
   * 워크플로우 실행 이력 조회
   */
  async getInstances(
    workflowId: string,
    status?: string
  ): Promise<WorkflowInstanceListResponse> {
    const endpoint = status
      ? `/api/v1/workflows/${workflowId}/instances?status=${status}`
      : `/api/v1/workflows/${workflowId}/instances`;

    return await apiClient.get<WorkflowInstanceListResponse>(endpoint);
  },

  /**
   * 액션 카탈로그 조회
   */
  async getActionCatalog(category?: string): Promise<ActionCatalogResponse> {
    const endpoint = category
      ? `/api/v1/workflows/actions?category=${category}`
      : '/api/v1/workflows/actions';

    return await apiClient.get<ActionCatalogResponse>(endpoint);
  },
};
