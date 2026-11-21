import asyncio
from unittest.mock import patch

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.schemas.book import BookCreate


def test_book_list_endpoints():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        async def test_db():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_db
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                response = await client.post('/api/books/lists/csv', json={'list_name': 'CSV', 'csv_content': 'title,author\nExample,Writer\n'})
                assert response.status_code == 200, response.text
                assert response.json()['books'][0]['title'] == 'Example'
                with patch('app.services.book_fetcher.BookFetcherService.fetch_amazon_list', return_value=([BookCreate(title='Amazon book')], 'https://amazon.com/', None, None)):
                    response = await client.post('/api/books/lists/amazon', json={'list_name': 'Amazon'})
                assert response.status_code == 200, response.text
                list_id = response.json()['id']
                assert response.json()['books'][0]['title'] == 'Amazon book'
                response = await client.get('/api/books/lists')
                assert response.status_code == 200, response.text
                assert len(response.json()) == 2
                assert all(len(item['books']) == 1 for item in response.json())
                response = await client.get(f'/api/books/lists/{list_id}')
                assert response.status_code == 200, response.text
                assert response.json()['books'][0]['title'] == 'Amazon book'
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()

    asyncio.run(check())
