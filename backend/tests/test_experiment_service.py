"""
Experiment Service 테스트
A/B 테스트 실험 관리 서비스 테스트
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.services.experiment_service import ExperimentService
from app.models import (
    Experiment,
    ExperimentVariant,
    ExperimentAssignment,
    ExperimentMetric,
    Ruleset,
    Tenant,
)


class TestExperimentCRUD:
    """Experiment CRUD 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        """ExperimentService 인스턴스"""
        return ExperimentService(mock_db)

    @pytest.fixture
    def sample_experiment(self):
        """샘플 Experiment"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.tenant_id = uuid4()
        exp.name = "Test Experiment"
        exp.status = "draft"
        exp.traffic_percentage = 100
        exp.min_sample_size = 100
        exp.confidence_level = 0.95
        exp.variants = []
        return exp

    def test_create_experiment(self, service, mock_db):
        """실험 생성 테스트"""
        tenant_id = uuid4()
        user_id = uuid4()

        result = service.create_experiment(
            tenant_id=tenant_id,
            name="New Experiment",
            description="Test description",
            hypothesis="Test hypothesis",
            traffic_percentage=50,
            min_sample_size=200,
            confidence_level=0.90,
            created_by=user_id,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_get_experiment_found(self, service, mock_db, sample_experiment):
        """실험 조회 - 존재하는 경우"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_experiment

        result = service.get_experiment(sample_experiment.experiment_id)

        assert result == sample_experiment
        mock_db.query.assert_called_once()

    def test_get_experiment_not_found(self, service, mock_db):
        """실험 조회 - 존재하지 않는 경우"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_experiment(uuid4())

        assert result is None

    def test_list_experiments(self, service, mock_db, sample_experiment):
        """실험 목록 조회"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_experiment]

        tenant_id = uuid4()
        result = service.list_experiments(tenant_id=tenant_id, status="running", limit=10, offset=0)

        assert len(result) == 1
        assert result[0] == sample_experiment

    def test_list_experiments_no_filter(self, service, mock_db, sample_experiment):
        """실험 목록 조회 - 필터 없이"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_experiment]

        result = service.list_experiments()

        assert len(result) == 1

    def test_update_experiment_draft(self, service, mock_db, sample_experiment):
        """실험 수정 - draft 상태"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_experiment
        sample_experiment.status = "draft"

        result = service.update_experiment(
            sample_experiment.experiment_id,
            name="Updated Name",
            description="Updated desc",
        )

        assert result.name == "Updated Name"
        mock_db.commit.assert_called_once()

    def test_update_experiment_not_draft(self, service, mock_db, sample_experiment):
        """실험 수정 - draft가 아닌 상태에서 오류"""
        sample_experiment.status = "running"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_experiment

        with pytest.raises(ValueError, match="draft 상태일 때만"):
            service.update_experiment(sample_experiment.experiment_id, name="New Name")

    def test_update_experiment_not_found(self, service, mock_db):
        """실험 수정 - 존재하지 않는 경우"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.update_experiment(uuid4(), name="New Name")

        assert result is None

    def test_delete_experiment_draft(self, service, mock_db, sample_experiment):
        """실험 삭제 - draft 상태"""
        sample_experiment.status = "draft"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_experiment

        result = service.delete_experiment(sample_experiment.experiment_id)

        assert result is True
        mock_db.delete.assert_called_once_with(sample_experiment)
        mock_db.commit.assert_called_once()

    def test_delete_experiment_cancelled(self, service, mock_db, sample_experiment):
        """실험 삭제 - cancelled 상태"""
        sample_experiment.status = "cancelled"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_experiment

        result = service.delete_experiment(sample_experiment.experiment_id)

        assert result is True

    def test_delete_experiment_running(self, service, mock_db, sample_experiment):
        """실험 삭제 - running 상태에서 오류"""
        sample_experiment.status = "running"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_experiment

        with pytest.raises(ValueError, match="draft 또는 cancelled 상태"):
            service.delete_experiment(sample_experiment.experiment_id)

    def test_delete_experiment_not_found(self, service, mock_db):
        """실험 삭제 - 존재하지 않는 경우"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.delete_experiment(uuid4())

        assert result is False


class TestVariantManagement:
    """Variant 관리 테스트"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ExperimentService(mock_db)

    @pytest.fixture
    def sample_experiment(self):
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "draft"
        exp.variants = []
        return exp

    @pytest.fixture
    def sample_variant(self, sample_experiment):
        variant = MagicMock(spec=ExperimentVariant)
        variant.variant_id = uuid4()
        variant.experiment_id = sample_experiment.experiment_id
        variant.name = "Control"
        variant.is_control = True
        variant.traffic_weight = 50
        return variant

    def test_add_variant_success(self, service, mock_db, sample_experiment):
        """변형 추가 성공"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_experiment

        result = service.add_variant(
            experiment_id=sample_experiment.experiment_id,
            name="Control",
            is_control=True,
            traffic_weight=50,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_add_variant_experiment_not_found(self, service, mock_db):
        """변형 추가 - 실험 없음"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="실험을 찾을 수 없습니다"):
            service.add_variant(experiment_id=uuid4(), name="Control")

    def test_add_variant_not_draft(self, service, mock_db, sample_experiment):
        """변형 추가 - draft가 아닌 상태"""
        sample_experiment.status = "running"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_experiment

        with pytest.raises(ValueError, match="draft 상태의 실험에만"):
            service.add_variant(experiment_id=sample_experiment.experiment_id, name="Control")

    def test_update_variant_success(self, service, mock_db, sample_experiment, sample_variant):
        """변형 수정 성공"""
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_variant,
            sample_experiment,
        ]

        result = service.update_variant(
            variant_id=sample_variant.variant_id,
            name="Updated Control",
            traffic_weight=60,
        )

        assert result.name == "Updated Control"
        mock_db.commit.assert_called_once()

    def test_update_variant_not_found(self, service, mock_db):
        """변형 수정 - 존재하지 않음"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.update_variant(uuid4(), name="New Name")

        assert result is None

    def test_update_variant_not_draft(self, service, mock_db, sample_experiment, sample_variant):
        """변형 수정 - draft가 아닌 상태"""
        sample_experiment.status = "running"
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_variant,
            sample_experiment,
        ]

        with pytest.raises(ValueError, match="draft 상태의 실험에서만"):
            service.update_variant(sample_variant.variant_id, name="New Name")

    def test_delete_variant_success(self, service, mock_db, sample_experiment, sample_variant):
        """변형 삭제 성공"""
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_variant,
            sample_experiment,
        ]

        result = service.delete_variant(sample_variant.variant_id)

        assert result is True
        mock_db.delete.assert_called_once_with(sample_variant)

    def test_delete_variant_not_found(self, service, mock_db):
        """변형 삭제 - 존재하지 않음"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.delete_variant(uuid4())

        assert result is False

    def test_delete_variant_not_draft(self, service, mock_db, sample_experiment, sample_variant):
        """변형 삭제 - draft가 아닌 상태"""
        sample_experiment.status = "running"
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_variant,
            sample_experiment,
        ]

        with pytest.raises(ValueError, match="draft 상태의 실험에서만"):
            service.delete_variant(sample_variant.variant_id)


class TestExperimentLifecycle:
    """실험 생명주기 테스트"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ExperimentService(mock_db)

    @pytest.fixture
    def sample_experiment_with_variants(self):
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "draft"
        exp.traffic_percentage = 100

        control = MagicMock(spec=ExperimentVariant)
        control.variant_id = uuid4()
        control.is_control = True
        control.traffic_weight = 50

        treatment = MagicMock(spec=ExperimentVariant)
        treatment.variant_id = uuid4()
        treatment.is_control = False
        treatment.traffic_weight = 50

        exp.variants = [control, treatment]
        return exp

    def test_start_experiment_success(self, service, mock_db, sample_experiment_with_variants):
        """실험 시작 성공"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_experiment_with_variants

        result = service.start_experiment(sample_experiment_with_variants.experiment_id)

        assert result.status == "running"
        assert result.start_date is not None
        mock_db.commit.assert_called_once()

    def test_start_experiment_not_found(self, service, mock_db):
        """실험 시작 - 실험 없음"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="실험을 찾을 수 없습니다"):
            service.start_experiment(uuid4())

    def test_start_experiment_not_draft(self, service, mock_db, sample_experiment_with_variants):
        """실험 시작 - draft가 아닌 상태"""
        sample_experiment_with_variants.status = "running"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_experiment_with_variants

        with pytest.raises(ValueError, match="draft 상태의 실험만"):
            service.start_experiment(sample_experiment_with_variants.experiment_id)

    def test_start_experiment_insufficient_variants(self, service, mock_db):
        """실험 시작 - 변형 부족"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "draft"
        exp.variants = [MagicMock()]  # 1개만
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        with pytest.raises(ValueError, match="최소 2개의 변형이 필요합니다"):
            service.start_experiment(exp.experiment_id)

    def test_start_experiment_no_control(self, service, mock_db):
        """실험 시작 - control 그룹 없음"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "draft"

        v1 = MagicMock()
        v1.is_control = False
        v1.traffic_weight = 50
        v2 = MagicMock()
        v2.is_control = False
        v2.traffic_weight = 50
        exp.variants = [v1, v2]
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        with pytest.raises(ValueError, match="control 그룹이 필요합니다"):
            service.start_experiment(exp.experiment_id)

    def test_start_experiment_invalid_weight(self, service, mock_db):
        """실험 시작 - 가중치 합계 오류"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "draft"

        v1 = MagicMock()
        v1.is_control = True
        v1.traffic_weight = 30
        v2 = MagicMock()
        v2.is_control = False
        v2.traffic_weight = 30
        exp.variants = [v1, v2]  # 합계 60
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        with pytest.raises(ValueError, match="트래픽 가중치 합계가 100%"):
            service.start_experiment(exp.experiment_id)

    def test_pause_experiment_success(self, service, mock_db):
        """실험 일시정지"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "running"
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        result = service.pause_experiment(exp.experiment_id)

        assert result.status == "paused"

    def test_pause_experiment_not_running(self, service, mock_db):
        """실험 일시정지 - running이 아닌 상태"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "paused"
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        with pytest.raises(ValueError, match="running 상태의 실험만"):
            service.pause_experiment(exp.experiment_id)

    def test_resume_experiment_success(self, service, mock_db):
        """실험 재개"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "paused"
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        result = service.resume_experiment(exp.experiment_id)

        assert result.status == "running"

    def test_resume_experiment_not_paused(self, service, mock_db):
        """실험 재개 - paused가 아닌 상태"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "running"
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        with pytest.raises(ValueError, match="paused 상태의 실험만"):
            service.resume_experiment(exp.experiment_id)

    def test_complete_experiment_from_running(self, service, mock_db):
        """실험 완료 - running 상태에서"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "running"
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        result = service.complete_experiment(exp.experiment_id)

        assert result.status == "completed"
        assert result.end_date is not None

    def test_complete_experiment_from_paused(self, service, mock_db):
        """실험 완료 - paused 상태에서"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "paused"
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        result = service.complete_experiment(exp.experiment_id)

        assert result.status == "completed"

    def test_complete_experiment_invalid_status(self, service, mock_db):
        """실험 완료 - 잘못된 상태"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "draft"
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        with pytest.raises(ValueError, match="running 또는 paused 상태"):
            service.complete_experiment(exp.experiment_id)

    def test_cancel_experiment_success(self, service, mock_db):
        """실험 취소"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "running"
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        result = service.cancel_experiment(exp.experiment_id)

        assert result.status == "cancelled"
        assert result.end_date is not None

    def test_cancel_experiment_completed(self, service, mock_db):
        """실험 취소 - 완료된 실험"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "completed"
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        with pytest.raises(ValueError, match="완료된 실험은 취소할 수 없습니다"):
            service.cancel_experiment(exp.experiment_id)


class TestAssignmentLogic:
    """사용자 할당 로직 테스트"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ExperimentService(mock_db)

    @pytest.fixture
    def running_experiment(self):
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "running"
        exp.traffic_percentage = 100

        control = MagicMock(spec=ExperimentVariant)
        control.variant_id = uuid4()
        control.is_control = True
        control.traffic_weight = 50

        treatment = MagicMock(spec=ExperimentVariant)
        treatment.variant_id = uuid4()
        treatment.is_control = False
        treatment.traffic_weight = 50

        exp.variants = [control, treatment]
        return exp

    def test_assign_user_no_identifier(self, service):
        """할당 - 식별자 없음"""
        with pytest.raises(ValueError, match="user_id 또는 session_id"):
            service.assign_user_to_variant(uuid4())

    def test_assign_user_experiment_not_found(self, service, mock_db):
        """할당 - 실험 없음"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.assign_user_to_variant(uuid4(), user_id=uuid4())

        assert result is None

    def test_assign_user_experiment_not_running(self, service, mock_db):
        """할당 - 실험이 running이 아님"""
        exp = MagicMock(spec=Experiment)
        exp.status = "paused"
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        result = service.assign_user_to_variant(exp.experiment_id, user_id=uuid4())

        assert result is None

    def test_assign_user_existing_assignment(self, service, mock_db, running_experiment):
        """할당 - 기존 할당 존재"""
        existing = MagicMock(spec=ExperimentAssignment)

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            running_experiment,
        ]
        mock_filter = MagicMock()
        mock_db.query.return_value.filter.return_value = mock_filter
        mock_filter.filter.return_value.first.return_value = existing

        # 실험 조회 후 기존 할당 조회
        mock_db.query.return_value.filter.return_value.first.return_value = running_experiment
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = existing

        result = service.assign_user_to_variant(running_experiment.experiment_id, user_id=uuid4())

        assert result == existing

    def test_assign_user_by_session_id(self, service, mock_db, running_experiment):
        """할당 - session_id로 할당"""
        mock_db.query.return_value.filter.return_value.first.return_value = running_experiment
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        result = service.assign_user_to_variant(
            running_experiment.experiment_id,
            session_id="test-session-123",
        )

        mock_db.add.assert_called_once()

    def test_get_user_assignment(self, service, mock_db):
        """사용자 할당 조회"""
        assignment = MagicMock(spec=ExperimentAssignment)
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = assignment

        result = service.get_user_assignment(uuid4(), user_id=uuid4())

        assert result == assignment

    def test_get_user_assignment_by_session(self, service, mock_db):
        """사용자 할당 조회 - session_id"""
        assignment = MagicMock(spec=ExperimentAssignment)
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = assignment

        result = service.get_user_assignment(uuid4(), session_id="session-123")

        assert result == assignment

    def test_get_ruleset_for_user_no_assignment(self, service, mock_db):
        """룰셋 조회 - 할당 없음"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_ruleset_for_user(uuid4(), user_id=uuid4())

        assert result is None


class TestMetrics:
    """메트릭 기록 및 통계 테스트"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ExperimentService(mock_db)

    def test_record_metric(self, service, mock_db):
        """메트릭 기록"""
        exp_id = uuid4()
        variant_id = uuid4()

        result = service.record_metric(
            experiment_id=exp_id,
            variant_id=variant_id,
            metric_name="conversion_rate",
            metric_value=0.15,
            context_data={"source": "checkout"},
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_get_experiment_stats_not_found(self, service, mock_db):
        """통계 조회 - 실험 없음"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_experiment_stats(uuid4())

        assert result == {}

    def test_get_experiment_stats_success(self, service, mock_db):
        """통계 조회 성공"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.status = "running"

        variant = MagicMock(spec=ExperimentVariant)
        variant.variant_id = uuid4()
        variant.name = "Control"
        variant.is_control = True
        variant.traffic_weight = 50
        exp.variants = [variant]

        mock_db.query.return_value.filter.return_value.first.return_value = exp
        mock_db.query.return_value.filter.return_value.count.return_value = 100
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []

        result = service.get_experiment_stats(exp.experiment_id)

        assert result["experiment_id"] == str(exp.experiment_id)
        assert result["status"] == "running"

    def test_calculate_significance_no_experiment(self, service, mock_db):
        """유의성 계산 - 실험 없음"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.calculate_significance(uuid4(), "conversion")

        assert "error" in result

    def test_calculate_significance_no_control(self, service, mock_db):
        """유의성 계산 - control 없음"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()

        v1 = MagicMock()
        v1.is_control = False
        exp.variants = [v1]

        mock_db.query.return_value.filter.return_value.first.return_value = exp

        result = service.calculate_significance(exp.experiment_id, "conversion")

        assert result["error"] == "control 그룹이 없습니다"

    def test_calculate_significance_success(self, service, mock_db):
        """유의성 계산 성공"""
        exp = MagicMock(spec=Experiment)
        exp.experiment_id = uuid4()
        exp.confidence_level = 0.95
        exp.min_sample_size = 100

        control = MagicMock()
        control.variant_id = uuid4()
        control.name = "Control"
        control.is_control = True

        treatment = MagicMock()
        treatment.variant_id = uuid4()
        treatment.name = "Treatment"
        treatment.is_control = False

        exp.variants = [control, treatment]

        # get_experiment 호출을 위한 mock
        mock_db.query.return_value.filter.return_value.first.return_value = exp

        # Aggregation 결과를 실제 tuple로 반환 (count, avg, stddev)
        # control_agg[0], control_agg[1], control_agg[2] 접근 가능하도록
        control_agg = (100, 0.10, 0.05)  # n, mean, std
        treatment_agg = (100, 0.15, 0.05)  # n, mean, std
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            exp,  # get_experiment
            control_agg,  # control aggregation
            treatment_agg,  # treatment aggregation
        ]

        result = service.calculate_significance(exp.experiment_id, "conversion")

        assert "metric_name" in result
        assert result["metric_name"] == "conversion"
