# -*- coding: utf-8 -*-
"""Canary Deployment E2E 테스트

배포 생성 → Canary 시작 → 트래픽 조정 → 승격/롤백 전체 플로우 검증
"""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

from app.main import app
from app.models import RuleDeployment, Ruleset, RulesetVersion


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_canary_deployment_e2e(db_session: Session, test_tenant_id, test_user_id):
    """
    Canary Deployment E2E 테스트

    플로우:
    1. Ruleset 및 Version 생성
    2. 배포 생성 (draft 상태)
    3. Canary 시작 (10% 트래픽)
    4. 메트릭 확인
    5. 트래픽 증가 (10% → 50%)
    6. 승격 (100% 배포)
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # ============================================
        # 1. Ruleset 및 Version 생성 (테스트 데이터)
        # ============================================

        # Ruleset 생성
        ruleset_data = {
            "name": "E2E Canary Test Ruleset",
            "description": "Canary 배포 테스트용",
            "category": "threshold_check"
        }

        ruleset_resp = await client.post(
            "/api/v1/rulesets",
            json=ruleset_data,
            headers={"X-Tenant-ID": str(test_tenant_id)}
        )

        assert ruleset_resp.status_code == 201
        ruleset_id = ruleset_resp.json()["ruleset_id"]

        # RulesetVersion 생성 (v1)
        version_v1_data = {
            "version": "v1.0.0",
            "rhai_code": 'if temperature > 25.0 { "HIGH" } else { "NORMAL" }',
            "changelog": "초기 버전",
            "trust_level": 2  # Low Risk Auto
        }

        version_resp = await client.post(
            f"/api/v1/rulesets/{ruleset_id}/versions",
            json=version_v1_data,
            headers={"X-Tenant-ID": str(test_tenant_id)}
        )

        assert version_resp.status_code == 201
        version_v1_id = version_resp.json()["version_id"]

        # RulesetVersion v2 생성 (Canary 대상)
        version_v2_data = {
            "version": "v2.0.0",
            "rhai_code": 'if temperature > 27.0 { "HIGH" } else { "NORMAL" }',  # 임계값 변경
            "changelog": "임계값 25 → 27로 조정",
            "trust_level": 0  # Proposed
        }

        version_v2_resp = await client.post(
            f"/api/v1/rulesets/{ruleset_id}/versions",
            json=version_v2_data,
            headers={"X-Tenant-ID": str(test_tenant_id)}
        )

        assert version_v2_resp.status_code == 201
        version_v2_id = version_v2_resp.json()["version_id"]

        # ============================================
        # 2. 배포 생성
        # ============================================
        deployment_data = {
            "ruleset_id": ruleset_id,
            "version": "v2.0.0",
            "changelog": "Canary 배포 테스트",
            "canary_config": {
                "initial_traffic_percentage": 10,
                "increment": 10,
                "duration_minutes": 60,
                "success_threshold": 0.95,
                "error_threshold": 0.05
            },
            "compensation_strategy": "rollback_only"
        }

        deployment_resp = await client.post(
            "/api/v1/deployments",
            json=deployment_data,
            headers={"X-Tenant-ID": str(test_tenant_id)}
        )

        assert deployment_resp.status_code == 200, f"배포 생성 실패: {deployment_resp.text}"
        deployment_id = deployment_resp.json()["deployment_id"]

        # DB에서 배포 확인
        deployment = db_session.query(RuleDeployment).filter(
            RuleDeployment.deployment_id == deployment_id
        ).first()
        assert deployment is not None
        assert deployment.status == "draft"

        # ============================================
        # 3. Canary 시작 (10% 트래픽)
        # ============================================
        start_canary_req = {
            "canary_pct": 10
        }

        start_resp = await client.post(
            f"/api/v1/deployments/{deployment_id}/start-canary",
            json=start_canary_req,
            headers={"X-Tenant-ID": str(test_tenant_id)}
        )

        assert start_resp.status_code == 200, f"Canary 시작 실패: {start_resp.text}"
        start_data = start_resp.json()
        assert start_data["status"] == "canary"

        # DB에서 상태 확인
        db_session.refresh(deployment)
        assert deployment.status == "canary"

        # ============================================
        # 4. Sticky Session 할당 확인
        # ============================================
        assignments_resp = await client.get(
            f"/api/v1/deployments/{deployment_id}/assignments",
            headers={"X-Tenant-ID": str(test_tenant_id)}
        )

        # 할당이 없을 수도 있음 (아직 요청 없음)
        assert assignments_resp.status_code == 200

        # ============================================
        # 5. 메트릭 조회
        # ============================================
        metrics_resp = await client.get(
            f"/api/v1/deployments/{deployment_id}/metrics",
            headers={"X-Tenant-ID": str(test_tenant_id)}
        )

        # 메트릭 데이터가 없을 수 있음 (실제 실행 없음)
        assert metrics_resp.status_code in [200, 404]

        # ============================================
        # 6. 트래픽 증가 (10% → 50%)
        # ============================================
        traffic_req = {
            "traffic_percentage": 50
        }

        traffic_resp = await client.put(
            f"/api/v1/deployments/{deployment_id}/traffic",
            json=traffic_req,
            headers={"X-Tenant-ID": str(test_tenant_id)}
        )

        assert traffic_resp.status_code == 200, f"트래픽 조정 실패: {traffic_resp.text}"

        # 배포 상세 조회로 트래픽 비율 확인
        detail_resp = await client.get(
            f"/api/v1/deployments/{deployment_id}",
            headers={"X-Tenant-ID": str(test_tenant_id)}
        )

        assert detail_resp.status_code == 200
        # Note: canary_config에서 traffic_percentage가 업데이트되었는지 확인

        # ============================================
        # 7. 승격 (100% 배포)
        # ============================================
        promote_resp = await client.post(
            f"/api/v1/deployments/{deployment_id}/promote",
            headers={"X-Tenant-ID": str(test_tenant_id)}
        )

        assert promote_resp.status_code == 200, f"승격 실패: {promote_resp.text}"
        promote_data = promote_resp.json()
        assert promote_data["status"] == "active"

        # DB에서 최종 상태 확인
        db_session.refresh(deployment)
        assert deployment.status == "active"


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_canary_rollback(db_session: Session, test_tenant_id):
    """
    Canary 롤백 테스트

    플로우:
    1. 배포 생성 및 Canary 시작
    2. 롤백 실행
    3. 상태 확인 (rolled_back)
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # Ruleset & Version 생성 (생략, 위와 동일)
        # ...

        # 배포 생성 및 Canary 시작
        # (코드 생략)

        # deployment_id 가정
        # deployment_id = "..."

        # ============================================
        # 롤백 실행
        # ============================================
        rollback_req = {
            "reason": "E2E 테스트 - 의도적 롤백",
            "apply_compensation": True
        }

        # TODO: 실제 Ruleset 생성 및 Canary 배포 후 롤백 테스트 구현 필요
        pass

        # Note: deployment_id가 필요하므로 실제 구현 시 위 단계 포함 필요
        # rollback_resp = await client.post(
        #     f"/api/v1/deployments/{deployment_id}/rollback",
        #     json=rollback_req,
        #     headers={"X-Tenant-ID": str(test_tenant_id)}
        # )
        #
        # assert rollback_resp.status_code == 200
        # rollback_data = rollback_resp.json()
        # assert rollback_data["status"] == "rolled_back"


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_canary_sticky_session(db_session: Session, test_tenant_id):
    """
    Sticky Session 테스트

    플로우:
    1. Canary 시작
    2. 특정 사용자에게 v2 할당
    3. 동일 사용자 재요청 시 v2 유지 확인
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Note: Sticky Session은 실제 judgment/workflow 실행 시 동작하므로
        # API 레벨에서는 할당만 확인 가능
        # TODO: 실제 Ruleset 생성 및 Canary 배포 후 테스트 구현 필요
        pass

        # deployment_id 가정
        # ...

        # 할당 조회
        # assignments_resp = await client.get(
        #     f"/api/v1/deployments/{deployment_id}/assignments?user_id={test_user_id}",
        #     headers={"X-Tenant-ID": str(test_tenant_id)}
        # )
        #
        # assert assignments_resp.status_code == 200
        # assignments = assignments_resp.json()["assignments"]
        #
        # if len(assignments) > 0:
        #     # 동일 사용자는 동일 버전 유지
        #     first_version = assignments[0]["canary_version_id"]
        #     for assignment in assignments:
        #         assert assignment["canary_version_id"] == first_version


@pytest.mark.asyncio
async def test_canary_health_check(db_session: Session, test_tenant_id):
    """
    Canary 건강 상태 체크 테스트

    검증:
    - health_status 조회
    - circuit_breaker_state 확인
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # TODO: 실제 Ruleset 생성 및 Canary 배포 후 테스트 구현 필요
        pass

        # deployment_id 가정
        # ...

        # 건강 상태 조회
        # health_resp = await client.get(
        #     f"/api/v1/deployments/{deployment_id}/health",
        #     headers={"X-Tenant-ID": str(test_tenant_id)}
        # )
        #
        # assert health_resp.status_code == 200
        # health = health_resp.json()
        #
        # assert "health_status" in health
        # assert "circuit_breaker_state" in health
        # assert health["circuit_breaker_state"] in ["CLOSED", "OPEN", "HALF_OPEN"]
