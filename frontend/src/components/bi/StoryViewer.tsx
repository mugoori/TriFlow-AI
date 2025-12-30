/**
 * StoryViewer - Data Story 뷰어 컴포넌트
 * AWS QuickSight GenBI Data Stories 슬라이드/스크롤 뷰어
 */

import { useState, useEffect } from 'react';
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  X,
  Maximize2,
  Minimize2,
  List,
  Presentation,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { ChartRenderer } from '@/components/charts';
import type { DataStory, StorySection, StoryViewMode } from '@/types/bi';
import { SECTION_TYPE_LABELS, SECTION_TYPE_COLORS } from '@/types/bi';
import { biService } from '@/services/biService';

interface StoryViewerProps {
  story?: DataStory;
  storyId?: string;
  onClose?: () => void;
  initialMode?: StoryViewMode;
  className?: string;
}

export function StoryViewer({
  story: initialStory,
  storyId,
  onClose,
  initialMode = 'slide',
  className = '',
}: StoryViewerProps) {
  const [story, setStory] = useState<DataStory | null>(initialStory || null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<StoryViewMode>(initialMode);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // 스토리 로드 - 항상 상세 API 호출하여 sections 포함된 데이터 가져오기
  useEffect(() => {
    const storyIdToLoad = storyId || initialStory?.story_id;
    if (storyIdToLoad) {
      loadStory(storyIdToLoad);
    }
  }, [storyId, initialStory?.story_id]);

  const loadStory = async (id: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await biService.getStory(id);
      setStory(data);
    } catch (err) {
      console.error('Failed to load story:', err);
      setError(err instanceof Error ? err.message : 'Failed to load story');
    } finally {
      setIsLoading(false);
    }
  };

  const sections = story?.sections || [];
  const totalSlides = sections.length;

  const goToSlide = (index: number) => {
    if (index >= 0 && index < totalSlides) {
      setCurrentSlide(index);
    }
  };

  const nextSlide = () => goToSlide(currentSlide + 1);
  const prevSlide = () => goToSlide(currentSlide - 1);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  // 키보드 네비게이션
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (viewMode === 'slide') {
        if (e.key === 'ArrowRight' || e.key === ' ') {
          nextSlide();
        } else if (e.key === 'ArrowLeft') {
          prevSlide();
        } else if (e.key === 'Escape') {
          if (isFullscreen) {
            document.exitFullscreen();
            setIsFullscreen(false);
          } else {
            onClose?.();
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [viewMode, currentSlide, totalSlides, isFullscreen]);

  // Loading
  if (isLoading) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  // Error
  if (error) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <div className="text-center">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-500" />
          <p className="text-red-600">{error}</p>
          <button
            onClick={onClose}
            className="mt-4 px-4 py-2 bg-slate-200 dark:bg-slate-700 rounded-lg"
          >
            닫기
          </button>
        </div>
      </div>
    );
  }

  // No story
  if (!story) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <div className="text-center text-slate-500">
          <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>스토리를 선택해주세요</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`h-full flex flex-col ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
        <div className="flex items-center gap-3">
          <BookOpen className="w-5 h-5 text-indigo-500" />
          <h2 className="font-semibold text-slate-900 dark:text-slate-50">
            {story.title}
          </h2>
          {story.published_at && (
            <span className="px-2 py-0.5 text-xs bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 rounded">
              발행됨
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* View Mode Toggle */}
          <div className="flex items-center bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
            <button
              onClick={() => setViewMode('slide')}
              className={`p-1.5 rounded ${
                viewMode === 'slide'
                  ? 'bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-slate-100'
                  : 'text-slate-500 dark:text-slate-400'
              }`}
              title="슬라이드 모드"
            >
              <Presentation className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('scroll')}
              className={`p-1.5 rounded ${
                viewMode === 'scroll'
                  ? 'bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-slate-100'
                  : 'text-slate-500 dark:text-slate-400'
              }`}
              title="스크롤 모드"
            >
              <List className="w-4 h-4" />
            </button>
          </div>
          <button
            onClick={toggleFullscreen}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400"
            title={isFullscreen ? '전체화면 종료' : '전체화면'}
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400"
              title="닫기"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {sections.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-500">
            <div className="text-center">
              <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>섹션이 없습니다</p>
            </div>
          </div>
        ) : viewMode === 'slide' ? (
          <SlideView
            sections={sections}
            currentSlide={currentSlide}
            onPrev={prevSlide}
            onNext={nextSlide}
            onGoTo={goToSlide}
          />
        ) : (
          <ScrollView sections={sections} />
        )}
      </div>
    </div>
  );
}

// =====================================================
// SlideView 컴포넌트
// =====================================================

interface SlideViewProps {
  sections: StorySection[];
  currentSlide: number;
  onPrev: () => void;
  onNext: () => void;
  onGoTo: (index: number) => void;
}

function SlideView({ sections, currentSlide, onPrev, onNext, onGoTo }: SlideViewProps) {
  const section = sections[currentSlide];
  if (!section) return null;

  return (
    <div className="h-full flex flex-col bg-white dark:bg-slate-900">
      {/* Slide Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <SectionContent section={section} isSlideMode />
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
        <button
          onClick={onPrev}
          disabled={currentSlide === 0}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-5 h-5" />
          이전
        </button>

        {/* Dot Navigation */}
        <div className="flex items-center gap-2">
          {sections.map((_, index) => (
            <button
              key={index}
              onClick={() => onGoTo(index)}
              className={`w-2.5 h-2.5 rounded-full transition-colors ${
                index === currentSlide
                  ? 'bg-indigo-500'
                  : 'bg-slate-300 dark:bg-slate-600 hover:bg-slate-400'
              }`}
              title={`섹션 ${index + 1}`}
            />
          ))}
        </div>

        <button
          onClick={onNext}
          disabled={currentSlide === sections.length - 1}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          다음
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

// =====================================================
// ScrollView 컴포넌트
// =====================================================

interface ScrollViewProps {
  sections: StorySection[];
}

function ScrollView({ sections }: ScrollViewProps) {
  return (
    <div className="h-full overflow-y-auto p-6 space-y-8 bg-white dark:bg-slate-900">
      {sections.map((section, index) => (
        <div key={section.section_id} className="scroll-mt-4">
          <SectionContent section={section} isSlideMode={false} />
          {index < sections.length - 1 && (
            <hr className="mt-8 border-slate-200 dark:border-slate-700" />
          )}
        </div>
      ))}
    </div>
  );
}

// =====================================================
// SectionContent 컴포넌트
// =====================================================

interface SectionContentProps {
  section: StorySection;
  isSlideMode: boolean;
}

function SectionContent({ section, isSlideMode }: SectionContentProps) {
  const typeColor = SECTION_TYPE_COLORS[section.section_type];
  const typeLabel = SECTION_TYPE_LABELS[section.section_type];

  return (
    <div className={isSlideMode ? 'max-w-4xl mx-auto' : ''}>
      {/* Section Header */}
      <div className="mb-6">
        <span
          className="inline-block px-3 py-1 text-sm font-medium rounded-full mb-3"
          style={{
            backgroundColor: `${typeColor}20`,
            color: typeColor,
          }}
        >
          {typeLabel}
        </span>
        <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-50">
          {section.title}
        </h3>
      </div>

      {/* Narrative */}
      <div className="prose prose-slate dark:prose-invert max-w-none mb-6">
        <NarrativeRenderer content={section.narrative} />
      </div>

      {/* Charts */}
      {section.charts && section.charts.length > 0 && (
        <div className={`grid gap-6 ${
          section.charts.length === 1
            ? 'grid-cols-1'
            : 'grid-cols-1 lg:grid-cols-2'
        }`}>
          {section.charts.map((chart, index) => (
            <Card key={index}>
              <CardContent className="p-4">
                <ChartRenderer config={chart.chart_config} />
                {chart.caption && (
                  <p className="text-sm text-slate-500 mt-3 text-center italic">
                    {chart.caption}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* AI Generated Badge */}
      {section.ai_generated && (
        <div className="mt-4 text-xs text-slate-400 flex items-center gap-1">
          <span className="w-1.5 h-1.5 bg-purple-400 rounded-full" />
          AI 자동 생성
        </div>
      )}
    </div>
  );
}

// =====================================================
// NarrativeRenderer - 간단한 Markdown 렌더러
// =====================================================

function NarrativeRenderer({ content }: { content: string }) {
  // 간단한 Markdown 파싱 (실제로는 react-markdown 사용 권장)
  const lines = content.split('\n');

  return (
    <div className="space-y-3 text-slate-800 dark:text-slate-200">
      {lines.map((line, index) => {
        // 헤더
        if (line.startsWith('### ')) {
          return (
            <h4 key={index} className="text-lg font-semibold mt-4 text-slate-900 dark:text-slate-100">
              {line.slice(4)}
            </h4>
          );
        }
        if (line.startsWith('## ')) {
          return (
            <h3 key={index} className="text-xl font-bold mt-4 text-slate-900 dark:text-slate-100">
              {line.slice(3)}
            </h3>
          );
        }
        // 불릿
        if (line.startsWith('- ') || line.startsWith('* ')) {
          return (
            <li key={index} className="ml-4 text-slate-700 dark:text-slate-300">
              {line.slice(2)}
            </li>
          );
        }
        // 굵은 텍스트
        const boldProcessed = line.replace(
          /\*\*(.*?)\*\*/g,
          '<strong class="text-slate-900 dark:text-slate-100">$1</strong>'
        );
        // 빈 줄
        if (!line.trim()) {
          return <br key={index} />;
        }
        // 일반 텍스트
        return (
          <p
            key={index}
            className="text-slate-700 dark:text-slate-300"
            dangerouslySetInnerHTML={{ __html: boldProcessed }}
          />
        );
      })}
    </div>
  );
}

export default StoryViewer;
