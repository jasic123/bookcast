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
            'speaker_count': 2, 'duration': 2, 'style': '自然对谈', 'audience': '普通读者',
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
        assert result['decision'] == 'approved', result['reviews']
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


def test_english_script_keeps_speaker_labels_and_rejects_chinese_dialogue():
    async def check():
        plan = json.dumps({'premise': 'Discuss', 'outline': [{'title': 'Opening', 'minutes': 2, 'focus': 'Book'}]})
        english = '主持人：' + ('The source supports this reading of the book. ' * 44) + '[1]'
        chinese = '主持人：' + ('这本书的观点需要资料支持。' * 40) + '[1]'
        approval = json.dumps({'approved': True, 'issues': [], 'summary': 'Approved'})
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(side_effect=[plan, chinese, approval, english, approval])
        search = type('Search', (), {})()
        search.search = AsyncMock(return_value=[])
        with patch('app.services.podcast_agents.curate_review_sources', new_callable=AsyncMock,
                   side_effect=lambda client, book, sources: (sources, {'findings': [], 'gaps': []}, [])):
            result = await run_podcast_flow({**_request(), 'speaker_count': 1, 'language': 'en'}, client=client, search=search)
        assert result['decision'] == 'approved', result['reviews']
        assert any('英文文稿' in issue for issue in result['reviews'][0]['issues'])
        assert result['drafts'][-1]['content'].startswith('主持人：The source')
        writer_prompt = client.chat_completion.await_args_list[1].args[0][0]['content']
        assert 'Write all spoken dialogue in natural English' in writer_prompt
        assert '"language": "en"' in client.chat_completion.await_args_list[1].args[0][1]['content']

    asyncio.run(check())


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


def test_graph_writes_selected_solo_and_three_speaker_formats():
    async def check(count, script, expected):
        plan = json.dumps({'premise': 'Discuss',
                           'roles': [{'speaker': role, 'purpose': '讨论'} for role in expected] +
                                    [{'speaker': '额外角色', 'purpose': '错误角色'}],
                           'outline': [{'title': 'Opening', 'minutes': 2, 'focus': 'Book'}]})
        review = json.dumps({'approved': True, 'issues': [], 'summary': '通过'})
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(side_effect=[plan, script, review])
        search = type('Search', (), {})()
        search.search = AsyncMock(return_value=[])
        request = {**_request(), 'speaker_count': count}
        with patch('app.services.podcast_agents.curate_review_sources', new_callable=AsyncMock,
                   side_effect=lambda client, book, sources: (sources, {'findings': [], 'gaps': []}, [])):
            result = await run_podcast_flow(request, client=client, search=search)
        assert result['speakers'] == expected
        assert result['plan']['speakers'] == expected
        assert [role['speaker'] for role in result['plan']['roles']] == expected
        assert result['reviews'][-1]['approved']

    solo = '主持人：' + ('这本书的观点需要证据支持。' * 40) + '[1]'
    panel = '\n'.join(f'{role}：' + ('这本书的观点需要证据支持。' * 14) + '[1]'
                      for role in ('主持人', '嘉宾1', '嘉宾2'))
    asyncio.run(check(1, solo, ['主持人']))
    asyncio.run(check(3, panel, ['主持人', '嘉宾1', '嘉宾2']))


def test_critic_rejects_missing_selected_speaker():
    async def check():
        plan = json.dumps({'premise': 'Discuss', 'outline': [{'title': 'Opening', 'minutes': 2, 'focus': 'Book'}]})
        review = json.dumps({'approved': True, 'issues': [], 'summary': '通过'})
        draft = '主持人：' + ('这是有资料支持的讨论。' * 20) + '[1]\n嘉宾1：' + ('我会核对证据。' * 20) + '[1]'
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(side_effect=[plan, draft, review, draft, review, draft, review])
        search = type('Search', (), {})()
        search.search = AsyncMock(return_value=[])
        with patch('app.services.podcast_agents.curate_review_sources', new_callable=AsyncMock,
                   side_effect=lambda client, book, sources: (sources, {'findings': [], 'gaps': []}, [])):
            result = await run_podcast_flow({**_request(), 'speaker_count': 3}, client=client, search=search)
        assert result['decision'] == 'stop'
        assert not result['reviews'][-1]['approved']
        assert any('嘉宾2' in issue for issue in result['reviews'][-1]['issues'])

    asyncio.run(check())


def test_checkpoint_resume_skips_planning_and_research():
    async def check():
        checkpoint = {
            **{**_request(), 'speaker_count': 1},
            'speakers': ['主持人'],
            'plan': {'premise': 'Saved plan', 'outline': [{'title': 'Opening', 'minutes': 2, 'focus': 'Book'}], 'roles': []},
            'sources': [{'source_id': 1, 'title': 'Saved source', 'url': 'https://example.com',
                         'source_type': 'review', 'basis': 'page', 'summary': 'Saved', 'excerpt': 'Saved', 'points': []}],
            'evidence': {'findings': [], 'gaps': []},
            'drafts': [], 'reviews': [], 'checkpoint_stage': 'researched',
        }
        script = '主持人：' + ('这本书的观点需要证据支持。' * 40) + '[1]'
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(side_effect=[script, json.dumps({'approved': True, 'issues': [], 'summary': '通过'})])
        search = type('Search', (), {})()
        search.search = AsyncMock(side_effect=AssertionError('resumed task should not search again'))
        saved = []
        async def on_checkpoint(stage, state):
            saved.append((stage, state['checkpoint_stage']))

        with patch('app.services.podcast_agents.curate_review_sources', new_callable=AsyncMock,
                   side_effect=AssertionError('resumed task should not research again')):
            result = await run_podcast_flow(checkpoint, checkpoint=checkpoint, client=client,
                                            search=search, on_checkpoint=on_checkpoint)
        assert result['decision'] == 'approved'
        assert saved == [('drafted', 'drafted'), ('reviewed', 'reviewed'), ('complete', 'complete')]
        assert client.chat_completion.await_count == 2

    asyncio.run(check())


def test_checkpoint_resume_reviews_saved_draft_without_rewriting():
    async def check():
        request = {**_request(), 'speaker_count': 1}
        checkpoint = {
            'plan': {'premise': 'Saved plan', 'outline': [{'title': 'Opening', 'minutes': 2, 'focus': 'Book'}]},
            'sources': request['sources'], 'evidence': {'findings': [], 'gaps': []},
            'drafts': [{'iteration': 1, 'content': '主持人：' + ('有资料支持的观点。' * 40) + '[1]'}],
            'reviews': [], 'checkpoint_stage': 'drafted',
        }
        client = type('Client', (), {})()
        client.chat_completion = AsyncMock(return_value=json.dumps({'approved': True, 'issues': [], 'summary': '通过'}))
        search = type('Search', (), {})()
        search.search = AsyncMock(side_effect=AssertionError('saved research must be reused'))
        result = await run_podcast_flow(request, checkpoint=checkpoint, client=client, search=search)
        assert result['decision'] == 'approved'
        assert len(result['drafts']) == 1
        assert client.chat_completion.await_count == 1

    asyncio.run(check())


def test_checkpoint_resume_revision_writes_next_version():
    async def check():
        request = {**_request(), 'speaker_count': 1}
        first = '主持人：' + ('第一版内容。' * 40) + '[1]'
        second = '主持人：' + ('修改后的内容。' * 65) + '[1]'
        feedback = {'iteration': 1, 'approved': False, 'issues': ['补充论据'], 'summary': '重写', 'estimated_minutes': 2}
        checkpoint = {
            'plan': {'premise': 'Saved plan', 'outline': [{'title': 'Opening', 'minutes': 2, 'focus': 'Book'}]},
            'sources': request['sources'], 'evidence': {'findings': [], 'gaps': []},
            'drafts': [{'iteration': 1, 'content': first}], 'reviews': [feedback],
            'feedback': feedback, 'decision': 'revise', 'checkpoint_stage': 'reviewed',
        }
        client = type('Client', (), {})()
        async def respond(messages, **kwargs):
            return second if '播客稿作者' in messages[0]['content'] else json.dumps({'approved': True, 'issues': [], 'summary': '通过'})
        client.chat_completion = AsyncMock(side_effect=respond)
        search = type('Search', (), {})()
        search.search = AsyncMock(side_effect=AssertionError('saved research must be reused'))
        result = await run_podcast_flow(request, checkpoint=checkpoint, client=client, search=search)
        assert result['decision'] == 'approved', result['reviews']
        assert [draft['iteration'] for draft in result['drafts']] == [1, 2]
        assert [review['iteration'] for review in result['reviews']] == [1, 2]
        assert client.chat_completion.await_count == 2

    asyncio.run(check())


def test_user_selected_feedback_revises_saved_draft_once():
    async def check():
        request = {**_request(), 'speaker_count': 1}
        first = '主持人：' + ('旧稿内容。' * 60) + '[1]'
        second = '主持人：' + ('只调整开场后的内容。' * 55) + '[1]'
        checkpoint = {
            'plan': {'premise': 'Saved', 'outline': [{'title': 'Opening', 'minutes': 2, 'focus': 'Book'}]},
            'sources': request['sources'], 'evidence': {'findings': [], 'gaps': []},
            'drafts': [{'iteration': 1, 'content': first}],
            'reviews': [{'iteration': 1, 'approved': False, 'issues': ['补充证据', '调整开场']}],
            'feedback': {'iteration': 1, 'issues': ['调整开场'], 'selected_by_user': True},
            'decision': 'revise', 'checkpoint_stage': 'reviewed', 'manual_revision_target': 2,
        }
        client = type('Client', (), {})()
        async def respond(messages, **kwargs):
            if '播客稿作者' in messages[0]['content']:
                payload = json.loads(messages[1]['content'])
                assert payload['feedback']['issues'] == ['调整开场']
                assert payload['previous_script'] == first
                return second
            return json.dumps({'approved': False, 'issues': ['需人工审阅'], 'summary': '未通过'})
        client.chat_completion = AsyncMock(side_effect=respond)
        search = type('Search', (), {})()
        search.search = AsyncMock(side_effect=AssertionError('saved research must be reused'))
        result = await run_podcast_flow(request, checkpoint=checkpoint, client=client, search=search)
        assert result['decision'] == 'stop'
        assert [draft['iteration'] for draft in result['drafts']] == [1, 2]
        assert [review['iteration'] for review in result['reviews']] == [1, 2]
        assert client.chat_completion.await_count == 2

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
                    response = await client.post('/api/podcasts/', json={'research_id': research_id, 'speaker_count': 1, 'language': 'en', 'duration': 5, 'reference_text': 'Reference'})
                    assert response.status_code == 200, response.text
                    run = response.json()
                    assert run['status'] == 'queued'
                    assert run['speakers'] == ['主持人']
                    assert run['language'] == 'en'
                    assert (await client.post('/api/podcasts/', json={'research_id': research_id, 'speaker_count': 1, 'language': 'fr'})).status_code == 422
                    assert (await client.post('/api/podcasts/', json={'research_id': research_id})).status_code == 422
                    assert (await client.get(f'/api/podcasts/{run["id"]}')).json()['id'] == run['id']
                    assert (await client.get(f'/api/podcasts/research/{research_id}')).json()['id'] == run['id']
                    enqueue.assert_called_once_with(run['id'])
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()
    asyncio.run(check())
