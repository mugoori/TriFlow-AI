/**
 * Settings Page
 * 일반 설정, Backend 연결, AI 모델, 알림 설정, 앱 정보
 */
import { useState, useEffect, useRef } from 'react';
import { settingsService, NotificationTestResult } from '../../services/settingsService';

type Theme = 'system' | 'light' | 'dark';
type Language = 'ko' | 'en';

interface ConnectionStatus {
  backend: 'connected' | 'disconnected' | 'checking';
  database: 'connected' | 'disconnected' | 'unknown';
}

interface Settings {
  // 일반 설정
  theme: Theme;
  language: Language;
  notifications: boolean;
  // Backend 연결
  backendUrl: string;
  autoReconnect: boolean;
  // AI 모델
  aiModel: string;
  maxTokens: number;
  // 테넌트
  tenantId: string;
}

interface NotificationSettings {
  // Slack
  slack_webhook_url: string;
  slack_default_channel: string;
  // Email
  smtp_host: string;
  smtp_port: string;
  smtp_user: string;
  smtp_password: string;
  smtp_from: string;
  smtp_use_tls: string;
}

const AI_MODELS = [
  { id: 'claude-sonnet-4-5-20250929', name: 'Claude Sonnet 4.5 (Latest)' },
  { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet' },
  { id: 'claude-3-haiku-20240307', name: 'Claude 3 Haiku (Fast)' },
];

const APP_INFO = {
  version: '0.1.0',
  build: '2025.11.27',
  license: 'MIT License',
  github: 'https://github.com/mugoori/TriFlow-AI',
};

// localStorage에서 초기 설정 로드 (컴포넌트 외부에서 동기적으로 실행)
function getInitialSettings(): Settings {
  const defaultSettings: Settings = {
    theme: 'system',
    language: 'ko',
    notifications: true,
    backendUrl: 'http://localhost:8000',
    autoReconnect: true,
    aiModel: 'claude-sonnet-4-5-20250929',
    maxTokens: 4096,
    tenantId: 'default-tenant',
  };

  try {
    const saved = localStorage.getItem('triflow-settings');
    if (saved) {
      return { ...defaultSettings, ...JSON.parse(saved) };
    }
  } catch (e) {
    console.error('Failed to parse saved settings:', e);
  }
  return defaultSettings;
}

export function SettingsPage() {
  // 초기 상태를 localStorage에서 동기적으로 로드 (깜빡임 방지)
  const [settings, setSettings] = useState<Settings>(getInitialSettings);

  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    backend: 'checking',
    database: 'unknown',
  });

  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [testingConnection, setTestingConnection] = useState(false);

  // 알림 설정 상태
  const [notificationSettings, setNotificationSettings] = useState<NotificationSettings>({
    slack_webhook_url: '',
    slack_default_channel: '#alerts',
    smtp_host: '',
    smtp_port: '587',
    smtp_user: '',
    smtp_password: '',
    smtp_from: '',
    smtp_use_tls: 'true',
  });
  const [notificationSaveStatus, setNotificationSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [testResult, setTestResult] = useState<{ type: 'slack' | 'email'; result: NotificationTestResult } | null>(null);
  const [testingNotification, setTestingNotification] = useState<'slack' | 'email' | null>(null);
  const [testEmailTo, setTestEmailTo] = useState('');

  // Gmail 프리셋 적용
  const applyGmailPreset = () => {
    setNotificationSettings(prev => ({
      ...prev,
      smtp_host: 'smtp.gmail.com',
      smtp_port: '587',
      smtp_use_tls: 'true',
    }));
    setNotificationSaveStatus('idle');
  };

  // 설정 상태 계산 (마스킹된 값도 설정된 것으로 간주)
  const slackConfigured = !!notificationSettings.slack_webhook_url;

  const emailRequiredFields: (keyof NotificationSettings)[] = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from'];
  const emailFilledCount = emailRequiredFields.filter(k =>
    notificationSettings[k]
  ).length;
  const emailConfigured = emailFilledCount === 5;

  // 초기 마운트 여부 추적 (깜빡임 방지)
  // 참고: 설정은 getInitialSettings()에서 동기적으로 이미 로드됨
  const isInitialMount = useRef(true);

  // Apply theme (사용자가 테마를 변경할 때만 적용, 초기 마운트 시 건너뜀)
  // index.html의 인라인 스크립트가 이미 올바른 테마를 적용했으므로
  // 초기 마운트 시 재적용하면 깜빡임이 발생함
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return; // 초기 마운트 시 건너뛰기
    }

    const root = document.documentElement;
    if (settings.theme === 'dark') {
      root.classList.add('dark');
    } else if (settings.theme === 'light') {
      root.classList.remove('dark');
    } else {
      // System preference
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
    }
  }, [settings.theme]);

  // Check backend connection on mount
  useEffect(() => {
    checkBackendConnection();
  }, []);

  // Load notification settings from backend
  useEffect(() => {
    const loadNotificationSettings = async () => {
      try {
        const response = await settingsService.getSettings('notification');
        const settingsMap: Record<string, string> = {};
        response.settings.forEach((s) => {
          settingsMap[s.key] = s.value || '';
        });
        setNotificationSettings((prev) => ({
          ...prev,
          ...settingsMap,
        }));
      } catch (error) {
        console.error('Failed to load notification settings:', error);
      }
    };
    loadNotificationSettings();
  }, []);

  const checkBackendConnection = async () => {
    setConnectionStatus(prev => ({ ...prev, backend: 'checking' }));
    setTestingConnection(true);

    try {
      const response = await fetch(`${settings.backendUrl}/health`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      });

      if (response.ok) {
        const data = await response.json();
        setConnectionStatus({
          backend: 'connected',
          database: data.database === 'connected' ? 'connected' : 'disconnected',
        });
      } else {
        setConnectionStatus({ backend: 'disconnected', database: 'unknown' });
      }
    } catch (error) {
      console.error('Backend connection check failed:', error);
      setConnectionStatus({ backend: 'disconnected', database: 'unknown' });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSave = () => {
    setSaveStatus('saving');

    try {
      localStorage.setItem('triflow-settings', JSON.stringify(settings));
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('Failed to save settings:', error);
      setSaveStatus('error');
    }
  };

  const handleChange = <K extends keyof Settings>(field: K, value: Settings[K]) => {
    setSettings(prev => ({ ...prev, [field]: value }));
    setSaveStatus('idle');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'bg-green-500';
      case 'disconnected': return 'bg-red-500';
      case 'checking': return 'bg-yellow-500 animate-pulse';
      default: return 'bg-slate-400';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'connected': return '연결됨';
      case 'disconnected': return '연결 안됨';
      case 'checking': return '확인 중...';
      default: return '알 수 없음';
    }
  };

  // 알림 설정 변경 핸들러
  const handleNotificationChange = (key: keyof NotificationSettings, value: string) => {
    setNotificationSettings((prev) => ({ ...prev, [key]: value }));
    setNotificationSaveStatus('idle');
  };

  // 알림 설정 저장
  const handleSaveNotificationSettings = async () => {
    setNotificationSaveStatus('saving');
    try {
      // 빈 값과 마스킹된 값(...)은 제외하고 저장
      const settingsToSave: Record<string, string> = {};
      Object.entries(notificationSettings).forEach(([key, value]) => {
        // 빈 값이거나 마스킹된 값(예: "http.../xyz", "nzvp...oahy")은 저장하지 않음
        if (value && !value.includes('...')) {
          settingsToSave[key] = value;
        }
      });

      await settingsService.updateSettings(settingsToSave);
      setNotificationSaveStatus('saved');
      setTimeout(() => setNotificationSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('Failed to save notification settings:', error);
      setNotificationSaveStatus('error');
    }
  };

  // Slack 테스트
  const handleTestSlack = async () => {
    setTestingNotification('slack');
    setTestResult(null);
    try {
      const result = await settingsService.testSlack();
      setTestResult({ type: 'slack', result });
    } catch (error) {
      setTestResult({
        type: 'slack',
        result: { status: 'failed', message: String(error) },
      });
    } finally {
      setTestingNotification(null);
    }
  };

  // Email 테스트
  const handleTestEmail = async () => {
    if (!testEmailTo) {
      setTestResult({
        type: 'email',
        result: { status: 'failed', message: '테스트 수신 이메일을 입력하세요' },
      });
      return;
    }
    setTestingNotification('email');
    setTestResult(null);
    try {
      const result = await settingsService.testEmail(testEmailTo);
      setTestResult({ type: 'email', result });
    } catch (error) {
      setTestResult({
        type: 'email',
        result: { status: 'failed', message: String(error) },
      });
    } finally {
      setTestingNotification(null);
    }
  };

  return (
    <div className="h-full overflow-y-auto bg-slate-50 dark:bg-slate-900">
      <div className="max-w-4xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 일반 설정 카드 */}
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-lg">⚙️</span>
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">일반 설정</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">기본 애플리케이션 설정</p>
              </div>
            </div>

            <div className="space-y-4">
              {/* 테마 */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  테마
                </label>
                <div className="flex gap-2">
                  {(['system', 'light', 'dark'] as Theme[]).map((theme) => (
                    <button
                      key={theme}
                      onClick={() => handleChange('theme', theme)}
                      className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        settings.theme === theme
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
                      }`}
                    >
                      {theme === 'system' ? '시스템' : theme === 'light' ? '라이트' : '다크'}
                    </button>
                  ))}
                </div>
              </div>

              {/* 언어 */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  언어
                </label>
                <select
                  value={settings.language}
                  onChange={(e) => handleChange('language', e.target.value as Language)}
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="ko">한국어</option>
                  <option value="en">English</option>
                </select>
              </div>

              {/* 알림 */}
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  알림
                </label>
                <button
                  onClick={() => handleChange('notifications', !settings.notifications)}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    settings.notifications ? 'bg-blue-600' : 'bg-slate-300 dark:bg-slate-600'
                  }`}
                >
                  <div
                    className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                      settings.notifications ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>

          {/* Backend 연결 카드 */}
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-lg">🔌</span>
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">Backend 연결</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">서버 연결 설정</p>
              </div>
            </div>

            <div className="space-y-4">
              {/* 연결 상태 표시 */}
              <div className={`p-4 rounded-lg ${
                connectionStatus.backend === 'connected'
                  ? 'bg-green-50 dark:bg-green-900/20'
                  : 'bg-red-50 dark:bg-red-900/20'
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${getStatusColor(connectionStatus.backend)}`} />
                    <div>
                      <p className={`font-medium ${
                        connectionStatus.backend === 'connected'
                          ? 'text-green-800 dark:text-green-300'
                          : 'text-red-800 dark:text-red-300'
                      }`}>
                        {getStatusText(connectionStatus.backend)}
                      </p>
                      <p className={`text-sm ${
                        connectionStatus.backend === 'connected'
                          ? 'text-green-700 dark:text-green-400'
                          : 'text-red-700 dark:text-red-400'
                      }`}>
                        {settings.backendUrl}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={checkBackendConnection}
                    disabled={testingConnection}
                    className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                      connectionStatus.backend === 'connected'
                        ? 'bg-green-700 text-white hover:bg-green-800'
                        : 'bg-red-700 text-white hover:bg-red-800'
                    } disabled:opacity-50`}
                  >
                    {testingConnection ? '테스트 중...' : '테스트'}
                  </button>
                </div>
              </div>

              {/* API URL */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  API URL
                </label>
                <input
                  type="text"
                  value={settings.backendUrl}
                  onChange={(e) => handleChange('backendUrl', e.target.value)}
                  placeholder="http://localhost:8000"
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* 자동 재연결 */}
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  자동 재연결
                </label>
                <button
                  onClick={() => handleChange('autoReconnect', !settings.autoReconnect)}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    settings.autoReconnect ? 'bg-blue-600' : 'bg-slate-300 dark:bg-slate-600'
                  }`}
                >
                  <div
                    className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                      settings.autoReconnect ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>

          {/* AI 모델 카드 */}
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-lg">🤖</span>
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">AI 모델</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">LLM 설정</p>
              </div>
            </div>

            <div className="space-y-4">
              {/* 모델 선택 */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  모델
                </label>
                <select
                  value={settings.aiModel}
                  onChange={(e) => handleChange('aiModel', e.target.value)}
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {AI_MODELS.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Max Tokens */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Max Tokens
                </label>
                <input
                  type="number"
                  value={settings.maxTokens}
                  onChange={(e) => handleChange('maxTokens', parseInt(e.target.value) || 4096)}
                  min={256}
                  max={16384}
                  step={256}
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  256 ~ 16,384 범위
                </p>
              </div>

              {/* Tenant ID */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Tenant ID
                </label>
                <input
                  type="text"
                  value={settings.tenantId}
                  onChange={(e) => handleChange('tenantId', e.target.value)}
                  placeholder="default-tenant"
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          {/* 앱 정보 카드 */}
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-lg">ℹ️</span>
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">앱 정보</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">버전 및 라이선스</p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-slate-600 dark:text-slate-400">버전</span>
                <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{APP_INFO.version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-slate-600 dark:text-slate-400">빌드</span>
                <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{APP_INFO.build}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-slate-600 dark:text-slate-400">라이선스</span>
                <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{APP_INFO.license}</span>
              </div>

              {/* GitHub 링크 */}
              <a
                href={APP_INFO.github}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 flex items-center gap-2 p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-blue-600 dark:text-blue-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <span>🔗</span>
                <span className="text-sm">GitHub: github.com/mugoori/TriFlow-AI</span>
              </a>
            </div>
          </div>
        </div>

        {/* 알림 설정 섹션 헤더 */}
        <div className="mt-8 mb-4">
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">알림 설정</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">Slack, Email 알림 연동 설정 (관리자 전용)</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Slack 알림 카드 */}
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-lg">#</span>
                <div>
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">Slack 알림</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">Incoming Webhook 연동</p>
                </div>
              </div>
              {/* 설정 상태 배지 */}
              <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                slackConfigured
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                  : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
              }`}>
                {slackConfigured ? '✓ 설정됨' : '○ 미설정'}
              </span>
            </div>

            <div className="space-y-4">
              {/* Webhook URL */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Webhook URL <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  value={notificationSettings.slack_webhook_url}
                  onChange={(e) => handleNotificationChange('slack_webhook_url', e.target.value)}
                  placeholder="https://hooks.slack.com/services/..."
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {notificationSettings.slack_webhook_url.includes('...') ? (
                  <p className="mt-1 text-xs text-blue-500 dark:text-blue-400">
                    저장된 값이 있습니다. 변경하려면 새 값을 입력하세요.
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Slack App에서 Incoming Webhook URL을 생성하세요
                  </p>
                )}
              </div>

              {/* Default Channel */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  기본 채널
                </label>
                <input
                  type="text"
                  value={notificationSettings.slack_default_channel}
                  onChange={(e) => handleNotificationChange('slack_default_channel', e.target.value)}
                  placeholder="#alerts"
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* 테스트 버튼 */}
              <button
                onClick={handleTestSlack}
                disabled={!notificationSettings.slack_webhook_url || testingNotification === 'slack'}
                className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {testingNotification === 'slack' ? '테스트 중...' : 'Slack 테스트 전송'}
              </button>

              {/* 테스트 결과 */}
              {testResult && testResult.type === 'slack' && (
                <div className={`p-3 rounded-lg text-sm ${
                  testResult.result.status === 'success'
                    ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'
                    : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
                }`}>
                  {testResult.result.message}
                </div>
              )}
            </div>
          </div>

          {/* Email 알림 카드 */}
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-lg">✉️</span>
                <div>
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">Email 알림</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">SMTP 서버 설정</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {/* Gmail 프리셋 버튼 */}
                <button
                  onClick={applyGmailPreset}
                  className="px-2 py-1 text-xs font-medium bg-red-50 text-red-600 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/30 rounded transition-colors"
                >
                  Gmail 자동 입력
                </button>
                {/* 설정 상태 배지 */}
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                  emailConfigured
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                }`}>
                  {emailConfigured ? '✓ 설정됨' : `○ ${emailFilledCount}/5`}
                </span>
              </div>
            </div>

            <div className="space-y-4">
              {/* SMTP Host */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    SMTP 호스트 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={notificationSettings.smtp_host}
                    onChange={(e) => handleNotificationChange('smtp_host', e.target.value)}
                    placeholder="smtp.gmail.com"
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    포트 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={notificationSettings.smtp_port}
                    onChange={(e) => handleNotificationChange('smtp_port', e.target.value)}
                    placeholder="587"
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* SMTP User / Password */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    사용자명 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={notificationSettings.smtp_user}
                    onChange={(e) => handleNotificationChange('smtp_user', e.target.value)}
                    placeholder="user@example.com"
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    비밀번호 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="password"
                    value={notificationSettings.smtp_password}
                    onChange={(e) => handleNotificationChange('smtp_password', e.target.value)}
                    placeholder="앱 비밀번호"
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  {notificationSettings.smtp_password.includes('...') && (
                    <p className="mt-1 text-xs text-blue-500 dark:text-blue-400">
                      저장된 값이 있습니다
                    </p>
                  )}
                </div>
              </div>

              {/* From Address */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  발신자 주소 <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={notificationSettings.smtp_from}
                  onChange={(e) => handleNotificationChange('smtp_from', e.target.value)}
                  placeholder="noreply@example.com"
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* TLS Toggle */}
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  TLS 사용
                </label>
                <button
                  onClick={() => handleNotificationChange('smtp_use_tls', notificationSettings.smtp_use_tls === 'true' ? 'false' : 'true')}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    notificationSettings.smtp_use_tls === 'true' ? 'bg-blue-600' : 'bg-slate-300 dark:bg-slate-600'
                  }`}
                >
                  <div
                    className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                      notificationSettings.smtp_use_tls === 'true' ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              {/* 테스트 이메일 입력 */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  테스트 수신 주소
                </label>
                <input
                  type="email"
                  value={testEmailTo}
                  onChange={(e) => setTestEmailTo(e.target.value)}
                  placeholder="test@example.com"
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* 테스트 버튼 */}
              <button
                onClick={handleTestEmail}
                disabled={!emailConfigured || testingNotification === 'email' || !testEmailTo}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {testingNotification === 'email' ? '테스트 중...' : 'Email 테스트 전송'}
              </button>

              {/* 미완성 안내 */}
              {!emailConfigured && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  모든 필수 필드(*)를 입력해야 테스트할 수 있습니다
                </p>
              )}

              {/* 테스트 결과 */}
              {testResult && testResult.type === 'email' && (
                <div className={`p-3 rounded-lg text-sm ${
                  testResult.result.status === 'success'
                    ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'
                    : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
                }`}>
                  {testResult.result.message}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 알림 설정 저장 버튼 */}
        <div className="mt-6 flex items-center justify-between p-4 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700">
          <div className="text-sm">
            {notificationSaveStatus === 'saved' && (
              <span className="text-green-600 dark:text-green-400 flex items-center gap-1">
                <span>✓</span> 알림 설정이 저장되었습니다
              </span>
            )}
            {notificationSaveStatus === 'error' && (
              <span className="text-red-600 dark:text-red-400">저장 중 오류가 발생했습니다 (관리자 권한 필요)</span>
            )}
          </div>

          <button
            onClick={handleSaveNotificationSettings}
            disabled={notificationSaveStatus === 'saving'}
            className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {notificationSaveStatus === 'saving' ? '저장 중...' : '알림 설정 저장'}
          </button>
        </div>

        {/* 저장 버튼 영역 */}
        <div className="mt-6 flex items-center justify-between p-4 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700">
          <div className="text-sm">
            {saveStatus === 'saved' && (
              <span className="text-green-600 dark:text-green-400 flex items-center gap-1">
                <span>✓</span> 설정이 저장되었습니다
              </span>
            )}
            {saveStatus === 'error' && (
              <span className="text-red-600 dark:text-red-400">저장 중 오류가 발생했습니다</span>
            )}
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => {
                localStorage.removeItem('triflow-settings');
                window.location.reload();
              }}
              className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
            >
              초기화
            </button>
            <button
              onClick={handleSave}
              disabled={saveStatus === 'saving'}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {saveStatus === 'saving' ? '저장 중...' : '설정 저장'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
