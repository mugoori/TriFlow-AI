# 🎯 다음 작업 우선순위 추천

**분석 일시**: 2026-01-22 (저녁)
**현재 상태**: 기능 구현율 90%, 프로덕션 준비도 97%

---

## 📊 현재 상황 분석

### ✅ 오늘 완료 (8개)
- 보안 강화 (2개)
- UX 개선 (2개)
- 운영 안정성 (1개)
- AI 개선 (1개)
- BI 준비 (2개)

### ⏸️ 남은 주요 작업
- Workflow Engine TODO (3개)
- Judgment Replay (1개)
- ETL 자동화 (1개)
- Module Progress (1개)

---

## 🎯 다음 작업 Top 5 추천

### 1️⃣ **Workflow 롤백 구현** (2-3시간) ⭐⭐⭐⭐⭐

**파일**: workflow_engine.py:5891

**기능**:
```python
async def _rollback_workflow(workflow_id, version):
    # workflow_versions 테이블에서 이전 버전 조회
    # 현재 Workflow를 이전 버전으로 복원
    # 롤백 이력 기록
```

**사용 사례**:
```
상황: 새 Workflow v3 배포 → 버그 발견!

Before:
- 개발자가 수동으로 DB 접속
- SQL UPDATE로 수동 복원
- 30분 소요

After:
- Admin이 "Rollback to v2" 버튼 클릭
- 자동 복원
- 5초 소요 ✅
```

**우선순위 근거**:
- 운영 안정성 핵심
- 빠른 복구 = MTTR 감소
- Canary 롤백과 시너지
- 오늘 Redis Pub/Sub 완료 → 롤백 이벤트도 실시간 표시 가능

---

### 2️⃣ **Checkpoint 영구 저장** (2-3시간) ⭐⭐⭐⭐⭐

**파일**: workflow_engine.py:6469

**기능**:
```python
async def save_checkpoint(instance_id, node_id, state):
    # 1. 메모리 저장 (빠른 접근)
    # 2. Redis 저장 (중간 지속성, TTL 1시간)
    # 3. DB 저장 (영구 보관)
```

**사용 사례**:
```
상황: 30분 걸리는 Workflow 실행 중
      20분 시점에 서버 재시작

Before:
- Checkpoint가 메모리에만 있음
- 20분 작업 날아감
- 처음부터 다시 실행 (30분)

After:
- Redis/DB에서 마지막 Checkpoint 조회
- 20분 지점부터 재개
- 10분만 더 실행 (절약: 20분) ✅
```

**우선순위 근거**:
- 긴 Workflow 안정성
- 서버 재시작 대응
- Redis 재사용 (오늘 구현)
- Workflow 롤백과 함께 완성도 향상

---

### 3️⃣ **Judgment Replay 구현** (3-4시간) ⭐⭐⭐⭐

**파일**: 신규 (judgment_replay_service.py)

**스펙 요구**: A-2-1 JUD-FR-070

**기능**:
```python
async def replay_judgment(execution_id):
    # 1. 과거 execution_id로 입력 데이터 조회
    # 2. 동일 입력으로 현재 Ruleset 재실행
    # 3. 결과 비교 (이전 vs 현재)
    # 4. 차이 분석
```

**사용 사례**:
```
상황: Rule 버전 업그레이드 후 결과 검증

"execution-123"의 판정:
- 이전 Rule v1: "normal"
- 현재 Rule v2: "warning" (변경됨!)

→ 차이 원인 분석
→ Rule v2 검증
→ A/B 테스트
```

**우선순위 근거**:
- 스펙 필수 요구사항
- Rule 버전 관리 핵심
- Canary 배포와 시너지
- Judgment Engine 86% → 100%

---

### 4️⃣ **ETL 파이프라인 구현** (4-6시간) ⭐⭐⭐⭐

**파일**: 신규 (etl_service.py)

**기능**:
```python
class ETLService:
    async def run_raw_to_fact_daily_production():
        # Mock API 데이터 → FACT 변환
        # core.erp_mes_data → bi.fact_daily_production

    async def run_daily_etl_batch():
        # 일일 배치 (어제 데이터 처리)

    async def schedule_etl():
        # Celery Beat 스케줄 (매일 새벽 2시)
```

**사용 사례**:
```
현재:
- Mock API로 데이터 생성
- 수동 SQL로 FACT 변환
- 번거로움

After:
- Mock API로 데이터 생성
- 자동으로 FACT 변환 (매일 새벽)
- BI에서 즉시 조회 가능 ✅
```

**우선순위 근거**:
- BI 데이터 파이프라인 완성
- 오늘 BI 시드 완료 → 자연스러운 다음 단계
- 자동화 = 운영 효율성

---

### 5️⃣ **Module 설치 Progress** (3-4시간) ⭐⭐⭐⭐

**파일**: routers/modules.py:345

**기능**:
```python
@router.post("/{module_code}/install")
async def install_module(module_code):
    # 설치 단계별 이벤트 발행
    emit_progress("extracting", 25%)
    emit_progress("validating", 50%)
    emit_progress("building", 75%)
    emit_progress("completed", 100%)
```

**사용 사례**:
```
사용자: "Quality Analytics 모듈 설치" 클릭

Before:
- "설치 중..." (5분간 화면 고정)
- 언제 끝나는지 모름

After:
- ✅ ZIP 압축 해제 중... (25%)
- ✅ 스키마 검증 중... (50%)
- ✅ Frontend 빌드 중... (75%)
- ✅ 설치 완료! (100%)
```

**우선순위 근거**:
- 사용자 체감 효과 큼
- 오늘 WebSocket 구현 → 재사용
- Workflow Progress와 동일 패턴

---

## 💡 시나리오별 추천

### 시나리오 1: "Workflow를 완성하고 싶어요"

**추천**: 1번 + 2번 (4-6시간)
```
1. Workflow 롤백 (2-3h)
2. Checkpoint 영구 저장 (2-3h)

완료 후:
✅ Workflow Engine 78% → 95%
✅ 운영 안정성 대폭 향상
```

---

### 시나리오 2: "빠르게 여러 개 완성하고 싶어요"

**추천**: 1번 + 2번 + 5번 (7-10시간)
```
1. Workflow 롤백 (2-3h)
2. Checkpoint 영구 (2-3h)
3. Module Progress (3-4h)

완료 후:
✅ 3개 기능 완성
✅ Workflow + Module 개선
```

---

### 시나리오 3: "스펙 준수를 완성하고 싶어요"

**추천**: 3번 + 4번 (7-10시간)
```
1. Judgment Replay (3-4h)
2. ETL 자동화 (4-6h)

완료 후:
✅ 스펙 필수 항목 완성
✅ Judgment 100%, BI 자동화
```

---

### 시나리오 4: "빠른 작업만 하고 싶어요"

**추천**: 1번 단독 (2-3시간)
```
1. Workflow 롤백 (2-3h)

완료 후:
✅ 빠른 복구 능력
✅ 운영 안정성 향상
```

---

## 🎯 **최종 추천: Option 1 + 2 (Workflow 완성)**

### Workflow 롤백 + Checkpoint 영구 저장 (4-6시간)

**추천 이유**:

1. ✅ **Workflow Engine 완성**
   - 78% → 95% (거의 완성)
   - TODO 4개 → 1개 (ML 모델만 남음)

2. ✅ **오늘 작업과 시너지**
   - Redis Pub/Sub 완료 → 재사용
   - Redis Client 구현 → 재사용
   - 실시간 이벤트 → 롤백 알림도 표시

3. ✅ **운영 안정성 핵심**
   - 빠른 롤백 = MTTR 감소
   - 장애 복구 = 긴 Workflow 안전

4. ✅ **적절한 시간** (4-6시간)
   - 1일 작업
   - 리스크 중간
   - 효과 큼

---

### 작업 순서

```
Step 1: Workflow 롤백 (2-3h)
├─ workflow_versions 테이블 활용
├─ 롤백 로직 구현
├─ API 엔드포인트 추가
└─ 테스트

Step 2: Checkpoint 영구 저장 (2-3h)
├─ workflow_checkpoints 테이블 생성
├─ Redis + DB 저장 로직
├─ 복구 로직 구현
└─ 테스트

완료 후:
✅ Workflow Engine 거의 완성
✅ 전체 90% → 92%
```

---

### 완료 후 상태

**Workflow Engine**:
- TODO: 4개 → **1개** (ML 모델 배포만)
- 완성도: 78% → **95%**

**전체 기능**:
- 구현율: 90% → **92%**

---

## 📋 다음 다음 작업

**Workflow 완성 후**:
1. Judgment Replay (3-4h)
2. Module Progress (3-4h)
3. ETL 자동화 (4-6h)

**전부 완료 시**: 전체 92% → **98%** ✅

---

## 🎊 제 최종 추천

### **Workflow 롤백 + Checkpoint 영구 저장** (4-6시간)

**내일 작업으로 최적**:
- 적절한 작업량 (4-6h)
- Workflow Engine 완성
- 오늘 작업과 연결
- 운영 안정성 완성

---

어떤 작업을 진행하시겠습니까?

1. **Workflow 롤백 + Checkpoint** (4-6h) - 강력 추천 ⭐⭐⭐⭐⭐
2. **Judgment Replay** (3-4h) - 스펙 필수 ⭐⭐⭐⭐
3. **짧은 작업 하나** (Workflow 롤백만, 2-3h) ⭐⭐⭐⭐
4. **다른 추천** - 다시 분석