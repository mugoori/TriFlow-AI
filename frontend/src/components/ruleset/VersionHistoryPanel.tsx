/**
 * VersionHistoryPanel
 * 룰셋 버전 히스토리 표시 및 롤백 기능
 */

import { useState, useEffect, useCallback } from 'react';
import {
  History,
  RotateCcw,
  Eye,
  Trash2,
  ChevronDown,
  ChevronUp,
  Clock,
  AlertCircle,
  RefreshCw,
  X,
} from 'lucide-react';
import {
  listRulesetVersions,
  rollbackToVersion,
  deleteVersion,
  createVersionSnapshot,
  type RulesetVersion,
} from '@/services/rulesetVersionService';

interface VersionHistoryPanelProps {
  rulesetId: string;
  currentVersion: string;
  onRollback?: () => void;
}

export function VersionHistoryPanel({
  rulesetId,
  currentVersion,
  onRollback,
}: VersionHistoryPanelProps) {
  const [versions, setVersions] = useState<RulesetVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<RulesetVersion | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const loadVersions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listRulesetVersions(rulesetId, { limit: 20 });
      setVersions(response.versions);
    } catch (err) {
      console.error('Failed to load versions:', err);
      setError('버전 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [rulesetId]);

  useEffect(() => {
    if (expanded) {
      loadVersions();
    }
  }, [expanded, loadVersions]);

  const handleSaveSnapshot = async () => {
    setActionLoading(true);
    try {
      await createVersionSnapshot(rulesetId, '수동 스냅샷 저장');
      await loadVersions();
    } catch (err) {
      console.error('Failed to save snapshot:', err);
      setError('스냅샷 저장에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRollback = async (version: RulesetVersion) => {
    if (!confirm(`v${version.version_label}로 롤백하시겠습니까?\n현재 상태는 자동으로 저장됩니다.`)) {
      return;
    }

    setActionLoading(true);
    try {
      await rollbackToVersion(rulesetId, version.version_id);
      await loadVersions();
      onRollback?.();
    } catch (err) {
      console.error('Failed to rollback:', err);
      setError('롤백에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async (version: RulesetVersion) => {
    if (!confirm(`v${version.version_label} 버전을 삭제하시겠습니까?`)) {
      return;
    }

    setActionLoading(true);
    try {
      await deleteVersion(rulesetId, version.version_id);
      await loadVersions();
      if (selectedVersion?.version_id === version.version_id) {
        setSelectedVersion(null);
        setShowPreview(false);
      }
    } catch (err) {
      console.error('Failed to delete version:', err);
      setError('버전 삭제에 실패했습니다. (가장 최근 버전만 삭제 가능)');
    } finally {
      setActionLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
      {/* Header - Always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
      >
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-slate-500" />
          <span className="font-medium text-sm text-slate-700 dark:text-slate-300">
            버전 히스토리
          </span>
          <span className="text-xs text-slate-500">
            (현재: v{currentVersion})
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="p-3 bg-white dark:bg-slate-900">
          {/* Actions */}
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={handleSaveSnapshot}
              disabled={actionLoading}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors disabled:opacity-50"
            >
              {actionLoading ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : (
                <History className="w-3 h-3" />
              )}
              현재 상태 저장
            </button>
            <button
              onClick={loadVersions}
              disabled={loading}
              className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
              title="새로고침"
            >
              <RefreshCw className={`w-4 h-4 text-slate-400 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-2 mb-3 bg-red-50 dark:bg-red-900/20 rounded-lg text-sm text-red-600 dark:text-red-400">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          {/* Version List */}
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <RefreshCw className="w-5 h-5 text-slate-400 animate-spin" />
            </div>
          ) : versions.length === 0 ? (
            <div className="text-center py-4 text-sm text-slate-500">
              저장된 버전이 없습니다
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {versions.map((version, index) => (
                <div
                  key={version.version_id}
                  className={`p-2 rounded-lg border transition-colors ${
                    selectedVersion?.version_id === version.version_id
                      ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/20'
                      : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm text-slate-700 dark:text-slate-300">
                          v{version.version_label}
                        </span>
                        {index === 0 && (
                          <span className="px-1.5 py-0.5 text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded">
                            최신
                          </span>
                        )}
                      </div>
                      {version.change_summary && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">
                          {version.change_summary}
                        </p>
                      )}
                      <div className="flex items-center gap-1 text-xs text-slate-400 mt-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(version.created_at)}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1 ml-2">
                      <button
                        onClick={() => {
                          setSelectedVersion(version);
                          setShowPreview(true);
                        }}
                        className="p-1.5 rounded hover:bg-slate-200 dark:hover:bg-slate-700"
                        title="미리보기"
                      >
                        <Eye className="w-4 h-4 text-slate-400" />
                      </button>
                      <button
                        onClick={() => handleRollback(version)}
                        disabled={actionLoading}
                        className="p-1.5 rounded hover:bg-blue-100 dark:hover:bg-blue-900/30"
                        title="이 버전으로 롤백"
                      >
                        <RotateCcw className="w-4 h-4 text-blue-500" />
                      </button>
                      {index === 0 && versions.length > 1 && (
                        <button
                          onClick={() => handleDelete(version)}
                          disabled={actionLoading}
                          className="p-1.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30"
                          title="삭제"
                        >
                          <Trash2 className="w-4 h-4 text-red-400" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Preview Modal */}
      {showPreview && selectedVersion && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-900 rounded-lg w-full max-w-3xl max-h-[80vh] flex flex-col shadow-xl">
            <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
              <div>
                <h3 className="font-medium text-slate-900 dark:text-white">
                  버전 미리보기: v{selectedVersion.version_label}
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                  {selectedVersion.change_summary || '변경 사항 없음'}
                </p>
              </div>
              <button
                onClick={() => {
                  setShowPreview(false);
                  setSelectedVersion(null);
                }}
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              <pre className="text-sm font-mono bg-slate-900 text-slate-100 p-4 rounded-lg overflow-auto">
                {selectedVersion.rhai_script}
              </pre>
            </div>
            <div className="flex items-center justify-end gap-2 p-4 border-t border-slate-200 dark:border-slate-700">
              <button
                onClick={() => {
                  setShowPreview(false);
                  setSelectedVersion(null);
                }}
                className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
              >
                닫기
              </button>
              <button
                onClick={() => {
                  handleRollback(selectedVersion);
                  setShowPreview(false);
                }}
                disabled={actionLoading}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                <RotateCcw className="w-4 h-4" />
                이 버전으로 롤백
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
