"""Book-related schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class BookBase(BaseModel):
    """Base book schema."""
    title: str = Field(..., min_length=1, max_length=500)
    author: Optional[str] = Field(None, max_length=500)
    isbn: Optional[str] = Field(None, max_length=20)
    asin: Optional[str] = Field(None, max_length=20)
    rank: Optional[int] = Field(None, ge=1)
    description: Optional[str] = None
    source_url: Optional[str] = None
    platform_id: Optional[str] = Field(None, max_length=100)


class BookCreate(BookBase):
    """Schema for creating a book."""
    pass


class BookResponse(BookBase):
    """Schema for book response."""
    id: int
    book_list_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class BookListBase(BaseModel):
    """Base book list schema."""
    name: str = Field(..., min_length=1, max_length=255)
    source_type: str = Field(..., min_length=1, max_length=50)
    source_url: Optional[str] = None
    list_date: Optional[datetime] = None


class BookListCreate(BookListBase):
    """Schema for creating a book list."""
    books: List[BookCreate] = Field(default_factory=list)


class BookListResponse(BookListBase):
    """Schema for book list response."""
    id: int
    fetched_at: datetime
    created_at: datetime
    books: List[BookResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AmazonListFetchRequest(BaseModel):
    """Request to fetch Amazon bestseller list."""
    list_url: Optional[str] = Field(
        None,
        description="URL of Amazon bestseller list. If not provided, uses default."
    )
    list_name: str = Field(
        default="Amazon Best Sellers",
        description="Name to identify this list"
    )


class CSVUploadRequest(BaseModel):
    """Request to upload CSV book list."""
    csv_content: str = Field(..., description="CSV content as string")
    list_name: str = Field(..., description="Name to identify this list")
