/**
 * ConditionBuilder
 * 조건식을 시각적으로 구성할 수 있는 빌더 컴포넌트
 */

import { useState, useCallback, useEffect } from 'react';
import { Plus, Trash2 } from 'lucide-react';

// ============ Types ============

type Operator = '>' | '<' | '>=' | '<=' | '==' | '!=';
type LogicalOperator = 'AND' | 'OR';

interface Condition {
  id: string;
  variable: string;
  operator: Operator;
  value: string;
}

interface ConditionGroup {
  id: string;
  logicalOperator: LogicalOperator;
  conditions: Condition[];
}

interface ConditionBuilderProps {
  value: string;
  onChange: (value: string) => void;
  variables?: string[];
  placeholder?: string;
}

// ============ Constants ============

const operators: { value: Operator; label: string }[] = [
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '>=', label: '>=' },
  { value: '<=', label: '<=' },
  { value: '==', label: '==' },
  { value: '!=', label: '!=' },
];

const defaultVariables = [
  'temperature',
  'pressure',
  'humidity',
  'vibration',
  'speed',
  'power',
  'defect_rate',
  'production_count',
  'error_count',
  'sensor_value',
];

// ============ Helper Functions ============

function generateId(): string {
  return `cond_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function parseConditionString(str: string): ConditionGroup[] {
  if (!str.trim()) {
    return [{ id: generateId(), logicalOperator: 'AND', conditions: [] }];
  }

  // 간단한 파싱: OR로 분리 후 각 그룹 내에서 AND로 분리
  const groups: ConditionGroup[] = [];
  const orParts = str.split(/\s*\|\|\s*/);

  orParts.forEach((orPart) => {
    const andParts = orPart.split(/\s*&&\s*/);
    const conditions: Condition[] = [];

    andParts.forEach((part) => {
      const match = part.trim().match(/^(\w+)\s*(>=|<=|==|!=|>|<)\s*(.+)$/);
      if (match) {
        conditions.push({
          id: generateId(),
          variable: match[1],
          operator: match[2] as Operator,
          value: match[3].trim(),
        });
      }
    });

    if (conditions.length > 0) {
      groups.push({
        id: generateId(),
        logicalOperator: 'AND',
        conditions,
      });
    }
  });

  if (groups.length === 0) {
    return [{ id: generateId(), logicalOperator: 'AND', conditions: [] }];
  }

  return groups;
}

function buildConditionString(groups: ConditionGroup[]): string {
  const groupStrings = groups
    .filter((g) => g.conditions.length > 0)
    .map((group) => {
      const conditionStrings = group.conditions.map(
        (c) => `${c.variable} ${c.operator} ${c.value}`
      );
      return conditionStrings.join(' && ');
    });

  return groupStrings.join(' || ');
}

// ============ Single Condition Row ============

interface ConditionRowProps {
  condition: Condition;
  onChange: (condition: Condition) => void;
  onDelete: () => void;
  variables: string[];
  showDelete: boolean;
}

function ConditionRow({
  condition,
  onChange,
  onDelete,
  variables,
  showDelete,
}: ConditionRowProps) {
  const [showVariableDropdown, setShowVariableDropdown] = useState(false);

  return (
    <div className="p-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900 space-y-2">
      {/* 헤더: 삭제 버튼 */}
      {showDelete && (
        <div className="flex justify-end">
          <button
            onClick={onDelete}
            className="p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
            title="조건 삭제"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 변수 선택 */}
      <div className="relative">
        <label className="block text-xs text-slate-500 mb-1">변수</label>
        <input
          type="text"
          value={condition.variable}
          onChange={(e) => onChange({ ...condition, variable: e.target.value })}
          onFocus={() => setShowVariableDropdown(true)}
          onBlur={() => setTimeout(() => setShowVariableDropdown(false), 200)}
          className="w-full px-2 py-1.5 text-sm border rounded bg-white dark:bg-slate-800 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
          placeholder="예: temperature"
        />
        {showVariableDropdown && (
          <div className="absolute top-full left-0 right-0 z-20 mt-1 max-h-32 overflow-y-auto bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg">
            {variables
              .filter((v) =>
                v.toLowerCase().includes(condition.variable.toLowerCase())
              )
              .slice(0, 8)
              .map((v) => (
                <button
                  key={v}
                  onMouseDown={() => onChange({ ...condition, variable: v })}
                  className="w-full px-3 py-1.5 text-left text-sm text-slate-900 dark:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-700"
                >
                  {v}
                </button>
              ))}
          </div>
        )}
      </div>

      {/* 연산자와 값 - 가로 배치 */}
      <div className="flex gap-2">
        <div className="w-20 shrink-0">
          <label className="block text-xs text-slate-500 mb-1">연산자</label>
          <select
            value={condition.operator}
            onChange={(e) =>
              onChange({ ...condition, operator: e.target.value as Operator })
            }
            className="w-full px-2 py-1.5 text-sm border rounded bg-white dark:bg-slate-800 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
          >
            {operators.map((op) => (
              <option key={op.value} value={op.value}>
                {op.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 min-w-0">
          <label className="block text-xs text-slate-500 mb-1">값</label>
          <input
            type="text"
            value={condition.value}
            onChange={(e) => onChange({ ...condition, value: e.target.value })}
            className="w-full px-2 py-1.5 text-sm border rounded bg-white dark:bg-slate-800 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
            placeholder="예: 80"
          />
        </div>
      </div>
    </div>
  );
}

// ============ Condition Group ============

interface ConditionGroupComponentProps {
  group: ConditionGroup;
  groupIndex: number;
  onChange: (group: ConditionGroup) => void;
  onDelete: () => void;
  variables: string[];
  showDelete: boolean;
}

function ConditionGroupComponent({
  group,
  groupIndex,
  onChange,
  onDelete,
  variables,
  showDelete,
}: ConditionGroupComponentProps) {
  const handleAddCondition = () => {
    const newCondition: Condition = {
      id: generateId(),
      variable: '',
      operator: '>',
      value: '',
    };
    onChange({
      ...group,
      conditions: [...group.conditions, newCondition],
    });
  };

  const handleUpdateCondition = (index: number, condition: Condition) => {
    const newConditions = [...group.conditions];
    newConditions[index] = condition;
    onChange({ ...group, conditions: newConditions });
  };

  const handleDeleteCondition = (index: number) => {
    onChange({
      ...group,
      conditions: group.conditions.filter((_, i) => i !== index),
    });
  };

  return (
    <div className="space-y-2 p-3 border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50/50 dark:bg-slate-800/50">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500">
          그룹 {groupIndex + 1}
        </span>
        {showDelete && (
          <button
            onClick={onDelete}
            className="text-xs text-red-500 hover:underline"
          >
            그룹 삭제
          </button>
        )}
      </div>

      {group.conditions.length === 0 ? (
        <div className="text-center py-2 text-xs text-slate-400">
          조건을 추가하세요
        </div>
      ) : (
        <div className="space-y-2">
          {group.conditions.map((condition, index) => (
            <div key={condition.id}>
              {index > 0 && (
                <div className="flex items-center justify-center my-1">
                  <span className="px-2 py-0.5 text-xs font-medium text-blue-600 bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400 rounded">
                    AND
                  </span>
                </div>
              )}
              <ConditionRow
                condition={condition}
                onChange={(c) => handleUpdateCondition(index, c)}
                onDelete={() => handleDeleteCondition(index)}
                variables={variables}
                showDelete={group.conditions.length > 1}
              />
            </div>
          ))}
        </div>
      )}

      <button
        onClick={handleAddCondition}
        className="flex items-center gap-1 w-full px-2 py-1.5 text-xs text-slate-600 dark:text-slate-400 border border-dashed border-slate-300 dark:border-slate-600 rounded hover:border-blue-400 hover:text-blue-600"
      >
        <Plus className="w-3 h-3" />
        AND 조건 추가
      </button>
    </div>
  );
}

// ============ Main Component ============

export function ConditionBuilder({
  value,
  onChange,
  variables = defaultVariables,
  placeholder = 'temperature > 80',
}: ConditionBuilderProps) {
  const [mode, setMode] = useState<'text' | 'builder'>('text');
  const [groups, setGroups] = useState<ConditionGroup[]>(() =>
    parseConditionString(value)
  );

  // 외부 value 변경 시 동기화
  useEffect(() => {
    if (mode === 'text') {
      setGroups(parseConditionString(value));
    }
  }, [value, mode]);

  // 빌더 모드에서 그룹 변경 시 외부로 전파
  const updateGroups = useCallback(
    (newGroups: ConditionGroup[]) => {
      setGroups(newGroups);
      if (mode === 'builder') {
        onChange(buildConditionString(newGroups));
      }
    },
    [mode, onChange]
  );

  const handleModeChange = (newMode: 'text' | 'builder') => {
    if (newMode === 'builder') {
      setGroups(parseConditionString(value));
    }
    setMode(newMode);
  };

  const handleAddGroup = () => {
    updateGroups([
      ...groups,
      { id: generateId(), logicalOperator: 'AND', conditions: [] },
    ]);
  };

  const handleUpdateGroup = (index: number, group: ConditionGroup) => {
    const newGroups = [...groups];
    newGroups[index] = group;
    updateGroups(newGroups);
  };

  const handleDeleteGroup = (index: number) => {
    if (groups.length <= 1) return;
    updateGroups(groups.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-2">
      {/* 모드 전환 탭 */}
      <div className="flex border-b border-slate-200 dark:border-slate-700">
        <button
          onClick={() => handleModeChange('text')}
          className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
            mode === 'text'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          텍스트 입력
        </button>
        <button
          onClick={() => handleModeChange('builder')}
          className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
            mode === 'builder'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          빌더
        </button>
      </div>

      {/* 텍스트 모드 */}
      {mode === 'text' && (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
          placeholder={placeholder}
        />
      )}

      {/* 빌더 모드 */}
      {mode === 'builder' && (
        <div className="space-y-3">
          {groups.map((group, index) => (
            <div key={group.id}>
              {index > 0 && (
                <div className="flex items-center justify-center my-2">
                  <span className="px-3 py-1 text-xs font-medium text-orange-600 bg-orange-100 dark:bg-orange-900/30 dark:text-orange-400 rounded-full">
                    OR
                  </span>
                </div>
              )}
              <ConditionGroupComponent
                group={group}
                groupIndex={index}
                onChange={(g) => handleUpdateGroup(index, g)}
                onDelete={() => handleDeleteGroup(index)}
                variables={variables}
                showDelete={groups.length > 1}
              />
            </div>
          ))}

          <button
            onClick={handleAddGroup}
            className="flex items-center gap-1 w-full px-3 py-2 text-sm text-orange-600 dark:text-orange-400 border-2 border-dashed border-orange-300 dark:border-orange-700 rounded-lg hover:bg-orange-50 dark:hover:bg-orange-900/20"
          >
            <Plus className="w-4 h-4" />
            OR 그룹 추가
          </button>

          {/* 미리보기 */}
          <div className="p-2 bg-slate-100 dark:bg-slate-900 rounded-lg">
            <span className="text-xs text-slate-500">미리보기:</span>
            <code className="block mt-1 text-xs font-mono text-slate-700 dark:text-slate-300">
              {buildConditionString(groups) || '(조건 없음)'}
            </code>
          </div>
        </div>
      )}
    </div>
  );
}
