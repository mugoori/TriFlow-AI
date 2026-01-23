/**
 * RBAC (Role-Based Access Control) 관련 TypeScript 타입 정의
 */

// 5-Tier 역할 타입
export type Role = 'admin' | 'approver' | 'operator' | 'user' | 'viewer';

// 역할 계층 레벨
export const ROLE_LEVELS: Record<Role, number> = {
  admin: 5,
  approver: 4,
  operator: 3,
  user: 2,
  viewer: 1,
};

// 역할 메타데이터
export interface RoleInfo {
  role: Role;
  level: number;
  label: string;
  description: string;
}

// 역할 목록 응답
export interface RoleListResponse {
  roles: RoleInfo[];
}

// Data Scope 설정
export interface DataScope {
  factory_codes: string[];
  line_codes: string[];
  product_families: string[];
  shift_codes: string[];
  equipment_ids: string[];
  all_access: boolean;
}

// 사용자 상세 정보
export interface UserDetail {
  user_id: string;
  tenant_id: string;
  email: string;
  username: string;
  display_name: string | null;
  role: Role;
  is_active: boolean;
  status: string;
  created_at: string;
  last_login: string | null;
  data_scope: DataScope;
  oauth_provider: string | null;
  profile_image_url: string | null;
}

// 사용자 목록 응답
export interface UserListResponse {
  users: UserDetail[];
  total: number;
}

// 역할 변경 요청
export interface UserRoleUpdateRequest {
  role: Role;
}

// Data Scope 변경 요청
export interface DataScopeUpdateRequest {
  factory_codes: string[];
  line_codes: string[];
  product_families: string[];
  shift_codes: string[];
  equipment_ids: string[];
  all_access: boolean;
}

// 권한 정보
export interface PermissionInfo {
  resource: string;
  action: string;
  permission: string;
}

// 역할별 권한 응답
export interface RolePermissionsResponse {
  role: string;
  level: number;
  permissions: string[];
  permissions_detail: PermissionInfo[];
}

// 공장/라인 코드 응답
export interface FactoryLineResponse {
  factory_codes: string[];
  line_codes: string[];
}

// 역할 변경 결과
export interface RoleUpdateResult {
  message: string;
  user_id: string;
  old_role: string;
  new_role: string;
}

// Data Scope 변경 결과
export interface DataScopeUpdateResult {
  message: string;
  user_id: string;
  data_scope: DataScope;
}

// 역할 한글 라벨
export const ROLE_LABELS: Record<Role, string> = {
  admin: '관리자',
  approver: '승인자',
  operator: '운영자',
  user: '사용자',
  viewer: '조회자',
};

// 역할 설명
export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  admin: '테넌트 전체 관리 권한. 모든 리소스에 대한 CRUD 및 사용자 관리 가능.',
  approver: '규칙/워크플로우 승인 권한. 읽기, 실행, 승인 가능.',
  operator: '일상 운영 담당. 읽기, 실행, 센서 데이터 관리 가능.',
  user: '기본 사용자. 생성/수정 가능, 삭제/승인 불가.',
  viewer: '읽기 전용. 조회만 가능, 채팅 허용.',
};
