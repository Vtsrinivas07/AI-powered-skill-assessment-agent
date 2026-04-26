"""
Visualization engine for the Skill Assessment Agent.

Generates radar charts and bar charts to visually represent skill gaps
between job requirements and assessed proficiency levels.

Validates Requirements: 3.4
"""

import logging
import os
from typing import List, Optional, Tuple

from src.exceptions import VisualizationError
from src.models import GapAnalysis, ProficiencyLevel, SkillGap

logger = logging.getLogger(__name__)

# Numeric value for each proficiency level (used in charts)
_LEVEL_VALUES = {
    ProficiencyLevel.NONE: 0,
    ProficiencyLevel.BEGINNER: 1,
    ProficiencyLevel.INTERMEDIATE: 2,
    ProficiencyLevel.ADVANCED: 3,
    ProficiencyLevel.EXPERT: 4,
}

_MAX_LEVEL = 4  # ProficiencyLevel.EXPERT.value


class VisualizationEngine:
    """
    Generates visual representations of skill gap analysis results.

    Produces:
    - Radar chart: required vs. assessed proficiency across all skills.
    - Bar chart: gap magnitude per skill, colour-coded by severity.
    """

    def __init__(self, output_dir: str = "outputs") -> None:
        """
        Initialise the VisualizationEngine.

        Args:
            output_dir: Directory where chart images will be saved.
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_radar_chart(
        self,
        gap_analysis: GapAnalysis,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Create a radar chart comparing required vs. assessed skill levels.
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np
        except ImportError as exc:
            raise VisualizationError(f"matplotlib/numpy not installed: {exc}") from exc

        all_gaps = gap_analysis.gaps
        if not all_gaps:
            raise VisualizationError("No skill gaps to visualise.")

        # Limit to 10 skills for readability
        gaps = all_gaps[:10]
        labels = [g.skill for g in gaps]
        required_vals = [_LEVEL_VALUES.get(g.required_level, 0) for g in gaps]
        assessed_vals = [_LEVEL_VALUES.get(g.assessed_level, 0) for g in gaps]

        n = len(labels)
        angles = self._compute_angles(n)

        # Close the polygon
        required_vals += required_vals[:1]
        assessed_vals += assessed_vals[:1]
        angles_closed = angles + angles[:1]

        # Use a dark theme for the figure
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(9, 9), subplot_kw={"polar": True}, facecolor='#0a0a0c')
        ax.set_facecolor('#111116')
        
        self._style_radar_axes(ax, angles, labels, n)

        # Plot Required with a soft glow
        ax.plot(angles_closed, required_vals, "o-", linewidth=3, color="#6366f1", label="Required", markersize=6)
        ax.fill(angles_closed, required_vals, alpha=0.15, color="#6366f1")

        # Plot Assessed with a distinct emerald color
        ax.plot(angles_closed, assessed_vals, "o-", linewidth=3, color="#10b981", label="Assessed", markersize=6)
        ax.fill(angles_closed, assessed_vals, alpha=0.25, color="#10b981")

        ax.set_ylim(0, _MAX_LEVEL)
        ax.set_yticks(range(_MAX_LEVEL + 1))
        ax.set_yticklabels(
            ["None", "Beginner", "Inter", "Adv", "Expert"],
            fontsize=8,
            color="#94a3b8",
        )

        legend = ax.legend(loc="upper right", bbox_to_anchor=(1.2, 1.1), fontsize=11, frameon=False)
        plt.setp(legend.get_texts(), color='#e2e8f0')
        
        ax.set_title("Skill Proficiency Profile", size=18, pad=30, fontweight="bold", color="#f8fafc")

        path = output_path or os.path.join(self.output_dir, "radar_chart.png")
        try:
            fig.savefig(path, bbox_inches="tight", dpi=200, transparent=False, facecolor=fig.get_facecolor())
            plt.close(fig)
        except Exception as exc:
            plt.close(fig)
            raise VisualizationError(f"Failed to save radar chart: {exc}") from exc

        logger.info("Radar chart saved to %s", path)
        return path

    def create_gap_bar_chart(
        self,
        gap_analysis: GapAnalysis,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Create a horizontal bar chart showing gap magnitudes per skill.
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise VisualizationError(f"matplotlib not installed: {exc}") from exc

        from src.models import GapCategory

        all_gaps = gap_analysis.gaps
        if not all_gaps:
            raise VisualizationError("No skill gaps to visualise.")

        gaps = all_gaps[:15]
        skills = [g.skill for g in gaps]
        magnitudes = [g.gap_magnitude for g in gaps]

        # Modern palette
        colour_map = {
            GapCategory.CRITICAL: "#ef4444",   # Rose/Red
            GapCategory.MODERATE: "#f59e0b",   # Amber
            GapCategory.MINOR: "#10b981",      # Emerald
            GapCategory.STRENGTH: "#3b82f6",   # Blue
        }
        colours = [colour_map.get(g.category, "#64748b") for g in gaps]

        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(11, max(5, len(gaps) * 0.5 + 2)), facecolor='#0a0a0c')
        ax.set_facecolor('#0a0a0c')
        
        bars = ax.barh(skills, magnitudes, color=colours, edgecolor="none", height=0.7, alpha=0.85)

        # Value labels with better styling
        for bar, mag in zip(bars, magnitudes):
            ax.text(
                bar.get_width() + 0.1,
                bar.get_y() + bar.get_height() / 2,
                f"Gap: {mag}",
                va="center",
                fontsize=10,
                color="#cbd5e1",
                fontweight='500'
            )

        ax.set_xlabel("Proficiency Level Gap", fontsize=12, color="#94a3b8", labelpad=15)
        ax.set_title("Skill Gap Magnitude Analysis", fontsize=18, fontweight="bold", color="#f1f5f9", pad=25)
        ax.set_xlim(0, _MAX_LEVEL + 0.5)
        ax.set_xticks(range(_MAX_LEVEL + 1))
        
        # Cleaner axes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#334155')
        ax.spines['bottom'].set_color('#334155')
        ax.tick_params(axis='both', colors='#94a3b8')
        
        ax.invert_yaxis()

        # Custom Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#ef4444", label="Critical Gap", alpha=0.85),
            Patch(facecolor="#f59e0b", label="Moderate Gap", alpha=0.85),
            Patch(facecolor="#10b981", label="Minor Gap", alpha=0.85),
        ]
        leg = ax.legend(handles=legend_elements, loc="lower right", fontsize=10, frameon=False)
        plt.setp(leg.get_texts(), color='#94a3b8')

        plt.tight_layout()

        path = output_path or os.path.join(self.output_dir, "gap_bar_chart.png")
        try:
            fig.savefig(path, bbox_inches="tight", dpi=200, facecolor=fig.get_facecolor())
            plt.close(fig)
        except Exception as exc:
            plt.close(fig)
            raise VisualizationError(f"Failed to save bar chart: {exc}") from exc

        logger.info("Bar chart saved to %s", path)
        return path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_angles(n: int) -> List[float]:
        """Compute evenly-spaced angles for a radar chart with n axes."""
        import math
        return [2 * math.pi * i / n for i in range(n)]

    @staticmethod
    def _style_radar_axes(ax, angles: List[float], labels: List[str], n: int) -> None:
        """Apply consistent styling to radar chart axes."""
        import numpy as np
        ax.set_xticks(angles)
        ax.set_xticklabels(labels, fontsize=10, wrap=True, color="#cbd5e1", fontweight='500')
        ax.grid(color="#334155", linestyle="--", linewidth=0.5, alpha=0.5)
        ax.spines["polar"].set_visible(False)

    @staticmethod
    def _normalize_proficiency_scores(gaps: List[SkillGap]) -> Tuple[List[float], List[float]]:
        """
        Convert proficiency levels to normalised [0, 1] floats.

        Args:
            gaps: List of SkillGap objects.

        Returns:
            Tuple of (required_scores, assessed_scores) as floats in [0, 1].
        """
        required = [_LEVEL_VALUES.get(g.required_level, 0) / _MAX_LEVEL for g in gaps]
        assessed = [_LEVEL_VALUES.get(g.assessed_level, 0) / _MAX_LEVEL for g in gaps]
        return required, assessed
