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
} from 'lucide-react';
import type { WorkflowDSL, WorkflowNode, WorkflowInstance } from '@/services/workflowService';
import { workflowService } from '@/services/workflowService';

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

// 커스텀 노드 데이터 타입 (index signature 추가)
interface CustomNodeData {
  label: string;
  nodeType: NodeType;
  config: Record<string, unknown>;
  executionStatus?: NodeExecutionStatus;
  [key: string]: unknown;
}

// ============ Constants ============

const nodeTypeColors: Record<string, { bg: string; border: string; text: string }> = {
  condition: { bg: 'bg-yellow-50 dark:bg-yellow-900/30', border: 'border-yellow-400', text: 'text-yellow-700 dark:text-yellow-400' },
  action: { bg: 'bg-blue-50 dark:bg-blue-900/30', border: 'border-blue-400', text: 'text-blue-700 dark:text-blue-400' },
  if_else: { bg: 'bg-purple-50 dark:bg-purple-900/30', border: 'border-purple-400', text: 'text-purple-700 dark:text-purple-400' },
  loop: { bg: 'bg-green-50 dark:bg-green-900/30', border: 'border-green-400', text: 'text-green-700 dark:text-green-400' },
  parallel: { bg: 'bg-orange-50 dark:bg-orange-900/30', border: 'border-orange-400', text: 'text-orange-700 dark:text-orange-400' },
  trigger: { bg: 'bg-emerald-50 dark:bg-emerald-900/30', border: 'border-emerald-400', text: 'text-emerald-700 dark:text-emerald-400' },
};

const nodeTypeLabels: Record<string, string> = {
  condition: '조건',
  action: '액션',
  if_else: 'If/Else',
  loop: '반복',
  parallel: '병렬',
  trigger: '트리거',
};

const nodeTypeIcons: Record<string, typeof AlertTriangle> = {
  condition: AlertTriangle,
  action: Zap,
  if_else: Split,
  loop: Repeat,
  parallel: Layers,
  trigger: Play,
};

// 액션 한글 이름 매핑
const actionLabels: Record<string, string> = {
  send_slack_notification: 'Slack 알림',
  send_email: '이메일 발송',
  send_sms: 'SMS 발송',
  save_to_database: 'DB 저장',
  export_to_csv: 'CSV 내보내기',
  log_event: '로그 기록',
  stop_production_line: '라인 정지',
  adjust_sensor_threshold: '임계값 조정',
  trigger_maintenance: '유지보수 요청',
  calculate_defect_rate: '불량률 계산',
  analyze_sensor_trend: '추세 분석',
  predict_equipment_failure: '고장 예측',
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
      case 'condition':
        return (config.condition as string) || '조건 미설정';
      case 'action':
        return actionLabels[(config.action as string) || ''] || (config.action as string) || '액션 미설정';
      case 'if_else':
        return (config.condition as string) || 'If/Else';
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
type PaletteNodeType = 'condition' | 'action' | 'if_else' | 'loop' | 'parallel';

interface NodePaletteProps {
  onDragStart: (event: React.DragEvent, nodeType: PaletteNodeType) => void;
}

function NodePalette({ onDragStart }: NodePaletteProps) {
  const nodeTypes: PaletteNodeType[] = ['condition', 'action', 'if_else', 'loop', 'parallel'];

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
        노드 추가
      </h3>
      <div className="space-y-1">
        {nodeTypes.map((type) => {
          const colors = nodeTypeColors[type];
          const Icon = nodeTypeIcons[type];
          return (
            <div
              key={type}
              draggable
              onDragStart={(e) => onDragStart(e, type)}
              className={`
                flex items-center gap-2 px-3 py-2 rounded-lg border-2 cursor-grab
                ${colors.bg} ${colors.border}
                hover:shadow-md transition-shadow
              `}
            >
              <Icon className={`w-4 h-4 ${colors.text}`} />
              <span className={`text-sm font-medium ${colors.text}`}>
                {nodeTypeLabels[type]}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============ Node Config Panel ============

interface NodeConfigPanelProps {
  node: Node<CustomNodeData> | null;
  onUpdate: (nodeId: string, data: CustomNodeData) => void;
  onClose: () => void;
}

function NodeConfigPanel({ node, onUpdate, onClose }: NodeConfigPanelProps) {
  if (!node) return null;

  const data = node.data;
  const nodeType = data.nodeType;

  const updateConfig = (key: string, value: unknown) => {
    onUpdate(node.id, {
      ...data,
      config: { ...data.config, [key]: value },
    });
  };

  return (
    <div className="w-72 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
      <div className="flex items-center justify-between p-3 border-b border-slate-200 dark:border-slate-700">
        <h3 className="text-sm font-semibold">노드 설정</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-3 space-y-3 max-h-[400px] overflow-y-auto">
        {/* 조건 노드 */}
        {nodeType === 'condition' && (
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              조건식
            </label>
            <input
              type="text"
              value={(data.config.condition as string) || ''}
              onChange={(e) => updateConfig('condition', e.target.value)}
              className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
              placeholder="temperature > 80"
            />
          </div>
        )}

        {/* 액션 노드 */}
        {nodeType === 'action' && (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                액션
              </label>
              <select
                value={(data.config.action as string) || ''}
                onChange={(e) => updateConfig('action', e.target.value)}
                className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
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
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                파라미터 (JSON)
              </label>
              <textarea
                value={JSON.stringify(data.config.parameters || {}, null, 2)}
                onChange={(e) => {
                  try {
                    updateConfig('parameters', JSON.parse(e.target.value));
                  } catch {
                    // ignore parse error while typing
                  }
                }}
                className="w-full px-3 py-2 text-xs font-mono border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 h-20"
                placeholder='{"message": "알림 내용"}'
              />
            </div>
          </>
        )}

        {/* If/Else 노드 */}
        {nodeType === 'if_else' && (
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              분기 조건
            </label>
            <input
              type="text"
              value={(data.config.condition as string) || ''}
              onChange={(e) => updateConfig('condition', e.target.value)}
              className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
              placeholder="temperature > 80"
            />
            <p className="mt-1 text-xs text-slate-500">
              참이면 then, 거짓이면 else 브랜치 실행
            </p>
          </div>
        )}

        {/* Loop 노드 */}
        {nodeType === 'loop' && (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                반복 유형
              </label>
              <select
                value={(data.config.loop_type as string) || 'for'}
                onChange={(e) => updateConfig('loop_type', e.target.value)}
                className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
              >
                <option value="for">횟수 반복</option>
                <option value="while">조건 반복</option>
              </select>
            </div>
            {(data.config.loop_type as string) === 'while' ? (
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                  반복 조건
                </label>
                <input
                  type="text"
                  value={(data.config.condition as string) || ''}
                  onChange={(e) => updateConfig('condition', e.target.value)}
                  className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
                  placeholder="retry_count < 3"
                />
              </div>
            ) : (
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                  반복 횟수
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={(data.config.count as number) || 1}
                  onChange={(e) => updateConfig('count', parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
                />
              </div>
            )}
          </>
        )}

        {/* Parallel 노드 */}
        {nodeType === 'parallel' && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <input
                type="checkbox"
                id="fail_fast"
                checked={(data.config.fail_fast as boolean) || false}
                onChange={(e) => updateConfig('fail_fast', e.target.checked)}
                className="rounded border-slate-300"
              />
              <label htmlFor="fail_fast" className="text-xs text-slate-600 dark:text-slate-400">
                실패 시 즉시 중단
              </label>
            </div>
            <p className="text-xs text-slate-500">
              병렬 브랜치는 연결된 노드들로 자동 구성됩니다.
            </p>
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

// Flow 노드/엣지 → DSL 변환
function flowToDSL(
  nodes: Node<CustomNodeData>[],
  edges: Edge[],
  workflowName: string,
  workflowDescription: string,
  triggerType: 'manual' | 'event' | 'schedule'
): WorkflowDSL {
  // 트리거 노드 제외한 노드만 추출
  const workflowNodes = nodes.filter(n => n.data.nodeType !== 'trigger');

  // 노드 ID → 다음 노드 ID 매핑 생성
  const nextMap: Record<string, string[]> = {};
  edges.forEach(edge => {
    if (!nextMap[edge.source]) nextMap[edge.source] = [];
    nextMap[edge.source].push(edge.target);
  });

  const dslNodes: WorkflowNode[] = workflowNodes.map(node => ({
    id: node.id,
    type: node.data.nodeType as WorkflowNode['type'],
    config: node.data.config,
    next: nextMap[node.id] || [],
  }));

  return {
    name: workflowName,
    description: workflowDescription,
    trigger: {
      type: triggerType,
      config: {},
    },
    nodes: dslNodes,
  };
}

// DSL → Flow 노드/엣지 변환
function dslToFlow(dsl: WorkflowDSL): { nodes: Node<CustomNodeData>[]; edges: Edge[] } {
  const nodes: Node<CustomNodeData>[] = [];
  const edges: Edge[] = [];

  // 트리거 노드 추가
  nodes.push({
    id: 'trigger',
    type: 'custom',
    position: { x: 250, y: 0 },
    data: {
      label: '트리거',
      nodeType: 'trigger',
      config: { type: dsl.trigger.type, ...dsl.trigger.config },
    },
  });

  // 워크플로우 노드 추가
  dsl.nodes.forEach((node, index) => {
    nodes.push({
      id: node.id,
      type: 'custom',
      position: { x: 250, y: 100 + index * 120 },
      data: {
        label: node.id,
        nodeType: node.type,
        config: node.config,
      },
    });

    // 엣지 생성
    node.next.forEach(nextId => {
      edges.push({
        id: `${node.id}-${nextId}`,
        source: node.id,
        target: nextId,
        markerEnd: { type: MarkerType.ArrowClosed },
      });
    });
  });

  // 트리거 → 첫 번째 노드 연결
  if (dsl.nodes.length > 0) {
    edges.push({
      id: `trigger-${dsl.nodes[0].id}`,
      source: 'trigger',
      target: dsl.nodes[0].id,
      markerEnd: { type: MarkerType.ArrowClosed },
    });
  }

  return { nodes, edges };
}

// ============ Main Component ============

// 타입 단언 헬퍼
type FlowNode = Node<CustomNodeData>;

// 내부 컴포넌트 (useReactFlow 사용을 위해 분리)
function FlowEditorInner({ initialDSL, workflowId: propWorkflowId, onSave, onCancel }: FlowEditorProps) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();
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

  // Flow 상태 (any 타입 사용하여 호환성 문제 해결)
  const initialFlow = useMemo(() => dslToFlow(dsl), []);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialFlow.nodes as Node[]);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialFlow.edges);

  // 선택된 노드
  const [selectedNode, setSelectedNode] = useState<FlowNode | null>(null);

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
    setSelectedNode(node as FlowNode);
  }, []);

  // 노드 데이터 업데이트
  const updateNodeData = useCallback((nodeId: string, data: CustomNodeData) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data } : n))
    );
    setSelectedNode((prev) => (prev?.id === nodeId ? { ...prev, data } : prev));
  }, [setNodes]);

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
      default:
        return {};
    }
  }

  // 저장 핸들러
  const handleSave = useCallback(async () => {
    const dslResult = flowToDSL(nodes as FlowNode[], edges, workflowName, workflowDescription, triggerType);
    console.log('[FlowEditor] Saving DSL:', JSON.stringify(dslResult, null, 2));
    setIsSaving(true);
    try {
      const result = await onSave?.(dslResult);
      if (result) {
        setCurrentWorkflowId(result);
      }
      return result;
    } finally {
      setIsSaving(false);
    }
  }, [nodes, edges, workflowName, workflowDescription, triggerType, onSave]);

  // 저장 후 실행 핸들러
  const handleSaveAndRun = useCallback(async () => {
    const savedId = await handleSave();
    const wfId = savedId || currentWorkflowId;
    if (wfId) {
      setShowSimulationModal(true);
    } else {
      alert('먼저 워크플로우를 저장해주세요.');
    }
  }, [handleSave, currentWorkflowId]);

  // 워크플로우 실행 핸들러
  const handleRunWorkflow = useCallback(async (inputData: Record<string, unknown>) => {
    if (!currentWorkflowId) {
      alert('워크플로우 ID가 없습니다. 먼저 저장해주세요.');
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
  }, [currentWorkflowId, workflowName, setNodes]);

  // 노드 더블클릭 핸들러 (인라인 편집)
  const onNodeDoubleClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.data.nodeType !== 'trigger') {
      setEditingNode(node as FlowNode);
      setSelectedNode(node as FlowNode);
    }
  }, []);

  // 현재 DSL 미리보기
  const currentDSL = useMemo(
    () => flowToDSL(nodes as FlowNode[], edges, workflowName, workflowDescription, triggerType),
    [nodes, edges, workflowName, workflowDescription, triggerType]
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
              className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
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

          {/* React Flow Canvas */}
          <div className="flex-1" ref={reactFlowWrapper}>
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
              <Background color="#e2e8f0" gap={15} />
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
                    onClose={() => setSelectedNode(null)}
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
