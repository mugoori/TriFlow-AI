/**
 * StatusBadge - 상태 뱃지 컴포넌트
 * 승인 상태를 일관된 스타일로 표시
 */

import { type ElementType } from 'react';
import { STATUS_LABELS, STATUS_COLORS } from '@/lib/statusConfig';
import type { ApprovalStatus } from '@/services/ruleExtractionService';
import type { SampleStatus } from '@/services/sampleService';

type StatusType = ApprovalStatus | SampleStatus | string;

export interface StatusBadgeProps {
  /** 상태 값 */
  status: StatusType;
  /** 상태 앞에 표시할 아이콘 */
  icon?: ElementType;
  /** 크기 (기본: sm) */
  size?: 'xs' | 'sm' | 'md';
}

const SIZE_CLASSES = {
  xs: 'px-1.5 py-0.5 text-xs',
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-sm',
};

export function StatusBadge({ status, icon: Icon, size = 'sm' }: StatusBadgeProps) {
  const label = STATUS_LABELS[status as keyof typeof STATUS_LABELS] || status;
  const colorClass = STATUS_COLORS[status as keyof typeof STATUS_COLORS] || 'bg-gray-100 text-gray-700';

  return (
    <span className={`inline-flex items-center gap-1 rounded-full ${SIZE_CLASSES[size]} ${colorClass}`}>
      {Icon && <Icon className="w-3 h-3" />}
      {label}
    </span>
  );
}

export default StatusBadge;
