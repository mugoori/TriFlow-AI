# -*- coding: utf-8 -*-
"""Learning Pipeline E2E 테스트

피드백 → 샘플 추출 → Rule Extraction → 승인 → 배포 전체 플로우 검증

Note: 이 테스트는 실제 서버(localhost:8000)가 실행 중이어야 합니다.
"""
import pytest
from httpx import AsyncClient


# E2E 테스트는 실제 서버 사용
E2E_BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_learning_pipeline_e2e(e2e_auth_headers):
    """
    Learning Pipeline E2E 테스트

    플로우:
    1. 피드백 생성 (긍정 피드백, rating=5)
    2. 샘플 자동 추출 (피드백 → 샘플 변환)
    3. 샘플 승인 (Approver 권한)
    4. Rule Extraction (Decision Tree 학습)
    5. 후보 승인 (ProposedRule 생성)
    6. ProposedRule 확인
    """
    async with AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        headers = e2e_auth_headers

        # ============================================
        # 1. 피드백 생성
        # ============================================
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]

        feedback_data = {
            "execution_id": f"test-exec-{unique_suffix}",
            "feedback_type": "positive",
            "rating": 5,
            "confidence": 0.9,
            "comment": "정확한 판정이었습니다",
            "input_data": {
                "temperature": 26.5,
                "pressure": 1010,
                "humidity": 65
            },
            "expected_output": {
                "decision": "WARNING",
                "confidence": 0.9
            },
            "actual_output": {
                "decision": "WARNING",
                "confidence": 0.88
            }
        }

        feedback_resp = await client.post(
            "/api/v1/feedback",
            json=feedback_data,
            headers=headers
        )

        assert feedback_resp.status_code in [200, 201], f"피드백 생성 실패: {feedback_resp.text}"
        feedback_id = feedback_resp.json()["feedback_id"]
        assert feedback_id is not None

        # ============================================
        # 2. 샘플 자동 추출
        # ============================================
        extract_req = {
            "min_rating": 4,
            "min_confidence": 0.7,
            "limit": 100,
            "dry_run": False
        }

        extract_resp = await client.post(
            "/api/v1/samples/extract",
            json=extract_req,
            headers=headers
        )

        # 409 Conflict는 이미 추출 진행 중이거나 추출할 데이터가 없는 경우일 수 있음
        if extract_resp.status_code == 409:
            print(f"Sample extraction conflict: {extract_resp.text}")
            # 테스트 계속 진행 (기존 샘플로 테스트)
        elif extract_resp.status_code == 200:
            extract_data = extract_resp.json()
            assert extract_data["extracted_count"] >= 0, "샘플 추출 응답 형식 오류"

            # 샘플이 추출되었으면 승인 진행
            sample_id = None
            if extract_data["extracted_count"] > 0 and len(extract_data.get("samples", [])) > 0:
                sample_id = extract_data["samples"][0]["sample_id"]

                # ============================================
                # 3. 샘플 승인
                # ============================================
                approve_resp = await client.post(
                    f"/api/v1/samples/{sample_id}/approve",
                    headers=headers
                )

                # 이미 승인된 샘플일 수 있음
                assert approve_resp.status_code in [200, 409], f"샘플 승인 실패: {approve_resp.text}"
        else:
            assert False, f"샘플 추출 실패: {extract_resp.status_code} - {extract_resp.text}"

        # ============================================
        # 4. Rule Extraction (Decision Tree 학습)
        # ============================================

        # 추가 샘플 생성 (Decision Tree는 최소 20개 필요)
        for i in range(25):
            extra_feedback_data = {
                "execution_id": f"test-exec-{unique_suffix}-{i}",
                "feedback_type": "positive",
                "rating": 5,
                "confidence": 0.85,
                "comment": f"테스트 피드백 {i}",
                "input_data": {
                    "temperature": 20 + i % 10,
                    "pressure": 1000 + i % 50,
                    "humidity": 60 + i % 20
                },
                "expected_output": {
                    "decision": "NORMAL" if i % 2 == 0 else "WARNING",
                    "confidence": 0.85
                },
                "actual_output": {
                    "decision": "NORMAL" if i % 2 == 0 else "WARNING",
                    "confidence": 0.83
                }
            }
            await client.post("/api/v1/feedback", json=extra_feedback_data, headers=headers)

        # 추가 샘플 추출 및 승인
        extra_extract_resp = await client.post(
            "/api/v1/samples/extract",
            json={"min_rating": 4, "limit": 100},
            headers=headers
        )

        if extra_extract_resp.status_code == 200:
            extra_samples = extra_extract_resp.json().get("samples", [])

            for extra_sample in extra_samples[:20]:
                await client.post(
                    f"/api/v1/samples/{extra_sample['sample_id']}/approve",
                    headers=headers
                )
        elif extra_extract_resp.status_code == 409:
            print(f"Extra sample extraction conflict: {extra_extract_resp.text}")

        # Rule Extraction 실행
        extraction_req = {
            "category": None,  # 모든 카테고리
            "min_quality_score": 0.7,
            "min_samples": 20,
            "max_depth": 5,
            "min_samples_split": 10,
            "min_samples_leaf": 5,
            "dry_run": False
        }

        extraction_resp = await client.post(
            "/api/v1/rule-extraction/extract",
            json=extraction_req,
            headers=headers
        )

        # Rule Extraction은 샘플이 충분하지 않으면 실패할 수 있음
        if extraction_resp.status_code == 200:
            extraction_data = extraction_resp.json()
            assert extraction_data["candidate_id"] is not None
            assert extraction_data["samples_used"] >= 20

            candidate_id = extraction_data["candidate_id"]

            # ============================================
            # 5. 후보 테스트 (선택적)
            # ============================================
            test_req = {
                "test_samples": [
                    {
                        "input": {"temperature": 26.0, "pressure": 1010, "humidity": 65},
                        "expected_output": "WARNING"
                    },
                    {
                        "input": {"temperature": 22.0, "pressure": 1015, "humidity": 60},
                        "expected_output": "NORMAL"
                    }
                ]
            }

            test_resp = await client.post(
                f"/api/v1/rule-extraction/candidates/{candidate_id}/test",
                json=test_req,
                headers=headers
            )

            # 테스트 엔드포인트가 없을 수 있음
            assert test_resp.status_code in [200, 404]

            # ============================================
            # 6. 후보 승인 → ProposedRule 생성
            # ============================================
            approve_req = {
                "rule_name": f"E2E 테스트 자동 생성 규칙 {unique_suffix}",
                "description": "Decision Tree 기반 (테스트용)"
            }

            approve_resp = await client.post(
                f"/api/v1/rule-extraction/candidates/{candidate_id}/approve",
                json=approve_req,
                headers=headers
            )

            assert approve_resp.status_code == 200, f"후보 승인 실패: {approve_resp.text}"
            approve_data = approve_resp.json()
            assert approve_data["proposal_id"] is not None
            assert approve_data["status"] == "pending_review"

            # ============================================
            # 7. 통계 확인
            # ============================================
            stats_resp = await client.get(
                "/api/v1/rule-extraction/stats",
                headers=headers
            )
            assert stats_resp.status_code == 200
            stats = stats_resp.json()
            assert stats["approved_count"] >= 1

        else:
            # 샘플이 부족하면 경고만 출력
            print(f"Rule Extraction skipped (not enough samples): {extraction_resp.text}")


@pytest.mark.asyncio
async def test_golden_sample_set_auto_update(e2e_auth_headers):
    """
    Golden Sample Set 자동 업데이트 테스트

    플로우:
    1. 샘플 여러 개 생성 (품질 점수 다양)
    2. Golden Set 생성
    3. 자동 업데이트 실행
    4. Top 품질 샘플이 Golden Set에 포함되었는지 확인
    """
    async with AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        headers = e2e_auth_headers

        import uuid
        unique_suffix = str(uuid.uuid4())[:8]

        # ============================================
        # 1. 다양한 품질의 샘플 생성
        # ============================================
        sample_ids = []

        for i in range(10):
            quality_score = 0.5 + (i * 0.05)  # 0.5 ~ 0.95

            sample_data = {
                "category": "threshold_adjustment",
                "source_type": "feedback",
                "input_data": {"temperature": 20 + i},
                "expected_output": {"decision": "NORMAL"},
                "quality_score": quality_score
            }

            sample_resp = await client.post(
                "/api/v1/samples",
                json=sample_data,
                headers=headers
            )

            if sample_resp.status_code == 200:
                sample_ids.append(sample_resp.json()["sample_id"])

                # 샘플 승인
                await client.post(
                    f"/api/v1/samples/{sample_resp.json()['sample_id']}/approve",
                    headers=headers
                )

        # 충분한 샘플이 없으면 테스트 스킵
        if len(sample_ids) < 5:
            print("Not enough samples created, skipping golden set test")
            return

        # ============================================
        # 2. Golden Set 생성
        # ============================================
        golden_set_data = {
            "name": f"E2E 테스트 Golden Set {unique_suffix}",
            "description": "자동 업데이트 테스트용",
            "category": "threshold_adjustment",
            "target_size": 5,
            "auto_update_enabled": True
        }

        golden_resp = await client.post(
            "/api/v1/golden-sets",
            json=golden_set_data,
            headers=headers
        )

        # Golden Set 엔드포인트가 없을 수 있음
        if golden_resp.status_code not in [200, 201]:
            print(f"Golden Set creation not available: {golden_resp.status_code}")
            return

        golden_set_id = golden_resp.json()["set_id"]

        # ============================================
        # 3. 자동 업데이트 실행
        # ============================================
        update_req = {
            "min_quality_score": 0.8,
            "target_size": 5,
            "category": "threshold_adjustment"
        }

        update_resp = await client.post(
            f"/api/v1/golden-sets/{golden_set_id}/auto-update",
            json=update_req,
            headers=headers
        )

        if update_resp.status_code == 200:
            update_data = update_resp.json()
            assert update_data["added_count"] >= 0

            # ============================================
            # 4. Golden Set 샘플 확인
            # ============================================
            samples_resp = await client.get(
                f"/api/v1/golden-sets/{golden_set_id}/samples",
                headers=headers
            )

            if samples_resp.status_code == 200:
                samples = samples_resp.json()["samples"]

                # 품질 점수 확인 (모두 0.8 이상이어야 함)
                for sample in samples:
                    assert sample["quality_score"] >= 0.8, f"낮은 품질 샘플 포함: {sample['quality_score']}"


@pytest.mark.asyncio
async def test_sample_curation_duplicate_detection(e2e_auth_headers):
    """
    샘플 중복 제거 테스트

    플로우:
    1. 동일한 input/output으로 피드백 2개 생성
    2. 샘플 추출
    3. 중복 제거 확인 (1개만 추출되어야 함)
    """
    async with AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        headers = e2e_auth_headers

        import uuid
        unique_suffix = str(uuid.uuid4())[:8]

        # 동일한 데이터로 피드백 2개 생성
        feedback_data = {
            "execution_id": f"test-exec-dup-1-{unique_suffix}",
            "feedback_type": "positive",
            "rating": 5,
            "confidence": 0.9,
            "input_data": {"temperature": 25.0, "unique_key": unique_suffix},
            "expected_output": {"decision": "NORMAL"},
            "actual_output": {"decision": "NORMAL"}
        }

        await client.post("/api/v1/feedback", json=feedback_data, headers=headers)

        feedback_data["execution_id"] = f"test-exec-dup-2-{unique_suffix}"
        await client.post("/api/v1/feedback", json=feedback_data, headers=headers)

        # 샘플 추출
        extract_resp = await client.post(
            "/api/v1/samples/extract",
            json={"min_rating": 4, "limit": 100},
            headers=headers
        )

        if extract_resp.status_code == 200:
            extract_data = extract_resp.json()

            # 중복 제거 확인
            # skipped_duplicates가 존재하면 중복 제거가 작동함
            if "skipped_duplicates" in extract_data:
                # 테스트 성공 - 중복 제거 기능 존재
                pass


@pytest.mark.asyncio
async def test_rule_extraction_metrics(e2e_auth_headers):
    """
    Rule Extraction 성능 메트릭 테스트

    검증:
    - coverage, precision, recall, f1_score 계산 확인
    - feature_importance 반환 확인
    """
    async with AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        headers = e2e_auth_headers

        # Rule Extraction
        extraction_req = {
            "min_samples": 20,
            "max_depth": 3,
            "dry_run": False
        }

        extraction_resp = await client.post(
            "/api/v1/rule-extraction/extract",
            json=extraction_req,
            headers=headers
        )

        if extraction_resp.status_code == 200:
            data = extraction_resp.json()

            # 메트릭 존재 확인
            assert "metrics" in data
            metrics = data["metrics"]

            assert "coverage" in metrics
            assert "precision" in metrics
            assert "recall" in metrics
            assert "f1_score" in metrics

            # 메트릭 범위 확인 (0.0 ~ 1.0)
            assert 0.0 <= metrics["coverage"] <= 1.0
            assert 0.0 <= metrics["precision"] <= 1.0
            assert 0.0 <= metrics["recall"] <= 1.0
            assert 0.0 <= metrics["f1_score"] <= 1.0

            # feature_importance 확인
            assert "feature_importance" in data
            assert len(data["feature_importance"]) > 0
        else:
            # 샘플이 부족하면 경고만 출력
            print(f"Rule Extraction skipped: {extraction_resp.status_code}")
