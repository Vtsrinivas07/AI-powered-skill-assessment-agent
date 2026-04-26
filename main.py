#!/usr/bin/env python3
"""
Skill Assessment Agent — Main Entry Point

Orchestrates the complete workflow:
  1. Parse job description and resume
  2. Extract required and claimed skills
  3. Conduct conversational skill assessment
  4. Analyse skill gaps
  5. Generate personalised learning plan
  6. Create visualisations
  7. Export JSON and Markdown reports

Usage:
    python main.py --jd <job_description_file> --resume <resume_file>
    python main.py --help
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

# Force UTF-8 output on Windows to handle emoji/unicode in print statements
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# MainController
# ---------------------------------------------------------------------------

class MainController:
    """
    End-to-end orchestrator for the Skill Assessment Agent.

    Wires together all components and manages the assessment workflow
    within the configured time budget.
    """

    def __init__(
        self,
        output_dir: str = "outputs",
        max_assessment_time: int = 900,
        max_turns_per_skill: int = 3,
    ) -> None:
        """
        Initialise the MainController.

        Args:
            output_dir: Directory for output files.
            max_assessment_time: Maximum total assessment time in seconds.
            max_turns_per_skill: Max question-answer turns per skill.
        """
        self.output_dir = output_dir
        self.max_assessment_time = max_assessment_time
        self.max_turns_per_skill = max_turns_per_skill
        os.makedirs(output_dir, exist_ok=True)

    def run_assessment(
        self,
        jd_path: str,
        resume_path: str,
        candidate_name: Optional[str] = None,
        interactive: bool = True,
    ) -> dict:
        """
        Run the complete assessment workflow.

        Args:
            jd_path: Path to the job description file.
            resume_path: Path to the resume file.
            candidate_name: Optional candidate name for the report.
            interactive: If True, prompts the user for answers via stdin.
                         If False, uses placeholder responses (demo/test mode).

        Returns:
            Dict with keys: report, json_path, markdown_path, visualizations.
        """
        from config import Config
        from src.input_parser import InputParser
        from src.skill_extractor import SkillExtractor
        from src.gemini_client import GeminiClient
        from src.assessment_engine import AssessmentEngine
        from src.gap_analyzer import GapAnalyzer
        from src.resource_curator import ResourceCurator
        from src.learning_plan import LearningPlanGenerator
        from src.visualization import VisualizationEngine
        from src.output_generator import OutputGenerator
        from src.exceptions import VisualizationError

        start_time = time.time()

        # ----------------------------------------------------------------
        # Step 1: Parse documents
        # ----------------------------------------------------------------
        self._print_step(1, "Parsing documents…")
        parser = InputParser()
        jd_doc = parser.parse_document(jd_path)
        resume_doc = parser.parse_document(resume_path)
        self._print_ok(f"JD: {len(jd_doc.content)} chars | Resume: {len(resume_doc.content)} chars")

        # ----------------------------------------------------------------
        # Step 2: Extract skills
        # ----------------------------------------------------------------
        self._print_step(2, "Extracting skills…")
        llm = GeminiClient()
        extractor = SkillExtractor(llm)
        required_skills = extractor.extract_job_skills(jd_doc.content)
        claimed_skills = extractor.extract_resume_skills(resume_doc.content)
        self._print_ok(
            f"{len(required_skills)} required skills | {len(claimed_skills)} claimed skills"
        )

        # Infer job title from JD (first non-empty line)
        job_title = self._infer_job_title(jd_doc.content)

        # ----------------------------------------------------------------
        # Step 3: Conversational assessment
        # ----------------------------------------------------------------
        self._print_step(3, "Conducting skill assessment…")
        engine = AssessmentEngine(llm, max_turns=self.max_turns_per_skill)

        assessments = []
        time_per_skill = self._budget_time_per_skill(
            len(required_skills), start_time
        )

        for i, skill in enumerate(required_skills):
            elapsed = time.time() - start_time
            if elapsed >= self.max_assessment_time:
                logger.warning("Time budget exhausted after %d skills.", i)
                break

            print(f"\n  [{i + 1}/{len(required_skills)}] Assessing: {skill.name}")

            if interactive:
                get_response = self._interactive_response
                turns = self.max_turns_per_skill
            else:
                # Demo mode: single turn only to save time and API quota
                get_response = lambda q: f"I have significant practical experience with {skill.name} in high-stakes environments."
                turns = 1

            try:
                assessment = engine.assess_skill(
                    skill,
                    get_response_fn=get_response,
                    max_turns=turns,
                )
                assessments.append(assessment)
                print(
                    f"  → {assessment.proficiency.level.name} "
                    f"(confidence: {assessment.proficiency.confidence:.0%})"
                )
            except Exception as exc:
                logger.warning("Assessment failed for '%s': %s", skill.name, exc)

        self._print_ok(f"{len(assessments)} skills assessed")

        # ----------------------------------------------------------------
        # Step 4: Gap analysis
        # ----------------------------------------------------------------
        self._print_step(4, "Analysing skill gaps…")
        analyzer = GapAnalyzer()
        gap_analysis = analyzer.analyze_gaps(required_skills, assessments)
        self._print_ok(
            f"Match score: {gap_analysis.match_score:.1f}/100 | "
            f"{len(gap_analysis.critical_gaps)} critical, "
            f"{len(gap_analysis.moderate_gaps)} moderate, "
            f"{len(gap_analysis.minor_gaps)} minor gaps"
        )

        # ----------------------------------------------------------------
        # Step 5: Learning plan
        # ----------------------------------------------------------------
        self._print_step(5, "Generating learning plan…")
        curator = ResourceCurator(llm)
        planner = LearningPlanGenerator(resource_curator=curator)
        learning_plan = planner.generate_plan(gap_analysis, assessments)
        self._print_ok(
            f"{len(learning_plan.steps)} steps | "
            f"{learning_plan.total_hours} hours (~{learning_plan.timeline_weeks} weeks)"
        )

        # ----------------------------------------------------------------
        # Step 6: Visualisations
        # ----------------------------------------------------------------
        self._print_step(6, "Creating visualisations…")
        viz_engine = VisualizationEngine(output_dir=self.output_dir)
        visualizations: List[str] = []
        try:
            radar_path = viz_engine.create_radar_chart(gap_analysis)
            visualizations.append(radar_path)
        except VisualizationError as exc:
            logger.warning("Radar chart failed: %s", exc)
        try:
            bar_path = viz_engine.create_gap_bar_chart(gap_analysis)
            visualizations.append(bar_path)
        except VisualizationError as exc:
            logger.warning("Bar chart failed: %s", exc)
        self._print_ok(f"{len(visualizations)} chart(s) created")

        # ----------------------------------------------------------------
        # Step 7: Export reports
        # ----------------------------------------------------------------
        self._print_step(7, "Exporting reports…")
        generator = OutputGenerator(output_dir=self.output_dir)
        report = generator.generate_report(
            assessments=assessments,
            gap_analysis=gap_analysis,
            learning_plan=learning_plan,
            visualizations=visualizations,
            job_title=job_title,
            candidate_name=candidate_name,
        )
        json_path = generator.export_json(report)
        md_path = generator.export_markdown(report)
        self._print_ok(f"JSON → {json_path} | Markdown → {md_path}")

        # ----------------------------------------------------------------
        # Done
        # ----------------------------------------------------------------
        total_time = time.time() - start_time
        print(f"\n{'=' * 70}")
        print(f"  Assessment complete in {total_time:.1f}s")
        print(f"  Match score: {gap_analysis.match_score:.1f}/100")
        print(f"  Reports saved to: {self.output_dir}/")
        print(f"{'=' * 70}\n")

        return {
            "report": report,
            "json_path": json_path,
            "markdown_path": md_path,
            "visualizations": visualizations,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _interactive_response(question: str) -> str:
        """Prompt the user for a response via stdin."""
        print(f"\n  Q: {question}")
        try:
            answer = input("  A: ").strip()
            return answer if answer else "(no response)"
        except (EOFError, KeyboardInterrupt):
            return "(no response)"

    @staticmethod
    def _infer_job_title(jd_text: str) -> str:
        """Extract the first meaningful line as the job title."""
        for line in jd_text.splitlines():
            line = line.strip()
            if line and len(line) < 100:
                return line
        return "Unknown Position"

    def _budget_time_per_skill(self, n_skills: int, start_time: float) -> float:
        """Calculate seconds available per skill."""
        if n_skills == 0:
            return self.max_assessment_time
        remaining = self.max_assessment_time - (time.time() - start_time)
        return max(30.0, remaining / n_skills)

    @staticmethod
    def _print_step(n: int, msg: str) -> None:
        print(f"\n[{n}/7] {msg}")

    @staticmethod
    def _print_ok(msg: str) -> None:
        print(f"  [OK] {msg}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-Powered Skill Assessment & Personalised Learning Plan Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --jd samples/job_description.txt --resume samples/resume.txt
  python main.py --jd job.pdf --resume cv.pdf --output-dir my_reports
  python main.py --jd job.txt --resume cv.txt --no-interactive  # demo mode

Environment Variables:
  GEMINI_API_KEY    Google Gemini API key (required)
  API_TIMEOUT       API timeout in seconds (default: 30)
  MAX_RETRIES       API retry attempts (default: 3)
        """,
    )
    parser.add_argument(
        "--jd", "--job-description",
        dest="job_description",
        required=True,
        help="Path to job description file (PDF or text)",
    )
    parser.add_argument(
        "--resume",
        required=True,
        help="Path to resume file (PDF or text)",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory for output files (default: outputs)",
    )
    parser.add_argument(
        "--max-assessment-time",
        type=int,
        default=900,
        help="Maximum assessment time in seconds (default: 900)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=3,
        help="Max question-answer turns per skill (default: 3)",
    )
    parser.add_argument(
        "--candidate-name",
        default=None,
        help="Candidate name for the report (optional)",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Run in demo mode with placeholder responses (no user input)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="Skill Assessment Agent v1.0.0",
    )
    return parser.parse_args()


def main() -> int:
    try:
        # Load .env if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        args = parse_arguments()

        # Validate files exist
        for label, path in [("Job description", args.job_description), ("Resume", args.resume)]:
            if not os.path.exists(path):
                print(f"[ERROR] {label} file not found: {path}", file=sys.stderr)
                return 1

        # Validate API key
        if not os.getenv("GEMINI_API_KEY"):
            print(
                "[ERROR] GEMINI_API_KEY environment variable not set.\n"
                "        Copy .env.example to .env and add your key.",
                file=sys.stderr,
            )
            return 1

        print("=" * 70)
        print("  Skill Assessment Agent")
        print("=" * 70)
        print(f"  Job Description : {args.job_description}")
        print(f"  Resume          : {args.resume}")
        print(f"  Output Directory: {args.output_dir}")
        print(f"  Max Time        : {args.max_assessment_time}s")
        print(f"  Mode            : {'demo (no-interactive)' if args.no_interactive else 'interactive'}")

        controller = MainController(
            output_dir=args.output_dir,
            max_assessment_time=args.max_assessment_time,
            max_turns_per_skill=args.max_turns,
        )

        result = controller.run_assessment(
            jd_path=args.job_description,
            resume_path=args.resume,
            candidate_name=args.candidate_name,
            interactive=not args.no_interactive,
        )

        return 0

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        logger.exception("Unhandled exception")
        return 1


if __name__ == "__main__":
    sys.exit(main())
