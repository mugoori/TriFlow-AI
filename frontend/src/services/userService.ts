/**
 * 사용자 관리 서비스
 * RBAC 및 Data Scope 관리 API 호출
 */
import { apiClient } from './api';
import type {
  UserListResponse,
  UserDetail,
  RoleListResponse,
  RolePermissionsResponse,
  FactoryLineResponse,
  UserRoleUpdateRequest,
  DataScopeUpdateRequest,
  RoleUpdateResult,
  DataScopeUpdateResult,
  DataScope,
} from '../types/rbac';

const BASE_PATH = '/api/v1/users';

export const userService = {
  /**
   * 테넌트 내 사용자 목록 조회
   * admin, approver만 접근 가능
   */
  async listUsers(params?: {
    skip?: number;
    limit?: number;
    search?: string;
    role_filter?: string;
  }): Promise<UserListResponse> {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.set('skip', String(params.skip));
    if (params?.limit !== undefined) queryParams.set('limit', String(params.limit));
    if (params?.search) queryParams.set('search', params.search);
    if (params?.role_filter) queryParams.set('role_filter', params.role_filter);

    const queryString = queryParams.toString();
    const endpoint = queryString ? `${BASE_PATH}/?${queryString}` : `${BASE_PATH}/`;

    return apiClient.get<UserListResponse>(endpoint);
  },

  /**
   * 사용자 상세 조회
   * admin, approver만 접근 가능
   */
  async getUser(userId: string): Promise<UserDetail> {
    return apiClient.get<UserDetail>(`${BASE_PATH}/${userId}`);
  },

  /**
   * 사용자 역할 변경
   * admin만 접근 가능
   */
  async updateRole(userId: string, role: string): Promise<RoleUpdateResult> {
    return apiClient.patch<RoleUpdateResult>(`${BASE_PATH}/${userId}/role`, {
      role,
    } as UserRoleUpdateRequest);
  },

  /**
   * 사용자 Data Scope 조회
   * admin만 접근 가능
   */
  async getDataScope(userId: string): Promise<DataScope> {
    return apiClient.get<DataScope>(`${BASE_PATH}/${userId}/data-scope`);
  },

  /**
   * 사용자 Data Scope 설정
   * admin만 접근 가능
   */
  async updateDataScope(
    userId: string,
    scope: DataScopeUpdateRequest
  ): Promise<DataScopeUpdateResult> {
    return apiClient.patch<DataScopeUpdateResult>(
      `${BASE_PATH}/${userId}/data-scope`,
      scope
    );
  },

  /**
   * 역할 목록 조회
   * 모든 인증된 사용자 접근 가능
   */
  async getRoles(): Promise<RoleListResponse> {
    return apiClient.get<RoleListResponse>(`${BASE_PATH}/roles`);
  },

  /**
   * 역할별 권한 조회
   * 모든 인증된 사용자 접근 가능
   */
  async getRolePermissions(role: string): Promise<RolePermissionsResponse> {
    return apiClient.get<RolePermissionsResponse>(`${BASE_PATH}/roles/${role}/permissions`);
  },

  /**
   * 공장/라인 코드 목록 조회
   * admin만 접근 가능
   */
  async getFactoryLines(): Promise<FactoryLineResponse> {
    return apiClient.get<FactoryLineResponse>(`${BASE_PATH}/factory-lines`);
  },

  /**
   * 현재 사용자의 Data Scope 조회
   * 모든 인증된 사용자 접근 가능
   */
  async getMyDataScope(): Promise<DataScope> {
    return apiClient.get<DataScope>(`${BASE_PATH}/me/data-scope`);
  },
};
