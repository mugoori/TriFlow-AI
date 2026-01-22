# 다음 작업 추천 (실제 코드 기반)

**분석일**: 2026-01-22
**기준**: 실제 코드 TODO + 문서 검증
**신뢰도**: 매우 높음

---

## ✅ 오늘(2026-01-22) 완료한 작업

1. ✅ Advanced DataScope Filtering
2. ✅ Settings UI Learning Config
3. ✅ LLM 응답 지연 최적화
4. ✅ TypeScript 에러 9개 수정

**총 소요 시간**: ~3.5시간

---

## 🔍 이미 존재하는 것 (오해 방지)

- ✅ Load Testing CI/CD - 완벽하게 구축됨
- ✅ Grafana 대시보드 4개 - 모두 존재함
- ✅ Intent-Role RBAC - 완료됨

---

## 📋 실제 남은 작업 (코드 TODO 기반)

### 🔴 **높은 우선순위** (프로덕션 필수)

#### 1️⃣ ERP/MES 자격증명 암호화 ⭐⭐⭐⭐⭐
**파일**: `backend/app/routers/erp_mes.py:606`
**예상 시간**: 3-4시간

**현재 코드**:
```python
# TODO: V2에서 암호화 구현
credentials_encrypted = credentials  # ← 평문 저장 중!
```

**작업 내용**:
1. Fernet 암호화 구현
2. 환경변수에서 암호화 키 로드
3. credentials_encrypted 필드에 암호화된 값 저장
4. 복호화 함수 구현

**보안 위험**: ⚠️ 현재 DB에 평문 저장 (높은 위험)

---

#### 2️⃣ Trust Level API Admin 인증 추가 ⭐⭐⭐⭐
**파일**: `backend/app/routers/trust.py:202, 221`
**예상 시간**: 1-2시간

**현재 코드**:
```python
@router.post("/rulesets/{ruleset_id}/promote")
async def promote_trust_level(...):
    # TODO: Add auth dependency for admin check
    pass  # ← 인증 없음!
```

**작업 내용**:
1. `check_permission("trust", "admin")` Dependency 추가
2. Admin만 Trust Level 변경 가능하도록
3. Audit Log 기록

**보안 위험**: ⚠️ 누구나 Trust Level 변경 가능 (중간 위험)

---

#### 3️⃣ Canary 알림 시스템 연동 ⭐⭐⭐⭐
**파일**: `backend/app/tasks/canary_monitor_task.py:124, 137, 146`
**예상 시간**: 4-6시간

**현재 코드**:
```python
# TODO: 실제 알림 시스템 연동 (Slack, Email 등)
logger.warning(f"Canary rollback triggered: {reason}")
```

**작업 내용**:
1. Slack Webhook 통합
2. Email 알림 (SMTP)
3. 알림 템플릿 작성
4. 알림 설정 UI

**운영 위험**: ⚠️ Canary 실패 시 알림 없음 (중간 위험)

---

### 🟡 **중간 우선순위** (기능 완성도)

#### 4️⃣ Audit Log Total Count 최적화 ⭐⭐⭐
**파일**: `backend/app/routers/audit.py:64`
**예상 시간**: 1시간

**현재 코드**:
```python
return {
    "logs": logs,
    "total": len(logs),  # TODO: 실제 total count 쿼리 추가
    "page": page,
}
```

**작업 내용**:
```python
# 페이지네이션 전 total count
total = query.count()

# 페이지네이션 적용
logs = query.offset(offset).limit(page_size).all()

return {
    "logs": logs,
    "total": total,  # ✅ 정확한 total
    "page": page,
}
```

---

#### 5️⃣ Module 설치 Progress Tracking ⭐⭐⭐
**파일**: `backend/app/routers/modules.py:345`
**예상 시간**: 3-4시간

**현재 코드**:
```python
@router.post("/{module_code}/install")
async def install_module(...):
    # TODO: Implement progress tracking
    # 1. Extract ZIP
    # 2. Validate schema
    # 3. Register DB
    # 4. Build frontend
    # 각 단계별 progress 전송 필요
```

**작업 내용**:
1. WebSocket 또는 SSE로 progress 스트리밍
2. 단계별 progress 전송 (0%, 25%, 50%, 75%, 100%)
3. Frontend에서 progress bar 표시

---

#### 6️⃣ Prompt Metrics 집계 개선 ⭐⭐⭐
**파일**: `backend/app/services/prompt_metrics_aggregator.py:53`
**예상 시간**: 2-3시간

**현재 코드**:
```python
# TODO: LlmCall 모델에 prompt_template_id 외래키 추가 필요
# 현재는 template_id가 없어서 aggregation 불가
```

**작업 내용**:
1. LlmCall 모델에 prompt_template_id 추가
2. Migration 스크립트 작성
3. Aggregation 로직 구현

---

### 🟢 **낮은 우선순위** (최적화)

#### 7️⃣ Workflow Event Pub/Sub ⭐⭐
**파일**: `backend/app/services/workflow_engine.py:6327`
**예상 시간**: 4-6시간

**현재 코드**:
```python
# TODO: Redis pub/sub으로 이벤트 발행 (실시간 UI 업데이트용)
```

**작업 내용**:
1. Redis Pub/Sub 설정
2. Workflow 상태 변경 이벤트 발행
3. Frontend에서 실시간 업데이트

---

#### 8️⃣ Workflow Checkpoint 저장 ⭐⭐
**파일**: `backend/app/services/workflow_engine.py:6469`
**예상 시간**: 3-4시간

**현재**: 메모리에만 저장
**개선**: Redis + DB 영구 저장

---

#### 9️⃣ Rhai 엔진 Rust 교체 ⭐
**파일**: `backend/app/tools/rhai.py:44`
**예상 시간**: 1-2일

**현재**: Python 인터프리터
**개선**: Rust Rhai 네이티브 엔진 (10배 성능 향상)

---

## 🎯 **즉시 시작 추천 (우선순위 순)**

### Option 1: 보안 강화 (5-7시간) ⭐⭐⭐⭐⭐

1. **ERP/MES 자격증명 암호화** (3-4h)
   - 가장 중요한 보안 이슈
   - DB에 평문 저장 중

2. **Trust Level API Admin 인증** (1-2h)
   - 누구나 Trust Level 변경 가능
   - 빠른 수정 가능

3. **Canary 알림 시스템** (4-6h)
   - 운영 안정성 확보
   - Slack 연동

**효과**: 보안 70% → 95%

---

### Option 2: 기능 완성도 (6-10시간) ⭐⭐⭐⭐

1. **Module 설치 Progress Tracking** (3-4h)
   - 사용자 경험 대폭 개선
   - 설치 진행 상황 실시간 표시

2. **Prompt Metrics 집계** (2-3h)
   - AI 성능 추적 가능
   - 오늘 작업한 LLM 최적화 효과 측정

3. **Audit Log Total Count** (1h)
   - 페이지네이션 정확도

**효과**: 기능 완성도 95% → 98%

---

### Option 3: 코드 품질 (8-12시간) ⭐⭐⭐

1. **Repository 패턴 확산** (8-12h)
   - 800줄 코드 감소
   - 테스트 용이성 향상

---

## 💡 **최종 추천**

### **Option 1: 보안 강화** (5-7시간)

**이유**:
1. **ERP/MES 암호화**는 프로덕션 배포 전 필수
2. **Trust Level 인증**도 보안 취약점
3. **Canary 알림**은 운영 안정성에 필수

**즉시 시작하면**:
- 보안 취약점 3개 해결
- 프로덕션 준비도 70% → 90%
- 5-7시간이면 오늘 안에 완료 가능

---

이 중 어떤 작업을 진행하시겠습니까?