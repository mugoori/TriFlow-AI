# 🧩 TriFlow AI 모듈 시스템

모듈 단위로 기능을 개발하고 배포하는 플러그인 시스템입니다.

---

## 🎯 주요 기능

### 1️⃣ 공유 라이브러리 (Phase 1 ✅)

**코드 80% 감소!**

```typescript
// Before: 300줄
const [data, setData] = useState([]);
const [loading, setLoading] = useState(false);
// ... 250줄 더

// After: 50줄
import { useModuleTable, DataTable } from '@/shared';
const { items, loading, page, setPage } = useModuleTable('/api/data', 20);
```

**제공되는 것들**:
- ✅ `useModuleTable` - 테이블 상태 자동 관리
- ✅ `useModuleData` - API 호출 자동화
- ✅ `ModulePageLayout` - 표준 페이지 레이아웃
- ✅ `DataTable` - 범용 데이터 테이블
- ✅ `BaseService` - 백엔드 CRUD 자동화

### 2️⃣ 대화형 Generator (Phase 2 ✅)

**5분 안에 모듈 생성!**

```bash
$ python scripts/create_module_interactive.py

Module: customer_feedback
Template: CRUD Table
Fields:
  - customer_name (str)
  - rating (int, 1-5)
  - comment (str)

✅ 생성 완료! 바로 사용 가능합니다.
```

**자동 생성되는 것들**:
- ✅ manifest.json
- ✅ FastAPI 라우터 (CRUD API)
- ✅ Pydantic 스키마
- ✅ React 페이지 컴포넌트
- ✅ 테이블/필터 UI

### 3️⃣ ZIP 설치 시스템 (Phase 3 ✅)

**외부 모듈 2분 안에 설치!**

```bash
# CLI
python scripts/install_module.py awesome_module.zip

# 또는 Web UI
Settings → 모듈 관리 → ZIP 업로드
```

**자동 처리되는 것들**:
- ✅ manifest.json 검증
- ✅ 보안 스캔 (악성 코드 차단)
- ✅ Python 의존성 설치
- ✅ Node.js 의존성 설치
- ✅ 모듈 등록
- ✅ 실패 시 자동 롤백

---

## 📂 파일 위치

### 공유 라이브러리
```
frontend/src/shared/
├── hooks/
│   ├── useModuleData.ts
│   ├── useModuleTable.ts      ⭐ 가장 중요!
│   └── useModuleFilters.ts
├── components/
│   ├── layouts/ModulePageLayout.tsx
│   └── data/DataTable.tsx
└── index.ts

backend/app/shared/
├── base_service.py             ⭐ 가장 중요!
├── pagination.py
└── schemas/
```

### 템플릿
```
module_templates/
└── crud_table/
    ├── manifest.json.j2
    ├── backend/
    │   ├── router.py.j2
    │   ├── service.py.j2
    │   └── schemas.py.j2
    └── frontend/
        └── Page.tsx.j2
```

### CLI 도구
```
scripts/
├── create_module_interactive.py   # 대화형 Generator
├── install_module.py              # ZIP 설치
├── uninstall_module.py            # 모듈 제거
└── list_modules.py                # 모듈 목록
```

### API
```
backend/app/routers/modules.py
- POST /api/v1/modules/upload      # ZIP 업로드
- GET  /api/v1/modules             # 모듈 목록
- DELETE /api/v1/modules/{code}    # 모듈 제거
```

### UI
```
frontend/src/components/settings/
└── ModuleManagerSection.tsx       # Settings 페이지 내 모듈 관리
```

---

## 📚 문서

| 대상 | 문서 | 설명 |
|-----|------|------|
| **전체** | [MODULE_SYSTEM_GUIDE.md](./docs/MODULE_SYSTEM_GUIDE.md) | 시스템 개요 |
| **내부 개발자** | [INTERNAL_MODULE_DEVELOPMENT.md](./docs/INTERNAL_MODULE_DEVELOPMENT.md) | 상세 개발 가이드 |
| **외부 파트너** | [EXTERNAL_MODULE_DEVELOPMENT.md](./docs/EXTERNAL_MODULE_DEVELOPMENT.md) | 모듈 개발 규격 |

---

## 🎓 사용 예시

### 예시 1: 내부 - "재고 관리" 모듈 개발

```bash
# 1. Generator 실행 (5분)
python scripts/create_module_interactive.py
> inventory_management
> Template: CRUD Table
> Fields: product_name, quantity, price

# 2. 비즈니스 로직 추가 (1시간)
# - "재고 10개 이하면 알림" 기능 추가

# 3. 완료! (총 1시간)
```

### 예시 2: 외부 - 파트너사 모듈 설치

```bash
# 파트너사로부터 받은 ZIP
advanced_analytics.zip

# 설치 (2분)
python scripts/install_module.py advanced_analytics.zip

# 또는 Web UI에서 Drag & Drop

# 완료! 자동으로 의존성 설치됨
```

---

## ⚙️ 설정 및 요구사항

### 필수 의존성

**Python**:
- jinja2==3.1.3 (템플릿 엔진)

**이미 requirements.txt에 추가됨!**

### 모듈 규격 요구사항

**백엔드**:
- Python 3.11+
- FastAPI

**프론트엔드**:
- React 18+
- TypeScript (권장)

---

## 🚀 시작하기

### 1. 의존성 설치

```bash
cd backend
pip install -r requirements.txt  # jinja2 포함
```

### 2. 첫 모듈 만들기

```bash
# 기존 방식 (빠름)
python scripts/create_module.py test_module --name "테스트 모듈"

# 대화형 (Phase 2 완료 후)
python scripts/create_module_interactive.py
```

### 3. 서버 재시작

```bash
# 백엔드
uvicorn app.main:app --reload

# 프론트엔드
npm run dev --prefix frontend
```

### 4. 모듈 활성화

```
Settings → Tenant Modules → test_module 활성화
```

---

## 📈 로드맵

### ✅ 완료 (2026-01-19)
- Phase 1: 공유 라이브러리
- Phase 2: 대화형 Generator (템플릿)
- Phase 3: ZIP 설치 시스템 (기본)
- 문서 작성

### 🔜 향후 계획
- [ ] Dashboard 템플릿
- [ ] Chat Interface 템플릿
- [ ] Hot Module Reload
- [ ] 모듈 마켓플레이스
- [ ] 모듈 간 이벤트 버스
- [ ] 자동 테스트 생성

---

## 💡 팁

1. **항상 공유 라이브러리 사용하기** - 코드가 80% 줄어듭니다!
2. **CRUD 모듈은 Generator 사용** - 5분 안에 생성 가능
3. **외부 모듈은 ZIP 설치** - 클릭 몇 번으로 완료
4. **테넌트 격리 필수** - 모든 쿼리에 `tenant_id` 적용
5. **문서 참고** - 막히면 docs/ 폴더 확인

---

## 🆘 문제 해결

### Generator 실행 안됨
```bash
pip install jinja2
```

### 모듈이 메뉴에 안 나타남
```bash
# Settings에서 모듈 활성화 확인
# 서버 재시작 확인
```

### ZIP 설치 실패
```bash
# 검증만 실행
python scripts/install_module.py module.zip --dry-run

# 에러 메시지 확인 후 수정
```

---

**시작하려면**: [docs/MODULE_SYSTEM_GUIDE.md](./docs/MODULE_SYSTEM_GUIDE.md)

**문의**: support@triflow.ai
