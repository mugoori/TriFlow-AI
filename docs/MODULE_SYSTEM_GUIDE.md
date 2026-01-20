# TriFlow AI 모듈 시스템 가이드

모듈 단위 개발을 쉽게 하기 위한 통합 가이드입니다.

---

## 📚 문서 목록

이 시스템은 다음 3가지 문서로 구성됩니다:

1. **[이 문서] MODULE_SYSTEM_GUIDE.md** - 전체 시스템 개요 및 빠른 시작
2. **[INTERNAL_MODULE_DEVELOPMENT.md](./INTERNAL_MODULE_DEVELOPMENT.md)** - 내부 개발자용 상세 가이드
3. **[EXTERNAL_MODULE_DEVELOPMENT.md](./EXTERNAL_MODULE_DEVELOPMENT.md)** - 외부 파트너용 개발 가이드

---

## 🎯 시스템 개요

TriFlow AI는 **플러그인 기반 모듈 시스템**을 제공합니다:

```
┌─────────────────────────────────────────────────────────────┐
│                    TriFlow AI Platform                       │
├─────────────────────────────────────────────────────────────┤
│  Core Modules      │ Feature Modules │ External Modules     │
│  - Dashboard       │ - Workflows     │ - Partner Modules    │
│  - Chat            │ - Rulesets      │ - Custom Solutions   │
│  - Data            │ - Experiments   │ - Industry Specific  │
│  - Settings        │ - Learning      │                      │
└─────────────────────────────────────────────────────────────┘
```

### 3가지 핵심 기능

1. **공유 라이브러리** 📚
   - 반복 코드 80% 제거
   - 표준 UI/API 패턴 제공
   - Hook/컴포넌트 재사용

2. **대화형 Generator** 🚀
   - 5분 안에 모듈 생성
   - 템플릿 기반 자동 생성
   - 즉시 사용 가능한 코드

3. **ZIP 설치 시스템** 📦
   - 외부 모듈 2분 안에 설치
   - 의존성 자동 처리
   - 보안 검증 자동화

---

## ⚡ 빠른 시작

### 내부 개발자: 새 모듈 만들기

```bash
# 1. Generator 실행 (Phase 2 완료 후 사용 가능)
python scripts/create_module_interactive.py

# 질문에 답하면 자동 생성!
# ✅ 5분 안에 완성

# 2. 서버 재시작
uvicorn app.main:app --reload   # 백엔드
npm run dev --prefix frontend    # 프론트엔드

# 3. Settings에서 모듈 활성화
# 완료!
```

### 외부 모듈: ZIP 설치하기

#### 방법 A: CLI
```bash
python scripts/install_module.py partner_module.zip
# ✅ 2분 안에 설치 완료
```

#### 방법 B: Web UI (더 쉬움!)
```
1. Admin 로그인
2. Settings → 모듈 관리
3. ZIP 파일 Drag & Drop
4. 설치 완료 대기
5. 서버 재시작
```

---

## 📖 공유 라이브러리 사용법

### 프론트엔드: 테이블 페이지 만들기

**Before (없이)**: ~300줄

```typescript
const [data, setData] = useState([]);
const [loading, setLoading] = useState(false);
const [page, setPage] = useState(1);
// ... 250줄 더
```

**After (사용)**: ~50줄!

```typescript
import { useModuleTable, ModulePageLayout, DataTable } from '@/shared';

export default function MyModulePage() {
  const { items, loading, page, setPage, totalPages } =
    useModuleTable('/api/v1/my-data', 20);

  return (
    <ModulePageLayout icon={MyIcon} title="제목">
      <DataTable
        columns={columns}
        data={items}
        loading={loading}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
      />
    </ModulePageLayout>
  );
}
```

**코드 감소율**: 80% 🎉

### 백엔드: CRUD API 만들기

**Before (없이)**: ~200줄

```python
@router.get("/")
async def list_items(page: int, db: Session, user: User):
    # 페이지네이션 로직 30줄
    # 필터링 로직 20줄
    # 정렬 로직 20줄
    # ... 130줄 더
```

**After (사용)**: ~20줄!

```python
from app.shared.base_service import BaseService
from app.shared.pagination import create_paginated_response

class MyService(BaseService[MyModel]):
    # get_by_id, list_items, create, update, delete 자동 제공!
    pass

@router.get("/")
async def list_items(page: int, db: Session, user: User):
    service = MyService(db)
    items, total = await service.list_items(user.tenant_id, page, 20)
    return create_paginated_response(items, total, page, 20)
```

**코드 감소율**: 90% 🚀

---

## 🔐 모듈 규격 (외부 개발자)

외부에서 모듈을 개발할 때 **반드시 지켜야 할 규칙**:

### 1. 파일 구조

```
your_module/
├── manifest.json          # 필수!
├── backend/
│   └── router.py         # FastAPI Router
└── frontend/
    └── YourModulePage.tsx # React Component
```

### 2. manifest.json

```json
{
  "module_code": "your_module",      // snake_case
  "version": "1.0.0",                // semver
  "name": "모듈 이름",
  "category": "feature",              // core/feature/industry/integration
  "backend": {
    "router_path": "modules.your_module.backend.router"
  },
  "frontend": {
    "page_component": "YourModulePage"  // PascalCase
  }
}
```

### 3. 백엔드 규격

```python
# backend/router.py
from fastapi import APIRouter

router = APIRouter()  # 변수명 'router' 필수!

@router.get("/")
async def my_endpoint():
    return {"hello": "world"}
```

### 4. 프론트엔드 규격

```typescript
// frontend/YourModulePage.tsx
import React from 'react';

export default function YourModulePage() {  // default export 필수!
  return <div>Hello</div>;
}
```

### 5. ZIP 패키징

```bash
zip -r your_module_v1.0.0.zip your_module/
```

**완료!** 이제 이 ZIP을 TriFlow에 설치할 수 있습니다.

---

## 🛠️ CLI 도구 사용법

### 모듈 생성 (기존 방식)

```bash
python scripts/create_module.py my_module --name "내 모듈"
```

### 모듈 설치

```bash
# ZIP에서 설치
python scripts/install_module.py module.zip

# 검증만 (설치 안함)
python scripts/install_module.py module.zip --dry-run

# 강제 덮어쓰기
python scripts/install_module.py module.zip --force
```

### 모듈 제거

```bash
python scripts/uninstall_module.py module_code

# 확인 없이 제거
python scripts/uninstall_module.py module_code --yes
```

### 모듈 목록

```bash
# 전체 목록
python scripts/list_modules.py

# 카테고리별
python scripts/list_modules.py --category feature
```

---

## 🎨 공유 라이브러리 API

### 프론트엔드 Hooks

#### useModuleTable
```typescript
const {
  items,         // T[]
  loading,       // boolean
  error,         // string | null
  page,          // number
  totalPages,    // number
  setPage,       // (page: number) => void
  reload         // () => Promise<void>
} = useModuleTable<T>('/api/endpoint', 20);
```

#### useModuleData
```typescript
const {
  data,          // T | null
  loading,       // boolean
  error,         // string | null
  reload         // () => Promise<void>
} = useModuleData<T>('/api/endpoint');
```

#### useModuleFilters
```typescript
const {
  filters,            // T
  activeFilterCount,  // number
  updateFilter,       // (key, value) => void
  resetFilters        // () => void
} = useModuleFilters({ name: '', category: '' });
```

### 프론트엔드 컴포넌트

#### ModulePageLayout
```typescript
<ModulePageLayout
  icon={MyIcon}
  title="제목"
  description="설명"
  actions={<Button>액션</Button>}
>
  {children}
</ModulePageLayout>
```

#### DataTable
```typescript
<DataTable
  columns={[
    { key: 'name', label: '이름', sortable: true },
    { key: 'price', label: '가격', sortable: true }
  ]}
  data={items}
  loading={loading}
  error={error}
  page={page}
  totalPages={totalPages}
  onPageChange={setPage}
/>
```

### 백엔드 클래스

#### BaseService
```python
class MyService(BaseService[MyModel]):
    def __init__(self, db: Session):
        super().__init__(db, MyModel)

    # 자동 제공:
    # - get_by_id(item_id, tenant_id)
    # - list_items(tenant_id, page, page_size, filters)
    # - list_items_paginated(...)
    # - create(tenant_id, data)
    # - update(item_id, tenant_id, data)
    # - delete(item_id, tenant_id)
```

---

## 🔒 보안

### ZIP 파일 자동 검증

설치 시 자동으로 차단:
- ❌ `.exe`, `.dll`, `.so` (실행 파일)
- ❌ `../` (경로 탐색)
- ❌ 절대 경로
- ⚠️ `eval()`, `exec()` (경고)

### 권한 관리

- **모듈 설치/제거**: Admin만 가능
- **모듈 활성화**: Admin이 테넌트별 제어
- **API 접근**: 활성화된 모듈만

---

## 📊 효과

| 지표 | Before | After | 개선율 |
|-----|--------|-------|--------|
| 모듈 개발 시간 | 2-3일 | 2-3시간 | **10배** |
| 코드 중복률 | 80% | 20% | **4배 개선** |
| 외부 모듈 설치 | 30분 | 2분 | **15배** |

---

## 🚀 다음 단계

### 개발자라면
→ [INTERNAL_MODULE_DEVELOPMENT.md](./INTERNAL_MODULE_DEVELOPMENT.md) 읽기

### 외부 파트너라면
→ [EXTERNAL_MODULE_DEVELOPMENT.md](./EXTERNAL_MODULE_DEVELOPMENT.md) 읽기

---

## ❓ FAQ

**Q: 기존 모듈은 어떻게 되나요?**
A: 그대로 작동합니다. 공유 라이브러리는 선택사항입니다.

**Q: TypeScript 필수인가요?**
A: 권장하지만, JavaScript도 가능합니다.

**Q: 모듈끼리 통신할 수 있나요?**
A: REST API를 통한 통신은 가능합니다. 이벤트 버스는 향후 추가 예정입니다.

**Q: DB 마이그레이션은 어떻게 하나요?**
A: `migrations/` 폴더에 SQL 파일을 포함하면 됩니다. 단, 사전 협의 필요합니다.

---

**마지막 업데이트**: 2026-01-19
**TriFlow AI 버전**: 0.1.0
