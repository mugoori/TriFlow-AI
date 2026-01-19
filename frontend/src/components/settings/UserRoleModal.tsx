/**
 * 사용자 역할 변경 모달
 * 5-Tier 역할 선택 및 권한 미리보기
 */
import { useState, useEffect } from 'react';
import { userService } from '../../services/userService';
import type { UserDetail, Role, RolePermissionsResponse } from '../../types/rbac';
import { ROLE_LABELS, ROLE_DESCRIPTIONS, ROLE_LEVELS } from '../../types/rbac';
import { useAuth } from '../../contexts/AuthContext';

interface UserRoleModalProps {
  user: UserDetail;
  onClose: () => void;
  onUpdated: () => void;
}

const ROLES: Role[] = ['admin', 'approver', 'operator', 'user', 'viewer'];

export default function UserRoleModal({ user, onClose, onUpdated }: UserRoleModalProps) {
  const { user: currentUser } = useAuth();
  const [selectedRole, setSelectedRole] = useState<Role>(user.role);
  const [permissions, setPermissions] = useState<RolePermissionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 자기 자신인지 체크
  const isSelf = currentUser?.user_id === user.user_id;

  // 선택된 역할의 권한 로드
  useEffect(() => {
    const loadPermissions = async () => {
      setLoading(true);
      try {
        const response = await userService.getRolePermissions(selectedRole);
        setPermissions(response);
      } catch (err) {
        console.error('Failed to load permissions:', err);
      } finally {
        setLoading(false);
      }
    };
    loadPermissions();
  }, [selectedRole]);

  const handleSave = async () => {
    if (selectedRole === user.role) {
      onClose();
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await userService.updateRole(user.user_id, selectedRole);
      onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : '역할 변경에 실패했습니다');
      setSaving(false);
    }
  };

  const getRoleLevelBadge = (role: Role) => {
    const level = ROLE_LEVELS[role];
    return `Lv.${level}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-lg mx-4 overflow-hidden">
        {/* 헤더 */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
            사용자 역할 변경
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {user.display_name || user.email}
          </p>
        </div>

        {/* 본문 */}
        <div className="px-6 py-4">
          {isSelf && (
            <div className="mb-4 p-3 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 rounded-lg text-sm">
              자기 자신의 역할은 변경할 수 없습니다.
            </div>
          )}

          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* 역할 선택 */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
              역할 선택
            </label>
            <div className="space-y-2">
              {ROLES.map((role) => (
                <button
                  key={role}
                  onClick={() => !isSelf && setSelectedRole(role)}
                  disabled={isSelf}
                  className={`w-full p-3 rounded-lg border text-left transition-colors ${
                    selectedRole === role
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
                  } ${isSelf ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium text-slate-900 dark:text-slate-100">
                        {ROLE_LABELS[role]}
                      </span>
                      <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
                        {getRoleLevelBadge(role)}
                      </span>
                    </div>
                    {selectedRole === role && (
                      <span className="text-blue-600 dark:text-blue-400">✓</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    {ROLE_DESCRIPTIONS[role]}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* 권한 미리보기 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
              권한 미리보기
            </label>
            <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded-lg max-h-40 overflow-y-auto">
              {loading ? (
                <div className="text-center py-4 text-slate-500 dark:text-slate-400 text-sm">
                  로딩 중...
                </div>
              ) : permissions ? (
                <div className="flex flex-wrap gap-1.5">
                  {permissions.permissions.map((perm) => (
                    <span
                      key={perm}
                      className="px-2 py-0.5 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded text-xs"
                    >
                      {perm}
                    </span>
                  ))}
                  {permissions.permissions.length === 0 && (
                    <span className="text-slate-500 dark:text-slate-400 text-sm">
                      권한 없음
                    </span>
                  )}
                </div>
              ) : (
                <span className="text-slate-500 dark:text-slate-400 text-sm">
                  권한을 불러올 수 없습니다
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 푸터 */}
        <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-700 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving || isSelf || selectedRole === user.role}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  );
}
