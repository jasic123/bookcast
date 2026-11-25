"""Book and BookList models."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class BookList(Base):
    """A collection of books from a specific source."""

    __tablename__ = "book_lists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    source_type = Column(String(50), nullable=False)  # amazon, csv, etc.
    source_url = Column(Text, nullable=True)
    list_date = Column(DateTime, nullable=True)  # When the list was published
    fetched_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    books = relationship("Book", back_populates="book_list", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_booklist_source", "source_type", "list_date"),
    )


class Book(Base):
    """A book from a bestseller list."""

    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    book_list_id = Column(Integer, ForeignKey("book_lists.id"), nullable=False)

    # Basic information
    title = Column(String(500), nullable=False)
    author = Column(String(500), nullable=True)
    isbn = Column(String(20), nullable=True)
    asin = Column(String(20), nullable=True)  # Amazon ASIN, separate from ISBN

    # List information
    rank = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)

    # Source information
    source_url = Column(Text, nullable=True)
    platform_id = Column(String(100), nullable=True)  # Platform-specific identifier

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    book_list = relationship("BookList", back_populates="books")
    researches = relationship("Research", back_populates="book", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_book_title_author", "title", "author"),
        Index("idx_book_isbn", "isbn"),
        Index("idx_book_asin", "asin"),
    )


class BookTopics(Base):
    """AI-generated preliminary topics for a book."""
    __tablename__ = "book_topics"

    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True)
    topics = Column(JSON, nullable=False)
