/**
 * Settings Service
 * 시스템 설정 API 클라이언트
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface SystemSetting {
  key: string;
  value: string | null;
  category: string;
  label: string;
  description?: string;
  sensitive: boolean;
}

export interface SettingsListResponse {
  settings: SystemSetting[];
  total: number;
}

export interface NotificationTestResult {
  status: 'success' | 'failed' | 'skipped';
  message: string;
  details?: Record<string, any>;
}

class SettingsService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_BASE_URL;
  }

  private getAuthHeader(): Record<string, string> {
    const token = localStorage.getItem('triflow_access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  /**
   * 모든 설정 조회
   */
  async getSettings(category?: string): Promise<SettingsListResponse> {
    const params = category ? `?category=${category}` : '';
    const response = await fetch(`${this.baseUrl}/api/v1/settings${params}`, {
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeader(),
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * 단일 설정 조회
   */
  async getSetting(key: string): Promise<SystemSetting> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/${key}`, {
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeader(),
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * 설정 업데이트
   */
  async updateSetting(key: string, value: string): Promise<SystemSetting> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/${key}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeader(),
      },
      body: JSON.stringify({ value }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * 여러 설정 일괄 업데이트
   */
  async updateSettings(settings: Record<string, string>): Promise<{ updated: string[] }> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/bulk`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeader(),
      },
      body: JSON.stringify({ settings }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Slack 알림 테스트
   */
  async testSlack(): Promise<NotificationTestResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/test/slack`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeader(),
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * Email 알림 테스트
   */
  async testEmail(to: string): Promise<NotificationTestResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/test/email`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeader(),
      },
      body: JSON.stringify({ to }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }
}

export const settingsService = new SettingsService();
