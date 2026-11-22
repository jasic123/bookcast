import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.book import Book, BookList
from app.models.research import Research
from app.services.podcast_agents import run_podcast_flow


def _request():
    return {'book': {'title': 'Test Book', 'author': 'Author'}, 'theme': 'friendship',
            'duration': 2, 'style': '自然对谈', 'audience': '普通读者',
            'sources': [{'source_id': 1, 'title': 'Source', 'url': 'https://example.org',
                         'source_type': 'reader_review', 'basis': 'page', 'summary': 'Evidence',
                         'excerpt': 'Evidence', 'points': []}]}


def _script():
    return '主持人：' + ('这是有资料支持的书籍讨论。' * 20) + '[1]\n嘉宾：' + ('这个观点需要结合读者意见理解。' * 20) + '[1]'


def test_graph_revises_after_criticism_then_approves():
    async def check():
        responses = [json.dumps({'premise': 'Discuss', 'outline': [{'title': 'Opening', 'minutes': 2, 'focus': 'Book'}]}),
                     _script(), json.dumps({'approved': False, 'issues': ['补充过渡'], 'summary': '需要修改'}),
                     _script(), json.dumps({'approved': True, 'issues': [], 'summary': '通过'})]
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(side_effect=responses)
        search = type('Search', (), {})()
        search.search = AsyncMock(return_value=[])
        steps = []
        async def progress(step): steps.append(step)
        with patch('app.services.podcast_agents.curate_review_sources', new_callable=AsyncMock, side_effect=lambda client, book, sources: (sources, {'findings': [], 'gaps': []}, [])):
            result = await run_podcast_flow(_request(), client=client, search=search, on_step=progress)
        assert result['decision'] == 'approved'
        assert len(result['drafts']) == len(result['reviews']) == 2
        assert result['reviews'][0]['issues'] == ['补充过渡']
        assert any('第 2 版' in step for step in steps)
        revision_request = client.chat_completion.await_args_list[3].args[0][1]['content']
        assert '补充过渡' in revision_request and 'previous_script' in revision_request and '主持人' in revision_request
        assert search.search.await_count == 1
    asyncio.run(check())


def test_citation_formats_are_normalized_without_inventing_ids():
    from app.services.podcast_agents import normalize_citations
    assert normalize_citations('观点[来源ID 12, 34]；另一观点【来源：56】。') == '观点[12][34]；另一观点[56]。'


def test_graph_stops_without_approval_after_three_drafts():
    async def check():
        plan = json.dumps({'premise': 'Discuss', 'outline': [{'title': 'Opening', 'minutes': 2, 'focus': 'Book'}]})
        reject = json.dumps({'approved': False, 'issues': ['证据不足'], 'summary': '未通过'})
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(side_effect=[plan, _script(), reject, _script(), reject, _script(), reject])
        search = type('Search', (), {})()
        search.search = AsyncMock(return_value=[])
        with patch('app.services.podcast_agents.curate_review_sources', new_callable=AsyncMock, side_effect=lambda client, book, sources: (sources, {'findings': [], 'gaps': []}, [])):
            result = await run_podcast_flow(_request(), client=client, search=search)
        assert result['decision'] == 'stop'
        assert len(result['drafts']) == 3
        assert not result['reviews'][-1]['approved']
    asyncio.run(check())


def test_podcast_api_queues_and_reads_run():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            listing = BookList(name='test', source_type='csv')
            db.add(listing)
            await db.flush()
            book = Book(book_list_id=listing.id, title='Book', author='Author')
            db.add(book)
            await db.flush()
            research = Research(book_id=book.id, themes=['other'], status='completed')
            db.add(research)
            await db.commit()
            research_id = research.id

        async def test_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        try:
            with patch('app.api.podcasts.enqueue_podcast', return_value='job') as enqueue:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.post('/api/podcasts/', json={'research_id': research_id, 'duration': 5, 'reference_text': 'Reference'})
                    assert response.status_code == 200, response.text
                    run = response.json()
                    assert run['status'] == 'queued'
                    assert (await client.get(f'/api/podcasts/{run["id"]}')).json()['id'] == run['id']
                    assert (await client.get(f'/api/podcasts/research/{research_id}')).json()['id'] == run['id']
                    enqueue.assert_called_once_with(run['id'])
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()
    asyncio.run(check())
