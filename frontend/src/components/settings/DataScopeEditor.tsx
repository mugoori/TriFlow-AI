/**
 * Data Scope 편집기
 * 사용자별 공장/라인 접근 범위 설정
 */
import { useState, useEffect } from 'react';
import { userService } from '../../services/userService';
import type { UserDetail, DataScope } from '../../types/rbac';

interface DataScopeEditorProps {
  user: UserDetail;
  onClose: () => void;
  onUpdated: () => void;
}

export default function DataScopeEditor({ user, onClose, onUpdated }: DataScopeEditorProps) {
  const [scope, setScope] = useState<DataScope>({
    factory_codes: [],
    line_codes: [],
    product_families: [],
    shift_codes: [],
    equipment_ids: [],
    all_access: false,
  });
  const [availableFactories, setAvailableFactories] = useState<string[]>([]);
  const [availableLines, setAvailableLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 초기 데이터 로드
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        // 현재 Data Scope 조회
        const currentScope = await userService.getDataScope(user.user_id);
        setScope({
          factory_codes: currentScope.factory_codes || [],
          line_codes: currentScope.line_codes || [],
          product_families: currentScope.product_families || [],
          shift_codes: currentScope.shift_codes || [],
          equipment_ids: currentScope.equipment_ids || [],
          all_access: currentScope.all_access || false,
        });

        // 사용 가능한 공장/라인 목록 조회
        try {
          const factoryLines = await userService.getFactoryLines();
          setAvailableFactories(factoryLines.factory_codes);
          setAvailableLines(factoryLines.line_codes);
        } catch {
          // 센서 데이터가 없을 경우 빈 목록 사용
          setAvailableFactories([]);
          setAvailableLines([]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Data Scope를 불러오는데 실패했습니다');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [user.user_id]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      await userService.updateDataScope(user.user_id, scope);
      onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Data Scope 저장에 실패했습니다');
      setSaving(false);
    }
  };

  const toggleFactory = (code: string) => {
    setScope((prev) => ({
      ...prev,
      factory_codes: prev.factory_codes.includes(code)
        ? prev.factory_codes.filter((c) => c !== code)
        : [...prev.factory_codes, code],
    }));
  };

  const toggleLine = (code: string) => {
    setScope((prev) => ({
      ...prev,
      line_codes: prev.line_codes.includes(code)
        ? prev.line_codes.filter((c) => c !== code)
        : [...prev.line_codes, code],
    }));
  };

  const toggleAllAccess = () => {
    setScope((prev) => ({
      ...prev,
      all_access: !prev.all_access,
      // all_access가 true가 되면 개별 선택은 무시됨
    }));
  };

  const selectAll = (type: 'factory' | 'line') => {
    if (type === 'factory') {
      setScope((prev) => ({
        ...prev,
        factory_codes: [...availableFactories],
      }));
    } else {
      setScope((prev) => ({
        ...prev,
        line_codes: [...availableLines],
      }));
    }
  };

  const clearAll = (type: 'factory' | 'line') => {
    if (type === 'factory') {
      setScope((prev) => ({
        ...prev,
        factory_codes: [],
      }));
    } else {
      setScope((prev) => ({
        ...prev,
        line_codes: [],
      }));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden max-h-[90vh] flex flex-col">
        {/* 헤더 */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
            데이터 접근 범위 설정
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {user.display_name || user.email}
          </p>
        </div>

        {/* 본문 */}
        <div className="px-6 py-4 overflow-y-auto flex-1">
          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-lg text-sm">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <>
              {/* 전체 접근 토글 */}
              <div className="mb-6 p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                <label className="flex items-center justify-between cursor-pointer">
                  <div>
                    <span className="font-medium text-purple-900 dark:text-purple-100">
                      전체 접근 (All Access)
                    </span>
                    <p className="text-sm text-purple-700 dark:text-purple-300 mt-1">
                      체크 시 모든 공장/라인 데이터에 접근 가능합니다
                    </p>
                  </div>
                  <button
                    onClick={toggleAllAccess}
                    className={`relative w-11 h-6 rounded-full transition-colors ${
                      scope.all_access ? 'bg-purple-600' : 'bg-slate-300 dark:bg-slate-600'
                    }`}
                  >
                    <div
                      className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                        scope.all_access ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </label>
              </div>

              {/* 개별 선택 (all_access가 false일 때만 활성화) */}
              <div className={scope.all_access ? 'opacity-50 pointer-events-none' : ''}>
                {/* 공장 코드 선택 */}
                <div className="mb-6">
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                      접근 가능 공장 ({scope.factory_codes.length}/{availableFactories.length})
                    </label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => selectAll('factory')}
                        className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        전체 선택
                      </button>
                      <button
                        onClick={() => clearAll('factory')}
                        className="text-xs text-slate-500 dark:text-slate-400 hover:underline"
                      >
                        전체 해제
                      </button>
                    </div>
                  </div>
                  {availableFactories.length === 0 ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400 p-3 bg-slate-50 dark:bg-slate-900 rounded-lg">
                      등록된 공장이 없습니다
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2 p-3 bg-slate-50 dark:bg-slate-900 rounded-lg max-h-32 overflow-y-auto">
                      {availableFactories.map((code) => (
                        <button
                          key={code}
                          onClick={() => toggleFactory(code)}
                          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                            scope.factory_codes.includes(code)
                              ? 'bg-blue-600 text-white'
                              : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-600'
                          }`}
                        >
                          {code}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* 라인 코드 선택 */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                      접근 가능 라인 ({scope.line_codes.length}/{availableLines.length})
                    </label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => selectAll('line')}
                        className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        전체 선택
                      </button>
                      <button
                        onClick={() => clearAll('line')}
                        className="text-xs text-slate-500 dark:text-slate-400 hover:underline"
                      >
                        전체 해제
                      </button>
                    </div>
                  </div>
                  {availableLines.length === 0 ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400 p-3 bg-slate-50 dark:bg-slate-900 rounded-lg">
                      등록된 라인이 없습니다. 센서 데이터를 먼저 업로드하세요.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2 p-3 bg-slate-50 dark:bg-slate-900 rounded-lg max-h-32 overflow-y-auto">
                      {availableLines.map((code) => (
                        <button
                          key={code}
                          onClick={() => toggleLine(code)}
                          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                            scope.line_codes.includes(code)
                              ? 'bg-green-600 text-white'
                              : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-600'
                          }`}
                        >
                          {code}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
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
            disabled={saving || loading}
            className="px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  );
}
