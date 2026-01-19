/**
 * 사용자 관리 섹션
 * 테넌트 내 사용자 목록 표시 및 역할/Data Scope 관리
 */
import { useState, useEffect, useCallback } from 'react';
import { userService } from '../../services/userService';
import type { UserDetail, Role } from '../../types/rbac';
import { ROLE_LABELS } from '../../types/rbac';
import UserRoleModal from './UserRoleModal';
import DataScopeEditor from './DataScopeEditor';

interface UserManagementSectionProps {
  isAdmin: boolean;
}

export default function UserManagementSection({ isAdmin }: UserManagementSectionProps) {
  const [users, setUsers] = useState<UserDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 검색/필터
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('');

  // 모달 상태
  const [selectedUser, setSelectedUser] = useState<UserDetail | null>(null);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [showScopeEditor, setShowScopeEditor] = useState(false);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await userService.listUsers({
        search: search || undefined,
        role_filter: roleFilter || undefined,
        limit: 50,
      });
      setUsers(response.users);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : '사용자 목록을 불러오는데 실패했습니다');
    } finally {
      setLoading(false);
    }
  }, [search, roleFilter]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleRoleClick = (user: UserDetail) => {
    setSelectedUser(user);
    setShowRoleModal(true);
  };

  const handleScopeClick = (user: UserDetail) => {
    setSelectedUser(user);
    setShowScopeEditor(true);
  };

  const handleRoleUpdated = () => {
    setShowRoleModal(false);
    setSelectedUser(null);
    loadUsers();
  };

  const handleScopeUpdated = () => {
    setShowScopeEditor(false);
    setSelectedUser(null);
    loadUsers();
  };

  const getRoleBadgeColor = (role: Role) => {
    switch (role) {
      case 'admin':
        return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
      case 'approver':
        return 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400';
      case 'operator':
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400';
      case 'user':
        return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400';
      case 'viewer':
        return 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400';
      default:
        return 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400';
    }
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <span className="text-lg">👥</span>
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
              사용자 관리
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              테넌트 내 사용자 목록 ({total}명)
            </p>
          </div>
        </div>
      </div>

      {/* 검색/필터 */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="이메일, 이름 검색..."
          className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        />
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        >
          <option value="">모든 역할</option>
          <option value="admin">관리자</option>
          <option value="approver">승인자</option>
          <option value="operator">운영자</option>
          <option value="user">사용자</option>
          <option value="viewer">조회자</option>
        </select>
        <button
          onClick={loadUsers}
          disabled={loading}
          className="px-4 py-2 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors text-sm font-medium disabled:opacity-50"
        >
          새로고침
        </button>
      </div>

      {/* 에러 표시 */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* 로딩 */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : users.length === 0 ? (
        <div className="text-center py-12 text-slate-500 dark:text-slate-400">
          사용자가 없습니다
        </div>
      ) : (
        /* 사용자 테이블 */
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600 dark:text-slate-400">
                  사용자
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600 dark:text-slate-400">
                  이메일
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600 dark:text-slate-400">
                  역할
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600 dark:text-slate-400">
                  상태
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-600 dark:text-slate-400">
                  Data Scope
                </th>
                {isAdmin && (
                  <th className="text-right py-3 px-4 text-sm font-medium text-slate-600 dark:text-slate-400">
                    액션
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr
                  key={user.user_id}
                  className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/30"
                >
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-600 flex items-center justify-center text-sm font-medium text-slate-600 dark:text-slate-300">
                        {(user.display_name || user.email)[0].toUpperCase()}
                      </div>
                      <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                        {user.display_name || user.username}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-sm text-slate-600 dark:text-slate-400">
                      {user.email}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRoleBadgeColor(user.role)}`}
                    >
                      {ROLE_LABELS[user.role] || user.role}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        user.is_active
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400'
                      }`}
                    >
                      {user.is_active ? '활성' : '비활성'}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    {user.data_scope.all_access ? (
                      <span className="text-xs text-purple-600 dark:text-purple-400 font-medium">
                        전체 접근
                      </span>
                    ) : (
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        {user.data_scope.factory_codes.length > 0 || user.data_scope.line_codes.length > 0
                          ? `공장 ${user.data_scope.factory_codes.length}개, 라인 ${user.data_scope.line_codes.length}개`
                          : '미설정'}
                      </span>
                    )}
                  </td>
                  {isAdmin && (
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleRoleClick(user)}
                          className="px-3 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                        >
                          역할 변경
                        </button>
                        <button
                          onClick={() => handleScopeClick(user)}
                          className="px-3 py-1 text-xs font-medium text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/20 rounded transition-colors"
                        >
                          범위 설정
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 역할 변경 모달 */}
      {showRoleModal && selectedUser && (
        <UserRoleModal
          user={selectedUser}
          onClose={() => {
            setShowRoleModal(false);
            setSelectedUser(null);
          }}
          onUpdated={handleRoleUpdated}
        />
      )}

      {/* Data Scope 편집기 */}
      {showScopeEditor && selectedUser && (
        <DataScopeEditor
          user={selectedUser}
          onClose={() => {
            setShowScopeEditor(false);
            setSelectedUser(null);
          }}
          onUpdated={handleScopeUpdated}
        />
      )}
    </div>
  );
}
