"""Theme-first book discovery API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.queue import enqueue_theme_search
from app.models.book import Book
from app.models.theme_search import ThemeBookEvidence, ThemeSearch

router = APIRouter(prefix='/theme-search', tags=['theme-search'])


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


async def _response(db, search):
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
async def create_theme_search(request: ThemeSearchCreate, db: AsyncSession = Depends(get_db)):
    search = ThemeSearch(theme=request.theme, limit=request.limit, status='queued')
    db.add(search)
    await db.commit()
    await db.refresh(search)
    try:
        enqueue_theme_search(search.id)
    except RedisError:
        search.status = 'failed'
        search.error_message = '无法连接任务队列，请检查 Redis 服务。'
        await db.commit()
        raise HTTPException(status_code=503, detail=search.error_message)
    return await _response(db, search)


@router.get('/latest')
async def latest_theme_search(db: AsyncSession = Depends(get_db)):
    search = (await db.execute(select(ThemeSearch).order_by(ThemeSearch.id.desc()).limit(1))).scalar_one_or_none()
    return await _response(db, search) if search else None


@router.get('/{search_id}')
async def get_theme_search(search_id: int, db: AsyncSession = Depends(get_db)):
    search = await db.get(ThemeSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='找书任务不存在。')
    return await _response(db, search)
