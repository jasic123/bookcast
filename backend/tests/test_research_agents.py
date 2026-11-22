import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.book import Book, BookList
from app.models.research import Research, Source, SourceType
from app.services.research_orchestrator import ResearchOrchestrator


def test_agent_workflow_preserves_catalog_and_gutenberg_excerpts():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            listing = BookList(name='test', source_type='csv')
            db.add(listing)
            await db.flush()
            book = Book(book_list_id=listing.id, title='Pride and Prejudice', author='Jane Austen')
            db.add(book)
            await db.flush()
            research = Research(book_id=book.id, themes=['marriage'], status='queued')
            db.add(research)
            await db.commit()
            orchestrator = ResearchOrchestrator(db)
            orchestrator.theme_screener.screen_book_for_themes = AsyncMock(return_value=[{'theme': 'marriage', 'status': 'candidate', 'reasoning': 'evidence'}])
            orchestrator.material_searcher.search_materials = AsyncMock(return_value=[])
            orchestrator.llm_client.assess_material_sufficiency = AsyncMock(return_value={'overall_assessment': 'insufficient', 'reasoning': 'limited'})
            catalog = {'title': 'Open Library 图书资料：Pride and Prejudice', 'url': 'https://openlibrary.org/works/OL66554W', 'content': 'Book information', 'description': 'Description', 'gutenberg_ids': [1342]}
            excerpts = {'title': 'Project Gutenberg 原文节选：Pride and Prejudice', 'url': 'https://www.gutenberg.org/ebooks/1342', 'content': '[正文节选] Elizabeth and Darcy', 'total_chars': 728264, 'excerpt_count': 3}
            with patch('app.services.research_orchestrator.open_library_book', new_callable=AsyncMock, return_value=catalog), patch('app.services.research_orchestrator.gutenberg_excerpts', new_callable=AsyncMock, return_value=excerpts) as get_text, patch('app.services.research_orchestrator.search_goodreads_reviews', new_callable=AsyncMock, return_value=[]):
                result = await orchestrator.conduct_research(research.id)
            assert result['status'] == 'completed', result
            get_text.assert_awaited_once_with('Pride and Prejudice', [1342])
            sources = (await db.execute(select(Source).order_by(Source.id))).scalars().all()
            assert [s.source_type for s in sources] == [SourceType.ENCYCLOPEDIA, SourceType.OTHER]
            assert sources[1].cleaned_content == excerpts['content']
            assert '并非全文' in sources[1].summary
            assert orchestrator.theme_screener.screen_book_for_themes.await_args.kwargs['book_description'] == 'Description'
        await engine.dispose()
    asyncio.run(check())


def test_article_agent_can_cite_original_excerpt_without_reader_reviews():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            listing = BookList(name='test', source_type='csv')
            db.add(listing)
            await db.flush()
            book = Book(book_list_id=listing.id, title='Pride and Prejudice', author='Jane Austen')
            db.add(book)
            await db.flush()
            research = Research(book_id=book.id, themes=['marriage'], status='completed')
            db.add(research)
            await db.flush()
            source = Source(research_id=research.id, title='Project Gutenberg 原文节选：Pride and Prejudice',
                            url='https://www.gutenberg.org/ebooks/1342', source_type=SourceType.OTHER,
                            is_duplicate=0, is_about_target_book=1, fetch_status='fetched',
                            cleaned_content='Elizabeth and Darcy', summary='正文节选，并非全文')
            db.add(source)
            await db.commit()
            research_id, source_id = research.id, source.id

        async def test_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        try:
            response_body = json.dumps({'paragraphs': [{'text': '来源中的原文节选可以支持这一观察。' * 8, 'source_ids': [source_id]}]}, ensure_ascii=False)
            with patch('app.api.research.curate_review_sources', new_callable=AsyncMock, side_effect=lambda client, book, sources: (sources, {'findings': [], 'gaps': []}, [])), patch('app.api.research.LLMClient.chat_completion', new_callable=AsyncMock, return_value=response_body) as model:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.post(f'/api/research/{research_id}/review-article')
            assert response.status_code == 200, response.text
            assert response.json()['version'] == 5
            assert response.json()['sources'][0]['source_id'] == source_id
            assert all(source_id in paragraph['source_ids'] for paragraph in response.json()['paragraphs'])
            assert model.await_count == 4
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()
    asyncio.run(check())


def test_article_accepts_attributed_publisher_information_without_reviews():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            listing = BookList(name='test', source_type='csv')
            db.add(listing)
            await db.flush()
            book = Book(book_list_id=listing.id, title='Test Book', author='Author')
            db.add(book)
            await db.flush()
            research = Research(book_id=book.id, themes=['death'], status='completed')
            db.add(research)
            await db.flush()
            source = Source(research_id=research.id, title='Publisher description', url='https://example.org/book',
                            source_type=SourceType.PUBLISHER_DESCRIPTION, is_duplicate=0, is_about_target_book=1,
                            fetch_status='fetched', cleaned_content='A story about a family.', summary='A family story.')
            db.add(source)
            await db.commit()
            research_id, source_id = research.id, source.id

        async def test_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        try:
            response_body = json.dumps({'paragraphs': [{'text': '出版社简介提到了家庭故事，现有资料尚不足以评价作品。' * 8, 'source_ids': [source_id]}]}, ensure_ascii=False)
            with patch('app.api.research.curate_review_sources', new_callable=AsyncMock, side_effect=lambda client, book, sources: (sources, {'findings': [], 'gaps': []}, [])), patch('app.api.research.LLMClient.chat_completion', new_callable=AsyncMock, return_value=response_body) as model:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.post(f'/api/research/{research_id}/review-article')
            assert response.status_code == 200, response.text
            assert response.json()['sources'][0]['source_id'] == source_id
            assert 'publisher_description' in str(model.await_args.args)
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()
    asyncio.run(check())


def test_review_agents_screen_sources_and_validate_evidence_ids():
    from app.services.review_pipeline import curate_review_sources, parse_model_json

    async def check():
        sources = [
            {'source_id': 1, 'title': 'Correct book', 'source_type': 'reader_review', 'basis': 'page', 'summary': 'Relevant', 'excerpt': 'Evidence'},
            {'source_id': 2, 'title': 'Different book', 'source_type': 'other', 'basis': 'page', 'summary': 'Unrelated', 'excerpt': 'Other'},
        ]
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(side_effect=[
            '{"keep":[1,999]}',
            '{"findings":[{"kind":"读者意见","text":"Relevant",source_ids":[1,999]}],"gaps":["缺少原文"]}',
        ])
        selected, evidence, warnings = await curate_review_sources(client, {'title': 'Book', 'author': 'Author'}, sources)
        assert [row['source_id'] for row in selected] == [1]
        assert evidence['findings'][0]['source_ids'] == [1]
        assert evidence['gaps'] == ['缺少原文']
        assert not warnings
        assert parse_model_json('{"paragraphs":[{"text":"example",source_ids":[1]}]}')['paragraphs'][0]['source_ids'] == [1]
    asyncio.run(check())
