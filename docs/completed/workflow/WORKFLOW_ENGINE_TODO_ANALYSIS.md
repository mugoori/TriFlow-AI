# 📋 Workflow Engine TODO 4개 상세 분석

**파일**: `backend/app/services/workflow_engine.py` (249KB, 6,300+ 라인)
**분석 일시**: 2026-01-22

---

## 🔍 TODO 4개 상세 설명

### 1️⃣ TODO #1: ML 모델 배포 로직 구현 ⭐⭐⭐

**위치**: [Line 5659](backend/app/services/workflow_engine.py#L5659)

**현재 코드**:
```python
async def _deploy_model(
    self,
    model_id: str,
    version: Optional[int],
    environment: str,
    tenant_id: str
) -> Dict[str, Any]:
    """ML 모델 배포 (placeholder)"""
    # TODO: 실제 ML 모델 배포 로직
    logger.info(f"ML 모델 배포: {model_id} v{version} -> {environment}")
    return {"success": True, "message": "모델 배포 완료 (mock)", "version": version}
```

**기능 설명**:
- **목적**: Workflow에서 ML 모델을 특정 환경(dev/staging/production)에 배포
- **노드 타입**: `DEPLOY` 노드 (node.type == "deploy", node.target_type == "model")
- **사용 사례**:
  - 학습된 ML 모델을 프로덕션 배포
  - Canary 배포 (일부 트래픽만)
  - Blue-Green 배포

**필요한 구현**:
```python
async def _deploy_model(...):
    # 1. 모델 저장소에서 모델 파일 조회 (S3, MLflow 등)
    model_artifact = await get_model_artifact(model_id, version)

    # 2. 배포 환경 준비
    if environment == "production":
        endpoint = create_sagemaker_endpoint(model_id, version)
    elif environment == "staging":
        endpoint = create_staging_endpoint(model_id, version)

    # 3. 헬스 체크
    health = await check_endpoint_health(endpoint)

    # 4. 배포 기록
    await log_deployment(model_id, version, environment, endpoint)

    return {
        "success": True,
        "endpoint": endpoint,
        "version": version,
        "environment": environment
    }
```

**우선순위**: ⭐⭐⭐ (Medium)
- **영향**: ML 모델 배포 자동화 불가
- **회피 방법**: 수동 배포 후 Workflow에서 호출만
- **예상 시간**: 3-4시간

---

### 2️⃣ TODO #2: Workflow 버전 롤백 로직 구현 ⭐⭐⭐⭐

**위치**: [Line 5891](backend/app/services/workflow_engine.py#L5891)

**현재 코드**:
```python
async def _rollback_workflow(
    self,
    workflow_id: str,
    version: int,
    tenant_id: str
) -> Dict[str, Any]:
    """워크플로우 롤백"""
    # TODO: workflow_versions 테이블 구현 후 실제 롤백 로직
    logger.info(f"워크플로우 롤백: {workflow_id} -> v{version}")
    return {"success": True, "message": f"워크플로우 v{version}으로 롤백 완료 (mock)"}
```

**기능 설명**:
- **목적**: Workflow를 이전 버전으로 롤백
- **노드 타입**: `ROLLBACK` 노드 (node.type == "rollback", node.target_type == "workflow")
- **사용 사례**:
  - 새 버전 배포 후 문제 발생 시 즉시 롤백
  - Canary 실패 시 자동 롤백
  - A/B 테스트 후 이전 버전 복원

**필요한 구현**:
```python
async def _rollback_workflow(...):
    # 1. workflow_versions 테이블에서 이전 버전 조회
    old_version = db.query(WorkflowVersion).filter(
        WorkflowVersion.workflow_id == workflow_id,
        WorkflowVersion.version == version
    ).first()

    if not old_version:
        return {"success": False, "message": f"버전 {version}을 찾을 수 없습니다"}

    # 2. 현재 활성 워크플로우 비활성화
    current_wf = db.query(Workflow).get(workflow_id)
    current_wf.is_active = False

    # 3. 이전 버전 복원
    current_wf.definition = old_version.definition  # JSON DSL
    current_wf.version = version
    current_wf.is_active = True

    # 4. 롤백 이력 기록
    await create_rollback_history(workflow_id, version, reason="Rollback requested")

    db.commit()

    return {
        "success": True,
        "workflow_id": workflow_id,
        "rolled_back_to_version": version,
        "previous_version": current_version
    }
```

**필요한 테이블**:
```sql
-- workflow_versions 테이블 (버전 히스토리)
CREATE TABLE core.workflow_versions (
    version_id UUID PRIMARY KEY,
    workflow_id UUID REFERENCES core.workflows,
    version INT NOT NULL,
    definition JSONB NOT NULL,  -- Workflow DSL
    created_by UUID,
    created_at TIMESTAMP,
    UNIQUE(workflow_id, version)
);
```

**우선순위**: ⭐⭐⭐⭐ (High)
- **영향**: Workflow 롤백 불가 → 장애 대응 어려움
- **회피 방법**: 수동 롤백 (DB 직접 수정)
- **예상 시간**: 2-3시간

---

### 3️⃣ TODO #3: Redis Pub/Sub 실시간 이벤트 발행 ⭐⭐⭐⭐⭐

**위치**: [Line 6327](backend/app/services/workflow_engine.py#L6327)

**현재 코드**:
```python
# 상태 변경 이벤트
event = {
    "instance_id": instance_id,
    "previous_state": old_state.value if old_state else None,
    "new_state": new_state.value,
    "reason": reason,
    "timestamp": datetime.utcnow().isoformat(),
}

# 실행 로그에 기록
execution_log_store.add_log(event)

# TODO: Redis pub/sub으로 이벤트 발행 (실시간 UI 업데이트용)
```

**기능 설명**:
- **목적**: Workflow 상태 변경을 Frontend에 실시간으로 전달
- **사용 사례**:
  - Workflow 실행 중 진행률 실시간 표시
  - 각 노드 실행 상태 실시간 업데이트
  - 에러 발생 시 즉시 알림

**필요한 구현**:
```python
# Redis Pub/Sub 설정
import redis.asyncio as redis

# StateManager 내부
async def _change_state(...):
    event = {...}

    # 로그에 기록
    execution_log_store.add_log(event)

    # ✅ Redis Pub/Sub으로 이벤트 발행
    redis_client = await get_redis_client()
    channel = f"workflow:{instance_id}:state"

    await redis_client.publish(
        channel,
        json.dumps(event)
    )

    logger.debug(f"Published state change event to {channel}")
```

**Frontend WebSocket**:
```typescript
// Frontend에서 실시간 수신
const ws = new WebSocket(`ws://api/v1/workflows/${instanceId}/subscribe`)

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  // {
  //   "instance_id": "...",
  //   "previous_state": "RUNNING",
  //   "new_state": "COMPLETED",
  //   "timestamp": "2026-01-22T..."
  // }

  // UI 업데이트
  updateWorkflowStatus(data.new_state)
}
```

**우선순위**: ⭐⭐⭐⭐⭐ (Very High)
- **영향**: 실시간 진행률 표시 불가 → UX 저하
- **사용자 경험**: "실행 중인데 진행 상황을 모르겠어요"
- **예상 시간**: 2-3시간

---

### 4️⃣ TODO #4: Checkpoint 영구 저장 (Redis + DB) ⭐⭐⭐

**위치**: [Line 6469](backend/app/services/workflow_engine.py#L6469-6475)

**현재 코드**:
```python
# Checkpoint를 메모리에만 저장
self._checkpoint_history[instance_id].append(checkpoint)

# TODO: 프로덕션에서는 Redis + DB에 저장
# await redis.set(
#     f"wf:checkpoint:{instance_id}",
#     json.dumps(checkpoint),
#     ex=self.checkpoint_ttl_seconds
# )
# await self._persist_to_db(checkpoint)
```

**기능 설명**:
- **목적**: Workflow 실행 중간 상태를 영구 저장하여 장애 복구
- **사용 사례**:
  - 서버 재시작 후 중단된 Workflow 재개
  - 긴 실행 Workflow (수 시간) 중간 저장
  - 노드 실패 시 마지막 Checkpoint부터 재실행

**필요한 구현**:
```python
async def save_checkpoint(...):
    checkpoint = {...}

    # 1. 메모리에 저장 (빠른 접근)
    self._checkpoint_history[instance_id].append(checkpoint)

    # 2. ✅ Redis에 저장 (중간 지속성, TTL 1시간)
    redis_client = await get_redis_client()
    await redis_client.setex(
        f"wf:checkpoint:{instance_id}:{checkpoint_id}",
        3600,  # 1시간 TTL
        json.dumps(checkpoint)
    )

    # 3. ✅ DB에 영구 저장 (장기 보관)
    db_checkpoint = WorkflowCheckpoint(
        checkpoint_id=checkpoint_id,
        instance_id=instance_id,
        node_id=node_id,
        state=checkpoint["state"],
        timestamp=checkpoint["timestamp"],
    )
    db.add(db_checkpoint)
    db.commit()

    logger.info(f"Checkpoint saved to Memory + Redis + DB")
```

**필요한 테이블**:
```sql
-- workflow_checkpoints 테이블
CREATE TABLE core.workflow_checkpoints (
    checkpoint_id UUID PRIMARY KEY,
    instance_id UUID REFERENCES core.workflow_instances,
    node_id VARCHAR(255) NOT NULL,
    state JSONB NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_instance_timestamp (instance_id, timestamp DESC)
);
```

**복구 로직**:
```python
async def restore_checkpoint(instance_id, checkpoint_id):
    # 1. 메모리에서 찾기 (가장 빠름)
    if instance_id in self._checkpoint_history:
        checkpoint = find_in_memory(checkpoint_id)
        if checkpoint:
            return checkpoint

    # 2. Redis에서 찾기 (중간 속도)
    redis_data = await redis.get(f"wf:checkpoint:{instance_id}:{checkpoint_id}")
    if redis_data:
        return json.loads(redis_data)

    # 3. DB에서 찾기 (가장 느림, 하지만 영구)
    db_checkpoint = db.query(WorkflowCheckpoint).get(checkpoint_id)
    if db_checkpoint:
        return db_checkpoint.state

    return None
```

**우선순위**: ⭐⭐⭐ (Medium-High)
- **영향**: 서버 재시작 시 실행 중인 Workflow 손실
- **회피 방법**: Workflow 재실행
- **예상 시간**: 2-3시간

---

## 📊 TODO 우선순위 매트릭스

| TODO | 기능 | 우선순위 | 사용자 영향 | 예상 시간 | 난이도 |
|------|------|---------|-----------|----------|--------|
| **#3** | Redis Pub/Sub | ⭐⭐⭐⭐⭐ | 매우 높음 | 2-3h | 중간 |
| **#2** | Workflow 롤백 | ⭐⭐⭐⭐ | 높음 | 2-3h | 중간 |
| **#4** | Checkpoint 영구 저장 | ⭐⭐⭐ | 중간 | 2-3h | 중간 |
| **#1** | ML 모델 배포 | ⭐⭐⭐ | 낮음 | 3-4h | 높음 |

---

## 🎯 각 TODO의 영향도 분석

### TODO #3: Redis Pub/Sub (최우선)

**사용자 경험 영향**: ⚠️⚠️⚠️ 매우 높음

**Before (현재)**:
```
사용자: "Workflow 실행" 버튼 클릭
Frontend: "실행 중..." (← 계속 이 화면만)

[5분 후]
사용자: "끝났나? 아직도 실행 중이라고만 나오는데..."
       "새로고침 해야 하나?"
       "혹시 실패한 거 아냐?"
```

**After (구현 후)**:
```
사용자: "Workflow 실행" 버튼 클릭
Frontend:
  ✅ 노드 1 (Data 조회) - 완료 (2초)
  🔄 노드 2 (Judgment) - 실행 중...
  ⏸️ 노드 3 (Action) - 대기 중
  ⏸️ 노드 4 (알림) - 대기 중

[30초 후]
  ✅ 노드 1 (Data 조회) - 완료
  ✅ 노드 2 (Judgment) - 완료
  ✅ 노드 3 (Action) - 완료
  🔄 노드 4 (알림) - 실행 중...

사용자: "진행 상황이 실시간으로 보이네! 안심된다."
```

---

### TODO #2: Workflow 롤백 (높은 우선순위)

**운영 영향**: ⚠️⚠️ 높음

**Before (현재)**:
```
상황: 새 Workflow 버전 배포 → 버그 발견!

대응:
1. 개발자가 수동으로 DB 접속
2. workflows 테이블에서 이전 definition 찾기
3. SQL UPDATE로 수동 복원
4. 재배포

소요 시간: 30분 - 1시간
```

**After (구현 후)**:
```
상황: 새 Workflow 버전 배포 → 버그 발견!

대응:
1. Admin이 UI에서 "Rollback to v2" 버튼 클릭
2. 자동으로 이전 버전 복원
3. 완료

소요 시간: 5초
```

**구현 예시**:
```json
// Workflow DSL에서 ROLLBACK 노드
{
  "node_id": "rollback_on_error",
  "type": "rollback",
  "target_type": "workflow",
  "config": {
    "workflow_id": "{{current_workflow_id}}",
    "version": 2,  // 롤백할 버전
    "reason": "Error detected in v3"
  }
}
```

---

### TODO #4: Checkpoint 영구 저장 (중간 우선순위)

**안정성 영향**: ⚠️⚠️ 중간

**Before (현재)**:
```
상황: 긴 Workflow 실행 중 (30분 소요)
      20분 실행 후 서버 재시작 (배포, 장애 등)

결과:
❌ Checkpoint가 메모리에만 있음 → 손실!
❌ 처음부터 다시 실행해야 함
❌ 20분 작업 날아감
```

**After (구현 후)**:
```
상황: 긴 Workflow 실행 중 (30분 소요)
      20분 실행 후 서버 재시작

복구:
✅ Redis/DB에서 마지막 Checkpoint 조회
✅ 20분 시점부터 재개 (처음부터 안 해도 됨!)
✅ 10분만 더 실행하면 완료

절약: 20분
```

**Checkpoint 데이터 예시**:
```json
{
  "checkpoint_id": "ckpt-123",
  "instance_id": "instance-456",
  "node_id": "node_15",
  "state": {
    "completed_nodes": ["node_1", "node_2", ..., "node_14"],
    "current_node": "node_15",
    "context": {
      "total_items": 1000,
      "processed_items": 750  // 75% 완료
    },
    "outputs": {
      "node_1": {...},
      "node_2": {...},
      ...
    }
  },
  "timestamp": "2026-01-22T10:35:00Z"
}
```

---

### TODO #1: ML 모델 배포 (낮은 우선순위)

**영향**: ⚠️ 낮음

**이유**:
- ML 모델 배포는 전문적인 작업 (MLOps)
- 대부분의 고객은 ML 모델 직접 배포 안 함
- SageMaker, Kubernetes 등 외부 도구 사용

**회피 방법**:
```python
# Workflow에서 외부 배포 API 호출로 대체
{
  "node_id": "deploy_model",
  "type": "action",  // DEPLOY 대신 ACTION 사용
  "action_type": "api_call",
  "config": {
    "url": "https://ml-platform.internal/deploy",
    "method": "POST",
    "body": {
      "model_id": "{{model_id}}",
      "version": "{{version}}",
      "environment": "production"
    }
  }
}
```

---

## 💡 구현 우선순위 추천

### Option 1: 실시간 UX 우선 (2-3시간) ⭐⭐⭐⭐⭐

```
1. Redis Pub/Sub 구현 (TODO #3)
   - WebSocket 엔드포인트 추가
   - Frontend 실시간 업데이트
```

**효과**:
- ✅ 사용자 경험 대폭 개선
- ✅ Enterprise 수준 UX
- ✅ 가장 빠른 시간에 큰 효과

---

### Option 2: 안정성 우선 (4-6시간) ⭐⭐⭐⭐

```
1. Workflow 롤백 구현 (TODO #2)
   - workflow_versions 테이블 생성
   - 롤백 로직 구현

2. Checkpoint 영구 저장 (TODO #4)
   - Redis + DB 저장
   - 복구 로직 구현
```

**효과**:
- ✅ 운영 안정성 확보
- ✅ 장애 복구 능력
- ✅ 긴 Workflow 안전 실행

---

### Option 3: 전체 완성 (8-12시간) ⭐⭐⭐⭐⭐

```
Day 1 (4-6h):
1. Redis Pub/Sub (2-3h)
2. Workflow 롤백 (2-3h)

Day 2 (4-6h):
3. Checkpoint 영구 저장 (2-3h)
4. ML 모델 배포 (3-4h) - 선택적
```

**효과**:
- ✅ Workflow Engine 71% → **100%**
- ✅ 전체 기능 구현율 86% → **92%**

---

## 🎯 제 추천: **Option 1 (Redis Pub/Sub 우선)**

**이유**:
1. ✅ **가장 빠름** (2-3시간)
2. ✅ **사용자 체감 효과 최대**
3. ✅ **Enterprise UX 필수 기능**
4. ✅ **오늘 작업과 시너지**:
   - Canary 알림 시스템 완료 → 실시간 통신 경험 활용
   - Notification Service → WebSocket 패턴 유사

**구현 내용**:
```
1. Redis Pub/Sub 설정 (30분)
2. StateManager 이벤트 발행 (1h)
3. WebSocket 엔드포인트 (1h)
4. 테스트 (30분)
```

**완료 후 다음 단계**:
```
오늘: Redis Pub/Sub (2-3h) → 실시간 UX ✅
내일: Workflow 롤백 (2-3h) → 운영 안정성 ✅
모레: Checkpoint 영구 저장 (2-3h) → 장애 복구 ✅
```

---

## 📝 요약

### Workflow Engine TODO 4개

| # | 기능 | 우선순위 | 시간 | 핵심 가치 |
|---|------|---------|------|---------|
| 3 | **Redis Pub/Sub** | ⭐⭐⭐⭐⭐ | 2-3h | 실시간 UX |
| 2 | **Workflow 롤백** | ⭐⭐⭐⭐ | 2-3h | 빠른 복구 |
| 4 | **Checkpoint 영구** | ⭐⭐⭐ | 2-3h | 장애 복구 |
| 1 | **ML 모델 배포** | ⭐⭐⭐ | 3-4h | MLOps 자동화 |

**전체 예상 시간**: 9-13시간 (1.5일)

---

어떤 작업을 진행하시겠습니까?
1. **Redis Pub/Sub** (2-3h) - 실시간 UX ⭐⭐⭐⭐⭐
2. **전체 완성** (9-13h, 1.5일) - Workflow 100% ⭐⭐⭐⭐⭐
3. **다른 작업** - 다음 우선순위 추천
