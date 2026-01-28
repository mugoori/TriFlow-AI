/**
 * AI Model Configuration Section
 * 관리자 전용: AI 모델 설정 (테넌트별/기능별)
 */
import { useState, useEffect } from 'react';
import { settingsService } from '../../services/settingsService';

// 사용 가능한 AI 모델 목록
const AVAILABLE_MODELS = [
  { id: '', name: '(기본값 사용)' },
  { id: 'claude-sonnet-4-5-20250929', name: 'Claude Sonnet 4.5 (Latest)' },
  { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet' },
  { id: 'claude-3-haiku-20240307', name: 'Claude 3 Haiku (Fast/Cheap)' },
];

// 에이전트별 설정 키와 표시 이름
const AGENT_MODEL_SETTINGS = [
  { key: 'default_llm_model', label: '기본 모델', description: '모든 에이전트의 기본 모델', required: true },
  { key: 'meta_router_model', label: 'Meta Router', description: 'Intent 분류 에이전트' },
  { key: 'bi_planner_model', label: 'BI Planner', description: 'Text-to-SQL, 차트 생성' },
  { key: 'workflow_planner_model', label: 'Workflow Planner', description: '워크플로우 DSL 생성' },
  { key: 'judgment_agent_model', label: 'Judgment Agent', description: '센서 판단, 규칙 실행' },
  { key: 'learning_agent_model', label: 'Learning Agent', description: '피드백 분석, 규칙 제안' },
];

interface AIModelSettings {
  default_llm_model: string;
  meta_router_model: string;
  bi_planner_model: string;
  workflow_planner_model: string;
  judgment_agent_model: string;
  learning_agent_model: string;
}

export default function AIModelConfigSection() {
  const [settings, setSettings] = useState<AIModelSettings>({
    default_llm_model: 'claude-sonnet-4-5-20250929',
    meta_router_model: '',
    bi_planner_model: '',
    workflow_planner_model: '',
    judgment_agent_model: '',
    learning_agent_model: '',
  });

  const [loading, setLoading] = useState(true);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  // 설정 로드
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const response = await settingsService.getSettings('ai');
        const settingsMap: Record<string, string> = {};
        response.settings.forEach((s) => {
          if (s.key in settings) {
            settingsMap[s.key] = s.value || '';
          }
        });
        setSettings((prev) => ({ ...prev, ...settingsMap }));
      } catch (error) {
        console.error('[AIModelConfig] Failed to load:', error);
      } finally {
        setLoading(false);
      }
    };
    loadSettings();
  }, []);

  // 설정 변경 핸들러
  const handleChange = (key: keyof AIModelSettings, value: string) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaveStatus('idle');
  };

  // 설정 저장
  const handleSave = async () => {
    setSaveStatus('saving');
    setErrorMessage('');

    try {
      // 빈 값이 아닌 설정만 저장
      const settingsToSave: Record<string, string> = {};
      Object.entries(settings).forEach(([key, value]) => {
        // default_llm_model은 항상 저장, 나머지는 값이 있을 때만
        if (key === 'default_llm_model' || value) {
          settingsToSave[key] = value;
        }
      });

      await settingsService.updateSettings(settingsToSave);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('[AIModelConfig] Failed to save:', error);
      setSaveStatus('error');
      setErrorMessage(error instanceof Error ? error.message : 'Unknown error');
    }
  };

  // 모든 에이전트 모델을 Haiku로 설정
  const applyHaikuPreset = () => {
    setSettings({
      default_llm_model: 'claude-3-haiku-20240307',
      meta_router_model: '',
      bi_planner_model: '',
      workflow_planner_model: '',
      judgment_agent_model: '',
      learning_agent_model: '',
    });
    setSaveStatus('idle');
  };

  // 하이브리드 프리셋 (Haiku 기본 + BI만 Sonnet)
  const applyHybridPreset = () => {
    setSettings({
      default_llm_model: 'claude-3-haiku-20240307',
      meta_router_model: '',
      bi_planner_model: 'claude-sonnet-4-5-20250929',  // BI만 Sonnet
      workflow_planner_model: '',
      judgment_agent_model: '',
      learning_agent_model: '',
    });
    setSaveStatus('idle');
  };

  // 기본 프리셋 (전체 Sonnet)
  const applySonnetPreset = () => {
    setSettings({
      default_llm_model: 'claude-sonnet-4-5-20250929',
      meta_router_model: '',
      bi_planner_model: '',
      workflow_planner_model: '',
      judgment_agent_model: '',
      learning_agent_model: '',
    });
    setSaveStatus('idle');
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-slate-200 dark:bg-slate-700 rounded w-1/3 mb-4"></div>
          <div className="space-y-3">
            <div className="h-10 bg-slate-200 dark:bg-slate-700 rounded"></div>
            <div className="h-10 bg-slate-200 dark:bg-slate-700 rounded"></div>
            <div className="h-10 bg-slate-200 dark:bg-slate-700 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <span className="text-lg">🤖</span>
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">AI 모델 설정</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">에이전트별 LLM 모델 설정 (DB 저장)</p>
          </div>
        </div>

        {/* 프리셋 버튼들 */}
        <div className="flex gap-2">
          <button
            onClick={applySonnetPreset}
            className="px-3 py-1.5 text-xs font-medium bg-blue-50 text-blue-600 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400 dark:hover:bg-blue-900/30 rounded transition-colors"
          >
            Sonnet (품질)
          </button>
          <button
            onClick={applyHybridPreset}
            className="px-3 py-1.5 text-xs font-medium bg-purple-50 text-purple-600 hover:bg-purple-100 dark:bg-purple-900/20 dark:text-purple-400 dark:hover:bg-purple-900/30 rounded transition-colors"
          >
            하이브리드
          </button>
          <button
            onClick={applyHaikuPreset}
            className="px-3 py-1.5 text-xs font-medium bg-green-50 text-green-600 hover:bg-green-100 dark:bg-green-900/20 dark:text-green-400 dark:hover:bg-green-900/30 rounded transition-colors"
          >
            Haiku (비용)
          </button>
        </div>
      </div>

      {/* 비용 안내 */}
      <div className="mb-6 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
        <p className="text-sm text-amber-700 dark:text-amber-300">
          <strong>💡 비용 참고:</strong> Haiku는 Sonnet 대비 약 12배 저렴합니다.
          단, 복잡한 SQL 생성이나 DSL 생성 품질이 낮아질 수 있습니다.
        </p>
      </div>

      {/* 설정 목록 */}
      <div className="space-y-4">
        {AGENT_MODEL_SETTINGS.map((agent) => (
          <div key={agent.key} className="flex items-center gap-4">
            <div className="w-40 flex-shrink-0">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                {agent.label}
                {agent.required && <span className="text-red-500 ml-1">*</span>}
              </label>
              <p className="text-xs text-slate-500 dark:text-slate-400">{agent.description}</p>
            </div>
            <div className="flex-1">
              <select
                value={settings[agent.key as keyof AIModelSettings]}
                onChange={(e) => handleChange(agent.key as keyof AIModelSettings, e.target.value)}
                className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {AVAILABLE_MODELS.map((model) => (
                  // 기본 모델은 "(기본값 사용)" 옵션 제외
                  (agent.required && model.id === '') ? null : (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  )
                ))}
              </select>
            </div>
            {/* 현재 값 표시 */}
            <div className="w-24 text-right">
              {settings[agent.key as keyof AIModelSettings] ? (
                <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded">
                  {settings[agent.key as keyof AIModelSettings].includes('haiku') ? 'Haiku' : 'Sonnet'}
                </span>
              ) : (
                <span className="text-xs px-2 py-1 bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400 rounded">
                  기본값
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 저장 버튼 영역 */}
      <div className="mt-6 pt-4 border-t border-slate-200 dark:border-slate-700 flex items-center justify-between">
        <div className="text-sm">
          {saveStatus === 'saved' && (
            <span className="text-green-600 dark:text-green-400 flex items-center gap-1">
              <span>✓</span> AI 모델 설정이 저장되었습니다
            </span>
          )}
          {saveStatus === 'error' && (
            <span className="text-red-600 dark:text-red-400">
              저장 실패: {errorMessage || '관리자 권한이 필요합니다'}
            </span>
          )}
        </div>

        <button
          onClick={handleSave}
          disabled={saveStatus === 'saving'}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
        >
          {saveStatus === 'saving' ? '저장 중...' : 'AI 모델 설정 저장'}
        </button>
      </div>

      {/* 설정 우선순위 안내 */}
      <div className="mt-4 p-3 bg-slate-50 dark:bg-slate-900 rounded-lg text-xs text-slate-600 dark:text-slate-400">
        <strong>설정 우선순위:</strong> 에이전트별 설정 → 기본 모델 → 환경변수 → 코드 기본값
      </div>
    </div>
  );
}
