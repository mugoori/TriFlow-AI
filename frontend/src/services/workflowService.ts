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

// 워크플로우 노드 타입 정의
// P0: condition, action, if_else, loop, parallel (기본)
// P1: data, judgment, bi, mcp, trigger, wait, approval (비즈니스)
// P2: compensation, deploy, rollback, simulate (고급)
export type WorkflowNodeType =
  // P0 기본
  | 'condition'
  | 'action'
  | 'if_else'
  | 'loop'
  | 'parallel'
  // P1 비즈니스
  | 'data'
  | 'judgment'
  | 'bi'
  | 'mcp'
  | 'trigger'
  | 'wait'
  | 'approval'
  // P2 고급
  | 'compensation'
  | 'deploy'
  | 'rollback'
  | 'simulate';

export interface WorkflowNode {
  id: string;
  type: WorkflowNodeType;
  config: Record<string, unknown>;
  next?: string[];  // 선택적: 중첩 노드 구조에서는 next 대신 then_nodes/else_nodes 사용
  // 중첩 노드 구조
  then_nodes?: WorkflowNode[];
  else_nodes?: WorkflowNode[];
  loop_nodes?: WorkflowNode[];
  parallel_nodes?: WorkflowNode[];
}

// 승인 요청 인터페이스
export interface ApprovalRequest {
  approval_id: string;
  workflow_id: string;
  workflow_name: string;
  instance_id?: string;
  node_id: string;
  title: string;
  description?: string;
  approvers: Array<{
    user_id: string;
    email?: string;
    status: 'pending' | 'approved' | 'rejected';
  }>;
  status: 'pending' | 'approved' | 'rejected' | 'timeout' | 'cancelled';
  requested_at: string;
  timeout_at?: string;
  decided_by?: string;
  decided_at?: string;
  decision_comment?: string;
}

export interface ApprovalListResponse {
  approvals: ApprovalRequest[];
  total: number;
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
  display_name: string;
  description: string;
  category: string;
  category_display_name: string;
  parameters: Record<string, string>;
}

export interface CategoryInfo {
  name: string;
  display_name: string;
}

export interface ActionCatalogResponse {
  categories: CategoryInfo[];
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

// 시뮬레이션 실행 옵션
export interface WorkflowRunOptions {
  input_data?: Record<string, unknown>;
  use_simulated_data?: boolean;
  simulation_scenario?: 'normal' | 'alert' | 'random';
}

// 센서 시뮬레이터 응답
export interface SimulatorResponse {
  success: boolean;
  data: Record<string, unknown>;
  available_sensors: string[];
  available_scenarios: string[];
}

// 조건 테스트 응답
export interface ConditionTestResponse {
  condition: string;
  context: Record<string, unknown>;
  result: boolean;
  message: string;
}

// 실행 로그
export interface ExecutionLog {
  log_id: string;
  timestamp: string;
  event_type: string;
  details: Record<string, unknown>;
  workflow_id?: string;
  node_id?: string;
  context?: Record<string, unknown>;
}

export interface ExecutionLogResponse {
  logs: ExecutionLog[];
  total: number;
}

// 버전 관리 타입
export interface WorkflowVersion {
  version_id: string;
  workflow_id: string;
  version: number;
  dsl_definition: Record<string, unknown>;
  change_log: string | null;
  status: 'draft' | 'active' | 'deprecated' | 'archived';
  created_by: string | null;
  published_at: string | null;
  created_at: string;
}

export interface WorkflowVersionListResponse {
  versions: WorkflowVersion[];
  total: number;
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
   * 워크플로우 수정 (기본 정보)
   */
  async update(
    workflowId: string,
    params: { name?: string; description?: string; is_active?: boolean }
  ): Promise<Workflow> {
    return await apiClient.patch<Workflow>(`/api/v1/workflows/${workflowId}`, params);
  },

  /**
   * 워크플로우 DSL 수정 (전체 DSL 업데이트)
   */
  async updateDSL(workflowId: string, dsl: WorkflowDSL): Promise<Workflow> {
    console.log('[workflowService.updateDSL] workflowId:', workflowId);
    console.log('[workflowService.updateDSL] dsl:', JSON.stringify(dsl, null, 2));
    const result = await apiClient.patch<Workflow>(`/api/v1/workflows/${workflowId}`, {
      dsl_definition: dsl,
    });
    console.log('[workflowService.updateDSL] result:', result);
    return result;
  },

  /**
   * 워크플로우 삭제
   */
  async delete(workflowId: string): Promise<void> {
    await apiClient.delete(`/api/v1/workflows/${workflowId}`);
  },

  /**
   * 워크플로우 실행 (시뮬레이션 옵션 지원)
   */
  async run(workflowId: string, options?: WorkflowRunOptions): Promise<WorkflowInstance> {
    return await apiClient.post<WorkflowInstance>(
      `/api/v1/workflows/${workflowId}/run`,
      options || {}
    );
  },

  /**
   * 시뮬레이션 데이터 생성
   */
  async generateSimulatedData(params?: {
    sensors?: string[];
    scenario?: 'normal' | 'alert' | 'random';
    scenario_name?: string;
  }): Promise<SimulatorResponse> {
    return await apiClient.post<SimulatorResponse>(
      '/api/v1/workflows/simulator/generate',
      params || {}
    );
  },

  /**
   * 조건식 테스트
   */
  async testCondition(
    condition: string,
    context: Record<string, unknown>
  ): Promise<ConditionTestResponse> {
    return await apiClient.post<ConditionTestResponse>('/api/v1/workflows/test/condition', {
      condition,
      context,
    });
  },

  /**
   * 실행 로그 조회
   */
  async getExecutionLogs(params?: {
    workflow_id?: string;
    event_type?: string;
    limit?: number;
  }): Promise<ExecutionLogResponse> {
    const searchParams = new URLSearchParams();
    if (params?.workflow_id) searchParams.append('workflow_id', params.workflow_id);
    if (params?.event_type) searchParams.append('event_type', params.event_type);
    if (params?.limit) searchParams.append('limit', params.limit.toString());

    const query = searchParams.toString();
    return await apiClient.get<ExecutionLogResponse>(
      `/api/v1/workflows/logs/execution${query ? `?${query}` : ''}`
    );
  },

  /**
   * 실행 로그 초기화
   */
  async clearExecutionLogs(): Promise<{ success: boolean; message: string }> {
    return await apiClient.delete('/api/v1/workflows/logs/execution');
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

  // ============ 승인 관련 API ============

  /**
   * 대기 중인 승인 목록 조회
   */
  async getPendingApprovals(): Promise<ApprovalListResponse> {
    return await apiClient.get<ApprovalListResponse>('/api/v1/workflows/approvals/pending');
  },

  /**
   * 승인 처리
   */
  async approve(approvalId: string, comment?: string): Promise<{ success: boolean; message: string }> {
    return await apiClient.post(`/api/v1/workflows/approvals/${approvalId}/approve`, { comment });
  },

  /**
   * 거부 처리
   */
  async reject(approvalId: string, comment?: string): Promise<{ success: boolean; message: string }> {
    return await apiClient.post(`/api/v1/workflows/approvals/${approvalId}/reject`, { comment });
  },

  /**
   * 승인 이력 조회
   */
  async getApprovalHistory(params?: {
    workflow_id?: string;
    status?: string;
    limit?: number;
  }): Promise<ApprovalListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.workflow_id) searchParams.append('workflow_id', params.workflow_id);
    if (params?.status) searchParams.append('status', params.status);
    if (params?.limit) searchParams.append('limit', params.limit.toString());

    const query = searchParams.toString();
    return await apiClient.get<ApprovalListResponse>(
      `/api/v1/workflows/approvals${query ? `?${query}` : ''}`
    );
  },

  // ============ 인스턴스 상태/체크포인트 API ============

  /**
   * 인스턴스 상태 조회
   */
  async getInstanceState(instanceId: string): Promise<{
    instance_id: string;
    state: string;
    updated_at: string;
  }> {
    return await apiClient.get(`/api/v1/workflows/instances/${instanceId}/state`);
  },

  /**
   * 인스턴스 일시 중지
   */
  async pauseInstance(instanceId: string, reason?: string): Promise<{ success: boolean; message: string }> {
    return await apiClient.post(`/api/v1/workflows/instances/${instanceId}/pause`, { reason });
  },

  /**
   * 인스턴스 재개
   */
  async resumeInstance(instanceId: string, checkpointId?: string): Promise<{ success: boolean; message: string }> {
    return await apiClient.post(`/api/v1/workflows/instances/${instanceId}/resume`, { checkpoint_id: checkpointId });
  },

  /**
   * 인스턴스 취소
   */
  async cancelInstance(instanceId: string, reason?: string): Promise<{ success: boolean; message: string }> {
    return await apiClient.post(`/api/v1/workflows/instances/${instanceId}/cancel`, { reason });
  },

  /**
   * 체크포인트 목록 조회
   */
  async getCheckpoints(instanceId: string): Promise<{
    checkpoints: Array<{
      checkpoint_id: string;
      node_id: string;
      created_at: string;
      expires_at: string;
    }>;
  }> {
    return await apiClient.get(`/api/v1/workflows/instances/${instanceId}/checkpoints`);
  },

  // ============ 버전 관리 API ============

  /**
   * 워크플로우 버전 목록 조회
   */
  async listVersions(
    workflowId: string,
    status?: 'draft' | 'active' | 'deprecated' | 'archived'
  ): Promise<WorkflowVersionListResponse> {
    const params = status ? `?status=${status}` : '';
    return await apiClient.get<WorkflowVersionListResponse>(
      `/api/v1/workflows/${workflowId}/versions${params}`
    );
  },

  /**
   * 새 버전 생성 (현재 DSL 스냅샷)
   */
  async createVersion(
    workflowId: string,
    changeLog?: string
  ): Promise<WorkflowVersion> {
    return await apiClient.post<WorkflowVersion>(
      `/api/v1/workflows/${workflowId}/versions`,
      { change_log: changeLog }
    );
  },

  /**
   * 특정 버전 조회
   */
  async getVersion(workflowId: string, version: number): Promise<WorkflowVersion> {
    return await apiClient.get<WorkflowVersion>(
      `/api/v1/workflows/${workflowId}/versions/${version}`
    );
  },

  /**
   * 버전 배포 (active로 변경)
   */
  async publishVersion(
    workflowId: string,
    version: number
  ): Promise<{ success: boolean; message: string }> {
    return await apiClient.post(
      `/api/v1/workflows/${workflowId}/versions/${version}/publish`,
      {}
    );
  },

  /**
   * 특정 버전으로 롤백
   */
  async rollbackVersion(
    workflowId: string,
    version: number
  ): Promise<{ success: boolean; message: string }> {
    return await apiClient.post(
      `/api/v1/workflows/${workflowId}/versions/${version}/rollback`,
      {}
    );
  },

  /**
   * 버전 삭제
   */
  async deleteVersion(
    workflowId: string,
    version: number
  ): Promise<{ success: boolean; message: string }> {
    return await apiClient.delete(
      `/api/v1/workflows/${workflowId}/versions/${version}`
    );
  },
};
