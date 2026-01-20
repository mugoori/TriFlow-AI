/**
 * useModuleFilters Hook
 *
 * Hook for managing filter state in module pages.
 * Tracks active filters and provides utilities for updating/resetting.
 *
 * Example:
 *   const {
 *     filters,
 *     activeFilterCount,
 *     updateFilter,
 *     resetFilters
 *   } = useModuleFilters({ category: '', rating: null });
 */
import { useState, useEffect } from 'react';

interface UseModuleFiltersResult<T extends Record<string, any>> {
  filters: T;
  activeFilterCount: number;
  updateFilter: (key: keyof T, value: any) => void;
  setFilters: (filters: T) => void;
  resetFilters: () => void;
}

export function useModuleFilters<T extends Record<string, any>>(
  initialFilters: T
): UseModuleFiltersResult<T> {
  const [filters, setFilters] = useState<T>(initialFilters);
  const [activeFilterCount, setActiveFilterCount] = useState(0);

  // Count active filters (non-empty, non-null values)
  useEffect(() => {
    const count = Object.values(filters).filter(
      v => v !== '' && v !== null && v !== undefined
    ).length;
    setActiveFilterCount(count);
  }, [filters]);

  const updateFilter = (key: keyof T, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const resetFilters = () => {
    setFilters(initialFilters);
  };

  return {
    filters,
    activeFilterCount,
    updateFilter,
    setFilters,
    resetFilters
  };
}
