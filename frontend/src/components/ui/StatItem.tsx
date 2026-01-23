/**
 * StatItem - 통계 아이템 컴포넌트
 * 아이콘, 라벨, 값을 표시하는 재사용 가능한 컴포넌트
 */

import { type ElementType } from 'react';

export interface StatItemProps {
  /** 표시할 라벨 */
  label: string;
  /** 표시할 값 */
  value: number | string;
  /** Lucide 아이콘 컴포넌트 */
  icon: ElementType;
  /** 배경 색상 클래스 (예: "bg-blue-500") */
  color: string;
}

export function StatItem({ label, value, icon: Icon, color }: StatItemProps) {
  return (
    <div className="flex items-center gap-3">
      <div className={`p-2 rounded-lg ${color}`}>
        <Icon className="w-4 h-4 text-white" />
      </div>
      <div>
        <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
        <p className="text-lg font-semibold text-gray-900 dark:text-white">{value}</p>
      </div>
    </div>
  );
}

export default StatItem;
