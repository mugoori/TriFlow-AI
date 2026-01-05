/**
 * RAG (지식 베이스) 서비스
 * 문서 업로드, 검색, 관리 API 클라이언트
 */

import { apiClient } from './api';

// ===========================================
// Types
// ===========================================

export interface RagDocument {
  document_id: string;
  title: string;
  document_type: string;
  source_url?: string;
  created_at?: string;
  chunk_count: number;
}

export interface DocumentUploadResult {
  success: boolean;
  document_id: string;
  chunks: number;
  title: string;
}

export interface SearchResult {
  document_id: string;
  title: string;
  document_type: string;
  chunk_text: string;
  chunk_index: number;
  similarity: number;
}

export interface SearchResponse {
  success: boolean;
  query: string;
  results: SearchResult[];
  count: number;
}

export interface DocumentListResponse {
  success: boolean;
  documents: RagDocument[];
  total: number;
}

export interface DocumentUploadOptions {
  title?: string;
  documentType?: string;
}

export interface ListDocumentsParams {
  documentType?: string;
  limit?: number;
  offset?: number;
}

export interface SearchParams {
  query: string;
  topK?: number;
  similarityThreshold?: number;
}

export interface DocumentDetail {
  document_id: string;
  title: string;
  source_type: string;
  source_id?: string;
  section?: string;
  content: string;
  chunk_count: number;
  chunk_total: number;
  char_count: number;
  created_at?: string;
  tags: string[];
}

export interface DocumentDetailResponse {
  success: boolean;
  document: DocumentDetail;
}

// ===========================================
// API Functions (using apiClient for automatic token handling)
// ===========================================

/**
 * 파일 업로드로 문서 추가
 */
export async function uploadDocument(
  file: File,
  options: DocumentUploadOptions = {}
): Promise<DocumentUploadResult> {
  const formData = new FormData();
  formData.append('file', file);

  if (options.title) {
    formData.append('title', options.title);
  }
  if (options.documentType) {
    formData.append('document_type', options.documentType);
  }

  return apiClient.postFormData<DocumentUploadResult>(
    '/api/v1/rag/documents/upload',
    formData
  );
}

/**
 * 텍스트로 문서 추가
 */
export async function addDocument(
  title: string,
  content: string,
  documentType: string = 'MANUAL'
): Promise<DocumentUploadResult> {
  return apiClient.post<DocumentUploadResult>('/api/v1/rag/documents', {
    title,
    content,
    document_type: documentType,
  });
}

/**
 * 문서 목록 조회
 */
export async function listDocuments(
  params: ListDocumentsParams = {}
): Promise<DocumentListResponse> {
  const searchParams = new URLSearchParams();

  if (params.documentType) {
    searchParams.append('document_type', params.documentType);
  }
  if (params.limit) {
    searchParams.append('limit', params.limit.toString());
  }
  if (params.offset) {
    searchParams.append('offset', params.offset.toString());
  }

  const query = searchParams.toString();
  const endpoint = `/api/v1/rag/documents${query ? `?${query}` : ''}`;

  return apiClient.get<DocumentListResponse>(endpoint);
}

/**
 * 문서 삭제
 */
export async function deleteDocument(
  documentId: string
): Promise<{ success: boolean; message: string }> {
  return apiClient.delete<{ success: boolean; message: string }>(
    `/api/v1/rag/documents/${documentId}`
  );
}

/**
 * 문서 검색
 */
export async function searchDocuments(
  params: SearchParams
): Promise<SearchResponse> {
  return apiClient.post<SearchResponse>('/api/v1/rag/search', {
    query: params.query,
    top_k: params.topK || 5,
    similarity_threshold: params.similarityThreshold || 0.5,
  });
}

/**
 * 문서 상세 조회
 */
export async function getDocument(
  documentId: string
): Promise<DocumentDetailResponse> {
  return apiClient.get<DocumentDetailResponse>(
    `/api/v1/rag/documents/${documentId}`
  );
}

// ===========================================
// Convenience Object Export
// ===========================================

export const ragService = {
  uploadDocument,
  addDocument,
  listDocuments,
  deleteDocument,
  searchDocuments,
  getDocument,
};

export default ragService;
