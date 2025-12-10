/**
 * Agent Service
 * Agent API와 통신하는 서비스
 */

import { apiClient } from './api';
import { getAccessToken } from './authService';
import type { AgentRequest, AgentResponse, SSEEvent } from '../types/agent';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const agentService = {
  /**
   * Meta Router를 통한 채팅 (일반 POST)
   */
  async chat(request: AgentRequest): Promise<AgentResponse> {
    return await apiClient.post<AgentResponse>('/api/v1/agents/chat', request);
  },

  /**
   * 스트리밍 채팅 (SSE)
   * @param request 채팅 요청
   * @param onEvent SSE 이벤트 콜백
   * @param onError 에러 콜백
   * @returns AbortController (취소용)
   */
  chatStream(
    request: AgentRequest,
    onEvent: (event: SSEEvent) => void,
    onError?: (error: Error) => void
  ): AbortController {
    const controller = new AbortController();

    const fetchStream = async () => {
      try {
        const token = getAccessToken();
        if (!token) {
          throw new Error('인증 토큰이 없습니다. 다시 로그인해주세요.');
        }

        const response = await fetch(`${API_BASE_URL}/api/v1/agents/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(request),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('Response body is not readable');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE 이벤트 파싱 (data: {...}\n\n 형식)
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || ''; // 마지막 불완전한 청크는 버퍼에 유지

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const jsonStr = line.slice(6); // 'data: ' 제거
                const event: SSEEvent = JSON.parse(jsonStr);
                onEvent(event);
              } catch (parseError) {
                console.warn('Failed to parse SSE event:', line);
              }
            }
          }
        }
      } catch (error) {
        if ((error as Error).name !== 'AbortError') {
          console.error('Stream error:', error);
          onError?.(error as Error);
        }
      }
    };

    fetchStream();
    return controller;
  },

  /**
   * Agent 시스템 상태 확인
   */
  async status(): Promise<any> {
    return await apiClient.get('/api/v1/agents/status');
  },
};
