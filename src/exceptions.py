"""
Custom exception classes for the Skill Assessment Agent.

This module defines all custom exceptions used throughout the application
for proper error handling and user feedback.

Validates Requirements: 1.6, 7.4, 7.7
"""


# ============================================================================
# Input Validation Errors
# ============================================================================

class InvalidFileError(Exception):
    """Raised when input file is invalid or corrupted."""
    pass


class UnsupportedFormatError(Exception):
    """Raised when file format is not supported."""
    pass


class ValidationError(Exception):
    """Raised when input content fails validation."""
    pass


# ============================================================================
# External API Errors
# ============================================================================

class APIError(Exception):
    """Base class for API-related errors."""
    pass


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""
    
    def __init__(self, retry_after: int):
        """
        Initialize RateLimitError.
        
        Args:
            retry_after: Number of seconds to wait before retrying
        """
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class APIConnectionError(APIError):
    """Raised when API connection fails."""
    pass


# ============================================================================
# Assessment Logic Errors
# ============================================================================

class AssessmentError(Exception):
    """Base class for assessment-related errors."""
    pass


class SkillExtractionError(AssessmentError):
    """Raised when skill extraction fails."""
    pass


class InvalidProficiencyError(AssessmentError):
    """Raised when proficiency rating is invalid."""
    pass


# ============================================================================
# Resource Curation Errors
# ============================================================================

class ResourceError(Exception):
    """Base class for resource-related errors."""
    pass


class InsufficientResourcesError(ResourceError):
    """Raised when not enough resources can be found."""
    pass


class URLValidationError(ResourceError):
    """Raised when resource URL is inaccessible."""
    pass


# ============================================================================
# Output Generation Errors
# ============================================================================

class OutputError(Exception):
    """Base class for output-related errors."""
    pass


class VisualizationError(OutputError):
    """Raised when chart generation fails."""
    pass


class ExportError(OutputError):
    """Raised when export to file fails."""
    pass
