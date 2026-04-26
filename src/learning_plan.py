"""
Learning plan generator for the Skill Assessment Agent.

Creates personalised, sequenced learning plans focused on adjacent skills
the candidate can realistically acquire, with milestone checkpoints.

Validates Requirements: 4.1, 4.2, 4.5, 4.6, 4.7, 4.8
"""

import logging
import math
from typing import Dict, List, Optional

from src.models import (
    GapAnalysis,
    GapCategory,
    LearningPlan,
    LearningResource,
    LearningStep,
    ProficiencyLevel,
    SkillAssessment,
    SkillGap,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estimated hours to advance one proficiency level
# ---------------------------------------------------------------------------
_HOURS_PER_LEVEL: Dict[ProficiencyLevel, int] = {
    ProficiencyLevel.NONE: 20,        # NONE → BEGINNER
    ProficiencyLevel.BEGINNER: 40,    # BEGINNER → INTERMEDIATE
    ProficiencyLevel.INTERMEDIATE: 80,  # INTERMEDIATE → ADVANCED
    ProficiencyLevel.ADVANCED: 160,   # ADVANCED → EXPERT
    ProficiencyLevel.EXPERT: 0,       # Already at top
}

# Large-gap threshold: gaps ≥ this many levels need prerequisites first
_LARGE_GAP_THRESHOLD = 2


class LearningPlanGenerator:
    """
    Generates personalised learning plans from gap analysis results.

    The generator:
    - Prioritises adjacent skills (gap ≤ 1 level) over distant ones.
    - Sequences skills from foundational to advanced.
    - Inserts prerequisite steps for large gaps.
    - Calculates realistic time estimates.
    - Creates milestone checkpoints.
    """

    def __init__(self, resource_curator: Optional[object] = None) -> None:
        """
        Initialise the LearningPlanGenerator.

        Args:
            resource_curator: Optional ResourceCurator instance. If provided,
                              it will be used to fetch real resources; otherwise
                              placeholder resources are used.
        """
        self.resource_curator = resource_curator

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_plan(
        self,
        gap_analysis: GapAnalysis,
        assessments: List[SkillAssessment],
    ) -> LearningPlan:
        """
        Generate a complete personalised learning plan.

        Args:
            gap_analysis: Completed gap analysis.
            assessments: Completed skill assessments (for current levels).

        Returns:
            LearningPlan with sequenced steps, resources, and milestones.
        """
        # Build current-level lookup
        current_levels: Dict[str, ProficiencyLevel] = {
            a.skill.name: a.proficiency.level for a in assessments
        }

        # Collect all actionable gaps (exclude strengths)
        actionable_gaps = [
            g for g in gap_analysis.gaps
            if g.category != GapCategory.STRENGTH and g.gap_magnitude > 0
        ]

        if not actionable_gaps:
            logger.info("No actionable gaps found — returning empty learning plan.")
            return LearningPlan(
                steps=[],
                total_hours=0,
                focus_areas=[],
                prerequisites_needed=[],
                milestones=["No skill gaps identified — candidate meets all requirements!"],
                timeline_weeks=0,
            )

        # Separate adjacent from distant gaps
        adjacent_gaps = [g for g in actionable_gaps if g.is_adjacent]
        distant_gaps = [g for g in actionable_gaps if not g.is_adjacent]

        # Build steps: adjacent first, then distant (with prerequisites)
        steps: List[LearningStep] = []
        prerequisites_needed: List[str] = []

        for gap in adjacent_gaps:
            current = current_levels.get(gap.skill, gap.assessed_level)
            step = self._build_step(gap, current)
            steps.append(step)

        for gap in distant_gaps:
            current = current_levels.get(gap.skill, gap.assessed_level)
            prereqs = self._identify_prerequisites(gap, current)
            prerequisites_needed.extend(prereqs)

            # Insert prerequisite steps before the main step
            for prereq_skill in prereqs:
                prereq_step = self._build_prerequisite_step(prereq_skill, current)
                # Avoid duplicates
                if not any(s.skill == prereq_skill for s in steps):
                    steps.append(prereq_step)

            step = self._build_step(gap, current)
            steps.append(step)

        # Sequence the steps
        steps = self.sequence_learning_path(steps)

        # Calculate totals
        total_hours = self.calculate_timeline(steps)
        timeline_weeks = math.ceil(total_hours / 10)  # Assume ~10 hrs/week

        focus_areas = [s.skill for s in steps if s.current_level != s.target_level]
        milestones = self._create_milestones(steps)

        logger.info(
            "Generated learning plan: %d steps, %d hours (~%d weeks)",
            len(steps), total_hours, timeline_weeks,
        )

        return LearningPlan(
            steps=steps,
            total_hours=total_hours,
            focus_areas=focus_areas,
            prerequisites_needed=list(dict.fromkeys(prerequisites_needed)),
            milestones=milestones,
            timeline_weeks=timeline_weeks,
        )

    def is_adjacent_skill(
        self,
        target_skill: str,
        current_proficiencies: Dict[str, ProficiencyLevel],
        required_level: ProficiencyLevel,
    ) -> bool:
        """
        Determine if a skill is adjacent based on current proficiency.

        A skill is adjacent when the gap between the candidate's current
        level and the required level is exactly 1.

        Args:
            target_skill: Name of the skill to check.
            current_proficiencies: Mapping of skill name → current level.
            required_level: The required proficiency level.

        Returns:
            True if the skill is adjacent.
        """
        current = current_proficiencies.get(target_skill, ProficiencyLevel.NONE)
        gap = required_level.value - current.value
        return gap == 1

    def sequence_learning_path(self, steps: List[LearningStep]) -> List[LearningStep]:
        """
        Sequence learning steps so prerequisites come before dependents.

        Uses a simple topological sort: steps with no prerequisites first,
        then steps whose prerequisites are already scheduled.

        Args:
            steps: Unordered list of LearningStep objects.

        Returns:
            Ordered list with prerequisites before dependents.
        """
        scheduled_skills: List[str] = []
        ordered: List[LearningStep] = []
        remaining = list(steps)

        max_iterations = len(steps) * 2  # Guard against infinite loops
        iteration = 0

        while remaining and iteration < max_iterations:
            iteration += 1
            progress = False
            for step in list(remaining):
                # A step is ready if all its prerequisites are already scheduled
                if all(p in scheduled_skills for p in step.prerequisites):
                    ordered.append(step)
                    scheduled_skills.append(step.skill)
                    remaining.remove(step)
                    progress = True

            if not progress:
                # Circular dependency or unresolvable — append remaining as-is
                logger.warning(
                    "Could not fully resolve prerequisite order; appending %d remaining steps.",
                    len(remaining),
                )
                ordered.extend(remaining)
                break

        return ordered

    def calculate_timeline(self, steps: List[LearningStep]) -> int:
        """
        Calculate total estimated hours for the learning plan.

        Args:
            steps: List of LearningStep objects.

        Returns:
            Sum of estimated_hours across all steps.
        """
        return sum(s.estimated_hours for s in steps)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_step(self, gap: SkillGap, current_level: ProficiencyLevel) -> LearningStep:
        """Build a LearningStep for a given gap."""
        hours = self._estimate_hours(current_level, gap.required_level)
        resources = self._get_resources(gap.skill, current_level, gap.required_level)
        milestone = self._milestone_for_step(gap.skill, gap.required_level)

        return LearningStep(
            skill=gap.skill,
            current_level=current_level,
            target_level=gap.required_level,
            resources=resources,
            estimated_hours=hours,
            prerequisites=[],
            milestone_criteria=milestone,
        )

    def _build_prerequisite_step(
        self, skill_name: str, current_level: ProficiencyLevel
    ) -> LearningStep:
        """Build a foundational prerequisite step."""
        target = ProficiencyLevel.BEGINNER
        hours = _HOURS_PER_LEVEL.get(ProficiencyLevel.NONE, 20)
        resources = self._get_resources(skill_name, ProficiencyLevel.NONE, target)

        return LearningStep(
            skill=skill_name,
            current_level=ProficiencyLevel.NONE,
            target_level=target,
            resources=resources,
            estimated_hours=hours,
            prerequisites=[],
            milestone_criteria=f"Complete a beginner tutorial for {skill_name}.",
        )

    def _identify_prerequisites(
        self, gap: SkillGap, current_level: ProficiencyLevel
    ) -> List[str]:
        """
        Identify prerequisite skills needed before tackling a large gap.

        For gaps ≥ _LARGE_GAP_THRESHOLD levels, we recommend building
        foundational knowledge first.

        Args:
            gap: The skill gap to analyse.
            current_level: Candidate's current level for this skill.

        Returns:
            List of prerequisite skill names (may be empty).
        """
        if gap.gap_magnitude < _LARGE_GAP_THRESHOLD:
            return []

        # For a large gap, the skill itself is its own prerequisite at a lower level
        # (i.e., the candidate needs to reach BEGINNER before targeting INTERMEDIATE+)
        if current_level == ProficiencyLevel.NONE:
            return [gap.skill]  # Need foundational step first

        return []

    def _estimate_hours(
        self, current_level: ProficiencyLevel, target_level: ProficiencyLevel
    ) -> int:
        """
        Estimate hours needed to advance from current to target level.

        Args:
            current_level: Starting proficiency.
            target_level: Target proficiency.

        Returns:
            Estimated hours (positive integer).
        """
        total = 0
        level_val = current_level.value
        while level_val < target_level.value:
            level = ProficiencyLevel(level_val)
            total += _HOURS_PER_LEVEL.get(level, 40)
            level_val += 1
        return max(total, 1)

    def _get_resources(
        self,
        skill: str,
        current_level: ProficiencyLevel,
        target_level: ProficiencyLevel,
    ) -> List[LearningResource]:
        """
        Get learning resources for a skill gap.

        Delegates to ResourceCurator if available; otherwise returns
        placeholder resources so the plan is always populated.

        Args:
            skill: Skill name.
            current_level: Current proficiency.
            target_level: Target proficiency.

        Returns:
            List of at least 3 LearningResource objects.
        """
        if self.resource_curator is not None:
            try:
                resources = self.resource_curator.curate_resources(
                    skill, current_level, target_level
                )
                if resources:
                    return resources
            except Exception as exc:
                logger.warning("ResourceCurator failed for '%s': %s", skill, exc)

        # Fallback placeholder resources
        return self._placeholder_resources(skill, current_level)

    @staticmethod
    def _placeholder_resources(
        skill: str, current_level: ProficiencyLevel
    ) -> List[LearningResource]:
        """Return generic placeholder resources when the curator is unavailable."""
        from src.models import ResourceFormat

        difficulty = current_level.name.lower() if current_level != ProficiencyLevel.NONE else "beginner"
        return [
            LearningResource(
                title=f"Official {skill} Documentation",
                url=f"https://docs.example.com/{skill.lower().replace(' ', '-')}",
                format=ResourceFormat.DOCUMENTATION,
                difficulty=difficulty,
                estimated_hours=5,
                is_free=True,
                description=f"Official documentation for {skill}.",
                provider="Official Docs",
            ),
            LearningResource(
                title=f"{skill} Beginner Tutorial",
                url=f"https://www.freecodecamp.org/learn/{skill.lower().replace(' ', '-')}",
                format=ResourceFormat.TUTORIAL,
                difficulty=difficulty,
                estimated_hours=8,
                is_free=True,
                description=f"Hands-on tutorial covering {skill} fundamentals.",
                provider="freeCodeCamp",
            ),
            LearningResource(
                title=f"{skill} Practice Projects",
                url=f"https://github.com/topics/{skill.lower().replace(' ', '-')}",
                format=ResourceFormat.PROJECT,
                difficulty=difficulty,
                estimated_hours=10,
                is_free=True,
                description=f"Open-source projects to practice {skill}.",
                provider="GitHub",
            ),
        ]

    @staticmethod
    def _milestone_for_step(skill: str, target_level: ProficiencyLevel) -> str:
        """Generate a milestone criterion string for a learning step."""
        level_descriptions = {
            ProficiencyLevel.BEGINNER: f"Complete a beginner project using {skill}.",
            ProficiencyLevel.INTERMEDIATE: f"Build a working application that uses {skill} in a real scenario.",
            ProficiencyLevel.ADVANCED: f"Contribute to an open-source {skill} project or solve advanced problems.",
            ProficiencyLevel.EXPERT: f"Lead a team project using {skill} or publish technical content about it.",
        }
        return level_descriptions.get(
            target_level, f"Demonstrate proficiency in {skill} at {target_level.name} level."
        )

    @staticmethod
    def _create_milestones(steps: List[LearningStep]) -> List[str]:
        """
        Create high-level milestone checkpoints for the learning plan.

        Groups steps into roughly equal thirds and creates a milestone
        for each group.

        Args:
            steps: Ordered list of learning steps.

        Returns:
            List of milestone strings.
        """
        if not steps:
            return []

        milestones = []
        third = max(1, len(steps) // 3)

        for i, step in enumerate(steps):
            if (i + 1) % third == 0 or i == len(steps) - 1:
                skills_so_far = [s.skill for s in steps[: i + 1]]
                milestones.append(
                    f"Milestone {len(milestones) + 1}: Complete learning for "
                    f"{', '.join(skills_so_far[-3:])}."
                )

        return milestones
