"""Cookie sessions and ownership checks for the local web application."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.book import Book, BookList
from app.core.config import settings
from app.models.research import Research
from app.models.podcast_run import PodcastRun
from app.models.theme_search import ThemeSearch
from app.models.user import LoginSession, User

SESSION_DAYS = 14


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f'{salt.hex()}:{digest.hex()}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt, expected = encoded.split(':', 1)
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(digest, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def new_session(user_id: int) -> tuple[str, LoginSession]:
    token = secrets.token_urlsafe(32)
    return token, LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user_id,
                               expires_at=datetime.utcnow() + timedelta(days=SESSION_DAYS))


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get('bookcast_session')
    if not token:
        raise HTTPException(status_code=401, detail='请先登录。')
    session = await db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not session or session.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=401, detail='登录已过期，请重新登录。')
    user = await db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail='用户不存在。')
    return user


async def require_same_origin(request: Request):
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return
    origin = request.headers.get('origin')
    if origin and origin not in settings.cors_origins_list and origin != f'{request.url.scheme}://{request.url.netloc}':
        raise HTTPException(status_code=403, detail='请求来源不可信。')


async def owned_book(db: AsyncSession, book_id: int, user: User) -> Book:
    book = (await db.execute(select(Book).join(BookList).where(
        Book.id == book_id, BookList.user_id == user.id))).scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail='书籍不存在。')
    return book


async def owned_research(db: AsyncSession, research_id: int, user: User) -> Research:
    research = (await db.execute(select(Research).join(Book, Research.book_id == Book.id)
        .join(BookList, Book.book_list_id == BookList.id).where(
            Research.id == research_id, BookList.user_id == user.id))).scalar_one_or_none()
    if not research:
        raise HTTPException(status_code=404, detail='研究记录不存在。')
    return research


async def owned_search(db: AsyncSession, search_id: int, user: User) -> ThemeSearch:
    search = await db.get(ThemeSearch, search_id)
    if not search or search.user_id != user.id:
        raise HTTPException(status_code=404, detail='找书任务不存在。')
    return search


async def owned_podcast(db: AsyncSession, run_id: int, user: User) -> PodcastRun:
    run = await db.get(PodcastRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail='播客任务不存在。')
    await owned_research(db, run.research_id, user)
    return run
