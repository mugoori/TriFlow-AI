# TriFlow AI

> 제조 현장 데이터 기반 AI 의사결정 지원 플랫폼

## 개요

TriFlow AI는 제조 현장의 판단을 지능화하여 **데이터 기반 의사결정을 실시간으로 지원**하는 데스크톱 애플리케이션입니다.

### 핵심 기능

- **Hybrid Judgment Engine**: Rule + LLM 조합으로 정확하고 설명 가능한 판단
- **Workflow Automation**: JSON DSL 기반 다단계 워크플로우 자동 실행
- **Natural Language BI**: 자연어 질의를 SQL 및 차트로 변환
- **Learning Pipeline**: 피드백 기반 자동 Rule 추출 및 개선

## 기술 스택

| 영역 | 기술 |
|------|------|
| **Client** | Tauri v2 + React + TypeScript + Tailwind CSS |
| **Server** | Python 3.11 + FastAPI + Pydantic |
| **Database** | PostgreSQL 14+ (pgvector) + Redis 7.2 |
| **Rule Engine** | Rhai (Rust 기반) |
| **AI Model** | Anthropic Claude API |

## 프로젝트 구조

```
triflow-ai/
├── backend/          # Python FastAPI 백엔드
│   ├── agents/       # AI 에이전트 로직
│   ├── tools/        # 에이전트 도구 (rhai, db 등)
│   ├── prompts/      # 프롬프트 템플릿
│   └── api/          # API 엔드포인트
├── frontend/         # Tauri + React 프론트엔드
│   ├── src/          # React 소스
│   └── src-tauri/    # Tauri (Rust) 소스
└── docs/             # 프로젝트 문서
```

## 시작하기

### 요구 사항

- Node.js 20+
- Python 3.11+
- Rust (Tauri용)
- Docker & Docker Compose

### 설치

```bash
# 저장소 클론
git clone https://github.com/mugoori/TriFlow-AI.git
cd triflow-ai

# 백엔드 의존성 설치
cd backend
pip install -r requirements.txt

# 프론트엔드 의존성 설치
cd ../frontend
npm install
```

### 개발 서버 실행

```bash
# Docker로 DB 실행
docker-compose up -d

# 백엔드 실행
cd backend
uvicorn main:app --reload

# 프론트엔드 실행 (별도 터미널)
cd frontend
npm run tauri dev
```

## 라이선스

MIT License
