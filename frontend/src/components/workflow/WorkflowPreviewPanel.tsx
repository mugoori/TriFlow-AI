/**
 * WorkflowPreviewPanel Component
 * 채팅에서 AI가 생성한 워크플로우를 미리보기하고 피드백을 주는 사이드 패널
 * 노드 선택 및 인라인 편집 기능 포함
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  X,
  Check,
  MessageSquare,
  ChevronDown,
  ChevronRight,
  Play,
  GitBranch,
  Repeat,
  Layers,
  Zap,
  ExternalLink,
  Settings,
} from 'lucide-react';

// 워크플로우 DSL 타입 정의
interface WorkflowNode {
  id: string;
  type: 'condition' | 'action' | 'if_else' | 'loop' | 'parallel';
  config: Record<string, unknown>;
  next?: string[];
  then_nodes?: WorkflowNode[];
  else_nodes?: WorkflowNode[];
  loop_nodes?: WorkflowNode[];
  parallel_nodes?: WorkflowNode[];
}

interface WorkflowTrigger {
  type: 'event' | 'schedule' | 'manual';
  config?: Record<string, unknown>;
}

export interface WorkflowDSL {
  name?: string;
  description?: string;
  trigger: WorkflowTrigger;
  nodes: WorkflowNode[];
}

interface WorkflowPreviewPanelProps {
  dsl: WorkflowDSL | null;
  workflowId?: string;
  workflowName?: string;
  isOpen: boolean;
  onApply: () => void;
  onRequestModification: (feedback: string) => void;
  onClose: () => void;
  onDslUpdate?: (updatedDsl: WorkflowDSL) => void;
}

// 노드 타입별 아이콘
const NodeIcon = ({ type }: { type: string }) => {
  switch (type) {
    case 'condition':
      return <GitBranch className="w-4 h-4 text-yellow-600" />;
    case 'action':
      return <Zap className="w-4 h-4 text-blue-600" />;
    case 'if_else':
      return <GitBranch className="w-4 h-4 text-purple-600" />;
    case 'loop':
      return <Repeat className="w-4 h-4 text-green-600" />;
    case 'parallel':
      return <Layers className="w-4 h-4 text-orange-600" />;
    default:
      return <Play className="w-4 h-4 text-slate-500" />;
  }
};

// 노드 타입별 라벨
const nodeTypeLabels: Record<string, string> = {
  condition: '조건',
  action: '액션',
  if_else: '조건 분기',
  loop: '반복',
  parallel: '병렬 실행',
};

// 연산자 옵션
const operatorOptions = [
  { value: '>=', label: '>= (이상)' },
  { value: '<=', label: '<= (이하)' },
  { value: '>', label: '> (초과)' },
  { value: '<', label: '< (미만)' },
  { value: '==', label: '== (같음)' },
  { value: '!=', label: '!= (다름)' },
];

// 액션 타입 옵션
const actionTypeOptions = [
  { value: 'send_slack_notification', label: 'Slack 알림 전송' },
  { value: 'stop_production_line', label: '생산라인 중지' },
  { value: 'send_email', label: '이메일 전송' },
  { value: 'log_event', label: '이벤트 로깅' },
  { value: 'call_api', label: 'API 호출' },
];

// ============ NodePropertyPanel 컴포넌트 ============

interface NodePropertyPanelProps {
  node: WorkflowNode;
  onUpdate: (updatedNode: WorkflowNode) => void;
  onClose: () => void;
  onDetailEdit: () => void;
}

function NodePropertyPanel({ node, onUpdate, onClose, onDetailEdit }: NodePropertyPanelProps) {
  const [localConfig, setLocalConfig] = useState<Record<string, unknown>>(node.config);

  // node.config 내용이 변경되면 localConfig 동기화
  // node 객체 참조 대신 node.id + config 내용을 비교하여 정확한 변경 감지
  useEffect(() => {
    setLocalConfig(node.config);
  }, [node.id, JSON.stringify(node.config)]);

  const handleConfigChange = useCallback((key: string, value: unknown) => {
    const newConfig = { ...localConfig, [key]: value };
    setLocalConfig(newConfig);
    onUpdate({ ...node, config: newConfig });
  }, [localConfig, node, onUpdate]);

  const handleConditionChange = useCallback((field: string, value: unknown) => {
    const currentCondition = (localConfig.condition as Record<string, unknown>) || {};
    const newCondition = { ...currentCondition, [field]: value };
    handleConfigChange('condition', newCondition);
  }, [localConfig, handleConfigChange]);

  // if_else 노드 편집 UI
  const renderIfElseEditor = () => {
    const condition = (localConfig.condition as { field?: string; operator?: string; value?: unknown }) || {};

    return (
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
            필드
          </label>
          <input
            type="text"
            value={condition.field || ''}
            onChange={(e) => handleConditionChange('field', e.target.value)}
            className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="예: temperature"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
            연산자
          </label>
          <select
            value={condition.operator || '>='}
            onChange={(e) => handleConditionChange('operator', e.target.value)}
            className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {operatorOptions.map((op) => (
              <option key={op.value} value={op.value}>{op.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
            값
          </label>
          <input
            type="text"
            value={String(condition.value ?? '')}
            onChange={(e) => {
              const val = e.target.value;
              // 숫자인 경우 숫자로 변환
              const numVal = Number(val);
              handleConditionChange('value', isNaN(numVal) ? val : numVal);
            }}
            className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="예: 80"
          />
        </div>
      </div>
    );
  };

  // 파라미터 변경 핸들러 (config.parameters 내부 값 수정)
  const handleParameterChange = useCallback((key: string, value: unknown) => {
    const currentParams = (localConfig.parameters as Record<string, unknown>) || {};
    const newParams = { ...currentParams, [key]: value };
    handleConfigChange('parameters', newParams);
  }, [localConfig, handleConfigChange]);

  // action 노드 편집 UI
  const renderActionEditor = () => {
    const actionType = (localConfig.action_type as string) || (localConfig.action as string) || '';

    // parameters 객체에서 값 읽기 (백엔드 DSL 구조에 맞춤)
    const parameters = (localConfig.parameters as Record<string, unknown>) || {};
    const channel = (parameters.channel as string) || (localConfig.channel as string) || '';
    const lineCode = (parameters.line_code as string) || (localConfig.line_code as string) || '';
    const message = (parameters.message as string) || (localConfig.message as string) || '';
    const reason = (parameters.reason as string) || (localConfig.reason as string) || '';
    const equipmentId = (parameters.equipment_id as string) || (localConfig.equipment_id as string) || '';
    const emailTo = (parameters.to as string) || (localConfig.to as string) || '';
    const emailSubject = (parameters.subject as string) || (localConfig.subject as string) || '';

    return (
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
            액션 타입
          </label>
          <select
            value={actionType}
            onChange={(e) => {
              handleConfigChange('action_type', e.target.value);
              handleConfigChange('action', e.target.value);
            }}
            className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">선택...</option>
            {actionTypeOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* Slack 알림 파라미터 - parameters에 값이 있거나 actionType이 맞으면 표시 */}
        {(parameters.channel !== undefined || actionType === 'send_slack_notification') && (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                채널 *
              </label>
              <input
                type="text"
                value={channel}
                onChange={(e) => handleParameterChange('channel', e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="#채널명"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                메시지 *
              </label>
              <textarea
                value={message}
                onChange={(e) => handleParameterChange('message', e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                rows={2}
                placeholder="알림 메시지..."
              />
            </div>
          </>
        )}

        {/* 라인 정지 파라미터 - parameters에 값이 있거나 actionType이 맞으면 표시 */}
        {(parameters.line_code !== undefined || actionType === 'stop_production_line') && (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                라인 ID *
              </label>
              <input
                type="text"
                value={lineCode}
                onChange={(e) => handleParameterChange('line_code', e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="LINE_001"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                정지 사유
              </label>
              <textarea
                value={reason}
                onChange={(e) => handleParameterChange('reason', e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                rows={2}
                placeholder="정지 사유..."
              />
            </div>
          </>
        )}

        {/* 유지보수 트리거 파라미터 - parameters에 값이 있거나 actionType이 맞으면 표시 */}
        {(parameters.equipment_id !== undefined || actionType === 'trigger_maintenance') && (
          <div>
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
              장비 ID *
            </label>
            <input
              type="text"
              value={equipmentId}
              onChange={(e) => handleParameterChange('equipment_id', e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="EQUIP_001"
            />
          </div>
        )}

        {/* 이메일 전송 파라미터 - parameters에 값이 있거나 actionType이 맞으면 표시 */}
        {(parameters.to !== undefined || actionType === 'send_email') && (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                수신자 *
              </label>
              <input
                type="text"
                value={emailTo}
                onChange={(e) => handleParameterChange('to', e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="email@example.com"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                제목 *
              </label>
              <input
                type="text"
                value={emailSubject}
                onChange={(e) => handleParameterChange('subject', e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="이메일 제목"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                본문 *
              </label>
              <textarea
                value={message}
                onChange={(e) => handleParameterChange('message', e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                rows={2}
                placeholder="이메일 본문..."
              />
            </div>
          </>
        )}
      </div>
    );
  };

  // condition 노드 편집 UI
  const renderConditionEditor = () => {
    const condition = (localConfig.condition as string) || '';

    return (
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
            조건식
          </label>
          <input
            type="text"
            value={condition}
            onChange={(e) => handleConfigChange('condition', e.target.value)}
            className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="예: temperature > 80"
          />
        </div>
      </div>
    );
  };

  // loop 노드 편집 UI
  const renderLoopEditor = () => {
    const loopType = (localConfig.loop_type as string) || 'for';
    const count = (localConfig.count as number) || 1;

    return (
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
            반복 타입
          </label>
          <select
            value={loopType}
            onChange={(e) => handleConfigChange('loop_type', e.target.value)}
            className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="for">횟수 반복</option>
            <option value="while">조건 반복</option>
          </select>
        </div>
        {loopType === 'for' && (
          <div>
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
              반복 횟수
            </label>
            <input
              type="number"
              value={count}
              onChange={(e) => handleConfigChange('count', Number(e.target.value))}
              min={1}
              className="w-full px-2 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        )}
      </div>
    );
  };

  const renderEditor = () => {
    switch (node.type) {
      case 'if_else':
        return renderIfElseEditor();
      case 'action':
        return renderActionEditor();
      case 'condition':
        return renderConditionEditor();
      case 'loop':
        return renderLoopEditor();
      default:
        return (
          <div className="text-sm text-slate-500 dark:text-slate-400">
            이 노드 타입은 인라인 편집을 지원하지 않습니다.
          </div>
        );
    }
  };

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800/50 overflow-hidden">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-100 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4 text-slate-500" />
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
            노드 속성: {node.id}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-0.5 hover:bg-slate-200 dark:hover:bg-slate-700 rounded"
        >
          <X className="w-4 h-4 text-slate-500" />
        </button>
      </div>

      {/* 내용 */}
      <div className="p-3 space-y-3">
        {/* 노드 타입 표시 */}
        <div className="flex items-center gap-2">
          <NodeIcon type={node.type} />
          <span className="text-sm text-slate-600 dark:text-slate-400">
            {nodeTypeLabels[node.type] || node.type}
          </span>
        </div>

        {/* 에디터 */}
        {renderEditor()}

        {/* 상세 편집 버튼 */}
        <button
          onClick={onDetailEdit}
          className="w-full px-3 py-1.5 text-sm border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 rounded hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
        >
          상세 편집 (FlowEditor)
        </button>
      </div>
    </div>
  );
}

// ============ NodeTreeItem 컴포넌트 ============

interface NodeTreeItemProps {
  node: WorkflowNode;
  depth?: number;
  selectedNodeId?: string;
  onSelectNode: (node: WorkflowNode) => void;
}

function NodeTreeItem({ node, depth = 0, selectedNodeId, onSelectNode }: NodeTreeItemProps) {
  const [expanded, setExpanded] = useState(true);
  const isSelected = selectedNodeId === node.id;

  const hasChildren =
    (node.then_nodes && node.then_nodes.length > 0) ||
    (node.else_nodes && node.else_nodes.length > 0) ||
    (node.loop_nodes && node.loop_nodes.length > 0) ||
    (node.parallel_nodes && node.parallel_nodes.length > 0);

  const getNodeLabel = () => {
    if (node.type === 'action') {
      const actionType = (node.config as { action_type?: string })?.action_type ||
                        (node.config as { action?: string })?.action ||
                        'action';
      return actionType.replace(/_/g, ' ');
    }
    if (node.type === 'condition') {
      const condition = (node.config as { condition?: string })?.condition || 'condition';
      return condition;
    }
    if (node.type === 'if_else') {
      const condition = (node.config as { condition?: { field?: string; operator?: string; value?: unknown } })?.condition;
      if (condition && typeof condition === 'object') {
        return `if ${condition.field} ${condition.operator} ${condition.value}`;
      }
      if (typeof condition === 'string') {
        return `if ${condition}`;
      }
      return 'if_else';
    }
    return node.type;
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelectNode(node);
  };

  const handleExpandToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasChildren) setExpanded(!expanded);
  };

  return (
    <div className="select-none">
      <div
        className={`flex items-center gap-2 py-1.5 px-2 rounded cursor-pointer transition-colors
          ${isSelected
            ? 'bg-blue-100 dark:bg-blue-900/50 ring-1 ring-blue-400'
            : 'hover:bg-slate-100 dark:hover:bg-slate-700'
          }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={handleClick}
      >
        <div onClick={handleExpandToggle}>
          {hasChildren ? (
            expanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            )
          ) : (
            <div className="w-3.5 h-3.5 flex-shrink-0" />
          )}
        </div>
        <NodeIcon type={node.type} />
        <span className="text-sm text-slate-700 dark:text-slate-300 truncate">
          {getNodeLabel()}
        </span>
        <span className="text-xs text-slate-400 ml-auto">{node.id}</span>
      </div>

      {expanded && hasChildren && (
        <div>
          {node.then_nodes && node.then_nodes.length > 0 && (
            <div>
              <div
                className="text-xs text-green-600 dark:text-green-400 py-0.5"
                style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}
              >
                then:
              </div>
              {node.then_nodes.map((child, idx) => (
                <NodeTreeItem
                  key={`${node.id}-then-${idx}`}
                  node={child}
                  depth={depth + 1}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={onSelectNode}
                />
              ))}
            </div>
          )}
          {node.else_nodes && node.else_nodes.length > 0 && (
            <div>
              <div
                className="text-xs text-red-600 dark:text-red-400 py-0.5"
                style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}
              >
                else:
              </div>
              {node.else_nodes.map((child, idx) => (
                <NodeTreeItem
                  key={`${node.id}-else-${idx}`}
                  node={child}
                  depth={depth + 1}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={onSelectNode}
                />
              ))}
            </div>
          )}
          {node.loop_nodes && node.loop_nodes.length > 0 && (
            <div>
              <div
                className="text-xs text-green-600 dark:text-green-400 py-0.5"
                style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}
              >
                loop:
              </div>
              {node.loop_nodes.map((child, idx) => (
                <NodeTreeItem
                  key={`${node.id}-loop-${idx}`}
                  node={child}
                  depth={depth + 1}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={onSelectNode}
                />
              ))}
            </div>
          )}
          {node.parallel_nodes && node.parallel_nodes.length > 0 && (
            <div>
              <div
                className="text-xs text-orange-600 dark:text-orange-400 py-0.5"
                style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}
              >
                parallel:
              </div>
              {node.parallel_nodes.map((child, idx) => (
                <NodeTreeItem
                  key={`${node.id}-parallel-${idx}`}
                  node={child}
                  depth={depth + 1}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={onSelectNode}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============ WorkflowPreviewPanel 메인 컴포넌트 ============

export function WorkflowPreviewPanel({
  dsl,
  workflowId,
  workflowName,
  isOpen,
  onApply,
  onRequestModification,
  onClose,
  onDslUpdate,
}: WorkflowPreviewPanelProps) {
  const [feedbackMode, setFeedbackMode] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [showJson, setShowJson] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [editedDsl, setEditedDsl] = useState<WorkflowDSL | null>(null);

  // DSL 초기화
  useEffect(() => {
    if (dsl) {
      setEditedDsl(JSON.parse(JSON.stringify(dsl))); // Deep copy
      setSelectedNodeId(null);
    }
  }, [dsl]);

  // editedDsl에서 ID로 노드 찾기 (중첩 구조 포함)
  const findNodeById = useCallback((nodeId: string): WorkflowNode | null => {
    if (!editedDsl) return null;

    const searchRecursive = (nodes: WorkflowNode[]): WorkflowNode | null => {
      for (const node of nodes) {
        if (node.id === nodeId) return node;

        const searchNested = (nestedNodes?: WorkflowNode[]) =>
          nestedNodes ? searchRecursive(nestedNodes) : null;

        const found = searchNested(node.then_nodes) ||
                      searchNested(node.else_nodes) ||
                      searchNested(node.loop_nodes) ||
                      searchNested(node.parallel_nodes);
        if (found) return found;
      }
      return null;
    };

    return searchRecursive(editedDsl.nodes);
  }, [editedDsl]);

  // selectedNodeId가 변경되거나 editedDsl이 변경될 때 노드 다시 찾기
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return findNodeById(selectedNodeId);
  }, [selectedNodeId, findNodeById]);

  // 노드 통계 계산
  const nodeStats = useMemo(() => {
    if (!editedDsl?.nodes) return { total: 0, byType: {} as Record<string, number> };

    const countNodes = (nodes: WorkflowNode[]): { total: number; byType: Record<string, number> } => {
      let total = 0;
      const byType: Record<string, number> = {};

      const countRecursive = (nodeList: WorkflowNode[]) => {
        for (const node of nodeList) {
          total++;
          byType[node.type] = (byType[node.type] || 0) + 1;

          if (node.then_nodes) countRecursive(node.then_nodes);
          if (node.else_nodes) countRecursive(node.else_nodes);
          if (node.loop_nodes) countRecursive(node.loop_nodes);
          if (node.parallel_nodes) countRecursive(node.parallel_nodes);
        }
      };

      countRecursive(nodes);
      return { total, byType };
    };

    return countNodes(editedDsl.nodes);
  }, [editedDsl]);

  // DSL 내 노드 업데이트
  const updateNodeInDsl = useCallback((updatedNode: WorkflowNode) => {
    if (!editedDsl) return;

    const updateRecursive = (nodes: WorkflowNode[]): WorkflowNode[] => {
      return nodes.map(n => {
        if (n.id === updatedNode.id) return updatedNode;
        return {
          ...n,
          then_nodes: n.then_nodes ? updateRecursive(n.then_nodes) : undefined,
          else_nodes: n.else_nodes ? updateRecursive(n.else_nodes) : undefined,
          loop_nodes: n.loop_nodes ? updateRecursive(n.loop_nodes) : undefined,
          parallel_nodes: n.parallel_nodes ? updateRecursive(n.parallel_nodes) : undefined,
        };
      });
    };

    const newDsl = {
      ...editedDsl,
      nodes: updateRecursive(editedDsl.nodes),
    };
    setEditedDsl(newDsl);
    // selectedNodeId는 그대로 유지 - useMemo가 새 editedDsl에서 노드를 자동으로 찾음

    // 부모에게 변경 알림
    if (onDslUpdate) {
      onDslUpdate(newDsl);
    }
  }, [editedDsl, onDslUpdate]);

  const handleSendFeedback = useCallback(() => {
    if (feedbackText.trim()) {
      onRequestModification(feedbackText.trim());
      setFeedbackText('');
      setFeedbackMode(false);
    }
  }, [feedbackText, onRequestModification]);

  const handleGoToWorkflows = useCallback(() => {
    onClose();
    // 커스텀 이벤트로 탭 전환 (App.tsx의 navigate-to-tab 이벤트 핸들러 사용)
    window.dispatchEvent(new CustomEvent('navigate-to-tab', {
      detail: { tab: 'workflows' }
    }));
  }, [onClose]);

  const handleDetailEdit = useCallback(() => {
    // 먼저 워크플로우를 저장하고 FlowEditor로 이동
    if (!workflowId) {
      onApply();
    }
    handleGoToWorkflows();
  }, [workflowId, onApply, handleGoToWorkflows]);

  if (!isOpen || !editedDsl) return null;

  return (
    <div className="w-96 h-full flex flex-col border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <Play className="w-5 h-5 text-blue-600" />
          <span className="font-medium text-slate-800 dark:text-slate-200">
            워크플로우 미리보기
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
        >
          <X className="w-5 h-5 text-slate-500" />
        </button>
      </div>

      {/* 컨텐츠 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* 워크플로우 정보 */}
        <div className="space-y-2">
          <h3 className="font-medium text-slate-800 dark:text-slate-200">
            {workflowName || editedDsl.name || '새 워크플로우'}
          </h3>
          {editedDsl.description && (
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {editedDsl.description}
            </p>
          )}
        </div>

        {/* 트리거 정보 */}
        <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
            트리거
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-sm rounded">
              {editedDsl.trigger.type}
            </span>
            {editedDsl.trigger.config?.event_type ? (
              <span className="text-sm text-slate-600 dark:text-slate-400">
                {String(editedDsl.trigger.config.event_type)}
              </span>
            ) : null}
          </div>
        </div>

        {/* 노드 통계 */}
        <div className="flex flex-wrap gap-2">
          <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs rounded">
            총 {nodeStats.total}개 노드
          </span>
          {Object.entries(nodeStats.byType).map(([type, count]) => (
            <span
              key={type}
              className="px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-xs rounded"
            >
              {type}: {count}
            </span>
          ))}
        </div>

        {/* 노드 트리 뷰 */}
        <div>
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            워크플로우 구조 (클릭하여 편집)
          </div>
          <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
            <div className="max-h-48 overflow-y-auto">
              {editedDsl.nodes.map((node, idx) => (
                <NodeTreeItem
                  key={`root-${idx}`}
                  node={node}
                  selectedNodeId={selectedNodeId ?? undefined}
                  onSelectNode={(node) => setSelectedNodeId(node.id)}
                />
              ))}
            </div>
          </div>
        </div>

        {/* 노드 속성 패널 */}
        {selectedNode && (
          <NodePropertyPanel
            key={selectedNode.id}
            node={selectedNode}
            onUpdate={updateNodeInDsl}
            onClose={() => setSelectedNodeId(null)}
            onDetailEdit={handleDetailEdit}
          />
        )}

        {/* JSON 토글 */}
        <div>
          <button
            onClick={() => setShowJson(!showJson)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            {showJson ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            DSL JSON 보기
          </button>
          {showJson && (
            <pre className="mt-2 p-3 bg-slate-900 dark:bg-slate-950 text-slate-100 text-xs rounded-lg overflow-x-auto max-h-48 overflow-y-auto">
              {JSON.stringify(editedDsl, null, 2)}
            </pre>
          )}
        </div>

        {/* 피드백 입력 */}
        {feedbackMode && (
          <div className="space-y-2">
            <textarea
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              placeholder="수정 요청 사항을 입력하세요..."
              className="w-full h-24 px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={handleSendFeedback}
                disabled={!feedbackText.trim()}
                className="flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-400 text-white text-sm rounded-lg transition-colors"
              >
                수정 요청
              </button>
              <button
                onClick={() => {
                  setFeedbackMode(false);
                  setFeedbackText('');
                }}
                className="px-3 py-2 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 text-sm rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                취소
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 액션 버튼 */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-700 space-y-2">
        {workflowId ? (
          // 이미 저장된 경우 - Workflows 페이지로 이동 버튼
          <button
            onClick={handleGoToWorkflows}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
            <span>Workflows 페이지에서 보기</span>
          </button>
        ) : (
          // 아직 저장되지 않은 경우 - 저장 버튼
          <button
            onClick={onApply}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
          >
            <Check className="w-4 h-4" />
            <span>워크플로우 적용</span>
          </button>
        )}

        {!feedbackMode && (
          <button
            onClick={() => setFeedbackMode(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <MessageSquare className="w-4 h-4" />
            <span>수정 요청</span>
          </button>
        )}
      </div>
    </div>
  );
}
