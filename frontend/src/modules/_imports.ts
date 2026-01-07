// AUTO-GENERATED - DO NOT EDIT
// Generated at: 2026-01-05T00:00:00Z
// Run: python scripts/build_frontend_imports.py

import { lazy } from 'react';

/**
 * 동적으로 로드되는 모듈 페이지 컴포넌트 맵
 * 빌드 시 자동 생성됩니다.
 *
 * 현재는 기존 pages 폴더의 컴포넌트를 사용합니다.
 * 새 모듈이 추가되면 이 파일이 자동으로 업데이트됩니다.
 */
export const PAGE_COMPONENTS: Record<string, React.LazyExoticComponent<React.ComponentType<any>>> = {
  // 기존 페이지들 (modules/ 폴더로 이관 전까지 사용)
  DashboardPage: lazy(() => import('@/components/pages/DashboardPage')),
  WorkflowsPage: lazy(() => import('@/components/pages/WorkflowsPage')),
  RulesetsPage: lazy(() => import('@/components/pages/RulesetsPage')),
  ExperimentsPage: lazy(() => import('@/components/pages/ExperimentsPage')),
  LearningPage: lazy(() => import('@/components/pages/LearningPage')),
  DataPage: lazy(() => import('@/components/pages/DataPage')),
  SettingsPage: lazy(() => import('@/components/pages/SettingsPage')),
};

/**
 * 모듈 코드로 페이지 컴포넌트를 가져옵니다.
 */
export function getPageComponent(moduleCode: string): React.LazyExoticComponent<React.ComponentType<any>> | null {
  // 모듈 코드 → 컴포넌트 이름 매핑
  const componentMap: Record<string, string> = {
    chat: 'ChatPage',
    dashboard: 'DashboardPage',
    workflows: 'WorkflowsPage',
    rulesets: 'RulesetsPage',
    experiments: 'ExperimentsPage',
    learning: 'LearningPage',
    data: 'DataPage',
    settings: 'SettingsPage',
  };

  const componentName = componentMap[moduleCode];
  if (!componentName) return null;

  return PAGE_COMPONENTS[componentName] || null;
}

/**
 * 등록된 모든 모듈 코드 목록
 */
export const REGISTERED_MODULES = [
  'chat',
  'dashboard',
  'workflows',
  'rulesets',
  'experiments',
  'learning',
  'data',
  'settings',
];
