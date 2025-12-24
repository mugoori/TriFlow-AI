/**
 * StatCard Types
 * 대시보드 StatCard 설정 및 데이터 타입 정의
 *
 * 데이터 소스 유형:
 * - kpi: bi.dim_kpi에서 정의된 KPI
 * - db_query: 사용자 정의 테이블/컬럼 쿼리
 * - mcp_tool: MCP 도구를 통한 외부 시스템 연동
 */

// =====================================================
// 공통 타입
// =====================================================

export type SourceType = 'kpi' | 'db_query' | 'mcp_tool';
export type AggregationType = 'sum' | 'avg' | 'min' | 'max' | 'count' | 'last';
export type StatusType = 'green' | 'yellow' | 'red' | 'gray';
export type TrendType = 'up' | 'down' | 'stable';

// =====================================================
// StatCard 설정 스키마
// =====================================================

export interface StatCardConfigBase {
  display_order: number;
  is_visible: boolean;

  source_type: SourceType;

  // KPI 소스 (source_type = 'kpi')
  kpi_code?: string;

  // DB Query 소스 (source_type = 'db_query')
  table_name?: string;
  column_name?: string;
  aggregation?: AggregationType;
  filter_condition?: Record<string, any>;

  // MCP Tool 소스 (source_type = 'mcp_tool')
  mcp_server_id?: string;
  mcp_tool_name?: string;
  mcp_params?: Record<string, any>;
  mcp_result_key?: string;

  // 표시 설정 (커스텀 오버라이드)
  custom_title?: string;
  custom_icon?: string;
  custom_unit?: string;

  // 임계값 (DB Query, MCP용 - KPI는 dim_kpi에서 가져옴)
  green_threshold?: number;
  yellow_threshold?: number;
  red_threshold?: number;
  higher_is_better: boolean;

  // 캐시 설정
  cache_ttl_seconds: number;
}

export interface StatCardConfigCreate extends StatCardConfigBase {}

export interface StatCardConfigUpdate {
  display_order?: number;
  is_visible?: boolean;

  source_type?: SourceType;
  kpi_code?: string;

  table_name?: string;
  column_name?: string;
  aggregation?: AggregationType;
  filter_condition?: Record<string, any>;

  mcp_server_id?: string;
  mcp_tool_name?: string;
  mcp_params?: Record<string, any>;
  mcp_result_key?: string;

  custom_title?: string;
  custom_icon?: string;
  custom_unit?: string;

  green_threshold?: number;
  yellow_threshold?: number;
  red_threshold?: number;
  higher_is_better?: boolean;

  cache_ttl_seconds?: number;
}

export interface StatCardConfig extends StatCardConfigBase {
  config_id: string;
  tenant_id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

// =====================================================
// StatCard 값 스키마
// =====================================================

export interface StatCardValue {
  config_id: string;
  value?: number;
  formatted_value?: string;
  previous_value?: number;
  change_percent?: number;
  trend?: TrendType;
  status: StatusType;

  // 메타데이터
  title: string;
  icon: string;
  unit?: string;

  // 집계 기간 정보
  period_start?: string;
  period_end?: string;
  period_label?: string;
  comparison_label?: string;

  // 출처 정보
  source_type: SourceType;
  fetched_at: string;
  is_cached: boolean;
}

export interface StatCardWithValue {
  config: StatCardConfig;
  value: StatCardValue;
}

// =====================================================
// 목록 조회 응답
// =====================================================

export interface StatCardListResponse {
  cards: StatCardWithValue[];
  total: number;
}

export interface StatCardReorderRequest {
  card_ids: string[];
}

// =====================================================
// KPI 목록 조회
// =====================================================

export interface KpiInfo {
  kpi_code: string;
  name: string;
  name_en?: string;
  category: string;
  unit?: string;
  description?: string;
  higher_is_better: boolean;
  default_target?: number;
  green_threshold?: number;
  yellow_threshold?: number;
  red_threshold?: number;
}

export interface KpiListResponse {
  kpis: KpiInfo[];
  categories: string[];
}

// =====================================================
// 사용 가능한 테이블/컬럼 조회
// =====================================================

export interface ColumnInfo {
  column_name: string;
  data_type: string;
  description?: string;
  allowed_aggregations: AggregationType[];
}

export interface TableInfo {
  schema_name: string;
  table_name: string;
  columns: ColumnInfo[];
}

export interface AvailableTablesResponse {
  tables: TableInfo[];
}

// =====================================================
// MCP 도구 목록 조회
// =====================================================

export interface McpToolInfo {
  server_id: string;
  server_name: string;
  tool_name: string;
  description?: string;
  input_schema?: Record<string, any>;
}

export interface McpToolListResponse {
  tools: McpToolInfo[];
}

// =====================================================
// UI 헬퍼 타입
// =====================================================

/** 소스 유형별 라벨 및 아이콘 */
export const SOURCE_TYPE_INFO: Record<SourceType, { label: string; icon: string; description: string }> = {
  kpi: {
    label: 'KPI',
    icon: 'BarChart3',
    description: '표준 KPI 지표 (불량률, OEE 등)',
  },
  db_query: {
    label: 'DB 쿼리',
    icon: 'Database',
    description: '테이블/컬럼 기반 커스텀 쿼리',
  },
  mcp_tool: {
    label: 'MCP 도구',
    icon: 'Plug',
    description: '외부 시스템 연동 (MES, ERP 등)',
  },
};

/** 집계 함수별 라벨 */
export const AGGREGATION_LABELS: Record<AggregationType, string> = {
  sum: '합계',
  avg: '평균',
  min: '최소',
  max: '최대',
  count: '개수',
  last: '최신값',
};

/** 상태별 색상 */
export const STATUS_COLORS: Record<StatusType, { bg: string; text: string; border: string }> = {
  green: {
    bg: 'bg-green-500/10',
    text: 'text-green-500',
    border: 'border-green-500/20',
  },
  yellow: {
    bg: 'bg-yellow-500/10',
    text: 'text-yellow-500',
    border: 'border-yellow-500/20',
  },
  red: {
    bg: 'bg-red-500/10',
    text: 'text-red-500',
    border: 'border-red-500/20',
  },
  gray: {
    bg: 'bg-gray-500/10',
    text: 'text-gray-500',
    border: 'border-gray-500/20',
  },
};

/** 추세별 아이콘 */
export const TREND_ICONS: Record<TrendType, { icon: string; color: string }> = {
  up: { icon: 'TrendingUp', color: 'text-green-500' },
  down: { icon: 'TrendingDown', color: 'text-red-500' },
  stable: { icon: 'Minus', color: 'text-gray-500' },
};
