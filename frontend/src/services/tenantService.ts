import { apiClient } from './api';
import type { Tenant, TenantCreate, TenantUpdate } from '../types/tenant';

export const tenantService = {
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
};
