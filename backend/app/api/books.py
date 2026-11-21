"""Book list API routes."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
import json
import logging

from app.core.database import get_db
from app.models.book import Book, BookList, BookTopics
from app.schemas.book import (
    BookListCreate,
    BookListResponse,
    BookResponse,
    AmazonListFetchRequest,
    CSVUploadRequest,
)
from app.services.book_fetcher import BookFetcherService
from app.services.llm_client import LLMClient

router = APIRouter(prefix="/books", tags=["books"])
logger = logging.getLogger(__name__)


@router.post("/lists/amazon", response_model=BookListResponse)
async def fetch_amazon_list(
    request: AmazonListFetchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Fetch books from Amazon bestseller list."""
    fetcher = BookFetcherService()

    books, source_url, error, list_date = await fetcher.fetch_amazon_list(
        list_url=request.list_url,
        list_name=request.list_name
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    if not books:
        raise HTTPException(
            status_code=404,
            detail="No books found. Amazon structure may have changed."
        )

    # Create book list
    book_list = BookList(
        name=request.list_name,
        source_type="amazon",
        source_url=source_url,
        list_date=list_date,
    )
    db.add(book_list)
    await db.commit()
    await db.refresh(book_list)

    # Add books
    for book_data in books:
        book = Book(
            book_list_id=book_list.id,
            title=book_data.title,
            author=book_data.author,
            isbn=book_data.isbn,
            asin=book_data.asin,
            rank=book_data.rank,
            description=book_data.description,
            source_url=book_data.source_url,
            platform_id=book_data.platform_id,
        )
        db.add(book)

    await db.commit()

    # Reload with books
    result = await db.execute(
        select(BookList).options(selectinload(BookList.books)).where(BookList.id == book_list.id)
    )
    book_list = result.scalar_one()

    return book_list


@router.post("/lists/csv", response_model=BookListResponse)
async def upload_csv_list(
    request: CSVUploadRequest,
    db: AsyncSession = Depends(get_db)
):
    """Upload books from CSV."""
    fetcher = BookFetcherService()

    books, error = await fetcher.parse_csv(
        csv_content=request.csv_content,
        list_name=request.list_name
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    if not books:
        raise HTTPException(status_code=400, detail="No valid books found in CSV")

    # Create book list
    book_list = BookList(
        name=request.list_name,
        source_type="csv",
    )
    db.add(book_list)
    await db.commit()
    await db.refresh(book_list)

    # Add books
    for book_data in books:
        book = Book(
            book_list_id=book_list.id,
            title=book_data.title,
            author=book_data.author,
            isbn=book_data.isbn,
            rank=book_data.rank,
            description=book_data.description,
        )
        db.add(book)

    await db.commit()

    # Reload with books
    result = await db.execute(
        select(BookList).options(selectinload(BookList.books)).where(BookList.id == book_list.id)
    )
    book_list = result.scalar_one()

    return book_list


@router.get("/lists", response_model=List[BookListResponse])
async def list_book_lists(db: AsyncSession = Depends(get_db)):
    """List all book lists."""
    result = await db.execute(
        select(BookList).options(selectinload(BookList.books)).order_by(BookList.created_at.desc())
    )
    book_lists = result.scalars().all()
    return book_lists


@router.get("/lists/{list_id}", response_model=BookListResponse)
async def get_book_list(list_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific book list with its books."""
    result = await db.execute(
        select(BookList).options(selectinload(BookList.books)).where(BookList.id == list_id)
    )
    book_list = result.scalar_one_or_none()

    if not book_list:
        raise HTTPException(status_code=404, detail="Book list not found")

    return book_list


@router.post("/lists/{list_id}/topics")
async def classify_book_topics(list_id: int, db: AsyncSession = Depends(get_db)):
    """Return cached preliminary topics and classify books that lack them."""
    book_list = (await db.execute(
        select(BookList).options(selectinload(BookList.books)).where(BookList.id == list_id)
    )).scalar_one_or_none()
    if not book_list:
        raise HTTPException(status_code=404, detail="Book list not found")
    book_ids = [book.id for book in book_list.books]
    cached = (await db.execute(select(BookTopics).where(BookTopics.book_id.in_(book_ids)))).scalars().all()
    topics = {row.book_id: row.topics for row in cached}
    missing = [book for book in book_list.books if book.id not in topics]
    if missing:
        client = LLMClient()
        try:
            for start in range(0, len(missing), 5):
                batch = missing[start:start + 5]
                data = [{"id": b.id, "title": b.title, "author": b.author,
                         "description": (b.description or "")[:500]} for b in batch]
                response = await client.chat_completion([
                    {"role": "system", "content": '根据书名、作者和简介为每本书提供一到三个简短中文主题标签，不确定请标注“待确认”。必须按下面格式给每本书返回一条记录，保留原始 id，禁止省略：{"books":[{"id":1,"topics":["科普"]}]}。仅输出 JSON，不要添加 Markdown。'},
                    {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
                ], temperature=0.2, max_tokens=1500)
                parsed = json.loads(response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
                if isinstance(parsed, dict) and isinstance(parsed.get("books"), list):
                    parsed = {str(item.get("id")): item.get("topics") for item in parsed["books"] if isinstance(item, dict)}
                if not isinstance(parsed, dict):
                    raise ValueError("Invalid topic response")
                for book in batch:
                    values = parsed.get(str(book.id))
                    if not isinstance(values, list):
                        continue
                    labels = [v.strip()[:30] for v in values if isinstance(v, str) and v.strip() and v.strip() != "待确认"][:3]
                    topics[book.id] = labels
                    db.add(BookTopics(book_id=book.id, topics=labels))
                await db.commit()
        except Exception:
            logger.exception("Book topic classification failed")
            await db.rollback()
            raise HTTPException(status_code=502, detail="主题分类暂时失败，请稍后重试。")
    return {str(book_id): labels for book_id, labels in topics.items()}


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific book."""
    result = await db.execute(
        select(Book).where(Book.id == book_id)
    )
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    return book
