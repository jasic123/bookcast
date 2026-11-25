import asyncio
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.book import Book, BookList
from app.models.research import Research, Source, SourceType, MaterialAssessment
from app.services.goodreads import select_book
from app.services.research_orchestrator import ResearchOrchestrator


def test_book_selection_rejects_summary_wrong_author_and_wrong_volume():
    books = [
        {"bookId": "1", "title": "Summary of The Nightingale", "author": {"name": "Kristin Hannah"}},
        {"bookId": "2", "title": "The Nightingale", "author": {"name": "Other Author"}},
        {"bookId": "3", "title": "The Nightingale", "author": {"name": "Kristin Hannah"}},
    ]
    assert select_book(books, "The Nightingale: A Novel", "Kristin Hannah")["bookId"] == "3"
    assert select_book(books[:2], "The Nightingale: A Novel", "Kristin Hannah") is None
    assert select_book([{"bookId": "4", "title": "Dog Man: Big Jim Begins", "author": {"name": "Dav Pilkey"}}], "Dog Man: A Sprinkle in Time", "Dav Pilkey") is None


def test_reader_review_is_saved_and_counted_without_fetching_page():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            listing = BookList(user_id=1, name='test', source_type='csv')
            db.add(listing)
            await db.flush()
            book = Book(book_list_id=listing.id, title='The Nightingale', author='Kristin Hannah')
            db.add(book)
            await db.flush()
            research = Research(book_id=book.id, themes=['war'], match_mode='any', status='queued')
            db.add(research)
            await db.commit()
            orchestrator = ResearchOrchestrator(db)
            orchestrator.theme_screener.screen_book_for_themes = AsyncMock(return_value=[{'theme': 'war', 'status': 'candidate', 'reasoning': 'Evidence'}])
            orchestrator.material_searcher.search_materials = AsyncMock(return_value=[])
            orchestrator.material_searcher.fetch_content = AsyncMock()
            orchestrator.llm_client.assess_material_sufficiency = AsyncMock(return_value={'overall_assessment': 'insufficient', 'reasoning': 'Limited'})
            review = {'title': 'Goodreads 读者评论：Alice（4/5）', 'url': 'https://www.goodreads.com/review/show/123', 'content': 'A reader opinion', 'rating': 4}
            with patch('app.services.research_orchestrator.open_library_book', new_callable=AsyncMock, return_value=None), patch('app.services.research_orchestrator.search_goodreads_reviews', new_callable=AsyncMock, return_value=[review]):
                result = await orchestrator.conduct_research(research.id)
            assert result['status'] == 'completed', result
            source = (await db.execute(select(Source))).scalar_one()
            assert source.source_type == SourceType.READER_REVIEW
            assert source.cleaned_content == review['content'] and source.fetch_status == 'fetched'
            assert (await db.execute(select(MaterialAssessment))).scalar_one().independent_review_count == 1
            orchestrator.material_searcher.fetch_content.assert_not_awaited()
        await engine.dispose()
    asyncio.run(check())
