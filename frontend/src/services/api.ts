import { getAccessToken, refreshAccessToken, clearAuth } from './authService';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export class ApiClient {
  private baseUrl: string;
  private isRefreshing = false;
  private refreshSubscribers: Array<(token: string | null) => void> = [];

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private subscribeTokenRefresh(cb: (token: string | null) => void) {
    this.refreshSubscribers.push(cb);
  }

  private onRefreshed(token: string | null) {
    this.refreshSubscribers.forEach(cb => cb(token));
    this.refreshSubscribers = [];
  }

  async request<T>(
    endpoint: string,
    options: RequestInit = {},
    retryCount = 0
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const token = getAccessToken();
    const config: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);

      // 401 에러 시 토큰 갱신 시도
      if (response.status === 401 && retryCount === 0) {
        // 이미 갱신 중이면 대기
        if (this.isRefreshing) {
          return new Promise<T>((resolve, reject) => {
            this.subscribeTokenRefresh((newToken) => {
              if (newToken) {
                // 새 토큰으로 재시도
                this.request<T>(endpoint, options, 1).then(resolve).catch(reject);
              } else {
                reject(new Error('Token refresh failed'));
              }
            });
          });
        }

        this.isRefreshing = true;
        try {
          const tokenResult = await refreshAccessToken();
          this.isRefreshing = false;

          if (tokenResult) {
            this.onRefreshed(tokenResult.access_token);
            // 새 토큰으로 재시도
            return this.request<T>(endpoint, options, 1);
          } else {
            this.onRefreshed(null);
            // 갱신 실패 시 로그아웃
            clearAuth();
            throw new Error('Session expired. Please login again.');
          }
        } catch (refreshError) {
          this.isRefreshing = false;
          this.onRefreshed(null);
          clearAuth();
          throw new Error('Session expired. Please login again.');
        }
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `HTTP ${response.status}: ${response.statusText}`
        );
      }

      // Handle 204 No Content
      if (response.status === 204) {
        return null as T;
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async patch<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async put<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  /**
   * FormData를 사용한 파일 업로드
   * Content-Type은 브라우저가 자동으로 multipart/form-data로 설정
   */
  async postFormData<T>(
    endpoint: string,
    formData: FormData,
    options: RequestInit = {},
    retryCount = 0
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const token = getAccessToken();
    const config: RequestInit = {
      method: 'POST',
      body: formData,
      ...options,
      headers: {
        // Content-Type을 설정하지 않음 - 브라우저가 boundary와 함께 자동 설정
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);

      // 401 에러 시 토큰 갱신 시도
      if (response.status === 401 && retryCount === 0) {
        if (this.isRefreshing) {
          return new Promise<T>((resolve, reject) => {
            this.subscribeTokenRefresh((newToken) => {
              if (newToken) {
                this.postFormData<T>(endpoint, formData, options, 1).then(resolve).catch(reject);
              } else {
                reject(new Error('Token refresh failed'));
              }
            });
          });
        }

        this.isRefreshing = true;
        try {
          const tokenResult = await refreshAccessToken();
          this.isRefreshing = false;

          if (tokenResult) {
            this.onRefreshed(tokenResult.access_token);
            return this.postFormData<T>(endpoint, formData, options, 1);
          } else {
            this.onRefreshed(null);
            clearAuth();
            throw new Error('Session expired. Please login again.');
          }
        } catch (refreshError) {
          this.isRefreshing = false;
          this.onRefreshed(null);
          clearAuth();
          throw new Error('Session expired. Please login again.');
        }
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `HTTP ${response.status}: ${response.statusText}`
        );
      }

      if (response.status === 204) {
        return null as T;
      }

      return await response.json();
    } catch (error) {
      console.error('File upload failed:', error);
      throw error;
    }
  }
}

export const apiClient = new ApiClient();
