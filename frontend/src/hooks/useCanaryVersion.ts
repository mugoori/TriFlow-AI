/**
 * useCanaryVersion Hook
 *
 * Canary 버전 컨텍스트 훅.
 * - X-Canary-Version 헤더 추적
 * - 버전 변경 시 관련 React Query 캐시 무효화
 */
import { useEffect, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { apiClient, CANARY_AFFECTED_QUERY_KEYS } from '../services/api';

interface UseCanaryVersionReturn {
  /** 현재 Canary 버전 (v1 또는 v2) */
  canaryVersion: string | null;
  /** 현재 Canary 배포 ID */
  deploymentId: string | null;
  /** Canary 활성 여부 */
  isCanaryActive: boolean;
  /** 관련 캐시 수동 무효화 */
  invalidateCanaryQueries: () => void;
}

/**
 * Canary 버전 관리 훅
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { canaryVersion, isCanaryActive, invalidateCanaryQueries } = useCanaryVersion();
 *
 *   return (
 *     <div>
 *       {isCanaryActive && <span>Canary: {canaryVersion}</span>}
 *       <button onClick={invalidateCanaryQueries}>새로고침</button>
 *     </div>
 *   );
 * }
 * ```
 */
export function useCanaryVersion(): UseCanaryVersionReturn {
  const queryClient = useQueryClient();

  const [canaryVersion, setCanaryVersion] = useState<string | null>(
    apiClient.getCanaryVersion()
  );
  const [deploymentId, setDeploymentId] = useState<string | null>(
    apiClient.getCanaryDeploymentId()
  );

  /**
   * 관련 쿼리 캐시 부분 무효화
   * queryClient.clear() 대신 선택적 무효화로 성능 최적화
   */
  const invalidateCanaryQueries = useCallback(() => {
    CANARY_AFFECTED_QUERY_KEYS.forEach((key) => {
      queryClient.invalidateQueries({ queryKey: [key] });
    });
  }, [queryClient]);

  /**
   * 버전 변경 핸들러 등록
   */
  useEffect(() => {
    const handleVersionChange = (newVersion: string) => {
      setCanaryVersion(newVersion);
      setDeploymentId(apiClient.getCanaryDeploymentId());

      // 버전 변경 시 관련 캐시 무효화
      invalidateCanaryQueries();
    };

    apiClient.setCanaryVersionChangeHandler(handleVersionChange);

    // Cleanup
    return () => {
      apiClient.setCanaryVersionChangeHandler(() => {});
    };
  }, [invalidateCanaryQueries]);

  /**
   * 주기적으로 버전 상태 동기화 (폴백)
   */
  useEffect(() => {
    const syncVersion = () => {
      const currentVersion = apiClient.getCanaryVersion();
      const currentDeploymentId = apiClient.getCanaryDeploymentId();

      if (currentVersion !== canaryVersion) {
        setCanaryVersion(currentVersion);
      }
      if (currentDeploymentId !== deploymentId) {
        setDeploymentId(currentDeploymentId);
      }
    };

    // 10초마다 동기화
    const interval = setInterval(syncVersion, 10000);

    return () => clearInterval(interval);
  }, [canaryVersion, deploymentId]);

  return {
    canaryVersion,
    deploymentId,
    isCanaryActive: canaryVersion === 'v2',
    invalidateCanaryQueries,
  };
}

/**
 * Canary 버전을 React Query 키에 포함시키는 헬퍼
 *
 * @example
 * ```tsx
 * const { data } = useQuery({
 *   queryKey: withCanaryVersion(['ruleset', rulesetId]),
 *   queryFn: () => fetchRuleset(rulesetId),
 * });
 * ```
 */
export function withCanaryVersion<T extends unknown[]>(queryKey: T): [...T, string | null] {
  return [...queryKey, apiClient.getCanaryVersion()];
}

export default useCanaryVersion;
