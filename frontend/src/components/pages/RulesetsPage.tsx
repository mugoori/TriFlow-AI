/**
 * RulesetsPage
 * 룰셋 관리 페이지
 * - 룰셋 목록 조회/검색/필터
 * - 룰셋 생성/편집/삭제
 * - Rhai 스크립트 편집기 (Monaco Editor)
 * - 룰셋 테스트 실행
 */

import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  Plus,
  Search,
  FileCode,
  MoreVertical,
  Edit,
  Trash2,
  Play,
  RefreshCw,
  CheckCircle,
  XCircle,
  Code,
  Clock,
  ToggleLeft,
  ToggleRight,
  Sparkles,
  ListChecks,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { rulesetService, type Ruleset, type RulesetExecuteResponse } from '@/services/rulesetService';
import { RulesetEditorModal } from '@/components/ruleset/RulesetEditorModal';
import { ProposalsPanel } from '@/components/ruleset/ProposalsPanel';
import { VersionHistoryPanel } from '@/components/ruleset/VersionHistoryPanel';
import { useToast } from '@/components/ui/Toast';

interface RulesetsPageProps {
  highlightRulesetId?: string | null;
}

export function RulesetsPage({ highlightRulesetId }: RulesetsPageProps) {
  const { isAuthenticated } = useAuth();
  const toast = useToast();
  // Tab state
  const [activeTab, setActiveTab] = useState<'rulesets' | 'proposals'>('rulesets');

  // Data state
  const [rulesets, setRulesets] = useState<Ruleset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [filterActive, setFilterActive] = useState<boolean | undefined>(undefined);

  // Selected ruleset for detail view
  const [selectedRuleset, setSelectedRuleset] = useState<Ruleset | null>(null);

  // Modal state
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<'create' | 'edit'>('create');
  const [editingRuleset, setEditingRuleset] = useState<Ruleset | null>(null);

  // Dropdown menu state
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  // Quick test state
  const [quickTestInput, setQuickTestInput] = useState('{"temperature": 75}');
  const [quickTestResult, setQuickTestResult] = useState<RulesetExecuteResponse | null>(null);
  const [quickTestLoading, setQuickTestLoading] = useState(false);
  const [quickTestError, setQuickTestError] = useState<string | null>(null);

  // Handle ruleset created from proposals
  const handleRulesetCreatedFromProposal = (_rulesetId: string) => {
    setActiveTab('rulesets');
    loadRulesets();
  };

  // Load rulesets
  const loadRulesets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await rulesetService.list({
        is_active: filterActive,
        search: searchQuery || undefined,
      });
      setRulesets(response.rulesets);
    } catch (err) {
      console.error('Failed to load rulesets:', err);
      setError('룰셋 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [searchQuery, filterActive]);

  useEffect(() => {
    if (!isAuthenticated) return;
    loadRulesets();
  }, [isAuthenticated, loadRulesets]);

  // Highlight 된 룰셋 자동 선택
  useEffect(() => {
    if (highlightRulesetId && rulesets.length > 0) {
      const targetRuleset = rulesets.find(r => r.ruleset_id === highlightRulesetId);
      if (targetRuleset) {
        setSelectedRuleset(targetRuleset);
        setQuickTestResult(null);
        setQuickTestError(null);
      }
    }
  }, [highlightRulesetId, rulesets]);

  // Create new ruleset
  const handleCreate = () => {
    setEditorMode('create');
    setEditingRuleset(null);
    setEditorOpen(true);
  };

  // Edit ruleset
  const handleEdit = (ruleset: Ruleset) => {
    setEditorMode('edit');
    setEditingRuleset(ruleset);
    setEditorOpen(true);
    setOpenMenu(null);
  };

  // Delete ruleset
  const handleDelete = async (ruleset: Ruleset) => {
    const confirmed = await toast.confirm({
      title: '룰셋 삭제',
      message: `"${ruleset.name}" 룰셋을 삭제하시겠습니까?`,
      confirmText: '삭제',
      cancelText: '취소',
      variant: 'danger',
    });
    if (!confirmed) return;

    try {
      await rulesetService.delete(ruleset.ruleset_id);
      setRulesets((prev) => prev.filter((r) => r.ruleset_id !== ruleset.ruleset_id));
      if (selectedRuleset?.ruleset_id === ruleset.ruleset_id) {
        setSelectedRuleset(null);
      }
      toast.success(`"${ruleset.name}" 룰셋이 삭제되었습니다.`);
    } catch (err) {
      console.error('Failed to delete ruleset:', err);
      toast.error('룰셋 삭제에 실패했습니다.');
    }
    setOpenMenu(null);
  };

  // Toggle active status
  const handleToggleActive = async (ruleset: Ruleset) => {
    try {
      const updated = await rulesetService.update(ruleset.ruleset_id, {
        is_active: !ruleset.is_active,
      });
      setRulesets((prev) =>
        prev.map((r) => (r.ruleset_id === ruleset.ruleset_id ? updated : r))
      );
      if (selectedRuleset?.ruleset_id === ruleset.ruleset_id) {
        setSelectedRuleset(updated);
      }
      toast.success(`룰셋이 ${!ruleset.is_active ? '활성화' : '비활성화'}되었습니다.`);
    } catch (err) {
      console.error('Failed to toggle ruleset:', err);
      toast.error('룰셋 상태 변경에 실패했습니다.');
    }
    setOpenMenu(null);
  };

  // Handle save from editor modal
  const handleSaveRuleset = (savedRuleset: Ruleset) => {
    if (editorMode === 'create') {
      setRulesets((prev) => [savedRuleset, ...prev]);
    } else {
      setRulesets((prev) =>
        prev.map((r) => (r.ruleset_id === savedRuleset.ruleset_id ? savedRuleset : r))
      );
      if (selectedRuleset?.ruleset_id === savedRuleset.ruleset_id) {
        setSelectedRuleset(savedRuleset);
      }
    }
  };

  // Quick test execution
  const handleQuickTest = async () => {
    if (!selectedRuleset) return;

    let inputData: Record<string, unknown>;
    try {
      inputData = JSON.parse(quickTestInput);
    } catch {
      setQuickTestError('유효하지 않은 JSON 형식입니다.');
      return;
    }

    setQuickTestLoading(true);
    setQuickTestError(null);
    setQuickTestResult(null);

    try {
      const result = await rulesetService.execute(selectedRuleset.ruleset_id, { input_data: inputData });
      setQuickTestResult(result);
    } catch (err) {
      console.error('Failed to execute ruleset:', err);
      setQuickTestError('룰셋 실행에 실패했습니다.');
    } finally {
      setQuickTestLoading(false);
    }
  };

  // Format date
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // AI 제안 탭인 경우 전체 화면으로 ProposalsPanel 렌더링
  if (activeTab === 'proposals') {
    return (
      <div className="flex-1 flex flex-col overflow-hidden bg-slate-50 dark:bg-slate-950">
        {/* Tab Header */}
        <div className="p-4 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg w-fit">
            <button
              onClick={() => setActiveTab('rulesets')}
              className="flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            >
              <ListChecks className="w-4 h-4" />
              룰셋
            </button>
            <button
              onClick={() => setActiveTab('proposals')}
              className="flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors bg-white dark:bg-slate-700 text-purple-600 dark:text-purple-400 shadow-sm"
            >
              <Sparkles className="w-4 h-4" />
              AI 제안
            </button>
          </div>
        </div>
        {/* ProposalsPanel - 전체 화면 */}
        <ProposalsPanel onRulesetCreated={handleRulesetCreatedFromProposal} />

        {/* Editor Modal */}
        <RulesetEditorModal
          ruleset={editingRuleset}
          isOpen={editorOpen}
          onClose={() => setEditorOpen(false)}
          onSave={handleSaveRuleset}
          mode={editorMode}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 flex overflow-hidden bg-slate-50 dark:bg-slate-950">
      {/* Left Panel - Ruleset List */}
      <div className="w-96 border-r border-slate-200 dark:border-slate-800 flex flex-col bg-white dark:bg-slate-900">
        {/* Header */}
        <div className="p-4 border-b border-slate-200 dark:border-slate-700">
          {/* Tab Buttons */}
          <div className="flex items-center gap-1 mb-4 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
            <button
              onClick={() => setActiveTab('rulesets')}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-colors bg-white dark:bg-slate-700 text-amber-600 dark:text-amber-400 shadow-sm"
            >
              <ListChecks className="w-4 h-4" />
              룰셋
            </button>
            <button
              onClick={() => setActiveTab('proposals')}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-colors text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            >
              <Sparkles className="w-4 h-4" />
              AI 제안
            </button>
          </div>

          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold text-slate-900 dark:text-white">룰셋</h1>
            <button
              onClick={handleCreate}
              className="flex items-center gap-2 px-3 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              새 룰셋
            </button>
          </div>

          {/* Search */}
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="룰셋 검색..."
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent"
            />
          </div>

          {/* Filter */}
          <div className="flex gap-2">
            <button
              onClick={() => setFilterActive(undefined)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                filterActive === undefined
                  ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                  : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              전체
            </button>
            <button
              onClick={() => setFilterActive(true)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                filterActive === true
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                  : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              활성
            </button>
            <button
              onClick={() => setFilterActive(false)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                filterActive === false
                  ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                  : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              비활성
            </button>
            <button
              onClick={loadRulesets}
              className="ml-auto p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title="새로고침"
            >
              <RefreshCw className="w-4 h-4 text-slate-500" />
            </button>
          </div>
        </div>

        {/* Ruleset List */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <RefreshCw className="w-6 h-6 text-slate-400 animate-spin" />
            </div>
          ) : error ? (
            <div className="p-4 text-center text-red-500">{error}</div>
          ) : rulesets.length === 0 ? (
            <div className="p-8 text-center">
              <FileCode className="w-12 h-12 mx-auto mb-3 text-slate-300 dark:text-slate-600" />
              <p className="text-slate-500 dark:text-slate-400">룰셋이 없습니다</p>
              <button
                onClick={handleCreate}
                className="mt-3 text-amber-600 hover:text-amber-700 text-sm"
              >
                첫 번째 룰셋 만들기
              </button>
            </div>
          ) : (
            <div className="divide-y divide-slate-200 dark:divide-slate-700">
              {rulesets.map((ruleset) => {
                const isHighlighted = highlightRulesetId === ruleset.ruleset_id;
                return (
                <div
                  key={ruleset.ruleset_id}
                  onClick={() => {
                    setSelectedRuleset(ruleset);
                    setQuickTestResult(null);
                    setQuickTestError(null);
                  }}
                  className={`p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-all ${
                    selectedRuleset?.ruleset_id === ruleset.ruleset_id
                      ? 'bg-amber-50 dark:bg-amber-900/20 border-l-4 border-amber-500'
                      : ''
                  } ${
                    isHighlighted
                      ? 'ring-2 ring-purple-500 ring-inset animate-pulse bg-purple-50 dark:bg-purple-900/20'
                      : ''
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-900 dark:text-white truncate">
                          {ruleset.name}
                        </span>
                        {isHighlighted && (
                          <span className="flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300 rounded-full">
                            <Sparkles className="w-3 h-3" />
                            방금 생성됨
                          </span>
                        )}
                        {ruleset.is_active ? (
                          <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                        ) : (
                          <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                        )}
                      </div>
                      {ruleset.description && (
                        <p className="text-sm text-slate-500 dark:text-slate-400 truncate mt-1">
                          {ruleset.description}
                        </p>
                      )}
                      <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
                        <span className="flex items-center gap-1">
                          <Code className="w-3 h-3" />
                          v{ruleset.version}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatDate(ruleset.updated_at)}
                        </span>
                      </div>
                    </div>

                    {/* Actions Menu */}
                    <div className="relative">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenu(openMenu === ruleset.ruleset_id ? null : ruleset.ruleset_id);
                        }}
                        className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700"
                      >
                        <MoreVertical className="w-4 h-4 text-slate-400" />
                      </button>
                      {openMenu === ruleset.ruleset_id && (
                        <div className="absolute right-0 top-full mt-1 w-40 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 z-10">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEdit(ruleset);
                            }}
                            className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2 text-slate-700 dark:text-slate-200"
                          >
                            <Edit className="w-4 h-4" />
                            편집
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleToggleActive(ruleset);
                            }}
                            className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2 text-slate-700 dark:text-slate-200"
                          >
                            {ruleset.is_active ? (
                              <>
                                <ToggleLeft className="w-4 h-4" />
                                비활성화
                              </>
                            ) : (
                              <>
                                <ToggleRight className="w-4 h-4" />
                                활성화
                              </>
                            )}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(ruleset);
                            }}
                            className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2 text-red-500"
                          >
                            <Trash2 className="w-4 h-4" />
                            삭제
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Right Panel - Detail View */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedRuleset ? (
          <>
            {/* Detail Header */}
            <div className="p-4 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                    {selectedRuleset.name}
                  </h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    {selectedRuleset.description || '설명 없음'}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`px-3 py-1 text-sm rounded-full ${
                      selectedRuleset.is_active
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                    }`}
                  >
                    {selectedRuleset.is_active ? '활성' : '비활성'}
                  </span>
                  <button
                    onClick={() => handleEdit(selectedRuleset)}
                    className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors"
                  >
                    <Edit className="w-4 h-4" />
                    편집
                  </button>
                </div>
              </div>
            </div>

            {/* Script Preview & Test */}
            <div className="flex-1 flex overflow-hidden">
              {/* Script Preview */}
              <div className="flex-1 p-4 overflow-auto">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Code className="w-4 h-4" />
                      Rhai 스크립트
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="text-sm font-mono bg-slate-900 text-slate-100 p-4 rounded-lg overflow-auto max-h-96">
                      {selectedRuleset.rhai_script}
                    </pre>
                    <div className="flex items-center gap-4 mt-3 text-sm text-slate-500">
                      <span>버전: {selectedRuleset.version}</span>
                      <span>생성: {formatDate(selectedRuleset.created_at)}</span>
                      <span>수정: {formatDate(selectedRuleset.updated_at)}</span>
                    </div>
                  </CardContent>
                </Card>

                {/* Version History Panel */}
                <div className="mt-4">
                  <VersionHistoryPanel
                    rulesetId={selectedRuleset.ruleset_id}
                    currentVersion={selectedRuleset.version}
                    onRollback={async () => {
                      // 롤백 후 룰셋 다시 로드
                      try {
                        const updated = await rulesetService.get(selectedRuleset.ruleset_id);
                        setSelectedRuleset(updated);
                        setRulesets((prev) =>
                          prev.map((r) => (r.ruleset_id === updated.ruleset_id ? updated : r))
                        );
                      } catch (err) {
                        console.error('Failed to refresh ruleset:', err);
                      }
                    }}
                  />
                </div>
              </div>

              {/* Quick Test Panel */}
              <div className="w-80 border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 flex flex-col">
                <h3 className="font-medium text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <Play className="w-4 h-4" />
                  빠른 테스트
                </h3>

                <div className="space-y-3 flex-1">
                  <div>
                    <label className="block text-sm text-slate-600 dark:text-slate-400 mb-1">
                      입력 데이터 (JSON)
                    </label>
                    <textarea
                      value={quickTestInput}
                      onChange={(e) => setQuickTestInput(e.target.value)}
                      placeholder='{"temperature": 75}'
                      className="w-full h-32 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-mono text-sm focus:ring-2 focus:ring-amber-500 focus:border-transparent resize-none"
                    />
                  </div>

                  <button
                    onClick={handleQuickTest}
                    disabled={quickTestLoading || !selectedRuleset.is_active}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {quickTestLoading ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                    테스트 실행
                  </button>

                  {!selectedRuleset.is_active && (
                    <p className="text-xs text-slate-500 dark:text-slate-400 text-center">
                      * 비활성 룰셋은 실행할 수 없습니다.
                    </p>
                  )}

                  {/* Test Result */}
                  {quickTestError && (
                    <div className="p-3 bg-red-50 dark:bg-red-900/30 rounded-lg">
                      <p className="text-sm text-red-600 dark:text-red-400">{quickTestError}</p>
                    </div>
                  )}

                  {quickTestResult && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-sm">
                        <CheckCircle className="w-4 h-4 text-green-500" />
                        <span className="text-slate-600 dark:text-slate-400">
                          실행 완료 ({quickTestResult.execution_time_ms}ms)
                        </span>
                      </div>
                      <div>
                        <label className="block text-sm text-slate-600 dark:text-slate-400 mb-1">
                          결과
                        </label>
                        <pre className="text-xs font-mono bg-slate-100 dark:bg-slate-800 p-2 rounded overflow-auto max-h-48">
                          {JSON.stringify(quickTestResult.output_data, null, 2)}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-slate-50 dark:bg-slate-950">
            <div className="text-center">
              <FileCode className="w-16 h-16 mx-auto mb-4 text-slate-300 dark:text-slate-600" />
              <p className="text-lg text-slate-500 dark:text-slate-400">
                룰셋을 선택하여 상세 정보를 확인하세요
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Editor Modal */}
      <RulesetEditorModal
        ruleset={editingRuleset}
        isOpen={editorOpen}
        onClose={() => setEditorOpen(false)}
        onSave={handleSaveRuleset}
        mode={editorMode}
      />

      {/* Click outside to close menu */}
      {openMenu && (
        <div
          className="fixed inset-0 z-0"
          onClick={() => setOpenMenu(null)}
        />
      )}
    </div>
  );
}
