# Tasks & Progress

## 2026-01-26: BI Chat 날짜 파싱 및 바이오팜 도메인 키워드 확장

### 완료된 작업

#### 1. BI Chat 날짜 파싱 기능 구현
- **문제**: 사용자가 "2025년 12월 24일 생산 현황" 질문 시 날짜 인식 안됨
- **해결**: 자연어 날짜 파싱 후 데이터 조회, 날짜 미지정 시 최신 데이터 날짜 자동 선택

**지원 날짜 형식**:
- 오늘, 어제, 그제
- N일 전, N주 전, N개월 전
- YYYY년 MM월 DD일
- YYYY-MM-DD, YYYY/MM/DD

**수정 파일**:
- `backend/app/services/bi_chat_service.py`: `parse_date_from_message()` 함수 추가
- `backend/app/services/bi_data_collector.py`: `get_latest_data_date()` 메서드 추가
- `backend/app/services/bi_correlation_analyzer.py`: None 값 비교 오류 수정

#### 2. async_engine 호환성 문제 해결
- **문제**: `cannot import name 'async_engine' from 'app.database'`
- **해결**: `_AsyncEngineProxy` 클래스 추가로 역방향 호환성 유지
- **수정 파일**: `backend/app/database.py`

#### 3. 바이오팜 도메인 키워드 확장
- **문제**: "마그네슘", "아연" 등 성분 키워드가 MetaRouterAgent로 잘못 라우팅
- **해결**: `modules/_registry.json`에 추가 키워드 등록

**추가된 키워드**:
```
마그네슘, 아연, 칼슘, 철분, 오메가,
유산균, 프로바이오틱스, 콜라겐, 히알루론산,
루테인, 밀크씨슬, 레시피, 제품, 건강기능식품
```

### 테스트 결과

| 쿼리 | Agent | 결과 |
|------|-------|------|
| "비타민D3 성분이 들어간 제품 목록" | BIPlannerAgent | 96개 제품 검색 |
| "마그네슘 포함 레시피 검색" | BIPlannerAgent | 50개 제품 |
| "아연이 들어간 제품 중 최근 5개" | BIPlannerAgent | 5개 제품 |
| "2025년 12월 24일 생산 현황" | BI Chat | 날짜 파싱 후 데이터 조회 |

---

## 2026-01-23: BI 데이터 질의 도구 강제 호출 및 tenant_id 자동 주입

### 완료된 작업

#### 1. tenant_id 자동 주입 (멀티테넌트 보안 강화)
- **문제**: AI가 도구 호출 시 `tenant_id` 파라미터를 생략하거나 잘못 전달
- **해결**: BaseAgent에서 도구 실행 전 필수 파라미터 자동 주입
- **구현 내용**:
  - `base_agent.py`: `_current_context` 저장 및 `_ensure_required_context()` 메서드 추가
  - 모든 도구 호출에 `tenant_id` 자동 주입 (AI 실수 방지)

#### 2. BI 데이터 질의 시 도구 호출 강제
- **문제**: 자연어 질의("비타민 C 제품 알려줘")에 AI가 도구 호출 없이 텍스트만 응답
- **해결**: 2단계 강제 메커니즘 적용

**2-1. 코드 레벨 (agent_orchestrator.py)**:
```python
# BI 데이터 질의 키워드 확장
data_query_keywords = [
    "알려", "보여", "찾아", "검색", "조회",
    "레시피", "제품", "원료", "배합", "비타민", "제형",
    ...
]
if any(kw in msg_lower for kw in data_query_keywords):
    return {"type": "any"}  # tool_choice 강제
```

**2-2. 프롬프트 레벨 (bi_planner.md)**:
- 🚨 MANDATORY 섹션 추가 (도구 사용 필수 규칙)
- 절대 금지 사항 명시 (텍스트만 응답 금지)
- 즉시 실행 SQL 패턴 제공

#### 3. 한국어 응답 규칙 추가
- **문제**: AI가 영어로 응답 ("Great, the query executed successfully...")
- **해결**: bi_planner.md에 언어 규칙 섹션 추가
```markdown
## 🌐 언어 규칙 (LANGUAGE RULE)
**반드시 한국어로 응답하세요!**
```

#### 4. 수정된 파일 목록

**Backend:**
- `backend/app/agents/base_agent.py` - tenant_id 자동 주입
- `backend/app/prompts/bi_planner.md` - 도구 강제 + 한국어 규칙
- `backend/app/services/agent_orchestrator.py` - tool_choice 강제

**Frontend:**
- `frontend/src/types/agent.ts` - 모델 타입 추가

### 검증 완료
- "비타민 C 제품을 포함한 레시피 10개 알려줘" 질의 시 데이터 정상 반환
- tenant_id 자동 주입 로그 확인 (`Auto-injected tenant_id`)
- 한국어 응답 규칙 적용 대기 중

---

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
