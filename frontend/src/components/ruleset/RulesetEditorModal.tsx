/**
 * RulesetEditorModal
 * Rhai 스크립트 편집기 모달
 * - Monaco Editor 기반 코드 편집
 * - Rhai 구문 하이라이팅 (Rust-like)
 * - 샘플 스크립트 선택
 * - 테스트 실행 기능
 */

import { useEffect, useState, useCallback } from 'react';
import Editor, { OnMount } from '@monaco-editor/react';
import {
  X,
  Save,
  Play,
  FileCode,
  ChevronDown,
  CheckCircle,
  AlertCircle,
  Loader2,
  Clipboard,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { rulesetService, type Ruleset, type SampleScript, type RulesetExecuteResponse } from '@/services/rulesetService';

interface RulesetEditorModalProps {
  ruleset: Ruleset | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (ruleset: Ruleset) => void;
  mode: 'create' | 'edit';
}

// Rhai 키워드 (Monaco에서 Rust로 하이라이팅)
const RHAI_KEYWORDS = [
  'let', 'const', 'if', 'else', 'while', 'loop', 'for', 'in',
  'break', 'continue', 'return', 'throw', 'try', 'catch',
  'fn', 'private', 'import', 'export', 'as', 'true', 'false',
  'null', 'this', 'print', 'debug', 'type_of', 'is_def_var',
];

// 기본 Rhai 템플릿
const DEFAULT_RHAI_SCRIPT = `// 새로운 Rhai 규칙 스크립트
// input 객체를 통해 입력 데이터에 접근합니다

let threshold = 50.0;
let value = input.value;

if value > threshold {
    #{
        "result": "alert",
        "message": "값이 임계값을 초과했습니다",
        "value": value,
        "threshold": threshold
    }
} else {
    #{
        "result": "normal",
        "message": "값이 정상 범위입니다",
        "value": value,
        "threshold": threshold
    }
}
`;

export function RulesetEditorModal({
  ruleset,
  isOpen,
  onClose,
  onSave,
  mode,
}: RulesetEditorModalProps) {
  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [script, setScript] = useState(DEFAULT_RHAI_SCRIPT);

  // UI state
  const [samples, setSamples] = useState<SampleScript[]>([]);
  const [showSamples, setShowSamples] = useState(false);
  const [saving, setSaving] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Test execution state
  const [testInput, setTestInput] = useState('{"value": 75}');
  const [testResult, setTestResult] = useState<RulesetExecuteResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  // Load ruleset data for edit mode
  useEffect(() => {
    if (isOpen && mode === 'edit' && ruleset) {
      setName(ruleset.name);
      setDescription(ruleset.description || '');
      setScript(ruleset.rhai_script);
    } else if (isOpen && mode === 'create') {
      setName('');
      setDescription('');
      setScript(DEFAULT_RHAI_SCRIPT);
    }
    setError(null);
    setTestResult(null);
    setTestError(null);
  }, [isOpen, mode, ruleset]);

  // Load sample scripts
  useEffect(() => {
    if (isOpen) {
      loadSamples();
    }
  }, [isOpen]);

  const loadSamples = async () => {
    try {
      const response = await rulesetService.getSamples();
      setSamples(response.samples);
    } catch (err) {
      console.error('Failed to load sample scripts:', err);
    }
  };

  // Monaco Editor 설정
  const handleEditorMount: OnMount = useCallback((editor, monaco) => {
    // Rhai를 위한 커스텀 토큰 규칙 (Rust 기반)
    monaco.languages.register({ id: 'rhai' });

    monaco.languages.setMonarchTokensProvider('rhai', {
      keywords: RHAI_KEYWORDS,
      operators: [
        '=', '>', '<', '!', '~', '?', ':', '==', '<=', '>=', '!=',
        '&&', '||', '++', '--', '+', '-', '*', '/', '&', '|', '^', '%',
        '<<', '>>', '>>>', '+=', '-=', '*=', '/=', '&=', '|=', '^=',
        '%=', '<<=', '>>=', '>>>=',
      ],
      symbols: /[=><!~?:&|+\-*\/\^%]+/,
      escapes: /\\(?:[abfnrtv\\"']|x[0-9A-Fa-f]{1,4}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8})/,
      tokenizer: {
        root: [
          // Comments
          [/\/\/.*$/, 'comment'],
          [/\/\*/, 'comment', '@comment'],

          // Identifiers and keywords
          [/[a-z_$][\w$]*/, {
            cases: {
              '@keywords': 'keyword',
              '@default': 'identifier'
            }
          }],

          // Numbers
          [/\d*\.\d+([eE][\-+]?\d+)?/, 'number.float'],
          [/0[xX][0-9a-fA-F]+/, 'number.hex'],
          [/\d+/, 'number'],

          // Strings
          [/"([^"\\]|\\.)*$/, 'string.invalid'],
          [/"/, 'string', '@string'],

          // Map/Object literal
          [/#\{/, 'delimiter.bracket', '@map'],

          // Delimiters
          [/[{}()\[\]]/, '@brackets'],
          [/[<>](?!@symbols)/, '@brackets'],
          [/@symbols/, {
            cases: {
              '@operators': 'operator',
              '@default': ''
            }
          }],

          // Delimiter
          [/[;,.]/, 'delimiter'],

          // Whitespace
          { include: '@whitespace' },
        ],
        comment: [
          [/[^\/*]+/, 'comment'],
          [/\/\*/, 'comment', '@push'],
          [/\*\//, 'comment', '@pop'],
          [/[\/*]/, 'comment'],
        ],
        string: [
          [/[^\\"]+/, 'string'],
          [/@escapes/, 'string.escape'],
          [/\\./, 'string.escape.invalid'],
          [/"/, 'string', '@pop'],
        ],
        map: [
          [/[^}]+/, 'string.key'],
          [/}/, 'delimiter.bracket', '@pop'],
        ],
        whitespace: [
          [/[ \t\r\n]+/, 'white'],
        ],
      },
    });

    // 자동완성 설정
    monaco.languages.registerCompletionItemProvider('rhai', {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      provideCompletionItems: (model: any, position: any) => {
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };

        const suggestions = [
          ...RHAI_KEYWORDS.map((kw) => ({
            label: kw,
            kind: monaco.languages.CompletionItemKind.Keyword,
            insertText: kw,
            range,
          })),
          {
            label: 'input',
            kind: monaco.languages.CompletionItemKind.Variable,
            insertText: 'input',
            detail: '입력 데이터 객체',
            range,
          },
          {
            label: 'input.temperature',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'input.temperature',
            detail: '온도 센서 값',
            range,
          },
          {
            label: 'input.pressure',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'input.pressure',
            detail: '압력 센서 값',
            range,
          },
          {
            label: 'input.humidity',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'input.humidity',
            detail: '습도 센서 값',
            range,
          },
          {
            label: 'input.defect_rate',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'input.defect_rate',
            detail: '불량률 (%)',
            range,
          },
        ];

        return { suggestions };
      },
    });

    // 에디터 포커스
    editor.focus();
  }, []);

  // 저장 처리
  const handleSave = async () => {
    if (!name.trim()) {
      setError('룰셋 이름을 입력해주세요.');
      return;
    }
    if (!script.trim()) {
      setError('Rhai 스크립트를 입력해주세요.');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      let savedRuleset: Ruleset;

      if (mode === 'create') {
        savedRuleset = await rulesetService.create({
          name: name.trim(),
          description: description.trim() || undefined,
          rhai_script: script,
        });
      } else if (ruleset) {
        savedRuleset = await rulesetService.update(ruleset.ruleset_id, {
          name: name.trim(),
          description: description.trim() || undefined,
          rhai_script: script,
        });
      } else {
        throw new Error('Invalid mode');
      }

      onSave(savedRuleset);
      onClose();
    } catch (err) {
      console.error('Failed to save ruleset:', err);
      setError('룰셋 저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  // 테스트 실행
  const handleTestExecute = async () => {
    if (mode === 'create' || !ruleset) {
      setTestError('테스트를 실행하려면 먼저 룰셋을 저장해주세요.');
      return;
    }

    let inputData: Record<string, unknown>;
    try {
      inputData = JSON.parse(testInput);
    } catch {
      setTestError('유효하지 않은 JSON 형식입니다.');
      return;
    }

    setExecuting(true);
    setTestError(null);
    setTestResult(null);

    try {
      const result = await rulesetService.execute(ruleset.ruleset_id, { input_data: inputData });
      setTestResult(result);
    } catch (err) {
      console.error('Failed to execute ruleset:', err);
      setTestError('룰셋 실행에 실패했습니다.');
    } finally {
      setExecuting(false);
    }
  };

  // 샘플 스크립트 적용
  const applySample = (sample: SampleScript) => {
    setScript(sample.script);
    if (!name) {
      setName(sample.name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
    }
    setShowSamples(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-6xl h-[90vh] mx-4 bg-white dark:bg-slate-900 rounded-xl shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
              <FileCode className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                {mode === 'create' ? '새 룰셋 생성' : '룰셋 편집'}
              </h2>
              <span className="text-sm text-slate-500 dark:text-slate-400">
                Rhai 스크립트 편집기
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel - Editor */}
          <div className="flex-1 flex flex-col border-r border-slate-200 dark:border-slate-700">
            {/* Form Fields */}
            <div className="p-4 space-y-3 border-b border-slate-200 dark:border-slate-700">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    룰셋 이름 *
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="예: 온도 임계값 체크"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    설명
                  </label>
                  <input
                    type="text"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="예: 온도가 70도 초과 시 알림"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                  />
                </div>
              </div>

              {/* Sample Scripts Dropdown */}
              <div className="relative">
                <button
                  onClick={() => setShowSamples(!showSamples)}
                  className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                >
                  <Clipboard className="w-4 h-4" />
                  샘플 스크립트
                  <ChevronDown className={`w-4 h-4 transition-transform ${showSamples ? 'rotate-180' : ''}`} />
                </button>
                {showSamples && (
                  <div className="absolute top-full left-0 mt-1 w-64 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 z-10">
                    {samples.map((sample) => (
                      <button
                        key={sample.name}
                        onClick={() => applySample(sample)}
                        className="w-full px-4 py-2 text-left hover:bg-slate-100 dark:hover:bg-slate-700 first:rounded-t-lg last:rounded-b-lg"
                      >
                        <div className="font-medium text-slate-900 dark:text-white">
                          {sample.name.replace(/_/g, ' ')}
                        </div>
                        <div className="text-sm text-slate-500 dark:text-slate-400 truncate">
                          {sample.description}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Monaco Editor */}
            <div className="flex-1">
              <Editor
                height="100%"
                defaultLanguage="rhai"
                language="rhai"
                value={script}
                onChange={(value) => setScript(value || '')}
                onMount={handleEditorMount}
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  fontSize: 14,
                  fontFamily: 'JetBrains Mono, Fira Code, monospace',
                  lineNumbers: 'on',
                  tabSize: 4,
                  insertSpaces: true,
                  automaticLayout: true,
                  scrollBeyondLastLine: false,
                  wordWrap: 'on',
                  padding: { top: 16 },
                }}
              />
            </div>
          </div>

          {/* Right Panel - Test */}
          <div className="w-96 flex flex-col">
            <div className="p-4 border-b border-slate-200 dark:border-slate-700">
              <h3 className="font-medium text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                <Play className="w-4 h-4" />
                테스트 실행
              </h3>

              <div className="space-y-3">
                <div>
                  <label className="block text-sm text-slate-600 dark:text-slate-400 mb-1">
                    입력 데이터 (JSON)
                  </label>
                  <textarea
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    placeholder='{"temperature": 75}'
                    className="w-full h-24 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-mono text-sm focus:ring-2 focus:ring-amber-500 focus:border-transparent resize-none"
                  />
                </div>

                <button
                  onClick={handleTestExecute}
                  disabled={executing || mode === 'create'}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {executing ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  테스트 실행
                </button>

                {mode === 'create' && (
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    * 테스트를 실행하려면 먼저 룰셋을 저장하세요.
                  </p>
                )}
              </div>
            </div>

            {/* Test Result */}
            <div className="flex-1 overflow-auto p-4">
              {testError && (
                <Card className="border-red-200 dark:border-red-800">
                  <CardContent className="py-3">
                    <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
                      <AlertCircle className="w-4 h-4" />
                      <span className="text-sm">{testError}</span>
                    </div>
                  </CardContent>
                </Card>
              )}

              {testResult && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      실행 결과
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="text-slate-500 dark:text-slate-400">실행 ID</div>
                      <div className="font-mono text-xs truncate">{testResult.execution_id.slice(0, 8)}...</div>
                      <div className="text-slate-500 dark:text-slate-400">실행 시간</div>
                      <div>{testResult.execution_time_ms}ms</div>
                      <div className="text-slate-500 dark:text-slate-400">신뢰도</div>
                      <div>{testResult.confidence_score ? `${(testResult.confidence_score * 100).toFixed(0)}%` : '-'}</div>
                    </div>

                    <div>
                      <div className="text-sm text-slate-500 dark:text-slate-400 mb-1">출력 데이터</div>
                      <pre className="text-xs font-mono bg-slate-100 dark:bg-slate-800 p-2 rounded overflow-auto max-h-48">
                        {JSON.stringify(testResult.output_data, null, 2)}
                      </pre>
                    </div>
                  </CardContent>
                </Card>
              )}

              {!testError && !testResult && (
                <div className="h-full flex items-center justify-center text-slate-400 dark:text-slate-500">
                  <div className="text-center">
                    <Play className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">테스트를 실행하면 결과가 여기에 표시됩니다</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        {error && (
          <div className="px-4 py-2 bg-red-50 dark:bg-red-900/30 border-t border-red-200 dark:border-red-800">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}
        <div className="flex justify-end gap-2 p-4 border-t border-slate-200 dark:border-slate-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 disabled:opacity-50 transition-colors"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {mode === 'create' ? '생성' : '저장'}
          </button>
        </div>
      </div>
    </div>
  );
}
