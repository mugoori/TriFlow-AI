/**
 * 인증 관련 TypeScript 타입 정의
 */

export interface User {
  user_id: string;
  tenant_id: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

// 에러 타입
export type AuthErrorType = 'credentials' | 'network' | 'unknown';

export interface AuthError {
  type: AuthErrorType;
  message: string;
}
