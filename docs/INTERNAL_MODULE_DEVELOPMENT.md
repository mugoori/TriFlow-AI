# 내부 개발자 모듈 개발 가이드

TriFlow AI 내부 개발자를 위한 신규 모듈 개발 가이드입니다.

---

## 📋 목차

1. [개발 환경 설정](#개발-환경-설정)
2. [모듈 생성 방법](#모듈-생성-방법)
3. [공유 라이브러리 활용](#공유-라이브러리-활용)
4. [개발 워크플로우](#개발-워크플로우)
5. [테스트 및 디버깅](#테스트-및-디버깅)
6. [Git 커밋 및 PR](#git-커밋-및-pr)
7. [베스트 프랙티스](#베스트-프랙티스)

---

## 개발 환경 설정

### 필수 도구

- **Python 3.11+**
- **Node.js 18+**
- **Git**
- **VS Code** (권장)

### 프로젝트 클론 및 설정

```bash
# 1. 저장소 클론
git clone https://github.com/mugoori/TriFlow-AI.git
cd TriFlow-AI

# 2. 백엔드 설정
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. 프론트엔드 설정
cd ../frontend
npm install

# 4. 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 DB 연결 정보 등 설정
```

### VS Code 확장 프로그램 (권장)

- **Python** (ms-python.python)
- **Pylance** (ms-python.vscode-pylance)
- **ES7+ React/Redux/React-Native snippets**
- **Tailwind CSS IntelliSense**
- **GitLens**

---

## 모듈 생성 방법

### 방법 1: 기본 모듈 생성 (CLI 인자)

기존 `create_module.py` 스크립트 사용:

```bash
cd c:\dev\triflow-ai
python scripts\create_module.py customer_feedback --name "고객 피드백" --category feature --icon MessageSquare
```

**장점**: 빠름
**단점**: 기본 템플릿만 제공, 필드 정의 없음

### 방법 2: 대화형 Generator (권장! 🚀)

**⚠️ 참고**: 이 기능은 Phase 2 구현 후 사용 가능합니다.

```bash
python scripts\create_module_interactive.py

# 대화형으로 질문에 답하면 자동 생성!
```

---

## 공유 라이브러리 활용

⚠️ **중요**: 새 모듈을 만들 때 **반드시** 공유 라이브러리를 사용하세요!
코드가 80% 줄어들고, 일관성이 유지됩니다.

### 백엔드 공유 라이브러리

#### 1. BaseService (CRUD 자동화)

```python
from app.shared.base_service import BaseService
from app.models.customer_feedback import CustomerFeedback

class CustomerFeedbackService(BaseService[CustomerFeedback]):
    def __init__(self, db: Session):
        super().__init__(db, CustomerFeedback)

    # ✅ 자동 제공: get_by_id, list_items, create, update, delete
    # 추가 비즈니스 로직만 구현하면 됨!

    async def send_alert_for_low_rating(self, feedback_id: UUID, tenant_id: UUID):
        """낮은 평점 알림 (커스텀 로직)"""
        feedback = await self.get_by_id(feedback_id, tenant_id)
        if feedback.rating <= 2:
            # 알림 로직
            pass
```

#### 2. PaginatedResponse

```python
from app.shared.pagination import create_paginated_response

items, total = await service.list_items(tenant_id, page, page_size)
return create_paginated_response(items, total, page, page_size)
```

### 프론트엔드 공유 라이브러리

#### 1. useModuleTable Hook ⭐ (가장 중요!)

**Before (공유 Hook 없이)**: 50줄

```typescript
const [data, setData] = useState([]);
const [loading, setLoading] = useState(false);
const [page, setPage] = useState(1);
const [total, setTotal] = useState(0);
// ... 20줄 더

const loadData = useCallback(async () => {
  setLoading(true);
  try {
    const response = await apiClient.get('/api/products', { page });
    setData(response.items);
    setTotal(response.total);
  } catch (err) {
    // 에러 처리
  } finally {
    setLoading(false);
  }
}, [page]);
// ... 20줄 더
```

**After (useModuleTable 사용)**: 3줄!

```typescript
import { useModuleTable } from '@/shared/hooks/useModuleTable';

const { items, loading, error, page, setPage, totalPages } =
  useModuleTable<Product>('/api/v1/products', 20);
```

#### 2. ModulePageLayout 컴포넌트

```typescript
import { ModulePageLayout } from '@/shared/components/layouts/ModulePageLayout';
import { MessageSquare } from 'lucide-react';

export default function CustomerFeedbackPage() {
  return (
    <ModulePageLayout
      icon={MessageSquare}
      title="고객 피드백"
      description="고객 피드백 수집 및 분석"
      actions={<Button>새 피드백</Button>}
    >
      {/* 콘텐츠 */}
    </ModulePageLayout>
  );
}
```

#### 3. DataTable 컴포넌트

```typescript
import { DataTable, DataTableColumn } from '@/shared/components/data/DataTable';

const columns: DataTableColumn<Feedback>[] = [
  { key: 'customer_name', label: '고객명', sortable: true },
  { key: 'rating', label: '평점', sortable: true },
  { key: 'comment', label: '내용' }
];

<DataTable
  columns={columns}
  data={items}
  loading={loading}
  error={error}
  page={page}
  totalPages={totalPages}
  onPageChange={setPage}
/>
```

---

## 개발 워크플로우

### 1단계: 모듈 생성

```bash
# 모듈 생성 (예: customer_feedback)
python scripts\create_module.py customer_feedback --name "고객 피드백" --category feature
```

생성된 파일:
```
modules/customer_feedback/
├── manifest.json
├── backend/
│   ├── __init__.py
│   ├── router.py
│   └── service.py
└── frontend/
    └── CustomerFeedbackPage.tsx
```

### 2단계: manifest.json 수정

```json
{
  "module_code": "customer_feedback",
  "version": "1.0.0",
  "name": "고객 피드백",
  "description": "고객 피드백 수집 및 분석",
  "category": "feature",
  "icon": "MessageSquare",
  "backend": {
    "router_path": "modules.customer_feedback.backend.router",
    "api_prefix": "/api/v1/customer-feedback"
  },
  "frontend": {
    "page_component": "CustomerFeedbackPage"
  }
}
```

### 3단계: 백엔드 구현

#### DB 모델 추가 (필요 시)

`backend/app/models/customer_feedback.py`:

```python
from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid
from datetime import datetime

class CustomerFeedback(Base):
    __tablename__ = "customer_feedbacks"
    __table_args__ = {"schema": "modules"}  # 모듈 전용 스키마

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    customer_name = Column(String(255), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=False)
    status = Column(String(50), default="pending")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### Pydantic 스키마 추가

`modules/customer_feedback/backend/schemas.py`:

```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class FeedbackBase(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=255)
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=1)

class FeedbackCreate(FeedbackBase):
    pass

class FeedbackUpdate(BaseModel):
    status: str = Field(..., regex="^(pending|reviewed|resolved)$")

class FeedbackResponse(FeedbackBase):
    id: UUID
    tenant_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

#### 서비스 구현

`modules/customer_feedback/backend/service.py`:

```python
from app.shared.base_service import BaseService
from app.models.customer_feedback import CustomerFeedback
from uuid import UUID

class CustomerFeedbackService(BaseService[CustomerFeedback]):
    def __init__(self, db: Session):
        super().__init__(db, CustomerFeedback)

    async def send_alert_if_low_rating(self, feedback: CustomerFeedback):
        """낮은 평점 시 알림 발송 (커스텀 로직)"""
        if feedback.rating <= 2:
            # Slack 알림 등
            pass
```

#### 라우터 구현

`modules/customer_feedback/backend/router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User
from app.shared.pagination import create_paginated_response, PaginatedResponse
from .service import CustomerFeedbackService
from .schemas import FeedbackCreate, FeedbackUpdate, FeedbackResponse

router = APIRouter()

@router.get("/", response_model=PaginatedResponse[FeedbackResponse])
async def list_feedbacks(
    page: int = 1,
    page_size: int = 20,
    rating: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """피드백 목록 조회"""
    service = CustomerFeedbackService(db)

    filters = {}
    if rating is not None:
        filters['rating'] = rating

    items, total = await service.list_items(
        tenant_id=current_user.tenant_id,
        page=page,
        page_size=page_size,
        filters=filters
    )

    return create_paginated_response(items, total, page, page_size)

@router.post("/", response_model=FeedbackResponse)
async def create_feedback(
    data: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """피드백 생성"""
    service = CustomerFeedbackService(db)

    feedback = await service.create(
        tenant_id=current_user.tenant_id,
        data=data.model_dump()
    )

    # 낮은 평점 알림
    await service.send_alert_if_low_rating(feedback)

    return feedback
```

### 4단계: 프론트엔드 구현

`modules/customer_feedback/frontend/CustomerFeedbackPage.tsx`:

```typescript
import React, { useState } from 'react';
import { MessageSquare, Plus } from 'lucide-react';
import {
  ModulePageLayout,
  DataTable,
  DataTableColumn,
  useModuleTable,
  useModuleFilters
} from '@/shared';

interface Feedback {
  id: string;
  customer_name: string;
  rating: number;
  comment: string;
  status: string;
  created_at: string;
}

export default function CustomerFeedbackPage() {
  const [showForm, setShowForm] = useState(false);

  const { filters, updateFilter, resetFilters } = useModuleFilters({
    rating: null,
    status: ''
  });

  const {
    items,
    loading,
    error,
    page,
    totalPages,
    setPage,
    reload
  } = useModuleTable<Feedback>('/api/v1/customer-feedback', 20, { filters });

  const columns: DataTableColumn<Feedback>[] = [
    { key: 'customer_name', label: '고객명', sortable: true },
    {
      key: 'rating',
      label: '평점',
      sortable: true,
      render: (item) => (
        <span className={item.rating <= 2 ? 'text-red-600 font-bold' : ''}>
          {item.rating}/5
        </span>
      )
    },
    { key: 'comment', label: '내용' },
    {
      key: 'status',
      label: '상태',
      render: (item) => (
        <span className={`px-2 py-1 rounded text-xs ${
          item.status === 'resolved' ? 'bg-green-100 text-green-700' :
          item.status === 'reviewed' ? 'bg-yellow-100 text-yellow-700' :
          'bg-gray-100 text-gray-700'
        }`}>
          {item.status}
        </span>
      )
    }
  ];

  return (
    <ModulePageLayout
      icon={MessageSquare}
      title="고객 피드백"
      description="고객 피드백 수집 및 분석"
      actions={
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Plus className="w-4 h-4 inline mr-2" />
          새 피드백 추가
        </button>
      }
    >
      {/* 필터 */}
      <div className="bg-white dark:bg-slate-800 rounded-lg border p-4 mb-4">
        <div className="grid grid-cols-3 gap-4">
          <select
            value={filters.rating || ''}
            onChange={(e) => updateFilter('rating', e.target.value ? parseInt(e.target.value) : null)}
            className="px-3 py-2 border rounded-lg"
          >
            <option value="">모든 평점</option>
            <option value="5">5점</option>
            <option value="4">4점</option>
            <option value="3">3점</option>
            <option value="2">2점</option>
            <option value="1">1점</option>
          </select>

          <select
            value={filters.status}
            onChange={(e) => updateFilter('status', e.target.value)}
            className="px-3 py-2 border rounded-lg"
          >
            <option value="">모든 상태</option>
            <option value="pending">대기</option>
            <option value="reviewed">검토 완료</option>
            <option value="resolved">해결 완료</option>
          </select>

          <button
            onClick={resetFilters}
            className="px-4 py-2 border rounded-lg hover:bg-gray-50"
          >
            필터 초기화
          </button>
        </div>
      </div>

      {/* 테이블 */}
      <DataTable
        columns={columns}
        data={items}
        loading={loading}
        error={error}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        emptyMessage="피드백이 없습니다"
      />
    </ModulePageLayout>
  );
}
```

### 5단계: 레지스트리 재빌드

```bash
# 백엔드와 프론트엔드 레지스트리 재빌드
python scripts\build_module_registry.py
python scripts\build_frontend_imports.py
```

### 6단계: 서버 재시작 및 테스트

```bash
# 백엔드 재시작
cd backend
uvicorn app.main:app --reload

# 프론트엔드 재시작 (별도 터미널)
cd frontend
npm run dev
```

### 7단계: 모듈 활성화

1. 브라우저에서 `http://localhost:5173` 접속
2. Admin 로그인
3. **Settings** → **Tenant Modules** → `customer_feedback` 활성화
4. Sidebar에 "고객 피드백" 메뉴 나타남!

---

## 테스트 및 디버깅

### 백엔드 테스트

```bash
# pytest 실행
cd backend
pytest tests/modules/test_customer_feedback.py -v

# 특정 테스트만
pytest tests/modules/test_customer_feedback.py::test_create_feedback -v
```

### API 테스트 (수동)

```bash
# curl 또는 httpie 사용
curl http://localhost:8000/api/v1/customer-feedback \
  -H "Authorization: Bearer YOUR_TOKEN"

# 또는 Swagger UI 사용
open http://localhost:8000/docs
```

### 프론트엔드 디버깅

VS Code의 Chrome 디버거 사용:

1. VS Code에서 `F5` (디버깅 시작)
2. 브레이크포인트 설정
3. 브라우저에서 액션 실행

---

## Git 커밋 및 PR

### 브랜치 전략

```bash
# 1. 새 브랜치 생성
git checkout -b feature/customer-feedback-module

# 2. 개발 진행

# 3. 커밋
git add modules/customer_feedback/
git commit -m "feat: Add customer feedback module

- Add DB models for feedback
- Implement CRUD API endpoints
- Create feedback management UI
- Add low-rating alert feature

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"

# 4. Push
git push origin feature/customer-feedback-module
```

### PR 생성

```bash
# GitHub CLI 사용
gh pr create --title "feat: Add customer feedback module" --body "
## Summary
고객 피드백 수집 및 관리 모듈 추가

## Features
- 피드백 CRUD API
- 평점별 필터링
- 낮은 평점 자동 알림
- 피드백 상태 관리

## Test Plan
- [ ] API 엔드포인트 테스트
- [ ] UI 렌더링 확인
- [ ] 필터링 동작 확인
- [ ] 알림 발송 확인

🤖 Generated with [Claude Code](https://claude.com/claude-code)
"
```

---

## 베스트 프랙티스

### ✅ DO

1. **공유 라이브러리 사용** - `useModuleTable`, `BaseService` 적극 활용
2. **테넌트 격리** - 모든 쿼리에 `tenant_id` 필터 필수
3. **타입 안전성** - TypeScript, Pydantic 활용
4. **에러 처리** - 모든 API 호출에 try-catch
5. **일관성 유지** - 기존 모듈 스타일 참고

### ❌ DON'T

1. **반복 코드 작성** - 공유 라이브러리로 대체 가능
2. **전역 상태 남용** - 모듈 로컬 상태로 충분
3. **하드코딩** - 환경 변수, 설정 파일 활용
4. **테넌트 격리 무시** - 보안 이슈 발생!
5. **과도한 추상화** - 필요한 만큼만

### 코드 리뷰 체크리스트

- [ ] 공유 라이브러리를 최대한 활용했는가?
- [ ] 테넌트 격리가 제대로 구현되었는가?
- [ ] 에러 처리가 적절한가?
- [ ] 타입 안전성이 보장되는가?
- [ ] 테스트 코드가 작성되었는가?
- [ ] 문서화 (주석, README)가 충분한가?

---

## 참고 자료

- **공유 라이브러리 문서**: [/docs/SHARED_LIBRARY.md](./SHARED_LIBRARY.md)
- **API 문서**: http://localhost:8000/docs
- **컴포넌트 스타일 가이드**: [/docs/UI_GUIDELINES.md](./UI_GUIDELINES.md)
- **외부 모듈 개발 가이드**: [/docs/EXTERNAL_MODULE_DEVELOPMENT.md](./EXTERNAL_MODULE_DEVELOPMENT.md)

---

**마지막 업데이트**: 2026-01-19
**TriFlow AI 버전**: 0.1.0
