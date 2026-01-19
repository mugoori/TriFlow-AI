/**
 * 인증 API 서비스
 * 로그인, 토큰 갱신, 사용자 정보 조회
 */

import type {
  LoginResponse,
  TokenResponse,
  User,
  AuthError,
  AuthErrorType,
} from '../types/auth';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const AUTH_API_URL = `${API_BASE_URL}/api/v1/auth`;

// localStorage 키
const STORAGE_KEYS = {
  ACCESS_TOKEN: 'triflow_access_token',
  REFRESH_TOKEN: 'triflow_refresh_token',
  USER: 'triflow_user',
} as const;

/**
 * 에러 타입 판별
 */
function getErrorType(error: unknown): AuthErrorType {
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return 'network';
  }
  if (error instanceof Error) {
    const message = error.message.toLowerCase();
    if (
      message.includes('401') ||
      message.includes('invalid') ||
      message.includes('incorrect')
    ) {
      return 'credentials';
    }
    if (message.includes('network') || message.includes('failed to fetch')) {
      return 'network';
    }
  }
  return 'unknown';
}

/**
 * AuthError 생성
 */
function createAuthError(error: unknown): AuthError {
  const type = getErrorType(error);
  let message: string;

  switch (type) {
    case 'credentials':
      message = '이메일 또는 비밀번호가 올바르지 않습니다.';
      break;
    case 'network':
      message = '서버에 연결할 수 없습니다. 네트워크 연결을 확인해주세요.';
      break;
    default:
      message = '로그인 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
  }

  return { type, message };
}

/**
 * 로그인 API 호출
 */
export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  try {
    const response = await fetch(`${AUTH_API_URL}/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }

    const data: LoginResponse = await response.json();

    // 토큰 및 사용자 정보 저장
    // 백엔드가 { user, tokens: { access_token, refresh_token } } 형식으로 응답
    const accessToken = data.tokens?.access_token || data.access_token;
    const refreshToken = data.tokens?.refresh_token || data.refresh_token;

    if (accessToken && refreshToken) {
      saveTokens(accessToken, refreshToken);
    }
    saveUser(data.user);

    return data;
  } catch (error) {
    // 네트워크 오류 또는 서버 오류 로그
    console.error('Login failed:', error);
    throw error;
  }
}

/**
 * 토큰 갱신 API 호출
 * 실패 시 자동으로 로그아웃 처리
 */
export async function refreshAccessToken(): Promise<TokenResponse | null> {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    clearAuth();
    return null;
  }

  try {
    const response = await fetch(`${AUTH_API_URL}/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      // Refresh 실패 시 모든 토큰 삭제 (무한 루프 방지)
      clearAuth();
      return null;
    }

    const data: TokenResponse = await response.json();

    // Access Token만 업데이트
    localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, data.access_token);

    return data;
  } catch {
    // 네트워크 오류 등 - 토큰 삭제
    clearAuth();
    return null;
  }
}

/**
 * 현재 사용자 정보 조회
 */
export async function getMe(accessToken: string): Promise<User | null> {
  try {
    const response = await fetch(`${AUTH_API_URL}/me`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch (error) {
    // 네트워크 오류 시 로그 출력
    console.error('Failed to fetch user info:', error);
    return null;
  }
}

/**
 * 토큰 저장
 */
export function saveTokens(
  accessToken: string,
  refreshToken: string
): void {
  localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, accessToken);
  localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refreshToken);
}

/**
 * 사용자 정보 저장
 */
export function saveUser(user: User): void {
  localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));
}

/**
 * Access Token 조회
 */
export function getAccessToken(): string | null {
  return localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
}

/**
 * Refresh Token 조회
 */
export function getRefreshToken(): string | null {
  return localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
}

/**
 * 저장된 사용자 정보 조회
 */
export function getSavedUser(): User | null {
  const userJson = localStorage.getItem(STORAGE_KEYS.USER);
  if (!userJson) return null;

  try {
    return JSON.parse(userJson) as User;
  } catch {
    return null;
  }
}

/**
 * 모든 인증 정보 삭제 (로그아웃)
 */
export function clearAuth(): void {
  localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
  localStorage.removeItem(STORAGE_KEYS.USER);
}

/**
 * 인증 상태 확인
 */
export function hasStoredAuth(): boolean {
  return !!getAccessToken() && !!getRefreshToken();
}

export { createAuthError, STORAGE_KEYS };
