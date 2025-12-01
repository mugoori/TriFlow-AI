/**
 * Protected Route 컴포넌트
 * 인증되지 않은 사용자는 로그인 페이지로 리다이렉트
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

interface LoaderProps {
  message?: string;
}

function Loader({ message = '시스템 시작 중...' }: LoaderProps) {
  return (
    <div className="flex flex-col items-center justify-center h-screen bg-slate-50 dark:bg-slate-950">

      {/* 로고 영역 */}
      <div className="relative flex items-center justify-center mb-8">
        {/* 1. 뒤에서 퍼지는 파동 효과 (Pulsing) */}
        <div className="absolute w-32 h-32 bg-blue-500/20 rounded-full animate-ping" />
        <div className="absolute w-28 h-28 bg-purple-500/10 rounded-full animate-ping [animation-delay:0.5s]" />

        {/* 2. 회전하는 테두리 링 (Spinning Ring) */}
        <div className="absolute w-28 h-28 rounded-full border-4 border-t-blue-500 border-r-transparent border-b-purple-500 border-l-transparent animate-spin" />

        {/* 3. 중앙 로고 이미지 (TriFlow Icon) */}
        <div className="relative z-10 w-20 h-20 bg-white dark:bg-slate-900 rounded-2xl shadow-xl flex items-center justify-center overflow-hidden">
          <img src="/logo.png" alt="TriFlow AI Logo" className="w-16 h-16 object-contain" />
        </div>
      </div>

      {/* 텍스트 영역 */}
      <div className="flex flex-col items-center space-y-3">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100 tracking-tight">
          TriFlow AI
        </h1>
        <div className="flex items-center space-x-2 text-slate-500 dark:text-slate-400">
          <span className="text-sm font-medium">{message}</span>
          <span className="flex space-x-1">
            <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
            <span className="w-1.5 h-1.5 bg-purple-500 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
            <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce"></span>
          </span>
        </div>
      </div>

    </div>
  );
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  // 초기 로딩 중 (자동 로그인 시도 중)
  if (isLoading) {
    return <Loader message="로딩 중..." />;
  }

  // 인증되지 않음 - 로그인 페이지로 리다이렉트
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 인증됨 - children 렌더링
  return <>{children}</>;
}

// Loader 컴포넌트 export (다른 곳에서도 사용 가능)
export { Loader };
