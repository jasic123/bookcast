"""Research-related schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.research import MatchStatus, SourceType, SufficiencyLevel


class ResearchCreate(BaseModel):
    """Schema for creating a research session."""
    book_id: int
    themes: List[str] = Field(default_factory=list, description="Optional themes; empty means research the whole book")
    match_mode: str = Field(default="any", pattern="^(any|all)$")


class ThemeSearchSource(BaseModel):
    title: str
    url: str


class ThemeMatchDetailsResponse(BaseModel):
    suggested_themes: List[str] = Field(default_factory=list)
    search_sources: List[ThemeSearchSource] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class ThemeMatchResponse(BaseModel):
    """Schema for theme match response."""
    id: int
    theme: str
    status: MatchStatus
    reasoning: str
    supporting_sources: Optional[List[int]] = None
    evidence_quotes: Optional[List[str]] = None
    details: Optional[ThemeMatchDetailsResponse] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceResponse(BaseModel):
    """Schema for source response."""
    id: int
    title: str
    url: str
    source_type: SourceType
    source_classification_reasoning: Optional[str] = None
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None
    fetch_status: str
    fetch_error: Optional[str] = None
    is_duplicate: bool
    duplicate_of: Optional[int] = None
    relevance_score: Optional[float] = None
    is_about_target_book: Optional[bool] = None
    book_identity_reasoning: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MaterialAssessmentResponse(BaseModel):
    """Schema for material assessment response."""
    id: int
    book_identity_confirmed: bool
    book_identity_notes: Optional[str] = None
    has_plot_summary: bool
    has_independent_reviews: bool
    has_author_background: bool
    has_multiple_perspectives: bool
    professional_review_count: int
    independent_review_count: int
    total_unique_sources: int
    source_diversity_score: Optional[float] = None
    content_depth_score: Optional[float] = None
    identified_gaps: Optional[List[str]] = None
    suggested_searches: Optional[List[str]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResearchResponse(BaseModel):
    """Schema for research response."""
    id: int
    book_id: int
    themes: List[str]
    match_mode: str
    status: str
    progress: float
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    overall_assessment: Optional[SufficiencyLevel] = None
    assessment_reasoning: Optional[str] = None
    material_gaps: Optional[List[str]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    # Nested relationships
    theme_matches: List[ThemeMatchResponse] = Field(default_factory=list)
    sources: List[SourceResponse] = Field(default_factory=list)
    material_assessment: Optional[MaterialAssessmentResponse] = None

    model_config = {"from_attributes": True}


class ResearchProgressUpdate(BaseModel):
    """WebSocket progress update."""
    research_id: int
    status: str
    progress: float
    current_step: Optional[str] = None
    message: Optional[str] = None
