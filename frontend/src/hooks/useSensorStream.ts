/**
 * useSensorStream Hook
 * WebSocket 실시간 센서 데이터 스트림 React Hook
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  sensorStreamService,
  SensorDataPoint,
  SensorStreamMessage,
  StreamFilters,
} from '@/services/sensorStreamService';

export interface UseSensorStreamOptions {
  /** 자동 연결 여부 (기본: true) */
  autoConnect?: boolean;
  /** Backend URL (기본: 환경변수에서 읽음) */
  backendUrl?: string;
  /** 초기 필터 */
  filters?: StreamFilters;
  /** 히스토리 유지 개수 (기본: 100) */
  historySize?: number;
}

export interface UseSensorStreamReturn {
  /** 연결 상태 */
  isConnected: boolean;
  /** 최신 센서 데이터 */
  latestData: SensorDataPoint[];
  /** 센서별 히스토리 데이터 */
  history: Map<string, SensorDataPoint[]>;
  /** 사용 가능한 라인 목록 */
  availableLines: string[];
  /** 사용 가능한 센서 타입 목록 */
  availableSensorTypes: string[];
  /** 에러 상태 */
  error: string | null;
  /** 수동 연결 */
  connect: () => void;
  /** 연결 해제 */
  disconnect: () => void;
  /** 필터 업데이트 */
  subscribe: (filters: StreamFilters) => void;
}

export function useSensorStream(options: UseSensorStreamOptions = {}): UseSensorStreamReturn {
  const {
    autoConnect = true,
    backendUrl,
    filters: initialFilters,
    historySize = 100,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [latestData, setLatestData] = useState<SensorDataPoint[]>([]);
  const [availableLines, setAvailableLines] = useState<string[]>([]);
  const [availableSensorTypes, setAvailableSensorTypes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // 히스토리는 ref로 관리 (리렌더링 최소화)
  const historyRef = useRef<Map<string, SensorDataPoint[]>>(new Map());
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_historyVersion, setHistoryVersion] = useState(0);

  // 메시지 핸들러
  const handleMessage = useCallback((message: SensorStreamMessage) => {
    switch (message.type) {
      case 'connected':
        setAvailableLines(message.available_lines || []);
        setAvailableSensorTypes(message.available_sensor_types || []);
        setError(null);
        break;

      case 'sensor_update':
        if (message.data) {
          setLatestData(message.data);

          // 히스토리 업데이트
          message.data.forEach(point => {
            const key = point.sensor_id;
            const existing = historyRef.current.get(key) || [];
            const updated = [...existing, point].slice(-historySize);
            historyRef.current.set(key, updated);
          });
          setHistoryVersion(v => v + 1);
        }
        break;

      case 'subscribed':
        console.log('[useSensorStream] Subscribed with filters:', message.filters);
        break;
    }
  }, [historySize]);

  // 연결 함수
  const connect = useCallback(() => {
    sensorStreamService.connect(backendUrl);
    if (initialFilters) {
      sensorStreamService.subscribe(initialFilters);
    }
  }, [backendUrl, initialFilters]);

  // 연결 해제 함수
  const disconnect = useCallback(() => {
    sensorStreamService.disconnect();
  }, []);

  // 필터 업데이트
  const subscribe = useCallback((filters: StreamFilters) => {
    sensorStreamService.subscribe(filters);
  }, []);

  // 이벤트 리스너 등록
  useEffect(() => {
    const unsubMessage = sensorStreamService.onMessage(handleMessage);
    const unsubConnect = sensorStreamService.onConnect(() => setIsConnected(true));
    const unsubDisconnect = sensorStreamService.onDisconnect(() => setIsConnected(false));
    const unsubError = sensorStreamService.onError(() => setError('WebSocket connection error'));

    // 자동 연결
    if (autoConnect) {
      connect();
    }

    return () => {
      unsubMessage();
      unsubConnect();
      unsubDisconnect();
      unsubError();
    };
  }, [autoConnect, connect, handleMessage]);

  return {
    isConnected,
    latestData,
    history: historyRef.current,
    availableLines,
    availableSensorTypes,
    error,
    connect,
    disconnect,
    subscribe,
  };
}
