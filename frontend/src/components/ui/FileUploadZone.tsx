/**
 * FileUploadZone
 * 드래그앤드롭 파일 업로드 컴포넌트
 */

import { useState, useRef, useCallback } from 'react';
import { Upload, File, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

interface FileUploadZoneProps {
  accept: string; // ".txt,.md,.pdf" 또는 ".csv,.xlsx,.xls"
  onUpload: (file: File) => Promise<void>;
  maxSize?: number; // 바이트 단위 (기본 50MB)
  multiple?: boolean;
  disabled?: boolean;
  title?: string;
  description?: string;
}

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

interface FileState {
  file: File;
  status: UploadStatus;
  error?: string;
}

export function FileUploadZone({
  accept,
  onUpload,
  maxSize = 50 * 1024 * 1024, // 50MB
  multiple = false,
  disabled = false,
  title = '파일 업로드',
  description,
}: FileUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<FileState[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  // 파일 확장자 검증
  const validateFile = useCallback(
    (file: File): string | null => {
      const extensions = accept.split(',').map((ext) => ext.trim().toLowerCase());
      const fileExt = '.' + file.name.split('.').pop()?.toLowerCase();

      if (!extensions.includes(fileExt)) {
        return `지원하지 않는 형식입니다. (${accept})`;
      }

      if (file.size > maxSize) {
        const maxMB = Math.round(maxSize / (1024 * 1024));
        return `파일 크기가 ${maxMB}MB를 초과합니다.`;
      }

      return null;
    },
    [accept, maxSize]
  );

  // 파일 처리
  const handleFiles = useCallback(
    async (selectedFiles: FileList | null) => {
      if (!selectedFiles || selectedFiles.length === 0) return;

      const fileArray = Array.from(selectedFiles);
      const filesToProcess = multiple ? fileArray : [fileArray[0]];

      for (const file of filesToProcess) {
        const error = validateFile(file);

        if (error) {
          setFiles((prev) => [...prev, { file, status: 'error', error }]);
          continue;
        }

        // 업로드 시작
        setFiles((prev) => [...prev, { file, status: 'uploading' }]);

        try {
          await onUpload(file);
          setFiles((prev) =>
            prev.map((f) => (f.file === file ? { ...f, status: 'success' } : f))
          );
        } catch (err) {
          setFiles((prev) =>
            prev.map((f) =>
              f.file === file
                ? { ...f, status: 'error', error: err instanceof Error ? err.message : '업로드 실패' }
                : f
            )
          );
        }
      }
    },
    [multiple, onUpload, validateFile]
  );

  // 드래그 이벤트
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (!disabled) handleFiles(e.dataTransfer.files);
  };

  // 클릭으로 파일 선택
  const handleClick = () => {
    if (!disabled) inputRef.current?.click();
  };

  // 파일 제거
  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // 파일 목록 초기화
  const clearFiles = () => {
    setFiles([]);
  };

  // 지원 형식 표시
  const formatAccept = accept
    .split(',')
    .map((ext) => ext.trim().toUpperCase().replace('.', ''))
    .join(', ');

  return (
    <div className="space-y-4">
      {/* 업로드 영역 */}
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-all duration-200
          ${isDragging ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-slate-300 dark:border-slate-600'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-blue-400 hover:bg-slate-50 dark:hover:bg-slate-800/50'}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={(e) => handleFiles(e.target.files)}
          className="hidden"
          disabled={disabled}
        />

        <Upload
          className={`w-12 h-12 mx-auto mb-4 ${isDragging ? 'text-blue-500' : 'text-slate-400'}`}
        />

        <p className="text-lg font-medium text-slate-700 dark:text-slate-200">{title}</p>

        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {description || '파일을 드래그하거나 클릭하여 선택하세요'}
        </p>

        <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
          지원 형식: {formatAccept} (최대 {Math.round(maxSize / (1024 * 1024))}MB)
        </p>
      </div>

      {/* 파일 목록 */}
      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
              업로드된 파일 ({files.length})
            </span>
            <button
              onClick={clearFiles}
              className="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            >
              모두 지우기
            </button>
          </div>

          <div className="space-y-2">
            {files.map((fileState, index) => (
              <div
                key={`${fileState.file.name}-${index}`}
                className={`
                  flex items-center gap-3 p-3 rounded-lg border
                  ${fileState.status === 'error' ? 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20' : ''}
                  ${fileState.status === 'success' ? 'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20' : ''}
                  ${fileState.status === 'uploading' ? 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20' : ''}
                  ${fileState.status === 'idle' ? 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800' : ''}
                `}
              >
                {/* 아이콘 */}
                {fileState.status === 'uploading' && (
                  <Loader2 className="w-5 h-5 text-blue-500 animate-spin flex-shrink-0" />
                )}
                {fileState.status === 'success' && (
                  <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                )}
                {fileState.status === 'error' && (
                  <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                )}
                {fileState.status === 'idle' && (
                  <File className="w-5 h-5 text-slate-400 flex-shrink-0" />
                )}

                {/* 파일 정보 */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">
                    {fileState.file.name}
                  </p>
                  <p className="text-xs text-slate-500">
                    {fileState.error || `${(fileState.file.size / 1024).toFixed(1)} KB`}
                  </p>
                </div>

                {/* 삭제 버튼 */}
                <button
                  onClick={() => removeFile(index)}
                  className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
