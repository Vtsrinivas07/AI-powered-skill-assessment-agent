"""
Google Gemini API client wrapper for the Skill Assessment Agent.

Uses the new `google-genai` SDK (replaces deprecated `google-generativeai`).
Handles API initialisation, retry logic with exponential backoff, and
structured error handling for rate limits and connection failures.

Validates Requirements: 7.2, 7.7, 8.6
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types as genai_types

from config import Config
from src.exceptions import APIConnectionError, APIError, RateLimitError

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Wrapper around the Google Gemini API (google-genai SDK).

    Provides a clean interface for making LLM calls with built-in retry
    logic, exponential backoff, and structured error handling.
    """

    # gemini-2.5-flash is the user's preferred high-performance model
    DEFAULT_MODEL = "gemini-2.5-flash"

    # Reduced delay (4s) to stay within 15 RPM limit (60s / 4s = 15 RPM)
    _INTER_CALL_DELAY = 4.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = 10,
    ) -> None:
        """
        Initialize the Gemini API client.

        Args:
            api_key: Gemini API key. Reads from environment if not provided.
            model_name: Gemini model to use.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
        """
        self.api_key = api_key or Config.get_gemini_api_key()
        self.model_name = model_name
        self.timeout = timeout or Config.get_api_timeout()
        self.max_retries = max_retries if max_retries is not None else Config.get_max_retries()
        self._last_call_time: float = 0.0
        self.mock_mode = os.getenv("MOCK_LLM", "").lower() == "true"

        # Initialise the new SDK client (only if not in mock mode)
        if not self.mock_mode:
            self._client = genai.Client(api_key=self.api_key)
            logger.info("GeminiClient initialised with model=%s", self.model_name)
        else:
            self._client = None
            logger.info("GeminiClient initialised in MOCK MODE")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_text(self, prompt: str, temperature: float = 0.3) -> str:
        """
        Generate text from a single prompt.

        Args:
            prompt: The prompt to send to the model.
            temperature: Sampling temperature (0 = deterministic, 1 = creative).

        Returns:
            Generated text string.

        Raises:
            RateLimitError: If the API rate limit is exceeded after all retries.
            APIConnectionError: If the API cannot be reached after all retries.
            APIError: For other unrecoverable API errors.
        """
        if self.mock_mode:
            return self._get_mock_response(prompt)

        config = genai_types.GenerateContentConfig(temperature=temperature)

        def _call() -> str:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            return self._extract_text(response)

        return self._call_with_retry(_call)

    def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
    ) -> str:
        """
        Generate a response given a conversation history.

        Args:
            messages: List of {"role": "user"|"model", "parts": [text]} dicts.
            temperature: Sampling temperature.

        Returns:
            Generated text string.

        Raises:
            RateLimitError: If the API rate limit is exceeded after all retries.
            APIConnectionError: If the API cannot be reached after all retries.
            APIError: For other unrecoverable API errors.
        """
        if self.mock_mode:
            # For simplicity in mock mode, just use the last message content
            text = messages[-1].get("parts", [""])[0] if messages else ""
            return self._get_mock_response(text)

        config = genai_types.GenerateContentConfig(temperature=temperature)

        # Build contents list from history
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            parts = msg.get("parts", [""])
            text = parts[0] if parts else ""
            contents.append(genai_types.Content(role=role, parts=[genai_types.Part(text=text)]))

        def _call() -> str:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )
            return self._extract_text(response)

        return self._call_with_retry(_call)

    # ------------------------------------------------------------------
    # Mocking Logic
    # ------------------------------------------------------------------

    def _get_mock_response(self, prompt: str) -> str:
        """Return a plausible mock response based on prompt keywords."""
        prompt_lower = prompt.lower()
        
        # 1. Skill Evaluation (Very specific to avoid collisions)
        if "evaluate the answer" in prompt_lower or "proficiency rating" in prompt_lower:
            if "python" in prompt_lower:
                return json.dumps({
                    "level": "ADVANCED",
                    "confidence": 0.95,
                    "justification": "Candidate showed deep knowledge of Python internals and best practices.",
                    "evidence": ["Expertly explained GIL and asyncio", "Mentioned decorators and context managers"]
                })
            return json.dumps({
                "level": "INTERMEDIATE",
                "confidence": 0.85,
                "justification": "Candidate demonstrated a clear understanding of the core concepts and provided practical examples.",
                "evidence": ["Correctly described architectural patterns", "Showed familiarity with common libraries"]
            })

        # 2. Skill Extraction (Job)
        if "extract all skills mentioned in the job description" in prompt_lower:
            return json.dumps([
                {"name": "Python", "priority": "required", "context": "Experience with Python 3.10+", "required_level": "advanced"},
                {"name": "FastAPI", "priority": "required", "context": "Building REST APIs with FastAPI", "required_level": "intermediate"},
                {"name": "PostgreSQL", "priority": "required", "context": "Working with SQL databases", "required_level": "advanced"}
            ])

        # 3. Skill Extraction (Resume)
        if "extract all skills mentioned in the resume" in prompt_lower:
            return json.dumps([
                {"name": "Python", "experience_years": 3.0, "context": "Python developer for 3 years"},
                {"name": "SQL", "experience_years": 2.0, "context": "Used SQL in various projects"}
            ])

        # 4. Assessment Question
        if "ask one" in prompt_lower and "question" in prompt_lower:
            if "python" in prompt_lower:
                return "Can you explain the difference between a list and a tuple in Python, and when you would use one over the other?"
            if "fastapi" in prompt_lower:
                return "How do you handle dependency injection in FastAPI, and why is it useful?"
            return "Could you describe a complex technical challenge you faced and how you solved it?"

        # 5. Resource Curation / Learning Plan
        if "learning plan" in prompt_lower or "resources" in prompt_lower:
            return json.dumps([
                {
                    "title": "FastAPI Masterclass",
                    "url": "https://example.com/fastapi",
                    "format": "course",
                    "difficulty": "intermediate",
                    "estimated_hours": 8,
                    "is_free": True,
                    "description": "Learn FastAPI from scratch.",
                    "provider": "Udemy"
                }
            ])

        return "This is a mock response from the Skill Assessment Agent."

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_with_retry(self, func: Any) -> str:
        """
        Execute a callable with exponential backoff retry logic.

        Args:
            func: Zero-argument callable that performs the API call.

        Returns:
            Result of func().

        Raises:
            RateLimitError: After exhausting retries due to rate limiting.
            APIConnectionError: After exhausting retries due to connection issues.
            APIError: For non-retryable API errors.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                # Throttle calls to stay within RPM limits
                elapsed = time.time() - self._last_call_time
                if elapsed < self._INTER_CALL_DELAY:
                    time.sleep(self._INTER_CALL_DELAY - elapsed)

                logger.debug("API call attempt %d/%d", attempt + 1, self.max_retries + 1)
                result = func()
                self._last_call_time = time.time()
                if attempt > 0:
                    logger.info("API call succeeded on attempt %d", attempt + 1)
                return result

            except Exception as exc:
                last_exception = exc
                error_str = str(exc).lower()

                # Detect rate-limit signals
                if any(kw in error_str for kw in ("429", "quota", "rate limit", "resource_exhausted")):
                    retry_after = self._parse_retry_after(str(exc))
                    if attempt < self.max_retries:
                        # Use a smarter backoff: max of API suggestion and our exponential wait
                        wait = max(retry_after, min(2 ** (attempt + 2), 65))
                        logger.warning(
                            "Rate limit hit (attempt %d). Retrying in %ds...", attempt + 1, wait
                        )
                        time.sleep(wait)
                        continue
                    raise RateLimitError(min(retry_after, 65)) from exc

                # Detect connection / transient errors
                if any(kw in error_str for kw in ("connection", "timeout", "unavailable", "503", "502", "getaddrinfo", "gaierror")):
                    if attempt < self.max_retries:
                        wait = 2 ** attempt
                        logger.warning(
                            "Connection error (attempt %d). Retrying in %ds…", attempt + 1, wait
                        )
                        time.sleep(wait)
                        continue
                    raise APIConnectionError(f"API connection failed: {exc}") from exc

                # Non-retryable error — raise immediately
                logger.error("Non-retryable API error: %s", exc)
                raise APIError(f"Gemini API error: {exc}") from exc

        # Should not reach here, but satisfy type checker
        raise APIError(f"API call failed after {self.max_retries + 1} attempts: {last_exception}")

    @staticmethod
    def _extract_text(response: Any) -> str:
        """
        Safely extract text from a Gemini API response.

        Args:
            response: Raw response object from the Gemini SDK.

        Returns:
            Extracted text string.

        Raises:
            APIError: If the response contains no usable text.
        """
        try:
            # New SDK: response.text is a direct property
            text = response.text
            if not text or not text.strip():
                raise APIError("Gemini returned an empty response.")
            logger.debug("Received response (%d chars)", len(text))
            return text.strip()
        except AttributeError:
            # Fallback: try candidates path
            try:
                text = response.candidates[0].content.parts[0].text
                if not text or not text.strip():
                    raise APIError("Gemini returned an empty response.")
                return text.strip()
            except Exception as exc:
                raise APIError(f"Failed to extract text from response: {exc}") from exc
        except Exception as exc:
            raise APIError(f"Failed to extract text from response: {exc}") from exc

    @staticmethod
    def _parse_retry_after(error_message: str) -> int:
        """
        Parse a retry-after delay from an error message.

        Falls back to 60 seconds if no value can be parsed.

        Args:
            error_message: Raw error message string.

        Returns:
            Number of seconds to wait before retrying.
        """
        import re
        match = re.search(r"retry.{0,20}?(\d+)\s*s", error_message, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 60
