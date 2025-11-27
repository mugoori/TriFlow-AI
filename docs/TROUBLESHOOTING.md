# TriFlow AI - Troubleshooting Log

> **목적**: 반복적인 에러 수정 시도(Loop)를 방지하고 효율적인 문제 해결을 위한 이력 관리
> **규칙**: AI_GUIDELINES.md의 Rule 9 (Anti-Loop & Troubleshooting Protocol) 준수

---

## 📋 Log Entry Template

각 에러 발생 시 아래 양식으로 기록:

```markdown
### [날짜] 에러 제목
- **에러 메시지**: `오류 메시지 요약`
- **발생 위치**: 파일명:라인번호 또는 컴포넌트명
- **시도한 해결책**:
  1. 첫 번째 시도 (결과: 성공/실패)
  2. 두 번째 시도 (결과: 성공/실패)
- **근본 원인 (RCA)**: 에러의 실제 원인
- **최종 해결책**: 성공한 방법 또는 미해결 상태
- **참고 링크**: 관련 이슈, 문서, Stack Overflow 등
```

---

## 🔍 Troubleshooting History

### [2025-11-27] 초기 파일 생성
- **목적**: Rule 9 적용을 위한 트러블슈팅 로그 파일 생성
- **상태**: 정상 운영 시작
- **비고**: 이후 에러 발생 시 본 파일에 기록

---

## 📚 Common Issues & Solutions

### 카테고리별 자주 발생하는 에러와 해결책

#### 🐍 Backend (Python/FastAPI)
- 아직 기록된 이슈 없음

#### 🎨 Frontend (Tauri/React)

**[2025-11-27] Tauri 빌드 시 TypeScript 컴파일 오류**
- **에러**: `Cannot find module '@/components/ui/alert'`, `Cannot find module '@/components/ui/table'`
- **해결책**: shadcn/ui의 alert.tsx, table.tsx 컴포넌트 수동 생성
- **RCA**: 차트 컴포넌트에서 아직 설치되지 않은 UI 컴포넌트를 참조

**[2025-11-27] PieChartComponent 타입 오류**
- **에러**: `Type '(entry: Record<string, unknown>) => string' is not assignable to type 'PieLabel'`
- **해결책**: `PieLabelRenderProps` 타입 import 후 props.name, props.value 사용
- **RCA**: Recharts의 label prop은 특정 타입의 함수만 허용

**[2025-11-27] Tauri config 오류**
- **에러**: `dangerousRemoteDomainIpcAccess was unexpected`
- **해결책**: tauri.conf.json에서 deprecated된 `dangerousRemoteDomainIpcAccess` 속성 제거
- **RCA**: Tauri v2에서 해당 속성이 더 이상 지원되지 않음

#### 🐳 Docker/Infrastructure
- 아직 기록된 이슈 없음

#### 🔄 CI/CD
- 아직 기록된 이슈 없음

---

## 🚫 Known Anti-Patterns (반복 금지)

이 섹션에는 **2회 이상 실패한 해결책**을 기록하여 재시도를 방지합니다.

- 아직 기록된 항목 없음

---

## 📝 Notes

- 에러 수정 전에 반드시 이 파일을 먼저 확인할 것
- 동일 에러가 2회 실패 시 즉시 작업 중단 후 사용자에게 보고
- 성공한 해결책은 "Common Issues & Solutions" 섹션에 정리
