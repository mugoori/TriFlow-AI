/**
 * Agent Service
 * Agent API와 통신하는 서비스
 */

import { apiClient } from './api';
import type { AgentRequest, AgentResponse } from '../types/agent';

export const agentService = {
  /**
   * Meta Router를 통한 채팅
   */
  async chat(request: AgentRequest): Promise<AgentResponse> {
    return await apiClient.post<AgentResponse>('/api/v1/agents/chat', request);
  },

  /**
   * Agent 시스템 상태 확인
   */
  async status(): Promise<any> {
    return await apiClient.get('/api/v1/agents/status');
  },
};
