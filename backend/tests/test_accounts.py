import asyncio
import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.auth import current_user
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.book import Book, BookList
from app.models.podcast_run import PodcastRun
from app.models.research import Research
from app.models.user import LoginSession


def test_accounts_isolate_books_jobs_voices_and_pronunciations(monkeypatch):
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            listing = BookList(name='Legacy library', source_type='csv')
            db.add(listing)
            await db.flush()
            book = Book(book_list_id=listing.id, title='Legacy book')
            db.add(book)
            await db.flush()
            research = Research(book_id=book.id, themes=[], status='completed', job_id='private-job')
            db.add(research)
            await db.flush()
            db.add(PodcastRun(research_id=research.id, status='completed', request={'language': 'en'},
                              audio_voices={'主持人': 'speech:owner:old'}, result={}))
            await db.commit()
            book_id = book.id
            research_id = research.id
            run_id = (await db.execute(select(PodcastRun.id))).scalar_one()

        async def test_db():
            async with sessions() as session:
                yield session

        saved_override = app.dependency_overrides.pop(current_user, None)
        app.dependency_overrides[get_db] = test_db
        monkeypatch.setattr(settings, 'AUTH_REGISTRATION_CODE', 'test-setup-code')
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url='http://test') as owner, \
                       httpx.AsyncClient(transport=transport, base_url='http://test') as stranger:
                payload = {'username': 'owner', 'password': 'long-password-123', 'registration_code': 'test-setup-code'}
                assert (await owner.post('/api/auth/register', json={**payload, 'registration_code': 'wrong'})).status_code == 403
                first = await owner.post('/api/auth/register', json=payload)
                assert first.status_code == 200, first.text
                assert (await owner.get('/api/books/' + str(book_id))).status_code == 200
                voices = (await owner.get('/api/voices')).json()
                assert any(row['voice_id'] == 'speech:owner:old' and row['language'] == 'en' for row in voices)
                assert (await owner.post('/api/voices/restore', json={'voice_id': 'speech:owner:old'})).status_code == 200
                assert (await owner.get('/api/voices')).json() == voices
                assert (await owner.post('/api/voices/pronunciations',
                                         json={'original': 'Cixin Liu', 'spoken': 'Tsee shin Lyoo'})).status_code == 200
                assert len((await owner.get('/api/voices/pronunciations')).json()) == 1
                with patch('app.api.research.get_job_status', return_value={'status': 'finished'}):
                    assert (await owner.get('/api/research/job/private-job')).status_code == 200
                    assert (await owner.get('/api/research/job/not-my-job')).status_code == 404
                assert (await stranger.get('/api/books/' + str(book_id))).status_code == 401
                second = await stranger.post('/api/auth/register', json={**payload, 'username': 'other'})
                assert second.status_code == 200, second.text
                for endpoint in (f'/api/books/{book_id}', f'/api/research/{research_id}',
                                 f'/api/podcasts/{run_id}',
                                 '/api/research/job/private-job'):
                    assert (await stranger.get(endpoint)).status_code == 404, endpoint
                assert (await stranger.get('/api/voices')).json() == []
                assert (await stranger.get('/api/voices/pronunciations')).json() == []
                assert (await stranger.post('/api/voices/restore', json={'voice_id': 'speech:owner:old'})).status_code == 404
                assert (await stranger.post('/api/voices/restore', json={'voice_id': 'FunAudioLLM/CosyVoice2-0.5B:alex'})).status_code == 400
                assert (await stranger.delete('/api/voices/saved/' + str(voices[0]['id']))).status_code == 404
                assert (await stranger.post('/api/voices/pronunciations',
                                            json={'original': 'x', 'spoken': 'y'},
                                            headers={'Origin': 'http://evil.example'})).status_code == 403
                assert (await owner.post('/api/auth/logout')).status_code == 200
                assert (await owner.get('/api/auth/me')).status_code == 401
                assert (await owner.post('/api/auth/login', json={'username': 'owner', 'password': 'wrong-password'})).status_code == 401
                assert (await owner.post('/api/auth/login', json=payload)).status_code == 200
                assert (await owner.get('/api/auth/me')).json()['username'] == 'owner'
                token = owner.cookies['bookcast_session']
                async with sessions() as db:
                    session = await db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
                    session.expires_at = datetime.utcnow() - timedelta(seconds=1)
                    await db.commit()
                assert (await owner.get('/api/auth/me')).status_code == 401
        finally:
            app.dependency_overrides.pop(get_db, None)
            if saved_override is not None:
                app.dependency_overrides[current_user] = saved_override
            await engine.dispose()

    asyncio.run(check())
