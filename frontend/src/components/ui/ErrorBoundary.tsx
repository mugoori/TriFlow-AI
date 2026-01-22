/**
 * Error Boundary Component
 * React 컴포넌트 에러를 포착하고 Fallback UI를 표시합니다
 */

import { Component, ReactNode, ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    // 커스텀 에러 핸들러 호출
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      // 커스텀 fallback이 제공된 경우
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // 기본 Fallback UI
      return (
        <div className="min-h-[400px] flex items-center justify-center p-6">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-6 max-w-md w-full">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                <AlertTriangle className="w-8 h-8 text-red-500" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-red-700 dark:text-red-300 mb-2">
                  문제가 발생했습니다
                </h3>
                <p className="text-sm text-red-600 dark:text-red-400 mb-4">
                  이 컴포넌트를 로드하는 중 오류가 발생했습니다.
                </p>

                {/* 개발 모드에서만 에러 상세 표시 */}
                {process.env.NODE_ENV === 'development' && this.state.error && (
                  <details className="mb-4">
                    <summary className="text-xs text-red-500 cursor-pointer hover:underline mb-2">
                      에러 상세 정보 (개발 모드)
                    </summary>
                    <pre className="text-xs bg-red-100 dark:bg-red-950 p-2 rounded overflow-auto max-h-40 text-red-900 dark:text-red-200">
                      {this.state.error.toString()}
                      {this.state.error.stack}
                    </pre>
                  </details>
                )}

                <div className="flex gap-3">
                  <button
                    onClick={this.handleReset}
                    className="px-4 py-2 text-sm font-medium text-red-700 dark:text-red-300 bg-white dark:bg-red-950 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/50 transition-colors"
                  >
                    다시 시도
                  </button>
                  <button
                    onClick={this.handleReload}
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors flex items-center gap-2"
                  >
                    <RefreshCw className="w-4 h-4" />
                    페이지 새로고침
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Functional wrapper for easier usage
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  fallback?: ReactNode
) {
  return function WithErrorBoundaryComponent(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <Component {...props} />
      </ErrorBoundary>
    );
  };
}
