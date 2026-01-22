/**
 * Module Management Service
 * API calls for module upload, installation, and management
 */
import { apiClient } from './api';
import { tenantService } from './tenantService';

export interface ModuleInfo {
  module_code: string;
  name: string;
  version: string;
  category: string;
  description: string;
  author?: string;
  icon?: string;
  is_enabled: boolean;
  is_system: boolean;
  can_uninstall: boolean;
  installed_at?: string;
}

export interface InstallResponse {
  success: boolean;
  module_code: string;
  version: string;
  installation_id: string;
  message: string;
}

export interface InstallationProgress {
  installation_id: string;
  module_code: string;
  version: string;
  status: 'pending' | 'installing' | 'success' | 'failed';
  progress: number;
  current_step: string;
  current_step_index: number;
  logs: Array<{ timestamp: string; level: string; message: string }>;
  error?: string;
}

class ModuleService {
  /**
   * List installed modules
   */
  async listModules(category?: string): Promise<ModuleInfo[]> {
    const endpoint = category ? `/api/v1/modules?category=${category}` : '/api/v1/modules';
    return await apiClient.get<ModuleInfo[]>(endpoint);
  }

  /**
   * Upload and install module from ZIP file
   */
  async uploadModule(file: File, force: boolean = false): Promise<InstallResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const token = localStorage.getItem('triflow_access_token');

    const response = await fetch(`${baseUrl}/api/v1/modules/upload?force=${force}`, {
      method: 'POST',
      headers: {
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      },
      body: formData
    });

    if (!response.ok) {
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        const error = await response.json();
        console.error('[MODULE UPLOAD] Server error response:', JSON.stringify(error, null, 2));

        // 에러 메시지 추출 (프로젝트의 에러 구조에 맞춤)
        const errorMessage = error.detail || error.error?.message || error.message || `HTTP ${response.status}: ${response.statusText}`;
        console.error('[MODULE UPLOAD] Error message:', errorMessage);
        throw new Error(errorMessage);
      } else {
        const text = await response.text();
        console.error('[MODULE UPLOAD] Non-JSON error response:', text);
        throw new Error(`HTTP ${response.status}: ${text || response.statusText}`);
      }
    }

    return await response.json();
  }

  /**
   * Get installation progress
   */
  async getInstallationProgress(installationId: string): Promise<InstallationProgress> {
    return await apiClient.get<InstallationProgress>(`/api/v1/modules/install/${installationId}`);
  }

  /**
   * Uninstall module
   */
  async uninstallModule(moduleCode: string, keepData: boolean = false): Promise<void> {
    const endpoint = keepData
      ? `/api/v1/modules/${moduleCode}?keep_data=true`
      : `/api/v1/modules/${moduleCode}`;
    await apiClient.delete(endpoint);
  }

  /**
   * Enable/disable module for current tenant
   */
  async toggleModule(moduleCode: string, enabled: boolean): Promise<void> {
    if (enabled) {
      await tenantService.enableModule(moduleCode);
    } else {
      await tenantService.disableModule(moduleCode);
    }
  }
}

export const moduleService = new ModuleService();
