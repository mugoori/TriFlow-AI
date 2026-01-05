# TriFlow AI Modules

이 디렉토리는 TriFlow AI의 플러그인 모듈을 포함합니다.

## 모듈 구조

```
modules/
├── module-schema.json     # 매니페스트 JSON 스키마
├── _registry.json         # 자동 생성되는 모듈 레지스트리
├── chat/                  # 예시: Chat 모듈
│   ├── manifest.json      # 모듈 매니페스트
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── router.py      # FastAPI 라우터
│   │   └── service.py     # 비즈니스 로직
│   └── frontend/
│       ├── ChatPage.tsx   # 메인 페이지 컴포넌트
│       └── components/    # 모듈별 컴포넌트
└── ...
```

## 새 모듈 생성

### CLI 도구 사용 (권장)

```bash
python scripts/create_module.py <module_code> --name "모듈 이름" --category feature
```

예시:
```bash
python scripts/create_module.py quality_analytics --name "품질 분석" --category feature
```

### 수동 생성

1. `modules/<module_code>/` 디렉토리 생성
2. `manifest.json` 작성 (module-schema.json 참조)
3. Backend: `backend/router.py` 생성
4. Frontend: `frontend/<ModuleName>Page.tsx` 생성
5. 레지스트리 재생성: `python scripts/build_module_registry.py`

## manifest.json 예시

```json
{
  "$schema": "../module-schema.json",
  "module_code": "quality_analytics",
  "version": "1.0.0",
  "name": "품질 분석",
  "description": "제품 품질 분석 및 리포팅",
  "category": "feature",
  "icon": "BarChart",
  "default_enabled": false,
  "requires_subscription": "standard",
  "depends_on": ["data"],
  "display_order": 50,
  "backend": {
    "router_path": "modules.quality_analytics.backend.router",
    "api_prefix": "/api/v1/quality",
    "tags": ["quality-analytics"]
  },
  "frontend": {
    "page_component": "QualityAnalyticsPage",
    "admin_only": false
  }
}
```

## 카테고리

| 카테고리 | 설명 |
|---------|------|
| `core` | 핵심 기능 (dashboard, chat, settings 등) |
| `feature` | 추가 기능 (workflows, rulesets 등) |
| `industry` | 산업별 특화 기능 (quality_pharma, quality_food 등) |
| `integration` | 외부 시스템 연동 |

## 구독 플랜 제한

| 플랜 | 사용 가능 모듈 |
|------|---------------|
| `free` | core 카테고리만 |
| `standard` | core + feature (일부) |
| `enterprise` | 모든 모듈 |

## 빌드 명령어

```bash
# 모듈 레지스트리 생성
python scripts/build_module_registry.py

# 프론트엔드 임포트 맵 생성
python scripts/build_frontend_imports.py

# 모든 빌드 실행 (권장)
npm run build:modules --prefix frontend
```

---

## 외부 모듈 통합 가이드

### 외부 개발자가 모듈을 공개할 때

외부 개발자는 GitHub에 다음 구조로 모듈을 공개합니다:

```
my-triflow-module/
├── manifest.json          # 필수: 모듈 정의
├── __init__.py
├── backend/
│   ├── __init__.py
│   └── router.py          # 필수: FastAPI 라우터
└── frontend/
    └── MyModulePage.tsx   # 필수: React 페이지
```

### 우리 코드베이스에 통합하는 절차

```bash
# 1. 외부 모듈 다운로드 (modules/ 폴더에 직접 clone)
git clone https://github.com/partner/pharma-quality-module modules/pharma_quality

# 2. 레지스트리 및 프론트엔드 임포트 맵 재빌드
npm run build:modules --prefix frontend

# 3. 서버 재시작 → 자동으로 라우터 등록됨
#    (DB 동기화는 서버 시작 시 자동 처리됨)
```

### 통합 후 프로세스

1. **코드 리뷰** - 보안, 품질 검증
2. **Git commit & push** - 정식 코드베이스에 포함
3. **릴리즈** - 모든 고객사에 배포
4. **활성화** - 프로필(tenant_modules)로 고객사별 On/Off

### 요약

| 구분 | 방법 |
|------|------|
| **내부 개발자** | `python scripts/create_module.py` → 개발 → `npm run build:modules` |
| **외부 모듈 통합** | `git clone ... modules/xxx` → `npm run build:modules` → 코드 리뷰 → 릴리즈 |
