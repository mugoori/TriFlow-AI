/**
 * ActionParameterForm
 * 액션별 파라미터를 자동으로 폼 필드로 생성하는 컴포넌트
 */

import { useState } from 'react';
import { ChevronDown, ChevronUp, Info } from 'lucide-react';

// ============ Types ============

interface FieldDefinition {
  key: string;
  label: string;
  type: 'text' | 'number' | 'textarea' | 'select' | 'checkbox' | 'email';
  placeholder?: string;
  required?: boolean;
  options?: { value: string; label: string }[];
  description?: string;
  default?: unknown;
}

interface ActionMetadata {
  name: string;
  label: string;
  description: string;
  category: string;
  fields: FieldDefinition[];
}

interface ActionParameterFormProps {
  action: string;
  parameters: Record<string, unknown>;
  onChange: (parameters: Record<string, unknown>) => void;
}

// ============ Action Metadata ============

const actionMetadata: Record<string, ActionMetadata> = {
  send_slack_notification: {
    name: 'send_slack_notification',
    label: 'Slack 알림',
    description: 'Slack 채널로 알림 메시지를 전송합니다',
    category: 'notification',
    fields: [
      {
        key: 'channel',
        label: '채널',
        type: 'text',
        placeholder: '#alerts',
        required: true,
        description: '# 포함한 채널명 또는 @사용자명',
      },
      {
        key: 'message',
        label: '메시지',
        type: 'textarea',
        placeholder: '알림 메시지를 입력하세요',
        required: true,
        description: '{{변수}} 형식으로 동적 값 삽입 가능',
      },
      {
        key: 'mention',
        label: '멘션',
        type: 'select',
        options: [
          { value: '', label: '없음' },
          { value: '@here', label: '@here' },
          { value: '@channel', label: '@channel' },
        ],
      },
    ],
  },
  send_email: {
    name: 'send_email',
    label: '이메일 발송',
    description: '지정된 수신자에게 이메일을 전송합니다',
    category: 'notification',
    fields: [
      {
        key: 'to',
        label: '수신자',
        type: 'email',
        placeholder: 'user@example.com',
        required: true,
        description: '여러 명은 쉼표로 구분',
      },
      {
        key: 'subject',
        label: '제목',
        type: 'text',
        placeholder: '알림: {{sensor_id}}',
        required: true,
      },
      {
        key: 'body',
        label: '본문',
        type: 'textarea',
        placeholder: '이메일 본문을 입력하세요',
        required: true,
      },
      {
        key: 'priority',
        label: '우선순위',
        type: 'select',
        options: [
          { value: 'low', label: '낮음' },
          { value: 'normal', label: '보통' },
          { value: 'high', label: '높음' },
        ],
        default: 'normal',
      },
    ],
  },
  send_sms: {
    name: 'send_sms',
    label: 'SMS 발송',
    description: '지정된 전화번호로 SMS를 전송합니다',
    category: 'notification',
    fields: [
      {
        key: 'phone_number',
        label: '전화번호',
        type: 'text',
        placeholder: '010-1234-5678',
        required: true,
      },
      {
        key: 'message',
        label: '메시지',
        type: 'textarea',
        placeholder: 'SMS 메시지 (90자 이내 권장)',
        required: true,
      },
    ],
  },
  save_to_database: {
    name: 'save_to_database',
    label: 'DB 저장',
    description: '데이터를 데이터베이스에 저장합니다',
    category: 'data',
    fields: [
      {
        key: 'table_name',
        label: '테이블명',
        type: 'text',
        placeholder: 'event_logs',
        required: true,
      },
      {
        key: 'data_fields',
        label: '저장할 필드',
        type: 'textarea',
        placeholder: '{"field1": "{{value1}}", "field2": "{{value2}}"}',
        description: 'JSON 형식으로 입력',
      },
    ],
  },
  export_to_csv: {
    name: 'export_to_csv',
    label: 'CSV 내보내기',
    description: '데이터를 CSV 파일로 내보냅니다',
    category: 'data',
    fields: [
      {
        key: 'filename',
        label: '파일명',
        type: 'text',
        placeholder: 'export_{{timestamp}}.csv',
        required: true,
      },
      {
        key: 'fields',
        label: '내보낼 필드',
        type: 'text',
        placeholder: 'sensor_id,temperature,timestamp',
        description: '쉼표로 구분',
      },
      {
        key: 'include_header',
        label: '헤더 포함',
        type: 'checkbox',
        default: true,
      },
    ],
  },
  log_event: {
    name: 'log_event',
    label: '로그 기록',
    description: '이벤트 로그를 기록합니다',
    category: 'data',
    fields: [
      {
        key: 'level',
        label: '로그 레벨',
        type: 'select',
        options: [
          { value: 'debug', label: 'DEBUG' },
          { value: 'info', label: 'INFO' },
          { value: 'warning', label: 'WARNING' },
          { value: 'error', label: 'ERROR' },
        ],
        default: 'info',
      },
      {
        key: 'message',
        label: '메시지',
        type: 'textarea',
        placeholder: '로그 메시지',
        required: true,
      },
      {
        key: 'include_context',
        label: '컨텍스트 포함',
        type: 'checkbox',
        default: true,
        description: '센서 데이터 등 컨텍스트 정보 포함',
      },
    ],
  },
  stop_production_line: {
    name: 'stop_production_line',
    label: '라인 정지',
    description: '생산 라인을 긴급 정지합니다',
    category: 'control',
    fields: [
      {
        key: 'line_code',
        label: '라인 ID',
        type: 'text',
        placeholder: 'LINE_001',
        required: true,
      },
      {
        key: 'reason',
        label: '정지 사유',
        type: 'textarea',
        placeholder: '긴급 정지 사유를 입력하세요',
        required: true,
      },
      {
        key: 'notify_supervisor',
        label: '관리자 알림',
        type: 'checkbox',
        default: true,
      },
    ],
  },
  adjust_sensor_threshold: {
    name: 'adjust_sensor_threshold',
    label: '임계값 조정',
    description: '센서 임계값을 동적으로 조정합니다',
    category: 'control',
    fields: [
      {
        key: 'sensor_id',
        label: '센서 ID',
        type: 'text',
        placeholder: 'SENSOR_001',
        required: true,
      },
      {
        key: 'threshold_type',
        label: '임계값 유형',
        type: 'select',
        options: [
          { value: 'min', label: '최소값' },
          { value: 'max', label: '최대값' },
          { value: 'warning', label: '경고' },
          { value: 'critical', label: '위험' },
        ],
        required: true,
      },
      {
        key: 'new_value',
        label: '새 임계값',
        type: 'number',
        placeholder: '100',
        required: true,
      },
    ],
  },
  trigger_maintenance: {
    name: 'trigger_maintenance',
    label: '유지보수 요청',
    description: '유지보수 작업 요청을 생성합니다',
    category: 'control',
    fields: [
      {
        key: 'equipment_id',
        label: '장비 ID',
        type: 'text',
        placeholder: 'EQP_001',
        required: true,
      },
      {
        key: 'maintenance_type',
        label: '유지보수 유형',
        type: 'select',
        options: [
          { value: 'inspection', label: '점검' },
          { value: 'repair', label: '수리' },
          { value: 'replacement', label: '교체' },
          { value: 'calibration', label: '교정' },
        ],
        required: true,
      },
      {
        key: 'priority',
        label: '우선순위',
        type: 'select',
        options: [
          { value: 'low', label: '낮음' },
          { value: 'medium', label: '보통' },
          { value: 'high', label: '높음' },
          { value: 'urgent', label: '긴급' },
        ],
        default: 'medium',
      },
      {
        key: 'description',
        label: '상세 설명',
        type: 'textarea',
        placeholder: '유지보수가 필요한 상세 내용',
      },
    ],
  },
  calculate_defect_rate: {
    name: 'calculate_defect_rate',
    label: '불량률 계산',
    description: '현재 불량률을 계산합니다',
    category: 'analysis',
    fields: [
      {
        key: 'line_code',
        label: '라인 ID',
        type: 'text',
        placeholder: 'LINE_001',
      },
      {
        key: 'time_window',
        label: '계산 기간',
        type: 'select',
        options: [
          { value: '1h', label: '최근 1시간' },
          { value: '8h', label: '최근 8시간' },
          { value: '24h', label: '최근 24시간' },
          { value: 'shift', label: '현재 교대' },
        ],
        default: '1h',
      },
      {
        key: 'store_result',
        label: '결과 저장',
        type: 'checkbox',
        default: true,
      },
    ],
  },
  analyze_sensor_trend: {
    name: 'analyze_sensor_trend',
    label: '추세 분석',
    description: '센서 데이터의 추세를 분석합니다',
    category: 'analysis',
    fields: [
      {
        key: 'sensor_id',
        label: '센서 ID',
        type: 'text',
        placeholder: 'SENSOR_001',
        required: true,
      },
      {
        key: 'analysis_type',
        label: '분석 유형',
        type: 'select',
        options: [
          { value: 'moving_average', label: '이동 평균' },
          { value: 'trend_detection', label: '추세 감지' },
          { value: 'anomaly_detection', label: '이상 감지' },
        ],
        default: 'trend_detection',
      },
      {
        key: 'window_size',
        label: '윈도우 크기',
        type: 'number',
        placeholder: '10',
        default: 10,
      },
    ],
  },
  predict_equipment_failure: {
    name: 'predict_equipment_failure',
    label: '고장 예측',
    description: '장비 고장을 예측합니다',
    category: 'analysis',
    fields: [
      {
        key: 'equipment_id',
        label: '장비 ID',
        type: 'text',
        placeholder: 'EQP_001',
        required: true,
      },
      {
        key: 'prediction_horizon',
        label: '예측 기간',
        type: 'select',
        options: [
          { value: '1h', label: '1시간' },
          { value: '4h', label: '4시간' },
          { value: '8h', label: '8시간' },
          { value: '24h', label: '24시간' },
        ],
        default: '4h',
      },
      {
        key: 'confidence_threshold',
        label: '신뢰도 임계값',
        type: 'number',
        placeholder: '0.8',
        default: 0.8,
        description: '0.0 ~ 1.0 사이 값',
      },
    ],
  },
};

// ============ Field Renderer ============

interface FieldRendererProps {
  field: FieldDefinition;
  value: unknown;
  onChange: (value: unknown) => void;
}

function FieldRenderer({ field, value, onChange }: FieldRendererProps) {
  const id = `field_${field.key}`;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label
          htmlFor={id}
          className="text-xs font-medium text-slate-600 dark:text-slate-400"
        >
          {field.label}
          {field.required && <span className="text-red-500 ml-0.5">*</span>}
        </label>
        {field.description && (
          <div className="group relative">
            <Info className="w-3 h-3 text-slate-400 cursor-help" />
            <div className="absolute bottom-full right-0 mb-1 w-48 p-2 text-xs bg-slate-800 text-white rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-10">
              {field.description}
            </div>
          </div>
        )}
      </div>

      {field.type === 'text' && (
        <input
          id={id}
          type="text"
          value={(value as string) || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className="w-full px-2 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
        />
      )}

      {field.type === 'email' && (
        <input
          id={id}
          type="email"
          value={(value as string) || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className="w-full px-2 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
        />
      )}

      {field.type === 'number' && (
        <input
          id={id}
          type="number"
          value={(value as number) ?? (field.default as number) ?? ''}
          onChange={(e) =>
            onChange(e.target.value ? parseFloat(e.target.value) : undefined)
          }
          placeholder={field.placeholder}
          className="w-full px-2 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
        />
      )}

      {field.type === 'textarea' && (
        <textarea
          id={id}
          value={(value as string) || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          rows={3}
          className="w-full px-2 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100 resize-none"
        />
      )}

      {field.type === 'select' && (
        <select
          id={id}
          value={(value as string) ?? (field.default as string) ?? ''}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-2 py-1.5 text-sm border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100"
        >
          {field.options?.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )}

      {field.type === 'checkbox' && (
        <div className="flex items-center gap-2">
          <input
            id={id}
            type="checkbox"
            checked={(value as boolean) ?? (field.default as boolean) ?? false}
            onChange={(e) => onChange(e.target.checked)}
            className="rounded border-slate-300"
          />
          <span className="text-xs text-slate-500">{field.placeholder}</span>
        </div>
      )}
    </div>
  );
}

// ============ Main Component ============

export function ActionParameterForm({
  action,
  parameters,
  onChange,
}: ActionParameterFormProps) {
  const [showJson, setShowJson] = useState(false);
  const metadata = actionMetadata[action];

  // 액션이 없거나 메타데이터가 없으면 JSON 입력으로 fallback
  if (!action || !metadata) {
    return (
      <div>
        <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
          파라미터 (JSON)
        </label>
        <textarea
          value={JSON.stringify(parameters || {}, null, 2)}
          onChange={(e) => {
            try {
              onChange(JSON.parse(e.target.value));
            } catch {
              // ignore parse error while typing
            }
          }}
          className="w-full px-2 py-1.5 text-xs font-mono border rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-slate-100 h-20"
          placeholder='{"key": "value"}'
        />
      </div>
    );
  }

  const handleFieldChange = (key: string, value: unknown) => {
    onChange({ ...parameters, [key]: value });
  };

  return (
    <div className="space-y-3">
      {/* 액션 설명 */}
      <p className="text-xs text-slate-500">{metadata.description}</p>

      {/* 필드들 */}
      {metadata.fields.map((field) => (
        <FieldRenderer
          key={field.key}
          field={field}
          value={parameters[field.key]}
          onChange={(value) => handleFieldChange(field.key, value)}
        />
      ))}

      {/* JSON 보기 토글 */}
      <button
        onClick={() => setShowJson(!showJson)}
        className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
      >
        {showJson ? (
          <ChevronUp className="w-3 h-3" />
        ) : (
          <ChevronDown className="w-3 h-3" />
        )}
        JSON 보기
      </button>

      {showJson && (
        <pre className="p-2 text-xs font-mono bg-slate-100 dark:bg-slate-900 rounded overflow-x-auto">
          {JSON.stringify(parameters, null, 2)}
        </pre>
      )}
    </div>
  );
}
