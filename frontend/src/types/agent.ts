/**
 * Agent API Types
 */

export interface ToolCall {
  tool: string;
  input: Record<string, any>;
  result: any;
}

export interface AgentResponse {
  response: string;
  agent_name: string;
  model?: string;
  tool_calls: ToolCall[];
  iterations: number;
  routing_info?: Record<string, any>;
  response_data?: Record<string, any>;
}

export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  agent_name?: string;
  tool_calls?: ToolCall[];
  response_data?: Record<string, any>;
}

/**
 * 대화 이력 메시지 (API 전송용)
 */
export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AgentRequest {
  message: string;
  context?: Record<string, any>;
  tenant_id?: string;
  conversation_history?: ConversationMessage[];
}

// SSE Streaming Event Types
export type SSEEventType = 'start' | 'routing' | 'routed' | 'processing' | 'content' | 'tools' | 'workflow' | 'response_data' | 'done' | 'error';

// 워크플로우 노드 타입 (재귀적 정의)
export interface WorkflowNode {
  id: string;
  type: 'condition' | 'action' | 'if_else' | 'loop' | 'parallel';
  config: Record<string, unknown>;
  next?: string[];
  then_nodes?: WorkflowNode[];
  else_nodes?: WorkflowNode[];
  loop_nodes?: WorkflowNode[];
  parallel_nodes?: WorkflowNode[];
}

// 워크플로우 DSL 타입 (SSE 이벤트용)
export interface WorkflowDSL {
  name?: string;
  description?: string;
  trigger: {
    type: 'event' | 'schedule' | 'manual';
    config?: Record<string, unknown>;
  };
  nodes: WorkflowNode[];
}

export interface SSEEvent {
  type: SSEEventType;
  message?: string;
  agent?: string;
  content?: string;
  tool_calls?: Array<{ tool: string; input: Record<string, any> }>;
  agent_name?: string;
  model?: string;
  iterations?: number;
  // 워크플로우 이벤트 관련 필드
  workflow?: {
    dsl: WorkflowDSL;
    workflowId?: string;
    workflowName?: string;
  };
  // response_data 이벤트 관련 필드 (BI 인사이트, 차트, 테이블 등)
  data?: Record<string, any>;
}

export interface StreamingState {
  isStreaming: boolean;
  currentAgent?: string;
  status?: string;
}
