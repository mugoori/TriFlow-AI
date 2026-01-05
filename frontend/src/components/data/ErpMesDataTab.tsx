/**
 * ErpMesDataTab
 * ERP/MES 데이터 관리 탭
 */

import { useState, useEffect, useCallback } from 'react';
import { useToast } from '@/components/ui/Toast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Database,
  RefreshCw,
  Trash2,
  Upload,
  Factory,
  BarChart3,
  Plus,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { FileUploadZone } from '@/components/ui/FileUploadZone';
import {
  erpMesService,
  type ErpMesData,
  type MockTypesResponse,
  type ErpMesStats,
} from '@/services/erpMesService';

// 소스 타입 한글 매핑
const sourceTypeLabels: Record<string, string> = {
  erp: 'ERP',
  mes: 'MES',
};

// 레코드 타입 한글 매핑
const recordTypeLabels: Record<string, string> = {
  production_order: '생산 오더',
  inventory: '재고',
  bom: '자재명세서(BOM)',
  work_order: '작업 지시',
  equipment_status: '설비 상태',
  quality_record: '품질 검사',
};

export function ErpMesDataTab() {
  const toast = useToast();

  // 상태
  const [data, setData] = useState<ErpMesData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [showMockGenerator, setShowMockGenerator] = useState(false);

  // 필터
  const [selectedSourceType, setSelectedSourceType] = useState<'erp' | 'mes' | ''>('');
  const [selectedRecordType, setSelectedRecordType] = useState('');

  // Mock 데이터 생성
  const [mockTypes, setMockTypes] = useState<MockTypesResponse | null>(null);
  const [mockSourceType, setMockSourceType] = useState<'erp' | 'mes'>('erp');
  const [mockRecordType, setMockRecordType] = useState('production_order');
  const [mockCount, setMockCount] = useState(10);
  const [generating, setGenerating] = useState(false);

  // 통계
  const [stats, setStats] = useState<ErpMesStats | null>(null);

  // 확장된 행
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  // Mock 타입 로드
  useEffect(() => {
    const loadMockTypes = async () => {
      try {
        const types = await erpMesService.getMockTypes();
        setMockTypes(types);
      } catch (err) {
        console.error('Failed to load mock types:', err);
      }
    };
    loadMockTypes();
  }, []);

  // 데이터 로드
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [dataResult, statsResult] = await Promise.all([
        erpMesService.listData({
          source_type: selectedSourceType || undefined,
          record_type: selectedRecordType || undefined,
          limit: 50,
        }),
        erpMesService.getStats(),
      ]);

      setData(dataResult);
      setStats(statsResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터 로드 실패');
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [selectedSourceType, selectedRecordType]);

  // 초기 로드
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Import 설정
  const [importSourceType, setImportSourceType] = useState<'erp' | 'mes'>('erp');
  const [importRecordType, setImportRecordType] = useState('production_order');

  // 파일 업로드 핸들러
  const handleFileUpload = async (file: File) => {
    const result = await erpMesService.importFile(
      file,
      importSourceType,
      importRecordType
    );

    if (!result.success) {
      throw new Error(`Import 실패: ${result.errors.join(', ')}`);
    }

    // 성공 시 데이터 새로고침
    await loadData();
  };

  // Mock 데이터 생성
  const handleGenerateMock = async () => {
    setGenerating(true);
    try {
      await erpMesService.generateMockData({
        source_type: mockSourceType,
        record_type: mockRecordType,
        count: mockCount,
      });
      await loadData();
      setShowMockGenerator(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Mock 데이터 생성 실패');
    } finally {
      setGenerating(false);
    }
  };

  // 데이터 삭제
  const handleDelete = async (dataId: string) => {
    const confirmed = await toast.confirm({
      title: '데이터 삭제',
      message: '이 데이터를 삭제하시겠습니까?',
      confirmText: '삭제',
      cancelText: '취소',
      variant: 'danger',
    });
    if (!confirmed) return;

    try {
      await erpMesService.deleteData(dataId);
      toast.success('데이터가 삭제되었습니다');
      await loadData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '삭제 실패');
    }
  };

  // 행 확장/축소 토글
  const toggleRowExpand = (dataId: string) => {
    setExpandedRow(expandedRow === dataId ? null : dataId);
  };

  // Mock 소스 타입 변경 시 레코드 타입 초기화
  useEffect(() => {
    if (mockTypes) {
      const types = mockTypes[mockSourceType]?.record_types || [];
      if (types.length > 0 && !types.includes(mockRecordType)) {
        setMockRecordType(types[0]);
      }
    }
  }, [mockSourceType, mockTypes, mockRecordType]);

  return (
    <div className="space-y-6">
      {/* 통계 카드 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <Database className="w-8 h-8 text-blue-500" />
                <div>
                  <p className="text-2xl font-bold">{stats.total_records}</p>
                  <p className="text-sm text-slate-500">총 레코드</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <Factory className="w-8 h-8 text-green-500" />
                <div>
                  <p className="text-2xl font-bold">{stats.by_source_type['erp'] || 0}</p>
                  <p className="text-sm text-slate-500">ERP 데이터</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <BarChart3 className="w-8 h-8 text-purple-500" />
                <div>
                  <p className="text-2xl font-bold">{stats.by_source_type['mes'] || 0}</p>
                  <p className="text-sm text-slate-500">MES 데이터</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <Database className="w-8 h-8 text-orange-500" />
                <div>
                  <p className="text-2xl font-bold">{stats.data_sources}</p>
                  <p className="text-sm text-slate-500">데이터 소스</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 액션 버튼 */}
      <div className="flex justify-end gap-2">
        <button
          onClick={() => {
            setShowMockGenerator(!showMockGenerator);
            setShowUpload(false);
          }}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-purple-600 text-white hover:bg-purple-700 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          {showMockGenerator ? '닫기' : 'Mock 데이터 생성'}
        </button>
        <button
          onClick={() => {
            setShowUpload(!showUpload);
            setShowMockGenerator(false);
          }}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-green-600 text-white hover:bg-green-700 rounded-lg transition-colors"
        >
          <Upload className="w-4 h-4" />
          {showUpload ? '닫기' : 'CSV/Excel 업로드'}
        </button>
      </div>

      {/* Mock 데이터 생성 폼 */}
      {showMockGenerator && mockTypes && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Mock 데이터 생성</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  소스 타입
                </label>
                <select
                  value={mockSourceType}
                  onChange={(e) => setMockSourceType(e.target.value as 'erp' | 'mes')}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="erp">ERP (Enterprise Resource Planning)</option>
                  <option value="mes">MES (Manufacturing Execution System)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  레코드 타입
                </label>
                <select
                  value={mockRecordType}
                  onChange={(e) => setMockRecordType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {mockTypes[mockSourceType]?.record_types.map((type) => (
                    <option key={type} value={type}>
                      {recordTypeLabels[type] || type}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  생성 개수
                </label>
                <input
                  type="number"
                  value={mockCount}
                  onChange={(e) => setMockCount(Math.min(100, Math.max(1, parseInt(e.target.value) || 1)))}
                  min={1}
                  max={100}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <button
                onClick={handleGenerateMock}
                disabled={generating}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-purple-600 text-white hover:bg-purple-700 rounded-lg transition-colors disabled:opacity-50"
              >
                {generating ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                Mock 데이터 생성
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 파일 업로드 영역 */}
      {showUpload && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">ERP/MES 데이터 파일 업로드</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Import 설정 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  소스 타입
                </label>
                <select
                  value={importSourceType}
                  onChange={(e) => setImportSourceType(e.target.value as 'erp' | 'mes')}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="erp">ERP</option>
                  <option value="mes">MES</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  레코드 타입
                </label>
                <select
                  value={importRecordType}
                  onChange={(e) => setImportRecordType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {Object.entries(recordTypeLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <FileUploadZone
              accept=".csv,.xlsx,.xls"
              onUpload={handleFileUpload}
              title="ERP/MES 데이터 파일 업로드"
              description="CSV 또는 Excel 파일을 드래그하거나 클릭하여 선택하세요"
            />
          </CardContent>
        </Card>
      )}

      {/* 필터 & 데이터 테이블 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-slate-600 dark:text-slate-400" />
              <CardTitle className="text-base">ERP/MES 데이터</CardTitle>
              <span className="text-sm text-slate-500">({data.length}건)</span>
            </div>
            <button
              onClick={loadData}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              새로고침
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {/* 필터 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                소스 타입
              </label>
              <select
                value={selectedSourceType}
                onChange={(e) => setSelectedSourceType(e.target.value as 'erp' | 'mes' | '')}
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">전체</option>
                <option value="erp">ERP</option>
                <option value="mes">MES</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                레코드 타입
              </label>
              <select
                value={selectedRecordType}
                onChange={(e) => setSelectedRecordType(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">전체</option>
                {Object.entries(recordTypeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* 테이블 */}
          {error ? (
            <div className="text-center py-8 text-red-500">
              <p>오류: {error}</p>
              <button
                onClick={loadData}
                className="mt-2 text-sm text-blue-600 hover:underline"
              >
                다시 시도
              </button>
            </div>
          ) : loading && data.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
              <p>데이터 로딩 중...</p>
            </div>
          ) : data.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <Database className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>등록된 데이터가 없습니다</p>
              <p className="text-sm mt-1">Mock 데이터 생성으로 테스트 데이터를 추가하세요</p>
            </div>
          ) : (
            <div className="border rounded-lg overflow-hidden dark:border-slate-700">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50 dark:bg-slate-800">
                    <TableHead className="w-10"></TableHead>
                    <TableHead className="font-semibold">외부 ID</TableHead>
                    <TableHead className="font-semibold">소스</TableHead>
                    <TableHead className="font-semibold">레코드 타입</TableHead>
                    <TableHead className="font-semibold">상태</TableHead>
                    <TableHead className="font-semibold">등록일</TableHead>
                    <TableHead className="font-semibold text-right">작업</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.map((item) => (
                    <>
                      <TableRow
                        key={item.data_id}
                        className="hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer"
                        onClick={() => toggleRowExpand(item.data_id)}
                      >
                        <TableCell>
                          {expandedRow === item.data_id ? (
                            <ChevronUp className="w-4 h-4 text-slate-400" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-slate-400" />
                          )}
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {item.external_id || '-'}
                        </TableCell>
                        <TableCell>
                          <span
                            className={`px-2 py-1 rounded text-sm ${
                              item.source_type === 'erp'
                                ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                                : 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400'
                            }`}
                          >
                            {sourceTypeLabels[item.source_type] || item.source_type}
                          </span>
                        </TableCell>
                        <TableCell>
                          {recordTypeLabels[item.record_type] || item.record_type}
                        </TableCell>
                        <TableCell>
                          {item.normalized_status && (
                            <span className="px-2 py-1 bg-slate-100 dark:bg-slate-700 rounded text-sm">
                              {item.normalized_status}
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-slate-500">
                          {new Date(item.created_at).toLocaleDateString('ko-KR')}
                        </TableCell>
                        <TableCell className="text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(item.data_id);
                            }}
                            className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                            title="삭제"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </TableCell>
                      </TableRow>
                      {expandedRow === item.data_id && (
                        <TableRow>
                          <TableCell colSpan={7} className="bg-slate-50 dark:bg-slate-800/50">
                            <div className="p-4">
                              <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                                Raw Data:
                              </p>
                              <pre className="text-xs bg-slate-100 dark:bg-slate-900 p-3 rounded overflow-x-auto">
                                {JSON.stringify(item.raw_data, null, 2)}
                              </pre>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
