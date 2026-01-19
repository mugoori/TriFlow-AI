# -*- coding: utf-8 -*-
"""
Few-Shot Selector Tests
Few-shot example 선택 알고리즘 테스트
"""
import pytest
from unittest.mock import MagicMock

from app.services.few_shot_selector import FewShotSelector
from app.models.sample import Sample


class TestFewShotSelector:
    """FewShotSelector 기본 테스트"""

    @pytest.fixture
    def selector(self):
        """FewShotSelector 인스턴스"""
        db = MagicMock()
        return FewShotSelector(db)

    def test_select_by_quality(self, selector):
        """품질 점수 기반 선택"""
        samples = [
            MagicMock(spec=Sample, quality_score=0.9, category="general"),
            MagicMock(spec=Sample, quality_score=0.7, category="general"),
            MagicMock(spec=Sample, quality_score=0.8, category="general"),
            MagicMock(spec=Sample, quality_score=0.6, category="general"),
        ]

        selected = selector._select_by_quality(samples, k=2)

        # Top 2 by quality
        assert len(selected) == 2
        assert selected[0].quality_score == 0.9
        assert selected[1].quality_score == 0.8

    def test_select_balanced_by_category(self, selector):
        """카테고리 균형 선택"""
        samples = [
            MagicMock(spec=Sample, quality_score=0.9, category="threshold_adjustment"),
            MagicMock(spec=Sample, quality_score=0.8, category="field_correction"),
            MagicMock(spec=Sample, quality_score=0.7, category="threshold_adjustment"),
            MagicMock(spec=Sample, quality_score=0.6, category="general"),
        ]

        selected = selector._select_balanced(samples, k=3)

        # Should have samples from different categories
        assert len(selected) == 3
        categories = [s.category for s in selected]
        # Should alternate categories
        assert len(set(categories)) >= 2

    def test_calculate_diversity(self, selector):
        """다양성 점수 계산"""
        candidate = MagicMock(spec=Sample)
        candidate.input_data = {"field1": "value1", "field2": "value2"}

        selected = [
            MagicMock(spec=Sample, input_data={"field1": "value1"}),  # 50% overlap
            MagicMock(spec=Sample, input_data={"field3": "value3"}),  # 0% overlap
        ]

        diversity = selector._calculate_diversity(candidate, selected)

        # Should be between 0 and 1
        assert 0 <= diversity <= 1

    def test_extract_field_set(self, selector):
        """필드 집합 추출"""
        data = {
            "temperature": 25.5,
            "sensor": {"type": "PT100", "location": "A1"},
            "readings": [1, 2, 3],
        }

        fields = selector._extract_field_set(data)

        # Should extract nested fields
        assert "temperature" in fields
        assert "sensor" in fields
        assert "sensor.type" in fields
        assert "sensor.location" in fields
        assert "readings" in fields or "readings[]" in fields

    def test_select_diverse_no_duplicates(self, selector):
        """다양성 선택 시 중복 없음"""
        samples = [
            MagicMock(
                spec=Sample,
                quality_score=0.9,
                input_data={"field1": "a"},
            ),
            MagicMock(
                spec=Sample,
                quality_score=0.8,
                input_data={"field1": "a"},  # Same fields
            ),
            MagicMock(
                spec=Sample,
                quality_score=0.7,
                input_data={"field2": "b"},  # Different
            ),
        ]

        selected = selector._select_diverse(samples, k=2)

        # Should select diverse samples (not just by quality)
        assert len(selected) == 2
        # First should be highest quality
        assert selected[0].quality_score == 0.9
