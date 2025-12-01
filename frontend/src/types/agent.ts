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

export interface AgentRequest {
  message: string;
  context?: Record<string, any>;
  tenant_id?: string;
}
