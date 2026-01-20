/**
 * 역할별 권한 카드
 * 5-Tier RBAC 역할 및 권한 정보 표시 (읽기 전용)
 */
import { useState, useEffect } from 'react';
import { userService } from '../../services/userService';
import type { RoleInfo } from '../../types/rbac';

// 권한 한글 매핑
const PERMISSION_LABELS: Record<string, Record<string, string>> = {
  // 리소스 한글명
  resources: {
    'agents': '에이전트',
    'audit': '감사 로그',
    'deployments': '배포',
    'experiments': '실험',
    'feedback': '피드백',
    'proposals': '제안',
    'rule_extraction': '규칙 추출',
    'rulesets': '규칙셋',
    'samples': '샘플',
    'sensors': '센서',
    'settings': '설정',
    'tenants': '테넌트',
    'users': '사용자',
    'workflows': '워크플로우',
    '워크플로우': '워크플로우',
    '규칙셋': '규칙셋',
  },
  // 액션 한글명
  actions: {
    'read': '조회',
    'create': '생성',
    'update': '수정',
    'delete': '삭제',
    'execute': '실행',
    'approve': '승인',
    'rollback': '롤백',
  }
};

// 모든 액션 타입 (테이블 헤더용)
const ALL_ACTIONS = ['read', 'create', 'update', 'delete', 'execute', 'approve', 'rollback'] as const;

export default function RolePermissionsCard() {
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [expandedRole, setExpandedRole] = useState<string | null>(null);
  const [permissions, setPermissions] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadRoles = async () => {
      try {
        const response = await userService.getRoles();
        setRoles(response.roles);
      } catch (err) {
        console.error('Failed to load roles:', err);
        // 폴백: 하드코딩된 역할 정보 사용
        setRoles([
          { role: 'admin', level: 5, label: 'Admin', description: '테넌트 전체 관리' },
          { role: 'approver', level: 4, label: 'Approver', description: '승인 권한' },
          { role: 'operator', level: 3, label: 'Operator', description: '운영 담당' },
          { role: 'user', level: 2, label: 'User', description: '기본 사용자' },
          { role: 'viewer', level: 1, label: 'Viewer', description: '읽기 전용' },
        ]);
      } finally {
        setLoading(false);
      }
    };
    loadRoles();
  }, []);

  const toggleExpand = async (role: string) => {
    if (expandedRole === role) {
      setExpandedRole(null);
      return;
    }

    setExpandedRole(role);

    // 권한 정보가 없으면 로드
    if (!permissions[role]) {
      try {
        const response = await userService.getRolePermissions(role);
        setPermissions((prev) => ({
          ...prev,
          [role]: response.permissions,
        }));
      } catch (err) {
        console.error(`Failed to load permissions for ${role}:`, err);
      }
    }
  };

  const getRoleLevelColor = (level: number) => {
    switch (level) {
      case 5:
        return 'bg-red-500';
      case 4:
        return 'bg-purple-500';
      case 3:
        return 'bg-blue-500';
      case 2:
        return 'bg-green-500';
      case 1:
        return 'bg-slate-400';
      default:
        return 'bg-slate-400';
    }
  };

  const getRoleBgColor = (level: number) => {
    switch (level) {
      case 5:
        return 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800';
      case 4:
        return 'bg-purple-50 dark:bg-purple-900/10 border-purple-200 dark:border-purple-800';
      case 3:
        return 'bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800';
      case 2:
        return 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800';
      case 1:
        return 'bg-slate-50 dark:bg-slate-900/30 border-slate-200 dark:border-slate-700';
      default:
        return 'bg-slate-50 dark:bg-slate-900/30 border-slate-200 dark:border-slate-700';
    }
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
      <div className="flex items-center gap-2 mb-6">
        <span className="text-lg">🔐</span>
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
            역할별 권한
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            5-Tier RBAC 역할 계층 (클릭하여 권한 확인)
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {roles.map((role) => (
          <div key={role.role} className="overflow-hidden">
            <button
              onClick={() => toggleExpand(role.role)}
              className={`w-full p-4 rounded-lg border transition-all ${getRoleBgColor(role.level)} ${
                expandedRole === role.role ? 'ring-2 ring-blue-500' : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-2 h-8 rounded-full ${getRoleLevelColor(role.level)}`}
                  />
                  <div className="text-left">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-900 dark:text-slate-100">
                        {role.label}
                      </span>
                      <span className="text-xs px-1.5 py-0.5 bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400 rounded">
                        Lv.{role.level}
                      </span>
                    </div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      {role.description}
                    </p>
                  </div>
                </div>
                <span
                  className={`text-slate-400 transition-transform ${
                    expandedRole === role.role ? 'rotate-180' : ''
                  }`}
                >
                  ▼
                </span>
              </div>
            </button>

            {/* 권한 목록 (확장 시) - 테이블 형식 */}
            {expandedRole === role.role && (
              <div className="mt-2 p-4 bg-slate-50 dark:bg-slate-900 rounded-lg overflow-x-auto">
                {permissions[role.role] ? (
                  permissions[role.role].length > 0 ? (
                    (() => {
                      // 권한을 리소스별로 그룹화
                      const groupedPermissions = permissions[role.role].reduce((acc, perm) => {
                        const [resource, action] = perm.split(':');
                        if (!acc[resource]) acc[resource] = [];
                        acc[resource].push(action);
                        return acc;
                      }, {} as Record<string, string[]>);

                      return (
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-slate-200 dark:border-slate-700">
                              <th className="text-left py-2 px-3 font-medium text-slate-700 dark:text-slate-300">
                                리소스
                              </th>
                              {ALL_ACTIONS.map(action => (
                                <th key={action} className="text-center py-2 px-2 font-medium text-slate-600 dark:text-slate-400">
                                  {PERMISSION_LABELS.actions[action]}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(groupedPermissions)
                              .sort(([a], [b]) => {
                                const labelA = PERMISSION_LABELS.resources[a] || a;
                                const labelB = PERMISSION_LABELS.resources[b] || b;
                                return labelA.localeCompare(labelB, 'ko');
                              })
                              .map(([resource, actions]) => {
                                const resourceLabel = PERMISSION_LABELS.resources[resource] || resource;
                                return (
                                  <tr key={resource} className="border-b border-slate-100 dark:border-slate-800 hover:bg-white dark:hover:bg-slate-800">
                                    <td className="py-2 px-3 font-medium text-slate-700 dark:text-slate-300">
                                      {resourceLabel}
                                    </td>
                                    {ALL_ACTIONS.map(action => (
                                      <td key={action} className="text-center py-2 px-2">
                                        {actions.includes(action) ? (
                                          <span className={`font-bold ${
                                            action === 'delete' ? 'text-red-600 dark:text-red-400' :
                                            action === 'approve' ? 'text-purple-600 dark:text-purple-400' :
                                            action === 'execute' ? 'text-blue-600 dark:text-blue-400' :
                                            action === 'rollback' ? 'text-orange-600 dark:text-orange-400' :
                                            'text-green-600 dark:text-green-400'
                                          }`}>
                                            ✓
                                          </span>
                                        ) : (
                                          <span className="text-slate-300 dark:text-slate-600">-</span>
                                        )}
                                      </td>
                                    ))}
                                  </tr>
                                );
                              })}
                          </tbody>
                        </table>
                      );
                    })()
                  ) : (
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      할당된 권한이 없습니다
                    </p>
                  )
                ) : (
                  <div className="flex items-center justify-center py-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
