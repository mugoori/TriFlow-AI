# TriFlow AI

> 제조 현장 데이터 기반 AI 의사결정 지원 플랫폼

## 개요

TriFlow AI는 제조 현장의 판단을 지능화하여 **데이터 기반 의사결정을 실시간으로 지원**하는 데스크톱 애플리케이션입니다.

### 핵심 기능

- **Hybrid Judgment Engine**: Rule + LLM 조합으로 정확하고 설명 가능한 판단
- **Workflow Automation**: JSON DSL 기반 다단계 워크플로우 자동 실행
- **Natural Language BI**: 자연어 질의를 SQL 및 차트로 변환
- **Learning Pipeline**: 피드백 기반 자동 Rule 추출 및 개선
- **Multi-Tenant Module**: 산업별 커스터마이징 (제약, 식품, 전자 등)

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
├── backend/              # Python FastAPI 백엔드
│   ├── app/
│   │   ├── agents/       # AI 에이전트 (5개)
│   │   ├── services/     # 비즈니스 로직
│   │   ├── routers/      # API 엔드포인트
│   │   └── prompts/      # 프롬프트 템플릿
│   └── alembic/          # DB 마이그레이션
├── frontend/             # Tauri + React 프론트엔드
│   ├── src/
│   │   ├── components/   # React 컴포넌트
│   │   └── services/     # API 클라이언트
│   └── src-tauri/        # Tauri (Rust)
├── modules/              # 플러그인 모듈
└── docs/                 # 문서
```

## 시작하기 전에

### 필수 요구사항

- **Docker Desktop 4.20+** (Windows/Mac) 또는 **Docker Engine 24+** (Linux)
- **Git 2.30+**
- (선택) Node.js 20+ / Python 3.11+ (로컬 개발 시)

### 시스템 요구사항

- **RAM**: 최소 8GB (권장 16GB)
- **Disk**: 10GB 여유 공간
- **포트**: 5432, 6379, 8000, 9000, 9090, 3001 사용 가능

---

## ⚡ 5분 Quick Start

### 1. 저장소 클론 및 환경 설정

```bash
git clone https://github.com/mugoori/TriFlow-AI.git
cd triflow-ai
cp .env.example backend/.env
```

### 2. Anthropic API 키 설정

1. https://console.anthropic.com 에서 API 키 발급
2. `backend/.env` 파일 열기
3. `ANTHROPIC_API_KEY=sk-ant-...` 값 입력

### 3. Docker로 전체 시스템 실행

```bash
docker-compose up -d
```

### 4. 서비스 상태 확인 (2분 대기)

```bash
docker-compose ps          # 모든 서비스 "healthy" 확인
docker-compose logs -f --tail=20  # 로그 실시간 확인 (Ctrl+C로 종료)
```

### 5. 접속

- **Backend API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **Grafana**: http://localhost:3001 (admin / triflow_grafana_password)
- **Prometheus**: http://localhost:9090

**첫 로그인**:
- Username: `admin`
- Password: `admin123!` (초기 비밀번호)

---

## 🔧 자주 발생하는 문제

### "Port already in use" 오류

```bash
# 사용 중인 포트 확인
docker ps
netstat -ano | findstr :5432  # Windows
lsof -i :5432                  # Mac/Linux

# 충돌하는 컨테이너 중지
docker stop <container-name>
```

### "Cannot connect to database" 오류

```bash
# 서비스 건강 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs postgres

# 재시작
docker-compose restart postgres
```

### 전체 리셋 (데이터 삭제 주의!)

```bash
docker-compose down -v  # 볼륨 포함 삭제
docker-compose up -d    # 재시작
```

---

## 📚 더 알아보기

### 로컬 개발 (Docker 없이)

자세한 가이드: [docs/guides/LOCAL_DEVELOPMENT.md](docs/guides/LOCAL_DEVELOPMENT.md)

### 프로덕션 배포

자세한 가이드: [docs/guides/DEPLOYMENT.md](docs/guides/DEPLOYMENT.md)

### 문제 해결

자세한 가이드: [docs/guides/TROUBLESHOOTING.md](docs/guides/TROUBLESHOOTING.md)

### Windows 사용자

자세한 가이드: [docs/guides/WINDOWS_SETUP.md](docs/guides/WINDOWS_SETUP.md)

## 문서

### 빠른 링크

| 문서 | 설명 |
|------|------|
| [프로젝트 현황](docs/project/PROJECT_STATUS.md) | Executive Summary |
| [개발 우선순위](docs/specs/implementation/DEVELOPMENT_PRIORITY_GUIDE.md) | ROI 기반 개발 가이드 |
| [스펙 리뷰 요약](docs/spec-reviews/00_SUMMARY_REPORT.md) | 구현률 75% 분석 |

### 문서 구조

```
docs/
├── README.md                 # 문서 네비게이션
├── project/                  # 프로젝트 관리 문서
├── specs/                    # 기술 스펙 문서
│   ├── A-requirements/       # 요구사항/기획
│   ├── B-design/             # 설계
│   ├── C-development/        # 개발/테스트
│   ├── D-operations/         # 운영
│   ├── E-advanced/           # 고급 기능
│   └── implementation/       # 구현 계획
├── spec-reviews/             # 스펙 검토 (36개)
├── guides/                   # 운영 가이드
└── archive/                  # 아카이브
```

자세한 문서 목록은 [docs/README.md](docs/README.md)를 참조하세요.

## 개발 가이드

- [AI_GUIDELINES.md](AI_GUIDELINES.md) - AI 개발 규칙 및 제약조건
- [modules/README.md](modules/README.md) - 플러그인 모듈 개발 가이드
- [docs/guides/TESTING.md](docs/guides/TESTING.md) - 테스트 가이드
- [docs/guides/DEPLOYMENT.md](docs/guides/DEPLOYMENT.md) - 배포 가이드

## 라이선스

MIT License
