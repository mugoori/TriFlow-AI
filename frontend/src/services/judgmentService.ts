/**
 * Judgment Service
 * Judgment Execute API 호출
 */
import api from './api';

export interface JudgmentExecuteRequest {
  ruleset_id: string;
  input_data: Record<string, any>;
  policy?: 'rule_only' | 'llm_only' | 'hybrid_weighted' | 'hybrid_gate' | 'rule_fallback' | 'llm_fallback' | 'escalate';
  need_explanation?: boolean;
  context?: Record<string, any>;
}

export interface Evidence {
  input_values: Record<string, any>;
  calculated_metrics: Record<string, any>;
  thresholds: Record<string, any>;
  historical_avg: Record<string, number>;
  similar_cases_count: number;
  rule_checks: Array<{
    name: string;
    status: string;
    value?: any;
    threshold?: any;
    passed: boolean;
  }>;
  data_refs: Array<{
    type: string;
    id?: string;
    name?: string;
    version?: string;
    model?: string;
  }>;
}

export interface RecommendedAction {
  priority: 'immediate' | 'high' | 'medium' | 'low';
  action: string;
  reason: string;
  field?: string;
  current_value?: any;
  threshold?: any;
}

export interface JudgmentExecuteResponse {
  execution_id: string;
  decision: 'OK' | 'WARNING' | 'CRITICAL' | 'UNKNOWN';
  confidence: number;
  source: string;
  policy_used: string;
  execution_time_ms: number;
  cached: boolean;
  explanation?: {
    summary: string;
    decision_factors: any[];
    source_details: Record<string, any>;
    policy?: string;
  };
  evidence?: Evidence;
  feature_importance?: Record<string, number>;
  recommended_actions?: RecommendedAction[];
  rule_result?: any;
  llm_result?: any;
  details: Record<string, any>;
  timestamp: string;
}

export interface JudgmentExecutionListResponse {
  executions: Array<{
    execution_id: string;
    ruleset_id: string | null;
    result: string;
    confidence: number;
    method_used: string;
    executed_at: string | null;
    input_summary: string | null;
  }>;
  total: number;
}

/**
 * Judgment 실행
 */
export const executeJudgment = async (
  request: JudgmentExecuteRequest
): Promise<JudgmentExecuteResponse> => {
  const response = await api.post('/api/v1/judgment/execute', request);
  return response.data;
};

/**
 * 최근 Judgment Execution 목록 조회
 */
export const getRecentExecutions = async (params?: {
  limit?: number;
  ruleset_id?: string;
  result?: string;
}): Promise<JudgmentExecutionListResponse> => {
  const response = await api.get('/api/v1/judgment/executions/recent', { params });
  return response.data;
};

/**
 * Judgment Execution 재실행 (Replay)
 */
export const replayExecution = async (
  execution_id: string,
  use_current_ruleset: boolean = true
): Promise<any> => {
  const response = await api.post(`/api/v1/judgment/replay/${execution_id}`, {
    use_current_ruleset,
  });
  return response.data;
};

export const judgmentService = {
  executeJudgment,
  getRecentExecutions,
  replayExecution,
};
