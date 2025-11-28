/**
 * 인증 상태 관리 Context
 * 앱 전역에서 인증 상태 공유
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import type { User, AuthContextType, AuthError } from '../types/auth';
import * as authService from '../services/authService';

const AuthContext = createContext<AuthContextType | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = !!user && !!accessToken;

  /**
   * 로그아웃
   */
  const logout = useCallback(() => {
    authService.clearAuth();
    setUser(null);
    setAccessToken(null);
    setRefreshToken(null);
  }, []);

  /**
   * 자동 로그인 시도 (앱 시작 시)
   */
  const tryAutoLogin = useCallback(async () => {
    const storedAccessToken = authService.getAccessToken();
    const storedRefreshToken = authService.getRefreshToken();
    const storedUser = authService.getSavedUser();

    if (!storedAccessToken || !storedRefreshToken) {
      setIsLoading(false);
      return;
    }

    // 저장된 토큰으로 사용자 정보 확인
    const userInfo = await authService.getMe(storedAccessToken);

    if (userInfo) {
      // 토큰 유효 - 로그인 상태 복원
      setUser(userInfo);
      setAccessToken(storedAccessToken);
      setRefreshToken(storedRefreshToken);
      authService.saveUser(userInfo);
    } else {
      // Access Token 만료 - Refresh 시도
      const newToken = await authService.refreshAccessToken();

      if (newToken) {
        // Refresh 성공 - 새 토큰으로 사용자 정보 조회
        const refreshedUser = await authService.getMe(newToken.access_token);

        if (refreshedUser) {
          setUser(refreshedUser);
          setAccessToken(newToken.access_token);
          setRefreshToken(storedRefreshToken);
          authService.saveUser(refreshedUser);
        } else {
          // 여전히 실패 - 로그아웃
          logout();
        }
      } else {
        // Refresh 실패 - 로그아웃 (authService에서 이미 clearAuth 호출됨)
        setUser(null);
        setAccessToken(null);
        setRefreshToken(null);
      }
    }

    setIsLoading(false);
  }, [logout]);

  /**
   * 로그인
   */
  const login = useCallback(async (email: string, password: string) => {
    const response = await authService.login(email, password);

    setUser(response.user);
    setAccessToken(response.access_token);
    setRefreshToken(response.refresh_token);
  }, []);

  // 앱 시작 시 자동 로그인 시도
  useEffect(() => {
    tryAutoLogin();
  }, [tryAutoLogin]);

  const value: AuthContextType = {
    user,
    accessToken,
    refreshToken,
    isAuthenticated,
    isLoading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Auth Context 사용 Hook
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
}

export { authService as authUtils };
export type { AuthError };
