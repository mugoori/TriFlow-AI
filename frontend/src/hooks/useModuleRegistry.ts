/**
 * Module Registry Hook
 *
 * 빌드 타임에 생성된 모듈 레지스트리를 로드하고
 * 모듈 정보를 제공합니다.
 */
import { useEffect, useState, useMemo } from 'react';

export interface ModuleManifest {
  module_code: string;
  version: string;
  name: string;
  description?: string;
  category: 'core' | 'feature' | 'industry' | 'integration';
  icon?: string;
  default_enabled: boolean;
  requires_subscription?: string | null;
  depends_on?: string[];
  display_order: number;
  backend?: {
    router_path?: string;
    api_prefix?: string;
    tags?: string[];
  };
  frontend?: {
    page_component?: string;
    route?: string;
    admin_only?: boolean;
    hide_from_nav?: boolean;
  };
}

interface ModuleRegistry {
  version: string;
  generated_at: string;
  modules: ModuleManifest[];
}

interface UseModuleRegistryResult {
  modules: ModuleManifest[];
  loading: boolean;
  error: Error | null;
  getModule: (moduleCode: string) => ModuleManifest | undefined;
  getModulesByCategory: (category: ModuleManifest['category']) => ModuleManifest[];
}

/**
 * 모듈 레지스트리를 로드하고 관리하는 훅
 *
 * @example
 * ```tsx
 * const { modules, loading, getModule } = useModuleRegistry();
 *
 * if (loading) return <Spinner />;
 *
 * const chatModule = getModule('chat');
 * ```
 */
export function useModuleRegistry(): UseModuleRegistryResult {
  const [registry, setRegistry] = useState<ModuleRegistry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function loadRegistry() {
      try {
        setLoading(true);
        // 동적 임포트로 레지스트리 로드
        // 빌드 시 생성되는 파일이므로 없을 수 있음
        const registryModule = await import('../modules/_registry.json');
        setRegistry(registryModule.default || registryModule);
        setError(null);
      } catch (err) {
        // 레지스트리가 없는 경우 (아직 빌드 안됨)
        console.warn('Module registry not found, using empty registry');
        setRegistry({ version: '0.0.0', generated_at: '', modules: [] });
        setError(null); // 에러로 처리하지 않음
      } finally {
        setLoading(false);
      }
    }

    loadRegistry();
  }, []);

  const modules = useMemo(() => {
    if (!registry) return [];
    return [...registry.modules].sort(
      (a, b) => (a.display_order || 999) - (b.display_order || 999)
    );
  }, [registry]);

  const getModule = (moduleCode: string): ModuleManifest | undefined => {
    return modules.find((m) => m.module_code === moduleCode);
  };

  const getModulesByCategory = (
    category: ModuleManifest['category']
  ): ModuleManifest[] => {
    return modules.filter((m) => m.category === category);
  };

  return {
    modules,
    loading,
    error,
    getModule,
    getModulesByCategory,
  };
}

/**
 * 특정 모듈이 존재하는지 확인하는 훅
 */
export function useModuleExists(moduleCode: string): boolean {
  const { modules } = useModuleRegistry();
  return modules.some((m) => m.module_code === moduleCode);
}

/**
 * 모듈의 아이콘 이름을 반환하는 유틸리티
 */
export function getModuleIcon(module: ModuleManifest): string {
  return module.icon || 'Box';
}

export default useModuleRegistry;
