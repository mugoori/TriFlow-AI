# 리팩토링 가이드

## Phase 1 완료: Repository 패턴 도입

### 📅 완료일: 2026-01-21

---

## 🎯 수행 작업

### 1. 새로 생성된 파일

#### Repositories (데이터 접근 계층)
```
backend/app/repositories/
├── __init__.py
├── base_repository.py       # 기본 Repository 클래스
├── user_repository.py        # User 데이터 접근
└── workflow_repository.py    # Workflow 데이터 접근
```

#### Utilities (유틸리티)
```
backend/app/utils/
├── errors.py                 # 에러 헬퍼 함수 추가
└── decorators.py             # 에러 처리 데코레이터 (신규)
```

### 2. 수정된 파일

**backend/app/routers/auth.py**
- `login` 엔드포인트: `UserRepository.get_by_email()` 사용
- `register` 엔드포인트: `UserRepository.email_exists()` 사용

---

## 📝 사용 예시

### Before (기존 코드)

```python
# 직접 DB 쿼리
user = db.query(User).filter(User.email == email).first()
if not user:
    raise HTTPException(status_code=404, detail="User not found")

# 중복 체크
existing = db.query(User).filter(User.email == email).first()
if existing:
    raise HTTPException(status_code=409, detail="Email already registered")
```

### After (리팩토링 후)

```python
# Repository 사용
user_repo = UserRepository(db)
user = user_repo.get_by_email(email)
if not user:
    raise_not_found("User", email)

# 중복 체크
if user_repo.email_exists(email):
    raise HTTPException(status_code=409, detail="Email already registered")
```

---

## 🔧 제공되는 기능

### UserRepository

```python
user_repo = UserRepository(db)

# 조회
user = user_repo.get_by_id_or_404(user_id)          # ID로 조회 (404)
user = user_repo.get_by_email(email)                # 이메일로 조회
user = user_repo.get_by_username(username)          # 사용자명으로 조회

# 목록
users = user_repo.get_active_users()                # 활성 사용자
users = user_repo.get_by_tenant(tenant_id)          # 테넌트별

# 검증
exists = user_repo.email_exists(email)              # 이메일 중복
exists = user_repo.username_exists(username)        # 사용자명 중복
```

### WorkflowRepository

```python
wf_repo = WorkflowRepository(db)

# 조회
workflow = wf_repo.get_by_id_or_404(workflow_id)    # ID로 조회 (404)
workflow = wf_repo.get_by_name(name, tenant_id)     # 이름으로 조회

# 목록
workflows = wf_repo.get_by_tenant(tenant_id)        # 테넌트별
workflows = wf_repo.get_active_workflows(tenant_id) # 활성만

# 검증
exists = wf_repo.name_exists(name, tenant_id)       # 이름 중복
```

### Error Utilities

```python
from app.utils.errors import (
    raise_not_found,
    raise_access_denied,
    raise_validation_error,
    require_resource,
    require_ownership
)

# 404 에러
raise_not_found("User", str(user_id))

# 403 에러
raise_access_denied("Workflow", "modify")

# 400 에러
raise_validation_error("email", "Invalid format")

# 리소스 존재 확인
user = require_resource(user, "User", str(user_id))

# 소유권 확인
require_ownership(workflow, current_user.user_id, "delete")
```

### Error Handling Decorator

```python
from app.utils.decorators import handle_service_errors

class WorkflowService:
    @handle_service_errors(resource="workflow", operation="execute")
    async def execute_workflow(self, workflow_id: UUID):
        # 비즈니스 로직만 작성
        # try-catch 불필요!
        result = await self.process_workflow(workflow_id)
        return result
```

---

## 📊 개선 효과

| 항목 | 개선 |
|------|------|
| 코드 중복 | 2개 엔드포인트에서 제거 |
| 일관성 | 에러 메시지 표준화 |
| 테스트 용이성 | Repository만 Mock 가능 |
| 유지보수성 | DB 쿼리 로직 한 곳에 집중 |

---

## 🚀 다음 단계: 추가 적용 가이드

### Step 1: 다른 Router에 적용

```python
# routers/workflows.py 예시
from app.repositories import WorkflowRepository

@router.get("/{workflow_id}")
async def get_workflow(workflow_id: UUID, db: Session = Depends(get_db)):
    workflow_repo = WorkflowRepository(db)
    workflow = workflow_repo.get_by_id_or_404(workflow_id)
    return workflow
```

### Step 2: 새 Repository 추가

```python
# repositories/ruleset_repository.py
from app.models.core import Ruleset
from app.repositories.base_repository import BaseRepository

class RulesetRepository(BaseRepository[Ruleset]):
    def __init__(self, db: Session):
        super().__init__(db, Ruleset)
    
    def get_by_id_or_404(self, ruleset_id: UUID) -> Ruleset:
        ruleset = self.db.query(Ruleset).filter(
            Ruleset.ruleset_id == ruleset_id
        ).first()
        if not ruleset:
            raise_not_found("Ruleset", str(ruleset_id))
        return ruleset
```

### Step 3: Decorator 활용

```python
# services/bi_service.py 예시
from app.utils.decorators import handle_service_errors

class BIService:
    @handle_service_errors(resource="BI query", operation="execute")
    async def execute_query(self, query: str):
        # 비즈니스 로직
        result = await self.db.execute(query)
        return result
```

---

## ✅ 검증 완료

- [x] 모든 import 성공
- [x] UserRepository 작동 확인
- [x] WorkflowRepository 작동 확인
- [x] Error utilities 작동 확인
- [x] Decorators 작동 확인
- [x] Auth router 로드 성공

---

## 📚 참고 자료

- Repository 패턴: [COMPREHENSIVE_ANALYSIS_REPORT.md](./COMPREHENSIVE_ANALYSIS_REPORT.md#1-repository-패턴-도입-800줄-감소)
- Error Handling: [COMPREHENSIVE_ANALYSIS_REPORT.md](./COMPREHENSIVE_ANALYSIS_REPORT.md#2-error-handling-통합-1600줄-감소)

---

## 🔄 롤백 방법

만약 문제가 발생하면:

```bash
# 새로 생성된 파일 삭제
rm -rf backend/app/repositories/
rm backend/app/utils/decorators.py

# auth.py 복구
git checkout backend/app/routers/auth.py

# errors.py에서 추가된 부분 제거 (마지막 ~80줄)
git checkout backend/app/utils/errors.py
```

---

**작성자:** Claude Code  
**버전:** v1.0  
**날짜:** 2026-01-21
