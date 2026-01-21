/**
 * System Diagnostics Section
 * 시스템 상태 모니터링 (Redis, Database, Cache, API)
 */

import { useState, useEffect, useCallback } from 'react';
import { Activity, Database, Zap, Clock, RefreshCw, CheckCircle, XCircle } from 'lucide-react';
import { apiClient } from '@/services/api';

interface HealthCheck {
  status: 'healthy' | 'unhealthy';
  checks: {
    database: 'ok' | 'error';
    redis: 'ok' | 'error';
  };
}

export function SystemDiagnosticsSection() {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiClient.get<HealthCheck>('/health');
      setHealth(data);
      setLastCheck(new Date());
    } catch (err) {
      console.error('Health check failed:', err);
      setHealth({
        status: 'unhealthy',
        checks: {
          database: 'error',
          redis: 'error',
        },
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    // Auto-refresh every 10 seconds
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  const StatusBadge = ({ status }: { status: 'ok' | 'error' }) => {
    if (status === 'ok') {
      return (
        <div className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
          <CheckCircle className="w-4 h-4" />
          <span className="text-sm font-medium">Connected</span>
        </div>
      );
    }
    return (
      <div className="flex items-center gap-1.5 text-red-600 dark:text-red-400">
        <XCircle className="w-4 h-4" />
        <span className="text-sm font-medium">Error</span>
      </div>
    );
  };

  const ServiceCard = ({
    title,
    icon: Icon,
    status,
    info,
  }: {
    title: string;
    icon: React.ElementType;
    status: 'ok' | 'error';
    info?: string;
  }) => (
    <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          <h4 className="font-medium text-gray-900 dark:text-white">{title}</h4>
        </div>
        <StatusBadge status={status} />
      </div>
      {info && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{info}</p>
      )}
    </div>
  );

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-500" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            System Diagnostics
          </h3>
        </div>
        <div className="flex items-center gap-3">
          {lastCheck && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Last check: {lastCheck.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={checkHealth}
            disabled={loading}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
            title="새로고침"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Overall Status */}
        <div className="mb-4 p-4 rounded-lg border-2 ${
          health?.status === 'healthy'
            ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
            : 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
        }">
          <div className="flex items-center gap-3">
            {health?.status === 'healthy' ? (
              <CheckCircle className="w-6 h-6 text-green-600 dark:text-green-400" />
            ) : (
              <XCircle className="w-6 h-6 text-red-600 dark:text-red-400" />
            )}
            <div>
              <p className={`font-semibold ${
                health?.status === 'healthy'
                  ? 'text-green-700 dark:text-green-300'
                  : 'text-red-700 dark:text-red-300'
              }`}>
                System Status: {health?.status === 'healthy' ? 'Healthy' : 'Issues Detected'}
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                All critical services are {health?.status === 'healthy' ? 'operational' : 'experiencing problems'}
              </p>
            </div>
          </div>
        </div>

        {/* Service Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ServiceCard
            title="PostgreSQL Database"
            icon={Database}
            status={health?.checks.database || 'error'}
            info="Primary data storage"
          />
          <ServiceCard
            title="Redis Cache"
            icon={Zap}
            status={health?.checks.redis || 'error'}
            info="Caching and session storage"
          />
        </div>

        {/* Additional Info */}
        <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <div className="flex items-start gap-2">
            <Clock className="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-blue-700 dark:text-blue-300">Auto-refresh enabled</p>
              <p className="text-blue-600 dark:text-blue-400 text-xs mt-1">
                System health checks run automatically every 10 seconds
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SystemDiagnosticsSection;
