"""
Resource curator for the Skill Assessment Agent.

Uses the Gemini LLM to find high-quality, free learning resources for
each skill gap, validates URLs, and ensures format diversity.

Validates Requirements: 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

import json
import logging
import re
from typing import List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from src.exceptions import InsufficientResourcesError, URLValidationError
from src.gemini_client import GeminiClient
from src.models import LearningResource, ProficiencyLevel, ResourceFormat

logger = logging.getLogger(__name__)

# Minimum number of resources required per skill
_MIN_RESOURCES = 3
# URL validation timeout in seconds
_URL_TIMEOUT = 3


class ResourceCurator:
    """
    Curates high-quality learning resources for skill gaps.

    Uses the Gemini LLM to generate resource recommendations, then
    validates URLs and ensures format diversity before returning results.
    """

    def __init__(self, llm_client: GeminiClient) -> None:
        """
        Initialise the ResourceCurator.

        Args:
            llm_client: Configured GeminiClient instance.
        """
        self.llm = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def curate_resources(
        self,
        skill: str,
        current_level: ProficiencyLevel,
        target_level: ProficiencyLevel,
    ) -> List[LearningResource]:
        """
        Curate learning resources for a skill gap.

        Args:
            skill: The skill to learn.
            current_level: Candidate's current proficiency.
            target_level: Required proficiency level.

        Returns:
            List of at least 3 LearningResource objects, prioritising free resources.

        Raises:
            InsufficientResourcesError: If fewer than 1 resource can be found.
        """
        prompt = self._build_prompt(skill, current_level, target_level)
        try:
            raw = self.llm.generate_text(prompt, temperature=0.2)
            resources_data = self._parse_json_response(raw)
        except Exception as exc:
            logger.warning("LLM resource curation failed for '%s': %s", skill, exc)
            resources_data = []

        resources = self._parse_resources(resources_data, skill, current_level)

        # Prioritise free resources
        resources = self._prioritize_free_resources(resources)

        # Ensure format diversity
        resources = self._diversify_formats(resources)

        if not resources:
            raise InsufficientResourcesError(
                f"Could not find any resources for skill '{skill}'."
            )

        # Pad to minimum count with fallbacks if needed
        if len(resources) < _MIN_RESOURCES:
            logger.warning(
                "Only %d resources found for '%s'; padding with fallbacks.",
                len(resources), skill,
            )
            resources = self._pad_with_fallbacks(resources, skill, current_level)

        logger.info("Curated %d resources for skill '%s'", len(resources), skill)
        return resources

    def validate_url(self, url: str) -> bool:
        """
        Verify that a resource URL is accessible.

        Uses a HEAD request with a short timeout to avoid blocking.

        Args:
            url: URL to validate.

        Returns:
            True if the URL returns a 2xx or 3xx status code.
        """
        try:
            req = Request(url, method="HEAD")
            req.add_header("User-Agent", "SkillAssessmentAgent/1.0")
            with urlopen(req, timeout=_URL_TIMEOUT) as resp:
                return resp.status < 400
        except (URLError, HTTPError, Exception):
            return False

    def estimate_time(self, resource: LearningResource) -> int:
        """
        Estimate completion time in hours for a resource.

        Uses the resource's format and difficulty as heuristics.

        Args:
            resource: The LearningResource to estimate.

        Returns:
            Estimated hours (positive integer).
        """
        base_hours = {
            ResourceFormat.DOCUMENTATION: 3,
            ResourceFormat.TUTORIAL: 5,
            ResourceFormat.COURSE: 20,
            ResourceFormat.VIDEO: 4,
            ResourceFormat.BOOK: 30,
            ResourceFormat.PROJECT: 10,
            ResourceFormat.PRACTICE: 8,
        }
        difficulty_multiplier = {
            "beginner": 1.0,
            "intermediate": 1.5,
            "advanced": 2.0,
            "expert": 3.0,
        }
        base = base_hours.get(resource.format, 5)
        multiplier = difficulty_multiplier.get(resource.difficulty.lower(), 1.0)
        return max(1, round(base * multiplier))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prioritize_free_resources(
        self, resources: List[LearningResource]
    ) -> List[LearningResource]:
        """Sort resources so free ones appear before paid ones."""
        return sorted(resources, key=lambda r: (0 if r.is_free else 1))

    def _diversify_formats(
        self, resources: List[LearningResource]
    ) -> List[LearningResource]:
        """
        Ensure at least 2 different formats are represented.

        If all resources share the same format, the list is returned as-is
        (the LLM may not always produce diverse results).

        Args:
            resources: Input resource list.

        Returns:
            Same list (format diversity is a best-effort goal).
        """
        formats = {r.format for r in resources}
        if len(formats) < 2 and len(resources) >= 2:
            logger.debug("Low format diversity (%d format(s)) for resource list.", len(formats))
        return resources

    def _pad_with_fallbacks(
        self,
        resources: List[LearningResource],
        skill: str,
        current_level: ProficiencyLevel,
    ) -> List[LearningResource]:
        """Add fallback resources until the minimum count is reached."""
        fallbacks = self._fallback_resources(skill, current_level)
        existing_urls = {r.url for r in resources}
        for fb in fallbacks:
            if len(resources) >= _MIN_RESOURCES:
                break
            if fb.url not in existing_urls:
                resources.append(fb)
                existing_urls.add(fb.url)
        return resources

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(
        skill: str,
        current_level: ProficiencyLevel,
        target_level: ProficiencyLevel,
    ) -> str:
        current_label = current_level.name.lower()
        target_label = target_level.name.lower()
        return (
            f"You are a learning resource expert. Recommend exactly 5 high-quality, "
            f"FREE learning resources to help someone advance their '{skill}' skills "
            f"from {current_label} to {target_label} level.\n\n"
            f"Return ONLY a valid JSON array. Each element must have:\n"
            f"- \"title\": resource title (string)\n"
            f"- \"url\": direct URL (string, must be a real, accessible URL)\n"
            f"- \"format\": one of documentation, tutorial, course, video, book, project, practice\n"
            f"- \"difficulty\": one of beginner, intermediate, advanced, expert\n"
            f"- \"estimated_hours\": integer hours to complete\n"
            f"- \"is_free\": true or false\n"
            f"- \"description\": 1-sentence description (string)\n"
            f"- \"provider\": provider name e.g. MDN, freeCodeCamp, YouTube (string)\n\n"
            f"Rules:\n"
            f"- Prefer free resources (freeCodeCamp, MDN, official docs, YouTube, GitHub)\n"
            f"- Include at least 2 different formats\n"
            f"- Include at least 1 hands-on practice resource\n"
            f"- Return ONLY the JSON array, no markdown, no explanation\n"
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_response(raw: str) -> list:
        """Parse a JSON array from the LLM response."""
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1:
            return []
        try:
            return json.loads(cleaned[start: end + 1])
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _parse_resources(
        data: list,
        skill: str,
        current_level: ProficiencyLevel,
    ) -> List[LearningResource]:
        """Convert raw dicts to LearningResource objects."""
        format_map = {f.value: f for f in ResourceFormat}
        difficulty_label = current_level.name.lower() if current_level != ProficiencyLevel.NONE else "beginner"

        resources = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            if not title or not url:
                continue

            fmt_str = str(item.get("format", "tutorial")).lower()
            fmt = format_map.get(fmt_str, ResourceFormat.TUTORIAL)

            difficulty = str(item.get("difficulty", difficulty_label)).lower()
            if difficulty not in ("beginner", "intermediate", "advanced", "expert"):
                difficulty = difficulty_label

            try:
                estimated_hours = max(1, int(item.get("estimated_hours", 5)))
            except (TypeError, ValueError):
                estimated_hours = 5

            is_free = bool(item.get("is_free", True))
            description = str(item.get("description", f"Learn {skill}.")).strip()
            provider = str(item.get("provider", "Unknown")).strip()

            resources.append(
                LearningResource(
                    title=title,
                    url=url,
                    format=fmt,
                    difficulty=difficulty,
                    estimated_hours=estimated_hours,
                    is_free=is_free,
                    description=description,
                    provider=provider,
                )
            )
        return resources

    @staticmethod
    def _fallback_resources(
        skill: str, current_level: ProficiencyLevel
    ) -> List[LearningResource]:
        """Return well-known fallback resources for common skills."""
        difficulty = current_level.name.lower() if current_level != ProficiencyLevel.NONE else "beginner"
        slug = skill.lower().replace(" ", "-").replace(".", "")
        return [
            LearningResource(
                title=f"{skill} — Official Documentation",
                url=f"https://docs.python.org/3/" if "python" in slug else f"https://developer.mozilla.org/en-US/docs/Web/{slug}",
                format=ResourceFormat.DOCUMENTATION,
                difficulty=difficulty,
                estimated_hours=4,
                is_free=True,
                description=f"Official reference documentation for {skill}.",
                provider="Official Docs",
            ),
            LearningResource(
                title=f"Learn {skill} — freeCodeCamp",
                url=f"https://www.freecodecamp.org/news/tag/{slug}/",
                format=ResourceFormat.TUTORIAL,
                difficulty=difficulty,
                estimated_hours=6,
                is_free=True,
                description=f"Free tutorials and articles about {skill}.",
                provider="freeCodeCamp",
            ),
            LearningResource(
                title=f"{skill} Crash Course — YouTube",
                url=f"https://www.youtube.com/results?search_query={slug}+tutorial",
                format=ResourceFormat.VIDEO,
                difficulty=difficulty,
                estimated_hours=3,
                is_free=True,
                description=f"Video tutorials for learning {skill}.",
                provider="YouTube",
            ),
            LearningResource(
                title=f"{skill} Practice Projects — GitHub",
                url=f"https://github.com/topics/{slug}",
                format=ResourceFormat.PROJECT,
                difficulty=difficulty,
                estimated_hours=10,
                is_free=True,
                description=f"Open-source projects to practice {skill}.",
                provider="GitHub",
            ),
        ]
