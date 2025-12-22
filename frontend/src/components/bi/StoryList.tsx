/**
 * StoryList - Data Stories 목록 컴포넌트
 * AWS QuickSight GenBI Data Stories 기능 구현
 */

import { useState, useEffect } from 'react';
import {
  BookOpen,
  Plus,
  RefreshCw,
  Loader2,
  AlertCircle,
  Globe,
  Lock,
  Calendar,
  MoreVertical,
  Trash2,
  Eye,
  FileText,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type { DataStory, StoryCreateRequest } from '@/types/bi';
import { biService } from '@/services/biService';

interface StoryListProps {
  onSelectStory?: (story: DataStory) => void;
  onCreateStory?: () => void;
  className?: string;
}

export function StoryList({ onSelectStory, onCreateStory, className = '' }: StoryListProps) {
  const [stories, setStories] = useState<DataStory[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    loadStories();
  }, []);

  const loadStories = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await biService.getStories({ include_public: true });
      setStories(response.stories);
    } catch (err) {
      console.error('Failed to load stories:', err);
      setError(err instanceof Error ? err.message : 'Failed to load stories');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteStory = async (storyId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('정말로 이 스토리를 삭제하시겠습니까?')) return;

    try {
      await biService.deleteStory(storyId);
      setStories((prev) => prev.filter((s) => s.story_id !== storyId));
    } catch (err) {
      console.error('Failed to delete story:', err);
      alert('스토리 삭제에 실패했습니다.');
    }
  };

  const handleCreateStory = () => {
    if (onCreateStory) {
      onCreateStory();
    } else {
      setShowCreateModal(true);
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-indigo-500" />
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
            Data Stories
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCreateStory}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-4 h-4" />새 스토리
          </button>
          <button
            onClick={loadStories}
            disabled={isLoading}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="새로고침"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-sm">
            <AlertCircle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Loading */}
      {isLoading && stories.length === 0 && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
        </div>
      )}

      {/* Empty State */}
      {!isLoading && stories.length === 0 && (
        <Card>
          <CardContent className="py-12">
            <div className="text-center text-slate-500">
              <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium mb-2">스토리가 없습니다</p>
              <p className="text-sm mb-4">
                "새 스토리" 버튼을 클릭하여 데이터 스토리를 생성하세요
              </p>
              <button
                onClick={handleCreateStory}
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
                스토리 만들기
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Story Grid */}
      {stories.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {stories.map((story) => (
            <StoryCard
              key={story.story_id}
              story={story}
              onClick={() => onSelectStory?.(story)}
              onDelete={(e) => handleDeleteStory(story.story_id, e)}
            />
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <CreateStoryModal
          onClose={() => setShowCreateModal(false)}
          onCreated={(story) => {
            setStories((prev) => [story, ...prev]);
            setShowCreateModal(false);
            onSelectStory?.(story);
          }}
        />
      )}
    </div>
  );
}

// =====================================================
// StoryCard 컴포넌트
// =====================================================

interface StoryCardProps {
  story: DataStory;
  onClick?: () => void;
  onDelete?: (e: React.MouseEvent) => void;
}

function StoryCard({ story, onClick, onDelete }: StoryCardProps) {
  const [showMenu, setShowMenu] = useState(false);

  const sectionCount = story.sections?.length || 0;
  const chartCount = story.sections?.reduce(
    (sum, s) => sum + (s.charts?.length || 0),
    0
  ) || 0;

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <h4 className="font-semibold text-slate-900 dark:text-slate-50 line-clamp-1">
              {story.title}
            </h4>
            {story.description && (
              <p className="text-sm text-slate-500 mt-1 line-clamp-2">
                {story.description}
              </p>
            )}
          </div>
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowMenu(!showMenu);
              }}
              className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <MoreVertical className="w-4 h-4 text-slate-400" />
            </button>
            {showMenu && (
              <div
                className="absolute right-0 top-8 w-36 bg-white dark:bg-slate-800 rounded-lg shadow-lg border dark:border-slate-700 py-1 z-10"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  onClick={onClick}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-100 dark:hover:bg-slate-700"
                >
                  <Eye className="w-4 h-4" /> 보기
                </button>
                <button
                  onClick={onDelete}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                >
                  <Trash2 className="w-4 h-4" /> 삭제
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-4 text-xs text-slate-500 mb-3">
          <span className="flex items-center gap-1">
            <FileText className="w-3 h-3" />
            {sectionCount}개 섹션
          </span>
          {chartCount > 0 && (
            <span>{chartCount}개 차트</span>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t dark:border-slate-700">
          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {new Date(story.created_at).toLocaleDateString('ko-KR')}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {story.is_public ? (
              <span className="flex items-center gap-1 text-xs text-green-600">
                <Globe className="w-3 h-3" /> 공개
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs text-slate-400">
                <Lock className="w-3 h-3" /> 비공개
              </span>
            )}
            {story.published_at && (
              <span className="px-2 py-0.5 text-xs bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 rounded">
                발행됨
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// =====================================================
// CreateStoryModal 컴포넌트
// =====================================================

interface CreateStoryModalProps {
  onClose: () => void;
  onCreated: (story: DataStory) => void;
}

function CreateStoryModal({ onClose, onCreated }: CreateStoryModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [autoGenerate, setAutoGenerate] = useState(true);
  const [focusTopic, setFocusTopic] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setIsCreating(true);
    setError(null);
    try {
      const request: StoryCreateRequest = {
        title: title.trim(),
        description: description.trim() || undefined,
        auto_generate: autoGenerate,
        focus_topic: focusTopic.trim() || undefined,
      };
      const story = await biService.createStory(request);
      onCreated(story);
    } catch (err) {
      console.error('Failed to create story:', err);
      setError(err instanceof Error ? err.message : 'Failed to create story');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="p-6">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50 mb-4">
            새 스토리 만들기
          </h3>

          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-sm">
                <AlertCircle className="w-4 h-4" />
                <span>{error}</span>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                제목 *
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="예: 월간 생산 효율 보고서"
                className="w-full px-3 py-2 border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                설명
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="스토리에 대한 간단한 설명"
                rows={2}
                className="w-full px-3 py-2 border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
            </div>

            <div>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={autoGenerate}
                  onChange={(e) => setAutoGenerate(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm text-slate-700 dark:text-slate-300">
                  AI 자동 생성 (대시보드 데이터 기반)
                </span>
              </label>
            </div>

            {autoGenerate && (
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  집중 주제 (선택)
                </label>
                <input
                  type="text"
                  value={focusTopic}
                  onChange={(e) => setFocusTopic(e.target.value)}
                  placeholder="예: 생산 효율, 품질 분석, 비용 절감"
                  className="w-full px-3 py-2 border dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            )}

            <div className="flex justify-end gap-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={isCreating || !title.trim()}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {isCreating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    생성 중...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    만들기
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default StoryList;
