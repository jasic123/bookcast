"""Background tasks for research operations."""

import asyncio
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.core.database import engine
from app.models.research import Research
from app.services.research_orchestrator import ResearchOrchestrator


async def _run_research_async(research_id: int) -> Dict[str, Any]:
    """
    Run the research workflow asynchronously.

    Args:
        research_id: ID of the research to run

    Returns:
        Dictionary with research results
    """
    # Create a new async session for this task
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as db:
        # Fetch the research
        result = await db.execute(
            select(Research).where(Research.id == research_id)
        )
        research = result.scalar_one_or_none()

        if not research:
            return {
                "success": False,
                "error": f"Research {research_id} not found"
            }

        try:
            orchestrator = ResearchOrchestrator(db)
            return await orchestrator.conduct_research(research_id)
        except Exception as e:
            await db.rollback()
            research = await db.get(Research, research_id)
            research.status = "failed"
            research.error_message = str(e)
            await db.commit()
            return {"status": "failed", "research_id": research_id, "error": str(e)}



def run_research_task(research_id: int) -> Dict[str, Any]:
    """
    RQ task wrapper for running research.

    This is the entry point called by RQ workers.
    It wraps the async function to run in the event loop.

    Args:
        research_id: ID of the research to run

    Returns:
        Dictionary with research results
    """
    # Run the async function in a new event loop
    return asyncio.run(_run_research_async(research_id))
