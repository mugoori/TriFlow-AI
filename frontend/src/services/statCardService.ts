/**
 * StatCard Service
 * 대시보드 StatCard API 호출 서비스
 */

import { apiClient } from './api';
import type {
  StatCardConfig,
  StatCardConfigCreate,
  StatCardConfigUpdate,
  StatCardListResponse,
  StatCardReorderRequest,
  KpiListResponse,
  AvailableTablesResponse,
  McpToolListResponse,
} from '../types/statcard';

const STAT_CARDS_BASE = '/api/v1/bi/stat-cards';

export const statCardService = {
  /**
   * 사용자 StatCard 목록 조회 (값 포함)
   */
  async getStatCards(): Promise<StatCardListResponse> {
    return apiClient.get<StatCardListResponse>(STAT_CARDS_BASE);
  },

  /**
   * StatCard 생성
   */
  async createStatCard(config: StatCardConfigCreate): Promise<StatCardConfig> {
    return apiClient.post<StatCardConfig>(STAT_CARDS_BASE, config);
  },

  /**
   * StatCard 수정
   */
  async updateStatCard(configId: string, update: StatCardConfigUpdate): Promise<StatCardConfig> {
    return apiClient.put<StatCardConfig>(`${STAT_CARDS_BASE}/${configId}`, update);
  },

  /**
   * StatCard 삭제
   */
  async deleteStatCard(configId: string): Promise<void> {
    return apiClient.delete<void>(`${STAT_CARDS_BASE}/${configId}`);
  },

  /**
   * StatCard 순서 변경
   */
  async reorderStatCards(cardIds: string[]): Promise<{ success: boolean }> {
    const request: StatCardReorderRequest = { card_ids: cardIds };
    return apiClient.put<{ success: boolean }>(`${STAT_CARDS_BASE}/reorder`, request);
  },

  /**
   * 사용 가능한 KPI 목록 조회
   */
  async getAvailableKpis(): Promise<KpiListResponse> {
    return apiClient.get<KpiListResponse>(`${STAT_CARDS_BASE}/kpis`);
  },

  /**
   * 사용 가능한 테이블/컬럼 목록 조회
   */
  async getAvailableTables(): Promise<AvailableTablesResponse> {
    return apiClient.get<AvailableTablesResponse>(`${STAT_CARDS_BASE}/tables`);
  },

  /**
   * 사용 가능한 MCP 도구 목록 조회
   */
  async getAvailableMcpTools(): Promise<McpToolListResponse> {
    return apiClient.get<McpToolListResponse>(`${STAT_CARDS_BASE}/mcp-tools`);
  },
};
