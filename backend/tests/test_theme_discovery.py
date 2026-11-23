import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.services.theme_discovery import discover_theme_books


def test_theme_discovery_requires_verifiable_book_and_author_evidence():
    async def check():
        topic_text = 'When Breath Becomes Air by Paul Kalanithi explores mortality and the meaning of life.'
        bio_text = 'Paul Kalanithi was an American neurosurgeon and writer.'
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(side_effect=[
            json.dumps({'english_theme': 'mortality'}),
            json.dumps({'books': [{'title': 'When Breath Becomes Air', 'author': 'Paul Kalanithi', 'reason': '探讨死亡与生命意义', 'source_id': 1, 'evidence_quote': topic_text}]}),
            json.dumps({'authors': [{'author': 'Paul Kalanithi', 'foreign': True, 'country': 'American', 'source_id': 1, 'quote': bio_text}]}),
        ])
        search = type('Search', (), {})()
        async def find(query, **kwargs):
            if 'nationality biography' in query:
                return [{'title': 'Paul Kalanithi', 'url': 'https://example.org/author', 'content': bio_text}]
            return [{'title': 'Books about mortality', 'url': 'https://example.org/books', 'content': topic_text}]
        search.search = AsyncMock(side_effect=find)
        def catalog(request):
            return httpx.Response(200, json={'docs': [{'key': '/works/OL1W', 'title': 'When Breath Becomes Air',
                'author_name': ['Paul Kalanithi'], 'isbn': ['9780812988406']}]})
        original = httpx.AsyncClient
        with patch.object(settings, 'GOODREADS_PROXY', ''), patch('app.services.theme_discovery.httpx.AsyncClient', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(catalog))):
            books = await discover_theme_books('死亡', 10, client=client, search=search)
        assert len(books) == 1
        assert books[0]['author_country'] == 'American'
        assert books[0]['evidence_excerpt'] == topic_text
        assert books[0]['author_evidence_url'] == 'https://example.org/author'
    asyncio.run(check())


def test_catalog_matching_handles_missing_subtitle_without_mixing_series():
    from app.services.theme_discovery import _catalog_title_matches, _author_matches
    assert _catalog_title_matches('The Meaning of Life and Death: Ten Classic Thinkers', 'The Meaning of Life and Death')
    assert not _catalog_title_matches('Dog Man: A Sprinkle in Time', 'Dog Man: Big Jim Begins')
    assert _author_matches('Jim B. Tucker', 'Jim B. Tucker M.D.')
    assert _author_matches('Raymond Moody', 'Raymond A. Moody')
    assert not _author_matches('Kate Atkinson', 'Raymond Moody')


def test_author_identity_does_not_infer_nationality_from_birthplace_or_other_person():
    from app.services.theme_discovery import _explicit_author_identity
    assert _explicit_author_identity('Paul Kalanithi', {'title': 'Paul Kalanithi', 'content': 'Paul Kalanithi was born in Arizona.', 'url': 'https://example.org'}) is None
    assert _explicit_author_identity('Paul Kalanithi', {'title': 'Paul Kalanithi', 'content': 'Paul Kalanithi interviewed American writer Jane Smith.', 'url': 'https://example.org'}) is None
    assert _explicit_author_identity('Paul Kalanithi', {'title': 'Paul Kalanithi', 'content': 'Paul Kalanithi was an Indian-American neurosurgeon and writer.', 'url': 'https://example.org'})['author_country'] == 'Indian-American'
    source = {'title': 'Ernest Becker', 'content': 'English Ernest Becker American cultural anthropologist (1924–1974)', 'url': 'https://example.org'}
    assert _explicit_author_identity('Ernest Becker', source)['author_country'] == 'American'


def test_unverified_quote_cannot_create_candidate():
    async def check():
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(side_effect=[
            json.dumps({'english_theme': 'mortality'}),
            json.dumps({'books': [{'title': 'When Breath Becomes Air', 'author': 'Paul Kalanithi', 'reason': 'reason', 'source_id': 1, 'evidence_quote': 'This sentence does not exist in the source.'}]}),
        ])
        search = type('Search', (), {})()
        search.search = AsyncMock(return_value=[{'title': 'Book', 'url': 'https://example.org/book', 'content': 'When Breath Becomes Air by Paul Kalanithi is a book.'}])
        assert await discover_theme_books('死亡', client=client, search=search) == []
    asyncio.run(check())


def test_missing_quote_gets_targeted_search_and_unknown_nationality_is_labelled():
    async def check():
        text = 'When Breath Becomes Air by Paul Kalanithi explores mortality and the meaning of life.'
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(side_effect=[
            json.dumps({'english_theme': 'mortality'}),
            json.dumps({'books': [{'title': 'When Breath Becomes Air', 'author': 'Paul Kalanithi', 'reason': '死亡与生命', 'source_id': 1, 'evidence_quote': 'not an actual quote'}]}),
            json.dumps({'source_id': 1, 'reason': '讨论死亡和生命意义', 'match_type': 'direct', 'evidence_quote': text}),
        ])
        search = type('Search', (), {})()
        async def find(query, **kwargs):
            if 'nationality biography' in query:
                return []
            return [{'title': 'When Breath Becomes Air', 'url': 'https://example.org/book', 'content': text}]
        search.search = AsyncMock(side_effect=find)
        def catalog(request):
            return httpx.Response(200, json={'docs': [{'key': '/works/OL1W', 'title': 'When Breath Becomes Air', 'author_name': ['Paul Kalanithi']}]})
        original = httpx.AsyncClient
        with patch.object(settings, 'GOODREADS_PROXY', ''), patch('app.services.theme_discovery.httpx.AsyncClient', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(catalog))):
            books = await discover_theme_books('死亡', client=client, search=search)
        assert len(books) == 1
        assert books[0]['evidence_excerpt'] == text
        assert books[0]['author_country'] == '待核实'
        assert books[0]['author_evidence_url'] == ''
    asyncio.run(check())


def test_theme_search_api_queues_and_checks_input():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async def test_db():
            async with sessions() as db:
                yield db
        app.dependency_overrides[get_db] = test_db
        try:
            with patch('app.api.theme_search.enqueue_theme_search', return_value='job') as enqueue, \
                    patch('app.api.theme_search._job_is_active', return_value=True):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.post('/api/theme-search/', json={'theme': '  死亡  ', 'limit': 10})
                    assert response.status_code == 200, response.text
                    value = response.json()
                    assert value['theme'] == '死亡' and value['status'] == 'queued'
                    assert (await client.get('/api/theme-search/latest')).json()['id'] == value['id']
                    assert (await client.post('/api/theme-search/', json={'theme': ' ', 'limit': 10})).status_code == 422
                    enqueue.assert_called_once_with(value['id'])
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()
    asyncio.run(check())


def test_lost_theme_search_job_becomes_retryable():
    from app.models.theme_search import ThemeSearch

    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            search = ThemeSearch(theme='爱情', limit=10, status='queued', job_id='lost-job')
            db.add(search)
            await db.commit()
            search_id = search.id

        async def test_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        try:
            with patch('app.api.theme_search._job_is_active', return_value=False):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.get(f'/api/theme-search/{search_id}')
                    assert response.status_code == 200
                    assert response.json()['status'] == 'failed'
                    assert '重新搜索' in response.json()['error_message']
            async with sessions() as db:
                assert (await db.get(ThemeSearch, search_id)).status == 'failed'
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()

    asyncio.run(check())


def test_existing_theme_search_table_gains_job_id():
    from app.core import database

    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.execute(text('CREATE TABLE theme_searches (id INTEGER PRIMARY KEY)'))
        with patch.object(database, 'engine', engine):
            await database.init_db()
        async with engine.connect() as conn:
            columns = (await conn.execute(text('PRAGMA table_info(theme_searches)'))).all()
            assert 'job_id' in {column[1] for column in columns}
        await engine.dispose()

    asyncio.run(check())


def test_theme_search_worker_persists_book_and_both_evidence_sources():
    from app.models.book import Book
    from app.models.theme_search import ThemeBookEvidence, ThemeSearch
    from app.tasks.theme_search_tasks import _run_theme_search_async

    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            search = ThemeSearch(theme='死亡', limit=10, status='queued')
            db.add(search)
            await db.commit()
            search_id = search.id
        book = {'title': 'When Breath Becomes Air', 'author': 'Paul Kalanithi', 'reason': '探讨死亡',
                'evidence_excerpt': 'A book about mortality.', 'evidence_url': 'https://example.org/book',
                'author_country': 'American', 'author_evidence_excerpt': 'An American writer.',
                'author_evidence_url': 'https://example.org/author', 'catalog_url': 'https://openlibrary.org/works/OL1W'}
        with patch('app.tasks.theme_search_tasks.engine', engine), patch('app.tasks.theme_search_tasks.discover_theme_books', new_callable=AsyncMock, return_value=[book]):
            result = await _run_theme_search_async(search_id)
        assert result['status'] == 'completed' and result['count'] == 1
        async with sessions() as db:
            stored = (await db.execute(select(Book))).scalar_one()
            evidence = await db.get(ThemeBookEvidence, stored.id)
            assert stored.description is None
            assert evidence.evidence_url == book['evidence_url']
            assert evidence.author_evidence_url == book['author_evidence_url']
        await engine.dispose()
    asyncio.run(check())
