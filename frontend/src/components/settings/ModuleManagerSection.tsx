/**
 * Module Manager Section
 * Admin-only section for uploading, installing, and managing modules
 */
import React, { useState, useEffect } from 'react';
import { Upload, Loader2, CheckCircle, XCircle, RefreshCw, Trash2 } from 'lucide-react';
import { moduleService, ModuleInfo } from '../../services/moduleService';

export default function ModuleManagerSection() {
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  // Load modules on mount
  useEffect(() => {
    loadModules();
  }, []);

  const loadModules = async () => {
    setLoading(true);
    try {
      const moduleList = await moduleService.listModules();
      setModules(moduleList);
    } catch (error) {
      console.error('Failed to load modules:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const response = await moduleService.uploadModule(file, false);
      setUploadSuccess(`모듈 '${response.module_code}' v${response.version} 업로드 완료!`);

      // Reload modules after 2 seconds
      setTimeout(() => {
        loadModules();
        setUploadSuccess(null);
      }, 2000);

    } catch (error) {
      console.error('[MODULE UPLOAD] Error:', error);
      const message = error instanceof Error ? error.message : '업로드 실패';
      setUploadError(`업로드 실패: ${message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.zip')) {
      handleFileUpload(file);
    } else {
      setUploadError('ZIP 파일만 업로드 가능합니다');
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleUninstall = async (moduleCode: string, moduleName: string) => {
    if (!confirm(`정말로 '${moduleName}' 모듈을 제거하시겠습니까?\n\n모듈 코드: ${moduleCode}`)) {
      return;
    }

    try {
      await moduleService.uninstallModule(moduleCode, false);
      loadModules();
    } catch (error) {
      alert(`제거 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`);
    }
  };

  const handleToggle = async (moduleCode: string, currentState: boolean) => {
    try {
      await moduleService.toggleModule(moduleCode, !currentState);
      loadModules();
    } catch (error) {
      alert(`활성화 변경 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Zone */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50 mb-4">
          모듈 설치
        </h3>

        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            uploading
              ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20'
              : 'border-slate-300 dark:border-slate-600 hover:border-blue-400 dark:hover:border-blue-500'
          }`}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
        >
          {uploading ? (
            <>
              <Loader2 className="w-12 h-12 mx-auto mb-4 text-blue-600 animate-spin" />
              <p className="text-lg font-medium text-blue-700 dark:text-blue-300">
                업로드 중...
              </p>
            </>
          ) : (
            <>
              <Upload className="w-12 h-12 mx-auto mb-4 text-slate-400 dark:text-slate-500" />
              <p className="text-lg font-medium text-slate-700 dark:text-slate-300 mb-2">
                ZIP 파일을 드래그하여 업로드
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                또는 클릭하여 파일 선택
              </p>
              <input
                type="file"
                accept=".zip"
                onChange={handleFileSelect}
                className="hidden"
                id="module-upload"
                disabled={uploading}
              />
              <label
                htmlFor="module-upload"
                className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                파일 선택
              </label>
            </>
          )}
        </div>

        {/* Upload Status */}
        {uploadSuccess && (
          <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
            <p className="text-sm text-green-700 dark:text-green-300">{uploadSuccess}</p>
          </div>
        )}

        {uploadError && (
          <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-3">
            <XCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
            <p className="text-sm text-red-700 dark:text-red-300">{uploadError}</p>
          </div>
        )}

        <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
          ⚠️ 모듈 설치 후 백엔드와 프론트엔드 서버를 재시작해야 합니다.
        </p>
      </div>

      {/* Installed Modules List */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700">
        <div className="p-6 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
            설치된 모듈
          </h3>
          <button
            onClick={loadModules}
            disabled={loading}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 text-slate-600 dark:text-slate-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {loading ? (
          <div className="p-12 text-center">
            <Loader2 className="w-8 h-8 mx-auto text-blue-600 animate-spin" />
            <p className="mt-4 text-sm text-slate-500">로딩 중...</p>
          </div>
        ) : modules.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-slate-500 dark:text-slate-400">설치된 모듈이 없습니다</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="px-6 py-3 text-left text-sm font-medium text-slate-700 dark:text-slate-300">
                    모듈
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-slate-700 dark:text-slate-300">
                    버전
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-slate-700 dark:text-slate-300">
                    카테고리
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-slate-700 dark:text-slate-300">
                    작성자
                  </th>
                  <th className="px-6 py-3 text-center text-sm font-medium text-slate-700 dark:text-slate-300">
                    상태
                  </th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-slate-700 dark:text-slate-300">
                    작업
                  </th>
                </tr>
              </thead>
              <tbody>
                {modules.map((module) => (
                  <tr
                    key={module.module_code}
                    className="border-b border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-900/50"
                  >
                    <td className="px-6 py-4">
                      <div>
                        <div className="font-medium text-slate-900 dark:text-slate-50">
                          {module.name}
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                          {module.module_code}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-700 dark:text-slate-300">
                      {module.version}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        module.category === 'core' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300' :
                        module.category === 'feature' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                        module.category === 'industry' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                        'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300'
                      }`}>
                        {module.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-700 dark:text-slate-300">
                      {module.author || 'Unknown'}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <button
                        onClick={() => handleToggle(module.module_code, module.is_enabled)}
                        disabled={module.is_system}
                        className={`relative w-11 h-6 rounded-full transition-colors ${
                          module.is_enabled
                            ? 'bg-green-600'
                            : 'bg-slate-300 dark:bg-slate-600'
                        } ${module.is_system ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                        title={module.is_system ? 'Core modules cannot be disabled' : ''}
                      >
                        <div
                          className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                            module.is_enabled ? 'translate-x-6' : 'translate-x-1'
                          }`}
                        />
                      </button>
                    </td>
                    <td className="px-6 py-4 text-right">
                      {module.can_uninstall ? (
                        <button
                          onClick={() => handleUninstall(module.module_code, module.name)}
                          className="p-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                          title="모듈 제거"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
