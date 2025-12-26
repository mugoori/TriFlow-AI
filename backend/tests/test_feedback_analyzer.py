"""
Feedback Analyzer Service 테스트
피드백 분석 및 규칙 제안 서비스 테스트
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.feedback_analyzer import (
    FeedbackPattern,
    FeedbackAnalyzer,
    run_feedback_analysis,
)
from app.models import FeedbackLog, ProposedRule, Tenant


class TestFeedbackPattern:
    """FeedbackPattern 클래스 테스트"""

    def test_pattern_creation(self):
        """패턴 객체 생성"""
        pattern = FeedbackPattern(
            pattern_type="agent_issue",
            description="Test pattern",
            frequency=5,
            sample_feedbacks=[{"id": "1", "text": "sample"}],
            suggested_action="Fix the issue",
            confidence=0.85,
        )

        assert pattern.pattern_type == "agent_issue"
        assert pattern.description == "Test pattern"
        assert pattern.frequency == 5
        assert pattern.confidence == 0.85

    def test_pattern_to_dict(self):
        """패턴을 딕셔너리로 변환"""
        pattern = FeedbackPattern(
            pattern_type="threshold_adjustment",
            description="Threshold needs adjustment",
            frequency=3,
            sample_feedbacks=[],
            suggested_action="Adjust threshold",
            confidence=0.75,
        )

        result = pattern.to_dict()

        assert result["pattern_type"] == "threshold_adjustment"
        assert result["frequency"] == 3
        assert result["confidence"] == 0.75
        assert isinstance(result["sample_feedbacks"], list)


class TestFeedbackAnalyzer:
    """FeedbackAnalyzer 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.fixture
    def analyzer(self, mock_db):
        """FeedbackAnalyzer 인스턴스"""
        return FeedbackAnalyzer(mock_db)

    @pytest.fixture
    def sample_feedbacks(self):
        """샘플 피드백 데이터"""
        feedbacks = []
        for i in range(5):
            fb = MagicMock(spec=FeedbackLog)
            fb.feedback_id = uuid4()
            fb.feedback_type = "negative"
            fb.feedback_text = f"Test feedback {i}"
            fb.context_data = {"agent_type": "judgment", "reason": "incorrect"}
            fb.corrected_output = None
            fb.created_at = datetime.utcnow() - timedelta(days=i)
            fb.is_processed = False
            feedbacks.append(fb)
        return feedbacks

    def test_analyze_feedback_patterns_no_feedbacks(self, analyzer, mock_db):
        """패턴 분석 - 피드백 없음"""
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = analyzer.analyze_feedback_patterns(days=7)

        assert result == []

    def test_analyze_feedback_patterns_with_agent_issue(self, analyzer, mock_db, sample_feedbacks):
        """패턴 분석 - 에이전트 이슈 발견"""
        # Query chain: db.query(FeedbackLog).filter(tenant).filter(created_at).filter(type,processed).order_by().all()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = sample_feedbacks

        result = analyzer.analyze_feedback_patterns(days=7, min_frequency=2)

        # judgment 에이전트 이슈 패턴이 발견되어야 함
        agent_patterns = [p for p in result if p.pattern_type == "agent_issue"]
        assert len(agent_patterns) >= 1

    def test_analyze_by_agent(self, analyzer, sample_feedbacks):
        """에이전트별 분석"""
        result = analyzer._analyze_by_agent(sample_feedbacks, min_frequency=2)

        assert len(result) >= 1
        assert all(p.pattern_type == "agent_issue" for p in result)

    def test_analyze_by_agent_unknown_agent(self, analyzer):
        """에이전트별 분석 - unknown 에이전트"""
        # _feedback_to_summary에 필요한 모든 속성 설정
        def create_mock_fb():
            fb = MagicMock(spec=FeedbackLog)
            fb.context_data = None  # context_data 없음
            fb.feedback_id = uuid4()
            fb.feedback_type = "negative"
            fb.feedback_text = "Test feedback"
            fb.created_at = datetime.utcnow()
            return fb

        feedbacks = [create_mock_fb() for _ in range(3)]

        result = analyzer._analyze_by_agent(feedbacks, min_frequency=2)

        unknown_patterns = [p for p in result if "unknown" in p.description]
        assert len(unknown_patterns) >= 1

    def test_analyze_by_reason(self, analyzer, sample_feedbacks):
        """피드백 이유별 분석"""
        result = analyzer._analyze_by_reason(sample_feedbacks, min_frequency=2)

        # "incorrect" 이유 패턴이 발견되어야 함
        reason_patterns = [p for p in result if p.pattern_type == "reason_pattern"]
        assert len(reason_patterns) >= 1

    def test_analyze_by_reason_unspecified(self, analyzer):
        """피드백 이유별 분석 - 미지정 이유"""
        fb = MagicMock(spec=FeedbackLog)
        fb.context_data = {}  # reason 없음
        feedbacks = [fb, fb, fb]

        result = analyzer._analyze_by_reason(feedbacks, min_frequency=2)

        # unspecified는 패턴으로 안 나옴
        assert len(result) == 0

    def test_analyze_corrections_no_corrections(self, analyzer, sample_feedbacks):
        """수정 제안 분석 - 수정 없음"""
        for fb in sample_feedbacks:
            fb.feedback_type = "negative"
            fb.corrected_output = None

        result = analyzer._analyze_corrections(sample_feedbacks)

        assert len(result) == 0

    def test_analyze_corrections_with_threshold(self, analyzer):
        """수정 제안 분석 - 임계값 관련 수정"""
        fb1 = MagicMock(spec=FeedbackLog)
        fb1.feedback_type = "correction"
        fb1.corrected_output = {"text": "온도 임계값을 85°C로 조정해야 합니다"}
        fb1.feedback_id = uuid4()
        fb1.feedback_text = "test"
        fb1.created_at = datetime.utcnow()

        fb2 = MagicMock(spec=FeedbackLog)
        fb2.feedback_type = "correction"
        fb2.corrected_output = {"text": "압력은 10 bar 이하로"}
        fb2.feedback_id = uuid4()
        fb2.feedback_text = "test"
        fb2.created_at = datetime.utcnow()

        feedbacks = [fb1, fb2]

        result = analyzer._analyze_corrections(feedbacks)

        threshold_patterns = [p for p in result if p.pattern_type == "threshold_adjustment"]
        assert len(threshold_patterns) == 1

    def test_analyze_corrections_string_output(self, analyzer):
        """수정 제안 분석 - 문자열 출력"""
        fb = MagicMock(spec=FeedbackLog)
        fb.feedback_type = "correction"
        fb.corrected_output = "습도가 90%를 넘으면 경고"
        fb.feedback_id = uuid4()
        fb.feedback_text = "test"
        fb.created_at = datetime.utcnow()

        result = analyzer._analyze_corrections([fb])

        assert len(result) == 1

    def test_feedback_to_summary(self, analyzer):
        """피드백 요약 변환"""
        fb = MagicMock(spec=FeedbackLog)
        fb.feedback_id = uuid4()
        fb.feedback_type = "negative"
        fb.feedback_text = "This is a long feedback text that should be truncated" * 5
        fb.created_at = datetime.utcnow()

        result = analyzer._feedback_to_summary(fb)

        assert "feedback_id" in result
        assert "type" in result
        assert len(result["text"]) <= 100

    def test_feedback_to_summary_no_text(self, analyzer):
        """피드백 요약 변환 - 텍스트 없음"""
        fb = MagicMock(spec=FeedbackLog)
        fb.feedback_id = uuid4()
        fb.feedback_type = "negative"
        fb.feedback_text = None
        fb.created_at = None

        result = analyzer._feedback_to_summary(fb)

        assert result["text"] is None
        assert result["created_at"] is None

    def test_suggest_action_for_reason(self, analyzer):
        """이유별 액션 제안"""
        assert "정확도" in analyzer._suggest_action_for_reason("incorrect")
        assert "상세한" in analyzer._suggest_action_for_reason("incomplete")
        assert "라우팅" in analyzer._suggest_action_for_reason("irrelevant")
        assert "명확" in analyzer._suggest_action_for_reason("unclear")
        assert "최적화" in analyzer._suggest_action_for_reason("slow")
        assert "검토" in analyzer._suggest_action_for_reason("unknown_reason")


class TestRuleProposals:
    """규칙 제안 생성 테스트"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def analyzer(self, mock_db):
        return FeedbackAnalyzer(mock_db)

    @pytest.fixture
    def threshold_pattern(self):
        return FeedbackPattern(
            pattern_type="threshold_adjustment",
            description="Temperature threshold adjustment",
            frequency=5,
            sample_feedbacks=[{"text": "temperature 임계값 조정"}],
            suggested_action="Adjust threshold",
            confidence=0.8,
        )

    @pytest.fixture
    def agent_pattern(self):
        return FeedbackPattern(
            pattern_type="agent_issue",
            description="Judgment agent issue",
            frequency=3,
            sample_feedbacks=[{"text": "에이전트 응답 품질 문제"}],
            suggested_action="Improve agent",
            confidence=0.7,
        )

    def test_generate_rule_proposals_threshold(self, analyzer, threshold_pattern):
        """임계값 패턴에서 규칙 제안 생성"""
        tenant_id = uuid4()

        result = analyzer.generate_rule_proposals([threshold_pattern], tenant_id)

        assert len(result) == 1
        assert "threshold" in result[0].rule_name

    def test_generate_rule_proposals_agent(self, analyzer, agent_pattern):
        """에이전트 패턴에서 규칙 제안 생성"""
        tenant_id = uuid4()

        result = analyzer.generate_rule_proposals([agent_pattern], tenant_id)

        assert len(result) == 1
        assert "quality" in result[0].rule_name

    def test_generate_rule_proposals_multiple(self, analyzer, threshold_pattern, agent_pattern):
        """여러 패턴에서 규칙 제안 생성"""
        tenant_id = uuid4()

        result = analyzer.generate_rule_proposals([threshold_pattern, agent_pattern], tenant_id)

        assert len(result) == 2

    def test_generate_rule_proposals_other_pattern(self, analyzer):
        """기타 패턴 - 제안 없음"""
        tenant_id = uuid4()
        other_pattern = FeedbackPattern(
            pattern_type="other_type",
            description="Other pattern",
            frequency=5,
            sample_feedbacks=[],
            suggested_action="Unknown",
            confidence=0.5,
        )

        result = analyzer.generate_rule_proposals([other_pattern], tenant_id)

        assert len(result) == 0

    def test_create_threshold_proposal(self, analyzer, threshold_pattern):
        """임계값 규칙 제안 생성"""
        tenant_id = uuid4()

        result = analyzer._create_threshold_proposal(threshold_pattern, tenant_id)

        assert result is not None
        assert result.tenant_id == tenant_id
        assert "rhai_script" in dir(result)
        assert result.source_type == "feedback_analysis"

    def test_create_threshold_proposal_with_sensor_type(self, analyzer):
        """임계값 규칙 제안 - 센서 타입 추출"""
        pattern = FeedbackPattern(
            pattern_type="threshold_adjustment",
            description="Pressure threshold",
            frequency=3,
            sample_feedbacks=[{"text": "pressure 값이 너무 높음"}],
            suggested_action="Adjust",
            confidence=0.75,
        )
        tenant_id = uuid4()

        result = analyzer._create_threshold_proposal(pattern, tenant_id)

        assert "pressure" in result.rhai_script

    def test_create_agent_improvement_proposal(self, analyzer, agent_pattern):
        """에이전트 개선 규칙 제안 생성"""
        tenant_id = uuid4()

        result = analyzer._create_agent_improvement_proposal(agent_pattern, tenant_id)

        assert result is not None
        assert result.tenant_id == tenant_id
        assert result.confidence == agent_pattern.confidence * 0.8


class TestSaveProposals:
    """규칙 제안 저장 테스트"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def analyzer(self, mock_db):
        return FeedbackAnalyzer(mock_db)

    def test_save_proposals_new(self, analyzer, mock_db):
        """새 제안 저장"""
        proposal = MagicMock(spec=ProposedRule)
        proposal.proposal_id = uuid4()
        proposal.rule_name = "new_rule"

        # 중복 체크 query chain: db.query(ProposedRule).filter(rule_name).filter(status).first()
        # 빈 결과 반환하여 중복이 아님을 표시
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = analyzer.save_proposals([proposal])

        assert len(result) == 1
        mock_db.add.assert_called_once_with(proposal)
        mock_db.commit.assert_called_once()

    def test_save_proposals_duplicate(self, analyzer, mock_db):
        """중복 제안 스킵"""
        proposal = MagicMock(spec=ProposedRule)
        proposal.rule_name = "existing_rule"

        existing = MagicMock(spec=ProposedRule)
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = existing

        result = analyzer.save_proposals([proposal])

        assert len(result) == 0
        mock_db.add.assert_not_called()

    def test_save_proposals_empty(self, analyzer, mock_db):
        """빈 제안 목록"""
        result = analyzer.save_proposals([])

        assert result == []
        mock_db.commit.assert_not_called()


class TestApproveRejectProposal:
    """제안 승인/거절 테스트"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def analyzer(self, mock_db):
        return FeedbackAnalyzer(mock_db)

    @pytest.fixture
    def pending_proposal(self):
        proposal = MagicMock(spec=ProposedRule)
        proposal.proposal_id = uuid4()
        proposal.tenant_id = uuid4()
        proposal.rule_name = "test_rule"
        proposal.rule_description = "Test description"
        proposal.rhai_script = "// test script"
        proposal.status = "pending"
        return proposal

    def test_approve_proposal_success(self, analyzer, mock_db, pending_proposal):
        """제안 승인 성공"""
        mock_db.query.return_value.filter.return_value.first.return_value = pending_proposal
        user_id = uuid4()

        result = analyzer.approve_proposal(
            pending_proposal.proposal_id,
            user_id=user_id,
            comment="Approved!",
        )

        assert result is not None
        mock_db.add.assert_called()  # Ruleset 추가
        mock_db.commit.assert_called()
        assert pending_proposal.status == "deployed"
        assert pending_proposal.reviewed_by == user_id

    def test_approve_proposal_not_found(self, analyzer, mock_db):
        """제안 승인 - 제안 없음"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = analyzer.approve_proposal(uuid4())

        assert result is None

    def test_approve_proposal_not_pending(self, analyzer, mock_db, pending_proposal):
        """제안 승인 - pending이 아닌 상태"""
        pending_proposal.status = "rejected"
        mock_db.query.return_value.filter.return_value.first.return_value = pending_proposal

        result = analyzer.approve_proposal(pending_proposal.proposal_id)

        assert result is None

    def test_reject_proposal_success(self, analyzer, mock_db, pending_proposal):
        """제안 거절 성공"""
        mock_db.query.return_value.filter.return_value.first.return_value = pending_proposal
        user_id = uuid4()

        result = analyzer.reject_proposal(
            pending_proposal.proposal_id,
            user_id=user_id,
            comment="Not suitable",
        )

        assert result is True
        assert pending_proposal.status == "rejected"
        assert pending_proposal.reviewed_by == user_id
        mock_db.commit.assert_called()

    def test_reject_proposal_not_found(self, analyzer, mock_db):
        """제안 거절 - 제안 없음"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = analyzer.reject_proposal(uuid4())

        assert result is False


class TestRunFeedbackAnalysis:
    """피드백 분석 실행 함수 테스트"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def test_run_analysis_no_patterns(self, mock_db):
        """분석 실행 - 패턴 없음"""
        with patch.object(FeedbackAnalyzer, 'analyze_feedback_patterns', return_value=[]):
            result = run_feedback_analysis(mock_db)

        assert result["status"] == "no_patterns"
        assert result["patterns_found"] == 0

    def test_run_analysis_no_tenant(self, mock_db):
        """분석 실행 - 테넌트 없음"""
        pattern = FeedbackPattern(
            pattern_type="agent_issue",
            description="Test",
            frequency=3,
            sample_feedbacks=[],
            suggested_action="Fix",
            confidence=0.8,
        )

        with patch.object(FeedbackAnalyzer, 'analyze_feedback_patterns', return_value=[pattern]):
            mock_db.query.return_value.first.return_value = None
            result = run_feedback_analysis(mock_db)

        assert result["status"] == "error"
        assert "테넌트" in result["message"]

    def test_run_analysis_success(self, mock_db):
        """분석 실행 성공"""
        pattern = FeedbackPattern(
            pattern_type="agent_issue",
            description="Test",
            frequency=3,
            sample_feedbacks=[],
            suggested_action="Fix",
            confidence=0.8,
        )

        tenant = MagicMock(spec=Tenant)
        tenant.tenant_id = uuid4()

        proposal = MagicMock(spec=ProposedRule)
        proposal.proposal_id = uuid4()

        with patch.object(FeedbackAnalyzer, 'analyze_feedback_patterns', return_value=[pattern]):
            with patch.object(FeedbackAnalyzer, 'generate_rule_proposals', return_value=[proposal]):
                with patch.object(FeedbackAnalyzer, 'save_proposals', return_value=[proposal]):
                    mock_db.query.return_value.first.return_value = tenant
                    result = run_feedback_analysis(mock_db)

        assert result["status"] == "success"
        assert result["patterns_found"] == 1
        assert result["proposals_created"] == 1


class TestFeedbackReasons:
    """피드백 이유 상수 테스트"""

    def test_feedback_reasons_defined(self):
        """모든 피드백 이유가 정의되어 있는지"""
        expected_reasons = ["incorrect", "incomplete", "irrelevant", "unclear", "slow", "other"]

        for reason in expected_reasons:
            assert reason in FeedbackAnalyzer.FEEDBACK_REASONS


class TestSensorThresholds:
    """센서 임계값 상수 테스트"""

    def test_sensor_thresholds_defined(self):
        """모든 센서 타입 임계값이 정의되어 있는지"""
        expected_sensors = ["temperature", "pressure", "humidity", "vibration", "flow_rate", "defect_rate"]

        for sensor in expected_sensors:
            assert sensor in FeedbackAnalyzer.SENSOR_THRESHOLDS
            threshold = FeedbackAnalyzer.SENSOR_THRESHOLDS[sensor]
            assert "warning" in threshold
            assert "critical" in threshold
            assert "unit" in threshold

    def test_sensor_thresholds_values(self):
        """임계값 순서 확인 (warning < critical)"""
        for sensor, threshold in FeedbackAnalyzer.SENSOR_THRESHOLDS.items():
            assert threshold["warning"] < threshold["critical"], f"{sensor} threshold order is wrong"
