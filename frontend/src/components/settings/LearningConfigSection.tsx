/**
 * Learning Configuration Section
 * 학습 파이프라인 설정 관리 (샘플 품질, 자동 추출, 규칙 추출, 골든셋)
 */
import { useState, useEffect, useCallback } from 'react';
import { settingsService } from '../../services/settingsService';
import { Database, RefreshCw, AlertCircle, CheckCircle, Sliders } from 'lucide-react';
import { useToast } from '../ui/Toast';

interface LearningConfigSectionProps {
  isAdmin: boolean;
}

interface LearningSettings {
  // Sample Curation
  learning_min_quality_score: string;
  learning_auto_extract_enabled: string;
  learning_auto_extract_interval_hours: string;
  // Rule Extraction
  learning_max_tree_depth: string;
  learning_min_samples_split: string;
  // Golden Set
  learning_golden_set_auto_update: string;
  learning_golden_set_threshold: string;
}

const DEFAULT_SETTINGS: LearningSettings = {
  learning_min_quality_score: '0.6',
  learning_auto_extract_enabled: 'false',
  learning_auto_extract_interval_hours: '6',
  learning_max_tree_depth: '5',
  learning_min_samples_split: '20',
  learning_golden_set_auto_update: 'false',
  learning_golden_set_threshold: '50',
};

export default function LearningConfigSection({ isAdmin }: LearningConfigSectionProps) {
  const [settings, setSettings] = useState<LearningSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const toast = useToast();

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await settingsService.getSettings('learning');
      const settingsMap: Record<string, string> = {};
      response.settings.forEach((s) => {
        settingsMap[s.key] = s.value || '';
      });

      setSettings({
        ...DEFAULT_SETTINGS,
        ...settingsMap,
      });
    } catch (err) {
      console.error('Failed to load learning settings:', err);
      setError('학습 설정을 불러오는데 실패했습니다');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const validateSettings = (settings: LearningSettings): Record<string, string> => {
    const errors: Record<string, string> = {};

    // Min Quality Score: 0-1
    const qualityScore = parseFloat(settings.learning_min_quality_score);
    if (isNaN(qualityScore) || qualityScore < 0 || qualityScore > 1) {
      errors.learning_min_quality_score = '품질 점수는 0과 1 사이여야 합니다';
    }

    // Auto Extract Interval: 1-24
    const interval = parseInt(settings.learning_auto_extract_interval_hours);
    if (isNaN(interval) || interval < 1 || interval > 24) {
      errors.learning_auto_extract_interval_hours = '추출 주기는 1~24시간 사이여야 합니다';
    }

    // Max Tree Depth: 3-10
    const treeDepth = parseInt(settings.learning_max_tree_depth);
    if (isNaN(treeDepth) || treeDepth < 3 || treeDepth > 10) {
      errors.learning_max_tree_depth = '트리 깊이는 3~10 사이여야 합니다';
    }

    // Min Samples Split: 10-100
    const minSamples = parseInt(settings.learning_min_samples_split);
    if (isNaN(minSamples) || minSamples < 10 || minSamples > 100) {
      errors.learning_min_samples_split = '최소 샘플은 10~100 사이여야 합니다';
    }

    // Golden Set Threshold: 10-100
    const threshold = parseInt(settings.learning_golden_set_threshold);
    if (isNaN(threshold) || threshold < 10 || threshold > 100) {
      errors.learning_golden_set_threshold = '임계값은 10~100 사이여야 합니다';
    }

    return errors;
  };

  const handleChange = (key: keyof LearningSettings, value: string) => {
    const newSettings = { ...settings, [key]: value };
    setSettings(newSettings);
    setSaveStatus('idle');

    // Real-time validation for this field
    const tempSettings = { ...settings, [key]: value };
    const errors = validateSettings(tempSettings);

    // Only keep error for current field if it exists
    if (errors[key]) {
      setValidationErrors((prev) => ({ ...prev, [key]: errors[key] }));
    } else {
      setValidationErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[key];
        return newErrors;
      });
    }
  };

  const handleToggle = (key: keyof LearningSettings) => {
    const newValue = settings[key] === 'true' ? 'false' : 'true';
    handleChange(key, newValue);
  };

  const handleSave = async () => {
    if (!isAdmin) {
      setError('관리자만 설정을 변경할 수 있습니다');
      toast.error('관리자만 설정을 변경할 수 있습니다');
      return;
    }

    // Validation check
    const errors = validateSettings(settings);
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      const firstError = Object.values(errors)[0];
      toast.error(`입력 오류: ${firstError}`);
      setSaveStatus('error');
      return;
    }

    setSaveStatus('saving');
    setError(null);
    setValidationErrors({});

    try {
      // 빈 값이거나 마스킹된 값은 제외하고 저장
      const settingsToSave: Record<string, string> = {};
      Object.entries(settings).forEach(([key, value]) => {
        if (value && !value.includes('...')) {
          settingsToSave[key] = value;
        }
      });

      await settingsService.updateSettings(settingsToSave);
      setSaveStatus('saved');
      toast.success('학습 설정이 성공적으로 저장되었습니다', 3000);

      // Reload settings to confirm save and show confirmation
      setTimeout(async () => {
        await loadSettings();
        toast.info('최신 설정이 반영되었습니다', 2000);
        setSaveStatus('idle');
      }, 1500);
    } catch (err) {
      console.error('Failed to save learning settings:', err);
      const errorMsg = '설정 저장에 실패했습니다';
      setError(errorMsg);
      toast.error(errorMsg);
      setSaveStatus('error');
    }
  };

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS);
    setSaveStatus('idle');
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-center gap-2 py-8">
          <RefreshCw className="w-5 h-5 animate-spin text-blue-500" />
          <span className="text-sm text-slate-600 dark:text-slate-400">
            학습 설정을 불러오는 중...
          </span>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-gray-100 dark:bg-gray-700 rounded-xl h-64 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className="text-red-700 dark:text-red-300">{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sample Curation Card */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-5 h-5 text-blue-500" />
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
                샘플 큐레이션
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                학습 샘플 품질 및 자동 추출 설정
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Min Quality Score */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                최소 품질 점수: {parseFloat(settings.learning_min_quality_score || '0.6').toFixed(2)}
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={settings.learning_min_quality_score}
                onChange={(e) => handleChange('learning_min_quality_score', e.target.value)}
                disabled={!isAdmin}
                className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer disabled:cursor-not-allowed"
              />
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                이 점수 이상의 샘플만 학습에 사용됩니다
              </p>
            </div>

            {/* Auto Extract Enabled */}
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  자동 추출 활성화
                </label>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  피드백에서 자동으로 샘플 추출
                </p>
              </div>
              <button
                onClick={() => handleToggle('learning_auto_extract_enabled')}
                disabled={!isAdmin}
                className={`relative w-11 h-6 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                  settings.learning_auto_extract_enabled === 'true' ? 'bg-blue-600' : 'bg-slate-300 dark:bg-slate-600'
                }`}
              >
                <div
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    settings.learning_auto_extract_enabled === 'true' ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Auto Extract Interval */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                추출 주기 (시간)
              </label>
              <input
                type="number"
                min="1"
                max="24"
                value={settings.learning_auto_extract_interval_hours}
                onChange={(e) => handleChange('learning_auto_extract_interval_hours', e.target.value)}
                disabled={!isAdmin || settings.learning_auto_extract_enabled !== 'true'}
                className={`w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                  validationErrors.learning_auto_extract_interval_hours
                    ? 'border-red-500 focus:ring-red-500'
                    : 'border-slate-300 dark:border-slate-600 focus:ring-blue-500'
                }`}
              />
              {validationErrors.learning_auto_extract_interval_hours ? (
                <p className="text-xs text-red-500 mt-1">
                  {validationErrors.learning_auto_extract_interval_hours}
                </p>
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  1-24시간 (기본값: 6시간)
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Rule Extraction Card */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Sliders className="w-5 h-5 text-purple-500" />
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
                규칙 추출
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Decision Tree 학습 민감도 설정
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Max Tree Depth */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                최대 트리 깊이
              </label>
              <input
                type="number"
                min="3"
                max="10"
                value={settings.learning_max_tree_depth}
                onChange={(e) => handleChange('learning_max_tree_depth', e.target.value)}
                disabled={!isAdmin}
                className={`w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                  validationErrors.learning_max_tree_depth
                    ? 'border-red-500 focus:ring-red-500'
                    : 'border-slate-300 dark:border-slate-600 focus:ring-blue-500'
                }`}
              />
              {validationErrors.learning_max_tree_depth ? (
                <p className="text-xs text-red-500 mt-1">
                  {validationErrors.learning_max_tree_depth}
                </p>
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  3-10 (기본값: 5) - 높을수록 복잡한 규칙 생성
                </p>
              )}
            </div>

            {/* Min Samples Split */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                최소 분할 샘플
              </label>
              <input
                type="number"
                min="10"
                max="100"
                step="10"
                value={settings.learning_min_samples_split}
                onChange={(e) => handleChange('learning_min_samples_split', e.target.value)}
                disabled={!isAdmin}
                className={`w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                  validationErrors.learning_min_samples_split
                    ? 'border-red-500 focus:ring-red-500'
                    : 'border-slate-300 dark:border-slate-600 focus:ring-blue-500'
                }`}
              />
              {validationErrors.learning_min_samples_split ? (
                <p className="text-xs text-red-500 mt-1">
                  {validationErrors.learning_min_samples_split}
                </p>
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  10-100 (기본값: 20) - 노드 분할에 필요한 최소 샘플 수
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Golden Set Card */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="flex items-center gap-2 mb-4">
            <RefreshCw className="w-5 h-5 text-green-500" />
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
                골든 샘플셋
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                고품질 샘플 자동 업데이트 설정
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Golden Set Auto Update */}
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  자동 업데이트 활성화
                </label>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  고품질 샘플 자동 추가
                </p>
              </div>
              <button
                onClick={() => handleToggle('learning_golden_set_auto_update')}
                disabled={!isAdmin}
                className={`relative w-11 h-6 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                  settings.learning_golden_set_auto_update === 'true' ? 'bg-green-600' : 'bg-slate-300 dark:bg-slate-600'
                }`}
              >
                <div
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    settings.learning_golden_set_auto_update === 'true' ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Golden Set Threshold */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                업데이트 임계값 (샘플 수)
              </label>
              <input
                type="number"
                min="10"
                max="100"
                step="10"
                value={settings.learning_golden_set_threshold}
                onChange={(e) => handleChange('learning_golden_set_threshold', e.target.value)}
                disabled={!isAdmin || settings.learning_golden_set_auto_update !== 'true'}
                className={`w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                  validationErrors.learning_golden_set_threshold
                    ? 'border-red-500 focus:ring-red-500'
                    : 'border-slate-300 dark:border-slate-600 focus:ring-blue-500'
                }`}
              />
              {validationErrors.learning_golden_set_threshold ? (
                <p className="text-xs text-red-500 mt-1">
                  {validationErrors.learning_golden_set_threshold}
                </p>
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  10-100 (기본값: 50) - 승인된 샘플이 이 수에 도달하면 자동 업데이트
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Save Button Area */}
      <div className="flex items-center justify-between p-4 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700">
        <div className="text-sm">
          {saveStatus === 'saved' && (
            <span className="text-green-600 dark:text-green-400 flex items-center gap-1">
              <CheckCircle className="w-4 h-4" />
              학습 설정이 저장되었습니다
            </span>
          )}
          {saveStatus === 'error' && (
            <span className="text-red-600 dark:text-red-400 flex items-center gap-1">
              <AlertCircle className="w-4 h-4" />
              {error || '저장 중 오류가 발생했습니다'}
            </span>
          )}
          {!isAdmin && (
            <span className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
              <AlertCircle className="w-4 h-4" />
              관리자만 설정을 변경할 수 있습니다
            </span>
          )}
        </div>

        <div className="flex gap-3">
          <button
            onClick={handleReset}
            disabled={!isAdmin || saveStatus === 'saving'}
            className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            기본값으로 재설정
          </button>
          <button
            onClick={handleSave}
            disabled={!isAdmin || saveStatus === 'saving'}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {saveStatus === 'saving' ? '저장 중...' : '설정 저장'}
          </button>
        </div>
      </div>
    </div>
  );
}
