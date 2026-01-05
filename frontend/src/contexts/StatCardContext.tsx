/**
 * StatCardContext
 * 대시보드 StatCard 상태를 전역으로 관리
 * - StatCard 설정 및 값 CRUD
 * - 사용 가능한 KPI, 테이블, MCP 도구 목록 캐싱
 * - 실시간 값 새로고침
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  ReactNode,
  useMemo,
} from 'react';
import { statCardService } from '../services/statCardService';
import type {
  StatCardWithValue,
  StatCardConfigCreate,
  StatCardConfigUpdate,
  KpiInfo,
  TableInfo,
  McpToolInfo,
  StatCardPeriod,
} from '../types/statcard';

interface StatCardContextType {
  // 상태
  cards: StatCardWithValue[];
  loading: boolean;
  error: string | null;

  // 기간 관련 상태
  selectedPeriod: StatCardPeriod;
  latestDataDate: string | null;
  setSelectedPeriod: (period: StatCardPeriod) => void;

  // KPI, 테이블, MCP 도구 목록 (설정 모달용)
  availableKpis: KpiInfo[];
  kpiCategories: string[];
  availableTables: TableInfo[];
  availableMcpTools: McpToolInfo[];
  optionsLoading: boolean;

  // 액션
  fetchCards: () => Promise<void>;
  createCard: (config: StatCardConfigCreate) => Promise<void>;
  updateCard: (configId: string, update: StatCardConfigUpdate) => Promise<void>;
  deleteCard: (configId: string) => Promise<void>;
  reorderCards: (cardIds: string[]) => Promise<void>;
  refreshValues: () => Promise<void>;
  fetchOptions: () => Promise<void>;
}

const StatCardContext = createContext<StatCardContextType | null>(null);

// 자동 새로고침 간격 (밀리초)
const AUTO_REFRESH_INTERVAL = 60000; // 1분

export function StatCardProvider({ children }: { children: ReactNode }) {
  // StatCard 상태
  const [cards, setCards] = useState<StatCardWithValue[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 기간 관련 상태
  const [selectedPeriod, setSelectedPeriod] = useState<StatCardPeriod>('auto');
  const [latestDataDate, setLatestDataDate] = useState<string | null>(null);

  // 설정 옵션 상태
  const [availableKpis, setAvailableKpis] = useState<KpiInfo[]>([]);
  const [kpiCategories, setKpiCategories] = useState<string[]>([]);
  const [availableTables, setAvailableTables] = useState<TableInfo[]>([]);
  const [availableMcpTools, setAvailableMcpTools] = useState<McpToolInfo[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);

  // StatCard 목록 조회
  const fetchCards = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await statCardService.getStatCards(selectedPeriod);
      setCards(response.cards);
      setLatestDataDate(response.latest_data_date || null);
    } catch (err) {
      const message = err instanceof Error ? err.message : '카드 조회 실패';
      setError(message);
      console.error('Failed to fetch stat cards:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedPeriod]);

  // StatCard 생성
  const createCard = useCallback(async (config: StatCardConfigCreate) => {
    setError(null);
    try {
      await statCardService.createStatCard(config);
      // 생성 후 목록 새로고침
      await fetchCards();
    } catch (err) {
      const message = err instanceof Error ? err.message : '카드 생성 실패';
      setError(message);
      throw err;
    }
  }, [fetchCards]);

  // StatCard 수정
  const updateCard = useCallback(async (configId: string, update: StatCardConfigUpdate) => {
    setError(null);
    try {
      await statCardService.updateStatCard(configId, update);
      // 수정 후 목록 새로고침
      await fetchCards();
    } catch (err) {
      const message = err instanceof Error ? err.message : '카드 수정 실패';
      setError(message);
      throw err;
    }
  }, [fetchCards]);

  // StatCard 삭제
  const deleteCard = useCallback(async (configId: string) => {
    setError(null);
    try {
      await statCardService.deleteStatCard(configId);
      // 삭제 후 로컬 상태 업데이트 (빠른 UI 반영)
      setCards((prev) => prev.filter((card) => card.config.config_id !== configId));
    } catch (err) {
      const message = err instanceof Error ? err.message : '카드 삭제 실패';
      setError(message);
      throw err;
    }
  }, []);

  // StatCard 순서 변경
  const reorderCards = useCallback(async (cardIds: string[]) => {
    setError(null);
    try {
      // 낙관적 UI 업데이트
      setCards((prev) => {
        const cardMap = new Map(prev.map((card) => [card.config.config_id, card]));
        return cardIds
          .map((id) => cardMap.get(id))
          .filter((card): card is StatCardWithValue => card !== undefined);
      });

      await statCardService.reorderStatCards(cardIds);
    } catch (err) {
      const message = err instanceof Error ? err.message : '순서 변경 실패';
      setError(message);
      // 실패 시 다시 조회
      await fetchCards();
      throw err;
    }
  }, [fetchCards]);

  // 값만 새로고침
  const refreshValues = useCallback(async () => {
    try {
      const response = await statCardService.getStatCards(selectedPeriod);
      setCards(response.cards);
      setLatestDataDate(response.latest_data_date || null);
    } catch (err) {
      console.error('Failed to refresh stat card values:', err);
    }
  }, [selectedPeriod]);

  // 설정 옵션 조회 (KPI, 테이블, MCP 도구)
  const fetchOptions = useCallback(async () => {
    setOptionsLoading(true);
    try {
      const [kpisResponse, tablesResponse, mcpToolsResponse] = await Promise.all([
        statCardService.getAvailableKpis(),
        statCardService.getAvailableTables(),
        statCardService.getAvailableMcpTools(),
      ]);

      setAvailableKpis(kpisResponse.kpis);
      setKpiCategories(kpisResponse.categories);
      setAvailableTables(tablesResponse.tables);
      setAvailableMcpTools(mcpToolsResponse.tools);
    } catch (err) {
      console.error('Failed to fetch stat card options:', err);
    } finally {
      setOptionsLoading(false);
    }
  }, []);

  // 초기 로드
  useEffect(() => {
    fetchCards();
  }, [fetchCards]);

  // 자동 새로고침
  useEffect(() => {
    const interval = setInterval(() => {
      refreshValues();
    }, AUTO_REFRESH_INTERVAL);

    return () => clearInterval(interval);
  }, [refreshValues]);

  const value = useMemo(
    () => ({
      cards,
      loading,
      error,
      selectedPeriod,
      latestDataDate,
      setSelectedPeriod,
      availableKpis,
      kpiCategories,
      availableTables,
      availableMcpTools,
      optionsLoading,
      fetchCards,
      createCard,
      updateCard,
      deleteCard,
      reorderCards,
      refreshValues,
      fetchOptions,
    }),
    [
      cards,
      loading,
      error,
      selectedPeriod,
      latestDataDate,
      availableKpis,
      kpiCategories,
      availableTables,
      availableMcpTools,
      optionsLoading,
      fetchCards,
      createCard,
      updateCard,
      deleteCard,
      reorderCards,
      refreshValues,
      fetchOptions,
    ]
  );

  return (
    <StatCardContext.Provider value={value}>
      {children}
    </StatCardContext.Provider>
  );
}

export function useStatCards() {
  const context = useContext(StatCardContext);
  if (!context) {
    throw new Error('useStatCards must be used within a StatCardProvider');
  }
  return context;
}
