"""Background theme-first book discovery."""
import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import engine
from app.models.book import Book, BookList
from app.models.theme_search import ThemeBookEvidence, ThemeSearch
from app.services.theme_discovery import discover_theme_books

logger = logging.getLogger(__name__)


async def _run_theme_search_async(search_id):
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sessions() as db:
        search = await db.get(ThemeSearch, search_id)
        if not search:
            return {'status': 'failed', 'error': 'Theme search not found'}
        try:
            search.status = 'running'
            await db.commit()

            async def on_step(step):
                search.current_step = step
                await db.commit()

            books = await discover_theme_books(search.theme, search.limit, on_step=on_step)
            listing = BookList(name=f'主题：{search.theme}'[:255], source_type='theme')
            db.add(listing)
            await db.flush()
            for index, item in enumerate(books, 1):
                book = Book(book_list_id=listing.id, title=item['title'], author=item['author'],
                            isbn=item.get('isbn'), rank=index, description=None, source_url=item['catalog_url'])
                db.add(book)
                await db.flush()
                db.add(ThemeBookEvidence(book_id=book.id, reasoning=item['reason'],
                    evidence_excerpt=item['evidence_excerpt'], evidence_url=item['evidence_url'],
                    author_country=item['author_country'], author_evidence_excerpt=item['author_evidence_excerpt'],
                    author_evidence_url=item['author_evidence_url']))
            search.book_list_id = listing.id
            search.status = 'completed'
            search.current_step = '找书完成' if books else '未找到充分核实的强关联书籍'
            search.completed_at = datetime.utcnow()
            await db.commit()
            return {'status': 'completed', 'search_id': search.id, 'count': len(books)}
        except Exception as error:
            logger.exception('Theme search failed for %s', search_id)
            await db.rollback()
            search = await db.get(ThemeSearch, search_id)
            if search:
                search.status = 'failed'
                search.error_message = '主题找书失败：' + str(error)[:200]
                search.completed_at = datetime.utcnow()
                await db.commit()
            return {'status': 'failed', 'search_id': search_id}


def run_theme_search_task(search_id):
    return asyncio.run(_run_theme_search_async(search_id))
