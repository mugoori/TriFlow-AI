# C-2. Coding Standard & Repo Guide

## 1. 언어별 코딩 컨벤션
- **TypeScript/Node**: ESLint+Prettier, strict TS, async/await, DI(선택)
- **Python(FastAPI)**: Ruff/Black, mypy(strict optional), Pydantic v2 모델
- **SQL**: 파일/마이그레이션 템플릿 관리, snake_case 테이블/컬럼, PK/FK 명시, COMMENT 필수
- **Markdown**: 헤더 표준화, TOC 자동화(필요 시), 코드블록 info string

## 2. 폴더/모듈 구조 예시
```
repo/
  services/
    api-gateway/
    chat/
    intent-router/
    workflow/
    judgment/
    bi/
    learning/
    mcp-hub/
  libs/
    common-types/
    tracing/
    cache/
  infra/
    k8s/
    terraform/
  data/
    migrations/
    seeds/
  docs/
    A-1_...md 등
```
- 서비스 단위 독립 배포 가능하게 설계, 공통 라이브러리 분리

## 3. 브랜치 전략
- 기본: **Trunk-based** + `feature/*` 단기 브랜치
- 릴리즈 태그: `v0.1.0` (MVP), `v1.0.0`(PoC), hotfix는 `hotfix/*`
- PR 필수 리뷰 1인 이상, CI 통과 조건: lint+test+build

## 4. 커밋 메시지 규칙
- 형식: `type(scope): message`
- type: feat, fix, chore, docs, refactor, test, perf, ci
- 예: `feat(judgment): add hybrid policy weighting`

## 5. 코드 리뷰 정책
- 최소 1명(핵심 모듈은 2명) 승인
- 리뷰 체크리스트: 기능 명세 준수, 오류/에러 핸들링, 로깅/추적, 보안/PII, 성능 영향, 테스트 포함 여부
- 큰 PR(>400loc) 지양, 기능 단위 쪼개기

## 6. 품질 자동화
- CI: lint/test/typecheck/build, SCA(취약점), 라이선스 스캔
- CD: staging → prod 승인 게이트, canary/blue-green(선택)
- Pre-commit 훅: lint/format/typecheck fast path

## 7. 문서/스키마 싱크
- OpenAPI/Proto → 코드/클라이언트 SDK 자동 생성(선택)
- DB 마이그레이션 툴(Prisma/Flyway/Alembic) 사용, 마이그레이션 리뷰 필수
- Prompt/Rule/DSL 버전은 repo 내 템플릿 디렉토리에 관리하고 배포 시 버전 태깅
