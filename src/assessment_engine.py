"""
Conversational assessment engine for the Skill Assessment Agent.

Conducts multi-turn dialogue to assess real proficiency on each required
skill, adapts question difficulty based on responses, detects evasion,
and produces structured proficiency ratings with justifications.

Validates Requirements: 2.1, 2.2, 2.3, 2.4, 2.7, 10.1, 10.2, 10.4, 10.5, 10.6
"""

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.conversation_state import ConversationState
from src.exceptions import AssessmentError, InvalidProficiencyError
from src.gemini_client import GeminiClient
from src.models import (
    ProficiencyLevel,
    ProficiencyRating,
    RequiredSkill,
    SkillAssessment,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_EVASION_PHRASES = [
    "i don't know",
    "not sure",
    "i'm not familiar",
    "i haven't used",
    "no experience",
    "never worked with",
    "i'll have to look that up",
    "i forget",
    "i can't remember",
]

_DIFFICULTY_LABELS = {
    ProficiencyLevel.NONE: "foundational",
    ProficiencyLevel.BEGINNER: "basic",
    ProficiencyLevel.INTERMEDIATE: "intermediate",
    ProficiencyLevel.ADVANCED: "advanced",
    ProficiencyLevel.EXPERT: "expert",
}


class AssessmentEngine:
    """
    Conducts conversational skill assessments via multi-turn dialogue.

    For each required skill the engine:
    1. Generates a contextual opening question.
    2. Evaluates the candidate's response.
    3. Adapts follow-up question difficulty.
    4. Produces a final ProficiencyRating with confidence and justification.
    """

    def __init__(
        self,
        llm_client: GeminiClient,
        max_turns: int = 3,
        confidence_threshold: float = 0.75,
    ) -> None:
        """
        Initialise the AssessmentEngine.

        Args:
            llm_client: Configured GeminiClient instance.
            max_turns: Maximum question-answer exchanges per skill.
            confidence_threshold: Stop early when confidence exceeds this value.
        """
        self.llm = llm_client
        self.max_turns = max_turns
        self.confidence_threshold = confidence_threshold
        self.conversation_state = ConversationState()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess_skill(
        self,
        skill: RequiredSkill,
        get_response_fn: Any,
        max_turns: Optional[int] = None,
    ) -> SkillAssessment:
        """
        Conduct a full multi-turn assessment for a single skill.

        Args:
            skill: The RequiredSkill to assess.
            get_response_fn: Callable(question: str) -> str that returns the
                             candidate's answer (e.g. reads from stdin or UI).
            max_turns: Override the default max_turns for this skill.

        Returns:
            SkillAssessment with final proficiency rating.

        Raises:
            AssessmentError: If the assessment cannot be completed.
        """
        turns = max_turns or self.max_turns
        self.conversation_state.reset_for_skill(skill.name)

        start_time = time.time()
        questions_asked: List[str] = []
        responses: List[str] = []
        current_difficulty = skill.required_level  # Start at required level

        # Collect evidence across turns
        all_evidence: List[str] = []
        running_rating: Optional[Dict[str, Any]] = None

        for turn in range(turns):
            # Generate question
            question = self.generate_question(skill, current_difficulty, turn)
            questions_asked.append(question)
            self.conversation_state.add_message("assistant", question)

            # Get candidate response
            try:
                response = get_response_fn(question)
            except Exception as exc:
                raise AssessmentError(f"Failed to get candidate response: {exc}") from exc

            if not response or not response.strip():
                response = "(no response provided)"

            responses.append(response)
            self.conversation_state.add_message("user", response)

            # Evaluate response
            rating_data = self.evaluate_response(question, response, skill)
            running_rating = rating_data
            all_evidence.extend(rating_data.get("evidence", []))

            # Adapt difficulty for next turn
            assessed_level = self._parse_level(rating_data.get("level", "intermediate"))
            current_difficulty = self._adapt_difficulty(assessed_level, skill.required_level, turn)

            # Early exit if confidence is high enough
            confidence = float(rating_data.get("confidence", 0.5))
            if confidence >= self.confidence_threshold and turn >= 1:
                logger.debug(
                    "Early exit at turn %d — confidence %.2f >= threshold %.2f",
                    turn + 1,
                    confidence,
                    self.confidence_threshold,
                )
                break

        # Build final proficiency rating
        if running_rating is None:
            raise AssessmentError("No rating produced during assessment.")

        proficiency = self._build_proficiency_rating(running_rating, all_evidence)
        duration = time.time() - start_time

        logger.info(
            "Assessed '%s': level=%s, confidence=%.2f, turns=%d, duration=%.1fs",
            skill.name,
            proficiency.level.name,
            proficiency.confidence,
            len(questions_asked),
            duration,
        )

        return SkillAssessment(
            skill=skill,
            proficiency=proficiency,
            questions_asked=questions_asked,
            responses=responses,
            duration_seconds=duration,
            timestamp=datetime.now(),
        )

    def generate_question(
        self,
        skill: RequiredSkill,
        difficulty: ProficiencyLevel,
        turn: int,
    ) -> str:
        """
        Generate a contextual assessment question for a skill.

        Args:
            skill: The skill being assessed.
            difficulty: Target difficulty level for this question.
            turn: Current turn index (0-based).

        Returns:
            Question string.
        """
        context_summary = self.conversation_state.get_context_summary()
        difficulty_label = _DIFFICULTY_LABELS.get(difficulty, "intermediate")

        if turn == 0:
            prompt = self._opening_question_prompt(skill, difficulty_label)
        else:
            prompt = self._followup_question_prompt(skill, difficulty_label, context_summary)

        try:
            question = self.llm.generate_text(prompt, temperature=0.4)
            return question.strip()
        except Exception as exc:
            # Fallback to a generic question
            logger.warning("Question generation failed, using fallback: %s", exc)
            return f"Can you describe your experience with {skill.name} and give a practical example?"

    def evaluate_response(
        self,
        question: str,
        response: str,
        skill: RequiredSkill,
    ) -> Dict[str, Any]:
        """
        Evaluate a candidate's response and produce a proficiency rating dict.

        Args:
            question: The question that was asked.
            response: The candidate's answer.
            skill: The skill being assessed.

        Returns:
            Dict with keys: level, confidence, justification, evidence.

        Raises:
            InvalidProficiencyError: If the LLM returns an unparseable rating.
        """
        # Check for evasion first
        if self._detect_evasion(response):
            logger.debug("Evasion detected in response for skill '%s'", skill.name)
            return {
                "level": "NONE",
                "confidence": 0.9,
                "justification": "Candidate indicated no familiarity with this skill.",
                "evidence": ["Candidate explicitly stated lack of knowledge or experience."],
            }

        prompt = self._evaluation_prompt(skill, question, response)
        try:
            raw = self.llm.generate_text(prompt, temperature=0.1)
            rating = self._parse_rating_response(raw)
        except InvalidProficiencyError:
            raise
        except Exception as exc:
            raise InvalidProficiencyError(f"Failed to evaluate response: {exc}") from exc

        return rating

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_evasion(self, response: str) -> bool:
        """
        Detect vague or evasive responses.

        Args:
            response: Candidate's answer string.

        Returns:
            True if the response appears evasive.
        """
        lower = response.lower().strip()
        # Very short responses are suspicious
        if len(lower.split()) < 5:
            for phrase in _EVASION_PHRASES:
                if phrase in lower:
                    return True
        return False

    def _adapt_difficulty(
        self,
        assessed_level: ProficiencyLevel,
        required_level: ProficiencyLevel,
        turn: int,
    ) -> ProficiencyLevel:
        """
        Adapt question difficulty based on the assessed level so far.

        Args:
            assessed_level: Level inferred from the last response.
            required_level: Level required by the job.
            turn: Current turn index.

        Returns:
            Difficulty level for the next question.
        """
        # On the first follow-up, probe one level above assessed to confirm
        if turn == 0:
            next_val = min(assessed_level.value + 1, ProficiencyLevel.EXPERT.value)
            return ProficiencyLevel(next_val)
        # On subsequent turns, stay at required level to confirm fit
        return required_level

    def _calculate_confidence(self, evidence: List[str], turns_completed: int) -> float:
        """
        Calculate a confidence score for the proficiency rating.

        More evidence and more turns → higher confidence, capped at 0.95.

        Args:
            evidence: List of evidence strings collected.
            turns_completed: Number of turns completed.

        Returns:
            Confidence float in [0.3, 0.95].
        """
        base = 0.3
        evidence_boost = min(len(evidence) * 0.1, 0.4)
        turn_boost = min(turns_completed * 0.1, 0.25)
        return min(base + evidence_boost + turn_boost, 0.95)

    def _build_proficiency_rating(
        self, rating_data: Dict[str, Any], all_evidence: List[str]
    ) -> ProficiencyRating:
        """
        Build a ProficiencyRating from raw rating data.

        Args:
            rating_data: Dict from evaluate_response().
            all_evidence: Accumulated evidence across all turns.

        Returns:
            ProficiencyRating dataclass instance.

        Raises:
            InvalidProficiencyError: If the level is invalid.
        """
        level = self._parse_level(rating_data.get("level", "INTERMEDIATE"))
        justification = rating_data.get("justification", "")
        if not justification:
            raise InvalidProficiencyError("Missing justification in proficiency rating.")

        confidence = float(rating_data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        # Deduplicate evidence
        unique_evidence = list(dict.fromkeys(all_evidence))

        return ProficiencyRating(
            level=level,
            confidence=confidence,
            justification=justification,
            evidence=unique_evidence,
        )

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    @staticmethod
    def _opening_question_prompt(skill: RequiredSkill, difficulty_label: str) -> str:
        return (
            f"You are a technical interviewer assessing a candidate's proficiency in '{skill.name}'.\n"
            f"Context from job description: {skill.context or 'N/A'}\n"
            f"Ask ONE {difficulty_label}-level question that reveals real understanding.\n"
            f"Rules:\n"
            f"- Ask only ONE question\n"
            f"- Be specific and practical (not 'what is X?')\n"
            f"- Do NOT include the answer\n"
            f"- Output only the question text, no preamble\n"
        )

    @staticmethod
    def _followup_question_prompt(
        skill: RequiredSkill, difficulty_label: str, context_summary: str
    ) -> str:
        return (
            f"You are a technical interviewer assessing '{skill.name}'.\n"
            f"Conversation so far:\n{context_summary}\n\n"
            f"Ask ONE {difficulty_label}-level follow-up question to probe deeper.\n"
            f"Rules:\n"
            f"- Build on the previous response\n"
            f"- Ask only ONE question\n"
            f"- Output only the question text, no preamble\n"
        )

    @staticmethod
    def _evaluation_prompt(skill: RequiredSkill, question: str, response: str) -> str:
        return (
            f"You are a senior technical interviewer evaluating a candidate's answer.\n\n"
            f"Skill being assessed: {skill.name}\n"
            f"Question asked: {question}\n"
            f"Candidate's answer: {response}\n\n"
            f"Evaluate the answer and return ONLY a valid JSON object with these fields:\n"
            f"- \"level\": one of NONE, BEGINNER, INTERMEDIATE, ADVANCED, EXPERT\n"
            f"- \"confidence\": float 0.0–1.0 (how confident you are in this rating)\n"
            f"- \"justification\": 1–2 sentence explanation of the rating\n"
            f"- \"evidence\": list of 1–3 specific points from the answer that support the rating\n\n"
            f"Return ONLY the JSON object, no markdown, no explanation.\n"
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_rating_response(raw: str) -> Dict[str, Any]:
        """
        Parse the LLM's JSON rating response.

        Args:
            raw: Raw LLM response string.

        Returns:
            Parsed dict with level, confidence, justification, evidence.

        Raises:
            InvalidProficiencyError: If parsing fails or required fields are missing.
        """
        # Strip markdown fences
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

        # Find JSON object boundaries
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise InvalidProficiencyError(f"No JSON object found in rating response: {cleaned[:200]}")

        json_str = cleaned[start : end + 1]
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise InvalidProficiencyError(f"Invalid JSON in rating response: {exc}") from exc

        # Validate required fields
        if "level" not in data:
            raise InvalidProficiencyError("Missing 'level' field in rating response.")
        if "justification" not in data or not data["justification"]:
            raise InvalidProficiencyError("Missing 'justification' field in rating response.")

        # Normalise level
        data["level"] = str(data["level"]).upper().strip()
        valid_levels = {lvl.name for lvl in ProficiencyLevel}
        if data["level"] not in valid_levels:
            raise InvalidProficiencyError(f"Invalid proficiency level: {data['level']}")

        # Normalise confidence
        try:
            data["confidence"] = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            data["confidence"] = 0.5

        # Normalise evidence
        if not isinstance(data.get("evidence"), list):
            data["evidence"] = []

        return data

    @staticmethod
    def _parse_level(level_str: str) -> ProficiencyLevel:
        """
        Convert a string level to ProficiencyLevel enum.

        Args:
            level_str: String like "INTERMEDIATE".

        Returns:
            ProficiencyLevel enum value.
        """
        mapping = {lvl.name: lvl for lvl in ProficiencyLevel}
        return mapping.get(level_str.upper().strip(), ProficiencyLevel.INTERMEDIATE)
