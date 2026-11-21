"""Script validation schemas."""

from pydantic import BaseModel, Field
from typing import List, Optional


class ScriptSection(BaseModel):
    """A section in the podcast script."""
    title: str
    word_count: int
    duration_minutes: float


class ScriptValidationRequest(BaseModel):
    """Request to validate a podcast script."""
    script_content: str = Field(..., description="Full podcast script text")
    speaking_rate: str = Field(
        default="normal",
        pattern="^(slow|normal|fast)$",
        description="Speaking rate: slow (120 wpm), normal (150 wpm), fast (180 wpm)"
    )


class ScriptValidationResponse(BaseModel):
    """Response from script validation."""
    total_words: int
    total_chars: int
    estimated_minutes: float
    is_sufficient: bool
    target_min_minutes: int = 20
    target_max_minutes: int = 30
    sections: List[ScriptSection]
    issues: List[str]
    recommendations: List[str]
    report: str = Field(description="Formatted markdown report")
