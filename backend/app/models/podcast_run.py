"""Persist a podcast-production run and its review history."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class PodcastRun(Base):
    __tablename__ = "podcast_runs"

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("researches.id"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="queued")
    current_step = Column(String(100), nullable=True)
    request = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    audio_status = Column(String(30), nullable=True)
    audio_step = Column(String(100), nullable=True)
    audio_error = Column(Text, nullable=True)
    audio_voices = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
