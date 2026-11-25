"""Theme-first book discovery and supporting evidence."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class ThemeSearch(Base):
    __tablename__ = 'theme_searches'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    theme = Column(String(200), nullable=False)
    limit = Column(Integer, nullable=False, default=10)
    status = Column(String(30), nullable=False, default='queued')
    job_id = Column(String(64), nullable=True)
    current_step = Column(String(100), nullable=True)
    book_list_id = Column(Integer, ForeignKey('book_lists.id'), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)


class ThemeBookEvidence(Base):
    __tablename__ = 'theme_book_evidence'
    book_id = Column(Integer, ForeignKey('books.id'), primary_key=True)
    reasoning = Column(Text, nullable=False)
    evidence_excerpt = Column(Text, nullable=False)
    evidence_url = Column(Text, nullable=False)
    author_country = Column(String(100), nullable=False)
    author_evidence_excerpt = Column(Text, nullable=False)
    author_evidence_url = Column(Text, nullable=False)
