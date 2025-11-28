/**
 * WorkflowEditor
 * 워크플로우 시각적 편집기 컴포넌트
 * - 드래그 앤 드롭으로 노드 추가/재배치
 * - 노드 연결 시각화
 * - DSL 실시간 미리보기
 */

import { useState } from 'react';
import {
  X,
  Plus,
  Trash2,
  GripVertical,
  ChevronRight,
  Play,
  Save,
  Eye,
  AlertTriangle,
  CheckCircle2,
  Zap,
  GitBranch,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { WorkflowNode, WorkflowDSL } from '@/services/workflowService';

interface WorkflowEditorProps {
  initialDSL?: WorkflowDSL;
  onSave?: (dsl: WorkflowDSL) => void;
  onCancel?: () => void;
  isOpen: boolean;
}


// 노드 타입별 색상
const nodeTypeColors: Record<string, string> = {
  condition: 'border-yellow-400 bg-yellow-50 dark:bg-yellow-900/20',
  action: 'border-blue-400 bg-blue-50 dark:bg-blue-900/20',
};

// 액션 ID → 한글 이름 매핑
const actionLabels: Record<string, string> = {
  // 알림
  send_slack_notification: 'Slack 알림 전송',
  send_email: '이메일 발송',
  send_sms: 'SMS 문자 발송',
  // 데이터
  save_to_database: '데이터베이스 저장',
  export_to_csv: 'CSV 파일 내보내기',
  log_event: '이벤트 로그 기록',
  // 제어
  stop_production_line: '생산라인 정지',
  adjust_sensor_threshold: '센서 임계값 조정',
  trigger_maintenance: '유지보수 요청 발생',
  // 분석
  calculate_defect_rate: '불량률 계산',
  analyze_sensor_trend: '센서 추세 분석',
  predict_equipment_failure: '장비 고장 예측',
};

// 조건 템플릿 정의
interface ConditionTemplate {
  id: string;
  name: string;
  description: string;
  template: string;
  variables: { name: string; placeholder: string; defaultValue: string }[];
}

const conditionTemplates: ConditionTemplate[] = [
  // 센서 값 비교
  {
    id: 'sensor_above',
    name: '센서 값 초과',
    description: '센서 값이 특정 임계값을 초과할 때',
    template: '{sensor} > {threshold}',
    variables: [
      { name: 'sensor', placeholder: '센서명', defaultValue: 'temperature' },
      { name: 'threshold', placeholder: '임계값', defaultValue: '80' },
    ],
  },
  {
    id: 'sensor_below',
    name: '센서 값 미만',
    description: '센서 값이 특정 임계값 미만일 때',
    template: '{sensor} < {threshold}',
    variables: [
      { name: 'sensor', placeholder: '센서명', defaultValue: 'pressure' },
      { name: 'threshold', placeholder: '임계값', defaultValue: '10' },
    ],
  },
  {
    id: 'sensor_range',
    name: '센서 값 범위 이탈',
    description: '센서 값이 정상 범위를 벗어날 때',
    template: '{sensor} < {min} || {sensor} > {max}',
    variables: [
      { name: 'sensor', placeholder: '센서명', defaultValue: 'humidity' },
      { name: 'min', placeholder: '최소값', defaultValue: '30' },
      { name: 'max', placeholder: '최대값', defaultValue: '70' },
    ],
  },
  // 품질 관련
  {
    id: 'defect_rate',
    name: '불량률 초과',
    description: '불량률이 허용 기준을 초과할 때',
    template: 'defect_rate > {threshold}',
    variables: [
      { name: 'threshold', placeholder: '허용 불량률 (%)', defaultValue: '5' },
    ],
  },
  {
    id: 'consecutive_defects',
    name: '연속 불량 발생',
    description: '연속으로 불량이 발생할 때',
    template: 'consecutive_defects >= {count}',
    variables: [
      { name: 'count', placeholder: '연속 불량 횟수', defaultValue: '3' },
    ],
  },
  // 장비 상태
  {
    id: 'equipment_status',
    name: '장비 상태 확인',
    description: '장비가 특정 상태일 때',
    template: 'equipment_status == "{status}"',
    variables: [
      { name: 'status', placeholder: '상태 (running/stopped/error)', defaultValue: 'error' },
    ],
  },
  {
    id: 'runtime_exceeded',
    name: '가동 시간 초과',
    description: '장비 연속 가동 시간이 초과할 때',
    template: 'runtime_hours > {hours}',
    variables: [
      { name: 'hours', placeholder: '가동 시간 (시)', defaultValue: '8' },
    ],
  },
  // 생산 관련
  {
    id: 'production_target',
    name: '생산 목표 달성',
    description: '생산량이 목표에 도달할 때',
    template: 'production_count >= {target}',
    variables: [
      { name: 'target', placeholder: '목표 생산량', defaultValue: '1000' },
    ],
  },
  {
    id: 'production_delay',
    name: '생산 지연',
    description: '생산 속도가 기준 미달일 때',
    template: 'units_per_hour < {rate}',
    variables: [
      { name: 'rate', placeholder: '기준 생산량 (개/시간)', defaultValue: '100' },
    ],
  },
  // 복합 조건
  {
    id: 'multi_sensor_alert',
    name: '복합 센서 이상',
    description: '여러 센서 값이 동시에 비정상일 때',
    template: '{sensor1} > {threshold1} && {sensor2} > {threshold2}',
    variables: [
      { name: 'sensor1', placeholder: '센서1', defaultValue: 'temperature' },
      { name: 'threshold1', placeholder: '임계값1', defaultValue: '80' },
      { name: 'sensor2', placeholder: '센서2', defaultValue: 'vibration' },
      { name: 'threshold2', placeholder: '임계값2', defaultValue: '50' },
    ],
  },
  // 시간 기반
  {
    id: 'shift_check',
    name: '근무 교대 시간',
    description: '특정 시간대에만 적용',
    template: 'current_hour >= {start} && current_hour < {end}',
    variables: [
      { name: 'start', placeholder: '시작 시간 (0-23)', defaultValue: '9' },
      { name: 'end', placeholder: '종료 시간 (0-23)', defaultValue: '18' },
    ],
  },
  // 직접 입력
  {
    id: 'custom',
    name: '직접 입력',
    description: 'Rhai 표현식을 직접 작성',
    template: '',
    variables: [],
  },
];

// 기본 워크플로우 템플릿
const defaultDSL: WorkflowDSL = {
  name: '새 워크플로우',
  description: '',
  trigger: {
    type: 'manual',
    config: {},
  },
  nodes: [],
};

// 템플릿에서 조건식 생성하는 헬퍼 함수
function buildConditionFromTemplate(
  template: ConditionTemplate,
  values: Record<string, string>
): string {
  if (template.id === 'custom') return values.custom || '';

  let result = template.template;
  template.variables.forEach((v) => {
    result = result.replace(new RegExp(`\\{${v.name}\\}`, 'g'), values[v.name] || v.defaultValue);
  });
  return result;
}

// 노드 에디터 컴포넌트
function NodeEditor({
  node,
  index,
  onUpdate,
  onDelete,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: {
  node: WorkflowNode;
  index: number;
  onUpdate: (node: WorkflowNode) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const NodeIcon = node.type === 'condition' ? AlertTriangle : Zap;

  // 조건 템플릿 관련 상태
  const nodeConfig = node.config as {
    condition?: string;
    templateId?: string;
    templateValues?: Record<string, string>;
  };
  const [selectedTemplateId, setSelectedTemplateId] = useState(
    nodeConfig.templateId || 'custom'
  );
  const [templateValues, setTemplateValues] = useState<Record<string, string>>(
    nodeConfig.templateValues || {}
  );

  const handleConfigChange = (key: string, value: string) => {
    onUpdate({
      ...node,
      config: {
        ...node.config,
        [key]: value,
      },
    });
  };

  // 템플릿 선택 핸들러
  const handleTemplateSelect = (templateId: string) => {
    setSelectedTemplateId(templateId);
    const template = conditionTemplates.find(t => t.id === templateId);
    if (!template) return;

    // 기본값으로 초기화
    const defaultValues: Record<string, string> = {};
    template.variables.forEach(v => {
      defaultValues[v.name] = templateValues[v.name] || v.defaultValue;
    });
    setTemplateValues(defaultValues);

    // 조건식 생성 및 저장
    const condition = buildConditionFromTemplate(template, defaultValues);
    onUpdate({
      ...node,
      config: {
        ...node.config,
        condition,
        templateId,
        templateValues: defaultValues,
      },
    });
  };

  // 템플릿 변수 값 변경 핸들러
  const handleTemplateValueChange = (varName: string, value: string) => {
    const newValues = { ...templateValues, [varName]: value };
    setTemplateValues(newValues);

    const template = conditionTemplates.find(t => t.id === selectedTemplateId);
    if (!template) return;

    const condition = buildConditionFromTemplate(template, newValues);
    onUpdate({
      ...node,
      config: {
        ...node.config,
        condition,
        templateId: selectedTemplateId,
        templateValues: newValues,
      },
    });
  };

  return (
    <div className="relative">
      {/* 연결선 */}
      {index > 0 && (
        <div className="absolute left-6 -top-4 w-0.5 h-4 bg-slate-300 dark:bg-slate-600" />
      )}

      <div className={`border-2 rounded-lg ${nodeTypeColors[node.type]} transition-all`}>
        {/* 노드 헤더 */}
        <div
          className="flex items-center gap-2 p-3 cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          <GripVertical className="w-4 h-4 text-slate-400 cursor-grab" />
          <div className={`p-1.5 rounded ${
            node.type === 'condition'
              ? 'bg-yellow-200 dark:bg-yellow-800'
              : 'bg-blue-200 dark:bg-blue-800'
          }`}>
            <NodeIcon className="w-4 h-4" />
          </div>
          <div className="flex-1">
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {index + 1}. {node.type === 'condition' ? '조건' : '액션'}
            </span>
            <h4 className="text-sm font-medium">
              {node.type === 'condition'
                ? (node.config as { condition?: string })?.condition || '조건 미설정'
                : actionLabels[(node.config as { action?: string })?.action || ''] || '액션 미설정'}
            </h4>
          </div>
          <div className="flex items-center gap-1">
            {!isFirst && (
              <button
                onClick={(e) => { e.stopPropagation(); onMoveUp(); }}
                className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700"
                title="위로 이동"
              >
                <ChevronRight className="w-4 h-4 -rotate-90" />
              </button>
            )}
            {!isLast && (
              <button
                onClick={(e) => { e.stopPropagation(); onMoveDown(); }}
                className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700"
                title="아래로 이동"
              >
                <ChevronRight className="w-4 h-4 rotate-90" />
              </button>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(); }}
              className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30"
              title="삭제"
            >
              <Trash2 className="w-4 h-4 text-red-500" />
            </button>
            <ChevronRight className={`w-4 h-4 transition-transform ${expanded ? 'rotate-90' : ''}`} />
          </div>
        </div>

        {/* 노드 설정 */}
        {expanded && (
          <div className="p-3 pt-0 border-t border-slate-200 dark:border-slate-700">
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                  노드 ID
                </label>
                <input
                  type="text"
                  value={node.id}
                  onChange={(e) => onUpdate({ ...node, id: e.target.value })}
                  className="w-full px-3 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
                  placeholder="node_id"
                />
              </div>

              {node.type === 'condition' ? (
                <div className="space-y-3">
                  {/* 템플릿 선택 */}
                  <div>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                      조건 유형 선택
                    </label>
                    <select
                      value={selectedTemplateId}
                      onChange={(e) => handleTemplateSelect(e.target.value)}
                      className="w-full px-3 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
                    >
                      <optgroup label="📊 센서 값 비교">
                        <option value="sensor_above">센서 값 초과</option>
                        <option value="sensor_below">센서 값 미만</option>
                        <option value="sensor_range">센서 값 범위 이탈</option>
                      </optgroup>
                      <optgroup label="🔍 품질 관리">
                        <option value="defect_rate">불량률 초과</option>
                        <option value="consecutive_defects">연속 불량 발생</option>
                      </optgroup>
                      <optgroup label="⚙️ 장비 상태">
                        <option value="equipment_status">장비 상태 확인</option>
                        <option value="runtime_exceeded">가동 시간 초과</option>
                      </optgroup>
                      <optgroup label="📦 생산 관리">
                        <option value="production_target">생산 목표 달성</option>
                        <option value="production_delay">생산 지연</option>
                      </optgroup>
                      <optgroup label="🔗 복합 조건">
                        <option value="multi_sensor_alert">복합 센서 이상</option>
                        <option value="shift_check">근무 교대 시간</option>
                      </optgroup>
                      <optgroup label="✏️ 기타">
                        <option value="custom">직접 입력</option>
                      </optgroup>
                    </select>
                    {/* 템플릿 설명 */}
                    {selectedTemplateId !== 'custom' && (
                      <p className="mt-1 text-xs text-slate-500">
                        {conditionTemplates.find(t => t.id === selectedTemplateId)?.description}
                      </p>
                    )}
                  </div>

                  {/* 템플릿 변수 입력 */}
                  {selectedTemplateId !== 'custom' && (
                    <div className="grid grid-cols-2 gap-2">
                      {conditionTemplates
                        .find(t => t.id === selectedTemplateId)
                        ?.variables.map((v) => (
                          <div key={v.name}>
                            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                              {v.placeholder}
                            </label>
                            <input
                              type="text"
                              value={templateValues[v.name] || v.defaultValue}
                              onChange={(e) => handleTemplateValueChange(v.name, e.target.value)}
                              className="w-full px-3 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
                              placeholder={v.defaultValue}
                            />
                          </div>
                        ))}
                    </div>
                  )}

                  {/* 직접 입력 모드 */}
                  {selectedTemplateId === 'custom' && (
                    <div>
                      <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                        조건식 직접 입력
                      </label>
                      <input
                        type="text"
                        value={(node.config as { condition?: string })?.condition || ''}
                        onChange={(e) => handleConfigChange('condition', e.target.value)}
                        className="w-full px-3 py-1.5 text-sm font-mono border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
                        placeholder="temperature > 80 && humidity < 50"
                      />
                      <p className="mt-1 text-xs text-slate-500">
                        Rhai 표현식을 입력하세요 (예: temperature &gt; 80)
                      </p>
                    </div>
                  )}

                  {/* 생성된 조건식 미리보기 */}
                  {selectedTemplateId !== 'custom' && (
                    <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded">
                      <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                        생성된 조건식
                      </label>
                      <code className="text-xs font-mono text-blue-600 dark:text-blue-400">
                        {(node.config as { condition?: string })?.condition || '조건을 설정하세요'}
                      </code>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                      액션 선택
                    </label>
                    <select
                      value={(node.config as { action?: string })?.action || ''}
                      onChange={(e) => handleConfigChange('action', e.target.value)}
                      className="w-full px-3 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
                    >
                      <option value="">액션을 선택하세요...</option>
                      <optgroup label="📢 알림">
                        <option value="send_slack_notification">Slack 알림 전송</option>
                        <option value="send_email">이메일 발송</option>
                        <option value="send_sms">SMS 문자 발송</option>
                      </optgroup>
                      <optgroup label="💾 데이터">
                        <option value="save_to_database">데이터베이스 저장</option>
                        <option value="export_to_csv">CSV 파일 내보내기</option>
                        <option value="log_event">이벤트 로그 기록</option>
                      </optgroup>
                      <optgroup label="⚙️ 제어">
                        <option value="stop_production_line">생산라인 정지</option>
                        <option value="adjust_sensor_threshold">센서 임계값 조정</option>
                        <option value="trigger_maintenance">유지보수 요청 발생</option>
                      </optgroup>
                      <optgroup label="📊 분석">
                        <option value="calculate_defect_rate">불량률 계산</option>
                        <option value="analyze_sensor_trend">센서 추세 분석</option>
                        <option value="predict_equipment_failure">장비 고장 예측</option>
                      </optgroup>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                      파라미터 (JSON)
                    </label>
                    <textarea
                      value={JSON.stringify((node.config as { parameters?: Record<string, unknown> })?.parameters || {}, null, 2)}
                      onChange={(e) => {
                        try {
                          const params = JSON.parse(e.target.value);
                          handleConfigChange('parameters', params);
                        } catch {
                          // JSON 파싱 오류 무시 (입력 중)
                        }
                      }}
                      className="w-full px-3 py-1.5 text-sm font-mono border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 h-20"
                      placeholder='{"key": "value"}'
                    />
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function WorkflowEditor({ initialDSL, onSave, onCancel, isOpen }: WorkflowEditorProps) {
  const [dsl, setDSL] = useState<WorkflowDSL>(initialDSL || defaultDSL);

  if (!isOpen) return null;

  // 노드 추가
  const addNode = (type: 'condition' | 'action') => {
    const newNode: WorkflowNode = {
      id: `${type}_${Date.now()}`,
      type,
      config: type === 'condition' ? { condition: '' } : { action: '', parameters: {} },
      next: [],
    };
    setDSL({
      ...dsl,
      nodes: [...dsl.nodes, newNode],
    });
  };

  // 노드 업데이트
  const updateNode = (index: number, node: WorkflowNode) => {
    const newNodes = [...dsl.nodes];
    newNodes[index] = node;
    setDSL({ ...dsl, nodes: newNodes });
  };

  // 노드 삭제
  const deleteNode = (index: number) => {
    setDSL({
      ...dsl,
      nodes: dsl.nodes.filter((_, i) => i !== index),
    });
  };

  // 노드 이동
  const moveNode = (index: number, direction: 'up' | 'down') => {
    const newNodes = [...dsl.nodes];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    [newNodes[index], newNodes[targetIndex]] = [newNodes[targetIndex], newNodes[index]];
    setDSL({ ...dsl, nodes: newNodes });
  };

  // 저장
  const handleSave = () => {
    // next 배열 자동 생성 (순차 실행)
    const nodesWithNext = dsl.nodes.map((node, index) => ({
      ...node,
      next: index < dsl.nodes.length - 1 ? [dsl.nodes[index + 1].id] : [],
    }));

    onSave?.({
      ...dsl,
      nodes: nodesWithNext,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onCancel} />

      {/* Editor Modal */}
      <div className="relative w-full max-w-4xl max-h-[90vh] mx-4 bg-white dark:bg-slate-900 rounded-xl shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center gap-3">
            <GitBranch className="w-6 h-6 text-blue-500" />
            <div>
              <input
                type="text"
                value={dsl.name}
                onChange={(e) => setDSL({ ...dsl, name: e.target.value })}
                className="text-lg font-semibold bg-transparent border-none focus:outline-none focus:ring-0"
                placeholder="워크플로우 이름"
              />
              <input
                type="text"
                value={dsl.description || ''}
                onChange={(e) => setDSL({ ...dsl, description: e.target.value })}
                className="block text-sm text-slate-500 bg-transparent border-none focus:outline-none focus:ring-0 w-full"
                placeholder="설명을 입력하세요..."
              />
            </div>
          </div>
          <button
            onClick={onCancel}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* 에디터 영역 */}
            <div className="space-y-4">
              {/* 트리거 설정 */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Play className="w-4 h-4 text-green-500" />
                    트리거
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <select
                    value={dsl.trigger.type}
                    onChange={(e) =>
                      setDSL({
                        ...dsl,
                        trigger: { ...dsl.trigger, type: e.target.value as 'event' | 'schedule' | 'manual' },
                      })
                    }
                    className="w-full px-3 py-2 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600"
                  >
                    <option value="manual">수동 실행</option>
                    <option value="event">이벤트 기반</option>
                    <option value="schedule">스케줄 기반</option>
                  </select>
                </CardContent>
              </Card>

              {/* 노드 목록 */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">노드</CardTitle>
                    <div className="flex gap-2">
                      <button
                        onClick={() => addNode('condition')}
                        className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-yellow-100 text-yellow-700 hover:bg-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400"
                      >
                        <Plus className="w-3 h-3" />
                        조건 추가
                      </button>
                      <button
                        onClick={() => addNode('action')}
                        className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-400"
                      >
                        <Plus className="w-3 h-3" />
                        액션 추가
                      </button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {dsl.nodes.length === 0 ? (
                    <div className="text-center py-8 text-slate-500">
                      <GitBranch className="w-12 h-12 mx-auto mb-2 opacity-30" />
                      <p>노드가 없습니다</p>
                      <p className="text-sm">위의 버튼으로 노드를 추가하세요</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {dsl.nodes.map((node, index) => (
                        <NodeEditor
                          key={node.id}
                          node={node}
                          index={index}
                          onUpdate={(n) => updateNode(index, n)}
                          onDelete={() => deleteNode(index)}
                          onMoveUp={() => moveNode(index, 'up')}
                          onMoveDown={() => moveNode(index, 'down')}
                          isFirst={index === 0}
                          isLast={index === dsl.nodes.length - 1}
                        />
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* DSL 미리보기 */}
            <Card className="sticky top-0">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Eye className="w-4 h-4" />
                    DSL 미리보기
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    {dsl.nodes.length > 0 && (
                      <span className="flex items-center gap-1 text-xs text-green-600">
                        <CheckCircle2 className="w-3 h-3" />
                        {dsl.nodes.length}개 노드
                      </span>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="p-3 text-xs font-mono bg-slate-900 text-slate-100 rounded-lg overflow-auto max-h-[500px]">
                  {JSON.stringify(dsl, null, 2)}
                </pre>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 p-4 border-t border-slate-200 dark:border-slate-700">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            <Save className="w-4 h-4" />
            저장
          </button>
        </div>
      </div>
    </div>
  );
}
