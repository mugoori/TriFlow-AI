# Learning Pipeline API

TriFlow AI의 학습 파이프라인 API 레퍼런스입니다.

## 개요

학습 파이프라인은 사용자 피드백을 자동으로 학습하여 판단 규칙을 개선하는 시스템입니다.

**워크플로우**: `피드백 수집` → `샘플 추출` → `샘플 승인` → `규칙 추출` → `후보 테스트` → `후보 승인` → `ProposedRule 생성`

---

## 샘플 관리 (Sample Management)

### 1. 피드백에서 샘플 자동 추출

**Endpoint**: `POST /api/samples/extract`
**권한**: `operator`, `approver`, `admin`

피드백 로그에서 학습 샘플을 자동으로 추출합니다.

**Request Body**:
```json
{
  "days": 7,
  "dry_run": false,
  "min_quality_score": 0.6
}
```

**Parameters**:
- `days` (int): 과거 N일간의 피드백 추출 (기본값: 7)
- `dry_run` (bool): true면 실제 생성 없이 미리보기만 (기본값: false)
- `min_quality_score` (float): 최소 품질 점수 (0.0-1.0, 기본값: 0.6)

**Response**:
```json
{
  "extracted_count": 35,
  "skipped_duplicates": 5,
  "samples": [...],
  "dry_run": false
}
```

**Quality Score 계산**:
```
quality_score = (rating/5) × confidence × recency_factor

Where:
  - rating: 사용자 피드백 평점 (1-5)
  - confidence: 실행 신뢰도 (0.0-1.0, 기본값 0.7)
  - recency_factor: max(0.5, 1.0 - days_old/30)
```

---

### 2. 샘플 생성 (수동)

**Endpoint**: `POST /api/samples`
**권한**: `user`, `operator`, `approver`, `admin`

수동으로 학습 샘플을 생성합니다.

**Request Body**:
```json
{
  "category": "threshold_adjustment",
  "input_data": {
    "temperature": 75.5,
    "pressure": 102.3,
    "humidity": 55.0
  },
  "expected_output": {
    "status": "warning"
  },
  "source_type": "manual",
  "confidence": 0.9
}
```

**Categories**:
- `threshold_adjustment`: 임계값 조정
- `field_correction`: 필드 수정
- `validation_failure`: 검증 실패
- `general`: 일반

**Source Types**:
- `feedback`: 피드백에서 자동 추출
- `validation`: 검증 실패에서 추출
- `manual`: 수동 생성

---

### 3. 샘플 승인

**Endpoint**: `POST /api/samples/{sample_id}/approve`
**권한**: `approver`, `admin`

샘플을 승인하여 학습에 사용 가능하게 만듭니다.

**Response**:
```json
{
  "sample_id": "uuid",
  "status": "approved",
  "approved_at": "2026-01-19T10:30:00Z",
  "approved_by": "user-uuid"
}
```

---

### 4. 샘플 목록 조회

**Endpoint**: `GET /api/samples`
**권한**: 모든 인증된 사용자

**Query Parameters**:
- `category` (str): 카테고리 필터
- `status` (str): 상태 필터 (pending, approved, rejected, archived)
- `source_type` (str): 소스 타입 필터
- `min_quality` (float): 최소 품질 점수
- `page` (int): 페이지 번호 (기본값: 1)
- `page_size` (int): 페이지 크기 (기본값: 20)

**Response**:
```json
{
  "samples": [...],
  "total": 150,
  "page": 1,
  "page_size": 20
}
```

---

### 5. 샘플 통계

**Endpoint**: `GET /api/samples/stats`
**권한**: 모든 인증된 사용자

**Response**:
```json
{
  "total": 150,
  "by_status": {
    "pending": 45,
    "approved": 80,
    "rejected": 15,
    "archived": 10
  },
  "by_category": {
    "threshold_adjustment": 60,
    "field_correction": 40,
    "validation_failure": 30,
    "general": 20
  },
  "avg_quality_score": 0.72
}
```

---

## 규칙 추출 (Rule Extraction)

### 1. 규칙 추출 (Decision Tree 학습)

**Endpoint**: `POST /api/rule-extraction/extract`
**권한**: `approver`, `admin`

승인된 샘플에서 Decision Tree를 학습하고 Rhai 규칙을 생성합니다.

**Request Body**:
```json
{
  "category": "threshold_adjustment",
  "min_samples": 20,
  "max_depth": 5,
  "min_samples_split": 20,
  "test_size": 0.2
}
```

**Parameters**:
- `category` (str, optional): 특정 카테고리만 학습 (null이면 전체)
- `min_samples` (int): 최소 샘플 수 (기본값: 20)
- `max_depth` (int): Decision Tree 최대 깊이 (기본값: 5)
- `min_samples_split` (int): 노드 분할 최소 샘플 (기본값: 20)
- `test_size` (float): 테스트 셋 비율 (기본값: 0.2)

**Response**:
```json
{
  "candidate_id": "uuid",
  "generated_rule": "fn check(input) { ... }",
  "metrics": {
    "coverage": 0.85,
    "precision": 0.82,
    "recall": 0.78,
    "f1_score": 0.80,
    "accuracy": 0.83
  },
  "feature_importance": {
    "temperature": 0.45,
    "pressure": 0.30,
    "humidity": 0.15,
    "defect_rate": 0.10
  },
  "sample_count": 120,
  "approval_status": "pending"
}
```

**Metrics 설명**:
- `coverage`: 전체 샘플 중 규칙이 처리할 수 있는 비율
- `precision`: 규칙이 맞다고 판단한 것 중 실제로 맞는 비율
- `recall`: 실제 정답 중 규칙이 찾아낸 비율
- `f1_score`: precision과 recall의 조화평균
- `accuracy`: 전체 정확도

---

### 2. 후보 목록 조회

**Endpoint**: `GET /api/rule-extraction/candidates`
**권한**: 모든 인증된 사용자

**Query Parameters**:
- `status` (str): 승인 상태 필터 (pending, approved, rejected, testing)
- `category` (str): 카테고리 필터
- `min_coverage` (float): 최소 커버리지
- `page` (int): 페이지 번호
- `page_size` (int): 페이지 크기

---

### 3. 후보 테스트

**Endpoint**: `POST /api/rule-extraction/candidates/{candidate_id}/test`
**권한**: `approver`, `admin`

생성된 Rhai 규칙을 테스트 샘플로 검증합니다.

**Request Body**:
```json
{
  "test_samples": [
    {
      "input": {
        "temperature": 75.0,
        "pressure": 100.0,
        "humidity": 50.0,
        "defect_rate": 0.05
      },
      "expected_output": {
        "status": "normal"
      }
    }
  ]
}
```

**Response**:
```json
{
  "test_count": 10,
  "passed": 8,
  "failed": 2,
  "accuracy": 0.80,
  "test_results": [
    {
      "sample_index": 0,
      "input": {...},
      "expected": "normal",
      "predicted": "normal",
      "correct": true,
      "confidence": 0.85
    }
  ]
}
```

---

### 4. 후보 승인

**Endpoint**: `POST /api/rule-extraction/candidates/{candidate_id}/approve`
**권한**: `approver`, `admin`

후보를 승인하고 ProposedRule을 생성합니다.

**Request Body**:
```json
{
  "rule_name": "Temperature-based Classification Rule",
  "description": "Auto-extracted from 120 feedback samples",
  "deploy_immediately": false
}
```

**Response**:
```json
{
  "candidate_id": "uuid",
  "proposal_id": "uuid",
  "rule_name": "Temperature-based Classification Rule",
  "status": "approved",
  "approved_at": "2026-01-19T10:30:00Z",
  "approved_by": "user-uuid"
}
```

**생성된 ProposedRule**:
- `source_type`: "auto_extraction"
- `status`: "pending" (배포 워크플로우로 이동)
- `rhai_script`: 후보의 generated_rule 복사

---

### 5. 후보 거절

**Endpoint**: `POST /api/rule-extraction/candidates/{candidate_id}/reject`
**권한**: `approver`, `admin`

**Request Body**:
```json
{
  "reason": "Accuracy too low for production use"
}
```

---

### 6. 통계 조회

**Endpoint**: `GET /api/rule-extraction/stats`
**권한**: 모든 인증된 사용자

**Response**:
```json
{
  "total_candidates": 45,
  "by_status": {
    "pending": 8,
    "approved": 28,
    "rejected": 7,
    "testing": 2
  },
  "avg_coverage": 0.78,
  "avg_precision": 0.82,
  "avg_f1_score": 0.79
}
```

---

## 골든 샘플셋 (Golden Sample Sets)

### 1. 골든셋 생성

**Endpoint**: `POST /api/golden-sets`
**권한**: `approver`, `admin`

**Request Body**:
```json
{
  "name": "High-Quality Threshold Adjustments",
  "description": "Curated samples for threshold tuning",
  "category": "threshold_adjustment",
  "min_quality_score": 0.8,
  "max_samples": 100,
  "auto_update": true
}
```

---

### 2. 골든셋 자동 업데이트

**Endpoint**: `POST /api/golden-sets/{set_id}/auto-update`
**권한**: `approver`, `admin`

품질 기준을 충족하는 샘플을 자동으로 추가합니다.

**Request Body**:
```json
{
  "force": false
}
```

**Parameters**:
- `force` (bool): true면 max_samples 제한 무시 (기본값: false)

**Response**:
```json
{
  "added_count": 15,
  "removed_count": 2,
  "current_sample_count": 85
}
```

**자동 업데이트 로직**:
1. 품질 점수 미달 샘플 제거 (force=false인 경우만)
2. 승인된 샘플 중 품질 기준 충족 샘플 추가
3. max_samples 제한 준수 (품질 점수 높은 순)

---

### 3. 골든셋 내보내기

**Endpoint**: `GET /api/golden-sets/{set_id}/export`
**권한**: `approver`, `admin`

**Query Parameters**:
- `format` (str): "json" 또는 "csv" (기본값: "json")
- `include_metadata` (bool): 메타데이터 포함 여부 (기본값: true)

**Response**: 파일 다운로드 (JSON 또는 CSV)

**JSON 형식 예시**:
```json
{
  "metadata": {
    "set_id": "uuid",
    "name": "High-Quality Samples",
    "sample_count": 85,
    "exported_at": "2026-01-19T10:30:00Z"
  },
  "samples": [
    {
      "input": {...},
      "expected_output": {...},
      "metadata": {
        "sample_id": "uuid",
        "category": "threshold_adjustment",
        "quality_score": 0.85,
        "confidence": 0.9
      }
    }
  ]
}
```

---

## 권한 매트릭스

| 역할 | 샘플 생성 | 샘플 추출 | 샘플 승인 | 규칙 추출 | 후보 승인 | 샘플 삭제 |
|------|:---------:|:---------:|:---------:|:---------:|:---------:|:---------:|
| **VIEWER** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **USER** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **OPERATOR** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **APPROVER** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **ADMIN** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 에러 코드

| HTTP Status | 설명 |
|-------------|------|
| `200 OK` | 요청 성공 |
| `201 Created` | 리소스 생성 성공 |
| `204 No Content` | 삭제 성공 |
| `400 Bad Request` | 잘못된 요청 (품질 점수 범위 등) |
| `401 Unauthorized` | 인증 필요 |
| `403 Forbidden` | 권한 부족 |
| `404 Not Found` | 리소스 없음 |
| `422 Unprocessable Entity` | 검증 실패 |
| `500 Internal Server Error` | 서버 오류 |

---

## 사용 예시

### 예시 1: 피드백에서 샘플 추출 및 승인

```bash
# 1. 샘플 추출 (Operator 역할 필요)
curl -X POST http://localhost:8000/api/samples/extract \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "days": 7,
    "dry_run": false,
    "min_quality_score": 0.6
  }'

# 2. 샘플 목록 조회
curl http://localhost:8000/api/samples?status=pending&page=1&page_size=20 \
  -H "Authorization: Bearer $TOKEN"

# 3. 샘플 승인 (Approver 역할 필요)
curl -X POST http://localhost:8000/api/samples/{sample_id}/approve \
  -H "Authorization: Bearer $TOKEN"
```

### 예시 2: 규칙 추출 및 테스트

```bash
# 1. 규칙 추출 (Approver 역할 필요)
curl -X POST http://localhost:8000/api/rule-extraction/extract \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "threshold_adjustment",
    "min_samples": 20,
    "max_depth": 5
  }'

# 2. 후보 테스트
curl -X POST http://localhost:8000/api/rule-extraction/candidates/{candidate_id}/test \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "test_samples": [
      {
        "input": {"temperature": 75.0, "pressure": 100.0},
        "expected_output": {"status": "normal"}
      }
    ]
  }'

# 3. 후보 승인
curl -X POST http://localhost:8000/api/rule-extraction/candidates/{candidate_id}/approve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "Auto-Generated Rule",
    "description": "Extracted from 120 samples",
    "deploy_immediately": false
  }'
```

### 예시 3: 골든 샘플셋 관리

```bash
# 1. 골든셋 생성 (Approver 역할 필요)
curl -X POST http://localhost:8000/api/golden-sets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Quality Samples",
    "min_quality_score": 0.8,
    "max_samples": 100,
    "auto_update": true
  }'

# 2. 자동 업데이트 트리거
curl -X POST http://localhost:8000/api/golden-sets/{set_id}/auto-update \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"force": false}'

# 3. JSON 내보내기
curl http://localhost:8000/api/golden-sets/{set_id}/export?format=json \
  -H "Authorization: Bearer $TOKEN" \
  -o golden_samples.json
```

---

## 스케줄러 작업

### 자동 실행되는 백그라운드 작업

#### 1. 샘플 자동 추출
- **Job ID**: `auto_extract_samples`
- **실행 주기**: 6시간 (설정 가능)
- **조건**: `learning_auto_extract_enabled = true`
- **동작**: 모든 테넌트의 최근 1일 피드백에서 샘플 추출

#### 2. 골든셋 자동 업데이트
- **Job ID**: `auto_update_golden_sets`
- **실행 주기**: 24시간
- **조건**: `learning_golden_set_auto_update = true`
- **동작**: 모든 활성 골든셋에 고품질 샘플 자동 추가

---

## 관련 문서

- [Learning Workflow User Guide](../user-guide/learning-workflow.md)
- [RBAC Specification](../specs/B-design/B-3-4-RBAC.md)
- [Sample Curation Spec (LRN-FR-020)](../specs/implementation/LRN-FR-020-Sample-Curation-Service.md)
- [Rule Extraction Spec (LRN-FR-030)](../specs/implementation/LRN-FR-030-Rule-Extraction-Service.md)
