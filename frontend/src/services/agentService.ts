/**
 * Agent Service
 * Agent API와 통신하는 서비스
 */

import { apiClient } from './api';
import { getAccessToken } from './authService';
import type { AgentRequest, AgentResponse, SSEEvent } from '../types/agent';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Tauri 환경 여부 캐시
let _isTauri: boolean | null = null;

// Tauri 환경 여부 확인 (플러그인 로드 성공 여부로 판단)
async function isTauriEnvironment(): Promise<boolean> {
  if (_isTauri !== null) return _isTauri;
  try {
    await import('@tauri-apps/plugin-http');
    _isTauri = true;
    console.log('[agentService] Tauri environment detected');
  } catch {
    _isTauri = false;
    console.log('[agentService] Browser environment detected');
  }
  return _isTauri;
}

// Tauri HTTP 플러그인 fetch - 항상 시도 후 실패하면 브라우저 fetch 사용
async function getTauriFetch(): Promise<typeof fetch> {
  try {
    const { fetch: tauriFetch } = await import('@tauri-apps/plugin-http');
    return tauriFetch;
  } catch (e) {
    return window.fetch.bind(window);
  }
}

export const agentService = {
  /**
   * Meta Router를 통한 채팅 (일반 POST)
   */
  async chat(request: AgentRequest): Promise<AgentResponse> {
    return await apiClient.post<AgentResponse>('/api/v1/agents/chat', request);
  },

  /**
   * 스트리밍 채팅 (SSE)
   * Tauri 환경에서는 비스트리밍 API 사용 (SSE 미지원), 브라우저에서는 SSE 스트리밍 사용
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

        const isTauri = await isTauriEnvironment();

        if (isTauri) {
          // Tauri: 비스트리밍 API 사용 (Tauri HTTP 플러그인은 SSE 미지원)
          console.log('[agentService] Tauri detected, using non-streaming API');
          onEvent({ type: 'start' });
          onEvent({ type: 'routing' });

          const fetchFn = await getTauriFetch();
          const response = await fetchFn(`${API_BASE_URL}/api/v1/agents/chat`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify(request),
          });

          if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
          }

          const result: AgentResponse = await response.json();
          console.log('[agentService] Non-streaming response:', result);

          onEvent({ type: 'routed', agent: result.agent_name });
          onEvent({ type: 'content', content: result.response });
          if (result.tool_calls && result.tool_calls.length > 0) {
            onEvent({ type: 'tools', tool_calls: result.tool_calls });

            // Tauri: tool_calls에서 workflow 이벤트 추출 (SSE에서는 백엔드가 처리)
            for (const tc of result.tool_calls) {
              const toolName = tc.tool;
              const toolResult = tc.result;
              if (
                (toolName === 'create_workflow' || toolName === 'create_complex_workflow') &&
                toolResult &&
                typeof toolResult === 'object' &&
                toolResult.success &&
                toolResult.dsl
              ) {
                console.log('[agentService] Workflow detected in tool_calls:', toolResult.name);
                onEvent({
                  type: 'workflow',
                  workflow: {
                    dsl: toolResult.dsl,
                    workflowId: toolResult.workflow_id,
                    workflowName: toolResult.name,
                  },
                });
              }
            }
          }
          onEvent({ type: 'done', agent_name: result.agent_name });
        } else {
          // 브라우저: 기존 SSE 스트리밍 사용
          console.log('[agentService] Browser detected, using SSE streaming');

          const response = await window.fetch(`${API_BASE_URL}/api/v1/agents/chat/stream`, {
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
            if (done) {
              console.log('[agentService] Stream completed normally');
              break;
            }

            buffer += decoder.decode(value, { stream: true });

            // SSE 이벤트 파싱 (data: {...}\n\n 형식)
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // 마지막 불완전한 청크는 버퍼에 유지

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const jsonStr = line.slice(6); // 'data: ' 제거

                // [DONE] 시그널 처리 (스트림 종료)
                if (jsonStr === '[DONE]') {
                  console.log('[agentService] Received [DONE] signal, closing stream');
                  return; // 스트림 정상 종료
                }

                try {
                  const event: SSEEvent = JSON.parse(jsonStr);
                  onEvent(event);
                } catch (parseError) {
                  console.warn('Failed to parse SSE event:', line);
                }
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
