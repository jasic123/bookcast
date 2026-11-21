"""Book list API routes."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.core.database import get_db
from app.models.book import Book, BookList
from app.schemas.book import (
    BookListCreate,
    BookListResponse,
    BookResponse,
    AmazonListFetchRequest,
    CSVUploadRequest,
)
from app.services.book_fetcher import BookFetcherService

router = APIRouter(prefix="/books", tags=["books"])


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
