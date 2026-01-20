/**
 * useModuleData Hook
 *
 * Generic hook for loading data from API endpoints with automatic
 * loading, error handling, and retry logic.
 *
 * Example:
 *   const { data, loading, error, reload } = useModuleData<Product[]>(
 *     '/api/v1/products',
 *     { params: { category: 'electronics' }, autoLoad: true }
 *   );
 */
import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '../../services/api';

interface UseModuleDataOptions {
  params?: Record<string, any>;
  dependencies?: any[];
  autoLoad?: boolean;
}

interface UseModuleDataResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export function useModuleData<T = any>(
  endpoint: string,
  options: UseModuleDataOptions = {}
): UseModuleDataResult<T> {
  const {
    params = {},
    dependencies = [],
    autoLoad = true
  } = options;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiClient.get<T>(endpoint, params);
      setData(result);
    } catch (err) {
      const errorMessage = err instanceof Error
        ? err.message
        : 'Failed to load data';
      setError(errorMessage);
      console.error(`[useModuleData] Error loading ${endpoint}:`, err);
    } finally {
      setLoading(false);
    }
  }, [endpoint, JSON.stringify(params)]);

  useEffect(() => {
    if (autoLoad) {
      loadData();
    }
  }, [loadData, ...dependencies]);

  return {
    data,
    loading,
    error,
    reload: loadData
  };
}
