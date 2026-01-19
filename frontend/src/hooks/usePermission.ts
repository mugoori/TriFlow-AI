/**
 * 권한 체크 Hook
 * 현재 사용자의 역할에 따른 권한 확인
 */
import { useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import type { Role } from '../types/rbac';
import { ROLE_LEVELS } from '../types/rbac';

export function usePermission() {
  const { user } = useAuth();

  return useMemo(() => {
    const userRole = (user?.role as Role) || 'viewer';
    const userLevel = ROLE_LEVELS[userRole] || 1;

    /**
     * 특정 역할 목록 중 하나인지 확인
     */
    const hasRole = (roles: Role[]): boolean => {
      return roles.includes(userRole);
    };

    /**
     * 특정 역할 이상인지 확인 (레벨 기반)
     */
    const hasRoleLevel = (minRole: Role): boolean => {
      const minLevel = ROLE_LEVELS[minRole] || 1;
      return userLevel >= minLevel;
    };

    /**
     * Admin인지 확인
     */
    const isAdmin = (): boolean => {
      return userRole === 'admin';
    };

    /**
     * Admin 또는 Approver인지 확인
     */
    const isApproverOrAbove = (): boolean => {
      return hasRole(['admin', 'approver']);
    };

    /**
     * Operator 이상인지 확인
     */
    const isOperatorOrAbove = (): boolean => {
      return hasRole(['admin', 'approver', 'operator']);
    };

    /**
     * User 이상인지 확인 (Viewer 제외)
     */
    const isUserOrAbove = (): boolean => {
      return hasRole(['admin', 'approver', 'operator', 'user']);
    };

    /**
     * 사용자 관리 권한 (admin만)
     */
    const canManageUsers = (): boolean => {
      return isAdmin();
    };

    /**
     * 사용자 목록 조회 권한 (admin, approver)
     */
    const canViewUsers = (): boolean => {
      return isApproverOrAbove();
    };

    /**
     * Data Scope 설정 권한 (admin만)
     */
    const canManageDataScope = (): boolean => {
      return isAdmin();
    };

    /**
     * 승인 권한 (admin, approver)
     */
    const canApprove = (): boolean => {
      return isApproverOrAbove();
    };

    /**
     * 실행 권한 (admin, approver, operator)
     */
    const canExecute = (): boolean => {
      return isOperatorOrAbove();
    };

    /**
     * 생성/수정 권한 (viewer 제외 모두)
     */
    const canEdit = (): boolean => {
      return isUserOrAbove();
    };

    /**
     * 삭제 권한 (admin만)
     */
    const canDelete = (): boolean => {
      return isAdmin();
    };

    return {
      // 현재 사용자 역할 정보
      userRole,
      userLevel,

      // 역할 체크 함수
      hasRole,
      hasRoleLevel,
      isAdmin,
      isApproverOrAbove,
      isOperatorOrAbove,
      isUserOrAbove,

      // 기능별 권한 체크
      canManageUsers,
      canViewUsers,
      canManageDataScope,
      canApprove,
      canExecute,
      canEdit,
      canDelete,
    };
  }, [user]);
}

export default usePermission;
