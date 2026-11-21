"""Podcast script model."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class PodcastScript(Base):
    """Generated podcast script for a research."""

    __tablename__ = "podcast_scripts"

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("researches.id"), nullable=False)

    # Generation parameters
    language = Column(String(10), nullable=False)  # zh, en
    style = Column(String(50), default="conversational")  # conversational, formal, casual
    target_duration = Column(Integer, default=25)  # Target minutes

    # Content
    content = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=False)
    estimated_minutes = Column(Float, nullable=False)
    is_sufficient = Column(Integer, default=1)  # Boolean: meets duration target

    # Validation
    validation_issues = Column(JSON, nullable=True)  # List of issues found

    # Timestamps
    generated_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)

    # Relationships
    research = relationship("Research", backref="scripts")
