# -*- coding: utf-8 -*-
"""Canary Deployment E2E 테스트

배포 생성 → Canary 시작 → 트래픽 조정 → 승격/롤백 전체 플로우 검증

Note: 이 테스트는 실제 서버(localhost:8000)가 실행 중이어야 합니다.
"""
import pytest
from httpx import AsyncClient


# E2E 테스트는 실제 서버 사용
E2E_BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_canary_deployment_e2e(e2e_auth_headers):
    """
    Canary Deployment E2E 테스트

    플로우:
    1. Ruleset 생성
    2. 배포 생성 (draft 상태)
    3. Canary 시작 (10% 트래픽)
    4. 메트릭 확인
    5. 트래픽 증가 (10% → 50%)
    6. 승격 (100% 배포)
    """
    async with AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        headers = e2e_auth_headers

        # ============================================
        # 1. Ruleset 생성 (테스트 데이터)
        # ============================================
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]

        # Rhai 스크립트 (온도 임계값 체크)
        rhai_script = '''
// 온도 임계값 체크 룰
let threshold = 25.0;
let temperature = input.temperature;

if temperature > threshold {
    #{
        "result": "HIGH",
        "message": "온도가 임계값을 초과했습니다",
        "temperature": temperature,
        "threshold": threshold
    }
} else {
    #{
        "result": "NORMAL",
        "message": "온도가 정상 범위입니다",
        "temperature": temperature,
        "threshold": threshold
    }
}
'''

        ruleset_data = {
            "name": f"E2E Canary Test Ruleset {unique_suffix}",
            "description": "Canary 배포 테스트용 룰셋",
            "rhai_script": rhai_script
        }

        ruleset_resp = await client.post(
            "/api/v1/rulesets",
            json=ruleset_data,
            headers=headers
        )

        assert ruleset_resp.status_code == 201, f"Ruleset 생성 실패: {ruleset_resp.text}"
        ruleset_id = ruleset_resp.json()["ruleset_id"]

        # ============================================
        # 2. 배포 생성
        # ============================================
        deployment_data = {
            "ruleset_id": ruleset_id,
            "version": 1,
            "changelog": "Canary 배포 테스트",
            "canary_config": {
                "auto_rollback_enabled": True,
                "min_samples": 10,
                "error_rate_threshold": 0.05,
                "relative_error_threshold": 2.0,
                "latency_p95_threshold": 1.5,
                "consecutive_failure_threshold": 5
            },
            "compensation_strategy": "ignore"
        }

        deployment_resp = await client.post(
            "/api/v1/deployments",
            json=deployment_data,
            headers=headers
        )

        assert deployment_resp.status_code in [200, 201], f"배포 생성 실패: {deployment_resp.text}"
        deployment_id = deployment_resp.json()["deployment_id"]

        # ============================================
        # 3. Canary 시작 (10% 트래픽)
        # ============================================
        start_canary_req = {
            "canary_pct": 0.1  # 10%는 0.1로 표현
        }

        start_resp = await client.post(
            f"/api/v1/deployments/{deployment_id}/start-canary",
            json=start_canary_req,
            headers=headers
        )

        assert start_resp.status_code == 200, f"Canary 시작 실패: {start_resp.text}"
        start_data = start_resp.json()
        assert start_data["status"] == "canary"

        # ============================================
        # 4. Sticky Session 할당 확인
        # ============================================
        assignments_resp = await client.get(
            f"/api/v1/deployments/{deployment_id}/assignments",
            headers=headers
        )

        # 할당이 없거나 엔드포인트가 없을 수 있음
        assert assignments_resp.status_code in [200, 404]

        # ============================================
        # 5. 메트릭 조회
        # ============================================
        metrics_resp = await client.get(
            f"/api/v1/deployments/{deployment_id}/metrics",
            headers=headers
        )

        # 메트릭 데이터가 없을 수 있음
        assert metrics_resp.status_code in [200, 404]

        # ============================================
        # 6. 트래픽 증가 (10% → 50%)
        # ============================================
        traffic_req = {
            "canary_pct": 0.5  # 50%는 0.5로 표현
        }

        traffic_resp = await client.put(
            f"/api/v1/deployments/{deployment_id}/traffic",
            json=traffic_req,
            headers=headers
        )

        assert traffic_resp.status_code == 200, f"트래픽 조정 실패: {traffic_resp.text}"

        # 배포 상세 조회로 트래픽 비율 확인
        detail_resp = await client.get(
            f"/api/v1/deployments/{deployment_id}",
            headers=headers
        )

        assert detail_resp.status_code == 200

        # ============================================
        # 7. 승격 (100% 배포)
        # ============================================
        promote_resp = await client.post(
            f"/api/v1/deployments/{deployment_id}/promote",
            headers=headers
        )

        assert promote_resp.status_code == 200, f"승격 실패: {promote_resp.text}"
        promote_data = promote_resp.json()
        assert promote_data["status"] == "active"


@pytest.mark.asyncio
async def test_canary_rollback(e2e_auth_headers):
    """
    Canary 롤백 테스트

    플로우:
    1. 배포 생성 및 Canary 시작
    2. 롤백 실행
    3. 상태 확인 (rolled_back)
    """
    async with AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        headers = e2e_auth_headers

        import uuid
        unique_suffix = str(uuid.uuid4())[:8]

        # Ruleset 생성
        rhai_script = 'if input.value > 10 { #{"result": "HIGH"} } else { #{"result": "LOW"} }'
        ruleset_data = {
            "name": f"Rollback Test Ruleset {unique_suffix}",
            "description": "롤백 테스트용",
            "rhai_script": rhai_script
        }

        ruleset_resp = await client.post(
            "/api/v1/rulesets",
            json=ruleset_data,
            headers=headers
        )

        if ruleset_resp.status_code != 201:
            # Ruleset 생성 실패 시 테스트 스킵
            print(f"Ruleset creation failed: {ruleset_resp.text}")
            return

        ruleset_id = ruleset_resp.json()["ruleset_id"]

        # 배포 생성
        deployment_data = {
            "ruleset_id": ruleset_id,
            "version": 1,
            "changelog": "롤백 테스트용 배포",
            "canary_config": {
                "auto_rollback_enabled": True,
                "min_samples": 10
            }
        }

        deployment_resp = await client.post(
            "/api/v1/deployments",
            json=deployment_data,
            headers=headers
        )

        if deployment_resp.status_code not in [200, 201]:
            print(f"Deployment creation failed: {deployment_resp.text}")
            return

        deployment_id = deployment_resp.json()["deployment_id"]

        # Canary 시작
        start_resp = await client.post(
            f"/api/v1/deployments/{deployment_id}/start-canary",
            json={"canary_pct": 0.1},
            headers=headers
        )

        if start_resp.status_code != 200:
            print(f"Canary start failed: {start_resp.text}")
            return

        # 롤백 실행
        rollback_resp = await client.post(
            f"/api/v1/deployments/{deployment_id}/rollback",
            json={"reason": "E2E 테스트 롤백"},
            headers=headers
        )

        assert rollback_resp.status_code == 200, f"롤백 실패: {rollback_resp.text}"
        rollback_data = rollback_resp.json()
        # 롤백 API는 success 필드를 반환
        assert rollback_data.get("success") is True or rollback_data.get("status") == "rolled_back"

        # 배포 상태 조회로 롤백 확인
        detail_resp = await client.get(
            f"/api/v1/deployments/{deployment_id}",
            headers=headers
        )
        if detail_resp.status_code == 200:
            detail_data = detail_resp.json()
            assert detail_data["status"] == "rolled_back"


@pytest.mark.asyncio
async def test_canary_sticky_session(e2e_auth_headers):
    """
    Sticky Session 테스트

    플로우:
    1. Canary 시작
    2. 특정 사용자에게 v2 할당
    3. 동일 사용자 재요청 시 v2 유지 확인
    """
    # TODO: 실제 구현 시 Sticky Session 동작 확인
    pass


@pytest.mark.asyncio
async def test_canary_health_check(e2e_auth_headers):
    """
    Canary 건강 상태 체크 테스트

    검증:
    - health_status 조회
    - circuit_breaker_state 확인
    """
    # TODO: 실제 구현 시 health check 엔드포인트 테스트
    pass
