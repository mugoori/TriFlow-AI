/**
 * Version Panel Component
 * 워크플로우 버전 관리 UI
 */

import { useState, useEffect, useCallback } from 'react';
import {
  History,
  GitBranch,
  Tag,
  Clock,
  CheckCircle,
  Archive,
  AlertTriangle,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Play,
  RotateCcw,
  Trash2,
  Plus,
  FileText,
  User,
} from 'lucide-react';
import { workflowService, WorkflowVersion } from '../../services/workflowService';

interface VersionPanelProps {
  workflowId: string;
  workflowName?: string;
  currentVersion?: string;
  onVersionChange?: () => void;
  className?: string;
}

const statusLabels: Record<string, string> = {
  draft: '초안',
  active: '활성',
  deprecated: '비권장',
  archived: '보관됨',
};

const statusColors: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  deprecated: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  archived: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
};

const statusIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  draft: FileText,
  active: CheckCircle,
  deprecated: AlertTriangle,
  archived: Archive,
};

export function VersionPanel({
  workflowId,
  workflowName,
  currentVersion,
  onVersionChange,
  className = '',
}: VersionPanelProps) {
  const [versions, setVersions] = useState<WorkflowVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedVersion, setExpandedVersion] = useState<number | null>(null);
  const [processing, setProcessing] = useState<number | null>(null);

  // 새 버전 생성 상태
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [changeLog, setChangeLog] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchVersions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await workflowService.listVersions(workflowId);
      setVersions(response.versions);
    } catch (err) {
      console.error('Failed to fetch versions:', err);
      setError('버전 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  useEffect(() => {
    if (workflowId) {
      fetchVersions();
    }
  }, [workflowId, fetchVersions]);

  const handleCreateVersion = async () => {
    if (!changeLog.trim()) {
      setError('변경 로그를 입력해주세요.');
      return;
    }

    try {
      setCreating(true);
      await workflowService.createVersion(workflowId, changeLog);
      setChangeLog('');
      setShowCreateForm(false);
      await fetchVersions();
      onVersionChange?.();
    } catch (err) {
      console.error('Failed to create version:', err);
      setError('버전 생성에 실패했습니다.');
    } finally {
      setCreating(false);
    }
  };

  const handlePublish = async (version: number) => {
    try {
      setProcessing(version);
      await workflowService.publishVersion(workflowId, version);
      await fetchVersions();
      onVersionChange?.();
    } catch (err) {
      console.error('Failed to publish version:', err);
      setError('버전 배포에 실패했습니다.');
    } finally {
      setProcessing(null);
    }
  };

  const handleRollback = async (version: number) => {
    const confirmed = window.confirm(
      `버전 ${version}으로 롤백하시겠습니까?\n현재 DSL이 해당 버전으로 복원됩니다.`
    );
    if (!confirmed) return;

    try {
      setProcessing(version);
      await workflowService.rollbackVersion(workflowId, version);
      await fetchVersions();
      onVersionChange?.();
    } catch (err) {
      console.error('Failed to rollback version:', err);
      setError('버전 롤백에 실패했습니다.');
    } finally {
      setProcessing(null);
    }
  };

  const handleDelete = async (version: number) => {
    const confirmed = window.confirm(
      `버전 ${version}을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.`
    );
    if (!confirmed) return;

    try {
      setProcessing(version);
      await workflowService.deleteVersion(workflowId, version);
      await fetchVersions();
    } catch (err) {
      console.error('Failed to delete version:', err);
      setError('버전 삭제에 실패했습니다.');
    } finally {
      setProcessing(null);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading && versions.length === 0) {
    return (
      <div className={`bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 ${className}`}>
        <div className="p-4 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
          <span className="ml-2 text-sm text-slate-600 dark:text-slate-400">로딩 중...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-blue-500" />
          <h3 className="font-semibold text-slate-900 dark:text-slate-100">버전 관리</h3>
          {workflowName && (
            <span className="text-sm text-slate-500 dark:text-slate-400">
              - {workflowName}
            </span>
          )}
          {currentVersion && (
            <span className="bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium px-2 py-0.5 rounded-full">
              v{currentVersion}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            새 버전
          </button>
          <button
            onClick={fetchVersions}
            disabled={loading}
            className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
            title="새로고침"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Create Version Form */}
      {showCreateForm && (
        <div className="p-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              변경 로그
            </label>
            <textarea
              value={changeLog}
              onChange={(e) => setChangeLog(e.target.value)}
              placeholder="이 버전에서 변경된 내용을 설명하세요..."
              className="w-full px-3 py-2 text-sm border rounded dark:bg-slate-800 dark:border-slate-600 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              rows={2}
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowCreateForm(false);
                  setChangeLog('');
                }}
                className="px-3 py-1.5 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
              >
                취소
              </button>
              <button
                onClick={handleCreateVersion}
                disabled={creating || !changeLog.trim()}
                className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors disabled:opacity-50"
              >
                {creating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Tag className="w-4 h-4" />
                )}
                버전 생성
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="m-3 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-600 dark:text-red-400">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 text-red-500 hover:text-red-700"
          >
            ✕
          </button>
        </div>
      )}

      {/* Version List */}
      <div className="max-h-[400px] overflow-y-auto">
        {versions.length === 0 ? (
          <div className="p-6 text-center text-slate-500 dark:text-slate-400">
            <GitBranch className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">저장된 버전이 없습니다.</p>
            <p className="text-xs mt-1">새 버전을 생성하여 현재 상태를 저장하세요.</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-200 dark:divide-slate-700">
            {versions.map((version) => {
              const StatusIcon = statusIcons[version.status] || FileText;
              const isExpanded = expandedVersion === version.version;
              const isProcessing = processing === version.version;

              return (
                <li key={version.version_id} className="p-3">
                  {/* Summary Row */}
                  <div
                    className="flex items-start justify-between cursor-pointer"
                    onClick={() => setExpandedVersion(isExpanded ? null : version.version)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Tag className="w-4 h-4 text-slate-400" />
                        <span className="font-medium text-sm text-slate-900 dark:text-slate-100">
                          v{version.version}
                        </span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${statusColors[version.status]}`}>
                          {statusLabels[version.status] || version.status}
                        </span>
                        {version.status === 'active' && (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        )}
                      </div>
                      {version.change_log && (
                        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400 truncate">
                          {version.change_log}
                        </p>
                      )}
                      <div className="mt-1 flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatDate(version.created_at)}
                        </span>
                        {version.created_by && (
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {version.created_by}
                          </span>
                        )}
                      </div>
                    </div>
                    <button className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </button>
                  </div>

                  {/* Expanded Detail */}
                  {isExpanded && (
                    <div className="mt-3 space-y-3">
                      {/* Version Info */}
                      <div className="p-2 bg-slate-50 dark:bg-slate-900 rounded text-sm">
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="text-slate-500 dark:text-slate-400">버전 ID:</span>{' '}
                            <span className="font-mono text-slate-700 dark:text-slate-300">
                              {version.version_id.slice(0, 8)}...
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 dark:text-slate-400">상태:</span>{' '}
                            <span className={`inline-flex items-center gap-1 ${
                              version.status === 'active' ? 'text-green-600' : 'text-slate-700 dark:text-slate-300'
                            }`}>
                              <StatusIcon className="w-3 h-3" />
                              {statusLabels[version.status]}
                            </span>
                          </div>
                          {version.published_at && (
                            <div className="col-span-2">
                              <span className="text-slate-500 dark:text-slate-400">배포일:</span>{' '}
                              <span className="text-slate-700 dark:text-slate-300">
                                {formatDate(version.published_at)}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Change Log */}
                      {version.change_log && (
                        <div className="p-2 bg-slate-50 dark:bg-slate-900 rounded">
                          <p className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                            변경 로그
                          </p>
                          <p className="text-sm text-slate-700 dark:text-slate-300">
                            {version.change_log}
                          </p>
                        </div>
                      )}

                      {/* Action Buttons */}
                      <div className="flex gap-2">
                        {version.status === 'draft' && (
                          <button
                            onClick={() => handlePublish(version.version)}
                            disabled={isProcessing}
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded transition-colors disabled:opacity-50"
                          >
                            {isProcessing ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Play className="w-4 h-4" />
                            )}
                            배포
                          </button>
                        )}
                        {version.status !== 'active' && (
                          <button
                            onClick={() => handleRollback(version.version)}
                            disabled={isProcessing}
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded transition-colors disabled:opacity-50"
                          >
                            {isProcessing ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <RotateCcw className="w-4 h-4" />
                            )}
                            롤백
                          </button>
                        )}
                        {version.status !== 'active' && (
                          <button
                            onClick={() => handleDelete(version.version)}
                            disabled={isProcessing}
                            className="flex items-center justify-center gap-1 px-3 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded transition-colors disabled:opacity-50"
                          >
                            {isProcessing ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

export default VersionPanel;
