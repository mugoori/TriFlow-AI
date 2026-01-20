import { apiClient } from './api';
import type { Tenant, TenantCreate, TenantUpdate } from '../types/tenant';

// =====================================================
// Multi-Tenant Module Configuration Types
// =====================================================

export interface IndustryInfo {
  code: string;
  name: string;
  icon?: string;
  default_kpis: string[];
}

export interface FeatureFlags {
  can_use_rulesets: boolean;
  can_use_experiments: boolean;
  can_use_learning: boolean;
  can_use_mcp: boolean;
  max_workflows: number;
  max_judgments_per_day: number;
  max_users: number;
}

export interface TenantConfig {
  tenant_id: string;
  tenant_name: string;
  subscription_plan: string;
  enabled_modules: string[];
  module_configs: Record<string, unknown>;
  industry: IndustryInfo | null;
  features: FeatureFlags;
}

export interface ModuleInfo {
  module_code: string;
  name: string;
  description?: string;
  category: string;
  icon?: string;
  default_enabled: boolean;
  requires_subscription?: string;
  display_order: number;
  is_enabled: boolean;
  config: Record<string, unknown>;
}

export interface IndustryProfile {
  industry_code: string;
  name: string;
  description?: string;
  default_modules: string[];
  default_kpis: string[];
  sample_rulesets: string[];
  icon?: string;
}

// =====================================================
// Tenant Service
// =====================================================

export const tenantService = {
  // Basic Tenant CRUD
  async list(skip: number = 0, limit: number = 100): Promise<Tenant[]> {
    return apiClient.get<Tenant[]>(`/api/v1/tenants/?skip=${skip}&limit=${limit}`);
  },

  async get(tenantId: string): Promise<Tenant> {
    return apiClient.get<Tenant>(`/api/v1/tenants/${tenantId}`);
  },

  async create(data: TenantCreate): Promise<Tenant> {
    return apiClient.post<Tenant>('/api/v1/tenants/', data);
  },

  async update(tenantId: string, data: TenantUpdate): Promise<Tenant> {
    return apiClient.patch<Tenant>(`/api/v1/tenants/${tenantId}`, data);
  },

  async delete(tenantId: string): Promise<void> {
    return apiClient.delete<void>(`/api/v1/tenants/${tenantId}`);
  },

  // =====================================================
  // Multi-Tenant Module Configuration
  // =====================================================

  /**
   * 현재 테넌트의 설정 조회
   * 로그인 후 호출하여 동적 UI 렌더링에 사용
   */
  async getConfig(): Promise<TenantConfig> {
    return apiClient.get<TenantConfig>('/api/v1/tenant-config/tenant/config');
  },

  /**
   * 테넌트의 모든 모듈 목록 조회
   */
  async getModules(): Promise<ModuleInfo[]> {
    return apiClient.get<ModuleInfo[]>('/api/v1/tenant-config/tenant/modules');
  },

  /**
   * 모듈 활성화 (Admin 전용)
   */
  async enableModule(moduleCode: string, config?: Record<string, unknown>): Promise<void> {
    await apiClient.post('/api/v1/tenant-config/tenant/modules/enable', {
      module_code: moduleCode,
      config,
    });
  },

  /**
   * 모듈 비활성화 (Admin 전용)
   */
  async disableModule(moduleCode: string): Promise<void> {
    await apiClient.post('/api/v1/tenant-config/tenant/modules/disable', {
      module_code: moduleCode,
    });
  },

  /**
   * 모듈 설정 업데이트 (Admin 전용)
   */
  async updateModuleConfig(moduleCode: string, config: Record<string, unknown>): Promise<void> {
    await apiClient.patch('/api/v1/tenant/modules/config', {
      module_code: moduleCode,
      config,
    });
  },

  /**
   * 기능 플래그 조회
   */
  async getFeatures(): Promise<FeatureFlags> {
    return apiClient.get<FeatureFlags>('/api/v1/tenant/features');
  },

  /**
   * 산업 프로필 목록 조회
   */
  async getIndustryProfiles(): Promise<IndustryProfile[]> {
    return apiClient.get<IndustryProfile[]>('/api/v1/tenant/industries');
  },

  /**
   * 산업 프로필 변경 (Admin 전용)
   */
  async changeIndustry(industryCode: string, resetModules: boolean = false): Promise<void> {
    await apiClient.post('/api/v1/tenant/industry', {
      industry_code: industryCode,
      reset_modules: resetModules,
    });
  },

  /**
   * 특정 모듈이 활성화되어 있는지 확인
   */
  async isModuleEnabled(moduleCode: string): Promise<boolean> {
    const result = await apiClient.get<{ enabled: boolean }>(
      `/api/v1/tenant/modules/${moduleCode}/enabled`
    );
    return result.enabled;
  },
};
