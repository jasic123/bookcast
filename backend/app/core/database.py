"""Database configuration and session management."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database - create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == 'sqlite':
            columns = (await conn.execute(text('PRAGMA table_info(podcast_runs)'))).all()
            existing = {column[1] for column in columns}
            for name, kind in {'audio_status': 'VARCHAR(30)', 'audio_step': 'VARCHAR(100)',
                               'audio_error': 'TEXT', 'audio_voices': 'JSON'}.items():
                if name not in existing:
                    await conn.execute(text(f'ALTER TABLE podcast_runs ADD COLUMN {name} {kind}'))
