/**
 * Tenant Configuration Context
 * 테넌트별 모듈 설정 및 기능 플래그 관리
 *
 * Multi-Tenant Customization:
 * - 로그인 후 테넌트 설정 자동 로드
 * - 활성화된 모듈 기반 동적 UI 렌더링
 * - 구독 플랜 기반 기능 제한
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import { useAuth } from './AuthContext';
import {
  tenantService,
  type TenantConfig,
  type FeatureFlags,
} from '../services/tenantService';

interface TenantConfigContextType {
  /** 테넌트 설정 (로딩 전이면 null) */
  config: TenantConfig | null;
  /** 설정 로딩 중 여부 */
  loading: boolean;
  /** 에러 메시지 */
  error: string | null;
  /** 특정 모듈이 활성화되어 있는지 확인 */
  isModuleEnabled: (moduleCode: string) => boolean;
  /** 특정 기능 플래그 확인 */
  hasFeature: (featureName: keyof FeatureFlags) => boolean;
  /** 설정 새로고침 */
  refreshConfig: () => Promise<void>;
}

const TenantConfigContext = createContext<TenantConfigContextType | undefined>(undefined);

interface TenantConfigProviderProps {
  children: ReactNode;
}

export function TenantConfigProvider({ children }: TenantConfigProviderProps) {
  const { isAuthenticated, user } = useAuth();
  const [config, setConfig] = useState<TenantConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    if (!isAuthenticated) {
      setConfig(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await tenantService.getConfig();
      setConfig(data);
    } catch (err) {
      console.error('Failed to fetch tenant config:', err);
      setError('설정을 불러오는데 실패했습니다.');
      // 에러 발생 시에도 기본 config 설정하여 앱이 동작하도록
      setConfig(null);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  // 인증 상태 변경 시 설정 새로고침
  useEffect(() => {
    fetchConfig();
  }, [fetchConfig, user?.tenant_id]);

  /**
   * 특정 모듈이 활성화되어 있는지 확인
   */
  const isModuleEnabled = useCallback(
    (moduleCode: string): boolean => {
      if (!config) return false;
      return config.enabled_modules.includes(moduleCode);
    },
    [config]
  );

  /**
   * 특정 기능 플래그 확인
   */
  const hasFeature = useCallback(
    (featureName: keyof FeatureFlags): boolean => {
      if (!config) return false;
      const value = config.features[featureName];
      // boolean인 경우 그대로 반환, number인 경우 0보다 큰지 확인
      return typeof value === 'boolean' ? value : value > 0;
    },
    [config]
  );

  return (
    <TenantConfigContext.Provider
      value={{
        config,
        loading,
        error,
        isModuleEnabled,
        hasFeature,
        refreshConfig: fetchConfig,
      }}
    >
      {children}
    </TenantConfigContext.Provider>
  );
}

/**
 * TenantConfig Context Hook
 */
export function useTenantConfig() {
  const context = useContext(TenantConfigContext);
  if (context === undefined) {
    throw new Error('useTenantConfig must be used within a TenantConfigProvider');
  }
  return context;
}
