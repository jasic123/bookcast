"""Research API routes."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from redis.exceptions import RedisError
from typing import List

from app.core.database import get_db
from app.core.queue import enqueue_research, get_job_status
from app.models.research import Research
from app.models.book import Book
from app.schemas.research import ResearchCreate, ResearchResponse

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/", response_model=dict)
async def create_research(
    request: ResearchCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new research session for a book.

    The research will run in the background via RQ task queue.
    Use GET /research/{id} to check progress.

    Returns:
        research_id: The ID of the created research
        job_id: RQ job ID for status tracking
        status: Current status
    """
    # Verify book exists
    result = await db.execute(
        select(Book).where(Book.id == request.book_id)
    )
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Create research
    research = Research(
        book_id=request.book_id,
        themes=request.themes,
        match_mode=request.match_mode,
        status="queued",
    )
    db.add(research)
    await db.commit()
    await db.refresh(research)

    # Enqueue research task in RQ
    try:
        job_id = enqueue_research(research.id)
    except RedisError:
        research.status = "failed"
        research.error_message = "无法连接任务队列，请检查 Redis 服务。"
        await db.commit()
        raise HTTPException(status_code=503, detail=research.error_message)

    return {
        "research_id": research.id,
        "job_id": job_id,
        "status": "queued",
        "message": "Research task queued successfully"
    }


@router.get("/{research_id}", response_model=ResearchResponse)
async def get_research(research_id: int, db: AsyncSession = Depends(get_db)):
    """Get research status and results."""
    result = await db.execute(
        select(Research).options(
            selectinload(Research.theme_matches), selectinload(Research.sources),
            selectinload(Research.material_assessment),
        ).where(Research.id == research_id)
    )
    research = result.scalar_one_or_none()

    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    return research


@router.get("/book/{book_id}", response_model=List[ResearchResponse])
async def list_research_for_book(
    book_id: int,
    db: AsyncSession = Depends(get_db)
):
    """List all research sessions for a book."""
    result = await db.execute(
        select(Research)
        .options(selectinload(Research.theme_matches), selectinload(Research.sources),
                 selectinload(Research.material_assessment))
        .where(Research.book_id == book_id)
        .order_by(Research.created_at.desc())
    )
    researches = result.scalars().all()
    return researches


@router.get("/job/{job_id}", response_model=dict)
async def get_job_status_endpoint(job_id: str):
    """
    Get the status of a background research job.

    Returns job status including:
    - queued: Job is waiting to be processed
    - started: Job is currently running
    - finished: Job completed successfully
    - failed: Job failed with an error
    """
    return get_job_status(job_id)
