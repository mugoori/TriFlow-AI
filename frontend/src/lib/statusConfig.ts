/**
 * 상태 표시 관련 공통 상수
 * 승인/거부 상태, 색상, 라벨 등을 중앙 관리
 */

// 공통 상태 (모든 승인 시스템에서 사용)
export type CommonStatus = 'pending' | 'approved' | 'rejected';

// 샘플 전용 상태
export type SampleStatus = CommonStatus | 'archived';

// 규칙 후보 전용 상태
export type RuleCandidateStatus = CommonStatus | 'testing';

// 모든 상태 타입
export type ApprovalStatus = CommonStatus | 'archived' | 'testing';

/**
 * 상태 라벨 (한글)
 */
export const STATUS_LABELS: Record<ApprovalStatus, string> = {
  pending: '대기',
  approved: '승인',
  rejected: '거부',
  archived: '보관',
  testing: '테스트 중',
};

/**
 * 상태별 색상 클래스 (Tailwind CSS)
 */
export const STATUS_COLORS: Record<ApprovalStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  approved: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  archived: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-400',
  testing: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

/**
 * 샘플 카테고리 라벨
 */
export const SAMPLE_CATEGORY_LABELS: Record<string, string> = {
  threshold_adjustment: '임계값 조정',
  field_correction: '필드 수정',
  validation_failure: '검증 실패',
  general: '일반',
};

/**
 * 상태 라벨 가져오기 (타입 안전)
 */
export function getStatusLabel(status: string): string {
  return STATUS_LABELS[status as ApprovalStatus] ?? status;
}

/**
 * 상태 색상 가져오기 (타입 안전)
 */
export function getStatusColor(status: string): string {
  return STATUS_COLORS[status as ApprovalStatus] ?? STATUS_COLORS.pending;
}
