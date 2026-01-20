/**
 * ModulePageLayout Component
 *
 * Standard layout for module pages with icon, title, description, and actions.
 *
 * Example:
 *   <ModulePageLayout
 *     icon={Database}
 *     title="센서 데이터"
 *     description="센서 데이터 관리 및 조회"
 *     actions={<Button>업로드</Button>}
 *   >
 *     {content}
 *   </ModulePageLayout>
 */
import React from 'react';
import { LucideIcon } from 'lucide-react';

interface ModulePageLayoutProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}

export function ModulePageLayout({
  icon: Icon,
  title,
  description,
  actions,
  children
}: ModulePageLayoutProps) {
  return (
    <div className="h-full overflow-y-auto bg-slate-50 dark:bg-slate-900">
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Icon className="w-8 h-8 text-blue-600 dark:text-blue-400" />
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">
                {title}
              </h1>
              {description && (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {description}
                </p>
              )}
            </div>
          </div>
          {actions && (
            <div className="flex gap-2">
              {actions}
            </div>
          )}
        </div>

        {/* Content */}
        <div>{children}</div>
      </div>
    </div>
  );
}
