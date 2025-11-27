/**
 * DashboardContext
 * 대시보드에 고정된 차트들을 관리하는 Context
 */

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import type { ChartConfig } from '../types/chart';

// 저장된 차트 타입
export interface SavedChart {
  id: string;
  config: ChartConfig;
  title: string;
  savedAt: Date;
}

interface DashboardContextType {
  // 저장된 차트 목록
  savedCharts: SavedChart[];
  // 차트 추가
  addChart: (config: ChartConfig, title?: string) => void;
  // 차트 삭제
  removeChart: (id: string) => void;
  // 차트 존재 여부 확인
  hasChart: (config: ChartConfig) => boolean;
}

const DashboardContext = createContext<DashboardContextType | null>(null);

// 차트 설정을 비교하여 동일한 차트인지 확인
function isSameChart(a: ChartConfig, b: ChartConfig): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

// 고유 ID 생성
function generateId(): string {
  return `chart_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [savedCharts, setSavedCharts] = useState<SavedChart[]>([]);

  // 차트 추가
  const addChart = useCallback((config: ChartConfig, title?: string) => {
    setSavedCharts(prev => {
      // 이미 동일한 차트가 있는지 확인
      if (prev.some(chart => isSameChart(chart.config, config))) {
        return prev;
      }

      const newChart: SavedChart = {
        id: generateId(),
        config,
        title: title || config.title || '차트',
        savedAt: new Date(),
      };

      return [...prev, newChart];
    });
  }, []);

  // 차트 삭제
  const removeChart = useCallback((id: string) => {
    setSavedCharts(prev => prev.filter(chart => chart.id !== id));
  }, []);

  // 차트 존재 여부 확인
  const hasChart = useCallback((config: ChartConfig) => {
    return savedCharts.some(chart => isSameChart(chart.config, config));
  }, [savedCharts]);

  return (
    <DashboardContext.Provider value={{ savedCharts, addChart, removeChart, hasChart }}>
      {children}
    </DashboardContext.Provider>
  );
}

// Hook
export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
}
