"""
Data models for the Skill Assessment Agent.

This module contains all data classes and enums used throughout the application
for type safety and data validation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict
from datetime import datetime


class ProficiencyLevel(Enum):
    """Proficiency levels for skill assessment."""
    NONE = 0
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4


class GapCategory(Enum):
    """Categorization of skill gap severity."""
    CRITICAL = "critical"  # Large gap in essential skill
    MODERATE = "moderate"  # Medium gap or non-critical skill
    MINOR = "minor"        # Small gap or nice-to-have skill
    STRENGTH = "strength"  # Candidate exceeds requirements


class ResourceFormat(Enum):
    """Learning resource formats."""
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    COURSE = "course"
    VIDEO = "video"
    BOOK = "book"
    PROJECT = "project"
    PRACTICE = "practice"


@dataclass
class ParsedDocument:
    """Parsed input document."""
    content: str
    file_path: str
    file_type: str  # "text" or "pdf"
    page_count: Optional[int] = None
    metadata: Optional[Dict[str, str]] = None


@dataclass
class RequiredSkill:
    """Skill required by job description."""
    name: str
    category: str  # e.g., "programming_language", "framework", "tool"
    context: str   # Context from job description
    priority: str  # "required" or "preferred"
    required_level: ProficiencyLevel = ProficiencyLevel.INTERMEDIATE


@dataclass
class ClaimedSkill:
    """Skill claimed in resume."""
    name: str
    experience_years: Optional[float] = None
    context: str = ""  # Context from resume


@dataclass
class Message:
    """Conversation message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    skill_context: Optional[str] = None


@dataclass
class ProficiencyRating:
    """Proficiency assessment result."""
    level: ProficiencyLevel
    confidence: float  # 0.0 to 1.0
    justification: str
    evidence: List[str] = field(default_factory=list)  # Key points from responses


@dataclass
class SkillAssessment:
    """Complete assessment for one skill."""
    skill: RequiredSkill
    proficiency: ProficiencyRating
    questions_asked: List[str]
    responses: List[str]
    duration_seconds: float
    timestamp: datetime


@dataclass
class SkillGap:
    """Identified skill gap."""
    skill: str
    required_level: ProficiencyLevel
    assessed_level: ProficiencyLevel
    gap_magnitude: int  # Numeric difference
    category: GapCategory
    priority_rank: int
    is_adjacent: bool  # Can be learned given current skills


@dataclass
class GapAnalysis:
    """Complete gap analysis results."""
    gaps: List[SkillGap]
    strengths: List[str]  # Skills where candidate exceeds requirements
    match_score: float  # 0-100
    critical_gaps: List[SkillGap]
    moderate_gaps: List[SkillGap]
    minor_gaps: List[SkillGap]


@dataclass
class LearningResource:
    """Curated learning resource."""
    title: str
    url: str
    format: ResourceFormat
    difficulty: str  # "beginner", "intermediate", "advanced"
    estimated_hours: int
    is_free: bool
    description: str
    provider: str  # e.g., "MDN", "freeCodeCamp", "Coursera"


@dataclass
class LearningStep:
    """Single step in learning plan."""
    skill: str
    current_level: ProficiencyLevel
    target_level: ProficiencyLevel
    resources: List[LearningResource]
    estimated_hours: int
    prerequisites: List[str]
    milestone_criteria: str


@dataclass
class LearningPlan:
    """Complete personalized learning plan."""
    steps: List[LearningStep]
    total_hours: int
    focus_areas: List[str]  # Adjacent skills prioritized
    prerequisites_needed: List[str]
    milestones: List[str]
    timeline_weeks: int


@dataclass
class Report:
    """Complete assessment report."""
    candidate_name: Optional[str]
    job_title: str
    assessment_date: datetime
    assessments: List[SkillAssessment]
    gap_analysis: GapAnalysis
    learning_plan: LearningPlan
    visualizations: List[str]  # Paths to chart images
    methodology_notes: str
    summary: str
