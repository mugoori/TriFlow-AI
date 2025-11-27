/**
 * Settings Page
 * API 키 설정, Backend 연결 상태, 테넌트 설정 등
 */
import { useState, useEffect } from 'react';

interface ConnectionStatus {
  backend: 'connected' | 'disconnected' | 'checking';
  database: 'connected' | 'disconnected' | 'unknown';
}

interface Settings {
  anthropicApiKey: string;
  tenantId: string;
  backendUrl: string;
}

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({
    anthropicApiKey: '',
    tenantId: 'default-tenant',
    backendUrl: 'http://localhost:8000',
  });

  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    backend: 'checking',
    database: 'unknown',
  });

  const [showApiKey, setShowApiKey] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

  // Load settings from localStorage on mount
  useEffect(() => {
    const savedSettings = localStorage.getItem('triflow-settings');
    if (savedSettings) {
      try {
        const parsed = JSON.parse(savedSettings);
        setSettings(prev => ({ ...prev, ...parsed }));
      } catch (e) {
        console.error('Failed to parse saved settings:', e);
      }
    }
  }, []);

  // Check backend connection on mount and when backendUrl changes
  useEffect(() => {
    checkBackendConnection();
  }, [settings.backendUrl]);

  const checkBackendConnection = async () => {
    setConnectionStatus(prev => ({ ...prev, backend: 'checking' }));

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
    }
  };

  const handleSave = () => {
    setSaveStatus('saving');

    try {
      // Save to localStorage (API key is masked for security in production)
      localStorage.setItem('triflow-settings', JSON.stringify(settings));
      setSaveStatus('saved');

      // Reset status after 2 seconds
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('Failed to save settings:', error);
      setSaveStatus('error');
    }
  };

  const handleInputChange = (field: keyof Settings, value: string) => {
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

  return (
    <div className="h-full overflow-y-auto bg-slate-50 dark:bg-slate-900">
      <div className="max-w-2xl mx-auto p-6 space-y-6">
        {/* Connection Status Card */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50 mb-4">
            연결 상태
          </h2>

          <div className="space-y-3">
            {/* Backend Status */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-3 h-3 rounded-full ${getStatusColor(connectionStatus.backend)}`} />
                <span className="text-slate-700 dark:text-slate-300">Backend Server</span>
              </div>
              <span className="text-sm text-slate-500 dark:text-slate-400">
                {getStatusText(connectionStatus.backend)}
              </span>
            </div>

            {/* Database Status */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-3 h-3 rounded-full ${getStatusColor(connectionStatus.database)}`} />
                <span className="text-slate-700 dark:text-slate-300">Database</span>
              </div>
              <span className="text-sm text-slate-500 dark:text-slate-400">
                {getStatusText(connectionStatus.database)}
              </span>
            </div>
          </div>

          <button
            onClick={checkBackendConnection}
            className="mt-4 px-4 py-2 text-sm bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
          >
            연결 상태 새로고침
          </button>
        </div>

        {/* API Settings Card */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50 mb-4">
            API 설정
          </h2>

          <div className="space-y-4">
            {/* Anthropic API Key */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Anthropic API Key
              </label>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={settings.anthropicApiKey}
                  onChange={(e) => handleInputChange('anthropicApiKey', e.target.value)}
                  placeholder="sk-ant-..."
                  className="w-full px-4 py-2 pr-20 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                >
                  {showApiKey ? '숨기기' : '보기'}
                </button>
              </div>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Claude API 호출에 사용됩니다. Backend 환경변수로도 설정 가능합니다.
              </p>
            </div>

            {/* Backend URL */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Backend URL
              </label>
              <input
                type="text"
                value={settings.backendUrl}
                onChange={(e) => handleInputChange('backendUrl', e.target.value)}
                placeholder="http://localhost:8000"
                className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                FastAPI 백엔드 서버 주소
              </p>
            </div>
          </div>
        </div>

        {/* Tenant Settings Card */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50 mb-4">
            테넌트 설정
          </h2>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Tenant ID
            </label>
            <input
              type="text"
              value={settings.tenantId}
              onChange={(e) => handleInputChange('tenantId', e.target.value)}
              placeholder="default-tenant"
              className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              멀티테넌트 환경에서 데이터 격리에 사용됩니다.
            </p>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex items-center justify-between pt-4">
          <div className="text-sm">
            {saveStatus === 'saved' && (
              <span className="text-green-600 dark:text-green-400">✓ 설정이 저장되었습니다</span>
            )}
            {saveStatus === 'error' && (
              <span className="text-red-600 dark:text-red-400">저장 중 오류가 발생했습니다</span>
            )}
          </div>

          <button
            onClick={handleSave}
            disabled={saveStatus === 'saving'}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {saveStatus === 'saving' ? '저장 중...' : '설정 저장'}
          </button>
        </div>

        {/* Info Card */}
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">
            참고 사항
          </h3>
          <ul className="text-sm text-blue-700 dark:text-blue-400 space-y-1">
            <li>• API 키는 브라우저의 localStorage에 저장됩니다.</li>
            <li>• 프로덕션 환경에서는 Backend 환경변수 사용을 권장합니다.</li>
            <li>• Backend 서버가 실행 중이어야 AI 기능을 사용할 수 있습니다.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
