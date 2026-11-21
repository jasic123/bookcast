"""Script generation and validation API routes."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.database import get_db
from app.models.research import Research
from app.models.book import Book
from app.models.script import PodcastScript
from app.schemas.script import (
    ScriptValidationRequest,
    ScriptValidationResponse,
    ScriptSection,
    ScriptGenerationRequest,
    ScriptGenerationResponse,
)
from app.services.script_validator import PodcastScriptValidator
from app.services.script_generator import PodcastScriptGenerator

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.post("/validate", response_model=ScriptValidationResponse)
async def validate_script(request: ScriptValidationRequest):
    """
    Validate if a podcast script is sufficient for 20-30 minute audio.

    Analyzes:
    - Word count and estimated duration
    - Section structure and balance
    - Content depth indicators

    Returns detailed assessment with recommendations.
    """
    validator = PodcastScriptValidator(speaking_rate=request.speaking_rate)
    analysis = validator.validate(request.script_content)
    report = validator.format_report(analysis)

    return ScriptValidationResponse(
        total_words=analysis.total_words,
        total_chars=analysis.total_chars,
        estimated_minutes=analysis.estimated_minutes,
        is_sufficient=analysis.is_sufficient,
        sections=[ScriptSection(**s) for s in analysis.sections],
        issues=analysis.issues,
        recommendations=analysis.recommendations,
        report=report,
    )


@router.post("/generate", response_model=ScriptGenerationResponse)
async def generate_script(
    request: ScriptGenerationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a podcast script from completed research.

    Requirements:
    - Research must be completed
    - Research must have sufficient materials
    - Book information must be available

    Returns generated script with validation results.
    """
    # Load research
    result = await db.execute(
        select(Research).where(Research.id == request.research_id)
    )
    research = result.scalar_one_or_none()

    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    if research.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Research is not completed (status: {research.status})"
        )

    # Load book
    result = await db.execute(
        select(Book).where(Book.id == research.book_id)
    )
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Prepare research data
    theme_matches = [
        {
            "theme": tm.theme,
            "status": tm.status.value,
            "reasoning": tm.reasoning,
        }
        for tm in research.theme_matches
    ]

    sources = [
        {
            "title": s.title,
            "source_type": s.source_type.value,
            "summary": s.summary,
            "key_points": s.key_points,
            "is_about_target": bool(s.is_about_target_book),
        }
        for s in research.sources
        if not s.is_duplicate
    ]

    material_assessment = {}
    if research.material_assessment:
        ma = research.material_assessment
        material_assessment = {
            "total_unique_sources": ma.total_unique_sources,
            "professional_review_count": ma.professional_review_count,
            "independent_review_count": ma.independent_review_count,
        }

    # Generate script
    generator = PodcastScriptGenerator()
    result = await generator.generate_and_validate(
        book_title=book.title,
        book_author=book.author,
        book_description=book.description,
        theme_matches=theme_matches,
        sources=sources,
        material_assessment=material_assessment,
        language=request.language,
        style=request.style,
        target_duration=request.target_duration,
        include_sections=request.include_sections,
    )

    # Save script
    script = PodcastScript(
        research_id=research.id,
        language=request.language,
        style=request.style,
        target_duration=request.target_duration,
        content=result["content"],
        word_count=result["word_count"],
        estimated_minutes=result["estimated_minutes"],
        is_sufficient=result["is_sufficient"],
        validation_issues=result["validation_issues"],
    )
    db.add(script)
    await db.commit()
    await db.refresh(script)

    return ScriptGenerationResponse(
        script_id=script.id,
        research_id=script.research_id,
        language=script.language,
        content=script.content,
        word_count=script.word_count,
        estimated_minutes=script.estimated_minutes,
        is_sufficient=bool(script.is_sufficient),
        validation_report=result["validation_report"],
        generated_at=script.generated_at,
    )


@router.get("/{script_id}", response_model=ScriptGenerationResponse)
async def get_script(script_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve a generated script by ID."""
    result = await db.execute(
        select(PodcastScript).where(PodcastScript.id == script_id)
    )
    script = result.scalar_one_or_none()

    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    # Generate validation report
    validator = PodcastScriptValidator()
    analysis = validator.validate(script.content)
    report = validator.format_report(analysis)

    return ScriptGenerationResponse(
        script_id=script.id,
        research_id=script.research_id,
        language=script.language,
        content=script.content,
        word_count=script.word_count,
        estimated_minutes=script.estimated_minutes,
        is_sufficient=bool(script.is_sufficient),
        validation_report=report,
        generated_at=script.generated_at,
    )


@router.get("/research/{research_id}")
async def list_scripts_for_research(
    research_id: int,
    db: AsyncSession = Depends(get_db)
):
    """List all scripts generated for a research."""
    result = await db.execute(
        select(PodcastScript)
        .where(PodcastScript.research_id == research_id)
        .order_by(PodcastScript.generated_at.desc())
    )
    scripts = result.scalars().all()

    return [
        {
            "script_id": s.id,
            "language": s.language,
            "style": s.style,
            "word_count": s.word_count,
            "estimated_minutes": s.estimated_minutes,
            "is_sufficient": bool(s.is_sufficient),
            "generated_at": s.generated_at,
        }
        for s in scripts
    ]
