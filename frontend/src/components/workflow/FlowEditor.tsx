/**
 * FlowEditor
 * React Flow 기반 드래그 앤 드롭 워크플로우 에디터
 */

import { useCallback, useMemo, useState, useEffect, useRef, type DragEvent } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  Handle,
  Position,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
  Panel,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Save,
  X,
  Play,
  Eye,
  GitBranch,
  AlertTriangle,
  Zap,
  Split,
  Repeat,
  Layers,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  SkipForward,
  Trash2,
  // P1 노드 아이콘
  Database,
  Brain,
  BarChart3,
  Plug,
  Pause,
  UserCheck,
  // P2 노드 아이콘
  Undo2,
  Rocket,
  RotateCcw,
  FlaskConical,
  // 추가 노드 아이콘
  Code,
  // 설정 관련
  Settings,
  Tag,
  Timer,
  RefreshCw,
} from 'lucide-react';
import type { WorkflowDSL, WorkflowNode, WorkflowInstance } from '@/services/workflowService';
import { workflowService } from '@/services/workflowService';
import {
  IfElseBranchEditor,
  LoopNodeEditor,
  ParallelBranchEditor,
  type InnerNode,
} from './BranchNodeEditor';
import { ConditionBuilder } from './ConditionBuilder';
import { ActionParameterForm } from './ActionParameterForm';
import { useToast } from '@/components/ui/Toast';

// ============ Types ============

interface FlowEditorProps {
  initialDSL?: WorkflowDSL;
  workflowId?: string; // 기존 워크플로우 편집 시 ID
  onSave?: (dsl: WorkflowDSL) => Promise<string | void>; // 저장 후 workflow_id 반환 가능
  onCancel?: () => void;
  isOpen: boolean;
}

// 노드 실행 상태
type NodeExecutionStatus = 'idle' | 'executing' | 'completed' | 'failed' | 'skipped';

// 노드 타입 (trigger 포함)
type NodeType = WorkflowNode['type'] | 'trigger';

// 브랜치 타입 (중첩 노드 추적용)
type BranchType = 'then' | 'else' | 'loop' | 'parallel';

// 커스텀 노드 데이터 타입 (index signature 추가)
interface CustomNodeData {
  label: string;
  nodeType: NodeType;
  config: Record<string, unknown>;
  executionStatus?: NodeExecutionStatus;
  // 중첩 노드 메타데이터
  _parentId?: string;
  _branchType?: BranchType;
  _depth?: number;
  [key: string]: unknown;
}

// ============ Constants ============

const nodeTypeColors: Record<string, { bg: string; border: string; text: string }> = {
  // P0 기본 노드
  condition: { bg: 'bg-yellow-100 dark:bg-yellow-900/30', border: 'border-yellow-600', text: 'text-yellow-900 dark:text-yellow-200' },
  action: { bg: 'bg-blue-100 dark:bg-blue-900/30', border: 'border-blue-600', text: 'text-blue-900 dark:text-blue-200' },
  if_else: { bg: 'bg-purple-100 dark:bg-purple-900/30', border: 'border-purple-600', text: 'text-purple-900 dark:text-purple-200' },
  loop: { bg: 'bg-green-100 dark:bg-green-900/30', border: 'border-green-600', text: 'text-green-900 dark:text-green-200' },
  parallel: { bg: 'bg-orange-100 dark:bg-orange-900/30', border: 'border-orange-600', text: 'text-orange-900 dark:text-orange-200' },
  trigger: { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-600', text: 'text-emerald-900 dark:text-emerald-200' },
  // P1 비즈니스 노드
  data: { bg: 'bg-cyan-100 dark:bg-cyan-900/30', border: 'border-cyan-600', text: 'text-cyan-900 dark:text-cyan-200' },
  judgment: { bg: 'bg-indigo-100 dark:bg-indigo-900/30', border: 'border-indigo-600', text: 'text-indigo-900 dark:text-indigo-200' },
  bi: { bg: 'bg-pink-100 dark:bg-pink-900/30', border: 'border-pink-600', text: 'text-pink-900 dark:text-pink-200' },
  mcp: { bg: 'bg-violet-100 dark:bg-violet-900/30', border: 'border-violet-600', text: 'text-violet-900 dark:text-violet-200' },
  wait: { bg: 'bg-slate-100 dark:bg-slate-900/30', border: 'border-slate-600', text: 'text-slate-900 dark:text-slate-200' },
  approval: { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-600', text: 'text-amber-900 dark:text-amber-200' },
  // P2 고급 노드
  compensation: { bg: 'bg-rose-100 dark:bg-rose-900/30', border: 'border-rose-600', text: 'text-rose-900 dark:text-rose-200' },
  deploy: { bg: 'bg-teal-100 dark:bg-teal-900/30', border: 'border-teal-600', text: 'text-teal-900 dark:text-teal-200' },
  rollback: { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-600', text: 'text-red-900 dark:text-red-200' },
  simulate: { bg: 'bg-fuchsia-100 dark:bg-fuchsia-900/30', border: 'border-fuchsia-600', text: 'text-fuchsia-900 dark:text-fuchsia-200' },
  // 추가 노드
  switch: { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-600', text: 'text-amber-900 dark:text-amber-200' },
  code: { bg: 'bg-gray-100 dark:bg-gray-900/30', border: 'border-gray-600', text: 'text-gray-900 dark:text-gray-200' },
};

const nodeTypeLabels: Record<string, string> = {
  // P0 기본 노드
  condition: '조건',
  action: '액션',
  if_else: 'If/Else',
  loop: '반복',
  parallel: '병렬',
  trigger: '트리거',
  // P1 비즈니스 노드
  data: '데이터',
  judgment: '판정',
  bi: 'BI 분석',
  mcp: 'MCP 도구',
  wait: '대기',
  approval: '승인',
  // P2 고급 노드
  compensation: '보상',
  deploy: '배포',
  rollback: '롤백',
  simulate: '시뮬레이션',
  // 추가 노드
  switch: '다중분기',
  code: '코드실행',
};

const nodeTypeIcons: Record<string, typeof AlertTriangle> = {
  // P0 기본 노드
  condition: AlertTriangle,
  action: Zap,
  if_else: Split,
  loop: Repeat,
  parallel: Layers,
  trigger: Play,
  // P1 비즈니스 노드
  data: Database,
  judgment: Brain,
  bi: BarChart3,
  mcp: Plug,
  wait: Pause,
  approval: UserCheck,
  // P2 고급 노드
  compensation: Undo2,
  deploy: Rocket,
  rollback: RotateCcw,
  simulate: FlaskConical,
  // 추가 노드
  switch: GitBranch,
  code: Code,
};

// 액션 한글 이름 매핑
const actionLabels: Record<string, string> = {
  // 알림 관련
  send_slack_notification: 'Slack 알림',
  slack_notification: 'Slack 알림',
  send_email: '이메일 발송',
  email: '이메일 발송',
  send_sms: 'SMS 발송',
  sms: 'SMS 발송',
  // 데이터 관련
  save_to_database: 'DB 저장',
  export_to_csv: 'CSV 내보내기',
  log_event: '로그 기록',
  log: '로그 기록',
  // 제어 관련
  stop_production_line: '라인 정지',
  stop_line: '라인 정지',
  adjust_sensor_threshold: '임계값 조정',
  trigger_maintenance: '유지보수 요청',
  maintenance: '유지보수 요청',
  // 분석 관련
  calculate_defect_rate: '불량률 계산',
  analyze_sensor_trend: '추세 분석',
  predict_equipment_failure: '고장 예측',
  // 기타 (AI 생성 DSL 호환)
  call_api: 'API 호출',
  webhook: '웹훅 호출',
};

// 실행 상태별 스타일
const executionStatusStyles: Record<NodeExecutionStatus, { ring: string; icon: typeof CheckCircle | null; animate: boolean }> = {
  idle: { ring: '', icon: null, animate: false },
  executing: { ring: 'ring-2 ring-blue-500 ring-offset-2', icon: Loader2, animate: true },
  completed: { ring: 'ring-2 ring-green-500 ring-offset-2', icon: CheckCircle, animate: false },
  failed: { ring: 'ring-2 ring-red-500 ring-offset-2', icon: XCircle, animate: false },
  skipped: { ring: 'ring-2 ring-gray-400 ring-offset-2', icon: SkipForward, animate: false },
};

// ============ Custom Node Component ============

function CustomNode({ data, selected }: { data: CustomNodeData; selected?: boolean }) {
  const colors = nodeTypeColors[data.nodeType] || nodeTypeColors.action;
  const Icon = nodeTypeIcons[data.nodeType] || Zap;
  const isTrigger = data.nodeType === 'trigger';
  const execStatus = data.executionStatus || 'idle';
  const execStyle = executionStatusStyles[execStatus];
  const StatusIcon = execStyle.icon;

  // 노드 요약 텍스트 생성
  const getSummary = () => {
    const config = data.config;
    switch (data.nodeType) {
      // P0 기본 노드
      case 'condition':
        return (config.condition as string) || '조건 미설정';
      case 'action': {
        // action_type 또는 action 키 모두 지원 (AI 생성 DSL 호환)
        const actionKey = (config.action_type as string) || (config.action as string) || '';
        return actionLabels[actionKey] || actionKey || '액션 미설정';
      }
      case 'if_else': {
        const cond = config.condition;
        if (typeof cond === 'string') return cond || 'If/Else';
        if (cond && typeof cond === 'object') {
          const { field, operator, value } = cond as { field?: string; operator?: string; value?: unknown };
          if (field && operator && value !== undefined) {
            return `${field} ${operator} ${value}`;
          }
        }
        return 'If/Else';
      }
      case 'loop': {
        const loopType = config.loop_type as string;
        if (loopType === 'for') return `${config.count || 1}회 반복`;
        return `조건 반복`;
      }
      case 'parallel': {
        const branches = config.branches as unknown[][];
        return `${branches?.length || 0}개 브랜치`;
      }
      case 'trigger':
        return (config.type as string) === 'manual' ? '수동 실행' : (config.type as string) || '트리거';
      // P1 비즈니스 노드
      case 'data': {
        const sourceType = config.source_type as string;
        if (sourceType === 'sensor') return '센서 데이터';
        if (sourceType === 'connector') return (config.connection as string) || '커넥터';
        if (sourceType === 'api') return (config.url as string)?.slice(0, 20) || 'API';
        return '데이터 조회';
      }
      case 'judgment': {
        const policyType = (config.policy as Record<string, unknown>)?.type as string;
        if (policyType === 'RULE_ONLY') return '룰 기반 판정';
        if (policyType === 'LLM_ONLY') return 'LLM 판정';
        return 'Hybrid 판정';
      }
      case 'bi': {
        const analysisType = (config.analysis as Record<string, unknown>)?.type as string;
        return analysisType || 'BI 분석';
      }
      case 'mcp': {
        const toolName = config.tool_name as string;
        return toolName || 'MCP 도구';
      }
      case 'wait': {
        const waitType = config.wait_type as string;
        if (waitType === 'duration') return `${config.duration_seconds || 0}초 대기`;
        if (waitType === 'event') return `이벤트 대기`;
        if (waitType === 'schedule') return 'cron 대기';
        return '대기';
      }
      case 'approval': {
        const title = config.title as string;
        return title || '승인 요청';
      }
      // P2 고급 노드
      case 'compensation':
        return '보상 트랜잭션';
      case 'deploy': {
        const deployType = config.deploy_type as string;
        if (deployType === 'ruleset') return '룰셋 배포';
        if (deployType === 'model') return '모델 배포';
        if (deployType === 'workflow') return '워크플로우 배포';
        return '배포';
      }
      case 'rollback': {
        const targetType = config.target_type as string;
        return `${targetType || ''} 롤백`;
      }
      case 'simulate': {
        const scenarios = config.scenarios as unknown[];
        return `${scenarios?.length || 0}개 시나리오`;
      }
      // 추가 노드
      case 'switch': {
        const cases = config.cases as unknown[];
        return `${cases?.length || 0}개 분기`;
      }
      case 'code': {
        const language = config.language as string;
        return language || 'Python';
      }
      default:
        return data.label;
    }
  };

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 min-w-[160px] shadow-sm relative
        ${colors.bg} ${colors.border}
        ${selected && execStatus === 'idle' ? 'ring-2 ring-blue-500 ring-offset-2' : ''}
        ${execStyle.ring}
        transition-all cursor-pointer
      `}
    >
      {/* 실행 상태 아이콘 */}
      {StatusIcon && (
        <div className="absolute -top-2 -right-2 bg-white dark:bg-slate-800 rounded-full p-0.5">
          <StatusIcon
            className={`w-4 h-4 ${
              execStatus === 'executing' ? 'text-blue-500 animate-spin' :
              execStatus === 'completed' ? 'text-green-500' :
              execStatus === 'failed' ? 'text-red-500' : 'text-gray-400'
            }`}
          />
        </div>
      )}

      {/* 입력 핸들 (트리거 노드 제외) */}
      {!isTrigger && (
        <Handle
          type="target"
          position={Position.Top}
          className="!w-3 !h-3 !bg-slate-400 !border-2 !border-white dark:!border-slate-800 hover:!bg-blue-500 transition-colors"
        />
      )}

      <div className="flex items-center gap-2">
        <div className={`p-1.5 rounded ${colors.bg}`}>
          <Icon className={`w-4 h-4 ${colors.text}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className={`text-xs font-medium ${colors.text}`}>
            {nodeTypeLabels[data.nodeType] || data.nodeType}
          </div>
          <div className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
            {getSummary()}
          </div>
        </div>
      </div>

      {/* 출력 핸들 */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-slate-400 !border-2 !border-white dark:!border-slate-800 hover:!bg-blue-500 transition-colors"
      />

      {/* If/Else 노드는 두 개의 출력 핸들 */}
      {data.nodeType === 'if_else' && (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="then"
            className="!w-3 !h-3 !bg-green-500 !border-2 !border-white dark:!border-slate-800 hover:!bg-green-600 transition-colors !left-[30%]"
          />
          <Handle
            type="source"
            position={Position.Bottom}
            id="else"
            className="!w-3 !h-3 !bg-red-500 !border-2 !border-white dark:!border-slate-800 hover:!bg-red-600 transition-colors !left-[70%]"
          />
        </>
      )}
    </div>
  );
}

// ============ Node Palette (드래그 소스) ============

// 팔레트에서 사용하는 노드 타입 (trigger 제외)
type PaletteNodeType =
  // P0 기본
  | 'condition' | 'action' | 'if_else' | 'loop' | 'parallel' | 'switch' | 'code'
  // P1 비즈니스
  | 'data' | 'judgment' | 'bi' | 'mcp' | 'wait' | 'approval'
  // P2 고급
  | 'compensation' | 'deploy' | 'rollback' | 'simulate';

// 노드 카테고리 정의
const nodeCategories: { label: string; types: PaletteNodeType[] }[] = [
  { label: '기본', types: ['condition', 'action', 'if_else', 'loop', 'parallel', 'switch', 'code'] },
  { label: '비즈니스', types: ['data', 'judgment', 'bi', 'mcp', 'wait', 'approval'] },
  { label: '고급', types: ['compensation', 'deploy', 'rollback', 'simulate'] },
];

interface NodePaletteProps {
  onDragStart: (event: React.DragEvent, nodeType: PaletteNodeType) => void;
}

function NodePalette({ onDragStart }: NodePaletteProps) {
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    '기본': true,
    '비즈니스': false,
    '고급': false,
  });

  const toggleCategory = (label: string) => {
    setExpandedCategories(prev => ({ ...prev, [label]: !prev[label] }));
  };

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
        노드 추가
      </h3>
      {nodeCategories.map((category) => (
        <div key={category.label} className="space-y-1">
          <button
            onClick={() => toggleCategory(category.label)}
            className="flex items-center justify-between w-full text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
          >
            <span>{category.label}</span>
            <span className="text-slate-400">{expandedCategories[category.label] ? '−' : '+'}</span>
          </button>
          {expandedCategories[category.label] && (
            <div className="space-y-1 pl-1">
              {category.types.map((type) => {
                const colors = nodeTypeColors[type];
                const Icon = nodeTypeIcons[type];
                return (
                  <div
                    key={type}
                    draggable
                    onDragStart={(e) => onDragStart(e, type)}
                    className={`
                      flex items-center gap-2 px-2 py-1.5 rounded-lg border cursor-grab
                      ${colors.bg} ${colors.border}
                      hover:shadow-md transition-shadow text-xs
                    `}
                  >
                    <Icon className={`w-3.5 h-3.5 ${colors.text}`} />
                    <span className={`font-medium ${colors.text}`}>
                      {nodeTypeLabels[type]}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ============ Node Config Panel ============

interface NodeConfigPanelProps {
  node: Node<CustomNodeData> | null;
  onUpdate: (nodeId: string, data: CustomNodeData) => void;
  onClose: () => void;
  onDelete: (nodeId: string) => void;
}

function NodeConfigPanel({ node, onUpdate, onClose, onDelete }: NodeConfigPanelProps) {
  const toast = useToast();

  if (!node) return null;

  const data = node.data;
  const nodeType = data.nodeType;

  const updateConfig = (key: string, value: unknown) => {
    onUpdate(node.id, {
      ...data,
      config: { ...data.config, [key]: value },
    });
  };

  // 복합 노드 (if_else, loop, parallel)는 더 넓은 패널 사용
  const isComplexNode = ['if_else', 'loop', 'parallel'].includes(nodeType);
  const panelWidth = isComplexNode ? 'w-96' : 'w-72';
  const maxHeight = isComplexNode ? 'max-h-[600px]' : 'max-h-[400px]';

  return (
    <div className={`${panelWidth} bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 flex flex-col ${maxHeight}`}>
      <div className="flex items-center justify-between p-3 border-b border-slate-200 dark:border-slate-700 flex-shrink-0">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          {nodeTypeLabels[nodeType] || '노드'} 설정
        </h3>
        <div className="flex items-center gap-1">
          <button
            onClick={async () => {
              const confirmed = await toast.confirm({
                title: '노드 삭제',
                message: '이 노드를 삭제하시겠습니까?',
                confirmText: '삭제',
                cancelText: '취소',
                variant: 'danger',
              });
              if (confirmed) {
                onDelete(node.id);
                onClose();
              }
            }}
            className="p-1 rounded text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
            title="노드 삭제"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <button onClick={onClose} className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="p-3 space-y-3 overflow-y-auto flex-1">
        {/* 조건 노드 - ConditionBuilder 사용 */}
        {nodeType === 'condition' && (
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
              조건식
            </label>
            <ConditionBuilder
              value={(data.config.condition as string) || ''}
              onChange={(value) => updateConfig('condition', value)}
            />
          </div>
        )}

        {/* 액션 노드 - ActionParameterForm 사용 */}
        {nodeType === 'action' && (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                액션
              </label>
              <select
                value={(data.config.action as string) || ''}
                onChange={(e) => {
                  updateConfig('action', e.target.value);
                  // 액션 변경 시 파라미터 초기화
                  updateConfig('parameters', {});
                }}
                className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
              >
                <option value="">선택...</option>
                <optgroup label="알림">
                  <option value="send_slack_notification">Slack 알림</option>
                  <option value="send_email">이메일 발송</option>
                  <option value="send_sms">SMS 발송</option>
                </optgroup>
                <optgroup label="데이터">
                  <option value="save_to_database">DB 저장</option>
                  <option value="export_to_csv">CSV 내보내기</option>
                  <option value="log_event">로그 기록</option>
                </optgroup>
                <optgroup label="제어">
                  <option value="stop_production_line">라인 정지</option>
                  <option value="adjust_sensor_threshold">임계값 조정</option>
                  <option value="trigger_maintenance">유지보수 요청</option>
                </optgroup>
                <optgroup label="분석">
                  <option value="calculate_defect_rate">불량률 계산</option>
                  <option value="analyze_sensor_trend">추세 분석</option>
                  <option value="predict_equipment_failure">고장 예측</option>
                </optgroup>
              </select>
            </div>
            {/* ActionParameterForm으로 파라미터 자동 폼 생성 */}
            <ActionParameterForm
              action={(data.config.action as string) || ''}
              parameters={(data.config.parameters as Record<string, unknown>) || {}}
              onChange={(params) => updateConfig('parameters', params)}
            />
          </>
        )}

        {/* If/Else 노드 - 분기 편집 UI */}
        {nodeType === 'if_else' && (
          <IfElseBranchEditor
            condition={(data.config.condition as string) || ''}
            onConditionChange={(value) => updateConfig('condition', value)}
            thenNodes={(data.config.then as InnerNode[]) || []}
            onThenNodesChange={(nodes) => updateConfig('then', nodes)}
            elseNodes={(data.config.else as InnerNode[]) || []}
            onElseNodesChange={(nodes) => updateConfig('else', nodes)}
          />
        )}

        {/* Loop 노드 - 반복 내부 노드 편집 UI */}
        {nodeType === 'loop' && (
          <LoopNodeEditor
            loopType={(data.config.loop_type as 'for' | 'while') || 'for'}
            onLoopTypeChange={(type) => updateConfig('loop_type', type)}
            count={(data.config.count as number) || 1}
            onCountChange={(value) => updateConfig('count', value)}
            condition={(data.config.condition as string) || ''}
            onConditionChange={(value) => updateConfig('condition', value)}
            nodes={(data.config.nodes as InnerNode[]) || []}
            onNodesChange={(nodes) => updateConfig('nodes', nodes)}
          />
        )}

        {/* Parallel 노드 - 병렬 브랜치 편집 UI */}
        {nodeType === 'parallel' && (
          <ParallelBranchEditor
            branches={(data.config.branches as InnerNode[][]) || [[]]}
            onChange={(branches) => updateConfig('branches', branches)}
            failFast={(data.config.fail_fast as boolean) || false}
            onFailFastChange={(value) => updateConfig('fail_fast', value)}
          />
        )}

        {/* ============ P1 비즈니스 노드 ============ */}

        {/* DATA 노드 - 데이터 소스 설정 */}
        {nodeType === 'data' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">소스 타입</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={(data.config.source_type as string) || 'sensor'}
                onChange={(e) => updateConfig('source_type', e.target.value)}
              >
                <option value="sensor">센서 데이터</option>
                <option value="connector">데이터 커넥터</option>
                <option value="api">외부 API</option>
                <option value="query">SQL 쿼리</option>
              </select>
            </div>

            {(data.config.source_type === 'sensor' || !data.config.source_type) && (
              <>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">센서 ID (쉼표 구분)</label>
                  <input
                    type="text"
                    className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                    placeholder="SENSOR_001, SENSOR_002"
                    value={((data.config.source as Record<string, unknown>)?.sensor_ids as string[])?.join(', ') || ''}
                    onChange={(e) => updateConfig('source', {
                      ...(data.config.source as Record<string, unknown> || {}),
                      sensor_ids: e.target.value.split(',').map(s => s.trim()).filter(Boolean)
                    })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">조회 기간</label>
                  <select
                    className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                    value={((data.config.source as Record<string, unknown>)?.time_range as string) || '1h'}
                    onChange={(e) => updateConfig('source', {
                      ...(data.config.source as Record<string, unknown> || {}),
                      time_range: e.target.value
                    })}
                  >
                    <option value="15m">15분</option>
                    <option value="1h">1시간</option>
                    <option value="6h">6시간</option>
                    <option value="24h">24시간</option>
                    <option value="7d">7일</option>
                  </select>
                </div>
              </>
            )}

            {data.config.source_type === 'connector' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">커넥터 ID</label>
                  <input
                    type="text"
                    className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                    placeholder="UUID"
                    value={((data.config.source as Record<string, unknown>)?.connection as string) || ''}
                    onChange={(e) => updateConfig('source', {
                      ...(data.config.source as Record<string, unknown> || {}),
                      connection: e.target.value
                    })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">쿼리</label>
                  <textarea
                    className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                    rows={3}
                    placeholder="SELECT * FROM ..."
                    value={((data.config.source as Record<string, unknown>)?.query as string) || ''}
                    onChange={(e) => updateConfig('source', {
                      ...(data.config.source as Record<string, unknown> || {}),
                      query: e.target.value
                    })}
                  />
                </div>
              </>
            )}

            {data.config.source_type === 'api' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">API URL</label>
                  <input
                    type="text"
                    className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                    placeholder="https://api.example.com/data"
                    value={((data.config.source as Record<string, unknown>)?.url as string) || ''}
                    onChange={(e) => updateConfig('source', {
                      ...(data.config.source as Record<string, unknown> || {}),
                      url: e.target.value
                    })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">HTTP 메서드</label>
                  <select
                    className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                    value={((data.config.source as Record<string, unknown>)?.method as string) || 'GET'}
                    onChange={(e) => updateConfig('source', {
                      ...(data.config.source as Record<string, unknown> || {}),
                      method: e.target.value
                    })}
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                  </select>
                </div>
              </>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">결과 변수명</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                placeholder="data"
                value={((data.config.output as Record<string, unknown>)?.variable as string) || 'data'}
                onChange={(e) => updateConfig('output', { variable: e.target.value })}
              />
            </div>
          </div>
        )}

        {/* JUDGMENT 노드 - 판단 정책 설정 */}
        {nodeType === 'judgment' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">판단 정책</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={((data.config.policy as Record<string, unknown>)?.type as string) || 'HYBRID'}
                onChange={(e) => updateConfig('policy', {
                  ...(data.config.policy as Record<string, unknown> || {}),
                  type: e.target.value
                })}
              >
                <option value="RULE_ONLY">룰 전용</option>
                <option value="LLM_ONLY">LLM 전용</option>
                <option value="HYBRID">하이브리드 (권장)</option>
              </select>
            </div>

            {((data.config.policy as Record<string, unknown>)?.type !== 'LLM_ONLY') && (
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">룰 팩 ID</label>
                <input
                  type="text"
                  className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                  placeholder="규칙 팩 UUID (선택)"
                  value={((data.config.policy as Record<string, unknown>)?.rule_pack_id as string) || ''}
                  onChange={(e) => updateConfig('policy', {
                    ...(data.config.policy as Record<string, unknown> || {}),
                    rule_pack_id: e.target.value
                  })}
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">입력 데이터 (JSON)</label>
              <textarea
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                rows={3}
                placeholder='{"temperature": "{{sensor.temp}}"}'
                value={JSON.stringify(data.config.input || {}, null, 2)}
                onChange={(e) => {
                  try {
                    updateConfig('input', JSON.parse(e.target.value));
                  } catch {
                    // JSON 파싱 실패 시 무시
                  }
                }}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">결과 변수명</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                placeholder="judgment_result"
                value={((data.config.output as Record<string, unknown>)?.variable as string) || 'judgment_result'}
                onChange={(e) => updateConfig('output', { variable: e.target.value })}
              />
            </div>
          </div>
        )}

        {/* BI 노드 - 분석 설정 */}
        {nodeType === 'bi' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">분석 타입</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={((data.config.analysis as Record<string, unknown>)?.type as string) || 'trend'}
                onChange={(e) => updateConfig('analysis', {
                  ...(data.config.analysis as Record<string, unknown> || {}),
                  type: e.target.value
                })}
              >
                <option value="trend">추이 분석</option>
                <option value="comparison">비교 분석</option>
                <option value="distribution">분포 분석</option>
                <option value="correlation">상관 분석</option>
                <option value="anomaly">이상 탐지</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">메트릭 (쉼표 구분)</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                placeholder="temperature, pressure, vibration"
                value={((data.config.analysis as Record<string, unknown>)?.metrics as string[])?.join(', ') || ''}
                onChange={(e) => updateConfig('analysis', {
                  ...(data.config.analysis as Record<string, unknown> || {}),
                  metrics: e.target.value.split(',').map(s => s.trim()).filter(Boolean)
                })}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">분석 기간</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={((data.config.analysis as Record<string, unknown>)?.time_range as string) || '24h'}
                onChange={(e) => updateConfig('analysis', {
                  ...(data.config.analysis as Record<string, unknown> || {}),
                  time_range: e.target.value
                })}
              >
                <option value="1h">1시간</option>
                <option value="6h">6시간</option>
                <option value="24h">24시간</option>
                <option value="7d">7일</option>
                <option value="30d">30일</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">결과 변수명</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                placeholder="bi_result"
                value={((data.config.output as Record<string, unknown>)?.variable as string) || 'bi_result'}
                onChange={(e) => updateConfig('output', { variable: e.target.value })}
              />
            </div>
          </div>
        )}

        {/* MCP 노드 - 외부 도구 호출 설정 */}
        {nodeType === 'mcp' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">MCP 서버 ID</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                placeholder="MCP 서버 UUID"
                value={(data.config.mcp_server_id as string) || ''}
                onChange={(e) => updateConfig('mcp_server_id', e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">도구 이름</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                placeholder="weather_api, database_query 등"
                value={(data.config.tool_name as string) || ''}
                onChange={(e) => updateConfig('tool_name', e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">파라미터 (JSON)</label>
              <textarea
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                rows={3}
                placeholder='{"location": "Seoul"}'
                value={JSON.stringify(data.config.parameters || {}, null, 2)}
                onChange={(e) => {
                  try {
                    updateConfig('parameters', JSON.parse(e.target.value));
                  } catch {
                    // JSON 파싱 실패 시 무시
                  }
                }}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">타임아웃 (ms)</label>
              <input
                type="number"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                min={1000}
                max={300000}
                step={1000}
                value={(data.config.timeout_ms as number) || 30000}
                onChange={(e) => updateConfig('timeout_ms', parseInt(e.target.value))}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">결과 변수명</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                placeholder="mcp_result"
                value={(data.config.output_variable as string) || 'mcp_result'}
                onChange={(e) => updateConfig('output_variable', e.target.value)}
              />
            </div>
          </div>
        )}

        {/* WAIT 노드 - 대기 설정 */}
        {nodeType === 'wait' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">대기 타입</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={(data.config.wait_type as string) || 'duration'}
                onChange={(e) => updateConfig('wait_type', e.target.value)}
              >
                <option value="duration">시간 대기</option>
                <option value="event">이벤트 대기</option>
                <option value="schedule">스케줄 대기</option>
              </select>
            </div>

            {(data.config.wait_type === 'duration' || !data.config.wait_type) && (
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">대기 시간 (초)</label>
                <input
                  type="number"
                  className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                  min={1}
                  max={86400}
                  value={(data.config.duration_seconds as number) || 60}
                  onChange={(e) => updateConfig('duration_seconds', parseInt(e.target.value))}
                />
              </div>
            )}

            {data.config.wait_type === 'event' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">이벤트 타입</label>
                  <input
                    type="text"
                    className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                    placeholder="sensor.alert, approval.complete 등"
                    value={(data.config.event_type as string) || ''}
                    onChange={(e) => updateConfig('event_type', e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">타임아웃 (초)</label>
                  <input
                    type="number"
                    className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                    min={60}
                    max={86400}
                    value={(data.config.timeout_seconds as number) || 3600}
                    onChange={(e) => updateConfig('timeout_seconds', parseInt(e.target.value))}
                  />
                </div>
              </>
            )}

            {data.config.wait_type === 'schedule' && (
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Cron 표현식</label>
                <input
                  type="text"
                  className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                  placeholder="0 9 * * * (매일 오전 9시)"
                  value={(data.config.schedule_cron as string) || ''}
                  onChange={(e) => updateConfig('schedule_cron', e.target.value)}
                />
                <p className="text-xs text-slate-500 mt-1">분 시 일 월 요일</p>
              </div>
            )}
          </div>
        )}

        {/* APPROVAL 노드 - 승인 설정 */}
        {nodeType === 'approval' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">승인 제목</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                placeholder="워크플로우 승인 요청"
                value={(data.config.title as string) || ''}
                onChange={(e) => updateConfig('title', e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">설명</label>
              <textarea
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                rows={2}
                placeholder="승인 요청에 대한 상세 설명"
                value={(data.config.description as string) || ''}
                onChange={(e) => updateConfig('description', e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">승인자 (이메일, 쉼표 구분)</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                placeholder="admin@company.com, manager@company.com"
                value={(data.config.approvers as string[])?.join(', ') || ''}
                onChange={(e) => updateConfig('approvers', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">알림 채널</label>
              <div className="flex gap-3">
                <label className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400">
                  <input
                    type="checkbox"
                    checked={(data.config.notification as string[])?.includes('email') ?? true}
                    onChange={(e) => {
                      const current = (data.config.notification as string[]) || ['email'];
                      if (e.target.checked) {
                        updateConfig('notification', [...current, 'email']);
                      } else {
                        updateConfig('notification', current.filter(n => n !== 'email'));
                      }
                    }}
                  />
                  이메일
                </label>
                <label className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400">
                  <input
                    type="checkbox"
                    checked={(data.config.notification as string[])?.includes('slack') ?? false}
                    onChange={(e) => {
                      const current = (data.config.notification as string[]) || [];
                      if (e.target.checked) {
                        updateConfig('notification', [...current, 'slack']);
                      } else {
                        updateConfig('notification', current.filter(n => n !== 'slack'));
                      }
                    }}
                  />
                  Slack
                </label>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">타임아웃 (시간)</label>
              <input
                type="number"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                min={1}
                max={168}
                value={(data.config.timeout_hours as number) || 24}
                onChange={(e) => updateConfig('timeout_hours', parseInt(e.target.value))}
              />
            </div>
          </div>
        )}

        {/* ============ P2 고급 노드 ============ */}

        {/* COMPENSATION 노드 - 보상 트랜잭션 설정 (Saga 패턴) */}
        {nodeType === 'compensation' && (
          <div className="space-y-3">
            {/* 보상 타입 */}
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">보상 타입</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={(data.config.compensation_type as string) || 'auto'}
                onChange={(e) => updateConfig('compensation_type', e.target.value)}
              >
                <option value="auto">자동 (역순 실행)</option>
                <option value="manual">수동 (액션 지정)</option>
              </select>
            </div>

            {/* 실패 시 동작 */}
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">보상 실패 시</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={(data.config.on_failure as string) || 'continue'}
                onChange={(e) => updateConfig('on_failure', e.target.value)}
              >
                <option value="continue">계속 진행 (다음 보상 실행)</option>
                <option value="abort">중단 (보상 중지)</option>
              </select>
            </div>

            {/* 수동 모드: 대상 노드 */}
            {(data.config.compensation_type as string) === 'manual' && (
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">대상 노드 ID (쉼표 구분)</label>
                <input
                  type="text"
                  className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                  placeholder="node_1, node_2, node_3"
                  value={(data.config.target_nodes as string[])?.join(', ') || ''}
                  onChange={(e) => updateConfig('target_nodes', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                />
              </div>
            )}

            {/* 수동 모드: 보상 액션 정의 */}
            {(data.config.compensation_type as string) === 'manual' && (
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                  보상 액션 (JSON)
                </label>
                <textarea
                  className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                  rows={4}
                  placeholder={`{
  "node_1": {
    "action_type": "api_call",
    "config": { "url": "/api/rollback", "method": "POST" }
  }
}`}
                  value={typeof data.config.compensation_actions === 'object'
                    ? JSON.stringify(data.config.compensation_actions, null, 2)
                    : '{}'}
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value);
                      updateConfig('compensation_actions', parsed);
                    } catch {
                      // JSON 파싱 실패 - 입력 중이므로 무시
                    }
                  }}
                />
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  action_type: api_call | db_rollback | state_restore
                </p>
              </div>
            )}

            {/* 자동 모드 안내 */}
            {(data.config.compensation_type as string) !== 'manual' && (
              <p className="text-xs text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 p-2 rounded">
                💡 자동 모드: 실행된 노드들을 역순으로 자동 보상합니다
              </p>
            )}
          </div>
        )}

        {/* DEPLOY 노드 - 배포 설정 */}
        {nodeType === 'deploy' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">배포 타입</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={(data.config.deploy_type as string) || 'ruleset'}
                onChange={(e) => updateConfig('deploy_type', e.target.value)}
              >
                <option value="ruleset">룰셋 배포</option>
                <option value="model">모델 배포</option>
                <option value="workflow">워크플로우 배포</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">대상 ID</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                placeholder="배포할 대상의 UUID"
                value={(data.config.target_id as string) || ''}
                onChange={(e) => updateConfig('target_id', e.target.value)}
              />
            </div>

            {/* 버전 (선택) */}
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">버전 (선택)</label>
              <input
                type="number"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                placeholder="비워두면 최신 버전"
                min={1}
                value={(data.config.version as number) || ''}
                onChange={(e) => updateConfig('version', e.target.value ? Number(e.target.value) : undefined)}
              />
              <p className="text-xs text-slate-500 mt-1">버전을 지정하지 않으면 최신 버전 배포</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">환경</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={(data.config.environment as string) || 'production'}
                onChange={(e) => updateConfig('environment', e.target.value)}
              >
                <option value="development">개발 (Development)</option>
                <option value="staging">스테이징 (Staging)</option>
                <option value="production">운영 (Production)</option>
              </select>
            </div>

            {/* 실패 시 롤백 */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="rollback_on_failure"
                checked={(data.config.rollback_on_failure as boolean) ?? true}
                onChange={(e) => updateConfig('rollback_on_failure', e.target.checked)}
                className="rounded"
              />
              <label htmlFor="rollback_on_failure" className="text-xs text-slate-600 dark:text-slate-400">
                배포 실패 시 자동 롤백
              </label>
            </div>

            {/* 배포 검증 규칙 */}
            <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded">
              <div className="flex items-center gap-2 mb-2">
                <input
                  type="checkbox"
                  id="validation_enabled"
                  checked={((data.config.validation as Record<string, unknown>)?.enabled as boolean) ?? false}
                  onChange={(e) => updateConfig('validation', {
                    ...(data.config.validation as Record<string, unknown> || {}),
                    enabled: e.target.checked
                  })}
                  className="rounded"
                />
                <label htmlFor="validation_enabled" className="text-xs font-medium text-slate-600 dark:text-slate-400">
                  배포 전 검증 활성화
                </label>
              </div>

              {Boolean((data.config.validation as Record<string, unknown>)?.enabled) && (
                <div className="space-y-1 pl-4">
                  {[
                    { key: 'no_syntax_errors', label: '문법 오류 없음' },
                    { key: 'test_coverage_80', label: '테스트 커버리지 80% 이상' },
                  ].map(({ key, label }) => (
                    <label key={key} className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
                      <input
                        type="checkbox"
                        checked={(((data.config.validation as Record<string, unknown>)?.rules as string[]) || []).includes(key)}
                        onChange={(e) => {
                          const currentRules = ((data.config.validation as Record<string, unknown>)?.rules as string[]) || [];
                          const newRules = e.target.checked
                            ? [...currentRules, key]
                            : currentRules.filter((r: string) => r !== key);
                          updateConfig('validation', {
                            ...(data.config.validation as Record<string, unknown> || {}),
                            rules: newRules
                          });
                        }}
                        className="rounded"
                      />
                      {label}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ROLLBACK 노드 - 롤백 설정 */}
        {nodeType === 'rollback' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">대상 타입</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={(data.config.target_type as string) || 'workflow'}
                onChange={(e) => updateConfig('target_type', e.target.value)}
              >
                <option value="workflow">워크플로우</option>
                <option value="ruleset">룰셋</option>
                <option value="model">모델</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">대상 ID</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                placeholder="롤백할 대상의 UUID"
                value={(data.config.target_id as string) || ''}
                onChange={(e) => updateConfig('target_id', e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">버전 (선택)</label>
              <input
                type="number"
                min="1"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                placeholder="예: 3"
                value={(data.config.version as number) || ''}
                onChange={(e) => updateConfig('version', e.target.value ? parseInt(e.target.value) : null)}
              />
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                💡 비워두면 직전 버전으로 자동 롤백됩니다
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">롤백 사유</label>
              <textarea
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                rows={2}
                placeholder="롤백 이유를 입력하세요 (감사 로그용)"
                value={(data.config.reason as string) || ''}
                onChange={(e) => updateConfig('reason', e.target.value)}
              />
            </div>
          </div>
        )}

        {/* SIMULATE 노드 - 시뮬레이션 설정 */}
        {nodeType === 'simulate' && (
          <div className="space-y-3">
            {/* 시뮬레이션 타입 선택 */}
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">시뮬레이션 타입</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={(data.config.simulation_type as string) || 'scenario'}
                onChange={(e) => updateConfig('simulation_type', e.target.value)}
              >
                <option value="scenario">시나리오 기반</option>
                <option value="parameter_sweep">파라미터 스윕</option>
                <option value="monte_carlo">몬테카를로</option>
              </select>
            </div>

            {/* 대상 노드 */}
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">대상 노드 (쉼표 구분)</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                placeholder="node_1, node_2"
                value={(data.config.target_nodes as string[])?.join(', ') || ''}
                onChange={(e) => updateConfig('target_nodes', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              />
            </div>

            {/* 측정 메트릭 */}
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">측정 메트릭</label>
              <div className="flex gap-3 flex-wrap">
                {[
                  { key: 'success_rate', label: '성공률' },
                  { key: 'execution_time', label: '실행시간' },
                ].map(({ key, label }) => (
                  <label key={key} className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400">
                    <input
                      type="checkbox"
                      checked={(data.config.metrics as string[] || ['success_rate']).includes(key)}
                      onChange={(e) => {
                        const current = (data.config.metrics as string[]) || ['success_rate'];
                        if (e.target.checked) {
                          updateConfig('metrics', [...current, key]);
                        } else {
                          updateConfig('metrics', current.filter(m => m !== key));
                        }
                      }}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>

            {/* 시나리오 타입일 때 */}
            {(data.config.simulation_type || 'scenario') === 'scenario' && (
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">시뮬레이션 시나리오 (JSON)</label>
                <textarea
                  className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                  rows={4}
                  placeholder={`[
  {"name": "고온 시나리오", "overrides": {"temp": 90}},
  {"name": "정상 시나리오", "overrides": {"temp": 70}}
]`}
                  value={JSON.stringify(data.config.scenarios || [], null, 2)}
                  onChange={(e) => {
                    try {
                      updateConfig('scenarios', JSON.parse(e.target.value));
                    } catch {
                      // JSON 파싱 실패 시 무시
                    }
                  }}
                />
              </div>
            )}

            {/* 파라미터 스윕 타입일 때 */}
            {data.config.simulation_type === 'parameter_sweep' && (
              <div className="space-y-2 p-2 bg-slate-50 dark:bg-slate-800 rounded">
                <p className="text-xs font-medium text-slate-600 dark:text-slate-400">파라미터 스윕 설정</p>
                <div className="grid grid-cols-2 gap-2">
                  <div className="col-span-2">
                    <label className="text-xs text-slate-500 dark:text-slate-400">파라미터명</label>
                    <input
                      type="text"
                      className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                      placeholder="temperature"
                      value={((data.config.sweep_config as Record<string, unknown>)?.parameter as string) || ''}
                      onChange={(e) => updateConfig('sweep_config', {
                        ...(data.config.sweep_config as Record<string, unknown> || {}),
                        parameter: e.target.value
                      })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">시작값</label>
                    <input
                      type="number"
                      className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                      value={((data.config.sweep_config as Record<string, unknown>)?.start as number) ?? 0}
                      onChange={(e) => updateConfig('sweep_config', {
                        ...(data.config.sweep_config as Record<string, unknown> || {}),
                        start: Number(e.target.value)
                      })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">종료값</label>
                    <input
                      type="number"
                      className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                      value={((data.config.sweep_config as Record<string, unknown>)?.end as number) ?? 100}
                      onChange={(e) => updateConfig('sweep_config', {
                        ...(data.config.sweep_config as Record<string, unknown> || {}),
                        end: Number(e.target.value)
                      })}
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="text-xs text-slate-500 dark:text-slate-400">증가값 (step)</label>
                    <input
                      type="number"
                      className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                      value={((data.config.sweep_config as Record<string, unknown>)?.step as number) ?? 10}
                      onChange={(e) => updateConfig('sweep_config', {
                        ...(data.config.sweep_config as Record<string, unknown> || {}),
                        step: Number(e.target.value)
                      })}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* 몬테카를로 타입일 때 */}
            {data.config.simulation_type === 'monte_carlo' && (
              <div className="space-y-2 p-2 bg-slate-50 dark:bg-slate-800 rounded">
                <p className="text-xs font-medium text-slate-600 dark:text-slate-400">몬테카를로 설정</p>
                <div>
                  <label className="text-xs text-slate-500 dark:text-slate-400">반복 횟수</label>
                  <input
                    type="number"
                    className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                    placeholder="100"
                    min={1}
                    max={1000}
                    value={(data.config.iterations as number) || 100}
                    onChange={(e) => updateConfig('iterations', Number(e.target.value))}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500 dark:text-slate-400">분포 설정 (JSON)</label>
                  <textarea
                    className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                    rows={4}
                    placeholder={`{
  "temperature": {"type": "normal", "mean": 70, "std": 10},
  "pressure": {"type": "uniform", "min": 80, "max": 120}
}`}
                    value={JSON.stringify(data.config.distributions || {}, null, 2)}
                    onChange={(e) => {
                      try {
                        updateConfig('distributions', JSON.parse(e.target.value));
                      } catch {
                        // JSON 파싱 실패 시 무시
                      }
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ============ 추가 노드 ============ */}

        {/* SWITCH 노드 - 다중 분기 설정 */}
        {nodeType === 'switch' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">분기 표현식</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                placeholder="${temperature} 또는 ${status}"
                value={(data.config.expression as string) || ''}
                onChange={(e) => updateConfig('expression', e.target.value)}
              />
              <p className="text-xs text-slate-500 mt-1">
                변수를 $&#123;name&#125; 형식으로 입력
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">분기 케이스 (JSON)</label>
              <textarea
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                rows={5}
                placeholder={`[
  {"value": "critical", "condition": "> 90", "next_node": "critical_action"},
  {"value": "warning", "condition": "> 70", "next_node": "warning_action"}
]`}
                value={JSON.stringify(data.config.cases || [], null, 2)}
                onChange={(e) => {
                  try {
                    updateConfig('cases', JSON.parse(e.target.value));
                  } catch {
                    // JSON 파싱 실패 시 무시
                  }
                }}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">기본 분기 (선택)</label>
              <input
                type="text"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                placeholder="default_action 노드 ID"
                value={(data.config.default_node as string) || ''}
                onChange={(e) => updateConfig('default_node', e.target.value || null)}
              />
            </div>
          </div>
        )}

        {/* CODE 노드 - 코드 실행 설정 */}
        {nodeType === 'code' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">언어</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={(data.config.language as string) || 'python'}
                onChange={(e) => updateConfig('language', e.target.value)}
              >
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="rhai">Rhai (내장)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">코드</label>
              <textarea
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                rows={8}
                placeholder={`# Python 예시
result = input_data.get('temperature', 0) * 1.8 + 32
# 또는 JavaScript 예시
// const result = inputData.temperature * 1.8 + 32;`}
                value={(data.config.code as string) || ''}
                onChange={(e) => updateConfig('code', e.target.value)}
              />
              <p className="text-xs text-slate-500 mt-1">
                input_data 변수로 입력 데이터에 접근 가능
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">타임아웃 (초)</label>
              <input
                type="number"
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                min={1}
                max={300}
                value={(data.config.timeout_seconds as number) || 30}
                onChange={(e) => updateConfig('timeout_seconds', parseInt(e.target.value) || 30)}
              />
            </div>
          </div>
        )}

        {/* TRIGGER 노드 - 트리거 설정 (추가) */}
        {nodeType === 'trigger' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">트리거 타입</label>
              <select
                className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                value={(data.config.trigger_type as string) || 'manual'}
                onChange={(e) => updateConfig('trigger_type', e.target.value)}
              >
                <option value="manual">수동 실행</option>
                <option value="schedule">스케줄 (Cron)</option>
                <option value="event">이벤트 기반</option>
                <option value="webhook">웹훅</option>
              </select>
            </div>

            {data.config.trigger_type === 'schedule' && (
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Cron 표현식</label>
                <input
                  type="text"
                  className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600 font-mono"
                  placeholder="0 * * * * (매시 정각)"
                  value={(data.config.schedule_cron as string) || ''}
                  onChange={(e) => updateConfig('schedule_cron', e.target.value)}
                />
              </div>
            )}

            {data.config.trigger_type === 'event' && (
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">이벤트 타입</label>
                <input
                  type="text"
                  className="w-full px-2 py-1.5 text-sm border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                  placeholder="sensor.alert, order.created 등"
                  value={(data.config.event_type as string) || ''}
                  onChange={(e) => updateConfig('event_type', e.target.value)}
                />
              </div>
            )}

            {data.config.trigger_type === 'webhook' && (
              <div className="bg-slate-50 dark:bg-slate-900 p-2 rounded">
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  웹훅 URL이 자동 생성됩니다.
                </p>
                <code className="text-xs font-mono text-blue-600">
                  POST /api/v1/workflows/webhook/{'{workflow_id}'}
                </code>
              </div>
            )}
          </div>
        )}

        {/* ============ 고급 설정 (Retry / Circuit Breaker) ============ */}
        {/* 외부 호출 노드: mcp, data(api), action, judgment, bi */}
        {(['mcp', 'action', 'judgment', 'bi'].includes(nodeType) ||
          (nodeType === 'data' && data.config.source_type === 'api')) && (
          <div className="mt-4 border-t border-slate-200 dark:border-slate-700 pt-3">
            <details className="group">
              <summary className="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-400 cursor-pointer hover:text-slate-800 dark:hover:text-slate-200">
                <Settings className="w-3.5 h-3.5" />
                <span>고급 설정 (Retry / Circuit Breaker)</span>
                <span className="ml-auto text-slate-400 group-open:rotate-90 transition-transform">▶</span>
              </summary>

              <div className="mt-3 space-y-4 pl-1">
                {/* Retry 설정 */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <RefreshCw className="w-3.5 h-3.5 text-blue-500" />
                    <span className="text-xs font-medium text-slate-700 dark:text-slate-300">재시도 설정</span>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">최대 재시도</label>
                      <input
                        type="number"
                        className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                        min={0}
                        max={10}
                        value={((data.config.retry as Record<string, unknown>)?.max_retries as number) ?? 3}
                        onChange={(e) => updateConfig('retry', {
                          ...(data.config.retry as Record<string, unknown> || {}),
                          max_retries: parseInt(e.target.value) || 0
                        })}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">백오프 전략</label>
                      <select
                        className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                        value={((data.config.retry as Record<string, unknown>)?.backoff_strategy as string) || 'exponential'}
                        onChange={(e) => updateConfig('retry', {
                          ...(data.config.retry as Record<string, unknown> || {}),
                          backoff_strategy: e.target.value
                        })}
                      >
                        <option value="exponential">Exponential</option>
                        <option value="linear">Linear</option>
                        <option value="fixed">Fixed</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">초기 지연 (ms)</label>
                      <input
                        type="number"
                        className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                        min={100}
                        max={30000}
                        step={100}
                        value={((data.config.retry as Record<string, unknown>)?.initial_delay_ms as number) ?? 1000}
                        onChange={(e) => updateConfig('retry', {
                          ...(data.config.retry as Record<string, unknown> || {}),
                          initial_delay_ms: parseInt(e.target.value) || 1000
                        })}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">최대 지연 (ms)</label>
                      <input
                        type="number"
                        className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                        min={1000}
                        max={60000}
                        step={1000}
                        value={((data.config.retry as Record<string, unknown>)?.max_delay_ms as number) ?? 30000}
                        onChange={(e) => updateConfig('retry', {
                          ...(data.config.retry as Record<string, unknown> || {}),
                          max_delay_ms: parseInt(e.target.value) || 30000
                        })}
                      />
                    </div>
                  </div>
                </div>

                {/* Circuit Breaker 설정 */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    <span className="text-xs font-medium text-slate-700 dark:text-slate-300">회로 차단기</span>
                    <label className="ml-auto flex items-center gap-1">
                      <input
                        type="checkbox"
                        className="w-3.5 h-3.5"
                        checked={((data.config.circuit_breaker as Record<string, unknown>)?.enabled as boolean) ?? true}
                        onChange={(e) => updateConfig('circuit_breaker', {
                          ...(data.config.circuit_breaker as Record<string, unknown> || {}),
                          enabled: e.target.checked
                        })}
                      />
                      <span className="text-xs text-slate-500">활성화</span>
                    </label>
                  </div>

                  {((data.config.circuit_breaker as Record<string, unknown>)?.enabled ?? true) && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">실패 임계값</label>
                        <input
                          type="number"
                          className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                          min={1}
                          max={20}
                          value={((data.config.circuit_breaker as Record<string, unknown>)?.failure_threshold as number) ?? 5}
                          onChange={(e) => updateConfig('circuit_breaker', {
                            ...(data.config.circuit_breaker as Record<string, unknown> || {}),
                            failure_threshold: parseInt(e.target.value) || 5
                          })}
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">복구 대기 (초)</label>
                        <input
                          type="number"
                          className="w-full px-2 py-1 text-xs border rounded text-slate-900 dark:text-slate-100 dark:bg-slate-700 dark:border-slate-600"
                          min={5}
                          max={300}
                          value={((data.config.circuit_breaker as Record<string, unknown>)?.timeout_seconds as number) ?? 30}
                          onChange={(e) => updateConfig('circuit_breaker', {
                            ...(data.config.circuit_breaker as Record<string, unknown> || {}),
                            timeout_seconds: parseInt(e.target.value) || 30
                          })}
                        />
                      </div>
                    </div>
                  )}

                  <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                    연속 실패 시 일시적으로 호출 차단
                  </p>
                </div>
              </div>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}

// ============ Execution Result Panel ============

interface ExecutionResultPanelProps {
  result: WorkflowInstance | null;
  isRunning: boolean;
  onClose: () => void;
}

function ExecutionResultPanel({ result, isRunning, onClose }: ExecutionResultPanelProps) {
  if (!result && !isRunning) return null;

  const getStatusIcon = () => {
    if (isRunning) return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
    if (result?.status === 'completed') return <CheckCircle className="w-5 h-5 text-green-500" />;
    if (result?.status === 'failed') return <XCircle className="w-5 h-5 text-red-500" />;
    return <Clock className="w-5 h-5 text-gray-500" />;
  };

  const getStatusText = () => {
    if (isRunning) return '실행 중...';
    if (result?.status === 'completed') return '완료';
    if (result?.status === 'failed') return '실패';
    return '대기 중';
  };

  const outputData = result?.output_data as {
    message?: string;
    nodes_total?: number;
    nodes_executed?: number;
    nodes_skipped?: number;
    execution_time_ms?: number;
    results?: Array<{ node_id: string; status: string; result?: unknown }>;
  } | undefined;

  return (
    <div className="w-80 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
      <div className="flex items-center justify-between p-3 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <h3 className="text-sm font-semibold">실행 결과: {getStatusText()}</h3>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-3 space-y-3 max-h-[300px] overflow-y-auto text-sm">
        {isRunning && (
          <div className="flex items-center gap-2 text-blue-600">
            <Loader2 className="w-4 h-4 animate-spin" />
            워크플로우 실행 중...
          </div>
        )}

        {result && (
          <>
            {/* 실행 요약 */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-slate-50 dark:bg-slate-900 p-2 rounded">
                <span className="text-slate-500">총 노드</span>
                <p className="font-semibold">{outputData?.nodes_total || 0}개</p>
              </div>
              <div className="bg-slate-50 dark:bg-slate-900 p-2 rounded">
                <span className="text-slate-500">실행됨</span>
                <p className="font-semibold text-green-600">{outputData?.nodes_executed || 0}개</p>
              </div>
              <div className="bg-slate-50 dark:bg-slate-900 p-2 rounded">
                <span className="text-slate-500">건너뜀</span>
                <p className="font-semibold text-gray-500">{outputData?.nodes_skipped || 0}개</p>
              </div>
              <div className="bg-slate-50 dark:bg-slate-900 p-2 rounded">
                <span className="text-slate-500">실행 시간</span>
                <p className="font-semibold">{outputData?.execution_time_ms || 0}ms</p>
              </div>
            </div>

            {/* 에러 메시지 */}
            {result.error_message && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-2">
                <p className="text-xs text-red-600 dark:text-red-400">{result.error_message}</p>
              </div>
            )}

            {/* 노드별 결과 */}
            {outputData?.results && outputData.results.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">노드별 결과</p>
                {outputData.results.map((r, idx) => (
                  <div
                    key={idx}
                    className={`flex items-center gap-2 text-xs p-1.5 rounded ${
                      r.status === 'success' ? 'bg-green-50 dark:bg-green-900/20' :
                      r.status === 'skipped' ? 'bg-gray-50 dark:bg-gray-900/20' :
                      'bg-red-50 dark:bg-red-900/20'
                    }`}
                  >
                    {r.status === 'success' ? (
                      <CheckCircle className="w-3 h-3 text-green-500" />
                    ) : r.status === 'skipped' ? (
                      <SkipForward className="w-3 h-3 text-gray-400" />
                    ) : (
                      <XCircle className="w-3 h-3 text-red-500" />
                    )}
                    <span className="font-mono">{r.node_id}</span>
                  </div>
                ))}
              </div>
            )}

            {/* 입력 데이터 */}
            {result.input_data && Object.keys(result.input_data).length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">입력 데이터</p>
                <pre className="text-xs bg-slate-50 dark:bg-slate-900 p-2 rounded overflow-x-auto">
                  {JSON.stringify(result.input_data, null, 2)}
                </pre>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ============ Simulation Data Modal ============

interface SimulationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRun: (inputData: Record<string, unknown>) => void;
}

function SimulationModal({ isOpen, onClose, onRun }: SimulationModalProps) {
  const [inputJson, setInputJson] = useState('{\n  "temperature": 85,\n  "pressure": 5.2,\n  "humidity": 45\n}');
  const [scenario, setScenario] = useState<'custom' | 'normal' | 'alert' | 'random'>('custom');
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerateSimulated = async () => {
    if (scenario === 'custom') return;
    setIsGenerating(true);
    try {
      const result = await workflowService.generateSimulatedData({
        scenario: scenario as 'normal' | 'alert' | 'random',
      });
      if (result.success) {
        setInputJson(JSON.stringify(result.data, null, 2));
      }
    } catch (error) {
      console.error('Failed to generate simulated data:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRun = () => {
    try {
      const data = JSON.parse(inputJson);
      onRun(data);
    } catch {
      alert('잘못된 JSON 형식입니다.');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white dark:bg-slate-800 rounded-lg shadow-xl w-[400px] overflow-hidden">
        <div className="p-4 border-b border-slate-200 dark:border-slate-700">
          <h3 className="text-lg font-semibold">워크플로우 실행</h3>
          <p className="text-sm text-slate-500">실행할 센서 데이터를 입력하세요</p>
        </div>

        <div className="p-4 space-y-4">
          {/* 시나리오 선택 */}
          <div>
            <label className="block text-sm font-medium mb-2">데이터 시나리오</label>
            <div className="grid grid-cols-4 gap-2">
              {(['custom', 'normal', 'alert', 'random'] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    setScenario(s);
                    if (s !== 'custom') {
                      handleGenerateSimulated();
                    }
                  }}
                  className={`px-3 py-1.5 text-xs rounded-lg border ${
                    scenario === s
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600'
                  }`}
                >
                  {s === 'custom' ? '직접 입력' : s === 'normal' ? '정상' : s === 'alert' ? '경고' : '랜덤'}
                </button>
              ))}
            </div>
          </div>

          {/* JSON 입력 */}
          <div>
            <label className="block text-sm font-medium mb-2">입력 데이터 (JSON)</label>
            <textarea
              value={inputJson}
              onChange={(e) => setInputJson(e.target.value)}
              className="w-full h-32 px-3 py-2 text-sm font-mono border rounded-lg bg-slate-50 dark:bg-slate-900 border-slate-300 dark:border-slate-600"
              placeholder='{"temperature": 85}'
            />
          </div>

          {isGenerating && (
            <div className="flex items-center gap-2 text-sm text-blue-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              시뮬레이션 데이터 생성 중...
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 p-4 border-t border-slate-200 dark:border-slate-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-700 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600"
          >
            취소
          </button>
          <button
            onClick={handleRun}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700"
          >
            <Play className="w-4 h-4" />
            실행
          </button>
        </div>
      </div>
    </div>
  );
}

// ============ DSL Conversion ============

// 평탄화된 노드 정보
interface FlattenedNode {
  node: WorkflowNode;
  parentId?: string;
  branchType?: BranchType;
  depth: number;
  siblingIndex: number;  // 같은 브랜치 내 순서
}

/**
 * 중첩된 DSL 노드를 평탄화하여 모든 노드를 배열로 추출
 */
function flattenNodes(
  nodes: WorkflowNode[],
  parentId?: string,
  branchType?: BranchType,
  depth = 0
): FlattenedNode[] {
  const result: FlattenedNode[] = [];

  nodes.forEach((node, siblingIndex) => {
    result.push({ node, parentId, branchType, depth, siblingIndex });

    // then_nodes 재귀 처리
    if (node.then_nodes?.length) {
      result.push(...flattenNodes(node.then_nodes, node.id, 'then', depth + 1));
    }
    // else_nodes 재귀 처리
    if (node.else_nodes?.length) {
      result.push(...flattenNodes(node.else_nodes, node.id, 'else', depth + 1));
    }
    // loop_nodes 재귀 처리 (loop 노드 내부)
    if (node.loop_nodes?.length) {
      result.push(...flattenNodes(node.loop_nodes, node.id, 'loop', depth + 1));
    }
    // parallel_nodes 재귀 처리
    if (node.parallel_nodes?.length) {
      result.push(...flattenNodes(node.parallel_nodes, node.id, 'parallel', depth + 1));
    }
  });

  return result;
}

/**
 * 평탄화된 노드의 위치를 계산
 */
function calculateNodePosition(
  flatNode: FlattenedNode,
  globalIndex: number,
  allFlatNodes: FlattenedNode[]
): { x: number; y: number } {
  const baseX = 250;
  const baseY = 120;
  const nodeHeight = 100;
  const branchOffsetX = 250; // then/else 브랜치 간격
  const depthOffsetX = 80;   // 깊이당 X 오프셋

  let x = baseX;
  let y = baseY;

  // 부모 노드가 있는 경우 부모의 Y 위치 기준으로 계산
  if (flatNode.parentId) {
    const parentIdx = allFlatNodes.findIndex(f => f.node.id === flatNode.parentId);
    if (parentIdx >= 0) {
      y = baseY + (parentIdx + 1) * nodeHeight + (flatNode.siblingIndex * nodeHeight);
    } else {
      y = baseY + globalIndex * nodeHeight;
    }
  } else {
    // 최상위 노드
    y = baseY + globalIndex * nodeHeight;
  }

  // 브랜치에 따른 X 오프셋
  if (flatNode.branchType === 'then') {
    x = baseX - branchOffsetX + (flatNode.depth * depthOffsetX);
  } else if (flatNode.branchType === 'else') {
    x = baseX + branchOffsetX + (flatNode.depth * depthOffsetX);
  } else if (flatNode.branchType === 'loop') {
    x = baseX + (flatNode.depth * depthOffsetX);
  } else if (flatNode.branchType === 'parallel') {
    // 병렬 브랜치는 수평으로 펼침
    x = baseX + (flatNode.siblingIndex * 200) - 100;
  } else {
    // 최상위 노드
    x = baseX;
  }

  return { x, y };
}

/**
 * 중첩 노드 간 엣지 생성
 */
function createEdgesForNestedNodes(flatNodes: FlattenedNode[]): Edge[] {
  const edges: Edge[] = [];
  const processedEdges = new Set<string>();

  for (const flatNode of flatNodes) {
    const { node, parentId, branchType } = flatNode;

    // 부모 → 자식 연결 (브랜치 타입에 따른 핸들 ID 사용)
    if (parentId && branchType) {
      const edgeId = `${parentId}-${branchType}-${node.id}`;
      if (!processedEdges.has(edgeId)) {
        processedEdges.add(edgeId);
        edges.push({
          id: edgeId,
          source: parentId,
          sourceHandle: branchType === 'then' || branchType === 'else' ? branchType : undefined,
          target: node.id,
          style: {
            stroke: branchType === 'then' ? '#22c55e' :
                    branchType === 'else' ? '#ef4444' :
                    branchType === 'loop' ? '#16a34a' :
                    branchType === 'parallel' ? '#f97316' : '#94a3b8',
            strokeWidth: 2,
          },
          markerEnd: { type: MarkerType.ArrowClosed },
          label: branchType === 'then' ? 'True' : branchType === 'else' ? 'False' : undefined,
          labelStyle: { fontSize: 10, fontWeight: 500 },
        });
      }
    }

    // 기존 next 배열 처리
    if (node.next?.length) {
      for (const nextId of node.next) {
        const edgeId = `${node.id}-next-${nextId}`;
        if (!processedEdges.has(edgeId)) {
          processedEdges.add(edgeId);
          edges.push({
            id: edgeId,
            source: node.id,
            target: nextId,
            style: { strokeWidth: 2, stroke: '#94a3b8' },
            markerEnd: { type: MarkerType.ArrowClosed },
          });
        }
      }
    }
  }

  return edges;
}

// Flow 노드/엣지 → DSL 변환 (중첩 구조 복원)
function flowToDSL(
  nodes: Node<CustomNodeData>[],
  edges: Edge[],
  workflowName: string,
  workflowDescription: string,
  triggerType: 'manual' | 'event' | 'schedule',
  globalSettings: { timeout_seconds: number; max_retry: number; tags: string[] } = {
    timeout_seconds: 300,
    max_retry: 3,
    tags: []
  }
): WorkflowDSL {
  // 트리거 노드 제외
  const workflowNodes = nodes.filter(n => n.data.nodeType !== 'trigger');

  // 노드 ID → 다음 노드 ID 매핑 (next 엣지만)
  const nextMap: Record<string, string[]> = {};
  edges.forEach(edge => {
    // then/else 브랜치 엣지는 next에 포함하지 않음
    if (edge.id.includes('-then-') || edge.id.includes('-else-') ||
        edge.id.includes('-loop-') || edge.id.includes('-parallel-')) {
      return;
    }
    if (!nextMap[edge.source]) nextMap[edge.source] = [];
    if (!nextMap[edge.source].includes(edge.target)) {
      nextMap[edge.source].push(edge.target);
    }
  });

  // 부모-자식 관계 맵 구축
  const childrenMap: Record<string, { then: string[]; else: string[]; loop: string[]; parallel: string[] }> = {};

  for (const node of workflowNodes) {
    const parentId = node.data._parentId;
    const branchType = node.data._branchType;

    if (parentId && branchType) {
      if (!childrenMap[parentId]) {
        childrenMap[parentId] = { then: [], else: [], loop: [], parallel: [] };
      }
      childrenMap[parentId][branchType].push(node.id);
    }
  }

  // 재귀적으로 DSL 노드 구축
  function buildDslNode(flowNode: Node<CustomNodeData>): WorkflowNode {
    const children = childrenMap[flowNode.id];

    // 액션 노드의 경우 config 역정규화 (FlowEditor 형식 → AI DSL 형식)
    let dslConfig = flowNode.data.config;
    if (flowNode.data.nodeType === 'action') {
      const flowConfig = flowNode.data.config as Record<string, unknown>;
      const action = flowConfig.action as string;
      const parameters = (flowConfig.parameters as Record<string, unknown>) || {};
      dslConfig = {
        action_type: action,
        ...parameters,  // parameters를 최상위로 펼침
      };
    }

    const dslNode: WorkflowNode = {
      id: flowNode.id,
      type: flowNode.data.nodeType as WorkflowNode['type'],
      config: dslConfig,
      next: nextMap[flowNode.id] || [],
    };

    // then_nodes 추가
    if (children?.then.length) {
      dslNode.then_nodes = children.then
        .map(id => workflowNodes.find(n => n.id === id))
        .filter(Boolean)
        .map(n => buildDslNode(n as Node<CustomNodeData>));
    }

    // else_nodes 추가
    if (children?.else.length) {
      dslNode.else_nodes = children.else
        .map(id => workflowNodes.find(n => n.id === id))
        .filter(Boolean)
        .map(n => buildDslNode(n as Node<CustomNodeData>));
    }

    // loop_nodes 추가
    if (children?.loop.length) {
      dslNode.loop_nodes = children.loop
        .map(id => workflowNodes.find(n => n.id === id))
        .filter(Boolean)
        .map(n => buildDslNode(n as Node<CustomNodeData>));
    }

    // parallel_nodes 추가
    if (children?.parallel.length) {
      dslNode.parallel_nodes = children.parallel
        .map(id => workflowNodes.find(n => n.id === id))
        .filter(Boolean)
        .map(n => buildDslNode(n as Node<CustomNodeData>));
    }

    return dslNode;
  }

  // 최상위 노드만 DSL로 변환 (부모가 없는 노드)
  const rootNodes = workflowNodes
    .filter(n => !n.data._parentId)
    .map(n => buildDslNode(n));

  return {
    name: workflowName,
    description: workflowDescription,
    trigger: {
      type: triggerType,
      config: {},
    },
    nodes: rootNodes,
    // 글로벌 설정 포함
    timeout_seconds: globalSettings.timeout_seconds,
    max_retry: globalSettings.max_retry,
    tags: globalSettings.tags,
  } as WorkflowDSL & { timeout_seconds: number; max_retry: number; tags: string[] };
}

// DSL → Flow 노드/엣지 변환 (중첩 구조 지원)
function dslToFlow(dsl: WorkflowDSL): { nodes: Node<CustomNodeData>[]; edges: Edge[] } {
  const flowNodes: Node<CustomNodeData>[] = [];
  const edges: Edge[] = [];

  // 1. 트리거 노드 추가
  flowNodes.push({
    id: 'trigger',
    type: 'custom',
    position: { x: 250, y: 0 },
    data: {
      label: '트리거',
      nodeType: 'trigger',
      config: { type: dsl.trigger.type, ...dsl.trigger.config },
    },
  });

  // 2. 모든 중첩 노드를 평탄화
  const flatNodes = flattenNodes(dsl.nodes);

  // 3. 각 노드를 ReactFlow 노드로 변환
  flatNodes.forEach((flatNode, index) => {
    const position = calculateNodePosition(flatNode, index, flatNodes);

    // 액션 노드의 경우 config 정규화 (AI 생성 DSL → FlowEditor 형식)
    let normalizedConfig = flatNode.node.config;
    if (flatNode.node.type === 'action') {
      const rawConfig = flatNode.node.config as Record<string, unknown>;
      const actionType = (rawConfig.action_type as string) || (rawConfig.action as string) || '';

      // 이미 parameters가 있으면 그대로 사용, 없으면 나머지 키들을 parameters로 변환
      let parameters: Record<string, unknown>;
      if (rawConfig.parameters && typeof rawConfig.parameters === 'object') {
        // 백엔드 DSL 형식: { action_type, parameters: {...} }
        parameters = rawConfig.parameters as Record<string, unknown>;
      } else {
        // 레거시/간단 형식: { action_type, channel, message, ... }
        const { action_type: _at, action: _a, parameters: _p, ...rest } = rawConfig;
        parameters = rest;
      }

      normalizedConfig = {
        action: actionType,
        parameters,
      };
    }

    flowNodes.push({
      id: flatNode.node.id,
      type: 'custom',
      position,
      data: {
        label: flatNode.node.id,
        nodeType: flatNode.node.type,
        config: normalizedConfig,
        // 메타데이터 (부모-자식 관계 추적용)
        _parentId: flatNode.parentId,
        _branchType: flatNode.branchType,
        _depth: flatNode.depth,
      },
    });
  });

  // 4. 엣지 생성
  edges.push(...createEdgesForNestedNodes(flatNodes));

  // 5. 트리거 → 첫 번째 최상위 노드 연결
  const firstRootNode = flatNodes.find(f => !f.parentId);
  if (firstRootNode) {
    edges.push({
      id: `trigger-${firstRootNode.node.id}`,
      source: 'trigger',
      target: firstRootNode.node.id,
      style: { strokeWidth: 2, stroke: '#94a3b8' },
      markerEnd: { type: MarkerType.ArrowClosed },
    });
  }

  return { nodes: flowNodes, edges };
}

// ============ Main Component ============

// 타입 단언 헬퍼
type FlowNode = Node<CustomNodeData>;

// 내부 컴포넌트 (useReactFlow 사용을 위해 분리)
function FlowEditorInner({ initialDSL, workflowId: propWorkflowId, onSave, onCancel }: FlowEditorProps) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();
  const toast = useToast();

  // 다크 모드 감지
  const [isDarkMode, setIsDarkMode] = useState(document.documentElement.classList.contains('dark'));

  useEffect(() => {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          setIsDarkMode(document.documentElement.classList.contains('dark'));
        }
      });
    });

    observer.observe(document.documentElement, { attributes: true });
    return () => observer.disconnect();
  }, []);
  // 기본 DSL
  const defaultDSL: WorkflowDSL = {
    name: '새 워크플로우',
    description: '',
    trigger: { type: 'manual', config: {} },
    nodes: [],
  };

  const dsl = initialDSL || defaultDSL;

  // 워크플로우 메타데이터
  const [workflowName, setWorkflowName] = useState(dsl.name);
  const [workflowDescription, setWorkflowDescription] = useState(dsl.description || '');
  const [triggerType, setTriggerType] = useState<'manual' | 'event' | 'schedule'>(dsl.trigger.type);

  // 글로벌 설정 (workflow-level settings)
  const [globalSettings, setGlobalSettings] = useState<{
    timeout_seconds: number;
    max_retry: number;
    tags: string[];
  }>({
    timeout_seconds: (dsl as unknown as { timeout_seconds?: number }).timeout_seconds || 3600,
    max_retry: (dsl as unknown as { max_retry?: number }).max_retry || 3,
    tags: (dsl as unknown as { tags?: string[] }).tags || [],
  });
  const [showGlobalSettings, setShowGlobalSettings] = useState(false);
  const [tagInput, setTagInput] = useState('');

  // Flow 상태 (any 타입 사용하여 호환성 문제 해결)
  const initialFlow = useMemo(() => dslToFlow(dsl), []);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialFlow.nodes as Node[]);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialFlow.edges);

  // 선택된 노드 ID (실제 노드 데이터는 nodes에서 가져옴)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // 선택된 노드 (nodes 배열에서 항상 최신 데이터를 가져옴)
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return (nodes.find(n => n.id === selectedNodeId) as FlowNode) || null;
  }, [selectedNodeId, nodes]);

  // DSL 미리보기 표시 여부
  const [showPreview, setShowPreview] = useState(false);

  // 실행 관련 상태
  const [currentWorkflowId, setCurrentWorkflowId] = useState<string | undefined>(propWorkflowId);
  const [isRunning, setIsRunning] = useState(false);
  const [executionResult, setExecutionResult] = useState<WorkflowInstance | null>(null);
  const [showSimulationModal, setShowSimulationModal] = useState(false);
  const [showExecutionResult, setShowExecutionResult] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // 더블클릭 편집 상태 (향후 인라인 편집 UI 구현 예정)
  const [_editingNode, setEditingNode] = useState<FlowNode | null>(null);
  void _editingNode; // 미사용 경고 방지

  // initialDSL 변경 시 동기화
  useEffect(() => {
    const newDsl = initialDSL || defaultDSL;
    setWorkflowName(newDsl.name);
    setWorkflowDescription(newDsl.description || '');
    setTriggerType(newDsl.trigger.type);
    // 글로벌 설정 동기화
    setGlobalSettings({
      timeout_seconds: (newDsl as unknown as { timeout_seconds?: number }).timeout_seconds || 3600,
      max_retry: (newDsl as unknown as { max_retry?: number }).max_retry || 3,
      tags: (newDsl as unknown as { tags?: string[] }).tags || [],
    });
    const flow = dslToFlow(newDsl);
    setNodes(flow.nodes as Node[]);
    setEdges(flow.edges);
  }, [initialDSL, setNodes, setEdges]);

  // 커스텀 노드 타입 등록
  const nodeTypes: NodeTypes = useMemo(() => ({
    custom: CustomNode,
  }), []);

  // 엣지 연결 핸들러
  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            markerEnd: { type: MarkerType.ArrowClosed },
          },
          eds
        )
      );
    },
    [setEdges]
  );

  // 노드 선택 핸들러
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  // 노드 데이터 업데이트
  const updateNodeData = useCallback((nodeId: string, data: CustomNodeData) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data } : n))
    );
    // selectedNode는 nodes에서 자동으로 최신 데이터를 가져오므로 별도 업데이트 불필요
  }, [setNodes]);

  // 노드 삭제
  const deleteNode = useCallback((nodeId: string) => {
    const nodeToDelete = nodes.find(n => n.id === nodeId);
    const nodeLabel = (nodeToDelete?.data as CustomNodeData)?.label || '노드';
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    setSelectedNodeId(null);
    toast.info(`"${nodeLabel}" 노드가 삭제되었습니다.`);
  }, [setNodes, setEdges, nodes, toast]);

  // 드래그 시작 핸들러
  const onDragStart = useCallback((event: React.DragEvent, nodeType: PaletteNodeType) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  }, []);

  // 드롭 핸들러
  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/reactflow') as PaletteNodeType;
      if (!type || !reactFlowWrapper.current) return;

      // 스크린 좌표를 플로우 좌표로 변환
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      // 새 노드 생성
      const newNode: Node = {
        id: `${type}_${Date.now()}`,
        type: 'custom',
        position,
        data: {
          label: nodeTypeLabels[type],
          nodeType: type,
          config: getDefaultConfig(type),
        },
      };

      setNodes((nds) => [...nds, newNode]);
    },
    [setNodes, screenToFlowPosition]
  );

  const onDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  // 노드 타입별 기본 config
  function getDefaultConfig(type: WorkflowNode['type']): Record<string, unknown> {
    switch (type) {
      // P0 기본 노드
      case 'condition':
        return { condition: '' };
      case 'action':
        return { action: '', parameters: {} };
      case 'if_else':
        return { condition: '', then: [], else: [] };
      case 'loop':
        return { loop_type: 'for', count: 1, nodes: [] };
      case 'parallel':
        return { branches: [[]], fail_fast: false };
      // P1 비즈니스 노드
      case 'data':
        return {
          source_type: 'sensor',
          source: { sensor_ids: [], time_range: '1h' },
          output: { variable: 'data' },
        };
      case 'judgment':
        return {
          policy: { type: 'HYBRID', rule_pack_id: '' },
          input: {},
          output: { variable: 'judgment_result' },
        };
      case 'bi':
        return {
          analysis: { type: 'trend', metrics: [], dimensions: [], time_range: '24h' },
          output: { variable: 'bi_result' },
        };
      case 'mcp':
        return {
          mcp_server_id: '',
          tool_name: '',
          parameters: {},
          timeout_ms: 30000,
          output_variable: 'mcp_result',
        };
      case 'wait':
        return {
          wait_type: 'duration',
          duration_seconds: 60,
        };
      case 'approval':
        return {
          title: '승인 요청',
          description: '',
          approvers: [],
          notification: ['email'],
          timeout_hours: 24,
        };
      // P2 고급 노드
      case 'compensation':
        return {
          compensation_type: 'auto',      // auto | manual
          target_nodes: [],               // 수동 모드 시 대상 노드
          compensation_actions: {},       // 노드별 보상 액션 정의
          on_failure: 'continue',         // continue | abort
        };
      case 'deploy':
        return {
          deploy_type: 'ruleset',  // ruleset | model | workflow
          target_id: '',
          version: undefined,  // undefined = 최신 버전
          environment: 'production',
          rollback_on_failure: true,
          validation: { enabled: false, rules: [] },
        };
      case 'rollback':
        return {
          target_type: 'workflow',
          target_id: '',
          version: null,  // null = 직전 버전
          reason: '',     // 롤백 사유 (감사 로그)
        };
      case 'simulate':
        return {
          simulation_type: 'scenario',
          scenarios: [],
          target_nodes: [],
          metrics: ['success_rate'],
          sweep_config: { parameter: '', start: 0, end: 100, step: 10 },
          iterations: 100,
          distributions: {},
        };
      // 추가 노드
      case 'switch':
        return {
          expression: '',
          cases: [],
          default_node: null,
        };
      case 'code':
        return {
          language: 'python',
          code: '',
          timeout_seconds: 30,
        };
      default:
        return {};
    }
  }

  // 저장 핸들러
  const handleSave = useCallback(async () => {
    const dslResult = flowToDSL(nodes as FlowNode[], edges, workflowName, workflowDescription, triggerType, globalSettings);
    console.log('[FlowEditor] Saving DSL:', JSON.stringify(dslResult, null, 2));
    setIsSaving(true);
    try {
      const result = await onSave?.(dslResult);
      if (result) {
        setCurrentWorkflowId(result);
      }
      toast.success(`워크플로우 "${workflowName}"이(가) 저장되었습니다.`);
      return result;
    } catch (error) {
      toast.error('워크플로우 저장에 실패했습니다.');
      throw error;
    } finally {
      setIsSaving(false);
    }
  }, [nodes, edges, workflowName, workflowDescription, triggerType, onSave, toast]);

  // 저장 후 실행 핸들러
  const handleSaveAndRun = useCallback(async () => {
    try {
      const savedId = await handleSave();
      const wfId = savedId || currentWorkflowId;
      if (wfId) {
        setShowSimulationModal(true);
      } else {
        toast.warning('먼저 워크플로우를 저장해주세요.');
      }
    } catch {
      // handleSave에서 이미 에러 토스트를 표시함
    }
  }, [handleSave, currentWorkflowId, toast]);

  // 워크플로우 실행 핸들러
  const handleRunWorkflow = useCallback(async (inputData: Record<string, unknown>) => {
    if (!currentWorkflowId) {
      toast.warning('워크플로우 ID가 없습니다. 먼저 저장해주세요.');
      return;
    }

    setShowSimulationModal(false);
    setIsRunning(true);
    setShowExecutionResult(true);
    setExecutionResult(null);

    // 모든 노드를 idle 상태로 리셋
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, executionStatus: 'idle' as NodeExecutionStatus },
      }))
    );

    try {
      // 워크플로우 실행
      const result = await workflowService.run(currentWorkflowId, {
        input_data: inputData,
      });

      setExecutionResult(result);
      toast.success('워크플로우 실행이 완료되었습니다.');

      // 실행 결과에 따라 노드 상태 업데이트
      const outputData = result.output_data as {
        results?: Array<{ node_id: string; status: string }>;
      };

      if (outputData?.results) {
        setNodes((nds) =>
          nds.map((n) => {
            const nodeResult = outputData.results?.find((r) => r.node_id === n.id);
            if (nodeResult) {
              const status: NodeExecutionStatus =
                nodeResult.status === 'success' ? 'completed' :
                nodeResult.status === 'skipped' ? 'skipped' : 'failed';
              return { ...n, data: { ...n.data, executionStatus: status } };
            }
            return n;
          })
        );
      }
    } catch (error) {
      console.error('Workflow execution failed:', error);
      toast.error('워크플로우 실행에 실패했습니다.');
      setExecutionResult({
        instance_id: '',
        workflow_id: currentWorkflowId,
        workflow_name: workflowName,
        status: 'failed',
        input_data: inputData,
        output_data: {},
        error_message: error instanceof Error ? error.message : '실행 실패',
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
      });
    } finally {
      setIsRunning(false);
    }
  }, [currentWorkflowId, workflowName, setNodes, toast]);

  // 노드 더블클릭 핸들러 (인라인 편집)
  const onNodeDoubleClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.data.nodeType !== 'trigger') {
      setEditingNode(node as FlowNode);
      setSelectedNodeId(node.id);
    }
  }, []);

  // 키보드 핸들러 (Delete/Backspace로 노드 삭제)
  const onKeyDown = useCallback(async (event: React.KeyboardEvent) => {
    if ((event.key === 'Delete' || event.key === 'Backspace') && selectedNodeId) {
      // 입력 필드에서는 삭제 동작 방지
      const target = event.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') {
        return;
      }

      const nodeToDelete = nodes.find(n => n.id === selectedNodeId);
      if (nodeToDelete && (nodeToDelete.data as CustomNodeData).nodeType !== 'trigger') {
        event.preventDefault();
        const confirmed = await toast.confirm({
          title: '노드 삭제',
          message: '선택된 노드를 삭제하시겠습니까?',
          confirmText: '삭제',
          cancelText: '취소',
          variant: 'danger',
        });
        if (confirmed) {
          deleteNode(selectedNodeId);
        }
      }
    }
  }, [selectedNodeId, nodes, deleteNode, toast]);

  // 현재 DSL 미리보기
  const currentDSL = useMemo(
    () => flowToDSL(nodes as FlowNode[], edges, workflowName, workflowDescription, triggerType, globalSettings),
    [nodes, edges, workflowName, workflowDescription, triggerType, globalSettings]
  );

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onCancel} />

      {/* Editor Container */}
      <div className="relative flex w-full h-full m-4 bg-white dark:bg-slate-900 rounded-xl shadow-2xl overflow-hidden">
        {/* Left Sidebar - Node Palette */}
        <div className="w-56 p-4 border-r border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          <NodePalette onDragStart={onDragStart} />

          {/* 트리거 설정 */}
          <div className="mt-6 space-y-2">
            <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              트리거
            </h3>
            <select
              value={triggerType}
              onChange={(e) => setTriggerType(e.target.value as 'manual' | 'event' | 'schedule')}
              className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
            >
              <option value="manual">수동 실행</option>
              <option value="event">이벤트 기반</option>
              <option value="schedule">스케줄 기반</option>
            </select>
          </div>
        </div>

        {/* Main Canvas */}
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
            <div className="flex items-center gap-3">
              <GitBranch className="w-6 h-6 text-blue-500" />
              <div>
                <input
                  type="text"
                  value={workflowName}
                  onChange={(e) => setWorkflowName(e.target.value)}
                  className="text-lg font-semibold bg-transparent border-none focus:outline-none focus:ring-0"
                  placeholder="워크플로우 이름"
                />
                <input
                  type="text"
                  value={workflowDescription}
                  onChange={(e) => setWorkflowDescription(e.target.value)}
                  className="block text-sm text-slate-500 bg-transparent border-none focus:outline-none focus:ring-0 w-64"
                  placeholder="설명을 입력하세요..."
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowGlobalSettings(!showGlobalSettings)}
                className={`flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors ${
                  showGlobalSettings
                    ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                }`}
                title="글로벌 설정"
              >
                <Settings className="w-4 h-4" />
                설정
              </button>
              <button
                onClick={() => setShowPreview(!showPreview)}
                className={`flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors ${
                  showPreview
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                }`}
              >
                <Eye className="w-4 h-4" />
                DSL
              </button>
              <button
                onClick={onCancel}
                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* 글로벌 설정 패널 */}
          {showGlobalSettings && (
            <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* 타임아웃 설정 */}
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                    <Timer className="w-4 h-4" />
                    <label className="text-sm font-medium">타임아웃</label>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      value={globalSettings.timeout_seconds}
                      onChange={(e) => setGlobalSettings(prev => ({
                        ...prev,
                        timeout_seconds: parseInt(e.target.value) || 3600
                      }))}
                      min={60}
                      max={86400}
                      className="w-24 px-2 py-1 text-sm border rounded dark:bg-slate-800 dark:border-slate-600 text-slate-900 dark:text-slate-100"
                    />
                    <span className="text-xs text-slate-500">초</span>
                  </div>
                </div>

                {/* 최대 재시도 설정 */}
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                    <RefreshCw className="w-4 h-4" />
                    <label className="text-sm font-medium">최대 재시도</label>
                  </div>
                  <input
                    type="number"
                    value={globalSettings.max_retry}
                    onChange={(e) => setGlobalSettings(prev => ({
                      ...prev,
                      max_retry: parseInt(e.target.value) || 3
                    }))}
                    min={0}
                    max={10}
                    className="w-16 px-2 py-1 text-sm border rounded dark:bg-slate-800 dark:border-slate-600 text-slate-900 dark:text-slate-100"
                  />
                </div>

                {/* 태그 설정 */}
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                    <Tag className="w-4 h-4" />
                    <label className="text-sm font-medium">태그</label>
                  </div>
                  <div className="flex-1 flex flex-wrap items-center gap-1">
                    {globalSettings.tags.map((tag, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full"
                      >
                        {tag}
                        <button
                          onClick={() => setGlobalSettings(prev => ({
                            ...prev,
                            tags: prev.tags.filter((_, i) => i !== idx)
                          }))}
                          className="hover:text-red-500"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                    <input
                      type="text"
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && tagInput.trim()) {
                          e.preventDefault();
                          if (!globalSettings.tags.includes(tagInput.trim())) {
                            setGlobalSettings(prev => ({
                              ...prev,
                              tags: [...prev.tags, tagInput.trim()]
                            }));
                          }
                          setTagInput('');
                        }
                      }}
                      placeholder="Enter로 추가..."
                      className="w-24 px-2 py-0.5 text-xs border rounded dark:bg-slate-800 dark:border-slate-600 text-slate-900 dark:text-slate-100"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* React Flow Canvas */}
          <div className="flex-1 outline-none" ref={reactFlowWrapper} tabIndex={0} onKeyDown={onKeyDown}>
            <ReactFlow
              onDrop={onDrop}
              onDragOver={onDragOver}
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              onNodeDoubleClick={onNodeDoubleClick}
              nodeTypes={nodeTypes}
              fitView
              snapToGrid
              snapGrid={[15, 15]}
              defaultEdgeOptions={{
                style: { strokeWidth: 2, stroke: '#94a3b8' },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
              }}
            >
              <Background color={isDarkMode ? "#334155" : "#e2e8f0"} gap={15} />
              <Controls />
              <MiniMap
                nodeColor={(node) => {
                  const colors: Record<string, string> = {
                    condition: '#fbbf24',
                    action: '#3b82f6',
                    if_else: '#a855f7',
                    loop: '#22c55e',
                    parallel: '#f97316',
                    trigger: '#10b981',
                  };
                  return colors[(node.data as CustomNodeData).nodeType] || '#64748b';
                }}
              />

              {/* 노드 설정 패널 */}
              {selectedNode && selectedNode.data.nodeType !== 'trigger' && (
                <Panel position="top-right">
                  <NodeConfigPanel
                    node={selectedNode}
                    onUpdate={updateNodeData}
                    onClose={() => setSelectedNodeId(null)}
                    onDelete={deleteNode}
                  />
                </Panel>
              )}

              {/* DSL 미리보기 패널 */}
              {showPreview && (
                <Panel position="bottom-right">
                  <div className="w-80 max-h-64 bg-slate-900 rounded-lg shadow-lg overflow-hidden">
                    <div className="p-2 border-b border-slate-700 flex justify-between items-center">
                      <span className="text-xs text-slate-400">DSL 미리보기</span>
                      <span className="text-xs text-green-400">
                        {currentDSL.nodes.length}개 노드
                      </span>
                    </div>
                    <pre className="p-3 text-xs font-mono text-slate-100 overflow-auto max-h-52">
                      {JSON.stringify(currentDSL, null, 2)}
                    </pre>
                  </div>
                </Panel>
              )}

              {/* 실행 결과 패널 */}
              {showExecutionResult && (
                <Panel position="bottom-left">
                  <ExecutionResultPanel
                    result={executionResult}
                    isRunning={isRunning}
                    onClose={() => setShowExecutionResult(false)}
                  />
                </Panel>
              )}
            </ReactFlow>
          </div>

          {/* Footer */}
          <div className="flex justify-between items-center p-4 border-t border-slate-200 dark:border-slate-700">
            <div className="text-xs text-slate-500">
              {currentWorkflowId && (
                <span className="bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
                  ID: {currentWorkflowId.slice(0, 8)}...
                </span>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={onCancel}
                className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700"
              >
                취소
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                저장
              </button>
              <button
                onClick={handleSaveAndRun}
                disabled={isSaving || isRunning}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                {isRunning ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                저장 & 실행
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 시뮬레이션 모달 */}
      <SimulationModal
        isOpen={showSimulationModal}
        onClose={() => setShowSimulationModal(false)}
        onRun={handleRunWorkflow}
      />
    </div>
  );
}

// 외부 컴포넌트: ReactFlowProvider로 감싸기
export function FlowEditor(props: FlowEditorProps) {
  if (!props.isOpen) return null;

  return (
    <ReactFlowProvider>
      <FlowEditorInner {...props} />
    </ReactFlowProvider>
  );
}
