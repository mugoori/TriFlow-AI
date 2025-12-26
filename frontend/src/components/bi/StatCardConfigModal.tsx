/**
 * StatCardConfigModal
 * StatCard 추가/편집 모달
 *
 * 3가지 소스 유형 지원:
 * - KPI: bi.dim_kpi에서 선택
 * - DB Query: 테이블/컬럼/집계 함수 선택
 * - MCP Tool: MCP 서버/도구 선택
 */

import { useState, useEffect } from 'react';
import { X, BarChart3, Database, Plug, Loader2 } from 'lucide-react';
import { useStatCards } from '@/contexts/StatCardContext';
import type {
  SourceType,
  AggregationType,
  StatCardConfigCreate,
  StatCardConfigUpdate,
  StatCardConfig,
} from '@/types/statcard';
import { SOURCE_TYPE_INFO, AGGREGATION_LABELS } from '@/types/statcard';

// 카테고리 한글 매핑
const CATEGORY_LABELS: Record<string, string> = {
  efficiency: '효율성',
  inventory: '재고',
  production: '생산',
  quality: '품질',
};

// 사용 가능한 아이콘 목록
const AVAILABLE_ICONS = [
  'BarChart3',
  'TrendingUp',
  'AlertTriangle',
  'Activity',
  'Clock',
  'Factory',
  'Gauge',
  'Thermometer',
  'Droplets',
  'Zap',
  'Target',
  'Package',
  'Settings',
];

interface StatCardConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  editConfig?: StatCardConfig; // 수정 모드일 때 기존 설정
}

export function StatCardConfigModal({ isOpen, onClose, editConfig }: StatCardConfigModalProps) {
  const {
    createCard,
    updateCard,
    availableKpis,
    kpiCategories,
    availableTables,
    availableMcpTools,
    optionsLoading,
    fetchOptions,
  } = useStatCards();

  // 폼 상태
  const [sourceType, setSourceType] = useState<SourceType>('kpi');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // KPI 설정
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedKpiCode, setSelectedKpiCode] = useState<string>('');

  // DB Query 설정
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [selectedColumn, setSelectedColumn] = useState<string>('');
  const [selectedAggregation, setSelectedAggregation] = useState<AggregationType>('avg');
  const [filterCondition, setFilterCondition] = useState<string>('');

  // MCP Tool 설정
  const [selectedMcpServerId, setSelectedMcpServerId] = useState<string>('');
  const [selectedMcpToolName, setSelectedMcpToolName] = useState<string>('');
  const [mcpParams, setMcpParams] = useState<string>('');
  const [mcpResultKey, setMcpResultKey] = useState<string>('');

  // 표시 설정
  const [customTitle, setCustomTitle] = useState<string>('');
  const [customIcon, setCustomIcon] = useState<string>('BarChart3');
  const [customUnit, setCustomUnit] = useState<string>('');

  // 임계값 설정 (DB Query, MCP용)
  const [greenThreshold, setGreenThreshold] = useState<string>('');
  const [yellowThreshold, setYellowThreshold] = useState<string>('');
  const [redThreshold, setRedThreshold] = useState<string>('');
  const [higherIsBetter, setHigherIsBetter] = useState(true);

  // 옵션 로드
  useEffect(() => {
    if (isOpen) {
      fetchOptions();
    }
  }, [isOpen, fetchOptions]);

  // 수정 모드일 때 기존 값 로드
  useEffect(() => {
    if (editConfig) {
      setSourceType(editConfig.source_type);

      // KPI
      setSelectedKpiCode(editConfig.kpi_code || '');

      // DB Query
      setSelectedTable(editConfig.table_name || '');
      setSelectedColumn(editConfig.column_name || '');
      setSelectedAggregation(editConfig.aggregation || 'avg');
      setFilterCondition(editConfig.filter_condition ? JSON.stringify(editConfig.filter_condition) : '');

      // MCP Tool
      setSelectedMcpServerId(editConfig.mcp_server_id || '');
      setSelectedMcpToolName(editConfig.mcp_tool_name || '');
      setMcpParams(editConfig.mcp_params ? JSON.stringify(editConfig.mcp_params) : '');
      setMcpResultKey(editConfig.mcp_result_key || '');

      // 표시 설정
      setCustomTitle(editConfig.custom_title || '');
      setCustomIcon(editConfig.custom_icon || 'BarChart3');
      setCustomUnit(editConfig.custom_unit || '');

      // 임계값
      setGreenThreshold(editConfig.green_threshold?.toString() || '');
      setYellowThreshold(editConfig.yellow_threshold?.toString() || '');
      setRedThreshold(editConfig.red_threshold?.toString() || '');
      setHigherIsBetter(editConfig.higher_is_better);
    } else {
      // 새로 만들기 - 초기화
      resetForm();
    }
  }, [editConfig]);

  // 카테고리별 KPI 필터링
  const filteredKpis = selectedCategory
    ? availableKpis.filter((kpi) => kpi.category === selectedCategory)
    : availableKpis;

  // 선택된 테이블의 컬럼 목록
  const selectedTableInfo = availableTables.find(
    (t) => `${t.schema_name}.${t.table_name}` === selectedTable
  );
  const availableColumns = selectedTableInfo?.columns || [];

  // 선택된 컬럼의 허용된 집계 함수
  const selectedColumnInfo = availableColumns.find((c) => c.column_name === selectedColumn);
  const allowedAggregations = selectedColumnInfo?.allowed_aggregations || ['sum', 'avg', 'min', 'max', 'count', 'last'];

  // 선택된 MCP 서버의 도구 목록
  const filteredMcpTools = selectedMcpServerId
    ? availableMcpTools.filter((t) => t.server_id === selectedMcpServerId)
    : availableMcpTools;

  // MCP 서버 목록 (중복 제거)
  const mcpServers = Array.from(
    new Map(availableMcpTools.map((t) => [t.server_id, { server_id: t.server_id, server_name: t.server_name }])).values()
  );

  const resetForm = () => {
    setSourceType('kpi');
    setSelectedCategory('');
    setSelectedKpiCode('');
    setSelectedTable('');
    setSelectedColumn('');
    setSelectedAggregation('avg');
    setFilterCondition('');
    setSelectedMcpServerId('');
    setSelectedMcpToolName('');
    setMcpParams('');
    setMcpResultKey('');
    setCustomTitle('');
    setCustomIcon('BarChart3');
    setCustomUnit('');
    setGreenThreshold('');
    setYellowThreshold('');
    setRedThreshold('');
    setHigherIsBetter(true);
    setError(null);
  };

  const handleSubmit = async () => {
    setError(null);
    setIsSubmitting(true);

    try {
      // 유효성 검사
      if (sourceType === 'kpi' && !selectedKpiCode) {
        throw new Error('KPI를 선택해주세요.');
      }
      if (sourceType === 'db_query' && (!selectedTable || !selectedColumn || !selectedAggregation)) {
        throw new Error('테이블, 컬럼, 집계 함수를 모두 선택해주세요.');
      }
      if (sourceType === 'mcp_tool' && (!selectedMcpServerId || !selectedMcpToolName)) {
        throw new Error('MCP 서버와 도구를 선택해주세요.');
      }

      // 설정 객체 구성
      const config: StatCardConfigCreate | StatCardConfigUpdate = {
        source_type: sourceType,
        display_order: editConfig?.display_order ?? 99,
        is_visible: true,
        higher_is_better: higherIsBetter,
        cache_ttl_seconds: 60,
      };

      // 소스별 설정
      if (sourceType === 'kpi') {
        config.kpi_code = selectedKpiCode;
      } else if (sourceType === 'db_query') {
        const [_schemaName, tableName] = selectedTable.split('.');
        config.table_name = tableName;
        config.column_name = selectedColumn;
        config.aggregation = selectedAggregation;
        if (filterCondition) {
          try {
            config.filter_condition = JSON.parse(filterCondition);
          } catch {
            throw new Error('필터 조건이 올바른 JSON 형식이 아닙니다.');
          }
        }
      } else if (sourceType === 'mcp_tool') {
        config.mcp_server_id = selectedMcpServerId;
        config.mcp_tool_name = selectedMcpToolName;
        if (mcpParams) {
          try {
            config.mcp_params = JSON.parse(mcpParams);
          } catch {
            throw new Error('MCP 파라미터가 올바른 JSON 형식이 아닙니다.');
          }
        }
        config.mcp_result_key = mcpResultKey || undefined;
      }

      // 표시 설정
      if (customTitle) config.custom_title = customTitle;
      if (customIcon) config.custom_icon = customIcon;
      if (customUnit) config.custom_unit = customUnit;

      // 임계값 (DB Query, MCP용)
      if (sourceType !== 'kpi') {
        if (greenThreshold) config.green_threshold = parseFloat(greenThreshold);
        if (yellowThreshold) config.yellow_threshold = parseFloat(yellowThreshold);
        if (redThreshold) config.red_threshold = parseFloat(redThreshold);
      }

      // 생성 또는 수정
      if (editConfig) {
        await updateCard(editConfig.config_id, config);
      } else {
        await createCard(config as StatCardConfigCreate);
      }

      onClose();
      resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장에 실패했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            {editConfig ? 'StatCard 편집' : 'StatCard 추가'}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4 overflow-y-auto max-h-[calc(90vh-140px)]">
          {optionsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
              <span className="ml-2 text-slate-500">옵션 로딩 중...</span>
            </div>
          ) : (
            <div className="space-y-6">
              {/* 소스 유형 선택 */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-2">데이터 소스</label>
                <div className="grid grid-cols-3 gap-2">
                  {(['kpi', 'db_query', 'mcp_tool'] as SourceType[]).map((type) => {
                    const info = SOURCE_TYPE_INFO[type];
                    const Icon = type === 'kpi' ? BarChart3 : type === 'db_query' ? Database : Plug;
                    return (
                      <button
                        key={type}
                        onClick={() => setSourceType(type)}
                        className={`p-3 rounded-lg border-2 text-center transition-colors ${
                          sourceType === type
                            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                            : 'border-slate-200 dark:border-slate-600 hover:border-slate-300 dark:hover:border-slate-500'
                        }`}
                      >
                        <Icon className={`w-5 h-5 mx-auto ${sourceType === type ? 'text-blue-500' : 'text-slate-400'}`} />
                        <span className={`text-sm mt-1 block ${sourceType === type ? 'text-blue-600 dark:text-blue-400 font-medium' : 'text-slate-600 dark:text-slate-300'}`}>
                          {info.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                  {SOURCE_TYPE_INFO[sourceType].description}
                </p>
              </div>

              {/* KPI 설정 */}
              {sourceType === 'kpi' && (
                <div className="space-y-4">
                  {/* 카테고리 선택 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">카테고리</label>
                    <select
                      value={selectedCategory}
                      onChange={(e) => {
                        setSelectedCategory(e.target.value);
                        setSelectedKpiCode('');
                      }}
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100"
                    >
                      <option value="">전체</option>
                      {kpiCategories.map((cat) => (
                        <option key={cat} value={cat}>{CATEGORY_LABELS[cat] || cat}</option>
                      ))}
                    </select>
                  </div>

                  {/* KPI 선택 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">KPI 선택</label>
                    <select
                      value={selectedKpiCode}
                      onChange={(e) => setSelectedKpiCode(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100"
                    >
                      <option value="">선택하세요</option>
                      {filteredKpis.map((kpi) => (
                        <option key={kpi.kpi_code} value={kpi.kpi_code}>
                          {kpi.name} {kpi.unit ? `(${kpi.unit})` : ''}
                        </option>
                      ))}
                    </select>
                    {selectedKpiCode && (
                      <p className="text-xs text-slate-500 mt-1">
                        {availableKpis.find((k) => k.kpi_code === selectedKpiCode)?.description}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* DB Query 설정 */}
              {sourceType === 'db_query' && (
                <div className="space-y-4">
                  {/* 테이블 선택 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">테이블</label>
                    <select
                      value={selectedTable}
                      onChange={(e) => {
                        setSelectedTable(e.target.value);
                        setSelectedColumn('');
                      }}
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100"
                    >
                      <option value="">선택하세요</option>
                      {availableTables.map((t) => (
                        <option key={`${t.schema_name}.${t.table_name}`} value={`${t.schema_name}.${t.table_name}`}>
                          {t.schema_name}.{t.table_name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* 컬럼 선택 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">컬럼</label>
                    <select
                      value={selectedColumn}
                      onChange={(e) => setSelectedColumn(e.target.value)}
                      disabled={!selectedTable}
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 disabled:opacity-50"
                    >
                      <option value="">선택하세요</option>
                      {availableColumns.map((c) => (
                        <option key={c.column_name} value={c.column_name}>
                          {c.column_name} ({c.data_type})
                        </option>
                      ))}
                    </select>
                    {selectedColumn && selectedColumnInfo?.description && (
                      <p className="text-xs text-slate-500 mt-1">{selectedColumnInfo.description}</p>
                    )}
                  </div>

                  {/* 집계 함수 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">집계 함수</label>
                    <select
                      value={selectedAggregation}
                      onChange={(e) => setSelectedAggregation(e.target.value as AggregationType)}
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100"
                    >
                      {(Object.keys(AGGREGATION_LABELS) as AggregationType[]).map((agg) => (
                        <option
                          key={agg}
                          value={agg}
                          disabled={!allowedAggregations.includes(agg)}
                        >
                          {AGGREGATION_LABELS[agg]}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* 필터 조건 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">필터 조건 (JSON, 선택사항)</label>
                    <input
                      type="text"
                      value={filterCondition}
                      onChange={(e) => setFilterCondition(e.target.value)}
                      placeholder='{"line_code": "L1"}'
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 placeholder:text-slate-400"
                    />
                  </div>
                </div>
              )}

              {/* MCP Tool 설정 */}
              {sourceType === 'mcp_tool' && (
                <div className="space-y-4">
                  {/* MCP 서버 선택 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">MCP 서버</label>
                    <select
                      value={selectedMcpServerId}
                      onChange={(e) => {
                        setSelectedMcpServerId(e.target.value);
                        setSelectedMcpToolName('');
                      }}
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100"
                    >
                      <option value="">선택하세요</option>
                      {mcpServers.map((s) => (
                        <option key={s.server_id} value={s.server_id}>{s.server_name}</option>
                      ))}
                    </select>
                  </div>

                  {/* MCP 도구 선택 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">도구</label>
                    <select
                      value={selectedMcpToolName}
                      onChange={(e) => setSelectedMcpToolName(e.target.value)}
                      disabled={!selectedMcpServerId}
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 disabled:opacity-50"
                    >
                      <option value="">선택하세요</option>
                      {filteredMcpTools.map((t) => (
                        <option key={t.tool_name} value={t.tool_name}>{t.tool_name}</option>
                      ))}
                    </select>
                    {selectedMcpToolName && (
                      <p className="text-xs text-slate-500 mt-1">
                        {filteredMcpTools.find((t) => t.tool_name === selectedMcpToolName)?.description}
                      </p>
                    )}
                  </div>

                  {/* MCP 파라미터 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">파라미터 (JSON, 선택사항)</label>
                    <input
                      type="text"
                      value={mcpParams}
                      onChange={(e) => setMcpParams(e.target.value)}
                      placeholder='{"date": "today"}'
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 placeholder:text-slate-400"
                    />
                  </div>

                  {/* 결과 키 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">결과 추출 키 (선택사항)</label>
                    <input
                      type="text"
                      value={mcpResultKey}
                      onChange={(e) => setMcpResultKey(e.target.value)}
                      placeholder="data.total_count"
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 placeholder:text-slate-400"
                    />
                    <p className="text-xs text-slate-500 mt-1">응답 JSON에서 값을 추출할 경로</p>
                  </div>
                </div>
              )}

              {/* 표시 설정 */}
              <div className="border-t border-slate-200 dark:border-slate-700 pt-4">
                <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">표시 설정 (선택사항)</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">커스텀 제목</label>
                    <input
                      type="text"
                      value={customTitle}
                      onChange={(e) => setCustomTitle(e.target.value)}
                      placeholder="기본값 사용"
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">커스텀 단위</label>
                    <input
                      type="text"
                      value={customUnit}
                      onChange={(e) => setCustomUnit(e.target.value)}
                      placeholder="%, 개, 건 등"
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400"
                    />
                  </div>
                </div>

                {/* 아이콘 선택 */}
                <div className="mt-4">
                  <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">아이콘</label>
                  <select
                    value={customIcon}
                    onChange={(e) => setCustomIcon(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-sm text-slate-900 dark:text-slate-100"
                  >
                    {AVAILABLE_ICONS.map((icon) => (
                      <option key={icon} value={icon}>{icon}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* 임계값 설정 (DB Query, MCP용) */}
              {sourceType !== 'kpi' && (
                <div className="border-t border-slate-200 dark:border-slate-700 pt-4">
                  <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">임계값 설정 (선택사항)</h3>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="block text-xs text-green-600 dark:text-green-400 mb-1">정상</label>
                      <input
                        type="number"
                        value={greenThreshold}
                        onChange={(e) => setGreenThreshold(e.target.value)}
                        className="w-full px-2 py-1 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-sm text-slate-900 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-yellow-600 dark:text-yellow-400 mb-1">주의</label>
                      <input
                        type="number"
                        value={yellowThreshold}
                        onChange={(e) => setYellowThreshold(e.target.value)}
                        className="w-full px-2 py-1 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-sm text-slate-900 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-red-600 dark:text-red-400 mb-1">위험</label>
                      <input
                        type="number"
                        value={redThreshold}
                        onChange={(e) => setRedThreshold(e.target.value)}
                        className="w-full px-2 py-1 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-sm text-slate-900 dark:text-slate-100"
                      />
                    </div>
                  </div>
                  <div className="mt-2">
                    <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
                      <input
                        type="checkbox"
                        checked={higherIsBetter}
                        onChange={(e) => setHigherIsBetter(e.target.checked)}
                        className="rounded"
                      />
                      높을수록 좋음
                    </label>
                  </div>
                </div>
              )}

              {/* 에러 메시지 */}
              {error && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
                  {error}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 dark:border-slate-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || optionsLoading}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
            {editConfig ? '저장' : '추가'}
          </button>
        </div>
      </div>
    </div>
  );
}
