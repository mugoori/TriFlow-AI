/**
 * ERP/MES 데이터 서비스
 * ERP/MES 데이터 조회, 업로드, Mock 생성 API 클라이언트
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

// ===========================================
// API Functions
// ===========================================

/**
 * ERP/MES 데이터 목록 조회
 */
export async function listErpMesData(
  params: ErpMesListParams = {},
  token: string
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

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to list ERP/MES data');
  }

  return response.json();
}

/**
 * ERP/MES 데이터 삭제
 */
export async function deleteErpMesData(
  dataId: string,
  token: string
): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/erp-mes/data/${dataId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to delete data');
  }

  return response.json();
}

/**
 * Mock 데이터 타입 조회
 */
export async function getMockTypes(): Promise<MockTypesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/erp-mes/mock/types`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to get mock types');
  }

  return response.json();
}

/**
 * Mock 데이터 생성
 */
export async function generateMockData(
  request: MockGenerateRequest,
  token: string
): Promise<MockGenerateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/erp-mes/mock/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      source_type: request.source_type,
      source_system: request.source_system || 'mock_system',
      record_type: request.record_type,
      count: request.count || 10,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to generate mock data');
  }

  return response.json();
}

/**
 * ERP/MES 통계 조회
 */
export async function getErpMesStats(token: string): Promise<ErpMesStats> {
  const response = await fetch(`${API_BASE_URL}/api/v1/erp-mes/stats`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to get stats');
  }

  return response.json();
}

/**
 * CSV/Excel 파일 Import (추후 백엔드 API 추가 예정)
 */
export async function importFile(
  file: File,
  sourceType: 'erp' | 'mes',
  recordType: string,
  token: string
): Promise<ImportResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_type', sourceType);
  formData.append('record_type', recordType);

  const response = await fetch(`${API_BASE_URL}/api/v1/erp-mes/import`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to import file');
  }

  return response.json();
}

// ===========================================
// Convenience Object Export
// ===========================================

export const erpMesService = {
  listData: listErpMesData,
  deleteData: deleteErpMesData,
  getMockTypes,
  generateMockData,
  getStats: getErpMesStats,
  importFile,
};

export default erpMesService;
