/**
 * RagDocumentsTab
 * RAG 지식 베이스 문서 관리 탭
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
  BookOpen,
  Search,
  RefreshCw,
  Trash2,
  FileText,
  Upload,
  Plus,
  X,
  Eye,
} from 'lucide-react';
import { FileUploadZone } from '@/components/ui/FileUploadZone';
import {
  ragService,
  type RagDocument,
  type SearchResult,
  type DocumentDetail,
} from '@/services/ragService';
import { useAuth } from '@/contexts/AuthContext';

// 문서 타입 한글 매핑
const documentTypeLabels: Record<string, string> = {
  MANUAL: '매뉴얼',
  PROCEDURE: '절차서',
  STANDARD: '표준',
  REPORT: '보고서',
  OTHER: '기타',
};

export function RagDocumentsTab() {
  const { accessToken: token } = useAuth();
  const toast = useToast();

  // 상태
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [showAddText, setShowAddText] = useState(false);

  // 검색
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);

  // 텍스트 문서 추가 폼
  const [newDocTitle, setNewDocTitle] = useState('');
  const [newDocContent, setNewDocContent] = useState('');
  const [newDocType, setNewDocType] = useState('MANUAL');
  const [adding, setAdding] = useState(false);

  // 문서 상세 보기
  const [selectedDocument, setSelectedDocument] = useState<DocumentDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // 문서 목록 로드
  const loadDocuments = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError(null);

    try {
      const response = await ragService.listDocuments({}, token);
      setDocuments(response.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : '문서 목록 로드 실패');
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  // 초기 로드
  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // 파일 업로드 핸들러
  const handleFileUpload = async (file: File) => {
    if (!token) {
      throw new Error('로그인이 필요합니다');
    }

    await ragService.uploadDocument(file, {}, token);
    await loadDocuments();
  };

  // 텍스트 문서 추가
  const handleAddDocument = async () => {
    if (!token || !newDocTitle.trim() || !newDocContent.trim()) return;

    setAdding(true);
    try {
      await ragService.addDocument(newDocTitle, newDocContent, newDocType, token);
      setNewDocTitle('');
      setNewDocContent('');
      setNewDocType('MANUAL');
      setShowAddText(false);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : '문서 추가 실패');
    } finally {
      setAdding(false);
    }
  };

  // 문서 삭제
  const handleDelete = async (documentId: string) => {
    if (!token) return;

    const confirmed = await toast.confirm({
      title: '문서 삭제',
      message: '이 문서를 삭제하시겠습니까?',
      confirmText: '삭제',
      cancelText: '취소',
      variant: 'danger',
    });
    if (!confirmed) return;

    try {
      await ragService.deleteDocument(documentId, token);
      toast.success('문서가 삭제되었습니다');
      await loadDocuments();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '문서 삭제 실패');
    }
  };

  // 검색 실행
  const handleSearch = async () => {
    if (!token || !searchQuery.trim()) return;

    setSearching(true);
    try {
      const response = await ragService.searchDocuments(
        { query: searchQuery, topK: 10 },
        token
      );
      setSearchResults(response.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : '검색 실패');
    } finally {
      setSearching(false);
    }
  };

  // 검색 결과 초기화
  const clearSearch = () => {
    setSearchQuery('');
    setSearchResults(null);
  };

  // 문서 상세 보기
  const handleViewDocument = async (documentId: string) => {
    if (!token) return;

    setLoadingDetail(true);
    try {
      const response = await ragService.getDocument(documentId, token);
      setSelectedDocument(response.document);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '문서 조회 실패');
    } finally {
      setLoadingDetail(false);
    }
  };

  // 문서 상세 모달 닫기
  const closeDocumentDetail = () => {
    setSelectedDocument(null);
  };

  return (
    <div className="space-y-6">
      {/* 문서 상세 모달 */}
      {selectedDocument && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-slate-900 rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] flex flex-col">
            {/* 모달 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                  {selectedDocument.title}
                </h2>
                <div className="flex items-center gap-4 mt-1 text-sm text-slate-500">
                  <span>청크: {selectedDocument.chunk_count}개</span>
                  <span>문자: {selectedDocument.char_count.toLocaleString()}자</span>
                  {selectedDocument.created_at && (
                    <span>
                      등록일: {new Date(selectedDocument.created_at).toLocaleDateString('ko-KR')}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={closeDocumentDetail}
                className="p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 모달 본문 */}
            <div className="flex-1 overflow-y-auto p-6">
              <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {selectedDocument.content}
              </pre>
            </div>

            {/* 모달 푸터 */}
            <div className="flex justify-end px-6 py-4 border-t border-slate-200 dark:border-slate-700">
              <button
                onClick={closeDocumentDetail}
                className="px-4 py-2 text-sm bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 로딩 오버레이 */}
      {loadingDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white dark:bg-slate-900 rounded-lg shadow-xl p-6">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">문서 로딩 중...</p>
          </div>
        </div>
      )}

      {/* 액션 버튼 */}
      <div className="flex justify-end gap-2">
        <button
          onClick={() => {
            setShowAddText(!showAddText);
            setShowUpload(false);
          }}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          {showAddText ? '닫기' : '텍스트 추가'}
        </button>
        <button
          onClick={() => {
            setShowUpload(!showUpload);
            setShowAddText(false);
          }}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-green-600 text-white hover:bg-green-700 rounded-lg transition-colors"
        >
          <Upload className="w-4 h-4" />
          {showUpload ? '닫기' : '파일 업로드'}
        </button>
      </div>

      {/* 파일 업로드 영역 */}
      {showUpload && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">문서 파일 업로드</CardTitle>
          </CardHeader>
          <CardContent>
            <FileUploadZone
              accept=".txt,.md,.pdf"
              onUpload={handleFileUpload}
              title="RAG 문서 업로드"
              description="텍스트, 마크다운, PDF 파일을 드래그하거나 클릭하여 선택하세요"
            />
          </CardContent>
        </Card>
      )}

      {/* 텍스트 문서 추가 폼 */}
      {showAddText && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">텍스트로 문서 추가</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  제목
                </label>
                <input
                  type="text"
                  value={newDocTitle}
                  onChange={(e) => setNewDocTitle(e.target.value)}
                  placeholder="문서 제목"
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  문서 유형
                </label>
                <select
                  value={newDocType}
                  onChange={(e) => setNewDocType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {Object.entries(documentTypeLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                내용
              </label>
              <textarea
                value={newDocContent}
                onChange={(e) => setNewDocContent(e.target.value)}
                placeholder="문서 내용을 입력하세요..."
                rows={6}
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              />
            </div>
            <div className="flex justify-end">
              <button
                onClick={handleAddDocument}
                disabled={adding || !newDocTitle.trim() || !newDocContent.trim()}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
              >
                {adding ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                문서 추가
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 검색 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Search className="w-5 h-5 text-slate-600 dark:text-slate-400" />
            <CardTitle className="text-base">문서 검색</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="검색어를 입력하세요..."
              className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              onClick={handleSearch}
              disabled={searching || !searchQuery.trim()}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {searching ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
              검색
            </button>
            {searchResults && (
              <button
                onClick={clearSearch}
                className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
                초기화
              </button>
            )}
          </div>

          {/* 검색 결과 */}
          {searchResults && (
            <div className="mt-4 space-y-3">
              <p className="text-sm text-slate-500">
                검색 결과: {searchResults.length}건
              </p>
              {searchResults.length === 0 ? (
                <p className="text-center py-4 text-slate-500">
                  검색 결과가 없습니다
                </p>
              ) : (
                <div className="space-y-2">
                  {searchResults.map((result) => (
                    <div
                      key={`${result.document_id}-${result.chunk_index}`}
                      className="p-4 border border-slate-200 dark:border-slate-700 rounded-lg"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-slate-700 dark:text-slate-300">
                          {result.title}
                        </span>
                        <span className="text-xs text-slate-500">
                          유사도: {(result.similarity * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-400 line-clamp-3">
                        {result.chunk_text}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 문서 목록 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-slate-600 dark:text-slate-400" />
              <CardTitle className="text-base">문서 목록</CardTitle>
              <span className="text-sm text-slate-500">
                ({documents.length}개)
              </span>
            </div>
            <button
              onClick={loadDocuments}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              새로고침
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="text-center py-8 text-red-500">
              <p>오류: {error}</p>
              <button
                onClick={loadDocuments}
                className="mt-2 text-sm text-blue-600 hover:underline"
              >
                다시 시도
              </button>
            </div>
          ) : loading && documents.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
              <p>문서 목록 로딩 중...</p>
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <BookOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>등록된 문서가 없습니다</p>
              <p className="text-sm mt-1">파일 업로드 또는 텍스트 추가로 문서를 등록하세요</p>
            </div>
          ) : (
            <div className="border rounded-lg overflow-hidden dark:border-slate-700">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50 dark:bg-slate-800">
                    <TableHead className="font-semibold">제목</TableHead>
                    <TableHead className="font-semibold">유형</TableHead>
                    <TableHead className="font-semibold">청크 수</TableHead>
                    <TableHead className="font-semibold">등록일</TableHead>
                    <TableHead className="font-semibold text-right">작업</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((doc) => (
                    <TableRow
                      key={doc.document_id}
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer"
                      onClick={() => handleViewDocument(doc.document_id)}
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-slate-400" />
                          <span className="font-medium text-blue-600 dark:text-blue-400 hover:underline">
                            {doc.title}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 rounded text-sm">
                          {documentTypeLabels[doc.document_type] || doc.document_type}
                        </span>
                      </TableCell>
                      <TableCell>{doc.chunk_count}</TableCell>
                      <TableCell className="text-sm text-slate-500">
                        {doc.created_at
                          ? new Date(doc.created_at).toLocaleDateString('ko-KR')
                          : '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleViewDocument(doc.document_id);
                            }}
                            className="p-1.5 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                            title="보기"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(doc.document_id);
                            }}
                            className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                            title="삭제"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </TableCell>
                    </TableRow>
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
