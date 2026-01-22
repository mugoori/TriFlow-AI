# 📋 남은 작업 추천 (2026-01-22 기준)

**현재 시각**: 오늘 저녁
**오늘 완료 작업**: 7개 (10-11시간)
**기능 구현율**: 84% → **88%** (+4%)

---

## ✅ 오늘 완료한 작업 (7개)

| # | 작업 | 시간 | 카테고리 |
|---|------|------|---------|
| 1 | ERP/MES 자격증명 암호화 | 3-4h | 보안 |
| 2 | Trust Level Admin 인증 | 1h | 보안 |
| 3 | Audit Log Total Count | 30m | UX |
| 4 | Canary 알림 시스템 | 2h | 운영 |
| 5 | Prompt Tuning 자동화 | 2h | AI |
| 6 | Redis Pub/Sub 실시간 | 2h | UX |
| 7 | **BI 시드 데이터 스크립트** | 1h | **BI** |

**총**: 11-12시간

---

## 🎯 남은 작업 (카테고리별)

### 🔴 Workflow Engine TODO (3개, 6-9시간)

#### 1. Workflow 롤백 구현 ⭐⭐⭐⭐⭐
**위치**: workflow_engine.py:5891
**시간**: 2-3h
**효과**: Workflow 버전 관리, 빠른 복구

**기능**:
```python
async def _rollback_workflow(workflow_id, version):
    # workflow_versions 테이블에서 이전 버전 조회
    # 현재 활성 Workflow를 이전 버전으로 복원
    # 롤백 이력 기록
```

**사용 사례**:
- 새 Workflow 버전 배포 후 문제 발견
- "Rollback to v2" 버튼 클릭
- 5초 만에 이전 버전 복원

---

#### 2. Checkpoint 영구 저장 ⭐⭐⭐⭐
**위치**: workflow_engine.py:6469
**시간**: 2-3h
**효과**: 서버 재시작 후 재개 가능

**기능**:
```python
async def save_checkpoint(instance_id, node_id, state):
    # 메모리 + Redis + DB 3단계 저장
    # 서버 재시작 후 복구 가능
```

**사용 사례**:
- 30분 걸리는 Workflow 실행 중
- 20분 시점에 서버 재시작
- 20분 지점부터 재개 (처음부터 안 해도 됨)

---

#### 3. ML 모델 배포 ⭐⭐⭐
**위치**: workflow_engine.py:5659
**시간**: 3-4h
**효과**: ML 모델 자동 배포

**기능**:
```python
async def _deploy_model(model_id, version, environment):
    # ML 모델을 SageMaker/Kubernetes에 배포
    # 헬스 체크
    # 배포 기록
```

---

### 🟠 BI 관련 (3개, 8-11시간)

#### 4. Materialized Views 생성 ⭐⭐⭐⭐
**시간**: 3-4h
**효과**: 쿼리 성능 10배 향상

**기능**:
- mv_defect_trend (불량률 추이)
- mv_oee_daily (일일 OEE)
- mv_inventory_coverage (재고 커버리지)
- mv_line_performance (라인 성과)

---

#### 5. 캐싱 Redis 연동 ⭐⭐⭐⭐
**시간**: 2-3h
**효과**: 동일 쿼리 즉시 응답

**기능**:
```python
# bi_service.py 수정
cache_key = generate_cache_key(plan)
cached = await redis.get(f"bi:cache:{cache_key}")
if cached:
    return cached  # < 10ms 응답!
```

---

#### 6. ETL 파이프라인 ⭐⭐⭐
**시간**: 4-6h
**효과**: RAW → FACT 자동 변환

**기능**:
```python
# etl_service.py 신규
async def run_raw_to_fact():
    # Mock API 데이터 → FACT 변환
    # 스케줄링 (매일 새벽)
```

---

### 🟢 기타 개선 (3개, 8-12시간)

#### 7. Judgment Replay 구현 ⭐⭐⭐
**시간**: 3-4h
**효과**: 과거 판단 재실행, What-if 분석

---

#### 8. Module 설치 Progress ⭐⭐⭐
**시간**: 3-4h
**효과**: 설치 진행률 실시간 표시

---

#### 9. PII Masking 강화 ⭐⭐⭐
**시간**: 2-3h
**효과**: 이메일, 전화번호 자동 감지

---

## 💡 추천 작업 (우선순위별)

### **Option 1: Workflow Engine 완성** (6-9시간) ⭐⭐⭐⭐⭐

**가장 많은 TODO가 있는 모듈!**

```
1. Workflow 롤백 (2-3h)
2. Checkpoint 영구 저장 (2-3h)
3. ML 모델 배포 (3-4h) - 선택적

완료 후:
✅ Workflow Engine 78% → 95%
✅ 전체 기능 88% → 92%
✅ Workflow TODO 완전 해결
```

**이유**:
- Workflow는 시스템 핵심 엔진
- 3개 TODO 중 2개는 운영 필수
- 오늘 Redis Pub/Sub 완료 → 시너지

---

### **Option 2: BI 성능 최적화** (5-7시간) ⭐⭐⭐⭐

**BI를 프로덕션 수준으로!**

```
1. Materialized Views (3-4h)
2. 캐싱 Redis 연동 (2-3h)

완료 후:
✅ BI 쿼리 성능 10배 향상
✅ p95 < 2초 목표 달성
✅ LLM 비용 절감 (캐싱)
```

**이유**:
- BI 시드 데이터 스크립트 완료 → 자연스러운 연결
- 성능이 사용자 체감에 직접 영향
- 오늘 Redis Client 구현 → 재사용 가능

---

### **Option 3: 빠른 완성** (5-7시간) ⭐⭐⭐⭐

**여러 모듈 조금씩 완성!**

```
1. Checkpoint 영구 저장 (2-3h)
2. 캐싱 Redis 연동 (2-3h)
3. Judgment Replay (3-4h)

완료 후:
✅ Workflow 장애 복구 강화
✅ BI 성능 향상
✅ Judgment 디버깅 가능
```

**이유**:
- 각기 다른 모듈 개선
- 중간 난이도 작업
- Redis 재사용 (오늘 구현한 것)

---

### **Option 4: 사용자 경험** (6-8시간) ⭐⭐⭐⭐

**Frontend 사용자가 체감하는 개선!**

```
1. Module 설치 Progress (3-4h)
2. BI 성능 최적화 (3-4h)

완료 후:
✅ 모듈 설치 진행률 실시간 표시
✅ BI 쿼리 빠른 응답
✅ Enterprise UX 수준
```

**이유**:
- 사용자 체감 효과 큼
- 오늘 WebSocket 구현 → 재사용
- 데모에 효과적

---

## 📊 각 Option의 효과

| Option | 시간 | 기능 구현율 | 사용자 체감 | 기술 난이도 |
|--------|------|-------------|------------|------------|
| **1. Workflow** | 6-9h | 88% → 92% | 중간 | 중간 |
| **2. BI 성능** | 5-7h | 88% → 90% | 높음 | 쉬움 |
| **3. 빠른 완성** | 5-7h | 88% → 91% | 중간 | 중간 |
| **4. UX 개선** | 6-8h | 88% → 90% | 매우 높음 | 중간 |

---

## 🎯 제 추천: **Option 2 (BI 성능 최적화)**

### 이유

1. ✅ **오늘 작업과 자연스러운 연결**
   - BI 시드 데이터 스크립트 완료
   - Redis Client 구현 완료
   - 바로 이어서 작업 가능

2. ✅ **빠른 완성** (5-7시간)
   - Materialized Views (3-4h)
   - 캐싱 Redis 연동 (2-3h)

3. ✅ **사용자 체감 효과 큼**
   - 쿼리 응답 5초 → 0.5초 (10배 빠름)
   - "빠르다!" 즉시 느낌

4. ✅ **기술적으로 쉬움**
   - SQL 작성 위주
   - Redis는 이미 구현됨
   - 리스크 낮음

---

### 완료 후 상태

**BI 모듈**:
- 현재: 85% (엔진 완벽, 성능 미흡)
- 완료 후: **95%** (엔진 + 성능 모두 완벽)

**전체 기능**:
- 현재: 88%
- 완료 후: **90%**

---

## 🗓️ 다음 작업 로드맵

### 내일 (Option 2)
```
1. Materialized Views (3-4h)
2. 캐싱 Redis 연동 (2-3h)

완료: BI 성능 최적화 ✅
```

### 다음 주
```
3. Workflow 롤백 (2-3h)
4. Checkpoint 영구 저장 (2-3h)
5. Judgment Replay (3-4h)

완료: 전체 88% → 95% ✅
```

### 2주 후
```
6. ETL 자동화 (6-8h)
7. Module Progress (3-4h)
8. PII Masking (2-3h)

완료: 전체 95% → 99% ✅
```

---

## 📊 작업 완성도 로드맵

```
현재 (88%):
[█████████████████████░░░] 88%

Option 2 완료 (90%):
[█████████████████████▓░░] 90%

Workflow 완성 (92%):
[█████████████████████▓▓░] 92%

전체 완성 (99%):
[████████████████████████] 99%
```

---

## 💡 최종 추천

### **Option 2: BI 성능 최적화** (5-7시간) ⭐⭐⭐⭐⭐

**추천 이유**:
1. ✅ 오늘 작업과 연결 (BI 시드 → MV)
2. ✅ 빠른 시간에 큰 효과
3. ✅ 사용자 체감 명확 ("빠르다!")
4. ✅ 기술적으로 안전 (SQL 위주)
5. ✅ Redis 재사용 (오늘 구현)

**작업 내용**:
```
Day 1 (3-4h):
1. Materialized Views 4개 생성
   - mv_defect_trend
   - mv_oee_daily
   - mv_inventory_coverage
   - mv_line_performance
2. 리프레시 스케줄 설정

Day 2 (2-3h):
3. bi_service.py 캐싱 활성화
4. Redis 연동
5. 테스트
```

**완료 후**:
- ✅ BI 쿼리 10배 빠름
- ✅ 캐시 HIT 시 < 10ms
- ✅ LLM 비용 절감
- ✅ BI 모듈 95% 완성

---

## 📋 전체 작업 우선순위

| 순위 | 작업 | 시간 | 효과 | 난이도 |
|-----|------|------|------|--------|
| 1 | **BI MV + 캐싱** | 5-7h | 성능 10배 | 쉬움 |
| 2 | **Workflow 롤백** | 2-3h | 빠른 복구 | 중간 |
| 3 | **Checkpoint 영구** | 2-3h | 장애 복구 | 중간 |
| 4 | **Judgment Replay** | 3-4h | 디버깅 | 중간 |
| 5 | **ETL 자동화** | 6-8h | 자동화 | 높음 |
| 6 | **Module Progress** | 3-4h | UX | 중간 |
| 7 | **ML 모델 배포** | 3-4h | MLOps | 높음 |
| 8 | **PII Masking** | 2-3h | 보안 | 쉬움 |

---

## 🎯 시나리오별 추천

### 시나리오 1: "빠르게 완성하고 싶어요"

**추천**: Option 2 (BI 성능)
- 5-7시간
- 즉시 효과
- 리스크 낮음

---

### 시나리오 2: "핵심 엔진을 완성하고 싶어요"

**추천**: Option 1 (Workflow Engine)
- 6-9시간
- Workflow 완성
- 시스템 안정성

---

### 시나리오 3: "사용자에게 보여줄 것 만들고 싶어요"

**추천**: Option 4 (UX 개선)
- 6-8시간
- Module 설치 진행률
- BI 빠른 응답
- 데모 효과적

---

### 시나리오 4: "빨리 여러 개 완성하고 싶어요"

**추천**: 짧은 작업 3개 묶기
```
1. Workflow 롤백 (2-3h)
2. Checkpoint 영구 (2-3h)
3. 캐싱 Redis (2-3h)

총: 6-9시간
완료: 3개 기능!
```

---

## 📈 완성도 목표

### 단기 목표 (1주)
- **현재**: 88%
- **목표**: 92%
- **필요**: Workflow + BI 완성

### 중기 목표 (2주)
- **현재**: 88%
- **목표**: 95%
- **필요**: Judgment + Module + ETL

### 장기 목표 (1개월)
- **현재**: 88%
- **목표**: 99%
- **필요**: 모든 TODO 해결

---

## 💼 비즈니스 관점 추천

### Enterprise 고객 계약용
```
우선순위:
1. BI 성능 (빠른 응답 = 프로페셔널)
2. Workflow 롤백 (안정성 = 신뢰)
3. 실시간 Progress (UX = 차별화)
```

### 기술 부채 해소용
```
우선순위:
1. Workflow TODO 3개 (핵심 엔진)
2. ETL 자동화 (데이터 파이프라인)
3. Judgment Replay (완성도)
```

### 데모/시연용
```
우선순위:
1. BI 성능 (빠른 응답)
2. Module Progress (실시간 표시)
3. Workflow 실시간 (진행률)
```

---

## 🎯 **최종 추천: BI 성능 최적화**

**이유**:
1. 오늘 BI 시드 완료 → 자연스러운 다음 단계
2. 5-7시간 → 빠른 완성
3. 사용자 체감 즉시 ("10배 빠르다!")
4. Redis 재사용 (오늘 구현)
5. 리스크 낮음 (SQL 위주)

**작업 내용**:
```
1. Materialized Views 생성 (3-4h)
   - SQL DDL 작성
   - 인덱스 생성
   - 리프레시 스케줄

2. 캐싱 Redis 연동 (2-3h)
   - bi_service.py 수정
   - Redis get/set 활성화
   - 테스트
```

**완료 후**:
- ✅ BI 쿼리 5초 → 0.5초
- ✅ 캐시 HIT 시 < 10ms
- ✅ BI 모듈 95% 완성
- ✅ 전체 90% 달성

---

어떤 작업을 진행하시겠습니까?

1. **BI 성능 최적화** (5-7h) - 빠르고 효과적 ⭐⭐⭐⭐⭐
2. **Workflow Engine 완성** (6-9h) - 핵심 엔진 ⭐⭐⭐⭐⭐
3. **짧은 작업 3개** (6-9h) - 여러 개 완성 ⭐⭐⭐⭐
4. **다른 추천** - 다시 분석