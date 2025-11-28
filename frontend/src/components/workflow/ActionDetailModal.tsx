/**
 * ActionDetailModal
 * 액션 상세 정보를 보여주는 모달
 * - 액션 이름, 설명, 카테고리
 * - 파라미터 목록 및 타입
 * - 워크플로우에 추가하기 위한 복사 기능
 */

import React from 'react';
import { X, Copy, Check, Zap, Bell, Database, Settings, BarChart3 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { ActionCatalogItem } from '@/services/workflowService';

interface ActionDetailModalProps {
  action: ActionCatalogItem | null;
  isOpen: boolean;
  onClose: () => void;
}

// 카테고리별 아이콘 매핑
const categoryIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  notification: Bell,
  data: Database,
  control: Settings,
  analysis: BarChart3,
};

// 카테고리별 색상 매핑
const categoryColors: Record<string, string> = {
  notification: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  data: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  control: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  analysis: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
};

// 카테고리 한글 이름
const categoryLabels: Record<string, string> = {
  notification: '알림',
  data: '데이터',
  control: '제어',
  analysis: '분석',
};

export function ActionDetailModal({ action, isOpen, onClose }: ActionDetailModalProps) {
  const [copied, setCopied] = React.useState(false);

  if (!isOpen || !action) return null;

  const CategoryIcon = categoryIcons[action.category] || Zap;

  // DSL 예시 생성
  const generateDSLExample = () => {
    const params: Record<string, string> = {};
    Object.keys(action.parameters).forEach((key) => {
      params[key] = `<${key}>`;
    });

    return {
      id: `action_${Date.now()}`,
      type: 'action',
      config: {
        action: action.name,
        parameters: params,
      },
      next: [],
    };
  };

  const handleCopyDSL = async () => {
    const dsl = generateDSLExample();
    await navigator.clipboard.writeText(JSON.stringify(dsl, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-lg mx-4 bg-white dark:bg-slate-900 rounded-xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${categoryColors[action.category]}`}>
              <CategoryIcon className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                {action.name}
              </h2>
              <span className={`inline-block px-2 py-0.5 text-xs rounded ${categoryColors[action.category]}`}>
                {categoryLabels[action.category] || action.category}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Description */}
          <div>
            <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400 mb-1">
              설명
            </h3>
            <p className="text-slate-900 dark:text-white">
              {action.description}
            </p>
          </div>

          {/* Parameters */}
          <div>
            <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400 mb-2">
              파라미터
            </h3>
            <div className="space-y-2">
              {Object.entries(action.parameters).map(([name, type]) => (
                <div
                  key={name}
                  className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg"
                >
                  <div className="flex-1">
                    <code className="text-sm font-mono font-medium text-blue-600 dark:text-blue-400">
                      {name}
                    </code>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">
                      {type}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* DSL Example */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">DSL 예시</CardTitle>
                <button
                  onClick={handleCopyDSL}
                  className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-green-500" />
                      복사됨
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      복사
                    </>
                  )}
                </button>
              </div>
            </CardHeader>
            <CardContent>
              <pre className="text-xs font-mono bg-slate-900 dark:bg-slate-950 text-slate-100 p-3 rounded-lg overflow-x-auto">
                {JSON.stringify(generateDSLExample(), null, 2)}
              </pre>
            </CardContent>
          </Card>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 p-4 border-t border-slate-200 dark:border-slate-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            닫기
          </button>
          <button
            onClick={handleCopyDSL}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Copy className="w-4 h-4" />
            워크플로우에 추가
          </button>
        </div>
      </div>
    </div>
  );
}
