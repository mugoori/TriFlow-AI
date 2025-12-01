/**
 * Feedback Service
 * 사용자 피드백 수집 API 클라이언트
 */

import { apiClient } from './api';

// ============ Types ============

export type FeedbackType = 'positive' | 'negative' | 'correction';

export interface FeedbackCreate {
  feedback_type: FeedbackType;
  original_output?: Record<string, unknown>;
  corrected_output?: Record<string, unknown>;
  feedback_text?: string;
  context_data?: Record<string, unknown>;
  message_id?: string;
  agent_type?: string;
}

export interface FeedbackResponse {
  feedback_id: string;
  feedback_type: FeedbackType;
  original_output?: Record<string, unknown>;
  corrected_output?: Record<string, unknown>;
  feedback_text?: string;
  context_data: Record<string, unknown>;
  is_processed: boolean;
  created_at: string;
}

export interface FeedbackStats {
  total: number;
  positive: number;
  negative: number;
  correction: number;
  unprocessed: number;
}

// ============ API Functions ============

/**
 * 피드백 생성
 */
export async function createFeedback(data: FeedbackCreate): Promise<FeedbackResponse> {
  const response = await apiClient.post('/api/v1/feedback', data);
  return response.data;
}

/**
 * 피드백 목록 조회
 */
export async function listFeedback(params?: {
  feedback_type?: FeedbackType;
  is_processed?: boolean;
  limit?: number;
  offset?: number;
}): Promise<FeedbackResponse[]> {
  const response = await apiClient.get('/api/v1/feedback', { params });
  return response.data;
}

/**
 * 피드백 통계 조회
 */
export async function getFeedbackStats(): Promise<FeedbackStats> {
  const response = await apiClient.get('/api/v1/feedback/stats');
  return response.data;
}

/**
 * 피드백 상세 조회
 */
export async function getFeedback(feedbackId: string): Promise<FeedbackResponse> {
  const response = await apiClient.get(`/api/v1/feedback/${feedbackId}`);
  return response.data;
}

/**
 * 피드백 처리됨 마킹
 */
export async function markFeedbackAsProcessed(feedbackId: string): Promise<void> {
  await apiClient.patch(`/api/v1/feedback/${feedbackId}/process`);
}

/**
 * 피드백 삭제
 */
export async function deleteFeedback(feedbackId: string): Promise<void> {
  await apiClient.delete(`/api/v1/feedback/${feedbackId}`);
}

// ============ Helper Functions ============

/**
 * 빠른 피드백 전송 (좋아요/싫어요)
 */
export async function sendQuickFeedback(
  type: 'positive' | 'negative',
  messageId: string,
  agentType?: string,
  originalOutput?: Record<string, unknown>
): Promise<FeedbackResponse> {
  return createFeedback({
    feedback_type: type,
    message_id: messageId,
    agent_type: agentType,
    original_output: originalOutput,
  });
}

/**
 * 상세 피드백 전송 (코멘트 포함)
 */
export async function sendDetailedFeedback(
  type: FeedbackType,
  messageId: string,
  feedbackText: string,
  options?: {
    agentType?: string;
    originalOutput?: Record<string, unknown>;
    correctedOutput?: Record<string, unknown>;
  }
): Promise<FeedbackResponse> {
  return createFeedback({
    feedback_type: type,
    message_id: messageId,
    feedback_text: feedbackText,
    agent_type: options?.agentType,
    original_output: options?.originalOutput,
    corrected_output: options?.correctedOutput,
  });
}
