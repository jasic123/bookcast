"""Registration and login for a private, per-user library."""
import hashlib
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import SESSION_DAYS, current_user, new_session, password_hash, verify_password
from app.core.config import settings
from app.core.database import get_db
from app.models.book import Book, BookList
from app.models.theme_search import ThemeSearch
from app.models.user import LoginSession, SavedVoice, User
from app.models.research import Research
from app.models.podcast_run import PodcastRun

router = APIRouter(prefix='/auth', tags=['auth'])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=256)
    registration_code: str = ''


def set_session(response: Response, token: str):
    response.set_cookie('bookcast_session', token, httponly=True, secure=settings.SESSION_COOKIE_SECURE,
                        samesite='lax', max_age=SESSION_DAYS * 86400, path='/api')


@router.post('/register')
async def register(data: Credentials, response: Response, db: AsyncSession = Depends(get_db)):
    if not settings.AUTH_REGISTRATION_CODE or not secrets.compare_digest(data.registration_code, settings.AUTH_REGISTRATION_CODE):
        raise HTTPException(status_code=403, detail='注册口令不正确或尚未配置。')
    username = data.username.strip().casefold()
    if not re.fullmatch(r'[a-z0-9_-]{3,80}', username):
        raise HTTPException(status_code=422, detail='用户名只能包含英文字母、数字、下划线和连字符。')
    if (await db.execute(select(User).where(User.username == username))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail='用户名已存在。')
    user = User(username=username, password_hash=password_hash(data.password))
    db.add(user)
    await db.flush()
    if not (await db.execute(select(User.id).where(User.id != user.id).limit(1))).first():
        # Existing local data belongs to the first account created with the setup code.
        await db.execute(update(BookList).where(BookList.user_id.is_(None)).values(user_id=user.id))
        await db.execute(update(ThemeSearch).where(ThemeSearch.user_id.is_(None)).values(user_id=user.id))
        runs = (await db.execute(select(PodcastRun.audio_voices, PodcastRun.request).join(Research, PodcastRun.research_id == Research.id)
            .join(Book, Research.book_id == Book.id).join(BookList, Book.book_list_id == BookList.id)
            .where(BookList.user_id == user.id, PodcastRun.audio_voices.is_not(None)))).all()
        legacy = {(voice, (request or {}).get('language', 'zh'))
                  for mapping, request in runs for voice in (mapping or {}).values()
                  if isinstance(voice, str) and voice.startswith('speech:')}
        db.add_all(SavedVoice(user_id=user.id, name=f'legacy_{index}', voice_id=voice,
                              language=language if language in ('zh', 'en') else 'zh')
                   for index, (voice, language) in enumerate(sorted(legacy), 1))
    token, session = new_session(user.id)
    db.add(session)
    await db.commit()
    set_session(response, token)
    return {'id': user.id, 'username': user.username}


@router.post('/login')
async def login(data: Credentials, response: Response, db: AsyncSession = Depends(get_db)):
    username = data.username.strip().casefold()
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail='用户名或密码错误。')
    token, session = new_session(user.id)
    db.add(session)
    await db.commit()
    set_session(response, token)
    return {'id': user.id, 'username': user.username}


@router.post('/logout')
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get('bookcast_session')
    if token:
        session = await db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
        if session:
            await db.delete(session)
            await db.commit()
    response.delete_cookie('bookcast_session', path='/api')
    return {'ok': True}


@router.get('/me')
async def me(user: User = Depends(current_user)):
    return {'id': user.id, 'username': user.username}
