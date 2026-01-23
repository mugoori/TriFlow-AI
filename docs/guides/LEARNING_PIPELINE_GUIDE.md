# Learning Pipeline 사용 가이드

> **작성일**: 2026-01-23
> **대상**: 개발자, 운영자, Approver
> **관련 스펙**: LRN-FR-020, LRN-FR-030

---

## 목차

1. [개요](#개요)
2. [Sample Curation](#1-sample-curation)
3. [Rule Extraction](#2-rule-extraction)
4. [Golden Sample Sets](#3-golden-sample-sets)
5. [전체 워크플로우](#4-전체-워크플로우)
6. [트러블슈팅](#5-트러블슈팅)

---

## 개요

Learning Pipeline은 사용자 피드백을 기반으로 AI 규칙을 자동으로 생성하는 시스템입니다.

### 구성 요소

```
피드백 수집
    ↓
샘플 큐레이션 (자동/수동)
    ↓
Decision Tree 학습
    ↓
Rhai 스크립트 생성
    ↓
규칙 테스트
    ↓
승인 및 배포
    ↓
Trust Model 연동
```

### 자동화 수준

- **자동 샘플 추출**: 매시간 자동 실행 (스케줄러)
- **Golden Sets 업데이트**: 품질 점수 기준 자동 선정
- **품질 점수 계산**: rating × confidence × recency 자동 계산

---

## 1. Sample Curation

### 1.1 자동 샘플 추출 (권장)

**스케줄러 자동 실행**: 매시간 자동으로 피드백에서 샘플 추출

**설정 확인**:
```bash
# 스케줄러 상태 확인
GET /api/v1/scheduler/jobs

# extract_learning_samples job이 active인지 확인
```

**추출 조건**:
- `rating >= 4` (긍정 피드백)
- `confidence >= 0.7` (신뢰도 기준)
- 최근 30일 이내
- 중복 제거 (MD5 해시 기반)

**품질 점수 계산 공식**:
```
quality_score = (rating / 5.0) × confidence × recency_factor

recency_factor = 1.0 - (age_days / 30.0)
```

---

### 1.2 수동 샘플 추출

**사용 시점**: 특정 조건의 샘플이 즉시 필요할 때

**API**: `POST /api/v1/samples/extract`

**요청 예시**:
```bash
curl -X POST http://localhost:8000/api/v1/samples/extract \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "min_rating": 4,
    "min_confidence": 0.8,
    "min_date": "2026-01-01T00:00:00Z",
    "limit": 100,
    "category": "threshold_adjustment",
    "dry_run": false
  }'
```

**파라미터**:
| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `min_rating` | int | 4 | 최소 평점 (1-5) |
| `min_confidence` | float | 0.7 | 최소 신뢰도 (0.0-1.0) |
| `min_date` | datetime | 30일 전 | 최소 날짜 |
| `limit` | int | 100 | 최대 추출 개수 |
| `category` | string | null | 카테고리 필터 |
| `dry_run` | bool | false | 미리보기 모드 |

**응답 예시**:
```json
{
  "extracted_count": 45,
  "skipped_duplicates": 12,
  "samples": [
    {
      "sample_id": "uuid-123",
      "category": "threshold_adjustment",
      "source_type": "feedback",
      "input_data": {
        "temperature": 25.5,
        "pressure": 1013
      },
      "expected_output": {
        "decision": "NORMAL",
        "confidence": 0.85
      },
      "quality_score": 0.82,
      "status": "pending",
      "created_at": "2026-01-23T10:00:00Z"
    }
  ]
}
```

---

### 1.3 샘플 관리

#### 목록 조회

**API**: `GET /api/v1/samples`

```bash
# 모든 샘플 조회
GET /api/v1/samples?page=1&page_size=50

# 카테고리 필터
GET /api/v1/samples?category=threshold_adjustment

# 상태 필터
GET /api/v1/samples?status=approved

# 품질 점수 필터
GET /api/v1/samples?min_quality=0.8

# 골든 샘플만
GET /api/v1/samples?is_golden=true
```

#### 상세 조회

```bash
GET /api/v1/samples/{sample_id}
```

#### 샘플 승인

**권한**: Approver, Admin만 가능

```bash
POST /api/v1/samples/{sample_id}/approve
```

**효과**:
- `status: pending` → `approved`
- Rule Extraction에서 사용 가능
- Golden Set 후보로 자동 고려

#### 샘플 거부

```bash
POST /api/v1/samples/{sample_id}/reject
{
  "reason": "데이터 품질 낮음"
}
```

---

### 1.4 통계 확인

**API**: `GET /api/v1/samples/stats`

```bash
curl http://localhost:8000/api/v1/samples/stats
```

**응답 예시**:
```json
{
  "total_samples": 1245,
  "approved_samples": 823,
  "pending_samples": 312,
  "rejected_samples": 110,
  "golden_samples": 89,
  "avg_quality_score": 0.78,
  "by_category": {
    "threshold_adjustment": 450,
    "field_correction": 395,
    "validation_failure": 400
  },
  "recent_extractions": 45
}
```

---

## 2. Rule Extraction

### 2.1 Decision Tree 학습 및 Rhai 생성

**API**: `POST /api/v1/rule-extraction/extract`

**요청 예시**:
```bash
curl -X POST http://localhost:8000/api/v1/rule-extraction/extract \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "category": "threshold_adjustment",
    "min_quality_score": 0.8,
    "min_samples": 20,
    "max_depth": 5,
    "min_samples_split": 10,
    "min_samples_leaf": 5,
    "dry_run": false
  }'
```

**파라미터**:
| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `category` | string | null | 샘플 카테고리 (null이면 전체) |
| `min_quality_score` | float | 0.7 | 최소 품질 점수 |
| `min_samples` | int | 20 | 최소 샘플 수 |
| `max_depth` | int | 5 | Decision Tree 최대 깊이 |
| `min_samples_split` | int | 10 | 노드 분할 최소 샘플 |
| `min_samples_leaf` | int | 5 | 리프 노드 최소 샘플 |
| `dry_run` | bool | false | 미리보기 모드 |

**응답 예시**:
```json
{
  "candidate_id": "uuid-456",
  "samples_used": 234,
  "tree_depth": 4,
  "feature_count": 6,
  "class_count": 3,
  "metrics": {
    "coverage": 0.95,
    "precision": 0.85,
    "recall": 0.82,
    "f1_score": 0.83
  },
  "rhai_preview": "if temperature > 25.0 {\n  if pressure < 1000.0 {\n    \"WARNING\"\n  } else {\n    \"NORMAL\"\n  }\n} else {\n  \"NORMAL\"\n}",
  "feature_importance": {
    "temperature": 0.45,
    "pressure": 0.32,
    "humidity": 0.15,
    "defect_rate": 0.08
  }
}
```

### 2.2 지원 특징 (Features)

Decision Tree 학습에 사용 가능한 특징:

| 특징 | 단위 | 범위 |
|------|------|------|
| `temperature` | °C | 0-100 |
| `pressure` | hPa | 800-1200 |
| `humidity` | % | 0-100 |
| `defect_rate` | % | 0-100 |
| `speed` | RPM | 0-5000 |
| `voltage` | V | 0-500 |
| `current` | A | 0-100 |
| `vibration` | mm/s | 0-20 |
| `noise_level` | dB | 0-120 |
| `cycle_time` | sec | 0-600 |

### 2.3 분류 클래스

Decision Tree가 예측하는 결과:
- `NORMAL`: 정상
- `WARNING`: 주의
- `CRITICAL`: 위험

---

### 2.4 규칙 후보 관리

#### 목록 조회

```bash
# 모든 후보
GET /api/v1/rule-extraction/candidates?page=1&page_size=20

# 상태 필터
GET /api/v1/rule-extraction/candidates?status=pending
GET /api/v1/rule-extraction/candidates?status=approved
GET /api/v1/rule-extraction/candidates?status=rejected
```

#### 상세 조회

```bash
GET /api/v1/rule-extraction/candidates/{candidate_id}
```

**응답**:
```json
{
  "candidate_id": "uuid-456",
  "tenant_id": "uuid-tenant",
  "ruleset_id": null,
  "generated_rule": "if temperature > 25.0 { ... }",
  "generation_method": "decision_tree",
  "coverage": 0.95,
  "precision": 0.85,
  "recall": 0.82,
  "f1_score": 0.83,
  "approval_status": "pending",
  "test_results": null,
  "created_at": "2026-01-23T10:00:00Z"
}
```

---

### 2.5 테스트 실행

**API**: `POST /api/v1/rule-extraction/candidates/{candidate_id}/test`

```bash
curl -X POST http://localhost:8000/api/v1/rule-extraction/candidates/{candidate_id}/test \
  -H "Content-Type: application/json" \
  -d '{
    "test_samples": [
      {
        "input": {"temperature": 26.5, "pressure": 1010},
        "expected_output": "WARNING"
      },
      {
        "input": {"temperature": 23.0, "pressure": 1015},
        "expected_output": "NORMAL"
      }
    ]
  }'
```

**응답**:
```json
{
  "total": 2,
  "passed": 2,
  "failed": 0,
  "accuracy": 1.0,
  "execution_time_ms": 45,
  "details": [
    {
      "input": {"temperature": 26.5, "pressure": 1010},
      "expected": "WARNING",
      "actual": "WARNING",
      "passed": true,
      "execution_time_ms": 12
    },
    {
      "input": {"temperature": 23.0, "pressure": 1015},
      "expected": "NORMAL",
      "actual": "NORMAL",
      "passed": true,
      "execution_time_ms": 10
    }
  ]
}
```

---

### 2.6 규칙 승인 및 배포

**권한**: Approver, Admin만 가능

**API**: `POST /api/v1/rule-extraction/candidates/{candidate_id}/approve`

```bash
curl -X POST http://localhost:8000/api/v1/rule-extraction/candidates/{candidate_id}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "온도-압력 경보 규칙 v1",
    "description": "Decision Tree 기반 자동 생성 (234 샘플, F1=0.83)"
  }'
```

**응답**:
```json
{
  "proposal_id": "uuid-789",
  "rule_name": "온도-압력 경보 규칙 v1",
  "confidence": 0.83,
  "status": "pending_review"
}
```

**효과**:
1. `AutoRuleCandidate.approval_status` → `approved`
2. `ProposedRule` 새로 생성됨
3. Learning 페이지 > Proposals 탭에 표시
4. Approver가 최종 승인 가능
5. 승인 후 Rulesets에 자동 추가

---

### 2.7 규칙 거부

```bash
POST /api/v1/rule-extraction/candidates/{candidate_id}/reject
{
  "reason": "정확도 부족 (F1 < 0.8)"
}
```

---

### 2.8 추출 통계

**API**: `GET /api/v1/rule-extraction/stats`

```bash
curl http://localhost:8000/api/v1/rule-extraction/stats
```

**응답**:
```json
{
  "total_candidates": 45,
  "pending_count": 12,
  "approved_count": 28,
  "rejected_count": 5,
  "testing_count": 0,
  "avg_f1_score": 0.81,
  "avg_coverage": 0.92,
  "recent_extractions": 8,
  "by_category": {
    "threshold_adjustment": 20,
    "field_correction": 15,
    "validation_failure": 10
  }
}
```

---

## 3. Golden Sample Sets

### 3.1 개요

Golden Sample Sets는 **최고 품질 샘플 모음**으로, 프롬프트 Few-shot 예시나 모델 평가에 사용됩니다.

### 3.2 자동 업데이트 (권장)

**API**: `POST /api/v1/golden-sets/{set_id}/auto-update`

```bash
curl -X POST http://localhost:8000/api/v1/golden-sets/{set_id}/auto-update \
  -H "Content-Type: application/json" \
  -d '{
    "min_quality_score": 0.85,
    "target_size": 100,
    "category": "threshold_adjustment"
  }'
```

**파라미터**:
| 필드 | 설명 |
|------|------|
| `min_quality_score` | 최소 품질 점수 (기본: 0.85) |
| `target_size` | 목표 샘플 수 (기본: 100) |
| `category` | 카테고리 필터 (선택) |

**응답**:
```json
{
  "set_id": "uuid-set",
  "added_count": 15,
  "removed_count": 8,
  "current_sample_count": 107
}
```

**동작 방식**:
1. 품질 점수 기준으로 Top N 샘플 선정
2. 기존 샘플 중 기준 미달 제거
3. 새 샘플 추가
4. `last_updated_at` 타임스탬프 업데이트

---

### 3.3 수동 샘플 추가/제거

**추가**:
```bash
POST /api/v1/golden-sets/{set_id}/samples
{
  "sample_id": "uuid-sample"
}
```

**제거**:
```bash
DELETE /api/v1/golden-sets/{set_id}/samples/{sample_id}
```

---

### 3.4 내보내기

**API**: `GET /api/v1/golden-sets/{set_id}/export`

**JSON 형식**:
```bash
GET /api/v1/golden-sets/{set_id}/export?format=json&include_metadata=true
```

**CSV 형식**:
```bash
GET /api/v1/golden-sets/{set_id}/export?format=csv&include_metadata=false
```

**파라미터**:
| 필드 | 설명 |
|------|------|
| `format` | `json` 또는 `csv` |
| `include_metadata` | 메타데이터 포함 여부 |

**응답**: 파일 다운로드 (Content-Disposition: attachment)

---

## 4. 전체 워크플로우

### 4.1 End-to-End 예시

```bash
# 1. 피드백 수집 (일반 사용자)
POST /api/v1/feedback
{
  "execution_id": "uuid-exec",
  "feedback_type": "positive",
  "rating": 5,
  "comment": "정확한 판정이었습니다"
}

# 2. 샘플 자동 추출 (매시간 자동 실행)
# → 스케줄러가 자동으로 실행
# → 수동 실행:
POST /api/v1/samples/extract
{
  "min_rating": 4,
  "limit": 100
}

# 3. 샘플 승인 (Approver)
POST /api/v1/samples/{sample_id}/approve

# 4. 규칙 추출 (Approver)
POST /api/v1/rule-extraction/extract
{
  "category": "threshold_adjustment",
  "min_samples": 20,
  "max_depth": 5
}

# 5. 후보 테스트 (선택적)
POST /api/v1/rule-extraction/candidates/{candidate_id}/test
{
  "test_samples": [...]
}

# 6. 후보 승인 (Approver)
POST /api/v1/rule-extraction/candidates/{candidate_id}/approve
{
  "rule_name": "자동 생성 규칙 v1",
  "description": "Decision Tree (234 샘플, F1=0.83)"
}

# 7. Proposal 최종 승인 (Admin)
# → Learning 페이지 > Proposals 탭에서 UI로 승인
# → 자동으로 Rulesets에 추가됨

# 8. Trust Level 자동 계산
# → Trust Service가 초기 Trust Level 0 (Proposed) 설정
# → 실행 이력 쌓이면 자동 승격
```

### 4.2 타임라인

```
Day 0: 피드백 수집 시작
    ↓
Day 1-7: 피드백 누적 (목표: 100개 이상)
    ↓
Day 7: 자동 샘플 추출 (스케줄러, 매시간)
    ↓
Day 8: Approver가 샘플 검토 및 승인
    ↓
Day 8: Rule Extraction 실행
    ↓
Day 8: 후보 테스트 및 승인
    ↓
Day 9: ProposedRule 최종 승인
    ↓
Day 9: Rulesets에 배포
    ↓
Day 10+: Trust Level 자동 승격 (실행 이력 기반)
```

---

## 5. 트러블슈팅

### 5.1 샘플이 추출되지 않음

**증상**: `extracted_count: 0`

**원인**:
1. 피드백 데이터가 부족
2. `min_rating` 기준이 너무 높음
3. 중복 샘플만 있음

**해결**:
```bash
# 1. 피드백 확인
GET /api/v1/feedback?rating_gte=4

# 2. 기준 낮추기
POST /api/v1/samples/extract
{
  "min_rating": 3,      # 4 → 3
  "min_confidence": 0.5 # 0.7 → 0.5
}

# 3. 중복 확인
GET /api/v1/samples?page=1&page_size=100
# → 이미 있는 샘플 확인
```

---

### 5.2 Rule Extraction 실패

**증상**: `ValueError: 샘플이 부족합니다`

**원인**: 승인된 샘플이 `min_samples` 미만

**해결**:
```bash
# 1. 승인된 샘플 확인
GET /api/v1/samples?status=approved

# 2. min_samples 낮추기
POST /api/v1/rule-extraction/extract
{
  "min_samples": 10  # 20 → 10
}

# 3. 더 많은 샘플 승인
POST /api/v1/samples/{sample_id}/approve
```

---

### 5.3 Decision Tree 정확도 낮음

**증상**: `f1_score < 0.7`

**원인**:
1. Tree가 너무 단순 (`max_depth` 낮음)
2. 샘플 품질 낮음
3. 특징 수 부족

**해결**:
```bash
# 1. max_depth 늘리기
POST /api/v1/rule-extraction/extract
{
  "max_depth": 10,          # 5 → 10
  "min_samples_leaf": 3     # 5 → 3 (더 세밀한 분할)
}

# 2. 품질 기준 올리기
POST /api/v1/rule-extraction/extract
{
  "min_quality_score": 0.9  # 0.7 → 0.9
}

# 3. 더 많은 특징 추가
# → input_data에 temperature, pressure, humidity 등 추가
```

---

### 5.4 Rhai 스크립트 컴파일 오류

**증상**: `RhaiEngine.compile() failed`

**원인**: Decision Tree → Rhai 변환 버그

**해결**:
```bash
# 1. 후보 상세 조회
GET /api/v1/rule-extraction/candidates/{candidate_id}

# 2. generated_rule 확인
# → Rhai 문법 오류 확인

# 3. 수동 수정 필요시
# → 후보 거절 후 수동으로 Ruleset 생성
POST /api/v1/rule-extraction/candidates/{candidate_id}/reject
{
  "reason": "Rhai 변환 오류, 수동 작성 필요"
}
```

---

### 5.5 Golden Set 자동 업데이트 안됨

**증상**: `added_count: 0, removed_count: 0`

**원인**: 품질 기준이 너무 높음

**해결**:
```bash
# 1. 현재 샘플 품질 확인
GET /api/v1/samples/stats
# → avg_quality_score 확인

# 2. min_quality_score 낮추기
POST /api/v1/golden-sets/{set_id}/auto-update
{
  "min_quality_score": 0.75  # 0.85 → 0.75
}
```

---

## 6. 성능 최적화

### 6.1 권장 설정

**일반 사용**:
```json
{
  "min_samples": 20,
  "max_depth": 5,
  "min_samples_split": 10,
  "min_samples_leaf": 5
}
```

**정확도 우선** (샘플 풍부):
```json
{
  "min_samples": 50,
  "max_depth": 10,
  "min_samples_split": 20,
  "min_samples_leaf": 10
}
```

**속도 우선** (샘플 부족):
```json
{
  "min_samples": 10,
  "max_depth": 3,
  "min_samples_split": 5,
  "min_samples_leaf": 3
}
```

---

### 6.2 성능 지표

| 작업 | 샘플 수 | 소요 시간 |
|------|---------|----------|
| 샘플 추출 | 100개 | ~500ms |
| Rule Extraction | 50개 | ~2초 |
| Rule Extraction | 200개 | ~8초 |
| 후보 테스트 | 10개 | ~100ms |

---

## 7. 권한 요구사항

| 작업 | 필요 권한 |
|------|----------|
| 샘플 조회 | Viewer 이상 |
| 샘플 추출 | Operator 이상 |
| 샘플 승인/거부 | Approver 이상 |
| 규칙 추출 | Approver 이상 |
| 후보 승인/거부 | Approver 이상 |
| 샘플 삭제 | Admin |
| Golden Set 관리 | Approver 이상 |

---

## 8. 프론트엔드 통합

### Learning 페이지 (이미 구현됨)

**위치**: `frontend/src/components/pages/LearningPage.tsx`

**4개 탭**:
1. **Feedback Stats**: 피드백 통계
2. **Proposals**: AI 제안 규칙 검토
3. **Samples**: 샘플 관리
4. **Rule Extraction**: 규칙 추출 실행

**서비스 레이어**:
- `frontend/src/services/sampleService.ts` - Sample CRUD
- `frontend/src/services/ruleExtractionService.ts` - Rule Extraction

---

## 9. 참조 문서

- [A-2-2_Integration_Learning_Chat_Spec.md](../specs/A-requirements/A-2-2_Integration_Learning_Chat_Spec.md) - 스펙 문서
- [07_A-2-2_Integration_Learning_Chat_Review.md](../spec-reviews/07_A-2-2_Integration_Learning_Chat_Review.md) - 스펙 검토
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - 일반 트러블슈팅

---

## 10. 체크리스트

### 초기 설정 (1회)
- [ ] 스케줄러 작동 확인 (`GET /api/v1/scheduler/jobs`)
- [ ] Golden Set 생성 (`POST /api/v1/golden-sets`)
- [ ] 권한 설정 (Approver 이상 할당)

### 일일 운영
- [ ] 피드백 수집 확인 (`GET /api/v1/feedback`)
- [ ] 샘플 통계 확인 (`GET /api/v1/samples/stats`)
- [ ] Pending 샘플 승인 (`POST /samples/{id}/approve`)

### 주간 운영
- [ ] Rule Extraction 실행 (샘플 50개 이상 시)
- [ ] 후보 테스트 실행
- [ ] 후보 승인 및 배포
- [ ] Golden Set 자동 업데이트

### 월간 운영
- [ ] 추출 통계 리뷰 (`GET /rule-extraction/stats`)
- [ ] 낮은 F1 score 후보 분석
- [ ] 샘플 품질 개선 방안 검토

---

**문서 버전**: 1.0
**최종 업데이트**: 2026-01-23
