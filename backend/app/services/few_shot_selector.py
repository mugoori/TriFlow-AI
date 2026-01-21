# -*- coding: utf-8 -*-
"""
Few-Shot Example Selector
Golden Sample Set에서 최적의 few-shot examples 선택
"""
import logging
import json
from typing import List, Dict, Any, Set, Optional
from uuid import UUID
import random

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.sample import Sample, GoldenSampleSet, GoldenSampleSetMember

logger = logging.getLogger(__name__)


class FewShotSelector:
    """Few-shot example 선택 알고리즘"""

    def __init__(self, db: Session):
        self.db = db

    def select_examples(
        self,
        golden_set_id: UUID,
        k: int = 5,
        strategy: str = "hybrid",
        diversity_weight: float = 0.3,
        quality_weight: float = 0.7,
        category: Optional[str] = None,
    ) -> List[Sample]:
        """
        Golden Sample Set에서 k개의 최적 examples 선택

        Args:
            golden_set_id: Golden Sample Set ID
            k: 선택할 샘플 수
            strategy: 선택 전략 (quality_rank, balanced, diverse, hybrid)
            diversity_weight: Diversity 가중치 (hybrid 전략용)
            quality_weight: Quality 가중치 (hybrid 전략용)
            category: 특정 카테고리만 선택 (선택)

        Returns:
            선택된 Sample 리스트 (최대 k개)
        """
        # Get golden set
        golden_set = self.db.query(GoldenSampleSet).get(golden_set_id)
        if not golden_set:
            raise ValueError(f"Golden set {golden_set_id} not found")

        # Get member samples
        query = (
            self.db.query(Sample)
            .join(GoldenSampleSetMember)
            .filter(GoldenSampleSetMember.set_id == golden_set_id)
            .filter(Sample.status == "approved")
        )

        if category:
            query = query.filter(Sample.category == category)

        samples = query.all()

        if not samples:
            logger.warning(f"No samples found in golden set {golden_set_id}")
            return []

        # Apply selection strategy
        if strategy == "quality_rank":
            return self._select_by_quality(samples, k)
        elif strategy == "balanced":
            return self._select_balanced(samples, k)
        elif strategy == "diverse":
            return self._select_diverse(samples, k)
        elif strategy == "hybrid":
            return self._select_hybrid(samples, k, diversity_weight, quality_weight)
        else:
            logger.warning(f"Unknown strategy '{strategy}', using quality_rank")
            return self._select_by_quality(samples, k)

    def _select_by_quality(self, samples: List[Sample], k: int) -> List[Sample]:
        """품질 점수 기반 선택 (상위 k개)"""
        sorted_samples = sorted(
            samples, key=lambda s: s.quality_score or 0, reverse=True
        )
        return sorted_samples[:k]

    def _select_balanced(self, samples: List[Sample], k: int) -> List[Sample]:
        """카테고리 균형 선택"""
        # Group by category
        by_category: Dict[str, List[Sample]] = {}
        for sample in samples:
            cat = sample.category or "general"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(sample)

        # Sort each category by quality
        for cat in by_category:
            by_category[cat].sort(key=lambda s: s.quality_score or 0, reverse=True)

        # Round-robin selection
        selected = []
        categories = list(by_category.keys())
        idx = 0

        while len(selected) < k and any(by_category.values()):
            cat = categories[idx % len(categories)]
            if by_category[cat]:
                selected.append(by_category[cat].pop(0))
            idx += 1

            # Remove empty categories
            if not by_category[cat]:
                categories.remove(cat)
                if not categories:
                    break

        return selected[:k]

    def _select_diverse(self, samples: List[Sample], k: int) -> List[Sample]:
        """다양성 기반 선택 (MMR-like 알고리즘)"""
        if not samples:
            return []

        selected = []
        candidates = samples.copy()

        # Start with highest quality sample
        candidates.sort(key=lambda s: s.quality_score or 0, reverse=True)
        selected.append(candidates.pop(0))

        # Iteratively select most diverse from remaining
        while len(selected) < k and candidates:
            best_candidate = None
            best_diversity = -1

            for candidate in candidates:
                diversity = self._calculate_diversity(candidate, selected)
                if diversity > best_diversity:
                    best_diversity = diversity
                    best_candidate = candidate

            if best_candidate:
                selected.append(best_candidate)
                candidates.remove(best_candidate)

        return selected

    def _select_hybrid(
        self,
        samples: List[Sample],
        k: int,
        diversity_weight: float,
        quality_weight: float,
    ) -> List[Sample]:
        """품질 + 다양성 하이브리드 선택"""
        if not samples:
            return []

        # Normalize weights
        total_weight = diversity_weight + quality_weight
        diversity_weight = diversity_weight / total_weight
        quality_weight = quality_weight / total_weight

        selected = []
        candidates = samples.copy()

        # Start with highest quality
        candidates.sort(key=lambda s: s.quality_score or 0, reverse=True)
        selected.append(candidates.pop(0))

        # Iteratively select best hybrid score
        while len(selected) < k and candidates:
            best_candidate = None
            best_score = -1

            for candidate in candidates:
                quality = candidate.quality_score or 0
                diversity = self._calculate_diversity(candidate, selected)

                # Hybrid score
                score = quality_weight * quality + diversity_weight * diversity

                if score > best_score:
                    best_score = score
                    best_candidate = candidate

            if best_candidate:
                selected.append(best_candidate)
                candidates.remove(best_candidate)

        return selected

    def _calculate_diversity(
        self, candidate: Sample, selected: List[Sample]
    ) -> float:
        """
        다양성 점수 계산 (0-1)

        현재 구현: JSONB 필드 overlap 기반
        향후: embedding 거리 기반으로 업그레이드 가능
        """
        if not selected:
            return 1.0

        candidate_fields = self._extract_field_set(candidate.input_data)

        # Calculate average dissimilarity with selected samples
        dissimilarities = []

        for selected_sample in selected:
            selected_fields = self._extract_field_set(selected_sample.input_data)

            # Jaccard distance = 1 - Jaccard similarity
            intersection = len(candidate_fields & selected_fields)
            union = len(candidate_fields | selected_fields)

            if union == 0:
                dissimilarity = 0.5  # Default
            else:
                jaccard_similarity = intersection / union
                dissimilarity = 1 - jaccard_similarity

            dissimilarities.append(dissimilarity)

        # Average dissimilarity
        return sum(dissimilarities) / len(dissimilarities)

    def _extract_field_set(self, data: Dict[str, Any]) -> Set[str]:
        """JSONB 데이터에서 필드 집합 추출 (다양성 계산용)"""
        if not data:
            return set()

        fields = set()

        def extract_keys(obj, prefix=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    field_name = f"{prefix}.{key}" if prefix else key
                    fields.add(field_name)
                    extract_keys(value, field_name)
            elif isinstance(obj, list) and obj:
                # Sample first item type
                fields.add(f"{prefix}[]")
                if isinstance(obj[0], (dict, list)):
                    extract_keys(obj[0], f"{prefix}[]")

        extract_keys(data)
        return fields
