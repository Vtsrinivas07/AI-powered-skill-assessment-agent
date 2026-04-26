"""
Skill gap analyzer for the Skill Assessment Agent.

Compares assessed proficiency levels against job requirements,
categorises gaps, calculates an overall match score, and ranks
gaps by learning priority.

Validates Requirements: 3.1, 3.2, 3.3, 3.5, 3.6
"""

import logging
from typing import Dict, List, Optional

from src.models import (
    GapAnalysis,
    GapCategory,
    ProficiencyLevel,
    RequiredSkill,
    SkillAssessment,
    SkillGap,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gap categorisation thresholds
# ---------------------------------------------------------------------------
# A gap is the numeric difference: required.value - assessed.value
# Positive → candidate is below requirement; negative → candidate exceeds it.
_CRITICAL_THRESHOLD = 2   # Gap ≥ 2 levels on a required skill
_MODERATE_THRESHOLD = 1   # Gap == 1 level on a required skill


class GapAnalyzer:
    """
    Analyses skill gaps between job requirements and assessed proficiency.

    All methods are pure functions of their inputs — no LLM calls needed.
    This makes the logic fully testable with property-based tests.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_gaps(
        self,
        required_skills: List[RequiredSkill],
        assessments: List[SkillAssessment],
    ) -> GapAnalysis:
        """
        Produce a complete gap analysis.

        Args:
            required_skills: Skills required by the job description.
            assessments: Completed skill assessments.

        Returns:
            GapAnalysis with categorised gaps, strengths, and match score.
        """
        # Build a lookup: skill name → assessed level
        assessed_map: Dict[str, ProficiencyLevel] = {
            a.skill.name: a.proficiency.level for a in assessments
        }

        gaps: List[SkillGap] = []
        strengths: List[str] = []

        for skill in required_skills:
            assessed_level = assessed_map.get(skill.name, ProficiencyLevel.NONE)
            gap = self.calculate_gap(skill, assessed_level)

            if gap.category == GapCategory.STRENGTH:
                strengths.append(skill.name)
            else:
                gaps.append(gap)

        # Rank gaps by priority
        ranked_gaps = self.rank_gaps_by_priority(gaps)

        # Assign priority ranks
        for rank, gap in enumerate(ranked_gaps, start=1):
            gap.priority_rank = rank

        # Categorise
        critical = [g for g in ranked_gaps if g.category == GapCategory.CRITICAL]
        moderate = [g for g in ranked_gaps if g.category == GapCategory.MODERATE]
        minor = [g for g in ranked_gaps if g.category == GapCategory.MINOR]

        match_score = self.calculate_match_score(required_skills, assessed_map)

        logger.info(
            "Gap analysis: %d critical, %d moderate, %d minor gaps; "
            "%d strengths; match_score=%.1f",
            len(critical), len(moderate), len(minor), len(strengths), match_score,
        )

        return GapAnalysis(
            gaps=ranked_gaps,
            strengths=strengths,
            match_score=match_score,
            critical_gaps=critical,
            moderate_gaps=moderate,
            minor_gaps=minor,
        )

    def calculate_gap(
        self,
        skill: RequiredSkill,
        assessed_level: ProficiencyLevel,
    ) -> SkillGap:
        """
        Calculate the gap for a single skill.

        Args:
            skill: The required skill with its required_level.
            assessed_level: The assessed proficiency level.

        Returns:
            SkillGap with magnitude, category, and adjacency flag.
        """
        magnitude = skill.required_level.value - assessed_level.value
        # Magnitude is always stored as non-negative
        abs_magnitude = abs(magnitude)

        if magnitude < 0:
            # Candidate exceeds requirement
            category = GapCategory.STRENGTH
        else:
            category = self.categorize_gap(skill, assessed_level)

        is_adjacent = self._is_adjacent(assessed_level, skill.required_level)

        return SkillGap(
            skill=skill.name,
            required_level=skill.required_level,
            assessed_level=assessed_level,
            gap_magnitude=abs_magnitude,
            category=category,
            priority_rank=0,  # Set later by rank_gaps_by_priority
            is_adjacent=is_adjacent,
        )

    def categorize_gap(
        self,
        skill: RequiredSkill,
        assessed_level: ProficiencyLevel,
    ) -> GapCategory:
        """
        Categorise a skill gap as critical, moderate, or minor.

        Args:
            skill: The required skill (includes priority and required_level).
            assessed_level: The assessed proficiency level.

        Returns:
            GapCategory enum value.
        """
        magnitude = skill.required_level.value - assessed_level.value

        if magnitude <= 0:
            return GapCategory.STRENGTH

        is_required = skill.priority.lower() == "required"

        if is_required and magnitude >= _CRITICAL_THRESHOLD:
            return GapCategory.CRITICAL
        if magnitude >= _MODERATE_THRESHOLD:
            return GapCategory.MODERATE
        return GapCategory.MINOR

    def calculate_match_score(
        self,
        required_skills: List[RequiredSkill],
        assessed_map: Dict[str, ProficiencyLevel],
    ) -> float:
        """
        Calculate an overall match score (0–100).

        Required skills are weighted 2× compared to preferred skills.
        A skill where the candidate meets or exceeds the requirement
        contributes its full weight; partial credit is given for partial
        proficiency.

        Args:
            required_skills: All skills from the job description.
            assessed_map: Mapping of skill name → assessed ProficiencyLevel.

        Returns:
            Float in [0.0, 100.0].
        """
        if not required_skills:
            return 0.0

        total_weight = 0.0
        earned_weight = 0.0

        for skill in required_skills:
            weight = 2.0 if skill.priority.lower() == "required" else 1.0
            total_weight += weight

            assessed = assessed_map.get(skill.name, ProficiencyLevel.NONE)
            required_val = skill.required_level.value
            assessed_val = assessed.value

            if required_val == 0:
                # No proficiency required — full credit
                ratio = 1.0
            else:
                ratio = min(assessed_val / required_val, 1.0)

            earned_weight += weight * ratio

        score = (earned_weight / total_weight) * 100.0
        return round(score, 2)

    def rank_gaps_by_priority(self, gaps: List[SkillGap]) -> List[SkillGap]:
        """
        Rank gaps by learning priority (highest priority first).

        Ranking criteria (descending importance):
        1. Critical gaps on required skills first.
        2. Moderate gaps next.
        3. Minor gaps last.
        4. Within the same category, adjacent skills rank higher
           (easier to learn → faster ROI).
        5. Larger gap magnitude ranks higher within the same category.

        Args:
            gaps: Unranked list of SkillGap objects.

        Returns:
            New list sorted by priority (highest first).
        """
        category_order = {
            GapCategory.CRITICAL: 0,
            GapCategory.MODERATE: 1,
            GapCategory.MINOR: 2,
            GapCategory.STRENGTH: 3,
        }

        def sort_key(gap: SkillGap):
            cat_rank = category_order.get(gap.category, 99)
            # Adjacent skills are easier → prioritise them (lower sort value)
            adjacency_rank = 0 if gap.is_adjacent else 1
            # Larger magnitude = bigger gap = higher priority
            magnitude_rank = -gap.gap_magnitude
            return (cat_rank, adjacency_rank, magnitude_rank)

        return sorted(gaps, key=sort_key)

    def _identify_strengths(
        self,
        required_skills: List[RequiredSkill],
        assessed_map: Dict[str, ProficiencyLevel],
    ) -> List[str]:
        """
        Identify skills where the candidate exceeds requirements.

        Args:
            required_skills: Skills required by the job.
            assessed_map: Mapping of skill name → assessed level.

        Returns:
            List of skill names where candidate exceeds requirement.
        """
        strengths = []
        for skill in required_skills:
            assessed = assessed_map.get(skill.name, ProficiencyLevel.NONE)
            if assessed.value > skill.required_level.value:
                strengths.append(skill.name)
        return strengths

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_adjacent(
        current_level: ProficiencyLevel,
        target_level: ProficiencyLevel,
    ) -> bool:
        """
        Determine if a skill is adjacent (gap ≤ 1 level).

        A skill is considered adjacent — and therefore realistically
        acquirable — when the gap is at most one proficiency level.

        Args:
            current_level: Candidate's current proficiency.
            target_level: Required proficiency level.

        Returns:
            True if the skill is adjacent.
        """
        gap = target_level.value - current_level.value
        return 0 < gap <= 1
