"""Research, Source, ThemeMatch, and MaterialAssessment models."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class MatchStatus(str, enum.Enum):
    """Theme matching status."""
    CANDIDATE = "candidate"  # Has evidence supporting the theme
    PENDING = "pending"  # Needs verification
    NO_EVIDENCE = "no_evidence"  # No evidence found


class SourceType(str, enum.Enum):
    """Type of source material."""
    PROFESSIONAL_REVIEW = "professional_review"
    READER_REVIEW = "reader_review"
    PUBLISHER_DESCRIPTION = "publisher_description"
    AUTHOR_INTERVIEW = "author_interview"
    NEWS_ARTICLE = "news_article"
    ENCYCLOPEDIA = "encyclopedia"
    OTHER = "other"
    IRRELEVANT = "irrelevant"


class SufficiencyLevel(str, enum.Enum):
    """Material sufficiency assessment."""
    RECOMMENDED = "recommended"  # Good theme match and sufficient materials
    INSUFFICIENT = "insufficient"  # Theme may match but materials lacking
    NEEDS_REVIEW = "needs_review"  # Uncertainty in book identity or theme
    NO_THEME_EVIDENCE = "no_theme_evidence"  # No theme evidence found


class Research(Base):
    """A research session for a book on specific themes."""

    __tablename__ = "researches"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)

    # Input
    themes = Column(JSON, nullable=False)  # List of themes to research
    match_mode = Column(String(20), default="any")  # "any" or "all"

    # Status
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    current_step = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    # Results
    overall_assessment = Column(SQLEnum(SufficiencyLevel), nullable=True)
    assessment_reasoning = Column(Text, nullable=True)
    material_gaps = Column(JSON, nullable=True)  # List of missing information

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    book = relationship("Book", back_populates="researches")
    theme_matches = relationship("ThemeMatch", back_populates="research", cascade="all, delete-orphan")
    sources = relationship("Source", back_populates="research", cascade="all, delete-orphan")
    material_assessment = relationship("MaterialAssessment", back_populates="research", uselist=False, cascade="all, delete-orphan")


class ThemeMatch(Base):
    """Theme matching result for a specific theme."""

    __tablename__ = "theme_matches"

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("researches.id"), nullable=False)

    theme = Column(String(200), nullable=False)
    status = Column(SQLEnum(MatchStatus), nullable=False)
    reasoning = Column(Text, nullable=False)
    supporting_sources = Column(JSON, nullable=True)  # List of source IDs
    evidence_quotes = Column(JSON, nullable=True)  # Key quotes supporting the match

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    research = relationship("Research", back_populates="theme_matches")
    details = relationship("ThemeMatchDetails", uselist=False, cascade="all, delete-orphan")


class ThemeMatchDetails(Base):
    """Search context and alternative themes for a theme screening."""
    __tablename__ = "theme_match_details"
    theme_match_id = Column(Integer, ForeignKey("theme_matches.id"), primary_key=True)
    suggested_themes = Column(JSON, nullable=False, default=list)
    search_sources = Column(JSON, nullable=False, default=list)


class Source(Base):
    """A source material found during research."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("researches.id"), nullable=False)

    # Source information
    title = Column(String(500), nullable=False)
    url = Column(Text, nullable=False)
    source_type = Column(SQLEnum(SourceType), nullable=False)
    source_classification_reasoning = Column(Text, nullable=True)

    # Content
    raw_content = Column(Text, nullable=True)  # Original fetched content
    cleaned_content = Column(Text, nullable=True)  # After cleaning
    summary = Column(Text, nullable=True)  # LLM-generated summary
    key_points = Column(JSON, nullable=True)  # List of key points

    # Metadata
    fetch_status = Column(String(50), default="pending")  # pending, fetched, failed, inaccessible
    fetch_error = Column(Text, nullable=True)
    fetched_at = Column(DateTime, nullable=True)
    is_duplicate = Column(Integer, default=0)  # Boolean: is this a duplicate of another source?
    duplicate_of = Column(Integer, ForeignKey("sources.id"), nullable=True)  # Original source ID

    # Relevance
    relevance_score = Column(Float, nullable=True)  # 0.0 to 1.0
    is_about_target_book = Column(Integer, default=1)  # Boolean: confirms this is about the target book
    book_identity_reasoning = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    research = relationship("Research", back_populates="sources")


class MaterialAssessment(Base):
    """Overall material sufficiency assessment."""

    __tablename__ = "material_assessments"

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("researches.id"), nullable=False, unique=True)

    # Book identity verification
    book_identity_confirmed = Column(Integer, default=0)  # Boolean
    book_identity_notes = Column(Text, nullable=True)

    # Content availability
    has_plot_summary = Column(Integer, default=0)  # Boolean
    has_independent_reviews = Column(Integer, default=0)  # Boolean
    has_author_background = Column(Integer, default=0)  # Boolean
    has_multiple_perspectives = Column(Integer, default=0)  # Boolean

    # Counts
    professional_review_count = Column(Integer, default=0)
    independent_review_count = Column(Integer, default=0)
    total_unique_sources = Column(Integer, default=0)

    # Quality indicators
    source_diversity_score = Column(Float, nullable=True)  # 0.0 to 1.0
    content_depth_score = Column(Float, nullable=True)  # 0.0 to 1.0

    # Gaps and recommendations
    identified_gaps = Column(JSON, nullable=True)  # List of missing elements
    suggested_searches = Column(JSON, nullable=True)  # Suggested follow-up searches

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    research = relationship("Research", back_populates="material_assessment")


class ReviewDigest(Base):
    """Cached source-linked review summaries for a research."""
    __tablename__ = "review_digests"
    research_id = Column(Integer, ForeignKey("researches.id"), primary_key=True)
    reviews = Column(JSON, nullable=False)


class ReviewArticle(Base):
    """A source-linked synthesis of reviews for one research."""
    __tablename__ = "review_articles"
    research_id = Column(Integer, ForeignKey("researches.id"), primary_key=True)
    article = Column(JSON, nullable=False)
