/**
 * Sensor Data Service
 * 센서 데이터 API 통신 서비스
 */

import { apiClient } from './api';

// Types
export interface SensorDataItem {
  sensor_id: string;
  recorded_at: string;
  line_code: string;
  sensor_type: string;
  value: number;
  unit: string | null;
}

export interface SensorDataResponse {
  data: SensorDataItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface SensorFilterOptions {
  lines: string[];
  sensor_types: string[];
}

export interface SensorSummaryItem {
  line_code: string;
  avg_temperature: number;
  avg_pressure: number;
  avg_humidity: number;
  total_readings: number;
  last_updated: string;
}

export interface SensorSummaryResponse {
  summary: SensorSummaryItem[];
}

export interface SensorDataParams {
  start_date?: string;
  end_date?: string;
  line_code?: string;
  sensor_type?: string;
  page?: number;
  page_size?: number;
}

export const sensorService = {
  /**
   * 센서 데이터 조회
   */
  async getData(params: SensorDataParams = {}): Promise<SensorDataResponse> {
    const searchParams = new URLSearchParams();

    if (params.start_date) searchParams.append('start_date', params.start_date);
    if (params.end_date) searchParams.append('end_date', params.end_date);
    if (params.line_code) searchParams.append('line_code', params.line_code);
    if (params.sensor_type) searchParams.append('sensor_type', params.sensor_type);
    if (params.page) searchParams.append('page', params.page.toString());
    if (params.page_size) searchParams.append('page_size', params.page_size.toString());

    const query = searchParams.toString();
    const endpoint = `/api/v1/sensors/data${query ? `?${query}` : ''}`;

    return await apiClient.get<SensorDataResponse>(endpoint);
  },

  /**
   * 필터 옵션 조회
   */
  async getFilterOptions(): Promise<SensorFilterOptions> {
    return await apiClient.get<SensorFilterOptions>('/api/v1/sensors/filters');
  },

  /**
   * 센서 요약 통계 조회
   */
  async getSummary(lineCode?: string): Promise<SensorSummaryResponse> {
    const endpoint = lineCode
      ? `/api/v1/sensors/summary?line_code=${lineCode}`
      : '/api/v1/sensors/summary';

    return await apiClient.get<SensorSummaryResponse>(endpoint);
  },
};
