"""
Output generator for the Skill Assessment Agent.

Compiles assessment results, gap analysis, and learning plans into
structured reports exported as JSON and human-readable Markdown.

Validates Requirements: 6.1, 6.2, 6.3, 6.4, 6.6
"""

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.exceptions import ExportError
from src.models import (
    GapAnalysis,
    GapCategory,
    LearningPlan,
    ProficiencyLevel,
    Report,
    SkillAssessment,
)

logger = logging.getLogger(__name__)


class OutputGenerator:
    """
    Compiles and exports assessment reports in JSON and Markdown formats.
    """

    def __init__(self, output_dir: str = "outputs") -> None:
        """
        Initialise the OutputGenerator.

        Args:
            output_dir: Directory where output files will be saved.
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_report(
        self,
        assessments: List[SkillAssessment],
        gap_analysis: GapAnalysis,
        learning_plan: LearningPlan,
        visualizations: List[str],
        job_title: str = "Unknown Position",
        candidate_name: Optional[str] = None,
    ) -> Report:
        """
        Compile all outputs into a Report object.

        Args:
            assessments: Completed skill assessments.
            gap_analysis: Analysed skill gaps.
            learning_plan: Generated learning plan.
            visualizations: Paths to chart images.
            job_title: Title of the job being assessed for.
            candidate_name: Optional candidate name.

        Returns:
            Report dataclass instance.
        """
        summary = self._create_summary(assessments, gap_analysis, learning_plan)
        methodology = self._document_methodology()

        report = Report(
            candidate_name=candidate_name,
            job_title=job_title,
            assessment_date=datetime.now(),
            assessments=assessments,
            gap_analysis=gap_analysis,
            learning_plan=learning_plan,
            visualizations=visualizations,
            methodology_notes=methodology,
            summary=summary,
        )

        logger.info(
            "Report generated: %d assessments, match_score=%.1f, %d learning steps",
            len(assessments),
            gap_analysis.match_score,
            len(learning_plan.steps),
        )
        return report

    def export_json(self, report: Report, output_path: Optional[str] = None) -> str:
        """
        Export the report as a structured JSON file.

        Args:
            report: The Report to export.
            output_path: File path. Auto-generated if None.

        Returns:
            Path to the saved JSON file.

        Raises:
            ExportError: If serialisation or file write fails.
        """
        path = output_path or os.path.join(self.output_dir, "assessment_report.json")
        try:
            data = self._report_to_dict(report)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as exc:
            raise ExportError(f"Failed to export JSON report: {exc}") from exc

        logger.info("JSON report saved to %s", path)
        return path

    def export_markdown(self, report: Report, output_path: Optional[str] = None) -> str:
        """
        Export the report as a human-readable Markdown file.

        Args:
            report: The Report to export.
            output_path: File path. Auto-generated if None.

        Returns:
            Path to the saved Markdown file.

        Raises:
            ExportError: If file write fails.
        """
        path = output_path or os.path.join(self.output_dir, "assessment_report.md")
        try:
            md = self._build_markdown(report)
            with open(path, "w", encoding="utf-8") as f:
                f.write(md)
        except Exception as exc:
            raise ExportError(f"Failed to export Markdown report: {exc}") from exc

        logger.info("Markdown report saved to %s", path)
        return path

    # ------------------------------------------------------------------
    # Summary and methodology
    # ------------------------------------------------------------------

    @staticmethod
    def _create_summary(
        assessments: List[SkillAssessment],
        gap_analysis: GapAnalysis,
        learning_plan: LearningPlan,
    ) -> str:
        """Generate a concise executive summary."""
        n_skills = len(assessments)
        n_critical = len(gap_analysis.critical_gaps)
        n_strengths = len(gap_analysis.strengths)
        match = gap_analysis.match_score
        total_hours = learning_plan.total_hours
        weeks = learning_plan.timeline_weeks

        lines = [
            f"Assessment completed for {n_skills} skill(s).",
            f"Overall match score: {match:.1f}/100.",
        ]
        if n_critical:
            critical_names = ", ".join(g.skill for g in gap_analysis.critical_gaps[:3])
            lines.append(f"Critical gaps identified: {critical_names}.")
        if n_strengths:
            lines.append(f"Strengths: {', '.join(gap_analysis.strengths[:3])}.")
        if total_hours:
            lines.append(
                f"Personalised learning plan: {total_hours} hours (~{weeks} weeks)."
            )
        return " ".join(lines)

    @staticmethod
    def _document_methodology() -> str:
        """Return a description of the assessment methodology."""
        return (
            "Proficiency levels: NONE (0), BEGINNER (1), INTERMEDIATE (2), "
            "ADVANCED (3), EXPERT (4). "
            "Each skill is assessed via multi-turn conversational questions. "
            "The LLM evaluates technical accuracy and depth, assigning a level "
            "with a confidence score (0–1) and justification. "
            "Gap magnitude = required_level − assessed_level. "
            "Critical gaps: required skill with magnitude ≥ 2. "
            "Moderate gaps: magnitude = 1 or non-critical skill. "
            "Match score: weighted average where required skills count 2× preferred. "
            "Adjacent skills (gap = 1) are prioritised in the learning plan."
        )

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def _report_to_dict(self, report: Report) -> Dict[str, Any]:
        """Convert a Report to a JSON-serialisable dict."""
        return {
            "candidate_name": report.candidate_name,
            "job_title": report.job_title,
            "assessment_date": report.assessment_date.isoformat(),
            "summary": report.summary,
            "methodology_notes": report.methodology_notes,
            "match_score": report.gap_analysis.match_score,
            "assessments": [self._assessment_to_dict(a) for a in report.assessments],
            "gap_analysis": self._gap_analysis_to_dict(report.gap_analysis),
            "learning_plan": self._learning_plan_to_dict(report.learning_plan),
            "visualizations": report.visualizations,
        }

    @staticmethod
    def _assessment_to_dict(a: SkillAssessment) -> Dict[str, Any]:
        return {
            "skill": a.skill.name,
            "category": a.skill.category,
            "priority": a.skill.priority,
            "required_level": a.skill.required_level.name,
            "assessed_level": a.proficiency.level.name,
            "confidence": a.proficiency.confidence,
            "justification": a.proficiency.justification,
            "evidence": a.proficiency.evidence,
            "questions_asked": a.questions_asked,
            "responses": a.responses,
            "duration_seconds": round(a.duration_seconds, 2),
        }

    @staticmethod
    def _gap_analysis_to_dict(ga: GapAnalysis) -> Dict[str, Any]:
        def gap_dict(g):
            return {
                "skill": g.skill,
                "required_level": g.required_level.name,
                "assessed_level": g.assessed_level.name,
                "gap_magnitude": g.gap_magnitude,
                "category": g.category.value,
                "priority_rank": g.priority_rank,
                "is_adjacent": g.is_adjacent,
            }
        return {
            "match_score": ga.match_score,
            "strengths": ga.strengths,
            "critical_gaps": [gap_dict(g) for g in ga.critical_gaps],
            "moderate_gaps": [gap_dict(g) for g in ga.moderate_gaps],
            "minor_gaps": [gap_dict(g) for g in ga.minor_gaps],
            "all_gaps": [gap_dict(g) for g in ga.gaps],
        }

    @staticmethod
    def _learning_plan_to_dict(lp: LearningPlan) -> Dict[str, Any]:
        def step_dict(s):
            return {
                "skill": s.skill,
                "current_level": s.current_level.name,
                "target_level": s.target_level.name,
                "estimated_hours": s.estimated_hours,
                "prerequisites": s.prerequisites,
                "milestone_criteria": s.milestone_criteria,
                "resources": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "format": r.format.value,
                        "difficulty": r.difficulty,
                        "estimated_hours": r.estimated_hours,
                        "is_free": r.is_free,
                        "description": r.description,
                        "provider": r.provider,
                    }
                    for r in s.resources
                ],
            }
        return {
            "total_hours": lp.total_hours,
            "timeline_weeks": lp.timeline_weeks,
            "focus_areas": lp.focus_areas,
            "prerequisites_needed": lp.prerequisites_needed,
            "milestones": lp.milestones,
            "steps": [step_dict(s) for s in lp.steps],
        }

    # ------------------------------------------------------------------
    # Markdown builder
    # ------------------------------------------------------------------

    def _build_markdown(self, report: Report) -> str:
        lines: List[str] = []

        # Header
        lines += [
            f"# Skill Assessment Report",
            f"",
            f"**Job Title:** {report.job_title}",
            f"**Assessment Date:** {report.assessment_date.strftime('%Y-%m-%d %H:%M')}",
        ]
        if report.candidate_name:
            lines.append(f"**Candidate:** {report.candidate_name}")
        lines += ["", "---", ""]

        # Summary
        lines += ["## Summary", "", report.summary, ""]

        # Match score
        score = report.gap_analysis.match_score
        bar = self._score_bar(score)
        lines += [
            "## Overall Match Score",
            "",
            f"**{score:.1f} / 100** {bar}",
            "",
        ]

        # Skill assessments
        lines += ["## Skill Assessments", ""]
        for a in report.assessments:
            gap_label = self._gap_label(a.skill.required_level, a.proficiency.level)
            lines += [
                f"### {a.skill.name} {gap_label}",
                f"- **Required:** {a.skill.required_level.name}",
                f"- **Assessed:** {a.proficiency.level.name} (confidence: {a.proficiency.confidence:.0%})",
                f"- **Justification:** {a.proficiency.justification}",
            ]
            if a.proficiency.evidence:
                lines.append("- **Evidence:**")
                for ev in a.proficiency.evidence:
                    lines.append(f"  - {ev}")
            lines.append("")

        # Gap analysis
        lines += ["## Skill Gap Analysis", ""]
        if report.gap_analysis.strengths:
            lines += [
                "### ✅ Strengths",
                "",
                ", ".join(report.gap_analysis.strengths),
                "",
            ]
        if report.gap_analysis.critical_gaps:
            lines += ["### 🔴 Critical Gaps", ""]
            for g in report.gap_analysis.critical_gaps:
                lines.append(f"- **{g.skill}**: {g.assessed_level.name} → {g.required_level.name} (gap: {g.gap_magnitude})")
            lines.append("")
        if report.gap_analysis.moderate_gaps:
            lines += ["### 🟠 Moderate Gaps", ""]
            for g in report.gap_analysis.moderate_gaps:
                lines.append(f"- **{g.skill}**: {g.assessed_level.name} → {g.required_level.name} (gap: {g.gap_magnitude})")
            lines.append("")
        if report.gap_analysis.minor_gaps:
            lines += ["### 🟡 Minor Gaps", ""]
            for g in report.gap_analysis.minor_gaps:
                lines.append(f"- **{g.skill}**: {g.assessed_level.name} → {g.required_level.name} (gap: {g.gap_magnitude})")
            lines.append("")

        # Visualizations
        if report.visualizations:
            lines += ["## Visualizations", ""]
            for viz_path in report.visualizations:
                fname = os.path.basename(viz_path)
                lines.append(f"![{fname}]({viz_path})")
            lines.append("")

        # Learning plan
        lp = report.learning_plan
        lines += [
            "## Personalised Learning Plan",
            "",
            f"**Total estimated time:** {lp.total_hours} hours (~{lp.timeline_weeks} weeks)",
            "",
        ]
        if lp.prerequisites_needed:
            lines += [
                "**Prerequisites needed first:**",
                ", ".join(lp.prerequisites_needed),
                "",
            ]
        for i, step in enumerate(lp.steps, 1):
            adj_tag = " *(adjacent)*" if step.current_level.value + 1 == step.target_level.value else ""
            lines += [
                f"### Step {i}: {step.skill}{adj_tag}",
                f"- **From:** {step.current_level.name} → **To:** {step.target_level.name}",
                f"- **Estimated time:** {step.estimated_hours} hours",
                f"- **Milestone:** {step.milestone_criteria}",
                "",
                "**Resources:**",
            ]
            for r in step.resources:
                free_tag = "🆓 " if r.is_free else "💰 "
                lines.append(f"- {free_tag}[{r.title}]({r.url}) — {r.format.value}, ~{r.estimated_hours}h ({r.provider})")
            lines.append("")

        if lp.milestones:
            lines += ["### Milestones", ""]
            for m in lp.milestones:
                lines.append(f"- {m}")
            lines.append("")

        # Methodology
        lines += [
            "---",
            "",
            "## Assessment Methodology",
            "",
            report.methodology_notes,
            "",
        ]

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_bar(score: float) -> str:
        """Return a simple ASCII progress bar for the match score."""
        filled = round(score / 10)
        return "█" * filled + "░" * (10 - filled)

    @staticmethod
    def _gap_label(required: ProficiencyLevel, assessed: ProficiencyLevel) -> str:
        """Return an emoji label based on gap direction."""
        if assessed.value >= required.value:
            return "✅"
        if required.value - assessed.value >= 2:
            return "🔴"
        return "🟠"
