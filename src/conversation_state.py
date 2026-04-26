"""
Conversation state management for the Skill Assessment Agent.

Maintains dialogue history and context across multi-turn assessment
exchanges, providing a clean interface for the assessment engine.

Validates Requirements: 2.6, 7.6
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from src.models import Message

logger = logging.getLogger(__name__)


class ConversationState:
    """
    Manages conversation history for multi-turn skill assessments.

    Each skill assessment gets its own isolated conversation context.
    The state can be reset between skills while preserving a summary
    of previous assessments for overall context.
    """

    def __init__(self) -> None:
        """Initialise an empty conversation state."""
        self.messages: List[Message] = []
        self.current_skill: Optional[str] = None
        self.turn_count: int = 0
        self._skill_summaries: List[str] = []  # Summaries of completed skills

    # ------------------------------------------------------------------
    # Message management
    # ------------------------------------------------------------------

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            role: Either "user" or "assistant".
            content: The message text.

        Raises:
            ValueError: If role is not "user" or "assistant".
        """
        if role not in ("user", "assistant"):
            raise ValueError(f"Invalid role '{role}'. Must be 'user' or 'assistant'.")

        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now(),
            skill_context=self.current_skill,
        )
        self.messages.append(message)
        self.turn_count += 1
        logger.debug("Added %s message (turn %d, skill=%s)", role, self.turn_count, self.current_skill)

    def get_history(self) -> List[Dict[str, str]]:
        """
        Return conversation history in Gemini API-compatible format.

        The Gemini SDK expects a list of dicts with "role" and "parts" keys,
        where "role" is "user" or "model" (not "assistant").

        Returns:
            List of {"role": str, "parts": [str]} dicts.
        """
        history = []
        for msg in self.messages:
            # Gemini uses "model" instead of "assistant"
            api_role = "model" if msg.role == "assistant" else "user"
            history.append({"role": api_role, "parts": [msg.content]})
        return history

    def get_messages_raw(self) -> List[Message]:
        """
        Return the raw Message objects in insertion order.

        Returns:
            List of Message dataclass instances.
        """
        return list(self.messages)

    # ------------------------------------------------------------------
    # Skill lifecycle
    # ------------------------------------------------------------------

    def reset_for_skill(self, skill: str) -> None:
        """
        Reset conversation history for a new skill assessment.

        Saves a brief summary of the current skill before clearing,
        so the overall context is not completely lost.

        Args:
            skill: Name of the skill about to be assessed.
        """
        if self.current_skill and self.messages:
            summary = self._build_summary()
            self._skill_summaries.append(summary)
            logger.debug("Saved summary for skill '%s'", self.current_skill)

        self.messages = []
        self.turn_count = 0
        self.current_skill = skill
        logger.info("Conversation state reset for skill: %s", skill)

    def get_context_summary(self) -> str:
        """
        Return a condensed summary of the current conversation context.

        Useful for injecting prior context into new question prompts
        without sending the full history.

        Returns:
            Multi-line string summarising the conversation so far.
        """
        if not self.messages:
            return f"Starting assessment for skill: {self.current_skill or 'unknown'}"

        lines = [f"Skill being assessed: {self.current_skill or 'unknown'}"]
        lines.append(f"Turns so far: {self.turn_count}")

        # Include the last exchange for immediate context
        user_msgs = [m for m in self.messages if m.role == "user"]
        assistant_msgs = [m for m in self.messages if m.role == "assistant"]

        if user_msgs:
            last_user = user_msgs[-1].content
            lines.append(f"Last candidate response: {last_user[:200]}{'…' if len(last_user) > 200 else ''}")

        if assistant_msgs:
            last_assistant = assistant_msgs[-1].content
            lines.append(f"Last question asked: {last_assistant[:200]}{'…' if len(last_assistant) > 200 else ''}")

        return "\n".join(lines)

    def get_all_skill_summaries(self) -> List[str]:
        """
        Return summaries of all previously assessed skills.

        Returns:
            List of summary strings, one per completed skill.
        """
        return list(self._skill_summaries)

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        """True if no messages have been added yet."""
        return len(self.messages) == 0

    @property
    def message_count(self) -> int:
        """Total number of messages in the current skill conversation."""
        return len(self.messages)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_summary(self) -> str:
        """
        Build a brief summary of the current skill conversation.

        Returns:
            One-line summary string.
        """
        user_responses = [m.content for m in self.messages if m.role == "user"]
        snippet = user_responses[-1][:100] if user_responses else "(no responses)"
        return (
            f"Skill '{self.current_skill}': {len(user_responses)} response(s). "
            f"Last response snippet: {snippet}"
        )
