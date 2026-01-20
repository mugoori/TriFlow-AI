# 외부 모듈 개발 가이드

TriFlow AI 플랫폼을 위한 외부 모듈을 개발하고 배포하는 방법을 설명합니다.

---

## 📋 목차

1. [모듈 규격 개요](#모듈-규격-개요)
2. [필수 파일 구조](#필수-파일-구조)
3. [manifest.json 작성 가이드](#manifestjson-작성-가이드)
4. [백엔드 개발 (FastAPI)](#백엔드-개발-fastapi)
5. [프론트엔드 개발 (React)](#프론트엔드-개발-react)
6. [의존성 관리](#의존성-관리)
7. [모듈 패키징 (ZIP)](#모듈-패키징-zip)
8. [설치 및 테스트](#설치-및-테스트)
9. [보안 주의사항](#보안-주의사항)
10. [FAQ](#faq)

---

## 모듈 규격 개요

TriFlow AI는 **플러그인 기반 아키텍처**를 사용합니다. 외부 개발자가 만든 모듈은 다음 규격만 지키면 **자동으로 통합**됩니다:

### 필수 조건

| 항목 | 요구사항 |
|-----|---------|
| **백엔드 언어** | Python 3.11+ |
| **백엔드 프레임워크** | FastAPI |
| **프론트엔드 언어** | TypeScript 또는 JavaScript |
| **프론트엔드 프레임워크** | React 18+ |
| **필수 파일** | `manifest.json` |

### 규격 준수 시 자동 지원

✅ **자동 라우터 등록** - FastAPI 라우터가 자동으로 로드됨
✅ **자동 UI 통합** - React 컴포넌트가 자동으로 메뉴에 추가됨
✅ **의존성 자동 설치** - Python/Node.js 패키지 자동 설치
✅ **테넌트 격리** - 멀티테넌트 환경 자동 지원
✅ **권한 관리** - RBAC 자동 적용

---

## 필수 파일 구조

모듈의 기본 구조입니다:

```
my_awesome_module/
├── manifest.json          # 필수: 모듈 메타데이터
├── README.md             # 선택: 모듈 설명
├── LICENSE               # 선택: 라이선스
├── requirements.txt      # 선택: Python 의존성
├── package.json          # 선택: Node.js 의존성
│
├── backend/              # 선택 (백엔드 기능 있을 때)
│   ├── __init__.py
│   ├── router.py        # 필수: FastAPI 라우터
│   ├── service.py       # 권장: 비즈니스 로직
│   ├── models.py        # 선택: DB 모델
│   └── schemas.py       # 권장: Pydantic 스키마
│
└── frontend/             # 선택 (프론트엔드 UI 있을 때)
    ├── MyAwesomeModulePage.tsx  # 필수: 메인 페이지 컴포넌트
    └── components/              # 선택: 하위 컴포넌트들
        ├── MyTable.tsx
        └── MyChart.tsx
```

---

## manifest.json 작성 가이드

`manifest.json`은 모듈의 **"설명서"**입니다. TriFlow는 이 파일을 읽어서 모듈을 자동으로 통합합니다.

### 필수 필드

```json
{
  "$schema": "../module-schema.json",
  "module_code": "my_awesome_module",
  "version": "1.0.0",
  "name": "나의 멋진 모듈",
  "description": "이 모듈은 멋진 기능을 제공합니다",
  "category": "feature"
}
```

### 전체 예시 (모든 필드)

```json
{
  "$schema": "../module-schema.json",

  "module_code": "quality_analytics",
  "version": "1.2.0",
  "name": "품질 분석",
  "description": "제품 품질 분석 및 리포팅 모듈",
  "category": "feature",
  "icon": "BarChart",
  "default_enabled": false,

  "author": "Partner Inc.",
  "license": "MIT",
  "repository": "https://github.com/partner/quality-analytics",

  "requires_subscription": "standard",
  "min_triflow_version": "0.1.0",
  "depends_on": ["data", "dashboard"],

  "python_dependencies": [
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "scikit-learn>=1.3.0"
  ],

  "node_dependencies": {
    "recharts": "^3.5.0",
    "axios": "^1.6.0"
  },

  "backend": {
    "router_path": "modules.quality_analytics.backend.router",
    "api_prefix": "/api/v1/quality-analytics",
    "tags": ["quality-analytics"]
  },

  "frontend": {
    "page_component": "QualityAnalyticsPage",
    "admin_only": false,
    "hide_from_nav": false
  },

  "display_order": 100
}
```

### 필드 설명

| 필드 | 필수 | 타입 | 설명 |
|-----|-----|------|------|
| `module_code` | ✅ | string | 고유 식별자 (snake_case, 예: `quality_analytics`) |
| `version` | ✅ | string | Semantic versioning (예: `1.2.0`) |
| `name` | ✅ | string | 표시 이름 (예: `"품질 분석"`) |
| `description` | ✅ | string | 모듈 설명 |
| `category` | ✅ | enum | `core`, `feature`, `industry`, `integration` 중 하나 |
| `icon` | ❌ | string | Lucide 아이콘 이름 (예: `"BarChart"`) |
| `author` | ❌ | string | 개발자/회사 이름 |
| `license` | ❌ | string | 라이선스 (예: `"MIT"`, `"proprietary"`) |
| `repository` | ❌ | string | Git 저장소 URL |
| `requires_subscription` | ❌ | enum | `free`, `standard`, `enterprise` |
| `min_triflow_version` | ❌ | string | 최소 플랫폼 버전 (예: `"0.1.0"`) |
| `depends_on` | ❌ | array | 의존 모듈 목록 (예: `["data", "dashboard"]`) |
| `python_dependencies` | ❌ | array | Python 패키지 목록 |
| `node_dependencies` | ❌ | object | Node.js 패키지 (key: 패키지명, value: 버전) |
| `backend` | ❌ | object | 백엔드 설정 |
| `backend.router_path` | ✅* | string | 라우터 import 경로 (*백엔드 있으면 필수) |
| `backend.api_prefix` | ❌ | string | API 엔드포인트 prefix |
| `backend.tags` | ❌ | array | OpenAPI 태그 |
| `frontend` | ❌ | object | 프론트엔드 설정 |
| `frontend.page_component` | ✅* | string | 컴포넌트 이름 (PascalCase) (*프론트엔드 있으면 필수) |
| `frontend.admin_only` | ❌ | boolean | Admin 전용 여부 (기본: `false`) |
| `display_order` | ❌ | number | 메뉴 정렬 순서 (기본: `100`) |

---

## 백엔드 개발 (FastAPI)

### 기본 구조

백엔드는 **FastAPI Router**를 export해야 합니다.

#### `backend/router.py` (필수)

```python
"""
품질 분석 Module - API Router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User
from .service import QualityAnalyticsService
from .schemas import QualityReportResponse

# 🔥 중요: 변수명은 반드시 'router'!
router = APIRouter()


@router.get("/reports", response_model=List[QualityReportResponse])
async def list_quality_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """품질 리포트 목록 조회"""
    service = QualityAnalyticsService(db)
    reports = await service.get_reports(current_user.tenant_id)
    return reports


@router.post("/reports")
async def create_quality_report(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """품질 리포트 생성"""
    service = QualityAnalyticsService(db)
    report = await service.create_report(current_user.tenant_id, data)
    return report
```

### 필수 규칙

1. **변수명은 `router`** - 다른 이름 사용 시 로드 실패!
2. **FastAPI Router 타입** - `APIRouter()` 인스턴스여야 함
3. **테넌트 격리** - 모든 쿼리에 `tenant_id` 필터 적용 필수!
4. **인증 의존성** - `get_current_user` 사용하여 인증 사용자 확인

### 서비스 레이어 (권장)

비즈니스 로직은 별도 서비스 클래스로 분리하는 것을 권장합니다.

#### `backend/service.py`

```python
"""
품질 분석 Module - Business Logic
"""
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session


class QualityAnalyticsService:
    """품질 분석 서비스"""

    def __init__(self, db: Session):
        self.db = db

    async def get_reports(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """리포트 목록 조회 (테넌트 격리)"""
        # TODO: 실제 DB 쿼리
        # 반드시 tenant_id 필터 적용!
        return []

    async def create_report(
        self,
        tenant_id: UUID,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """리포트 생성"""
        # TODO: 비즈니스 로직
        return {"id": "...", "status": "created"}
```

### Pydantic 스키마 (권장)

API 요청/응답 검증을 위한 스키마를 정의합니다.

#### `backend/schemas.py`

```python
"""
품질 분석 Module - Pydantic Schemas
"""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from typing import Optional


class QualityReportBase(BaseModel):
    product_id: str
    quality_score: float
    defect_count: int


class QualityReportCreate(QualityReportBase):
    """리포트 생성 요청"""
    pass


class QualityReportResponse(QualityReportBase):
    """리포트 응답"""
    id: UUID
    tenant_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
```

---

## 프론트엔드 개발 (React)

### 기본 구조

프론트엔드는 **React 컴포넌트**를 default export해야 합니다.

#### `frontend/QualityAnalyticsPage.tsx` (필수)

```typescript
/**
 * 품질 분석 Page
 */
import React, { useState } from 'react';
import { BarChart, Plus } from 'lucide-react';
import { ModulePageLayout } from '@/shared/components/layouts/ModulePageLayout';
import { useModuleTable } from '@/shared/hooks/useModuleTable';
import { DataTable, DataTableColumn } from '@/shared/components/data/DataTable';

interface QualityReport {
  id: string;
  product_id: string;
  quality_score: number;
  defect_count: number;
  created_at: string;
}

// 🔥 중요: 반드시 default export!
export default function QualityAnalyticsPage() {
  // 🔥 공유 Hook 사용 권장 - 코드 80% 감소!
  const {
    items,
    loading,
    error,
    page,
    totalPages,
    setPage,
    reload
  } = useModuleTable<QualityReport>('/api/v1/quality-analytics/reports', 20);

  const columns: DataTableColumn<QualityReport>[] = [
    { key: 'product_id', label: '제품 ID', sortable: true },
    { key: 'quality_score', label: '품질 점수', sortable: true },
    { key: 'defect_count', label: '결함 수', sortable: true },
    { key: 'created_at', label: '생성일', sortable: true }
  ];

  return (
    <ModulePageLayout
      icon={BarChart}
      title="품질 분석"
      description="제품 품질 분석 및 리포팅"
      actions={
        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg">
          <Plus className="w-4 h-4 inline mr-2" />
          새 리포트 생성
        </button>
      }
    >
      <DataTable
        columns={columns}
        data={items}
        loading={loading}
        error={error}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
      />
    </ModulePageLayout>
  );
}
```

### 필수 규칙

1. **Default export** - `export default function ComponentName()`
2. **컴포넌트 이름은 PascalCase** - `QualityAnalyticsPage` (manifest.json과 일치)
3. **파일명은 컴포넌트명과 동일** - `QualityAnalyticsPage.tsx`

### 공유 라이브러리 활용 (강력 권장!)

TriFlow는 반복 코드를 제거하는 **공유 라이브러리**를 제공합니다. 사용하면 코드가 80% 줄어듭니다!

#### 1. useModuleTable Hook (테이블 데이터)

```typescript
import { useModuleTable } from '@/shared/hooks/useModuleTable';

const {
  items,        // 데이터 배열
  loading,      // 로딩 상태
  error,        // 에러 메시지
  page,         // 현재 페이지
  totalPages,   // 전체 페이지 수
  setPage,      // 페이지 변경 함수
  reload        // 데이터 새로고침
} = useModuleTable<MyDataType>('/api/v1/my-endpoint', 20);
```

#### 2. useModuleData Hook (단순 데이터)

```typescript
import { useModuleData } from '@/shared/hooks/useModuleData';

const { data, loading, error, reload } = useModuleData<ConfigType>(
  '/api/v1/config',
  { autoLoad: true }
);
```

#### 3. ModulePageLayout 컴포넌트

```typescript
import { ModulePageLayout } from '@/shared/components/layouts/ModulePageLayout';

<ModulePageLayout
  icon={MyIcon}
  title="제목"
  description="설명"
  actions={<Button>버튼</Button>}
>
  {content}
</ModulePageLayout>
```

#### 4. DataTable 컴포넌트

```typescript
import { DataTable } from '@/shared/components/data/DataTable';

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

## 의존성 관리

### Python 의존성

#### 방법 1: manifest.json에 명시 (권장)

```json
{
  "python_dependencies": [
    "pandas>=2.0.0,<3.0.0",
    "numpy>=1.24.0",
    "scikit-learn==1.3.2"
  ]
}
```

#### 방법 2: requirements.txt 사용

```txt
pandas>=2.0.0,<3.0.0
numpy>=1.24.0
scikit-learn==1.3.2
matplotlib>=3.8.0
```

**설치 시 자동 실행**: `pip install -r requirements.txt`

### Node.js 의존성

#### 방법 1: manifest.json에 명시 (권장)

```json
{
  "node_dependencies": {
    "recharts": "^3.5.0",
    "axios": "^1.6.0",
    "lodash": "^4.17.21"
  }
}
```

#### 방법 2: package.json 사용

```json
{
  "dependencies": {
    "recharts": "^3.5.0",
    "axios": "^1.6.0"
  }
}
```

**설치 시 자동 실행**: `npm install`

### 주의사항

⚠️ **버전 충돌 방지**: 명확한 버전 범위 지정 권장
⚠️ **테스트 필수**: 로컬에서 의존성 설치 후 동작 확인
⚠️ **최소 버전만**: 개발에 실제 필요한 패키지만 포함

---

## 모듈 패키징 (ZIP)

개발이 완료되면 모듈을 ZIP 파일로 패키징합니다.

### 패키징 명령어

```bash
# Windows (PowerShell)
Compress-Archive -Path my_awesome_module/* -DestinationPath my_awesome_module_v1.0.0.zip

# macOS/Linux
cd my_awesome_module
zip -r ../my_awesome_module_v1.0.0.zip .

# 또는 Git 저장소에서
git archive --format=zip --output=my_awesome_module_v1.0.0.zip HEAD
```

### ZIP 파일 구조 검증

압축 해제 후 다음 구조여야 합니다:

```
my_awesome_module_v1.0.0.zip
└── manifest.json              ← 루트에 manifest.json 필수!
└── backend/
    └── router.py
└── frontend/
    └── MyPage.tsx
```

**잘못된 예**:
```
my_awesome_module_v1.0.0.zip
└── my_awesome_module/         ← ❌ 중복 폴더!
    └── manifest.json
```

---

## 설치 및 테스트

### 설치 방법 1: CLI (개발자용)

```bash
cd /path/to/triflow-ai
python scripts/install_module.py my_awesome_module_v1.0.0.zip

# 설치 전 검증만
python scripts/install_module.py my_awesome_module_v1.0.0.zip --dry-run

# 강제 덮어쓰기
python scripts/install_module.py my_awesome_module_v1.0.0.zip --force
```

### 설치 방법 2: Web UI (사용자용)

1. TriFlow AI 웹사이트 접속
2. **Admin** 계정으로 로그인
3. **Settings** 페이지로 이동
4. **모듈 관리** 섹션 찾기
5. ZIP 파일을 Drag & Drop 또는 파일 선택
6. 설치 진행 상태 확인
7. 서버 재시작

### 테스트 체크리스트

- [ ] manifest.json 검증 통과
- [ ] 의존성 자동 설치 성공
- [ ] API 엔드포인트 응답 확인
- [ ] 프론트엔드 페이지 렌더링 확인
- [ ] 테넌트 격리 동작 확인
- [ ] 권한 체크 동작 확인

---

## 보안 주의사항

### 금지 사항

TriFlow는 다음을 자동으로 차단합니다:

❌ **실행 파일**: `.exe`, `.dll`, `.so`, `.dylib`
❌ **쉘 스크립트**: `.sh`, `.bat`, `.cmd`
❌ **경로 탐색**: `../`, 절대 경로
❌ **위험한 코드**: `eval()`, `exec()`, `__import__`

### 권장 사항

✅ **최소 권한**: 필요한 데이터만 접근
✅ **입력 검증**: 사용자 입력은 항상 검증
✅ **SQL Injection 방지**: ORM 사용 (SQLAlchemy)
✅ **XSS 방지**: React는 기본적으로 방어하지만, `dangerouslySetInnerHTML` 사용 금지
✅ **환경 변수**: 민감한 정보는 환경 변수로 관리

---

## FAQ

### Q: TypeScript 대신 JavaScript를 사용해도 되나요?
**A**: 네, 가능합니다. 하지만 TypeScript를 강력히 권장합니다 (타입 안전성).

### Q: DB 마이그레이션이 필요한 경우는?
**A**: `migrations/` 폴더에 SQL 파일을 포함하면 설치 시 실행됩니다. 하지만 주의 필요! 기존 스키마와 충돌하지 않도록 사전 협의 필요합니다.

### Q: 모듈 간 통신은 어떻게 하나요?
**A**: 현재는 REST API를 통한 통신만 지원됩니다. 향후 이벤트 버스 시스템이 추가될 예정입니다.

### Q: 외부 API를 호출해도 되나요?
**A**: 네, 가능합니다. `requests`, `httpx`, `axios` 등 자유롭게 사용하세요.

### Q: 모듈 설치 실패 시 롤백되나요?
**A**: 네, 자동으로 이전 상태로 복구됩니다.

### Q: 모듈 업데이트는 어떻게 하나요?
**A**: 버전을 올린 ZIP 파일을 다시 설치하면 자동으로 업그레이드됩니다.

---

## 지원

문제가 발생하거나 질문이 있으면:

- **이슈 등록**: https://github.com/mugoori/TriFlow-AI/issues
- **이메일**: support@triflow.ai
- **문서**: https://docs.triflow.ai

---

**마지막 업데이트**: 2026-01-19
**TriFlow AI 버전**: 0.1.0
