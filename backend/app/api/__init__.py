"""API routes."""

from app.api.books import router as books_router
from app.api.research import router as research_router
# scripts router temporarily disabled due to import issues
# from app.api.scripts import router as scripts_router

__all__ = ["books_router", "research_router"]
