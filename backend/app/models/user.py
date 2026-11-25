"""Local accounts, sessions, and reusable custom voices."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), nullable=False, unique=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class LoginSession(Base):
    __tablename__ = 'login_sessions'

    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)


class SavedVoice(Base):
    __tablename__ = 'saved_voices'
    __table_args__ = (UniqueConstraint('user_id', 'name', name='uq_saved_voice_user_name'),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(30), nullable=False)
    voice_id = Column(String(200), nullable=False)
    language = Column(String(2), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PronunciationRule(Base):
    __tablename__ = 'pronunciation_rules'
    __table_args__ = (UniqueConstraint('user_id', 'original', name='uq_pronunciation_user_original'),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    original = Column(String(80), nullable=False)
    spoken = Column(String(120), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
