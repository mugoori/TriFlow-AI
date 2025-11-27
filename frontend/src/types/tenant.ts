export interface Tenant {
  tenant_id: string;
  name: string;
  slug: string;
  settings: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface TenantCreate {
  name: string;
  slug: string;
  settings?: Record<string, any>;
}

export interface TenantUpdate {
  name?: string;
  slug?: string;
  settings?: Record<string, any>;
}
