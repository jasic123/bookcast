import asyncio
from unittest.mock import patch

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.book import Book, BookList
from app.models.research import Research
from app.models.podcast_run import PodcastRun


def test_duplicate_podcast_creation_returns_existing_run():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
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
            research = Research(book_id=book.id, themes=['theme'], match_mode='any', status='completed')
            db.add(research)
            await db.commit()
            research_id = research.id

        async def test_db():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_db
        try:
            with patch('app.api.podcasts.enqueue_podcast') as enqueue:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    first = await client.post('/api/podcasts/', json={'research_id': research_id, 'speaker_count': 2})
                    second = await client.post('/api/podcasts/', json={'research_id': research_id, 'speaker_count': 2})
                assert first.status_code == 200
                assert second.status_code == 409
                assert second.json()['detail']['run_id'] == first.json()['id']
                enqueue.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()

    asyncio.run(check())


def test_panel_audio_requires_each_selected_voice():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
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
            research = Research(book_id=book.id, themes=['theme'], match_mode='any', status='completed')
            db.add(research)
            await db.flush()
            run = PodcastRun(research_id=research.id, status='completed',
                             request={'speaker_count': 3},
                             result={'drafts': [{'content': '主持人：开场。\n嘉宾1：第一点。\n嘉宾2：第二点。'}],
                                     'reviews': [{'approved': True}]})
            db.add(run)
            await db.commit()
            run_id = run.id

        async def test_db():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_db
        try:
            with patch('app.api.podcasts.enqueue_podcast_audio') as enqueue:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    invalid = await client.post(f'/api/podcasts/{run_id}/audio',
                                                json={'voices': {'主持人': 'host', '嘉宾1': 'one'}})
                    assert invalid.status_code == 400
                    valid = await client.post(f'/api/podcasts/{run_id}/audio',
                                              json={'voices': {'主持人': 'host', '嘉宾1': 'one', '嘉宾2': 'two'}})
                    assert valid.status_code == 200, valid.text
                    assert valid.json()['audio_voices'] == {'主持人': 'host', '嘉宾1': 'one', '嘉宾2': 'two'}
                    enqueue.assert_called_once_with(run_id)
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()

    asyncio.run(check())


def test_failed_podcast_retry_keeps_checkpoint():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
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
            research = Research(book_id=book.id, themes=['theme'], match_mode='any', status='completed')
            db.add(research)
            await db.flush()
            run = PodcastRun(research_id=research.id, status='failed', request={'speaker_count': 1},
                             result={'plan': {'premise': 'Saved'}, 'checkpoint_stage': 'planned'},
                             error_message='Temporary failure')
            db.add(run)
            await db.commit()
            run_id = run.id

        async def test_db():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_db
        try:
            with patch('app.api.podcasts.enqueue_podcast') as enqueue:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.post(f'/api/podcasts/{run_id}/retry')
                    assert response.status_code == 200, response.text
                    assert response.json()['status'] == 'queued'
                    assert response.json()['result']['checkpoint_stage'] == 'planned'
                    assert (await client.post(f'/api/podcasts/{run_id}/retry')).status_code == 409
                    enqueue.assert_called_once_with(run_id)
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()

    asyncio.run(check())
