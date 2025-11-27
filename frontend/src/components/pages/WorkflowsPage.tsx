/**
 * WorkflowsPage
 * 워크플로우 목록, 생성, 실행 관리 페이지
 */

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  GitBranch,
  Play,
  Pause,
  Trash2,
  Plus,
  RefreshCw,
  Search,
  CheckCircle,
  XCircle,
  Clock,
  Zap,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Settings,
} from 'lucide-react';
import {
  workflowService,
  type Workflow,
  type WorkflowInstance,
  type ActionCatalogItem,
} from '@/services/workflowService';

// 트리거 타입 한글 매핑
const triggerTypeLabels: Record<string, string> = {
  event: '이벤트',
  schedule: '스케줄',
  manual: '수동',
};

// 상태 아이콘 매핑
const statusIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  completed: CheckCircle,
  failed: XCircle,
  running: RefreshCw,
  pending: Clock,
};

// 상태 색상 매핑
const statusColors: Record<string, string> = {
  completed: 'text-green-600 bg-green-100 dark:bg-green-900/30',
  failed: 'text-red-600 bg-red-100 dark:bg-red-900/30',
  running: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30',
  pending: 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30',
};

export function WorkflowsPage() {
  // 상태
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filterActive, setFilterActive] = useState<boolean | undefined>(undefined);

  // 선택된 워크플로우 상세
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);
  const [instances, setInstances] = useState<WorkflowInstance[]>([]);
  const [loadingInstances, setLoadingInstances] = useState(false);

  // 액션 카탈로그
  const [showCatalog, setShowCatalog] = useState(false);
  const [actions, setActions] = useState<ActionCatalogItem[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState(false);

  // 워크플로우 목록 로드
  const loadWorkflows = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await workflowService.list({
        is_active: filterActive,
        search: search || undefined,
      });
      setWorkflows(response.workflows);
    } catch (err) {
      setError(err instanceof Error ? err.message : '워크플로우 로드 실패');
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  }, [search, filterActive]);

  // 초기 로드
  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  // 워크플로우 선택 시 실행 이력 로드
  const handleSelectWorkflow = async (workflow: Workflow) => {
    if (selectedWorkflow?.workflow_id === workflow.workflow_id) {
      setSelectedWorkflow(null);
      setInstances([]);
      return;
    }

    setSelectedWorkflow(workflow);
    setLoadingInstances(true);

    try {
      const response = await workflowService.getInstances(workflow.workflow_id);
      setInstances(response.instances);
    } catch (err) {
      console.error('Failed to load instances:', err);
      setInstances([]);
    } finally {
      setLoadingInstances(false);
    }
  };

  // 워크플로우 실행
  const handleRunWorkflow = async (workflow: Workflow, e: React.MouseEvent) => {
    e.stopPropagation();

    if (!workflow.is_active) {
      alert('비활성 워크플로우는 실행할 수 없습니다.');
      return;
    }

    try {
      const instance = await workflowService.run(workflow.workflow_id);
      alert(`워크플로우 실행 완료: ${instance.status}`);

      // 실행 이력 새로고침
      if (selectedWorkflow?.workflow_id === workflow.workflow_id) {
        const response = await workflowService.getInstances(workflow.workflow_id);
        setInstances(response.instances);
      }
    } catch (err) {
      alert(`실행 실패: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
    }
  };

  // 워크플로우 활성/비활성 토글
  const handleToggleActive = async (workflow: Workflow, e: React.MouseEvent) => {
    e.stopPropagation();

    try {
      await workflowService.update(workflow.workflow_id, {
        is_active: !workflow.is_active,
      });
      loadWorkflows();
    } catch (err) {
      alert(`상태 변경 실패: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
    }
  };

  // 워크플로우 삭제
  const handleDeleteWorkflow = async (workflow: Workflow, e: React.MouseEvent) => {
    e.stopPropagation();

    if (!confirm(`"${workflow.name}" 워크플로우를 삭제하시겠습니까?`)) {
      return;
    }

    try {
      await workflowService.delete(workflow.workflow_id);
      if (selectedWorkflow?.workflow_id === workflow.workflow_id) {
        setSelectedWorkflow(null);
        setInstances([]);
      }
      loadWorkflows();
    } catch (err) {
      alert(`삭제 실패: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
    }
  };

  // 액션 카탈로그 로드
  const handleShowCatalog = async () => {
    if (showCatalog) {
      setShowCatalog(false);
      return;
    }

    setShowCatalog(true);
    setLoadingCatalog(true);

    try {
      const response = await workflowService.getActionCatalog();
      setActions(response.actions);
    } catch (err) {
      console.error('Failed to load action catalog:', err);
      setActions([]);
    } finally {
      setLoadingCatalog(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 space-y-6">
        {/* 상단 컨트롤 */}
        <div className="flex flex-col sm:flex-row gap-4 justify-between">
          {/* 검색 및 필터 */}
          <div className="flex gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="워크플로우 검색..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 pr-4 py-2 w-64 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <select
              value={filterActive === undefined ? 'all' : filterActive.toString()}
              onChange={(e) => {
                const val = e.target.value;
                setFilterActive(val === 'all' ? undefined : val === 'true');
              }}
              className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
            >
              <option value="all">전체</option>
              <option value="true">활성</option>
              <option value="false">비활성</option>
            </select>
          </div>

          {/* 액션 버튼 */}
          <div className="flex gap-2">
            <button
              onClick={handleShowCatalog}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                showCatalog
                  ? 'bg-purple-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              <Settings className="w-4 h-4" />
              액션 카탈로그
            </button>
            <button
              onClick={loadWorkflows}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              새로고침
            </button>
            <button
              onClick={() => alert('AI Chat에서 "워크플로우 만들어줘"라고 요청하세요!')}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              새 워크플로우
            </button>
          </div>
        </div>

        {/* 액션 카탈로그 */}
        {showCatalog && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Zap className="w-5 h-5 text-purple-500" />
                사용 가능한 액션
              </CardTitle>
              <CardDescription>
                워크플로우에서 사용할 수 있는 액션 목록입니다
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loadingCatalog ? (
                <div className="text-center py-4">
                  <RefreshCw className="w-6 h-6 mx-auto animate-spin text-slate-400" />
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {actions.map((action) => (
                    <div
                      key={action.name}
                      className="p-3 border border-slate-200 dark:border-slate-700 rounded-lg"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="px-2 py-0.5 text-xs rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                          {action.category}
                        </span>
                        <span className="font-mono text-sm font-medium">{action.name}</span>
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-400">
                        {action.description}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* 워크플로우 목록 */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <GitBranch className="w-5 h-5 text-slate-600 dark:text-slate-400" />
              <CardTitle className="text-base">워크플로우</CardTitle>
              <span className="text-sm text-slate-500">({workflows.length}개)</span>
            </div>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="text-center py-8 text-red-500">
                <AlertCircle className="w-8 h-8 mx-auto mb-2" />
                <p>오류: {error}</p>
                <button onClick={loadWorkflows} className="mt-2 text-sm text-blue-600 hover:underline">
                  다시 시도
                </button>
              </div>
            ) : loading && workflows.length === 0 ? (
              <div className="text-center py-8 text-slate-500">
                <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
                <p>로딩 중...</p>
              </div>
            ) : workflows.length === 0 ? (
              <div className="text-center py-8 text-slate-500">
                <GitBranch className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p className="text-lg font-medium mb-2">워크플로우가 없습니다</p>
                <p className="text-sm">AI Chat에서 "워크플로우 만들어줘"라고 요청하세요</p>
              </div>
            ) : (
              <div className="border rounded-lg overflow-hidden dark:border-slate-700">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50 dark:bg-slate-800">
                      <TableHead className="w-8"></TableHead>
                      <TableHead className="font-semibold">이름</TableHead>
                      <TableHead className="font-semibold">트리거</TableHead>
                      <TableHead className="font-semibold">상태</TableHead>
                      <TableHead className="font-semibold">버전</TableHead>
                      <TableHead className="font-semibold">수정일</TableHead>
                      <TableHead className="font-semibold text-right">액션</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {workflows.map((workflow) => (
                      <>
                        <TableRow
                          key={workflow.workflow_id}
                          onClick={() => handleSelectWorkflow(workflow)}
                          className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        >
                          <TableCell>
                            {selectedWorkflow?.workflow_id === workflow.workflow_id ? (
                              <ChevronDown className="w-4 h-4 text-slate-400" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-slate-400" />
                            )}
                          </TableCell>
                          <TableCell>
                            <div>
                              <p className="font-medium">{workflow.name}</p>
                              {workflow.description && (
                                <p className="text-xs text-slate-500 truncate max-w-xs">
                                  {workflow.description}
                                </p>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <span className="px-2 py-1 text-xs rounded bg-slate-100 dark:bg-slate-800">
                              {triggerTypeLabels[workflow.dsl_definition.trigger.type] ||
                                workflow.dsl_definition.trigger.type}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span
                              className={`px-2 py-1 text-xs rounded ${
                                workflow.is_active
                                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                  : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                              }`}
                            >
                              {workflow.is_active ? '활성' : '비활성'}
                            </span>
                          </TableCell>
                          <TableCell className="font-mono text-sm">{workflow.version}</TableCell>
                          <TableCell className="text-sm text-slate-500">
                            {new Date(workflow.updated_at).toLocaleDateString('ko-KR')}
                          </TableCell>
                          <TableCell>
                            <div className="flex justify-end gap-1">
                              <button
                                onClick={(e) => handleRunWorkflow(workflow, e)}
                                disabled={!workflow.is_active}
                                className="p-1.5 rounded hover:bg-green-100 dark:hover:bg-green-900/30 disabled:opacity-50 disabled:cursor-not-allowed"
                                title="실행"
                              >
                                <Play className="w-4 h-4 text-green-600" />
                              </button>
                              <button
                                onClick={(e) => handleToggleActive(workflow, e)}
                                className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
                                title={workflow.is_active ? '비활성화' : '활성화'}
                              >
                                {workflow.is_active ? (
                                  <Pause className="w-4 h-4 text-yellow-600" />
                                ) : (
                                  <Play className="w-4 h-4 text-blue-600" />
                                )}
                              </button>
                              <button
                                onClick={(e) => handleDeleteWorkflow(workflow, e)}
                                className="p-1.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30"
                                title="삭제"
                              >
                                <Trash2 className="w-4 h-4 text-red-600" />
                              </button>
                            </div>
                          </TableCell>
                        </TableRow>

                        {/* 선택된 워크플로우 상세 */}
                        {selectedWorkflow?.workflow_id === workflow.workflow_id && (
                          <TableRow>
                            <TableCell colSpan={7} className="bg-slate-50 dark:bg-slate-800/50 p-0">
                              <div className="p-4 space-y-4">
                                {/* DSL 미리보기 */}
                                <div>
                                  <h4 className="text-sm font-semibold mb-2">워크플로우 구조</h4>
                                  <div className="flex flex-wrap gap-2">
                                    {workflow.dsl_definition.nodes.map((node, idx) => (
                                      <div
                                        key={node.id}
                                        className={`px-3 py-2 rounded-lg border ${
                                          node.type === 'condition'
                                            ? 'border-yellow-300 bg-yellow-50 dark:bg-yellow-900/20'
                                            : 'border-blue-300 bg-blue-50 dark:bg-blue-900/20'
                                        }`}
                                      >
                                        <div className="text-xs text-slate-500">
                                          {idx + 1}. {node.type === 'condition' ? '조건' : '액션'}
                                        </div>
                                        <div className="text-sm font-mono">
                                          {node.type === 'condition'
                                            ? (node.config as { condition?: string }).condition || node.id
                                            : (node.config as { action?: string }).action || node.id}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>

                                {/* 실행 이력 */}
                                <div>
                                  <h4 className="text-sm font-semibold mb-2">최근 실행 이력</h4>
                                  {loadingInstances ? (
                                    <div className="text-sm text-slate-500">로딩 중...</div>
                                  ) : instances.length === 0 ? (
                                    <div className="text-sm text-slate-500">실행 이력이 없습니다</div>
                                  ) : (
                                    <div className="space-y-2">
                                      {instances.slice(0, 5).map((instance) => {
                                        const StatusIcon = statusIcons[instance.status] || Clock;
                                        return (
                                          <div
                                            key={instance.instance_id}
                                            className="flex items-center gap-3 p-2 bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700"
                                          >
                                            <div className={`p-1 rounded ${statusColors[instance.status]}`}>
                                              <StatusIcon className="w-4 h-4" />
                                            </div>
                                            <div className="flex-1">
                                              <span className="text-sm font-medium capitalize">
                                                {instance.status}
                                              </span>
                                              <span className="text-xs text-slate-500 ml-2">
                                                {new Date(instance.started_at).toLocaleString('ko-KR')}
                                              </span>
                                            </div>
                                            {instance.error_message && (
                                              <span className="text-xs text-red-500 truncate max-w-xs">
                                                {instance.error_message}
                                              </span>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                      </>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
