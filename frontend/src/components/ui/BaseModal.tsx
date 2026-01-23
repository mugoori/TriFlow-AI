/**
 * BaseModal - 공용 모달 컴포넌트
 * 모든 상세 모달의 공통 구조를 제공
 */

import { type ReactNode, type ElementType } from 'react';
import { X } from 'lucide-react';

export interface BaseModalProps {
  /** 모달 열림 상태 */
  isOpen?: boolean;
  /** 닫기 핸들러 */
  onClose: () => void;
  /** 모달 제목 */
  title: string;
  /** 제목 옆에 표시할 아이콘 */
  icon?: ElementType;
  /** 아이콘 색상 클래스 */
  iconColor?: string;
  /** 제목 옆에 표시할 상태 뱃지 */
  statusBadge?: ReactNode;
  /** 모달 내용 */
  children: ReactNode;
  /** 모달 하단 액션 버튼 */
  actions?: ReactNode;
  /** 모달 너비 (기본: max-w-3xl) */
  maxWidth?: string;
}

export function BaseModal({
  isOpen = true,
  onClose,
  title,
  icon: Icon,
  iconColor = 'text-blue-500',
  statusBadge,
  children,
  actions,
  maxWidth = 'max-w-3xl',
}: BaseModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className={`bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full ${maxWidth} max-h-[90vh] overflow-hidden flex flex-col`}>
        {/* Header */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {Icon && <Icon className={`w-5 h-5 ${iconColor}`} />}
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {title}
            </h2>
            {statusBadge}
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {children}
        </div>

        {/* Footer - Actions */}
        {actions && (
          <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-end gap-3">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}

export default BaseModal;
