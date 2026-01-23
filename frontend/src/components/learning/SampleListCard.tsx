/**
 * SampleListCard - 샘플 목록 카드
 * 샘플 테이블, 필터링, 승인/거부 버튼 제공
 */

import { useState, useEffect, useCallback } from 'react';
import {
  List,
  Filter,
  CheckCircle,
  XCircle,
  Eye,
} from 'lucide-react';
import { Pagination } from '@/components/ui/Pagination';
import {
  sampleService,
  Sample,
  SampleStatus,
  SampleCategory,
} from '@/services/sampleService';
import { STATUS_LABELS, STATUS_COLORS, SAMPLE_CATEGORY_LABELS } from '@/lib/statusConfig';

interface SampleListCardProps {
  onSelectSample?: (sample: Sample) => void;
  onRefresh?: () => void;
}

const CATEGORY_LABELS: Record<SampleCategory | string, string> = SAMPLE_CATEGORY_LABELS;

export function SampleListCard({ onSelectSample, onRefresh }: SampleListCardProps) {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 10;

  // Filters
  const [statusFilter, setStatusFilter] = useState<SampleStatus | ''>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [showFilters, setShowFilters] = useState(false);

  const loadSamples = useCallback(async () => {
    try {
      setLoading(true);
      const response = await sampleService.listSamples({
        status: statusFilter || undefined,
        category: categoryFilter || undefined,
        page,
        page_size: pageSize,
      });
      setSamples(response.samples);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to load samples:', err);
      // 데모 데이터
      setSamples([
        {
          sample_id: '1',
          tenant_id: 't1',
          source_type: 'feedback',
          category: 'threshold_adjustment',
          input_data: { temperature: 85, pressure: 102 },
          expected_output: { threshold: 90 },
          context: {},
          quality_score: 0.92,
          confidence: 0.88,
          content_hash: 'hash1',
          status: 'pending',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          sample_id: '2',
          tenant_id: 't1',
          source_type: 'validation',
          category: 'field_correction',
          input_data: { field_a: 'value1', field_b: 123 },
          expected_output: { corrected_value: 'value2' },
          context: {},
          quality_score: 0.85,
          confidence: 0.75,
          content_hash: 'hash2',
          status: 'approved',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]);
      setTotal(2);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, categoryFilter, page]);

  useEffect(() => {
    loadSamples();
  }, [loadSamples]);

  const handleApprove = async (sampleId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await sampleService.approveSample(sampleId);
      await loadSamples();
      onRefresh?.();
    } catch (err) {
      console.error('Failed to approve sample:', err);
    }
  };

  const handleReject = async (sampleId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const reason = prompt('거부 사유를 입력하세요:');
    if (!reason) return;

    try {
      await sampleService.rejectSample(sampleId, reason);
      await loadSamples();
      onRefresh?.();
    } catch (err) {
      console.error('Failed to reject sample:', err);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <List className="w-5 h-5 text-blue-500" />
          <h3 className="font-semibold text-gray-900 dark:text-white">샘플 목록</h3>
          <span className="text-sm text-gray-500 dark:text-gray-400">({total}개)</span>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`p-2 rounded-lg transition-colors ${
            showFilters
              ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
              : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
          }`}
        >
          <Filter className="w-4 h-4" />
        </button>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
          <div className="flex flex-wrap gap-4">
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">상태</label>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value as SampleStatus | '');
                  setPage(1);
                }}
                className="px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
              >
                <option value="">전체</option>
                <option value="pending">대기</option>
                <option value="approved">승인</option>
                <option value="rejected">거부</option>
                <option value="archived">보관</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">카테고리</label>
              <select
                value={categoryFilter}
                onChange={(e) => {
                  setCategoryFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
              >
                <option value="">전체</option>
                <option value="threshold_adjustment">임계값 조정</option>
                <option value="field_correction">필드 수정</option>
                <option value="validation_failure">검증 실패</option>
                <option value="general">일반</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        {loading ? (
          <div className="p-8 text-center">
            <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto" />
          </div>
        ) : samples.length > 0 ? (
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  카테고리
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  상태
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  품질
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  소스
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  생성일
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  작업
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {samples.map((sample) => (
                <tr
                  key={sample.sample_id}
                  onClick={() => onSelectSample?.(sample)}
                  className="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <span className="text-sm text-gray-900 dark:text-white">
                      {CATEGORY_LABELS[sample.category] || sample.category}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 text-xs rounded-full ${
                        STATUS_COLORS[sample.status]
                      }`}
                    >
                      {STATUS_LABELS[sample.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                        <div
                          className={`h-1.5 rounded-full ${
                            sample.quality_score >= 0.8
                              ? 'bg-green-500'
                              : sample.quality_score >= 0.6
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                          }`}
                          style={{ width: `${sample.quality_score * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {(sample.quality_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                      {sample.source_type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {new Date(sample.created_at).toLocaleDateString('ko-KR')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectSample?.(sample);
                        }}
                        className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                        title="상세 보기"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      {sample.status === 'pending' && (
                        <>
                          <button
                            onClick={(e) => handleApprove(sample.sample_id, e)}
                            className="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors"
                            title="승인"
                          >
                            <CheckCircle className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => handleReject(sample.sample_id, e)}
                            className="p-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                            title="거부"
                          >
                            <XCircle className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-8 text-center">
            <List className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400">샘플이 없습니다</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      <Pagination
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
      />
    </div>
  );
}

export default SampleListCard;
