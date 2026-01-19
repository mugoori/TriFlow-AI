# -*- coding: utf-8 -*-
"""
Learning Pipeline Integration Tests
End-to-end workflow: Feedback → Sample → Rule Candidate → Approval

완전한 학습 파이프라인 워크플로우 검증
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.sample_curation_service import SampleCurationService
from app.services.rule_extraction_service import RuleExtractionService
from app.services.golden_sample_set_service import GoldenSampleSetService
from app.models import FeedbackLog, JudgmentExecution
from app.schemas.sample import SampleExtractRequest, GoldenSetCreate, GoldenSetAutoUpdateRequest
from app.schemas.rule_extraction import RuleExtractionRequest, TestRequest, ApproveRequest


class TestLearningPipelineIntegration:
    """E2E Learning Pipeline Tests"""

    @pytest.fixture
    def sample_curation_service(self, db_session):
        """Sample Curation Service fixture"""
        return SampleCurationService(db_session)

    @pytest.fixture
    def rule_extraction_service(self, db_session):
        """Rule Extraction Service fixture"""
        return RuleExtractionService(db_session)

    @pytest.fixture
    def golden_set_service(self, db_session):
        """Golden Sample Set Service fixture"""
        return GoldenSampleSetService(db_session)

    @pytest.fixture
    def test_tenant_id(self):
        """Test tenant ID"""
        return uuid4()

    @pytest.fixture
    def test_user_id(self):
        """Test user ID"""
        return uuid4()

    def create_test_feedback_logs(self, db_session, tenant_id, count=50):
        """Create test feedback logs with varied quality"""
        feedback_logs = []

        for i in range(count):
            # Create JudgmentExecution
            execution = JudgmentExecution(
                execution_id=uuid4(),
                tenant_id=tenant_id,
                ruleset_id=uuid4(),
                input_data={
                    "temperature": 70.0 + i,
                    "pressure": 100.0 + i * 0.5,
                    "humidity": 50.0,
                    "defect_rate": 0.01 * i,
                },
                result="normal" if i % 3 != 0 else "warning",
                confidence=0.8 if i % 3 != 0 else 0.6,
                method_used="hybrid",
                trust_level=2,
                executed_at=datetime.utcnow() - timedelta(days=i % 7),
            )
            db_session.add(execution)

            # Create FeedbackLog
            feedback = FeedbackLog(
                feedback_id=uuid4(),
                tenant_id=tenant_id,
                execution_id=execution.execution_id,
                user_id=uuid4(),
                feedback_type="correction" if i % 5 == 0 else "positive",
                rating=5 if i % 2 == 0 else 4,
                comment=f"Test feedback {i}",
                corrected_result="critical" if i % 10 == 0 else None,
                original_output={"status": execution.result},
                corrected_output={"status": "critical"} if i % 10 == 0 else None,
                context_data={"agent_type": "judgment"},
                is_processed=False,
                created_at=datetime.utcnow() - timedelta(days=i % 7),
            )
            db_session.add(feedback)
            feedback_logs.append(feedback)

        db_session.commit()
        return feedback_logs

    def test_feedback_to_approved_rule_workflow(
        self,
        db_session,
        sample_curation_service,
        rule_extraction_service,
        test_tenant_id,
        test_user_id,
    ):
        """
        Complete workflow:
        1. Create feedback logs
        2. Extract samples from feedback
        3. Approve samples
        4. Extract rules from samples
        5. Test rule candidate
        6. Approve candidate → ProposedRule
        """
        # 1. Setup: Create 50 feedback logs
        feedback_logs = self.create_test_feedback_logs(db_session, test_tenant_id, count=50)
        assert len(feedback_logs) == 50

        # 2. Extract samples (should get 30+)
        extract_request = SampleExtractRequest(
            days=7,
            dry_run=False,
            min_quality_score=0.5,
        )
        samples, skipped = sample_curation_service.extract_samples_from_feedback(
            tenant_id=test_tenant_id,
            request=extract_request,
        )
        assert len(samples) >= 30, f"Expected at least 30 samples, got {len(samples)}"
        assert skipped >= 0

        # 3. Approve samples (filter quality > 0.6)
        approved_count = 0
        for sample in samples:
            if sample.quality_score and sample.quality_score >= 0.6:
                sample_curation_service.approve_sample(sample.sample_id, test_user_id)
                approved_count += 1

        assert approved_count >= 20, f"Expected at least 20 approved samples, got {approved_count}"

        # 4. Extract rules (min_samples=20)
        extraction_request = RuleExtractionRequest(
            category=None,  # All categories
            min_samples=20,
            max_depth=5,
            min_samples_split=10,
        )

        candidate, metrics, feature_importance = rule_extraction_service.extract_rules(
            tenant_id=test_tenant_id,
            request=extraction_request,
        )

        assert candidate is not None
        assert candidate.approval_status == "pending"
        assert metrics.get("coverage", 0) > 0
        assert metrics.get("precision", 0) > 0

        # 5. Verify candidate metrics (coverage > 0.5)
        assert metrics["coverage"] >= 0.5, f"Coverage too low: {metrics['coverage']}"

        # 6. Test candidate with test samples
        test_samples_data = [
            {
                "input": {
                    "temperature": 75.0,
                    "pressure": 105.0,
                    "humidity": 50.0,
                    "defect_rate": 0.05,
                },
                "expected_output": {"status": "normal"},
            }
        ]

        test_request = TestRequest(test_samples=test_samples_data)
        test_results = rule_extraction_service.test_candidate(
            candidate_id=candidate.candidate_id,
            request=test_request,
        )

        assert test_results is not None
        assert "test_count" in test_results
        assert test_results["test_count"] == 1

        # 7. Approve candidate
        approve_request = ApproveRequest(
            rule_name="Auto-Generated Rule",
            description="Automatically extracted from feedback",
        )

        proposed_rule = rule_extraction_service.approve_candidate(
            candidate_id=candidate.candidate_id,
            request=approve_request,
            approver_id=test_user_id,
        )

        # 8. Verify ProposedRule created
        assert proposed_rule is not None
        assert proposed_rule.rule_name == "Auto-Generated Rule"
        assert proposed_rule.source_type == "auto_extraction"
        assert proposed_rule.status == "pending"

        # Verify candidate status updated
        db_session.refresh(candidate)
        assert candidate.approval_status == "approved"
        assert candidate.approver_id == test_user_id

    def test_golden_set_auto_update(
        self,
        db_session,
        sample_curation_service,
        golden_set_service,
        test_tenant_id,
        test_user_id,
    ):
        """
        Golden set workflow:
        1. Create golden set
        2. Add initial samples
        3. Create new high-quality samples
        4. Trigger auto-update
        5. Verify new samples added
        """
        # 1. Create golden set
        golden_set_request = GoldenSetCreate(
            name="Test Golden Set",
            description="For testing auto-update",
            category="threshold_adjustment",
            min_quality_score=0.7,
            max_samples=100,
            auto_update=True,
        )

        golden_set = golden_set_service.create_set(
            tenant_id=test_tenant_id,
            request=golden_set_request,
            created_by=test_user_id,
        )

        assert golden_set is not None
        assert golden_set.auto_update is True

        # 2. Create and approve initial samples
        initial_sample_count = 5
        for i in range(initial_sample_count):
            sample = sample_curation_service.create_sample(
                tenant_id=test_tenant_id,
                request={
                    "category": "threshold_adjustment",
                    "input_data": {"temperature": 70.0 + i},
                    "expected_output": {"status": "normal"},
                    "source_type": "manual",
                    "confidence": 0.8,
                },
            )
            sample_curation_service.approve_sample(sample.sample_id, test_user_id)

            # Add to golden set
            golden_set_service.add_sample(
                set_id=golden_set.set_id,
                sample_id=sample.sample_id,
                added_by=test_user_id,
            )

        # 3. Create new high-quality samples
        new_sample_count = 10
        new_samples = []
        for i in range(new_sample_count):
            sample = sample_curation_service.create_sample(
                tenant_id=test_tenant_id,
                request={
                    "category": "threshold_adjustment",
                    "input_data": {"temperature": 80.0 + i},
                    "expected_output": {"status": "warning"},
                    "source_type": "manual",
                    "confidence": 0.85,  # High quality
                },
            )
            sample_curation_service.approve_sample(sample.sample_id, test_user_id)
            new_samples.append(sample)

        # 4. Trigger auto-update
        auto_update_request = GoldenSetAutoUpdateRequest(force=False)
        result = golden_set_service.auto_update_set(
            set_id=golden_set.set_id,
            request=auto_update_request,
        )

        # 5. Verify new samples added
        assert result["added_count"] > 0, "No samples were added during auto-update"
        assert result["current_sample_count"] == initial_sample_count + result["added_count"]

        # Verify samples in set
        samples, total = golden_set_service.get_samples(set_id=golden_set.set_id, page=1, page_size=50)
        assert total >= initial_sample_count

    def test_rbac_permissions(self, db_session, test_tenant_id):
        """
        Verify RBAC enforcement:
        - Viewer: can only read (tested via API layer)
        - User: can create samples
        - Operator: can extract samples
        - Approver: can approve samples/candidates
        - Admin: all permissions

        Note: Full RBAC testing requires API-level tests with different user roles
        This test verifies the service layer works correctly
        """
        # This is a placeholder for RBAC testing
        # Full tests should be done at API level with authentication
        service = SampleCurationService(db_session)

        # Verify service methods work without permission checks
        sample = service.create_sample(
            tenant_id=test_tenant_id,
            request={
                "category": "general",
                "input_data": {"test": "data"},
                "expected_output": {"status": "normal"},
                "source_type": "manual",
            },
        )

        assert sample is not None
        assert sample.tenant_id == test_tenant_id

    def test_sample_extraction_deduplication(
        self,
        db_session,
        sample_curation_service,
        test_tenant_id,
    ):
        """
        Verify deduplication works:
        1. Create feedback with same input/output
        2. Extract samples twice
        3. Verify only one sample created (deduplication by content_hash)
        """
        # Create two identical feedback logs
        execution = JudgmentExecution(
            execution_id=uuid4(),
            tenant_id=test_tenant_id,
            ruleset_id=uuid4(),
            input_data={"temperature": 75.0, "pressure": 100.0},
            result="normal",
            confidence=0.8,
            method_used="hybrid",
            trust_level=2,
            executed_at=datetime.utcnow(),
        )
        db_session.add(execution)

        feedback1 = FeedbackLog(
            feedback_id=uuid4(),
            tenant_id=test_tenant_id,
            execution_id=execution.execution_id,
            user_id=uuid4(),
            feedback_type="correction",
            rating=5,
            corrected_result="warning",
            original_output={"status": "normal"},
            corrected_output={"status": "warning"},
            is_processed=False,
            created_at=datetime.utcnow(),
        )
        db_session.add(feedback1)

        feedback2 = FeedbackLog(
            feedback_id=uuid4(),
            tenant_id=test_tenant_id,
            execution_id=execution.execution_id,
            user_id=uuid4(),
            feedback_type="correction",
            rating=5,
            corrected_result="warning",
            original_output={"status": "normal"},
            corrected_output={"status": "warning"},
            is_processed=False,
            created_at=datetime.utcnow(),
        )
        db_session.add(feedback2)
        db_session.commit()

        # Extract samples
        extract_request = SampleExtractRequest(days=1, dry_run=False)
        samples, skipped = sample_curation_service.extract_samples_from_feedback(
            tenant_id=test_tenant_id,
            request=extract_request,
        )

        # Verify only one sample created (second was duplicate)
        assert len(samples) == 1, f"Expected 1 sample, got {len(samples)}"
        assert skipped == 1, f"Expected 1 skipped duplicate, got {skipped}"

        # Verify content_hash is set
        assert samples[0].content_hash is not None
        assert len(samples[0].content_hash) == 32  # MD5 hash length


# Pytest configuration
@pytest.fixture
def db_session():
    """
    Database session fixture
    Note: This assumes pytest fixtures are configured in conftest.py
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
