# 새 공급사/모듈 추가 가이드

## 개요

TriFlow AI에서 새로운 공급사 또는 산업별 모듈을 추가하는 방법을 설명합니다.

**핵심**: `modules/_registry.json`에 `domain_config`를 추가하기만 하면 AI 채팅이 자동으로 인식합니다.

## 빠른 시작 (5분 내 완료)

### 1단계: 모듈 레지스트리에 domain_config 추가

**파일**: `modules/_registry.json`

```json
{
  "version": "1.0.0",
  "modules": [
    {
      "module_code": "your_supplier_name",
      "name": "공급사명",
      "description": "공급사 설명",
      "category": "industry",
      "icon": "Package",

      "domain_config": {
        "keywords": [
          "키워드1", "키워드2", "키워드3"
        ],
        "schema_name": "your_schema_name",
        "tables": ["table1", "table2"],
        "route_to": "BI_GUIDE",
        "sample_queries": [
          "예시 질문 1",
          "예시 질문 2"
        ],
        "description": "데이터 설명"
      }
    }
  ]
}
```

### 2단계: 백엔드 재시작

```bash
# 백엔드 재시작 (자동 리로드)
# 또는 서버가 이미 실행 중이면 자동으로 리로드됨
```

### 3단계: 테스트

AI 채팅에서:
```
"키워드1을 포함한 데이터 보여줘"
```

→ 자동으로 `your_schema_name` 스키마 조회! ✅

---

## domain_config 상세 설명

### 필수 필드

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `keywords` | List[string] | 도메인 인식 키워드 | `["비타민", "원료", "배합비"]` |
| `schema_name` | string | PostgreSQL 스키마 이름 | `"korea_biopharm"` |
| `tables` | List[string] | 주요 테이블 목록 | `["recipe_metadata", "historical_recipes"]` |

### 선택 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `route_to` | string | `"BI_GUIDE"` | 라우팅 대상 (대부분 BI_GUIDE) |
| `sample_queries` | List[string] | `[]` | AI 학습용 예시 쿼리 |
| `description` | string | `null` | 데이터 설명 |

---

## 실제 예시

### 예시 1: 한국바이오팜 (현재 구현)

```json
{
  "module_code": "korea_biopharm",
  "name": "한국바이오팜",
  "description": "바이오팜 제품 배합비 데이터베이스",
  "category": "industry",
  "icon": "FlaskConical",

  "domain_config": {
    "keywords": [
      "비타민", "미네랄", "원료", "성분", "배합비",
      "정제", "캡슐", "시럽", "제형", "연질캡슐",
      "한국바이오팜", "바이오팜"
    ],
    "schema_name": "korea_biopharm",
    "tables": ["recipe_metadata", "historical_recipes"],
    "route_to": "BI_GUIDE",
    "sample_queries": [
      "비타민C를 포함한 제품 찾아줘",
      "정제 제품 10개 보여줘",
      "제형별 제품 수 분석해줘",
      "원료 사용 빈도 Top 20"
    ],
    "description": "한국바이오팜 배합비 및 제품 데이터"
  }
}
```

**AI 채팅 테스트**:
- "비타민C 포함 제품" → korea_biopharm 스키마 자동 조회 ✅
- "정제 제품 10개" → korea_biopharm.recipe_metadata 조회 ✅
- "배합비 데이터" → korea_biopharm 스키마 인식 ✅

---

### 예시 2: 품질 분석 모듈

```json
{
  "module_code": "quality_analytics",
  "name": "품질 분석",
  "description": "제품 품질 검사 및 분석",
  "category": "feature",
  "icon": "BarChart",

  "domain_config": {
    "keywords": [
      "품질", "검사", "시험", "규격", "불합격", "합격률"
    ],
    "schema_name": "quality_analytics",
    "tables": ["inspections", "test_results"],
    "route_to": "BI_GUIDE",
    "sample_queries": [
      "품질 검사 데이터 보여줘",
      "불합격률 분석해줘",
      "시험 결과 10개"
    ],
    "description": "품질 검사 및 시험 데이터"
  }
}
```

**AI 채팅 테스트**:
- "품질 검사 데이터" → quality_analytics 스키마 조회 ✅
- "불합격률 분석" → quality_analytics 스키마 인식 ✅

---

### 예시 3: 의약품 공급사 (PharmX)

```json
{
  "module_code": "pharmx_supplier",
  "name": "PharmX 공급사",
  "description": "PharmX 의약품 재고 및 처방 관리",
  "category": "industry",
  "icon": "Pill",

  "domain_config": {
    "keywords": [
      "PharmX", "의약품", "처방전", "약품", "처방", "재고"
    ],
    "schema_name": "pharmx",
    "tables": ["prescriptions", "inventory"],
    "route_to": "BI_GUIDE",
    "sample_queries": [
      "PharmX 재고 현황",
      "처방전 10개 보여줘",
      "의약품 재고 분석"
    ],
    "description": "PharmX 공급사 의약품 및 처방 데이터"
  }
}
```

**AI 채팅 테스트**:
- "PharmX 재고" → pharmx 스키마 조회 ✅
- "처방전 데이터" → pharmx 스키마 인식 ✅

---

## 키워드 선정 가이드

### 좋은 키워드 예시

✅ **도메인 특화 용어**
- 한국바이오팜: "비타민", "원료", "배합비", "제형"
- 품질 분석: "품질", "검사", "시험", "규격"
- 의약품: "처방전", "약품", "의약품"

✅ **회사/브랜드명**
- "한국바이오팜", "PharmX", "ABC공급사"

✅ **제품 타입**
- "정제", "캡슐", "시럽" (바이오팜)
- "처방약", "일반의약품" (의약품)

### 피해야 할 키워드 예시

❌ **너무 일반적인 단어**
- "데이터", "분석", "보기", "확인" → 다른 모듈과 충돌
- "제품", "회사" → 너무 광범위

❌ **제조 현장 용어**
- "온도", "압력", "센서" → core 스키마와 충돌
- "생산량", "불량률" → 기존 BI 기능과 충돌

❌ **중복 가능성 높은 단어**
- "관리", "시스템", "모듈"

---

## 키워드 우선순위

AI가 사용자 입력을 분석할 때:

1. **도메인 키워드 매칭 (최우선, confidence: 0.98)**
   - `domain_config.keywords`에 있는 단어 감지
   - 예: "비타민" → korea_biopharm 매칭

2. V7 규칙 기반 분류 (2순위)
   - "추이", "비교", "순위" 같은 일반 패턴

3. LLM fallback (3순위)
   - 애매한 경우 Claude가 판단

---

## 데이터베이스 스키마 설정

### Alembic Migration 생성

새 모듈의 스키마와 테이블을 생성하세요:

```python
# backend/alembic/versions/YYYYMMDD_your_module.py

def upgrade():
    # 스키마 생성
    op.execute("CREATE SCHEMA IF NOT EXISTS your_schema_name")

    # 테이블 생성
    op.create_table(
        'your_table',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        # ... 기타 컬럼들
        schema='your_schema_name'
    )

    # 인덱스
    op.create_index(
        'idx_your_table_tenant',
        'your_table',
        ['tenant_id'],
        schema='your_schema_name'
    )
```

### tenant_id 필수!

**모든 테이블에 tenant_id 컬럼 포함 필수**:
- Multi-tenant 보안
- 데이터 격리
- AI가 자동으로 필터링

---

## 동작 원리

### DomainRegistry 시스템

```
1. 백엔드 시작 시:
   ├─ DomainRegistry가 modules/_registry.json 로드
   ├─ domain_config가 있는 모듈만 등록
   └─ 메모리에 키워드 저장

2. AI 채팅 요청 시:
   ├─ V7IntentClassifier.classify() 호출
   ├─ 1차: DomainRegistry.match_domain() (키워드 매칭)
   │  └─ 매칭 성공 → confidence 0.98, route_to="BI_GUIDE"
   ├─ 2차: V7 규칙 기반 분류 (도메인 매칭 실패 시)
   └─ 3차: LLM fallback (규칙 실패 시)

3. BIPlannerAgent 실행 시:
   ├─ get_system_prompt() 호출
   ├─ DomainRegistry.generate_schema_docs() 호출
   ├─ 동적으로 스키마 정보 주입
   └─ AI가 해당 스키마 조회

4. SQL 실행 시:
   ├─ SafeQueryExecutor가 DomainRegistry.get_all_schemas() 호출
   ├─ 동적으로 허용된 스키마 확인
   └─ 스키마 접근 허용
```

---

## 전체 체크리스트

### Phase 1: 데이터베이스 준비
- [ ] PostgreSQL 스키마 생성
- [ ] Alembic migration 작성
- [ ] 테이블 생성 (tenant_id 필수!)
- [ ] 인덱스 추가
- [ ] 샘플 데이터 삽입

### Phase 2: 모듈 등록
- [ ] `modules/_registry.json` 수정
- [ ] `domain_config` 섹션 추가
- [ ] `keywords` 정의 (5-10개 권장)
- [ ] `schema_name`, `tables` 지정
- [ ] `sample_queries` 작성 (선택)

### Phase 3: 테스트
- [ ] 백엔드 재시작
- [ ] AI 채팅에서 키워드 테스트
- [ ] 스키마 자동 조회 확인
- [ ] SQL 쿼리 결과 검증

---

## 실전 예시: "ABC 식품" 공급사 추가

### 시나리오
ABC 식품 공급사의 레시피 데이터를 TriFlow AI에 통합하려고 합니다.

### Step 1: 스키마 생성

```sql
-- PostgreSQL
CREATE SCHEMA IF NOT EXISTS abc_foods;

CREATE TABLE abc_foods.recipes (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    recipe_name VARCHAR(500),
    category VARCHAR(100),
    ingredients JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_recipes_tenant ON abc_foods.recipes(tenant_id);
```

### Step 2: modules/_registry.json 수정

```json
{
  "module_code": "abc_foods",
  "name": "ABC 식품",
  "description": "ABC 식품 공급사 레시피 관리",
  "category": "industry",
  "icon": "ChefHat",

  "domain_config": {
    "keywords": [
      "ABC식품", "ABC", "레시피", "식품", "조리법", "재료"
    ],
    "schema_name": "abc_foods",
    "tables": ["recipes"],
    "route_to": "BI_GUIDE",
    "sample_queries": [
      "ABC 식품 레시피 10개 보여줘",
      "재료별 레시피 수 분석",
      "ABC 식품 데이터 보여줘"
    ],
    "description": "ABC 식품 공급사 레시피 및 재료 데이터"
  }
}
```

### Step 3: 테스트

AI 채팅:
```
사용자: "ABC 식품 레시피 10개 보여줘"

AI 응답:
- DomainRegistry가 "ABC" 키워드 감지
- abc_foods 스키마 자동 조회
- SELECT * FROM abc_foods.recipes LIMIT 10
- 결과 + 차트 반환
```

---

## 키워드 최적화 팁

### 1. 최소 5개, 최대 15개 권장

**이유**:
- 너무 적으면 (< 5개): 인식률 낮음
- 너무 많으면 (> 15개): 충돌 위험, 관리 어려움

### 2. 계층 구조로 정의

```json
"keywords": [
  // Tier 1: 브랜드/회사명 (최우선)
  "한국바이오팜", "바이오팜",

  // Tier 2: 도메인 고유 용어
  "배합비", "제형",

  // Tier 3: 일반 용어 (신중하게)
  "비타민", "원료", "성분"
]
```

### 3. 동의어 포함

```json
"keywords": [
  "레시피", "조리법",        // 동의어
  "재료", "원료", "성분",    // 유사 의미
  "ABC", "ABC식품"          // 약어 + 풀네임
]
```

### 4. 키워드 충돌 방지

**나쁜 예**:
```json
// 모듈 A
"keywords": ["제품", "데이터"]

// 모듈 B
"keywords": ["제품", "분석"]

→ "제품" 키워드로 충돌! 어느 모듈로 갈지 불명확
```

**좋은 예**:
```json
// 모듈 A
"keywords": ["한국바이오팜", "배합비", "제형"]

// 모듈 B
"keywords": ["ABC식품", "레시피", "조리법"]

→ 명확히 구분됨 ✅
```

---

## AI 채팅 동작 예시

### 사용자: "비타민C를 포함한 제품 찾아줘"

```
1. MetaRouterAgent 실행
   ├─ V7IntentClassifier.classify("비타민C를 포함한 제품 찾아줘")
   ├─ DomainRegistry.match_domain()
   │  └─ "비타민" 키워드 감지 → korea_biopharm 매칭!
   └─ 분류 결과:
      {
        "v7_intent": "CHECK",
        "route_to": "BI_GUIDE",
        "legacy_intent": "bi",
        "confidence": 0.98,
        "source": "domain_registry",
        "slots": {
          "domain": "korea_biopharm",
          "schema": "korea_biopharm"
        }
      }

2. BIPlannerAgent 실행
   ├─ get_system_prompt() 호출
   │  ├─ DomainRegistry.generate_schema_docs()
   │  ├─ korea_biopharm 스키마 정보 자동 추가
   │  └─ "비타민 키워드 → korea_biopharm 스키마 사용" 주입
   │
   ├─ AI가 프롬프트 이해:
   │  "사용자가 비타민을 언급 → korea_biopharm 스키마 사용해야 함"
   │
   └─ SQL 생성:
      SELECT DISTINCT
          rm.product_name,
          rm.formulation_type,
          hr.ingredient,
          hr.ratio
      FROM korea_biopharm.recipe_metadata rm
      JOIN korea_biopharm.historical_recipes hr ON rm.filename = hr.filename
      WHERE
          rm.tenant_id = :tenant_id
          AND hr.ingredient LIKE '%비타민C%'

3. SQL 실행
   ├─ SafeQueryExecutor.execute_safe_sql()
   ├─ get_all_schemas() → ['core', 'bi', 'rag', 'audit', 'korea_biopharm']
   ├─ korea_biopharm 허용 확인 ✅
   └─ 쿼리 실행 성공

4. 결과 반환
   ├─ 비타민C 포함 제품 목록
   ├─ 차트 생성
   └─ 사용자에게 표시
```

---

## 트러블슈팅

### 문제 1: AI가 내 모듈을 인식 못 함

**원인**: 키워드가 너무 일반적이거나 누락됨

**해결**:
```json
// 키워드 추가
"keywords": [
  "회사명",      // 브랜드명 추가
  "고유용어1",   // 도메인 특화 용어
  "고유용어2"
]
```

### 문제 2: 다른 모듈과 충돌

**원인**: 키워드 중복

**해결**:
```json
// 더 구체적인 키워드 사용
"keywords": [
  "ABC식품_레시피",  // 접두사 추가
  "ABC_재료"         // 명확한 구분
]
```

### 문제 3: Schema not allowed 에러

**원인**: DomainRegistry 로드 실패 또는 schema_name 오타

**확인**:
1. 백엔드 로그에서 `DomainRegistry loaded X domain configs` 확인
2. `schema_name`이 실제 PostgreSQL 스키마명과 일치하는지 확인

---

## 자주 묻는 질문 (FAQ)

### Q1: 기존 코드를 수정해야 하나요?
**A**: 아니요! `_registry.json`만 수정하면 됩니다.

### Q2: 백엔드를 재시작해야 하나요?
**A**: 네, DomainRegistry는 서버 시작 시 로드됩니다. 하지만 `--reload` 옵션이 있으면 자동 재시작됩니다.

### Q3: 여러 모듈이 같은 스키마를 공유할 수 있나요?
**A**: 네, `schema_name`을 동일하게 설정하면 됩니다. 단, 키워드는 중복되지 않게 주의하세요.

### Q4: 키워드를 나중에 추가/삭제할 수 있나요?
**A**: 네, `_registry.json` 수정 후 백엔드 재시작하면 됩니다.

### Q5: 100개 모듈을 추가하면 느려지나요?
**A**: 아니요. 키워드 매칭은 O(n)이고, 캐싱되므로 성능 문제 없습니다.

---

## 고급 기능

### 도메인별 프롬프트 커스터마이징 (향후)

```json
"domain_config": {
  "keywords": [...],
  "schema_name": "pharmx",
  "custom_prompt": "당신은 의약품 전문가입니다. 처방전 데이터를 분석할 때는..."
}
```

### 도메인별 권한 관리 (향후)

```json
"domain_config": {
  "keywords": [...],
  "required_role": "manager",  // 관리자만 접근
  "required_permission": "view_prescriptions"
}
```

---

## 참고 파일

- **DomainRegistry 구현**: `backend/app/services/domain_registry.py`
- **Intent Classifier**: `backend/app/agents/intent_classifier.py`
- **BIPlannerAgent**: `backend/app/agents/bi_planner.py`
- **모듈 레지스트리**: `modules/_registry.json`

---

## 요약

### 새 공급사 추가 = 5줄 코드!

```json
{
  "module_code": "your_name",
  "domain_config": {
    "keywords": ["키워드1", "키워드2"],
    "schema_name": "your_schema",
    "tables": ["table1"]
  }
}
```

### 자동으로 동작하는 것들
- ✅ Intent 분류
- ✅ 라우팅
- ✅ 스키마 접근 권한
- ✅ AI 프롬프트 생성
- ✅ 도구 enum 업데이트

**코드 수정 불필요, 100개 공급사도 문제없음!** 🚀
