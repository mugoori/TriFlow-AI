/**
 * BI Types - AWS QuickSight GenBI 동일 기능 타입 정의
 *
 * 3대 핵심 기능:
 * 1. AI Dashboard Authoring (차트 생성 + Refinement Loop)
 * 2. Executive Summary (Fact/Reasoning/Action 인사이트)
 * 3. Data Stories (내러티브 보고서)
 *
 * v2: 고품질 인사이트 지원
 * - TableData: 표 형태 데이터
 * - AutoAnalysis: 자동 연관 분석
 * - InsightChart: threshold_lines, annotations 지원
 * - ComparisonData: 전일/전주 비교
 */

import { ChartConfig } from './chart';

// =====================================================
// v2: 고품질 인사이트 타입
// =====================================================

/**
 * 인사이트 상태
 */
export type InsightStatus = 'normal' | 'warning' | 'critical';

/**
 * 표 형태 데이터
 */
export interface TableData {
  headers: string[];
  rows: (string | number | boolean)[][];
  highlight_rules?: Record<string, string>; // 예: { "달성률 < 80": "critical" }
}

/**
 * 차트 기준선 (Threshold Line)
 */
export interface ThresholdLine {
  value: number;
  label: string;
  color?: string;
}

/**
 * 차트 주석
 */
export interface ChartAnnotation {
  x: string | number;
  y?: number;
  text: string;
}

/**
 * 인사이트 차트 (v2)
 */
export interface InsightChart {
  chart_type: 'bar' | 'line' | 'pie' | 'area' | 'scatter';
  title: string;
  data: Record<string, unknown>[];
  x_key?: string;
  y_key?: string;
  threshold_lines?: ThresholdLine[];
  annotations?: ChartAnnotation[];
}

/**
 * 분석 트리거
 */
export interface AnalysisTrigger {
  type: string;
  line_code: string;
  value: number;
  threshold: number;
  message?: string;
}

/**
 * 비가동 원인
 */
export interface DowntimeCause {
  reason: string;
  duration_min: number;
  percentage: number;
  equipment_code?: string;
}

/**
 * 불량 원인
 */
export interface DefectCause {
  defect_type: string;
  qty: number;
  percentage: number;
  root_causes?: string[];
}

/**
 * 자동 연관 분석 결과
 */
export interface AutoAnalysis {
  has_issues: boolean;
  triggers?: AnalysisTrigger[];
  downtime_causes?: DowntimeCause[];
  defect_causes?: DefectCause[];
  summary?: string;
}

/**
 * 비교 데이터
 */
export interface ComparisonData {
  vs_yesterday?: Record<string, number | string>;
  vs_last_week?: Record<string, number | string>;
}

// =====================================================
// 1. Executive Summary (AI Insights)
// =====================================================

/**
 * 인사이트 사실 (Fact) - v2 확장
 * 데이터에서 확인되는 객관적 사실
 */
export interface InsightFact {
  metric_name: string;
  current_value: number;
  previous_value?: number;
  change_percent?: number;
  trend: 'up' | 'down' | 'stable';
  period: string;
  unit?: string;
  status?: InsightStatus; // v2: 상태 추가
}

/**
 * 인사이트 분석 (Reasoning)
 * 왜 이런 결과가 나왔는지 원인 분석
 */
export interface InsightReasoning {
  analysis: string;
  contributing_factors: string[];
  confidence: number; // 0.0 ~ 1.0
  data_quality_notes?: string;
}

/**
 * 인사이트 권장 조치 (Action)
 * 구체적인 조치 권장 사항
 */
export interface InsightAction {
  priority: 'high' | 'medium' | 'low';
  action: string;
  expected_impact?: string;
  responsible_team?: string;
  deadline_suggestion?: string;
}

/**
 * AI 인사이트 (Executive Summary) - v2 확장
 */
export interface AIInsight {
  insight_id: string;
  tenant_id: string;
  source_type: 'chart' | 'dashboard' | 'dataset' | 'chat';
  source_id?: string;
  title: string;
  summary: string;

  // v2: 전체 상태
  status?: InsightStatus;

  // v2: 표 형태 데이터
  table_data?: TableData;

  facts: InsightFact[];

  // v2: 자동 연관 분석
  auto_analysis?: AutoAnalysis;

  reasoning: InsightReasoning;
  actions: InsightAction[];

  // v2: 전일/전주 비교
  comparison?: ComparisonData;

  // v2: 차트 설정 (threshold_lines 포함)
  charts?: InsightChart[];

  model_used: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  feedback_score?: number; // -1 ~ 1
  feedback_comment?: string;
  generated_at: string;
  created_by?: string;
}

/**
 * 인사이트 생성 요청
 */
export interface InsightRequest {
  source_type: 'chart' | 'dashboard' | 'dataset' | 'chat';
  source_id?: string;
  source_data?: Record<string, unknown>[];
  chart_config?: ChartConfig;
  focus_metrics?: string[];
  time_range?: string;
}

/**
 * 인사이트 응답
 */
export interface InsightResponse {
  insight: AIInsight;
  processing_time_ms: number;
}

/**
 * 인사이트 목록 응답
 */
export interface InsightListResponse {
  insights: AIInsight[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * 인사이트 피드백 요청
 */
export interface InsightFeedbackRequest {
  score: number; // -1 ~ 1
  comment?: string;
}

// =====================================================
// 2. Data Stories (내러티브 보고서)
// =====================================================

/**
 * 스토리 섹션 타입
 */
export type StorySectionType = 'introduction' | 'analysis' | 'finding' | 'conclusion';

/**
 * 스토리 섹션 내 차트
 */
export interface StorySectionChart {
  chart_config: ChartConfig;
  caption?: string;
  order: number;
}

/**
 * 스토리 섹션
 */
export interface StorySection {
  section_id: string;
  section_type: StorySectionType;
  order: number;
  title: string;
  narrative: string; // Markdown 형식
  charts: StorySectionChart[];
  ai_generated: boolean;
  created_at: string;
  updated_at?: string;
}

/**
 * 데이터 스토리 (내러티브 보고서)
 */
export interface DataStory {
  story_id: string;
  tenant_id: string;
  title: string;
  description?: string;
  sections: StorySection[];
  is_public: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  published_at?: string;
}

/**
 * 스토리 생성 요청
 */
export interface StoryCreateRequest {
  title: string;
  description?: string;
  auto_generate?: boolean;
  source_dashboard_id?: string;
  source_chart_ids?: string[];
  focus_topic?: string;
  time_range?: string;
}

/**
 * 스토리 수정 요청
 */
export interface StoryUpdateRequest {
  title?: string;
  description?: string;
  is_public?: boolean;
}

/**
 * 섹션 생성 요청
 */
export interface StorySectionCreateRequest {
  section_type: StorySectionType;
  title: string;
  narrative: string;
  charts?: StorySectionChart[];
  order?: number;
}

/**
 * 섹션 수정 요청
 */
export interface StorySectionUpdateRequest {
  title?: string;
  narrative?: string;
  charts?: StorySectionChart[];
  order?: number;
}

/**
 * 스토리 목록 응답
 */
export interface StoryListResponse {
  stories: DataStory[];
  total: number;
  page: number;
  page_size: number;
}

// =====================================================
// 3. Chart Refinement (Refinement Loop)
// =====================================================

/**
 * 차트 수정 요청
 */
export interface ChartRefineRequest {
  original_chart_config: ChartConfig;
  refinement_instruction: string;
  preserve_data?: boolean;
}

/**
 * 차트 수정 응답
 */
export interface ChartRefineResponse {
  refined_chart_config: ChartConfig;
  changes_made: string[];
  processing_time_ms: number;
}

// =====================================================
// 4. Saved Charts (대시보드 고정 차트)
// =====================================================

/**
 * 저장된 차트
 */
export interface SavedChart {
  chart_id: string;
  tenant_id: string;
  title: string;
  chart_config: ChartConfig;
  source_query?: string;
  source_insight_id?: string;
  dashboard_order: number;
  grid_position?: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
  created_by: string;
}

// =====================================================
// 5. UI Helper Types
// =====================================================

/**
 * 인사이트 뷰 모드
 */
export type InsightViewMode = 'compact' | 'expanded';

/**
 * 스토리 뷰 모드
 */
export type StoryViewMode = 'slide' | 'scroll';

/**
 * 우선순위 색상 매핑
 */
export const PRIORITY_COLORS: Record<InsightAction['priority'], string> = {
  high: '#ef4444',   // red-500
  medium: '#f59e0b', // amber-500
  low: '#22c55e',    // green-500
};

/**
 * 트렌드 아이콘 타입
 */
export const TREND_ICONS: Record<InsightFact['trend'], string> = {
  up: 'TrendingUp',
  down: 'TrendingDown',
  stable: 'Minus',
};

/**
 * 섹션 타입 라벨
 */
export const SECTION_TYPE_LABELS: Record<StorySectionType, string> = {
  introduction: '도입',
  analysis: '분석',
  finding: '발견',
  conclusion: '결론',
};

/**
 * 섹션 타입 색상
 */
export const SECTION_TYPE_COLORS: Record<StorySectionType, string> = {
  introduction: '#3b82f6', // blue-500
  analysis: '#8b5cf6',     // violet-500
  finding: '#f59e0b',      // amber-500
  conclusion: '#22c55e',   // green-500
};

// =====================================================
// 6. Chat (대화형 GenBI)
// =====================================================

/**
 * 채팅 컨텍스트 타입
 */
export type ChatContextType = 'general' | 'dashboard' | 'chart' | 'dataset';

/**
 * 응답 타입
 */
export type ChatResponseType = 'text' | 'insight' | 'chart' | 'story' | 'error' | 'card_action';

/**
 * 채팅 세션
 */
export interface ChatSession {
  session_id: string;
  tenant_id: string;
  user_id: string;
  title: string;
  context_type: ChatContextType;
  context_id?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_message_at?: string;
}

/**
 * 채팅 메시지
 */
export interface ChatMessage {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  response_type?: ChatResponseType;
  response_data?: {
    insight?: AIInsight;
    chart_config?: ChartConfig;
    story?: DataStory;
    error?: string;
    pinned?: boolean; // UI 상태용
  };
  linked_insight_id?: string;
  linked_chart_id?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  created_at: string;
}

/**
 * 채팅 요청
 */
export interface ChatRequest {
  message: string;
  session_id?: string;
  context_type?: ChatContextType;
  context_id?: string;
}

/**
 * 채팅 응답
 */
export interface ChatResponse {
  success: boolean;
  session_id: string;
  message_id: string;
  content: string;
  response_type: ChatResponseType;
  response_data?: Record<string, unknown>;
  linked_insight_id?: string | null;
  linked_chart_id?: string | null;
  insight?: AIInsight;
  chart_config?: ChartConfig;
}

/**
 * 채팅 세션 목록 응답
 */
export interface ChatSessionListResponse {
  sessions: ChatSession[];
  total: number;
}

/**
 * 채팅 메시지 목록 응답
 */
export interface ChatMessageListResponse {
  messages: ChatMessage[];
  total: number;
}

// =====================================================
// 7. Pinned Insights (고정된 인사이트)
// =====================================================

/**
 * 인사이트 표시 모드
 */
export type InsightDisplayMode = 'card' | 'compact' | 'expanded';

/**
 * 고정된 인사이트
 */
export interface PinnedInsight {
  pin_id: string;
  tenant_id: string;
  insight_id: string;
  insight: AIInsight;
  dashboard_order: number;
  grid_position?: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  display_mode: InsightDisplayMode;
  show_facts: boolean;
  show_reasoning: boolean;
  show_actions: boolean;
  pinned_at: string;
  pinned_by: string;
}

/**
 * 인사이트 Pin 요청
 */
export interface PinInsightRequest {
  display_mode?: InsightDisplayMode;
  grid_position?: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
}

/**
 * 인사이트 Pin 응답
 */
export interface PinInsightResponse {
  pin_id: string;
  insight_id: string;
  pinned_at: string;
}

/**
 * 고정된 인사이트 목록 응답
 */
export interface PinnedInsightsResponse {
  pinned_insights: PinnedInsight[];
  total: number;
}

// =====================================================
// 8. Dashboard (대시보드 관리)
// =====================================================

/**
 * 대시보드 레이아웃 컴포넌트
 */
export interface DashboardLayoutComponent {
  id: string;
  type: 'chart' | 'table' | 'kpi_card' | 'gauge' | 'insight';
  position: { x: number; y: number; w: number; h: number };
  config: Record<string, unknown>;
}

/**
 * 대시보드 레이아웃
 */
export interface DashboardLayout {
  components: DashboardLayoutComponent[];
}

/**
 * 대시보드
 */
export interface Dashboard {
  id: string;
  name: string;
  description?: string;
  layout: DashboardLayout;
  is_public: boolean;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

/**
 * 대시보드 생성 요청
 */
export interface DashboardCreateRequest {
  name: string;
  description?: string;
  layout: DashboardLayout;
  is_public?: boolean;
}

/**
 * 대시보드 수정 요청
 */
export interface DashboardUpdateRequest {
  name?: string;
  description?: string;
  layout?: DashboardLayout;
  is_public?: boolean;
}

/**
 * 대시보드 목록 응답
 */
export interface DashboardListResponse {
  dashboards: Dashboard[];
  total: number;
  page: number;
  page_size: number;
}

// =====================================================
// 9. Analytics (분석 API)
// =====================================================

/**
 * 생산 실적 요약
 */
export interface ProductionSummary {
  date: string;
  line_code: string;
  line_name?: string;
  product_code: string;
  product_name?: string;
  shift: string;
  total_qty: number;
  good_qty: number;
  defect_qty: number;
  defect_rate: number;
  yield_rate: number;
  runtime_minutes: number;
  downtime_minutes: number;
  availability: number;
}

/**
 * 생산 실적 응답
 */
export interface ProductionResponse {
  data: ProductionSummary[];
  total: number;
  summary: {
    total_production: number;
    total_defects: number;
    avg_yield_rate: number;
    avg_availability: number;
  };
}

/**
 * 불량 추이 아이템
 */
export interface DefectTrendItem {
  date: string;
  line_code: string;
  product_code?: string;
  total_qty: number;
  defect_qty: number;
  defect_rate: number;
  top_defect_types?: Array<{ type: string; qty: number; percentage: number }>;
}

/**
 * 불량 추이 응답
 */
export interface DefectTrendResponse {
  data: DefectTrendItem[];
  total: number;
  avg_defect_rate: number;
}

/**
 * OEE 아이템
 */
export interface OEEItem {
  date: string;
  line_code: string;
  line_name?: string;
  shift: string;
  availability: number;
  performance: number;
  quality: number;
  oee: number;
  runtime_minutes: number;
  downtime_minutes: number;
}

/**
 * OEE 응답
 */
export interface OEEResponse {
  data: OEEItem[];
  total: number;
  avg_oee: number;
  avg_availability: number;
  avg_performance: number;
  avg_quality: number;
}

/**
 * 재고 아이템
 */
export interface InventoryItem {
  date: string;
  product_code: string;
  product_name?: string;
  location: string;
  stock_qty: number;
  safety_stock_qty: number;
  available_qty: number;
  coverage_days?: number;
  stock_status: 'normal' | 'low' | 'critical' | 'excess';
}

/**
 * 재고 응답
 */
export interface InventoryResponse {
  data: InventoryItem[];
  total: number;
  summary: {
    total_stock_value: number;
    low_stock_items: number;
    critical_items: number;
  };
}

/**
 * 분석 API 공통 파라미터
 */
export interface AnalyticsParams {
  start_date?: string;
  end_date?: string;
  line_code?: string;
  product_code?: string;
  shift?: string;
  page?: number;
  page_size?: number;
}
