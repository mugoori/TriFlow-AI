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
  tool_calls: ToolCall[];
  iterations: number;
  routing_info?: Record<string, any>;
}

export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  agent_name?: string;
  tool_calls?: ToolCall[];
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
export type SSEEventType = 'start' | 'routing' | 'routed' | 'processing' | 'content' | 'tools' | 'done' | 'error';

export interface SSEEvent {
  type: SSEEventType;
  message?: string;
  agent?: string;
  content?: string;
  tool_calls?: Array<{ tool: string; input: Record<string, any> }>;
  agent_name?: string;
  iterations?: number;
}

export interface StreamingState {
  isStreaming: boolean;
  currentAgent?: string;
  status?: string;
}
