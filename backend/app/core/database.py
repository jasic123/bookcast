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
    connect_args={"timeout": 30} if settings.DATABASE_URL.startswith("sqlite") else {},
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
    import app.models  # Register every model before create_all.
    if engine.dialect.name == 'sqlite':
        async with engine.connect() as conn:
            await conn.execute(text('PRAGMA journal_mode=WAL'))
            await conn.execute(text('PRAGMA synchronous=NORMAL'))
            await conn.commit()
    async with engine.begin() as conn:
        if engine.dialect.name == 'sqlite':
            for table in ('book_lists', 'theme_searches'):
                columns = (await conn.execute(text(f'PRAGMA table_info({table})'))).all()
                if columns and 'user_id' not in {column[1] for column in columns}:
                    await conn.execute(text(f'ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)'))
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == 'sqlite':
            research_columns = (await conn.execute(text('PRAGMA table_info(researches)'))).all()
            if research_columns and 'job_id' not in {column[1] for column in research_columns}:
                await conn.execute(text('ALTER TABLE researches ADD COLUMN job_id VARCHAR(64)'))
            columns = (await conn.execute(text('PRAGMA table_info(podcast_runs)'))).all()
            existing = {column[1] for column in columns}
            for name, kind in {'audio_status': 'VARCHAR(30)', 'audio_step': 'VARCHAR(100)',
                               'audio_error': 'TEXT', 'audio_voices': 'JSON',
                               'audio_file': 'VARCHAR(150)'}.items():
                if name not in existing:
                    await conn.execute(text(f'ALTER TABLE podcast_runs ADD COLUMN {name} {kind}'))
            theme_columns = (await conn.execute(text('PRAGMA table_info(theme_searches)'))).all()
            if 'job_id' not in {column[1] for column in theme_columns}:
                await conn.execute(text('ALTER TABLE theme_searches ADD COLUMN job_id VARCHAR(64)'))
