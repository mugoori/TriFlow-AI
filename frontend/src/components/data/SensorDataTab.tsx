/**
 * SensorDataTab
 * 센서 데이터 조회 및 CSV 업로드 탭
 */

import { useState, useEffect, useCallback } from 'react';
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
  Filter,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Thermometer,
  Gauge,
  Droplets,
  Activity,
  Wind,
  Download,
  Upload,
} from 'lucide-react';
import {
  sensorService,
  type SensorDataItem,
  type SensorFilterOptions,
  type SensorDataParams,
} from '@/services/sensorService';
import { FileUploadZone } from '@/components/ui/FileUploadZone';
import { useAuth } from '@/contexts/AuthContext';

// 센서 타입별 아이콘 매핑
const sensorTypeIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  temperature: Thermometer,
  pressure: Gauge,
  humidity: Droplets,
  vibration: Activity,
  flow_rate: Wind,
};

// 센서 타입 한글 매핑
const sensorTypeLabels: Record<string, string> = {
  temperature: '온도',
  pressure: '압력',
  humidity: '습도',
  vibration: '진동',
  flow_rate: '유량',
};

export function SensorDataTab() {
  const { accessToken: token } = useAuth();

  // 상태
  const [data, setData] = useState<SensorDataItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterOptions, setFilterOptions] = useState<SensorFilterOptions | null>(null);
  const [showUpload, setShowUpload] = useState(false);

  // 페이지네이션
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);

  // 필터
  const [startDate, setStartDate] = useState<string>(() => {
    const date = new Date();
    date.setDate(date.getDate() - 1);
    return date.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState<string>(() => {
    return new Date().toISOString().split('T')[0];
  });
  const [selectedLine, setSelectedLine] = useState<string>('');
  const [selectedSensorType, setSelectedSensorType] = useState<string>('');

  // 필터 옵션 로드
  useEffect(() => {
    const loadFilterOptions = async () => {
      try {
        const options = await sensorService.getFilterOptions();
        setFilterOptions(options);
      } catch (err) {
        console.error('Failed to load filter options:', err);
      }
    };
    loadFilterOptions();
  }, []);

  // 데이터 로드
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const params: SensorDataParams = {
        page,
        page_size: pageSize,
      };

      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) {
        const end = new Date(endDate);
        end.setHours(23, 59, 59, 999);
        params.end_date = end.toISOString();
      }
      if (selectedLine) params.line_code = selectedLine;
      if (selectedSensorType) params.sensor_type = selectedSensorType;

      const response = await sensorService.getData(params);
      setData(response.data);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터 로드 실패');
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, startDate, endDate, selectedLine, selectedSensorType]);

  // 데이터 로드 트리거
  useEffect(() => {
    loadData();
  }, [loadData]);

  // 필터 초기화
  const resetFilters = () => {
    const date = new Date();
    date.setDate(date.getDate() - 1);
    setStartDate(date.toISOString().split('T')[0]);
    setEndDate(new Date().toISOString().split('T')[0]);
    setSelectedLine('');
    setSelectedSensorType('');
    setPage(1);
  };

  // CSV 다운로드
  const downloadCsv = () => {
    if (data.length === 0) return;

    const headers = ['센서ID', '기록시간', '라인', '센서타입', '값', '단위'];
    const rows = data.map((item) => [
      item.sensor_id,
      new Date(item.recorded_at).toLocaleString('ko-KR'),
      item.line_code,
      sensorTypeLabels[item.sensor_type] || item.sensor_type,
      item.value,
      item.unit || '',
    ]);

    const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `sensor_data_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // 파일 업로드 핸들러
  const handleFileUpload = async (file: File) => {
    if (!token) {
      throw new Error('로그인이 필요합니다');
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(
      `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/sensors/import`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || '업로드 실패');
    }

    // 업로드 성공 후 데이터 새로고침
    await loadData();
  };

  // 페이지 수 계산
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      {/* 업로드 토글 버튼 */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowUpload(!showUpload)}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-green-600 text-white hover:bg-green-700 rounded-lg transition-colors"
        >
          <Upload className="w-4 h-4" />
          {showUpload ? '업로드 닫기' : 'CSV/Excel 업로드'}
        </button>
      </div>

      {/* 업로드 영역 */}
      {showUpload && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">센서 데이터 업로드</CardTitle>
          </CardHeader>
          <CardContent>
            <FileUploadZone
              accept=".csv,.xlsx,.xls"
              onUpload={handleFileUpload}
              title="센서 데이터 파일 업로드"
              description="CSV 또는 Excel 파일을 드래그하거나 클릭하여 선택하세요"
            />
          </CardContent>
        </Card>
      )}

      {/* 필터 섹션 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-slate-600 dark:text-slate-400" />
              <CardTitle className="text-base">필터</CardTitle>
            </div>
            <div className="flex gap-2">
              <button
                onClick={resetFilters}
                className="px-3 py-1.5 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              >
                초기화
              </button>
              <button
                onClick={loadData}
                disabled={loading}
                className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                새로고침
              </button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 시작 날짜 */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                시작 날짜
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* 종료 날짜 */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                종료 날짜
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* 라인 선택 */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                생산 라인
              </label>
              <select
                value={selectedLine}
                onChange={(e) => {
                  setSelectedLine(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">전체</option>
                {filterOptions?.lines.map((line) => (
                  <option key={line} value={line}>
                    {line}
                  </option>
                ))}
              </select>
            </div>

            {/* 센서 타입 선택 */}
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                센서 타입
              </label>
              <select
                value={selectedSensorType}
                onChange={(e) => {
                  setSelectedSensorType(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">전체</option>
                {filterOptions?.sensor_types.map((type) => (
                  <option key={type} value={type}>
                    {sensorTypeLabels[type] || type}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 데이터 테이블 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-slate-600 dark:text-slate-400" />
              <CardTitle className="text-base">센서 데이터</CardTitle>
              <span className="text-sm text-slate-500">({total.toLocaleString()}건)</span>
            </div>
            <button
              onClick={downloadCsv}
              disabled={data.length === 0}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              CSV 다운로드
            </button>
          </div>
        </CardHeader>
        <CardContent>
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
              <p>조회된 데이터가 없습니다</p>
            </div>
          ) : (
            <>
              <div className="border rounded-lg overflow-hidden dark:border-slate-700">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50 dark:bg-slate-800">
                      <TableHead className="font-semibold">센서 ID</TableHead>
                      <TableHead className="font-semibold">기록 시간</TableHead>
                      <TableHead className="font-semibold">라인</TableHead>
                      <TableHead className="font-semibold">센서 타입</TableHead>
                      <TableHead className="font-semibold text-right">값</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.map((item, index) => {
                      const Icon = sensorTypeIcons[item.sensor_type] || Activity;
                      return (
                        <TableRow
                          key={`${item.sensor_id}-${index}`}
                          className="hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        >
                          <TableCell className="font-mono text-sm">
                            {item.sensor_id}
                          </TableCell>
                          <TableCell className="text-sm">
                            {new Date(item.recorded_at).toLocaleString('ko-KR')}
                          </TableCell>
                          <TableCell>
                            <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded text-sm">
                              {item.line_code}
                            </span>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Icon className="w-4 h-4 text-slate-500" />
                              <span>{sensorTypeLabels[item.sensor_type] || item.sensor_type}</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            <span className="font-semibold">{item.value}</span>
                            {item.unit && (
                              <span className="text-slate-500 ml-1">{item.unit}</span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>

              {/* 페이지네이션 */}
              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-slate-500">
                  {((page - 1) * pageSize + 1).toLocaleString()} -{' '}
                  {Math.min(page * pageSize, total).toLocaleString()} / {total.toLocaleString()}건
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <span className="text-sm text-slate-600 dark:text-slate-400">
                    {page} / {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
