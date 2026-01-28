/**
 * Sensor Stream Service
 * WebSocket을 통한 실시간 센서 데이터 스트리밍
 */

export interface SensorDataPoint {
  sensor_id: string;
  line_code: string;
  sensor_type: string;
  value: number;
  unit: string;
  recorded_at: string;
}

export interface SensorStreamMessage {
  type: 'connected' | 'sensor_update' | 'subscribed';
  timestamp?: string;
  data?: SensorDataPoint[];
  message?: string;
  available_lines?: string[];
  available_sensor_types?: string[];
  filters?: {
    lines: string[] | null;
    sensor_types: string[] | null;
  };
}

export interface StreamFilters {
  lines?: string[];
  sensor_types?: string[];
}

type MessageCallback = (message: SensorStreamMessage) => void;
type ErrorCallback = (error: Event) => void;
type ConnectionCallback = () => void;

class SensorStreamService {
  private ws: WebSocket | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 3000;

  private messageCallbacks: Set<MessageCallback> = new Set();
  private errorCallbacks: Set<ErrorCallback> = new Set();
  private connectCallbacks: Set<ConnectionCallback> = new Set();
  private disconnectCallbacks: Set<ConnectionCallback> = new Set();

  private filters: StreamFilters = {};

  /**
   * WebSocket 연결
   */
  connect(backendUrl?: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    // Backend URL에서 WebSocket URL 생성
    const baseUrl = backendUrl || import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const wsUrl = baseUrl.replace(/^http/, 'ws') + '/api/v1/sensors/stream';

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('[SensorStream] Connected');
        this.reconnectAttempts = 0;
        this.connectCallbacks.forEach(cb => cb());

        // 이전 필터가 있으면 다시 적용
        if (this.filters.lines || this.filters.sensor_types) {
          this.subscribe(this.filters);
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as SensorStreamMessage;
          this.messageCallbacks.forEach(cb => cb(message));
        } catch (error) {
          console.error('[SensorStream] Failed to parse message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[SensorStream] WebSocket error:', error);
        this.errorCallbacks.forEach(cb => cb(error));
      };

      this.ws.onclose = () => {
        console.log('[SensorStream] Disconnected');
        this.disconnectCallbacks.forEach(cb => cb());
        this.attemptReconnect();
      };
    } catch (error) {
      console.error('[SensorStream] Failed to create WebSocket:', error);
    }
  }

  /**
   * 재연결 시도
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[SensorStream] Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    console.log(`[SensorStream] Reconnecting in ${this.reconnectDelay}ms... (attempt ${this.reconnectAttempts})`);

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, this.reconnectDelay);
  }

  /**
   * 연결 해제
   */
  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.reconnectAttempts = this.maxReconnectAttempts; // 재연결 방지
  }

  /**
   * 특정 라인/센서 타입 구독
   */
  subscribe(filters: StreamFilters): void {
    this.filters = filters;

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'subscribe',
        filters: {
          lines: filters.lines || null,
          sensor_types: filters.sensor_types || null,
        },
      }));
    }
  }

  /**
   * 연결 상태 확인
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * 이벤트 리스너 등록
   */
  onMessage(callback: MessageCallback): () => void {
    this.messageCallbacks.add(callback);
    return () => this.messageCallbacks.delete(callback);
  }

  onError(callback: ErrorCallback): () => void {
    this.errorCallbacks.add(callback);
    return () => this.errorCallbacks.delete(callback);
  }

  onConnect(callback: ConnectionCallback): () => void {
    this.connectCallbacks.add(callback);
    return () => this.connectCallbacks.delete(callback);
  }

  onDisconnect(callback: ConnectionCallback): () => void {
    this.disconnectCallbacks.add(callback);
    return () => this.disconnectCallbacks.delete(callback);
  }
}

// 싱글톤 인스턴스
export const sensorStreamService = new SensorStreamService();
