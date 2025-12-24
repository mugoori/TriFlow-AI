/**
 * BI Service - AWS QuickSight GenBI 동일 기능 API 서비스
 *
 * 3대 핵심 기능:
 * 1. AI Insights (Executive Summary)
 * 2. Data Stories (내러티브 보고서)
 * 3. Chart Refinement (Refinement Loop)
 */

import { apiClient } from './api';
import type {
  AIInsight,
  InsightRequest,
  InsightResponse,
  InsightListResponse,
  InsightFeedbackRequest,
  DataStory,
  StoryCreateRequest,
  StoryUpdateRequest,
  StoryListResponse,
  StorySectionCreateRequest,
  StorySection,
  ChartRefineRequest,
  ChartRefineResponse,
  SavedChart,
  ChatRequest,
  ChatResponse,
  ChatSessionListResponse,
  ChatMessageListResponse,
  PinInsightResponse,
  PinnedInsightsResponse,
  InsightDisplayMode,
  Dashboard,
  DashboardCreateRequest,
  DashboardUpdateRequest,
  DashboardListResponse,
  ProductionResponse,
  DefectTrendResponse,
  OEEResponse,
  InventoryResponse,
  AnalyticsParams,
} from '../types/bi';

const BI_API_PREFIX = '/api/v1/bi';

export const biService = {
  // =====================================================
  // 1. AI Insights (Executive Summary)
  // =====================================================

  /**
   * AI 인사이트 생성
   */
  async generateInsight(request: InsightRequest): Promise<InsightResponse> {
    return await apiClient.post<InsightResponse>(`${BI_API_PREFIX}/insights`, request);
  },

  /**
   * 인사이트 목록 조회
   */
  async getInsights(params?: {
    source_type?: string;
    source_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<InsightListResponse> {
    const queryParams = new URLSearchParams();
    if (params?.source_type) queryParams.set('source_type', params.source_type);
    if (params?.source_id) queryParams.set('source_id', params.source_id);
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.page_size) queryParams.set('page_size', params.page_size.toString());

    const query = queryParams.toString();
    return await apiClient.get<InsightListResponse>(
      `${BI_API_PREFIX}/insights${query ? `?${query}` : ''}`
    );
  },

  /**
   * 인사이트 상세 조회
   */
  async getInsight(insightId: string): Promise<AIInsight> {
    return await apiClient.get<AIInsight>(`${BI_API_PREFIX}/insights/${insightId}`);
  },

  /**
   * 인사이트 피드백 제출
   */
  async submitInsightFeedback(
    insightId: string,
    feedback: InsightFeedbackRequest
  ): Promise<AIInsight> {
    return await apiClient.post<AIInsight>(
      `${BI_API_PREFIX}/insights/${insightId}/feedback`,
      feedback
    );
  },

  // =====================================================
  // 2. Data Stories (내러티브 보고서)
  // =====================================================

  /**
   * 스토리 생성
   */
  async createStory(request: StoryCreateRequest): Promise<DataStory> {
    return await apiClient.post<DataStory>(`${BI_API_PREFIX}/stories`, request);
  },

  /**
   * 스토리 목록 조회
   */
  async getStories(params?: {
    include_public?: boolean;
    page?: number;
    page_size?: number;
  }): Promise<StoryListResponse> {
    const queryParams = new URLSearchParams();
    if (params?.include_public !== undefined)
      queryParams.set('include_public', params.include_public.toString());
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.page_size) queryParams.set('page_size', params.page_size.toString());

    const query = queryParams.toString();
    return await apiClient.get<StoryListResponse>(
      `${BI_API_PREFIX}/stories${query ? `?${query}` : ''}`
    );
  },

  /**
   * 스토리 상세 조회
   */
  async getStory(storyId: string): Promise<DataStory> {
    return await apiClient.get<DataStory>(`${BI_API_PREFIX}/stories/${storyId}`);
  },

  /**
   * 스토리 수정
   */
  async updateStory(storyId: string, data: StoryUpdateRequest): Promise<DataStory> {
    return await apiClient.put<DataStory>(`${BI_API_PREFIX}/stories/${storyId}`, data);
  },

  /**
   * 스토리 삭제
   */
  async deleteStory(storyId: string): Promise<void> {
    return await apiClient.delete<void>(`${BI_API_PREFIX}/stories/${storyId}`);
  },

  /**
   * 스토리 발행
   */
  async publishStory(storyId: string): Promise<DataStory> {
    return await apiClient.post<DataStory>(`${BI_API_PREFIX}/stories/${storyId}/publish`, {});
  },

  /**
   * 섹션 추가
   */
  async addSection(storyId: string, section: StorySectionCreateRequest): Promise<StorySection> {
    return await apiClient.post<StorySection>(
      `${BI_API_PREFIX}/stories/${storyId}/sections`,
      section
    );
  },

  /**
   * 섹션 삭제
   */
  async deleteSection(storyId: string, sectionId: string): Promise<void> {
    return await apiClient.delete<void>(
      `${BI_API_PREFIX}/stories/${storyId}/sections/${sectionId}`
    );
  },

  // =====================================================
  // 3. Chart Refinement (Refinement Loop)
  // =====================================================

  /**
   * 차트 수정 (Refinement)
   */
  async refineChart(request: ChartRefineRequest): Promise<ChartRefineResponse> {
    return await apiClient.post<ChartRefineResponse>(`${BI_API_PREFIX}/charts/refine`, request);
  },

  // =====================================================
  // 4. Saved Charts (대시보드 고정 차트)
  // =====================================================

  /**
   * 저장된 차트 목록 조회
   */
  async getSavedCharts(): Promise<SavedChart[]> {
    return await apiClient.get<SavedChart[]>(`${BI_API_PREFIX}/charts/saved`);
  },

  /**
   * 차트 저장 (대시보드에 고정)
   */
  async saveChart(chart: Omit<SavedChart, 'chart_id' | 'created_at' | 'updated_at'>): Promise<SavedChart> {
    return await apiClient.post<SavedChart>(`${BI_API_PREFIX}/charts/saved`, chart);
  },

  /**
   * 저장된 차트 삭제
   */
  async deleteSavedChart(chartId: string): Promise<void> {
    return await apiClient.delete<void>(`${BI_API_PREFIX}/charts/saved/${chartId}`);
  },

  /**
   * 차트 순서 변경
   */
  async reorderCharts(chartIds: string[]): Promise<void> {
    return await apiClient.put<void>(`${BI_API_PREFIX}/charts/saved/reorder`, { chart_ids: chartIds });
  },

  // =====================================================
  // 5. Chat (대화형 GenBI)
  // =====================================================

  /**
   * AI 채팅 메시지 전송
   */
  async chat(request: ChatRequest): Promise<ChatResponse> {
    return await apiClient.post<ChatResponse>(`${BI_API_PREFIX}/chat`, request);
  },

  /**
   * 채팅 세션 목록 조회
   */
  async getChatSessions(params?: {
    include_inactive?: boolean;
    page?: number;
    page_size?: number;
  }): Promise<ChatSessionListResponse> {
    const queryParams = new URLSearchParams();
    if (params?.include_inactive !== undefined)
      queryParams.set('include_inactive', params.include_inactive.toString());
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.page_size) queryParams.set('page_size', params.page_size.toString());

    const query = queryParams.toString();
    return await apiClient.get<ChatSessionListResponse>(
      `${BI_API_PREFIX}/chat/sessions${query ? `?${query}` : ''}`
    );
  },

  /**
   * 채팅 세션 메시지 목록 조회
   */
  async getSessionMessages(
    sessionId: string,
    params?: { page?: number; page_size?: number }
  ): Promise<ChatMessageListResponse> {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.page_size) queryParams.set('page_size', params.page_size.toString());

    const query = queryParams.toString();
    return await apiClient.get<ChatMessageListResponse>(
      `${BI_API_PREFIX}/chat/sessions/${sessionId}/messages${query ? `?${query}` : ''}`
    );
  },

  /**
   * 채팅 세션 삭제
   */
  async deleteChatSession(sessionId: string): Promise<void> {
    return await apiClient.delete<void>(`${BI_API_PREFIX}/chat/sessions/${sessionId}`);
  },

  /**
   * 채팅 세션 제목 수정
   */
  async updateChatSession(sessionId: string, title: string): Promise<void> {
    return await apiClient.put<void>(`${BI_API_PREFIX}/chat/sessions/${sessionId}`, { title });
  },

  // =====================================================
  // 6. Pinned Insights (고정된 인사이트)
  // =====================================================

  /**
   * 인사이트 고정 (대시보드에 Pin)
   */
  async pinInsight(
    insightId: string,
    options?: {
      display_mode?: InsightDisplayMode;
      grid_position?: { x: number; y: number; w: number; h: number };
    }
  ): Promise<PinInsightResponse> {
    return await apiClient.post<PinInsightResponse>(
      `${BI_API_PREFIX}/insights/${insightId}/pin`,
      options || {}
    );
  },

  /**
   * 인사이트 고정 해제
   */
  async unpinInsight(insightId: string): Promise<void> {
    return await apiClient.delete<void>(`${BI_API_PREFIX}/insights/${insightId}/pin`);
  },

  /**
   * 고정된 인사이트 목록 조회
   */
  async getPinnedInsights(): Promise<PinnedInsightsResponse> {
    return await apiClient.get<PinnedInsightsResponse>(`${BI_API_PREFIX}/insights/pinned`);
  },

  // =====================================================
  // 7. Dashboard (대시보드 관리)
  // =====================================================

  /**
   * 대시보드 목록 조회
   */
  async getDashboards(params?: {
    page?: number;
    page_size?: number;
    include_public?: boolean;
  }): Promise<DashboardListResponse> {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.page_size) queryParams.set('page_size', params.page_size.toString());
    if (params?.include_public !== undefined)
      queryParams.set('include_public', params.include_public.toString());

    const query = queryParams.toString();
    return await apiClient.get<DashboardListResponse>(
      `${BI_API_PREFIX}/dashboards${query ? `?${query}` : ''}`
    );
  },

  /**
   * 대시보드 상세 조회
   */
  async getDashboard(dashboardId: string): Promise<Dashboard> {
    return await apiClient.get<Dashboard>(`${BI_API_PREFIX}/dashboards/${dashboardId}`);
  },

  /**
   * 대시보드 생성
   */
  async createDashboard(data: DashboardCreateRequest): Promise<Dashboard> {
    return await apiClient.post<Dashboard>(`${BI_API_PREFIX}/dashboards`, data);
  },

  /**
   * 대시보드 수정
   */
  async updateDashboard(dashboardId: string, data: DashboardUpdateRequest): Promise<Dashboard> {
    return await apiClient.put<Dashboard>(`${BI_API_PREFIX}/dashboards/${dashboardId}`, data);
  },

  /**
   * 대시보드 삭제
   */
  async deleteDashboard(dashboardId: string): Promise<void> {
    return await apiClient.delete<void>(`${BI_API_PREFIX}/dashboards/${dashboardId}`);
  },

  // =====================================================
  // 8. Analytics (분석 API)
  // =====================================================

  /**
   * 생산 실적 분석
   */
  async getProductionAnalytics(params?: AnalyticsParams): Promise<ProductionResponse> {
    const queryParams = new URLSearchParams();
    if (params?.start_date) queryParams.set('start_date', params.start_date);
    if (params?.end_date) queryParams.set('end_date', params.end_date);
    if (params?.line_code) queryParams.set('line_code', params.line_code);
    if (params?.product_code) queryParams.set('product_code', params.product_code);
    if (params?.shift) queryParams.set('shift', params.shift);
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.page_size) queryParams.set('page_size', params.page_size.toString());

    const query = queryParams.toString();
    return await apiClient.get<ProductionResponse>(
      `${BI_API_PREFIX}/analytics/production${query ? `?${query}` : ''}`
    );
  },

  /**
   * 불량 추이 분석
   */
  async getDefectTrend(params?: AnalyticsParams): Promise<DefectTrendResponse> {
    const queryParams = new URLSearchParams();
    if (params?.start_date) queryParams.set('start_date', params.start_date);
    if (params?.end_date) queryParams.set('end_date', params.end_date);
    if (params?.line_code) queryParams.set('line_code', params.line_code);
    if (params?.product_code) queryParams.set('product_code', params.product_code);
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.page_size) queryParams.set('page_size', params.page_size.toString());

    const query = queryParams.toString();
    return await apiClient.get<DefectTrendResponse>(
      `${BI_API_PREFIX}/analytics/defect-trend${query ? `?${query}` : ''}`
    );
  },

  /**
   * OEE 분석
   */
  async getOEEAnalytics(params?: AnalyticsParams): Promise<OEEResponse> {
    const queryParams = new URLSearchParams();
    if (params?.start_date) queryParams.set('start_date', params.start_date);
    if (params?.end_date) queryParams.set('end_date', params.end_date);
    if (params?.line_code) queryParams.set('line_code', params.line_code);
    if (params?.shift) queryParams.set('shift', params.shift);
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.page_size) queryParams.set('page_size', params.page_size.toString());

    const query = queryParams.toString();
    return await apiClient.get<OEEResponse>(
      `${BI_API_PREFIX}/analytics/oee${query ? `?${query}` : ''}`
    );
  },

  /**
   * 재고 분석
   */
  async getInventoryAnalytics(params?: AnalyticsParams): Promise<InventoryResponse> {
    const queryParams = new URLSearchParams();
    if (params?.start_date) queryParams.set('start_date', params.start_date);
    if (params?.end_date) queryParams.set('end_date', params.end_date);
    if (params?.product_code) queryParams.set('product_code', params.product_code);
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.page_size) queryParams.set('page_size', params.page_size.toString());

    const query = queryParams.toString();
    return await apiClient.get<InventoryResponse>(
      `${BI_API_PREFIX}/analytics/inventory${query ? `?${query}` : ''}`
    );
  },
};

export default biService;
