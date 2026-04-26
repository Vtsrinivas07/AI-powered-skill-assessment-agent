"""
Skill extractor for the Skill Assessment Agent.

Uses the Gemini LLM to extract required skills from job descriptions
and claimed skills from resumes, with normalisation and categorisation.

Validates Requirements: 1.3, 1.4
"""

import json
import logging
import re
from typing import Dict, List

from src.exceptions import SkillExtractionError
from src.gemini_client import GeminiClient
from src.models import ClaimedSkill, ProficiencyLevel, RequiredSkill

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skill name normalisation map (common aliases → canonical names)
# ---------------------------------------------------------------------------
_SKILL_ALIASES: Dict[str, str] = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python3": "Python",
    "golang": "Go",
    "k8s": "Kubernetes",
    "kube": "Kubernetes",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "react.js": "React",
    "reactjs": "React",
    "vue.js": "Vue",
    "vuejs": "Vue",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "ml": "Machine Learning",
    "ai": "Artificial Intelligence",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "rest": "REST APIs",
    "restful": "REST APIs",
    "graphql": "GraphQL",
    "sql": "SQL",
    "nosql": "NoSQL",
    "docker": "Docker",
    "git": "Git",
    "linux": "Linux",
}

# ---------------------------------------------------------------------------
# Skill category keywords
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "programming_language": [
        "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
        "ruby", "php", "swift", "kotlin", "scala", "r", "matlab",
    ],
    "framework": [
        "react", "vue", "angular", "django", "flask", "fastapi", "spring",
        "express", "rails", "laravel", "next.js", "nuxt", "svelte",
    ],
    "database": [
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra",
        "dynamodb", "sqlite", "oracle", "sql server", "nosql", "sql",
    ],
    "cloud": [
        "aws", "gcp", "azure", "cloud", "lambda", "s3", "ec2", "kubernetes",
        "docker", "terraform", "ansible", "ci/cd",
    ],
    "tool": [
        "git", "linux", "bash", "jira", "confluence", "figma", "postman",
        "graphql", "rest apis", "grpc", "kafka", "rabbitmq",
    ],
    "soft_skill": [
        "communication", "leadership", "teamwork", "problem solving",
        "critical thinking", "agile", "scrum", "kanban",
    ],
}


class SkillExtractor:
    """
    Extracts and normalises skills from job descriptions and resumes.

    Uses the Gemini LLM to parse free-form text and return structured
    skill lists with categories and proficiency context.
    """

    def __init__(self, llm_client: GeminiClient) -> None:
        """
        Initialise the SkillExtractor.

        Args:
            llm_client: Configured GeminiClient instance.
        """
        self.llm = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_job_skills(self, jd_text: str) -> List[RequiredSkill]:
        """
        Extract required skills from a job description.

        Args:
            jd_text: Full text of the job description.

        Returns:
            List of RequiredSkill objects with context and priority.

        Raises:
            SkillExtractionError: If extraction fails or returns no skills.
        """
        prompt = self._build_jd_prompt(jd_text)
        try:
            raw = self.llm.generate_text(prompt, temperature=0.1)
            skills_data = self._parse_json_response(raw)
        except Exception as exc:
            raise SkillExtractionError(f"Failed to extract job skills: {exc}") from exc

        if not skills_data:
            raise SkillExtractionError("No skills could be extracted from the job description.")

        skills: List[RequiredSkill] = []
        for item in skills_data:
            name = self._normalize_skill_name(item.get("name", "").strip())
            if not name:
                continue
            category = self._categorize_skill(name)
            priority = item.get("priority", "required").lower()
            if priority not in ("required", "preferred"):
                priority = "required"
            context = item.get("context", "")
            required_level = self._parse_proficiency(item.get("required_level", "intermediate"))

            skills.append(
                RequiredSkill(
                    name=name,
                    category=category,
                    context=context,
                    priority=priority,
                    required_level=required_level,
                )
            )

        # Limit to top 7 skills for demo performance and rate-limit safety
        skills.sort(key=lambda x: (x.priority == "preferred", x.name))
        skills = skills[:7]

        logger.info("Extracted %d required skills from job description (limited for performance)", len(skills))
        return skills

    def extract_resume_skills(self, resume_text: str) -> List[ClaimedSkill]:
        """
        Extract claimed skills and experience from a resume.

        Args:
            resume_text: Full text of the resume.

        Returns:
            List of ClaimedSkill objects with experience context.

        Raises:
            SkillExtractionError: If extraction fails or returns no skills.
        """
        prompt = self._build_resume_prompt(resume_text)
        try:
            raw = self.llm.generate_text(prompt, temperature=0.1)
            skills_data = self._parse_json_response(raw)
        except Exception as exc:
            raise SkillExtractionError(f"Failed to extract resume skills: {exc}") from exc

        if not skills_data:
            raise SkillExtractionError("No skills could be extracted from the resume.")

        skills: List[ClaimedSkill] = []
        for item in skills_data:
            name = self._normalize_skill_name(item.get("name", "").strip())
            if not name:
                continue
            years_raw = item.get("experience_years")
            try:
                experience_years = float(years_raw) if years_raw is not None else None
            except (TypeError, ValueError):
                experience_years = None
            context = item.get("context", "")

            skills.append(
                ClaimedSkill(
                    name=name,
                    experience_years=experience_years,
                    context=context,
                )
            )

        logger.info("Extracted %d claimed skills from resume", len(skills))
        return skills

    # ------------------------------------------------------------------
    # Normalisation & categorisation
    # ------------------------------------------------------------------

    def _normalize_skill_name(self, name: str) -> str:
        """
        Normalise a skill name to its canonical form.

        Args:
            name: Raw skill name string.

        Returns:
            Canonical skill name.
        """
        key = name.lower().strip()
        return _SKILL_ALIASES.get(key, name.strip())

    def _categorize_skill(self, name: str) -> str:
        """
        Assign a category to a skill based on keyword matching.

        Args:
            name: Canonical skill name.

        Returns:
            Category string (e.g. "programming_language", "framework").
        """
        lower = name.lower()
        for category, keywords in _CATEGORY_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return category
        return "other"

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_jd_prompt(jd_text: str) -> str:
        return f"""You are a technical recruiter. Extract ALL skills mentioned in the job description below.

Return ONLY a valid JSON array. Each element must have these fields:
- "name": skill name (string)
- "priority": "required" or "preferred"
- "context": brief context from the JD (≤ 20 words)
- "required_level": one of "beginner", "intermediate", "advanced", "expert"

Rules:
- Include both technical and soft skills
- Do NOT include generic phrases like "degree" or "experience"
- Return ONLY the JSON array, no markdown, no explanation

Job Description:
{jd_text}

JSON array:"""

    @staticmethod
    def _build_resume_prompt(resume_text: str) -> str:
        return f"""You are a technical recruiter. Extract ALL skills mentioned in the resume below.

Return ONLY a valid JSON array. Each element must have these fields:
- "name": skill name (string)
- "experience_years": estimated years of experience as a number, or null if unknown
- "context": brief context from the resume (≤ 20 words)

Rules:
- Include both technical and soft skills
- Infer experience years from dates/descriptions where possible
- Return ONLY the JSON array, no markdown, no explanation

Resume:
{resume_text}

JSON array:"""

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_response(raw: str) -> List[Dict]:
        """
        Parse a JSON array from the LLM response.

        Strips markdown code fences if present before parsing.

        Args:
            raw: Raw LLM response string.

        Returns:
            Parsed list of dicts.

        Raises:
            SkillExtractionError: If JSON cannot be parsed.
        """
        # Strip markdown code fences
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

        # Find the first '[' and last ']' to isolate the array
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1:
            raise SkillExtractionError(f"No JSON array found in response: {cleaned[:200]}")

        json_str = cleaned[start : end + 1]
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise SkillExtractionError(f"Invalid JSON in response: {exc}") from exc

        if not isinstance(data, list):
            raise SkillExtractionError("Expected a JSON array but got a different type.")

        return data

    @staticmethod
    def _parse_proficiency(level_str: str) -> ProficiencyLevel:
        """
        Convert a string proficiency level to the ProficiencyLevel enum.

        Args:
            level_str: String like "intermediate".

        Returns:
            Corresponding ProficiencyLevel enum value.
        """
        mapping = {
            "none": ProficiencyLevel.NONE,
            "beginner": ProficiencyLevel.BEGINNER,
            "intermediate": ProficiencyLevel.INTERMEDIATE,
            "advanced": ProficiencyLevel.ADVANCED,
            "expert": ProficiencyLevel.EXPERT,
        }
        return mapping.get(level_str.lower().strip(), ProficiencyLevel.INTERMEDIATE)
