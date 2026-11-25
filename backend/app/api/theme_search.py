"""Theme-first book discovery API."""
import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from redis.exceptions import RedisError
from rq.registry import StartedJobRegistry
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import current_user, owned_search
from app.core.queue import enqueue_theme_search, research_queue
from app.models.book import Book
from app.models.theme_search import ThemeBookEvidence, ThemeSearch
from app.models.user import User

router = APIRouter(prefix='/theme-search', tags=['theme-search'], dependencies=[Depends(current_user)])


class ThemeSearchCreate(BaseModel):
    theme: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=10)

    @field_validator('theme')
    @classmethod
    def strip_theme(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('请输入主题。')
        return value


def _job_is_active(job_id: str) -> bool:
    if job_id in research_queue.job_ids:
        return True
    return job_id in StartedJobRegistry(queue=research_queue).get_job_ids()


async def _sync_task_status(db, search):
    if search.status not in ('queued', 'running'):
        return
    if search.job_id:
        try:
            active = await asyncio.to_thread(_job_is_active, search.job_id)
            if not active:
                await asyncio.sleep(1)
                active = await asyncio.to_thread(_job_is_active, search.job_id)
        except RedisError:
            return
    else:
        # Older rows have no RQ job ID; allow existing jobs time to finish.
        limit = timedelta(minutes=30 if search.status == 'queued' else 60)
        active = not search.created_at or datetime.utcnow() - search.created_at < limit
    if active:
        return
    await db.execute(
        update(ThemeSearch)
        .where(ThemeSearch.id == search.id, ThemeSearch.status.in_(['queued', 'running']))
        .values(status='failed', error_message='找书任务已从队列中丢失，请重新搜索。')
    )
    await db.commit()
    await db.refresh(search)


async def _response(db, search):
    await _sync_task_status(db, search)
    books = []
    if search.book_list_id:
        result = await db.execute(select(Book, ThemeBookEvidence).join(ThemeBookEvidence, ThemeBookEvidence.book_id == Book.id)
                                  .where(Book.book_list_id == search.book_list_id).order_by(Book.rank))
        for book, evidence in result:
            books.append({'id': book.id, 'title': book.title, 'author': book.author, 'isbn': book.isbn,
                          'catalog_url': book.source_url, 'reasoning': evidence.reasoning,
                          'evidence_excerpt': evidence.evidence_excerpt, 'evidence_url': evidence.evidence_url,
                          'author_country': evidence.author_country, 'author_evidence_excerpt': evidence.author_evidence_excerpt,
                          'author_evidence_url': evidence.author_evidence_url})
    return {'id': search.id, 'theme': search.theme, 'status': search.status, 'current_step': search.current_step,
            'error_message': search.error_message, 'books': books, 'created_at': search.created_at}


@router.post('/')
async def create_theme_search(request: ThemeSearchCreate, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    search = ThemeSearch(theme=request.theme, limit=request.limit, status='queued', user_id=user.id)
    db.add(search)
    await db.commit()
    await db.refresh(search)
    try:
        search.job_id = enqueue_theme_search(search.id)
        await db.commit()
        await db.refresh(search)
    except RedisError:
        search.status = 'failed'
        search.error_message = '无法连接任务队列，请检查 Redis 服务。'
        await db.commit()
        raise HTTPException(status_code=503, detail=search.error_message)
    return await _response(db, search)


@router.get('/latest')
async def latest_theme_search(db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    search = (await db.execute(select(ThemeSearch).where(ThemeSearch.user_id == user.id).order_by(ThemeSearch.id.desc()).limit(1))).scalar_one_or_none()
    return await _response(db, search) if search else None


@router.get('/{search_id}')
async def get_theme_search(search_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    search = await owned_search(db, search_id, user)
    if not search:
        raise HTTPException(status_code=404, detail='找书任务不存在。')
    return await _response(db, search)
