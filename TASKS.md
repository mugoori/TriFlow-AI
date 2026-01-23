# Tasks & Progress

## 2026-01-23: AI 모델 설정 기능 구현 및 UI 정리

### 완료된 작업

#### 1. DB 기반 테넌트별 AI 모델 설정 구현
- **목적**: 다른 고객사 비용 절감 요구 대응 (Haiku는 Sonnet 대비 약 12배 저렴)
- **구현 내용**:
  - `settings_service.py`: AI 모델 설정 정의 추가 (`default_llm_model`, 에이전트별 모델)
  - `base_agent.py`: `get_model(context)` 메서드 추가 - 테넌트별 동적 모델 로딩
  - 모든 에이전트에서 하드코딩된 모델명 제거 (meta_router, bi_planner, workflow_planner, judgment_agent, learning_agent)
  - 서비스 클래스에서도 하드코딩 제거 (bi_chat_service, story_service, insight_service, judgment_policy)

#### 2. 설정 우선순위 체계
```
1. 에이전트별 테넌트 설정 (예: bi_planner_model for tenant-a)
2. 기본 테넌트 설정 (default_llm_model for tenant-a)
3. 글로벌 설정
4. 환경변수 (DEFAULT_LLM_MODEL)
5. 코드 기본값 (claude-sonnet-4-5-20250929)
```

#### 3. 프론트엔드 설정 UI 정리
- **제거된 항목** (사용자 설정 탭):
  - AI 모델 카드 (모델 선택, Max Tokens, Tenant ID) - localStorage만 사용, 실제 동작 안함
  - Backend 연결 카드 (연결 상태, API URL, 자동 재연결) - 실제 API 호출에 영향 없음

- **유지/추가된 항목** (관리자/운영 탭):
  - `AIModelConfigSection.tsx`: DB 기반 AI 모델 설정 컴포넌트
  - 프리셋 버튼: Sonnet (품질), 하이브리드, Haiku (비용)
  - 에이전트별 모델 설정 가능

#### 4. 수정된 파일 목록

**Backend:**
- `backend/app/agents/base_agent.py` - 동적 모델 로딩
- `backend/app/agents/meta_router.py` - 하드코딩 제거
- `backend/app/agents/bi_planner.py` - 하드코딩 제거
- `backend/app/agents/workflow_planner.py` - 하드코딩 제거
- `backend/app/agents/judgment_agent.py` - 하드코딩 제거
- `backend/app/agents/learning_agent.py` - 하드코딩 제거
- `backend/app/services/settings_service.py` - AI 모델 설정 정의
- `backend/app/services/bi_chat_service.py` - 하드코딩 제거
- `backend/app/services/story_service.py` - 하드코딩 제거
- `backend/app/services/insight_service.py` - 하드코딩 제거
- `backend/app/services/judgment_policy.py` - 하드코딩 제거

**Frontend:**
- `frontend/src/components/pages/SettingsPage.tsx` - UI 정리
- `frontend/src/components/settings/AIModelConfigSection.tsx` - 새 컴포넌트

### 검증 완료
- Haiku 프리셋 적용 후 백엔드 로그에서 `claude-3-haiku-20240307` 모델 사용 확인
- 설정 저장/로드 정상 동작 확인

### 하이브리드 접근법 권장
| 기능 | 권장 모델 | 이유 |
|------|-----------|------|
| Meta Router | Haiku | 규칙 기반 우선 처리 |
| Judgment Agent | Haiku | 단순 데이터 조회 |
| Learning Agent | Haiku | DB 집계 중심 |
| BI Planner (단순 SQL) | Haiku | 단일 테이블 쿼리 |
| BI Planner (복잡 SQL/차트/인사이트) | **Sonnet** | JOIN, 서브쿼리, JSON 구조 |
| Workflow Planner (복잡 DSL) | **Sonnet** | 중첩 노드 구조 |
