/**
 * ERP/MES 데이터 서비스
 * ERP/MES 데이터 조회, 업로드, Mock 생성 API 클라이언트
 */

import { apiClient } from './api';

// ===========================================
// Types
// ===========================================

export interface ErpMesData {
  data_id: string;
  tenant_id: string;
  source_type: 'erp' | 'mes';
  source_system: string;
  record_type: string;
  external_id?: string;
  raw_data: Record<string, unknown>;
  normalized_quantity?: number;
  normalized_status?: string;
  normalized_timestamp?: string;
  sync_status: string;
  synced_at: string;
  created_at: string;
}

export interface ErpMesListParams {
  source_type?: 'erp' | 'mes';
  source_system?: string;
  record_type?: string;
  limit?: number;
  offset?: number;
}

export interface MockGenerateRequest {
  source_type: 'erp' | 'mes';
  source_system?: string;
  record_type: string;
  count?: number;
}

export interface MockGenerateResponse {
  generated_count: number;
  source_type: string;
  source_system: string;
  record_type: string;
  sample_data: Record<string, unknown>[];
}

export interface MockTypesResponse {
  erp: {
    record_types: string[];
    description: string;
    examples: string[];
  };
  mes: {
    record_types: string[];
    description: string;
    examples: string[];
  };
}

export interface ImportResult {
  success: boolean;
  imported_count: number;
  failed_count: number;
  errors: string[];
}

export interface ErpMesStats {
  total_records: number;
  by_source_type: Record<string, number>;
  by_record_type: Record<string, number>;
  data_sources: number;
  field_mappings: number;
}

export interface DataSource {
  source_id: string;
  tenant_id: string;
  name: string;
  description?: string;
  source_type: 'erp' | 'mes';
  source_system: string;
  connection_type: 'rest_api' | 'soap' | 'db_direct' | 'file';
  connection_config: Record<string, unknown>;
  sync_enabled: boolean;
  sync_interval_minutes: number;
  last_sync_at?: string;
  last_sync_status?: string;
  is_active: boolean;
  created_at: string;
}

export interface DataSourceCreate {
  name: string;
  description?: string;
  source_type: 'erp' | 'mes';
  source_system: string;
  connection_type: 'rest_api' | 'soap' | 'db_direct' | 'file';
  connection_config: Record<string, unknown>;
  sync_enabled?: boolean;
  sync_interval_minutes?: number;
}

// ===========================================
// API Functions (using apiClient for automatic token handling)
// ===========================================

/**
 * ERP/MES 데이터 목록 조회
 */
export async function listErpMesData(
  params: ErpMesListParams = {}
): Promise<ErpMesData[]> {
  const searchParams = new URLSearchParams();

  if (params.source_type) {
    searchParams.append('source_type', params.source_type);
  }
  if (params.source_system) {
    searchParams.append('source_system', params.source_system);
  }
  if (params.record_type) {
    searchParams.append('record_type', params.record_type);
  }
  if (params.limit) {
    searchParams.append('limit', params.limit.toString());
  }
  if (params.offset) {
    searchParams.append('offset', params.offset.toString());
  }

  const query = searchParams.toString();
  const endpoint = `/api/v1/erp-mes/data${query ? `?${query}` : ''}`;

  return apiClient.get<ErpMesData[]>(endpoint);
}

/**
 * ERP/MES 데이터 삭제
 */
export async function deleteErpMesData(
  dataId: string
): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>(`/api/v1/erp-mes/data/${dataId}`);
}

/**
 * Mock 데이터 타입 조회
 */
export async function getMockTypes(): Promise<MockTypesResponse> {
  return apiClient.get<MockTypesResponse>('/api/v1/erp-mes/mock/types');
}

/**
 * Mock 데이터 생성
 */
export async function generateMockData(
  request: MockGenerateRequest
): Promise<MockGenerateResponse> {
  return apiClient.post<MockGenerateResponse>('/api/v1/erp-mes/mock/generate', {
    source_type: request.source_type,
    source_system: request.source_system || 'mock_system',
    record_type: request.record_type,
    count: request.count || 10,
  });
}

/**
 * ERP/MES 통계 조회
 */
export async function getErpMesStats(): Promise<ErpMesStats> {
  return apiClient.get<ErpMesStats>('/api/v1/erp-mes/stats');
}

/**
 * CSV/Excel 파일 Import
 */
export async function importFile(
  file: File,
  sourceType: 'erp' | 'mes',
  recordType: string
): Promise<ImportResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_type', sourceType);
  formData.append('record_type', recordType);

  return apiClient.postFormData<ImportResult>('/api/v1/erp-mes/import', formData);
}

// ===========================================
// Convenience Object Export
// ===========================================

/**
 * Data Source 생성
 */
export async function createDataSource(
  source: DataSourceCreate
): Promise<DataSource> {
  return apiClient.post<DataSource>('/api/v1/erp-mes/data-sources', source);
}

/**
 * Data Source 목록 조회
 */
export async function listDataSources(): Promise<DataSource[]> {
  return apiClient.get<DataSource[]>('/api/v1/erp-mes/data-sources');
}

/**
 * Data Source 연결 테스트
 */
export async function testConnection(
  sourceId: string
): Promise<{ success: boolean; message: string }> {
  return apiClient.post<{ success: boolean; message: string }>(
    `/api/v1/erp-mes/data-sources/${sourceId}/test`,
    {}
  );
}

/**
 * Data Source 삭제
 */
export async function deleteDataSource(sourceId: string): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>(`/api/v1/erp-mes/data-sources/${sourceId}`);
}

export const erpMesService = {
  listData: listErpMesData,
  deleteData: deleteErpMesData,
  getMockTypes,
  generateMockData,
  getStats: getErpMesStats,
  importFile,
  createDataSource,
  listDataSources,
  testConnection,
  deleteDataSource,
};

export default erpMesService;
