import asyncio
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.book import Book, BookList
from app.models.research import Research
from app.services.research_orchestrator import ResearchOrchestrator


def test_single_book_search_save_and_whole_book_research():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        async def test_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        rows = [
            {'key': '/works/OL123W', 'title': 'Spook', 'author_name': ['Mary Roach'], 'first_publish_year': 2005},
            {'key': '/works/OL124W', 'title': 'Spooky', 'author_name': ['Mary Roach']},
        ]
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                with patch('app.api.books._catalog_search', new_callable=AsyncMock, return_value=rows):
                    response = await client.get('/api/books/search', params={'title': 'Spook', 'author': 'Mary Roach'})
                    assert response.status_code == 200, response.text
                    assert [book['work_key'] for book in response.json()['books']] == ['/works/OL123W']

                    payload = {'title': 'Spook', 'author': 'Mary Roach', 'work_key': '/works/OL123W'}
                    response = await client.post('/api/books/single', json=payload)
                    assert response.status_code == 200, response.text
                    book_id = response.json()['id']
                    assert (await client.post('/api/books/single', json=payload)).json()['id'] == book_id
                    assert (await client.post('/api/books/single', json={**payload, 'author': 'Wrong Author'})).status_code == 400
                    assert (await client.post('/api/books/single', json={**payload, 'work_key': '/works/OL999W'})).status_code == 400

                    async with sessions() as db:
                        listing = BookList(user_id=1, name='Other source', source_type='amazon')
                        db.add(listing)
                        await db.flush()
                        db.add(Book(book_list_id=listing.id, title='Different book', author='Other Author', platform_id='/works/OL124W'))
                        await db.commit()
                    response = await client.post('/api/books/single', json={'title': 'Spooky', 'author': 'Mary Roach', 'work_key': '/works/OL124W'})
                    assert response.status_code == 200, response.text
                    assert response.json()['title'] == 'Spooky'

                with patch('app.api.research.enqueue_research', return_value='job-1'):
                    response = await client.post('/api/research/', json={'book_id': book_id, 'themes': []})
                assert response.status_code == 200, response.text
                research_id = response.json()['research_id']

                response = await client.post('/api/books/single', json={'title': 'Unknown title', 'author': 'Known author'})
                assert response.status_code == 200, response.text
                assert response.json()['platform_id'] is None
                assert (await client.post('/api/books/single', json={'title': 'Unknown title', 'author': 'Known author'})).json()['id'] == response.json()['id']

            async with sessions() as db:
                research = await db.get(Research, research_id)
                assert research.themes == []
                orchestrator = ResearchOrchestrator(db)
                orchestrator.theme_screener.screen_book_for_themes = AsyncMock(side_effect=AssertionError('unexpected theme screen'))
                orchestrator.theme_screener.aggregate_matches = AsyncMock(side_effect=AssertionError('unexpected theme aggregation'))
                orchestrator.material_searcher.search_materials = AsyncMock(return_value=[])
                orchestrator.llm_client.assess_material_sufficiency = AsyncMock(return_value={
                    'overall_assessment': 'insufficient', 'reasoning': 'No sources',
                })
                with (
                    patch('app.services.research_orchestrator.open_library_book', new_callable=AsyncMock, return_value=None),
                    patch('app.services.research_orchestrator.search_goodreads_reviews', new_callable=AsyncMock, return_value=[]),
                    patch('app.services.research_orchestrator.gutenberg_excerpts', new_callable=AsyncMock, return_value=None),
                ):
                    result = await orchestrator.conduct_research(research_id)
                assert result['status'] == 'completed', result
                assert result['theme_matches'] == 0
                assert result['assessment'] == 'insufficient'
                orchestrator.material_searcher.search_materials.assert_awaited_once()
                assert orchestrator.material_searcher.search_materials.await_args.kwargs['themes'] == []
                orchestrator.llm_client.assess_material_sufficiency.assert_awaited_once()
                assert orchestrator.llm_client.assess_material_sufficiency.await_args.kwargs['theme_matches'] == []
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()

    asyncio.run(check())


def test_single_book_search_falls_back_to_web_and_labels_unverified_results():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            catalog = AsyncMock(side_effect=[[], []])
            sources = [{'title': 'The Night Circus by Erin Morgenstern review',
                        'url': 'https://example.com/review',
                        'content': 'The Night Circus by Erin Morgenstern is a novel with a magical competition.'}]
            response_json = '{"books":[{"title":"The Night Circus","author":"Erin Morgenstern","source_id":1,"evidence_quote":"The Night Circus by Erin Morgenstern is a novel with a magical competition."}]}'
            with (patch('app.api.books._catalog_search', catalog),
                  patch('app.api.books.SearchClient') as search_client,
                  patch('app.api.books.LLMClient') as llm_client):
                search_client.return_value.search = AsyncMock(return_value=sources)
                llm_client.return_value.chat_completion = AsyncMock(return_value=response_json)
                response = await client.get('/api/books/search', params={'title': 'The Night Circus'})
                assert response.status_code == 200, response.text
                assert response.json()['books'][0]['source'] == 'web'
                assert response.json()['books'][0]['work_key'] is None
                assert response.json()['references'][0]['url'] == sources[0]['url']
                assert search_client.return_value.search.await_count == 2

            with (patch('app.api.books._catalog_search', AsyncMock(side_effect=httpx.ConnectError('offline'))),
                  patch('app.api.books.SearchClient') as search_client,
                  patch('app.api.books.LLMClient') as llm_client):
                search_client.return_value.search = AsyncMock(return_value=sources)
                llm_client.return_value.chat_completion = AsyncMock(return_value=response_json)
                response = await client.get('/api/books/search', params={'title': 'The Night Circus'})
                assert response.status_code == 200, response.text
                assert response.json()['books'][0]['source'] == 'web'

            with (patch('app.api.books._catalog_search', AsyncMock(return_value=[])),
                  patch('app.api.books.SearchClient') as search_client,
                  patch('app.api.books.LLMClient') as llm_client):
                search_client.return_value.search = AsyncMock(return_value=sources)
                llm_client.return_value.chat_completion = AsyncMock(return_value='{"books":[{"title":"Wrong book","author":"Wrong author","source_id":1,"evidence_quote":"The Night Circus by Erin Morgenstern is a novel with a magical competition."}]}')
                response = await client.get('/api/books/search', params={'title': 'The Night Circus'})
                assert response.status_code == 200, response.text
                assert response.json()['books'][0]['title'] == 'The Night Circus'
                assert response.json()['books'][0]['author'] == 'Erin Morgenstern'
                assert response.json()['books'][0]['source'] == 'web'
                assert response.json()['references']

    asyncio.run(check())


def test_web_candidate_can_be_saved_and_research_completed_for_writing():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        async def test_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        sources = [{'title': 'The Three-Body Problem novel by Cixin Liu | Britannica',
                    'url': 'https://example.org/three-body', 'content': 'The Three-Body Problem novel by Cixin Liu.'}]
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                with (patch('app.api.books._catalog_search', AsyncMock(return_value=[])),
                      patch('app.api.books.SearchClient') as search_client,
                      patch('app.api.books.LLMClient') as llm_client):
                    search_client.return_value.search = AsyncMock(return_value=sources)
                    llm_client.return_value.chat_completion = AsyncMock(side_effect=ConnectionError('model offline'))
                    response = await client.get('/api/books/search', params={'title': 'The Three-Body Problem'})
                    assert response.status_code == 200, response.text
                    candidate = response.json()['books'][0]
                    assert candidate['source'] == 'web'
                    assert candidate['author'] == 'Cixin Liu'
                response = await client.post('/api/books/single', json={
                    'title': candidate['title'], 'author': candidate['author'],
                })
                assert response.status_code == 200, response.text
                book_id = response.json()['id']
                with patch('app.api.research.enqueue_research', return_value='job-1'):
                    response = await client.post('/api/research/', json={'book_id': book_id, 'themes': []})
                assert response.status_code == 200, response.text
                research_id = response.json()['research_id']

                async with sessions() as db:
                    orchestrator = ResearchOrchestrator(db)
                    orchestrator.material_searcher.search_materials = AsyncMock(return_value=[])
                    orchestrator.llm_client.assess_material_sufficiency = AsyncMock(side_effect=ConnectionError('model offline'))
                    catalog = {'title': 'Open Library 图书资料：The Three-Body Problem',
                               'url': 'https://openlibrary.org/works/OL123W',
                               'content': 'The Three-Body Problem by Cixin Liu. ' + 'Catalog description. ' * 20,
                               'description': 'Catalog description. ' * 20, 'gutenberg_ids': []}
                    with (patch('app.services.research_orchestrator.open_library_book', AsyncMock(return_value=catalog)),
                          patch('app.services.research_orchestrator.search_goodreads_reviews', AsyncMock(return_value=[])),
                          patch('app.services.research_orchestrator.gutenberg_excerpts', AsyncMock(return_value=None))):
                        result = await orchestrator.conduct_research(research_id)
                    assert result['status'] == 'completed', result
                    assert result['assessment'] == 'needs_review'

                response = await client.get(f'/api/research/{research_id}')
                assert response.status_code == 200, response.text
                assert response.json()['status'] == 'completed'
                section = '{"paragraphs":[{"text":"' + ('基于馆藏资料讨论这本书的背景与叙事。' * 10) + '","source_ids":[1]}]}'
                with (patch('app.api.research.curate_review_sources', new_callable=AsyncMock,
                            side_effect=lambda client, book, sources: (sources, {'findings': [], 'gaps': []}, [])),
                      patch('app.services.llm_client.LLMClient.chat_completion', new_callable=AsyncMock, return_value=section)):
                    response = await client.post(f'/api/research/{research_id}/review-article')
                assert response.status_code == 200, response.text
                assert response.json()['paragraphs']
                with patch('app.api.podcasts.enqueue_podcast'):
                    response = await client.post('/api/podcasts/', json={
                        'research_id': research_id, 'speaker_count': 1, 'language': 'zh',
                    })
                assert response.status_code == 200, response.text
                assert response.json()['research_id'] == research_id
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()

    asyncio.run(check())
