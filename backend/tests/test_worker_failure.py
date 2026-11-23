import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.book import Book, BookList
from app.models.research import Research
from worker import mark_failed_job


def test_rq_failure_marks_domain_task_failed():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            listing = BookList(name='Test', source_type='csv')
            db.add(listing)
            await db.flush()
            book = Book(title='Test book', book_list_id=listing.id)
            db.add(book)
            await db.flush()
            research = Research(book_id=book.id, themes=['theme'], match_mode='any', status='running')
            db.add(research)
            await db.commit()
            return research.id

    research_id = asyncio.run(setup())
    job = SimpleNamespace(func_name='app.tasks.research_tasks.run_research_task', args=(research_id,), id='job')
    with patch('worker.engine', engine):
        assert mark_failed_job(job, TimeoutError, TimeoutError(), None) is True

    async def verify():
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            research = await db.get(Research, research_id)
            assert research.status == 'failed'
            assert '超时' in research.error_message
        await engine.dispose()

    asyncio.run(verify())
