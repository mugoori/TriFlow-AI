/**
 * BranchNodeEditor
 * If/Else, Loop, Parallel 노드의 내부 노드를 편집하는 컴포넌트
 */

import { useState, useCallback, useRef } from 'react';
import {
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  GripVertical,
  AlertTriangle,
  Zap,
  Repeat,
  Layers,
} from 'lucide-react';

// ============ Types ============

export type InnerNodeType = 'condition' | 'action';

export interface InnerNode {
  id: string;
  type: InnerNodeType;
  config: Record<string, unknown>;
}

interface BranchNodeEditorProps {
  title: string;
  description?: string;
  nodes: InnerNode[];
  onChange: (nodes: InnerNode[]) => void;
  className?: string;
}

interface ParallelBranchEditorProps {
  branches: InnerNode[][];
  onChange: (branches: InnerNode[][]) => void;
  failFast: boolean;
  onFailFastChange: (value: boolean) => void;
}

// ============ Constants ============

const nodeTypeLabels: Record<InnerNodeType, string> = {
  condition: '조건',
  action: '액션',
};

const nodeTypeIcons: Record<InnerNodeType, typeof AlertTriangle> = {
  condition: AlertTriangle,
  action: Zap,
};

const nodeTypeColors: Record<InnerNodeType, { bg: string; text: string }> = {
  condition: { bg: 'bg-yellow-100 dark:bg-yellow-900/30', text: 'text-yellow-700 dark:text-yellow-400' },
  action: { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-400' },
};

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

// ============ Inner Node Item ============

interface InnerNodeItemProps {
  node: InnerNode;
  index: number;
  onChange: (node: InnerNode) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
}

function InnerNodeItem({
  node,
  index,
  onChange,
  onDelete,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: InnerNodeItemProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const Icon = nodeTypeIcons[node.type];
  const colors = nodeTypeColors[node.type];

  const updateConfig = (key: string, value: unknown) => {
    onChange({
      ...node,
      config: { ...node.config, [key]: value },
    });
  };

  const getSummary = () => {
    if (node.type === 'condition') {
      return (node.config.condition as string) || '조건 미설정';
    }
    if (node.type === 'action') {
      const action = node.config.action as string;
      return actionLabels[action] || action || '액션 미설정';
    }
    return '';
  };

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className={`flex items-center gap-2 px-3 py-2 ${colors.bg} cursor-pointer`}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <GripVertical className="w-4 h-4 text-slate-400 cursor-grab" />
        <Icon className={`w-4 h-4 ${colors.text}`} />
        <span className={`text-xs font-medium ${colors.text}`}>
          {index + 1}. {nodeTypeLabels[node.type]}
        </span>
        <span className="flex-1 text-xs text-slate-600 dark:text-slate-400 truncate">
          {getSummary()}
        </span>

        <div className="flex items-center gap-1">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onMoveUp();
            }}
            disabled={isFirst}
            className="p-1 rounded hover:bg-white/50 disabled:opacity-30"
          >
            <ChevronUp className="w-3 h-3" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onMoveDown();
            }}
            disabled={isLast}
            className="p-1 rounded hover:bg-white/50 disabled:opacity-30"
          >
            <ChevronDown className="w-3 h-3" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Body */}
      {isExpanded && (
        <div className="p-3 space-y-2 bg-white dark:bg-slate-800/50">
          {node.type === 'condition' && (
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                조건식
              </label>
              <input
                type="text"
                value={(node.config.condition as string) || ''}
                onChange={(e) => updateConfig('condition', e.target.value)}
                className="w-full px-2 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
                placeholder="temperature > 80"
              />
            </div>
          )}

          {node.type === 'action' && (
            <>
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                  액션
                </label>
                <select
                  value={(node.config.action as string) || ''}
                  onChange={(e) => updateConfig('action', e.target.value)}
                  className="w-full px-2 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
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
                  value={JSON.stringify(node.config.parameters || {}, null, 2)}
                  onChange={(e) => {
                    try {
                      updateConfig('parameters', JSON.parse(e.target.value));
                    } catch {
                      // ignore parse error while typing
                    }
                  }}
                  className="w-full px-2 py-1.5 text-xs font-mono border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100 h-16"
                  placeholder='{"message": "알림"}'
                />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ============ Add Node Button ============

interface AddNodeButtonProps {
  onAdd: (type: InnerNodeType) => void;
}

function AddNodeButton({ onAdd }: AddNodeButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [buttonRect, setButtonRect] = useState<DOMRect | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const handleOpen = () => {
    if (buttonRef.current) {
      setButtonRect(buttonRef.current.getBoundingClientRect());
    }
    setIsOpen(!isOpen);
  };

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={handleOpen}
        className="flex items-center justify-center gap-1 w-full px-3 py-2 text-sm text-slate-600 dark:text-slate-400 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg hover:border-blue-400 hover:text-blue-600 dark:hover:border-blue-500 dark:hover:text-blue-400 transition-colors"
      >
        <Plus className="w-4 h-4" />
        노드 추가
      </button>

      {isOpen && buttonRect && (
        <>
          <div
            className="fixed inset-0 z-[100]"
            onClick={() => setIsOpen(false)}
          />
          <div
            className="fixed z-[101] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl"
            style={{
              top: buttonRect.bottom + 4,
              left: buttonRect.left,
              width: buttonRect.width,
              minWidth: '160px',
            }}
          >
            <button
              onClick={() => {
                onAdd('condition');
                setIsOpen(false);
              }}
              className="flex items-center gap-2 w-full px-3 py-2.5 text-sm text-slate-700 dark:text-slate-200 hover:bg-yellow-50 dark:hover:bg-yellow-900/20 rounded-t-lg"
            >
              <AlertTriangle className="w-4 h-4 text-yellow-600 flex-shrink-0" />
              <span>조건 노드</span>
            </button>
            <button
              onClick={() => {
                onAdd('action');
                setIsOpen(false);
              }}
              className="flex items-center gap-2 w-full px-3 py-2.5 text-sm text-slate-700 dark:text-slate-200 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-b-lg"
            >
              <Zap className="w-4 h-4 text-blue-600 flex-shrink-0" />
              <span>액션 노드</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ============ Branch Node Editor (단일 브랜치) ============

export function BranchNodeEditor({
  title,
  description,
  nodes,
  onChange,
  className = '',
}: BranchNodeEditorProps) {
  const handleAdd = useCallback(
    (type: InnerNodeType) => {
      const newNode: InnerNode = {
        id: `inner_${type}_${Date.now()}`,
        type,
        config: type === 'condition' ? { condition: '' } : { action: '', parameters: {} },
      };
      onChange([...nodes, newNode]);
    },
    [nodes, onChange]
  );

  const handleUpdate = useCallback(
    (index: number, node: InnerNode) => {
      const newNodes = [...nodes];
      newNodes[index] = node;
      onChange(newNodes);
    },
    [nodes, onChange]
  );

  const handleDelete = useCallback(
    (index: number) => {
      onChange(nodes.filter((_, i) => i !== index));
    },
    [nodes, onChange]
  );

  const handleMoveUp = useCallback(
    (index: number) => {
      if (index === 0) return;
      const newNodes = [...nodes];
      [newNodes[index - 1], newNodes[index]] = [newNodes[index], newNodes[index - 1]];
      onChange(newNodes);
    },
    [nodes, onChange]
  );

  const handleMoveDown = useCallback(
    (index: number) => {
      if (index === nodes.length - 1) return;
      const newNodes = [...nodes];
      [newNodes[index], newNodes[index + 1]] = [newNodes[index + 1], newNodes[index]];
      onChange(newNodes);
    },
    [nodes, onChange]
  );

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300">
          {title}
        </h4>
        <span className="text-xs text-slate-500">
          {nodes.length}개 노드
        </span>
      </div>

      {description && (
        <p className="text-xs text-slate-500">{description}</p>
      )}

      <div className="space-y-2">
        {nodes.length === 0 ? (
          <div className="text-center py-4 text-xs text-slate-400 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
            노드가 없습니다
          </div>
        ) : (
          nodes.map((node, index) => (
            <InnerNodeItem
              key={node.id}
              node={node}
              index={index}
              onChange={(n) => handleUpdate(index, n)}
              onDelete={() => handleDelete(index)}
              onMoveUp={() => handleMoveUp(index)}
              onMoveDown={() => handleMoveDown(index)}
              isFirst={index === 0}
              isLast={index === nodes.length - 1}
            />
          ))
        )}
      </div>

      <AddNodeButton onAdd={handleAdd} />
    </div>
  );
}

// ============ If/Else Branch Editor ============

interface IfElseBranchEditorProps {
  condition: string;
  onConditionChange: (value: string) => void;
  thenNodes: InnerNode[];
  onThenNodesChange: (nodes: InnerNode[]) => void;
  elseNodes: InnerNode[];
  onElseNodesChange: (nodes: InnerNode[]) => void;
}

export function IfElseBranchEditor({
  condition,
  onConditionChange,
  thenNodes,
  onThenNodesChange,
  elseNodes,
  onElseNodesChange,
}: IfElseBranchEditorProps) {
  return (
    <div className="space-y-4">
      {/* 조건 입력 */}
      <div>
        <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
          분기 조건
        </label>
        <input
          type="text"
          value={condition}
          onChange={(e) => onConditionChange(e.target.value)}
          className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
          placeholder="temperature > 80"
        />
      </div>

      {/* Then 브랜치 */}
      <div className="p-3 border-2 border-green-200 dark:border-green-800 rounded-lg bg-green-50/50 dark:bg-green-900/10">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-sm font-medium text-green-700 dark:text-green-400">
            Then (조건이 참일 때)
          </span>
        </div>
        <BranchNodeEditor
          title=""
          nodes={thenNodes}
          onChange={onThenNodesChange}
        />
      </div>

      {/* Else 브랜치 */}
      <div className="p-3 border-2 border-red-200 dark:border-red-800 rounded-lg bg-red-50/50 dark:bg-red-900/10">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-red-500" />
          <span className="text-sm font-medium text-red-700 dark:text-red-400">
            Else (조건이 거짓일 때)
          </span>
        </div>
        <BranchNodeEditor
          title=""
          nodes={elseNodes}
          onChange={onElseNodesChange}
        />
      </div>
    </div>
  );
}

// ============ Loop Node Editor ============

interface LoopNodeEditorProps {
  loopType: 'for' | 'while';
  onLoopTypeChange: (type: 'for' | 'while') => void;
  count: number;
  onCountChange: (value: number) => void;
  condition: string;
  onConditionChange: (value: string) => void;
  nodes: InnerNode[];
  onNodesChange: (nodes: InnerNode[]) => void;
}

export function LoopNodeEditor({
  loopType,
  onLoopTypeChange,
  count,
  onCountChange,
  condition,
  onConditionChange,
  nodes,
  onNodesChange,
}: LoopNodeEditorProps) {
  return (
    <div className="space-y-4">
      {/* 반복 유형 */}
      <div>
        <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
          반복 유형
        </label>
        <select
          value={loopType}
          onChange={(e) => onLoopTypeChange(e.target.value as 'for' | 'while')}
          className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
        >
          <option value="for">횟수 반복 (for)</option>
          <option value="while">조건 반복 (while)</option>
        </select>
      </div>

      {/* 반복 조건/횟수 */}
      {loopType === 'for' ? (
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
            반복 횟수
          </label>
          <input
            type="number"
            min="1"
            max="100"
            value={count}
            onChange={(e) => onCountChange(parseInt(e.target.value) || 1)}
            className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
          />
        </div>
      ) : (
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
            반복 조건
          </label>
          <input
            type="text"
            value={condition}
            onChange={(e) => onConditionChange(e.target.value)}
            className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
            placeholder="retry_count < 3"
          />
          <p className="mt-1 text-xs text-slate-500">
            최대 100회까지 반복됩니다
          </p>
        </div>
      )}

      {/* 반복 실행 노드 */}
      <div className="p-3 border-2 border-green-200 dark:border-green-800 rounded-lg bg-green-50/50 dark:bg-green-900/10">
        <div className="flex items-center gap-2 mb-3">
          <Repeat className="w-4 h-4 text-green-600" />
          <span className="text-sm font-medium text-green-700 dark:text-green-400">
            반복 실행할 노드
          </span>
        </div>
        <BranchNodeEditor
          title=""
          description="loop_index, loop_iteration 변수 사용 가능"
          nodes={nodes}
          onChange={onNodesChange}
        />
      </div>
    </div>
  );
}

// ============ Parallel Branch Editor ============

export function ParallelBranchEditor({
  branches,
  onChange,
  failFast,
  onFailFastChange,
}: ParallelBranchEditorProps) {
  const [activeTab, setActiveTab] = useState(0);

  const handleAddBranch = useCallback(() => {
    onChange([...branches, []]);
    setActiveTab(branches.length);
  }, [branches, onChange]);

  const handleRemoveBranch = useCallback(
    (index: number) => {
      if (branches.length <= 1) return;
      const newBranches = branches.filter((_, i) => i !== index);
      onChange(newBranches);
      if (activeTab >= newBranches.length) {
        setActiveTab(newBranches.length - 1);
      }
    },
    [branches, onChange, activeTab]
  );

  const handleBranchNodesChange = useCallback(
    (index: number, nodes: InnerNode[]) => {
      const newBranches = [...branches];
      newBranches[index] = nodes;
      onChange(newBranches);
    },
    [branches, onChange]
  );

  return (
    <div className="space-y-4">
      {/* Fail Fast 옵션 */}
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="parallel_fail_fast"
          checked={failFast}
          onChange={(e) => onFailFastChange(e.target.checked)}
          className="rounded border-slate-300"
        />
        <label
          htmlFor="parallel_fail_fast"
          className="text-sm text-slate-600 dark:text-slate-400"
        >
          하나 실패 시 전체 중단 (fail_fast)
        </label>
      </div>

      {/* 브랜치 탭 */}
      <div className="flex items-center gap-1 flex-wrap">
        {branches.map((_, index) => (
          <button
            key={index}
            onClick={() => setActiveTab(index)}
            className={`relative px-3 py-1.5 text-sm rounded-lg transition-colors ${
              activeTab === index
                ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
                : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
            }`}
          >
            브랜치 {index + 1}
            {branches.length > 1 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleRemoveBranch(index);
                }}
                className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white text-xs flex items-center justify-center hover:bg-red-600"
              >
                ×
              </button>
            )}
          </button>
        ))}
        <button
          onClick={handleAddBranch}
          className="px-3 py-1.5 text-sm text-slate-500 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg hover:border-orange-400 hover:text-orange-600"
        >
          <Plus className="w-4 h-4 inline" />
        </button>
      </div>

      {/* 활성 브랜치 편집 */}
      <div className="p-3 border-2 border-orange-200 dark:border-orange-800 rounded-lg bg-orange-50/50 dark:bg-orange-900/10">
        <div className="flex items-center gap-2 mb-3">
          <Layers className="w-4 h-4 text-orange-600" />
          <span className="text-sm font-medium text-orange-700 dark:text-orange-400">
            브랜치 {activeTab + 1} 노드
          </span>
        </div>
        <BranchNodeEditor
          title=""
          nodes={branches[activeTab] || []}
          onChange={(nodes) => handleBranchNodesChange(activeTab, nodes)}
        />
      </div>

      <p className="text-xs text-slate-500">
        모든 브랜치가 동시에 병렬로 실행됩니다
      </p>
    </div>
  );
}
