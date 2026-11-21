import asyncio
from unittest.mock import AsyncMock, patch

import httpx
from redis.exceptions import ConnectionError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.book import Book, BookList
from app.models.research import Research
from app.tasks.research_tasks import _run_research_async


def test_research_creation_and_worker():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            book_list = BookList(name='Test', source_type='csv')
            db.add(book_list)
            await db.flush()
            book = Book(title='Test book', book_list_id=book_list.id)
            db.add(book)
            await db.commit()
            book_id = book.id

        async def test_db():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_db
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                with patch('app.api.research.enqueue_research', return_value='job-1'):
                    response = await client.post('/api/research/', json={'book_id': book_id, 'themes': ['test']})
                assert response.status_code == 200, response.text
                research_id = response.json()['research_id']
                response = await client.get(f'/api/research/book/{book_id}')
                assert response.status_code == 200, response.text
                assert response.json()[0]['theme_matches'] == []
                with patch('app.api.research.enqueue_research', side_effect=ConnectionError('offline')):
                    response = await client.post('/api/research/', json={'book_id': book_id, 'themes': ['test']})
                assert response.status_code == 503, response.text
                async with sessions() as db:
                    assert (await db.get(Research, research_id + 1)).status == 'failed'
                with patch('app.tasks.research_tasks.engine', engine), patch('app.tasks.research_tasks.ResearchOrchestrator') as orchestrator:
                    orchestrator.return_value.conduct_research = AsyncMock(return_value={'status': 'completed'})
                    result = await _run_research_async(research_id)
                    assert result['status'] == 'completed'
                    orchestrator.return_value.conduct_research.assert_awaited_once_with(research_id)
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()

    asyncio.run(check())
