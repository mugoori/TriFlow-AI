/**
 * Feature Flag Service
 * V2 Feature Flags 관리 API
 */

import { apiClient } from './api';

export interface FeatureFlag {
  feature: string;
  name: string;
  description: string;
  enabled: boolean;
  rollout_percentage: number;
  tenant_overrides?: Record<string, boolean>;
}

export const featureFlagService = {
  /**
   * 모든 Feature Flags 조회
   */
  async listFlags(): Promise<FeatureFlag[]> {
    return apiClient.get<FeatureFlag[]>('/api/v2/feature-flags');
  },

  /**
   * Feature Flag 활성화
   */
  async enableFlag(feature: string): Promise<void> {
    return apiClient.post(`/api/v2/feature-flags/${feature}/enable`, {});
  },

  /**
   * Feature Flag 비활성화
   */
  async disableFlag(feature: string): Promise<void> {
    return apiClient.post(`/api/v2/feature-flags/${feature}/disable`, {});
  },

  /**
   * Rollout 비율 설정
   */
  async setRollout(feature: string, percentage: number): Promise<void> {
    return apiClient.post(`/api/v2/feature-flags/${feature}/rollout`, { percentage });
  },

  /**
   * Feature Flag 상태 조회
   */
  async getFlag(feature: string): Promise<FeatureFlag> {
    return apiClient.get<FeatureFlag>(`/api/v2/feature-flags/${feature}`);
  },
};
