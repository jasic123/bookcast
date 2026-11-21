import asyncio
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.book import Book, BookList
from app.models.research import Research
from app.services.research_orchestrator import ResearchOrchestrator
from app.services.theme_screener import ThemeScreenerService


def test_screening_searches_and_persists_details():
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
            await db.flush()
            research = Research(book_id=book.id, themes=['死亡'], match_mode='any', status='queued')
            db.add(research)
            await db.commit()
            research_id = research.id
            screening = ThemeScreenerService()
            screening.search_client.search = AsyncMock(return_value=[{'title': 'Review', 'url': 'https://example.org/review', 'content': 'A family story'}])
            screening.llm_client.analyze_theme_match = AsyncMock(return_value={'status': 'no_evidence', 'reasoning': '资料没有提及死亡。', 'suggested_themes': ['家庭']})
            orchestrator = ResearchOrchestrator(db)
            orchestrator.theme_screener = screening
            result = await orchestrator.conduct_research(research_id)
            assert result['assessment'] == 'no_theme_evidence'
            assert '死亡' in screening.search_client.search.await_args.args[0]
        async def test_db():
            async with sessions() as db:
                yield db
        app.dependency_overrides[get_db] = test_db
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                response = await client.get(f'/api/research/{research_id}')
                assert response.status_code == 200, response.text
                match = response.json()['theme_matches'][0]
                assert match['reasoning'] == '资料没有提及死亡。'
                assert match['details']['suggested_themes'] == ['家庭']
                assert match['details']['search_sources'][0]['url'] == 'https://example.org/review'
            screening.search_client.search = AsyncMock(side_effect=RuntimeError('unavailable'))
            result = await screening.screen_book_for_themes('Test book', None, None, ['死亡'])
            assert result[0]['status'] == 'pending'
            assert '搜索失败' in result[0]['reasoning']
            assert result[0]['suggested_themes'] == []
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()
    asyncio.run(check())


def test_candidate_reaches_material_assessment():
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
            await db.flush()
            research = Research(book_id=book.id, themes=['war'], match_mode='any', status='queued')
            db.add(research)
            await db.commit()
            orchestrator = ResearchOrchestrator(db)
            orchestrator.theme_screener.screen_book_for_themes = AsyncMock(return_value=[{'theme': 'war', 'status': 'candidate', 'reasoning': 'Evidence', 'suggested_themes': [], 'search_sources': []}])
            orchestrator.material_searcher.search_materials = AsyncMock(return_value=[])
            orchestrator.llm_client.assess_material_sufficiency = AsyncMock(return_value={'overall_assessment': 'insufficient', 'reasoning': 'No sources'})
            result = await orchestrator.conduct_research(research.id)
            assert result['status'] == 'completed', result
            assert result['assessment'] == 'insufficient'
            assert orchestrator.llm_client.assess_material_sufficiency.await_args.kwargs['theme_matches'][0]['theme'] == 'war'
        await engine.dispose()
    asyncio.run(check())


def test_review_digest_preserves_source_basis_and_caches():
    async def check():
        from app.models.research import Source, SourceType
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
            research = Research(book_id=book.id, themes=['test'], match_mode='any', status='completed')
            db.add(research)
            await db.flush()
            db.add(Source(research_id=research.id, title='Book review', url='https://example.org', source_type=SourceType.READER_REVIEW, fetch_status='failed', cleaned_content='Review excerpt', is_duplicate=0, is_about_target_book=1))
            await db.commit()
            research_id = research.id
        async def test_db():
            async with sessions() as session:
                yield session
        app.dependency_overrides[get_db] = test_db
        try:
            with patch('app.services.llm_client.LLMClient.chat_completion', new_callable=AsyncMock, return_value='{"summary":"观点摘要", "points":["优点"]}') as model:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.get(f'/api/research/{research_id}/reviews')
                    assert response.status_code == 200, response.text
                    assert response.json()['reviews'][0]['basis'] == 'search_snippet'
                    assert response.json()['reviews'][0]['url'] == 'https://example.org'
                    response = await client.get(f'/api/research/{research_id}/reviews')
                    assert response.status_code == 200
                    assert model.await_count == 1
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()
    asyncio.run(check())


def test_review_article_requires_valid_sources_and_caches():
    async def check():
        from app.models.research import ReviewDigest
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
            research = Research(book_id=book.id, themes=['test'], match_mode='any', status='completed')
            db.add(research)
            await db.flush()
            db.add(ReviewDigest(research_id=research.id, reviews=[{'source_id': 7, 'title': 'Review', 'url': 'https://example.org', 'basis': 'search_snippet', 'summary': 'Summary', 'points': []}]))
            await db.commit()
            research_id = research.id
        async def test_db():
            async with sessions() as session:
                yield session
        app.dependency_overrides[get_db] = test_db
        try:
            invalid = '{"title":"Test","paragraphs":[{"text":"Example", "source_ids":[999]}]}'
            valid = '{\"title\":\"Test\",\"paragraphs\":[' + ','.join(['{\"text\":\"' + ('Example analysis ' * 20) + '\",\"source_ids\":[7]}'] * 2) + ']}'
            with patch('app.services.llm_client.LLMClient.chat_completion', new_callable=AsyncMock, side_effect=[invalid, valid, valid, valid, valid]) as model:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.post(f'/api/research/{research_id}/review-article')
                    assert response.status_code == 200, response.text
                    assert response.json()['paragraphs'][0]['source_ids'] == [7]
                    assert response.json()['sources'][0]['basis'] == 'search_snippet'
                    response = await client.post(f'/api/research/{research_id}/review-article')
                    assert response.status_code == 200
                    assert model.await_count == 5
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()
    asyncio.run(check())
