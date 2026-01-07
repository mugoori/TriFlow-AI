# TriFlow AI Frontend

> Tauri v2 + React + TypeScript 기반 데스크톱 애플리케이션

## 기술 스택

- **Framework**: Tauri v2 (Rust) + React 18
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State**: React Context + Tanstack Query
- **Charts**: Recharts
- **Workflow**: React Flow

## 프로젝트 구조

```
frontend/
├── src/
│   ├── components/
│   │   ├── layout/       # Sidebar, Header 등
│   │   ├── pages/        # 페이지 컴포넌트
│   │   ├── workflow/     # 워크플로우 에디터
│   │   ├── ruleset/      # 룰셋 에디터
│   │   └── dashboard/    # 대시보드 위젯
│   ├── contexts/         # React Context
│   ├── hooks/            # Custom Hooks
│   ├── services/         # API 클라이언트
│   └── modules/          # 동적 모듈 임포트
├── src-tauri/            # Tauri (Rust) 설정
└── public/               # 정적 파일
```

## 시작하기

### 요구 사항

- Node.js 20+
- Rust (Tauri용)
- pnpm 또는 npm

### 설치 및 실행

```bash
# 의존성 설치
npm install

# 개발 서버 실행 (Tauri 앱)
npm run tauri dev

# 웹 개발 서버만 실행
npm run dev

# 프로덕션 빌드
npm run tauri build
```

## 주요 페이지

| 페이지 | 경로 | 설명 |
|--------|------|------|
| Dashboard | `/` | KPI 카드, 차트 |
| Chat | `/chat` | AI 채팅 인터페이스 |
| Workflows | `/workflows` | 워크플로우 빌더 |
| Rulesets | `/rulesets` | Rhai 룰셋 에디터 |
| Data | `/data` | 데이터 소스 관리 |
| Settings | `/settings` | 시스템 설정 |

## 개발 환경 설정

### 권장 IDE

- [VS Code](https://code.visualstudio.com/)
- [Tauri Extension](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode)
- [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)

### 환경 변수

`.env` 파일 생성:

```env
VITE_API_URL=http://localhost:8000
```

## 빌드

```bash
# Windows MSI/NSIS 빌드
npm run tauri build

# 모듈 레지스트리 재빌드
npm run build:modules
```
