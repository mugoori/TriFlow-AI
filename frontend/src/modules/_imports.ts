// AUTO-GENERATED - DO NOT EDIT
// Generated at: 2026-01-19T07:53:30.424564Z
// Run: python scripts/build_frontend_imports.py

import { lazy } from 'react';

/**
 * 동적으로 로드되는 모듈 페이지 컴포넌트 맵
 * 빌드 시 자동 생성됩니다.
 */
export const PAGE_COMPONENTS: Record<string, React.LazyExoticComponent<React.ComponentType<any>>> = {
  KoreaBiopharmPage: lazy(() => import('@/modules/korea_biopharm/frontend/KoreaBiopharmPage')),
  QualityAnalyticsPage: lazy(() => import('@/modules/quality_analytics/frontend/QualityAnalyticsPage')),
};

/**
 * 모듈 코드로 페이지 컴포넌트를 가져옵니다.
 */
export function getPageComponent(moduleCode: string): React.LazyExoticComponent<React.ComponentType<any>> | null {
  // 모듈 코드를 PascalCase로 변환 (예: korea_biopharm -> Koreabiopharm)
  const pascalCase = moduleCode
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join('');
  const componentName = `${pascalCase}Page`;

  return PAGE_COMPONENTS[componentName] || null;
}

/**
 * 등록된 모든 모듈 코드 목록
 */
export const REGISTERED_MODULES = [
  "korea_biopharm",
  "quality_analytics"
];
