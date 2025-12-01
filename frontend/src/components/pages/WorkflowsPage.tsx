/**
 * WorkflowsPage
 * 워크플로우 목록, 생성, 실행 관리 페이지
 */

import React, { useState, useEffect, useCallback } from 'react';
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
  Bell,
  Database,
  BarChart3,
  Filter,
  FlaskConical,
  ScrollText,
  Activity,
  Edit,
} from 'lucide-react';
import {
  workflowService,
  type Workflow,
  type WorkflowInstance,
  type ActionCatalogItem,
  type CategoryInfo,
  type ExecutionLog,
} from '@/services/workflowService';
import { ActionDetailModal } from '@/components/workflow/ActionDetailModal';
import { WorkflowEditor } from '@/components/workflow/WorkflowEditor';
import type { WorkflowDSL } from '@/services/workflowService';

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

// 카테고리별 아이콘 매핑
const categoryIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  notification: Bell,
  data: Database,
  control: Settings,
  analysis: BarChart3,
};

// 카테고리별 색상 매핑
const categoryColors: Record<string, string> = {
  notification: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 border-purple-200 dark:border-purple-800',
  data: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 border-blue-200 dark:border-blue-800',
  control: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400 border-orange-200 dark:border-orange-800',
  analysis: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 border-green-200 dark:border-green-800',
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
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // 액션 상세 모달
  const [selectedAction, setSelectedAction] = useState<ActionCatalogItem | null>(null);
  const [isActionModalOpen, setIsActionModalOpen] = useState(false);

  // 워크플로우 에디터
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingWorkflowDSL, setEditingWorkflowDSL] = useState<WorkflowDSL | undefined>(undefined);
  const [editingWorkflowId, setEditingWorkflowId] = useState<string | null>(null);

  // 시뮬레이션 테스트 패널
  const [showTestPanel, setShowTestPanel] = useState(false);
  const [testScenario, setTestScenario] = useState<'normal' | 'alert' | 'random'>('random');
  const [presetScenario, setPresetScenario] = useState<string>('');
  const [simulatedData, setSimulatedData] = useState<Record<string, unknown> | null>(null);
  const [testRunning, setTestRunning] = useState(false);
  const [testResult, setTestResult] = useState<WorkflowInstance | null>(null);

  // 실행 로그 패널
  const [showLogPanel, setShowLogPanel] = useState(false);
  const [executionLogs, setExecutionLogs] = useState<ExecutionLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);

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
      setCategories(response.categories);
    } catch (err) {
      console.error('Failed to load action catalog:', err);
      setActions([]);
      setCategories([]);
    } finally {
      setLoadingCatalog(false);
    }
  };

  // 카테고리 필터링된 액션 목록
  const filteredActions = selectedCategory
    ? actions.filter((a) => a.category === selectedCategory)
    : actions;

  // 액션 클릭 핸들러
  const handleActionClick = (action: ActionCatalogItem) => {
    setSelectedAction(action);
    setIsActionModalOpen(true);
  };

  // 카테고리 필터 토글
  const handleCategoryFilter = (category: string) => {
    setSelectedCategory(selectedCategory === category ? null : category);
  };


  // 시뮬레이션 데이터 생성
  const handleGenerateSimulatedData = async () => {
    try {
      const response = await workflowService.generateSimulatedData({
        scenario: testScenario,
        scenario_name: presetScenario || undefined,
      });
      setSimulatedData(response.data);
    } catch (err) {
      console.error('Failed to generate simulated data:', err);
    }
  };

  // 시뮬레이션 테스트 실행
  const handleRunWithSimulation = async (workflow: Workflow) => {
    if (!workflow.is_active) {
      alert('비활성 워크플로우는 실행할 수 없습니다.');
      return;
    }

    setTestRunning(true);
    setTestResult(null);

    try {
      const result = await workflowService.run(workflow.workflow_id, {
        use_simulated_data: !simulatedData,
        simulation_scenario: testScenario,
        input_data: simulatedData || undefined,
      });
      setTestResult(result);

      // 실행 이력 새로고침
      if (selectedWorkflow?.workflow_id === workflow.workflow_id) {
        const response = await workflowService.getInstances(workflow.workflow_id);
        setInstances(response.instances);
      }

      // 실행 로그 새로고침
      if (showLogPanel) {
        loadExecutionLogs();
      }
    } catch (err) {
      alert(`실행 실패: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
    } finally {
      setTestRunning(false);
    }
  };

  // 실행 로그 로드
  const loadExecutionLogs = async () => {
    setLoadingLogs(true);
    try {
      const response = await workflowService.getExecutionLogs({
        workflow_id: selectedWorkflow?.workflow_id,
        limit: 50,
      });
      setExecutionLogs(response.logs);
    } catch (err) {
      console.error('Failed to load execution logs:', err);
      setExecutionLogs([]);
    } finally {
      setLoadingLogs(false);
    }
  };

  // 실행 로그 패널 토글
  const handleToggleLogPanel = async () => {
    if (showLogPanel) {
      setShowLogPanel(false);
      return;
    }
    setShowLogPanel(true);
    await loadExecutionLogs();
  };

  // 실행 로그 초기화
  const handleClearLogs = async () => {
    if (!confirm('모든 실행 로그를 삭제하시겠습니까?')) return;
    try {
      await workflowService.clearExecutionLogs();
      setExecutionLogs([]);
    } catch (err) {
      console.error('Failed to clear logs:', err);
    }
  };

  // 워크플로우 저장
  const handleSaveWorkflow = async (dsl: WorkflowDSL) => {
    console.log('[WorkflowsPage] handleSaveWorkflow called');
    console.log('[WorkflowsPage] editingWorkflowId:', editingWorkflowId);
    console.log('[WorkflowsPage] DSL to save:', JSON.stringify(dsl, null, 2));

    try {
      if (editingWorkflowId) {
        // 편집 모드: DSL 업데이트
        console.log('[WorkflowsPage] Calling updateDSL...');
        const result = await workflowService.updateDSL(editingWorkflowId, dsl);
        console.log('[WorkflowsPage] updateDSL result:', result);
        alert('워크플로우가 수정되었습니다!');
      } else {
        // 생성 모드
        console.log('[WorkflowsPage] Calling create...');
        await workflowService.create({
          name: dsl.name,
          description: dsl.description,
          dsl_definition: dsl,
        });
        alert('워크플로우가 생성되었습니다!');
      }
      setIsEditorOpen(false);
      setEditingWorkflowId(null);
      setEditingWorkflowDSL(undefined);
      loadWorkflows();
    } catch (err) {
      console.error('[WorkflowsPage] Save error:', err);
      alert(`저장 실패: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
    }
  };

  // 워크플로우 편집 열기
  const handleEditWorkflow = (workflow: Workflow) => {
    console.log('[WorkflowsPage] handleEditWorkflow called, workflow_id:', workflow.workflow_id);
    setEditingWorkflowId(workflow.workflow_id);
    // 깊은 복사로 원본과 분리
    setEditingWorkflowDSL(JSON.parse(JSON.stringify(workflow.dsl_definition)));
    setIsEditorOpen(true);
  };

  // 새 워크플로우 생성 열기
  const handleNewWorkflow = () => {
    setEditingWorkflowId(null);
    setEditingWorkflowDSL(undefined);
    setIsEditorOpen(true);
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
              onClick={() => setShowTestPanel(!showTestPanel)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                showTestPanel
                  ? 'bg-green-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              <FlaskConical className="w-4 h-4" />
              시뮬레이션
            </button>
            <button
              onClick={handleToggleLogPanel}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                showLogPanel
                  ? 'bg-orange-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              <ScrollText className="w-4 h-4" />
              실행 로그
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
              onClick={handleNewWorkflow}
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
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Zap className="w-5 h-5 text-purple-500" />
                    액션 카탈로그
                    <span className="text-sm font-normal text-slate-500">
                      ({filteredActions.length}개)
                    </span>
                  </CardTitle>
                  <CardDescription>
                    워크플로우에서 사용할 수 있는 액션 목록입니다. 클릭하여 상세 정보를 확인하세요.
                  </CardDescription>
                </div>
              </div>

              {/* 카테고리 필터 */}
              {categories.length > 0 && (
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
                  <Filter className="w-4 h-4 text-slate-400" />
                  <span className="text-sm text-slate-500">필터:</span>
                  <div className="flex flex-wrap gap-2">
                    {categories.map((cat) => {
                      const CategoryIcon = categoryIcons[cat.name] || Zap;
                      const isSelected = selectedCategory === cat.name;
                      return (
                        <button
                          key={cat.name}
                          onClick={() => handleCategoryFilter(cat.name)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border transition-all ${
                            isSelected
                              ? categoryColors[cat.name]
                              : 'bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700'
                          }`}
                        >
                          <CategoryIcon className="w-3.5 h-3.5" />
                          {cat.display_name}
                          <span className="text-xs opacity-70">
                            ({actions.filter((a) => a.category === cat.name).length})
                          </span>
                        </button>
                      );
                    })}
                    {selectedCategory && (
                      <button
                        onClick={() => setSelectedCategory(null)}
                        className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                      >
                        초기화
                      </button>
                    )}
                  </div>
                </div>
              )}
            </CardHeader>
            <CardContent>
              {loadingCatalog ? (
                <div className="text-center py-8">
                  <RefreshCw className="w-8 h-8 mx-auto animate-spin text-slate-400" />
                  <p className="mt-2 text-sm text-slate-500">액션 목록을 불러오는 중...</p>
                </div>
              ) : filteredActions.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <Zap className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>해당 카테고리에 액션이 없습니다</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {filteredActions.map((action) => {
                    const CategoryIcon = categoryIcons[action.category] || Zap;
                    return (
                      <div
                        key={action.name}
                        onClick={() => handleActionClick(action)}
                        className={`p-4 border rounded-lg cursor-pointer transition-all hover:shadow-md hover:scale-[1.02] ${categoryColors[action.category]}`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="p-2 rounded-lg bg-white/50 dark:bg-slate-900/50">
                            <CategoryIcon className="w-5 h-5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4 className="text-sm font-semibold truncate">
                              {action.display_name}
                            </h4>
                            <p className="text-xs mt-0.5 opacity-80">
                              {action.category_display_name}
                            </p>
                          </div>
                        </div>
                        <p className="mt-2 text-sm line-clamp-2">
                          {action.description}
                        </p>
                        <div className="mt-2 flex items-center gap-1 text-xs opacity-70">
                          <span>파라미터: {Object.keys(action.parameters).length}개</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* 액션 상세 모달 */}
        <ActionDetailModal
          action={selectedAction}
          isOpen={isActionModalOpen}
          onClose={() => {
            setIsActionModalOpen(false);
            setSelectedAction(null);
          }}
        />

        {/* 시뮬레이션 테스트 패널 */}
        {showTestPanel && (
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <FlaskConical className="w-5 h-5 text-green-500" />
                    시뮬레이션 테스트
                  </CardTitle>
                  <CardDescription>
                    센서 데이터를 시뮬레이션하여 워크플로우를 테스트합니다.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 시뮬레이션 설정 */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">시나리오 타입</label>
                    <select
                      value={testScenario}
                      onChange={(e) => setTestScenario(e.target.value as 'normal' | 'alert' | 'random')}
                      className="w-full px-3 py-2 border rounded-lg bg-white dark:bg-slate-800 border-slate-300 dark:border-slate-600"
                    >
                      <option value="normal">정상 (Normal)</option>
                      <option value="alert">경고 (Alert)</option>
                      <option value="random">랜덤 (Random)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">사전 정의 시나리오</label>
                    <select
                      value={presetScenario}
                      onChange={(e) => setPresetScenario(e.target.value)}
                      className="w-full px-3 py-2 border rounded-lg bg-white dark:bg-slate-800 border-slate-300 dark:border-slate-600"
                    >
                      <option value="">선택 안 함</option>
                      <option value="high_temperature">고온 경고</option>
                      <option value="low_pressure">저압 경고</option>
                      <option value="equipment_error">장비 오류</option>
                      <option value="high_defect_rate">불량률 초과</option>
                      <option value="production_delay">생산 지연</option>
                      <option value="shift_change">교대 시간</option>
                      <option value="normal_operation">정상 가동</option>
                    </select>
                  </div>

                  <button
                    onClick={handleGenerateSimulatedData}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                  >
                    <Activity className="w-4 h-4" />
                    데이터 생성
                  </button>
                </div>

                {/* 생성된 데이터 미리보기 */}
                <div>
                  <label className="block text-sm font-medium mb-2">생성된 센서 데이터</label>
                  <div className="h-48 overflow-auto bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg p-3">
                    {simulatedData ? (
                      <pre className="text-xs font-mono whitespace-pre-wrap">
                        {JSON.stringify(simulatedData, null, 2)}
                      </pre>
                    ) : (
                      <div className="text-sm text-slate-500 text-center py-8">
                        &quot;데이터 생성&quot; 버튼을 클릭하여 시뮬레이션 데이터를 생성하세요
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* 테스트 결과 */}
              {testResult && (
                <div className="mt-4 p-4 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg">
                  <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                    <span className={testResult.status === 'completed' ? 'text-green-500' : 'text-red-500'}>
                      {testResult.status === 'completed' ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                    </span>
                    실행 결과: {testResult.status}
                  </h4>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-slate-500">실행 노드:</span>{' '}
                      <span className="font-medium">{(testResult.output_data as { nodes_executed?: number })?.nodes_executed || 0}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">스킵 노드:</span>{' '}
                      <span className="font-medium">{(testResult.output_data as { nodes_skipped?: number })?.nodes_skipped || 0}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">실행 시간:</span>{' '}
                      <span className="font-medium">{(testResult.output_data as { execution_time_ms?: number })?.execution_time_ms || 0}ms</span>
                    </div>
                  </div>
                  {testResult.error_message && (
                    <div className="mt-2 text-sm text-red-500">
                      오류: {testResult.error_message}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* 실행 로그 패널 */}
        {showLogPanel && (
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <ScrollText className="w-5 h-5 text-orange-500" />
                    실행 로그
                    <span className="text-sm font-normal text-slate-500">({executionLogs.length}개)</span>
                  </CardTitle>
                  <CardDescription>
                    워크플로우 실행 중 발생한 이벤트 로그입니다.
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={loadExecutionLogs}
                    disabled={loadingLogs}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-slate-100 dark:bg-slate-800 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loadingLogs ? 'animate-spin' : ''}`} />
                    새로고침
                  </button>
                  <button
                    onClick={handleClearLogs}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-red-100 dark:bg-red-900/30 text-red-600 rounded-lg hover:bg-red-200 dark:hover:bg-red-900/50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    초기화
                  </button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {loadingLogs ? (
                <div className="text-center py-8 text-slate-500">
                  <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
                  <p>로딩 중...</p>
                </div>
              ) : executionLogs.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <ScrollText className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>실행 로그가 없습니다</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {executionLogs.map((log) => (
                    <div
                      key={log.log_id}
                      className="p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 text-xs rounded ${
                            log.event_type === 'general' ? 'bg-slate-200 dark:bg-slate-700' :
                            log.event_type === 'database_save' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' :
                            log.event_type === 'production_line_stop' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' :
                            log.event_type === 'maintenance_triggered' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400' :
                            'bg-slate-200 dark:bg-slate-700'
                          }`}>
                            {log.event_type}
                          </span>
                          {log.node_id && (
                            <span className="text-xs text-slate-500">
                              노드: {log.node_id}
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-slate-400">
                          {new Date(log.timestamp).toLocaleString('ko-KR')}
                        </span>
                      </div>
                      {log.details && Object.keys(log.details).length > 0 && (
                        <div className="mt-2 text-xs font-mono text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 p-2 rounded overflow-x-auto">
                          {JSON.stringify(log.details, null, 2)}
                        </div>
                      )}
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
                      <React.Fragment key={workflow.workflow_id}>
                        <TableRow
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
                              {workflow.dsl_definition?.trigger?.type
                                ? (triggerTypeLabels[workflow.dsl_definition.trigger.type] ||
                                    workflow.dsl_definition.trigger.type)
                                : '-'}
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
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleEditWorkflow(workflow);
                                }}
                                className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700"
                                title="편집"
                              >
                                <Edit className="w-4 h-4 text-slate-600 dark:text-slate-400" />
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
                                {/* 시뮬레이션 테스트 버튼 */}
                                {showTestPanel && (
                                  <div className="mb-4">
                                    <button
                                      onClick={() => handleRunWithSimulation(workflow)}
                                      disabled={!workflow.is_active || testRunning}
                                      className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      <FlaskConical className={`w-4 h-4 ${testRunning ? 'animate-spin' : ''}`} />
                                      {testRunning ? '테스트 실행 중...' : '시뮬레이션으로 테스트 실행'}
                                    </button>
                                    {!workflow.is_active && (
                                      <p className="mt-1 text-xs text-yellow-600">워크플로우를 활성화하면 테스트할 수 있습니다.</p>
                                    )}
                                  </div>
                                )}

                                {/* DSL 미리보기 */}
                                <div>
                                  <h4 className="text-sm font-semibold mb-2">워크플로우 구조</h4>
                                  <div className="flex flex-wrap gap-2">
                                    {workflow.dsl_definition?.nodes?.length > 0 ? (
                                      workflow.dsl_definition.nodes.map((node, idx) => (
                                        <div
                                          key={node.id || idx}
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
                                              ? (node.config as { condition?: string })?.condition || node.id
                                              : (node.config as { action?: string })?.action || node.id}
                                          </div>
                                        </div>
                                      ))
                                    ) : (
                                      <span className="text-sm text-slate-500">노드 정보 없음</span>
                                    )}
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
                      </React.Fragment>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 워크플로우 에디터 */}
        <WorkflowEditor
          initialDSL={editingWorkflowDSL}
          isOpen={isEditorOpen}
          onSave={handleSaveWorkflow}
          onCancel={() => {
            setIsEditorOpen(false);
            setEditingWorkflowId(null);
            setEditingWorkflowDSL(undefined);
          }}
        />
      </div>
    </div>
  );
}
