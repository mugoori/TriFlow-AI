/**
 * StatCardGrid
 * 드래그앤드롭 지원 StatCard 그리드 컴포넌트
 *
 * 기능:
 * - 카드 드래그앤드롭 재정렬 (HTML5 Drag and Drop API)
 * - 편집 모드 토글
 * - 카드 개수 1~6개 조절
 */

import { useState, useCallback } from 'react';
import { Settings, GripVertical, Check, Calendar } from 'lucide-react';
import { DynamicStatCard, AddStatCardButton, StatCardSkeleton } from './DynamicStatCard';
import { useStatCards } from '@/contexts/StatCardContext';
import { PERIOD_OPTIONS, type StatCardPeriod } from '@/types/statcard';

interface StatCardGridProps {
  onAddCard: () => void;
  onEditCard: (configId: string) => void;
  onDeleteCard: (configId: string) => void;
  maxCards?: number;
}

export function StatCardGrid({
  onAddCard,
  onEditCard,
  onDeleteCard,
  maxCards = 6,
}: StatCardGridProps) {
  const {
    cards,
    loading,
    reorderCards,
    refreshValues,
    selectedPeriod,
    latestDataDate,
    setSelectedPeriod,
  } = useStatCards();
  const [isEditMode, setIsEditMode] = useState(false);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  // 기간 변경 핸들러
  const handlePeriodChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedPeriod(e.target.value as StatCardPeriod);
  }, [setSelectedPeriod]);

  // 드래그 시작
  const handleDragStart = useCallback((e: React.DragEvent, configId: string) => {
    setDraggedId(configId);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', configId);
  }, []);

  // 드래그 오버
  const handleDragOver = useCallback((e: React.DragEvent, configId: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (configId !== draggedId) {
      setDragOverId(configId);
    }
  }, [draggedId]);

  // 드래그 떠남
  const handleDragLeave = useCallback(() => {
    setDragOverId(null);
  }, []);

  // 드롭
  const handleDrop = useCallback(async (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    setDragOverId(null);

    if (!draggedId || draggedId === targetId) {
      setDraggedId(null);
      return;
    }

    // 새 순서 계산
    const currentIds = cards.map((c) => c.config.config_id);
    const draggedIndex = currentIds.indexOf(draggedId);
    const targetIndex = currentIds.indexOf(targetId);

    if (draggedIndex === -1 || targetIndex === -1) {
      setDraggedId(null);
      return;
    }

    // 배열에서 draggedId 제거 후 targetIndex 위치에 삽입
    const newIds = [...currentIds];
    newIds.splice(draggedIndex, 1);
    newIds.splice(targetIndex, 0, draggedId);

    try {
      await reorderCards(newIds);
    } catch (err) {
      console.error('Failed to reorder cards:', err);
    }

    setDraggedId(null);
  }, [draggedId, cards, reorderCards]);

  // 드래그 종료
  const handleDragEnd = useCallback(() => {
    setDraggedId(null);
    setDragOverId(null);
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-slate-600 dark:text-slate-400">핵심 지표</h3>
        </div>
        <div className="flex overflow-x-auto gap-4 pb-2 snap-x snap-mandatory scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-600 scrollbar-track-transparent">
          <div className="flex-shrink-0 w-64 snap-start"><StatCardSkeleton /></div>
          <div className="flex-shrink-0 w-64 snap-start"><StatCardSkeleton /></div>
          <div className="flex-shrink-0 w-64 snap-start"><StatCardSkeleton /></div>
          <div className="flex-shrink-0 w-64 snap-start"><StatCardSkeleton /></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-slate-600 dark:text-slate-400">
            핵심 지표
          </h3>
          <span className="text-xs text-slate-400">
            {cards.length}/{maxCards}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* 기간 선택 드롭다운 */}
          <div className="flex items-center gap-1">
            <Calendar className="w-4 h-4 text-slate-400" />
            <select
              value={selectedPeriod}
              onChange={handlePeriodChange}
              className="text-xs border border-slate-200 dark:border-slate-700 rounded px-2 py-1 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {PERIOD_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {latestDataDate && selectedPeriod === 'auto' && (
              <span className="text-xs text-slate-400 dark:text-slate-500">
                ({latestDataDate} 기준)
              </span>
            )}
          </div>

          {/* 편집 모드 토글 */}
          <button
            onClick={() => setIsEditMode(!isEditMode)}
            className={`p-2 rounded-lg transition-colors ${
              isEditMode
                ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
                : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500'
            }`}
            title={isEditMode ? '편집 완료' : '카드 편집'}
          >
            {isEditMode ? <Check className="w-4 h-4" /> : <Settings className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* 카드 슬라이드 (수평 스크롤) */}
      <div className="flex overflow-x-auto gap-4 pb-2 snap-x snap-mandatory scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-600 scrollbar-track-transparent">
        {cards.map((card) => (
          <div
            key={card.config.config_id}
            className={`relative flex-shrink-0 w-64 snap-start ${isEditMode ? 'cursor-move' : ''} ${
              dragOverId === card.config.config_id
                ? 'ring-2 ring-blue-500 ring-offset-2 rounded-lg'
                : ''
            } ${
              draggedId === card.config.config_id ? 'opacity-50' : ''
            }`}
            draggable={isEditMode}
            onDragStart={(e) => handleDragStart(e, card.config.config_id)}
            onDragOver={(e) => handleDragOver(e, card.config.config_id)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, card.config.config_id)}
            onDragEnd={handleDragEnd}
          >
            {/* 편집 모드일 때 드래그 핸들 표시 */}
            {isEditMode && (
              <div className="absolute -left-2 top-1/2 -translate-y-1/2 z-10 p-1 bg-white dark:bg-slate-800 rounded shadow border border-slate-200 dark:border-slate-700">
                <GripVertical className="w-4 h-4 text-slate-400" />
              </div>
            )}

            <DynamicStatCard
              card={card}
              onEdit={onEditCard}
              onDelete={onDeleteCard}
              onRefresh={() => refreshValues()}
              showActions={!isEditMode}
            />
          </div>
        ))}

        {/* 카드 추가 버튼 */}
        {cards.length < maxCards && (
          <div className="flex-shrink-0 w-64 snap-start">
            <AddStatCardButton onClick={onAddCard} />
          </div>
        )}
      </div>

      {/* 편집 모드 안내 */}
      {isEditMode && (
        <p className="text-xs text-slate-500 text-center">
          카드를 드래그하여 순서를 변경하세요
        </p>
      )}
    </div>
  );
}
