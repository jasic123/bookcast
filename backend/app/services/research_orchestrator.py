"""Research orchestrator - coordinates the entire research workflow."""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.book import Book
from app.models.research import (
    Research, ThemeMatch, ThemeMatchDetails, Source, MaterialAssessment,
    MatchStatus, SourceType, SufficiencyLevel
)
from app.services.theme_screener import ThemeScreenerService
from app.services.material_searcher import MaterialSearcherService
from app.services.llm_client import LLMClient
from app.services.goodreads import search_reviews as search_goodreads_reviews
from app.services.book_sources import open_library_book, gutenberg_excerpts
from app.services.research_agents import run_specialist
from app.core.config import settings

logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    """Orchestrates the entire book research workflow."""

    def __init__(self, db: AsyncSession, progress_callback: Optional[Callable] = None):
        self.db = db
        self.progress_callback = progress_callback
        self.theme_screener = ThemeScreenerService()
        self.material_searcher = MaterialSearcherService()
        self.llm_client = LLMClient()

    async def _update_progress(
        self,
        research: Research,
        progress: float,
        step: str,
        message: Optional[str] = None
    ):
        """Update research progress and notify via callback."""
        research.progress = progress
        research.current_step = step
        await self.db.commit()

        if self.progress_callback:
            await self.progress_callback({
                "research_id": research.id,
                "status": research.status,
                "progress": progress,
                "current_step": step,
                "message": message,
            })

    async def conduct_research(self, research_id: int) -> Dict[str, Any]:
        """
        Conduct full research for a book.

        Workflow:
        1. Fetch book details
        2. Screen themes (initial assessment)
        3. Search for materials
        4. Fetch and classify sources
        5. Detect duplicates
        6. Assess material sufficiency
        7. Generate final recommendations

        Returns research results summary.
        """
        # Load research and book
        result = await self.db.execute(
            select(Research).where(Research.id == research_id)
        )
        research = result.scalar_one_or_none()
        if not research:
            return {"error": "Research not found"}

        result = await self.db.execute(
            select(Book).where(Book.id == research.book_id)
        )
        book = result.scalar_one_or_none()
        if not book:
            return {"error": "Book not found"}

        try:
            research.status = "running"
            await self.db.commit()

            async def catalog_agent(payload):
                return await open_library_book(payload["title"], payload["author"])

            try:
                catalog = await asyncio.wait_for(run_specialist(
                    "catalog_agent", "核对书籍身份并收集图书馆资料",
                    {"title": book.title, "author": book.author}, catalog_agent,
                ), timeout=45)
            except Exception as error:
                logger.warning("Open Library unavailable: %s", type(error).__name__)
                catalog = None

            # Step 1: Theme screening (20%)
            await self._update_progress(research, 0.1, "Screening themes")

            async def theme_agent(payload):
                return await self.theme_screener.screen_book_for_themes(
                    book_title=payload["title"], book_author=payload["author"],
                    book_description=payload["description"], themes=payload["themes"],
                )

            theme_matches = await run_specialist(
                "theme_agent", "基于证据筛选主题", {"title": book.title, "author": book.author,
                "description": book.description or (catalog or {}).get("description"), "themes": research.themes}, theme_agent,
            ) if research.themes else []

            # Save theme matches
            for tm in theme_matches:
                theme_match = ThemeMatch(
                    research_id=research.id,
                    theme=tm["theme"],
                    status=MatchStatus(tm["status"]),
                    reasoning=tm["reasoning"],
                    supporting_sources=tm.get("source_indices"),
                    evidence_quotes=tm.get("evidence"),
                )
                theme_match.details = ThemeMatchDetails(
                    suggested_themes=tm.get("suggested_themes", []),
                    search_sources=tm.get("search_sources", []),
                )
                self.db.add(theme_match)

            await self.db.commit()
            await self._update_progress(research, 0.2, "Theme screening completed")

            # Check if any theme is a candidate
            is_candidate, _ = self.theme_screener.aggregate_matches(
                theme_matches, research.match_mode
            ) if research.themes else (True, '整本书研究，不筛选主题')

            # A theme mismatch is a research finding, not a reason to skip
            # general book materials needed for a separate review.
            # Step 2: Search for materials (40%)
            await self._update_progress(research, 0.3, "Searching for materials")

            async def discovery_agent(payload):
                web, readers, text = await asyncio.gather(
                    self.material_searcher.search_materials(book_title=payload["title"], book_author=payload["author"], themes=payload["themes"]),
                    search_goodreads_reviews(payload["title"], payload["author"]),
                    gutenberg_excerpts(payload["title"], payload["gutenberg_ids"]),
                    return_exceptions=True,
                )
                if isinstance(web, Exception):
                    raise web
                if isinstance(readers, Exception):
                    logger.warning("Goodreads reader reviews unavailable: %s", type(readers).__name__)
                    readers = []
                if isinstance(text, Exception):
                    logger.warning("Gutenberg excerpts unavailable: %s", type(text).__name__)
                    text = None
                results = web[:20] + [dict(r, goodreads_review=True) for r in readers]
                if payload.get("catalog"):
                    results.append(dict(payload["catalog"], book_source_kind="catalog"))
                if text:
                    results.append(dict(text, book_source_kind="excerpt"))
                return results

            search_results = await run_specialist(
                "discovery_agent", "收集专业书评、读者反馈与原文节选",
                {"title": book.title, "author": book.author, "themes": research.themes,
                 "gutenberg_ids": (catalog or {}).get("gutenberg_ids", []), "catalog": catalog}, discovery_agent,
            )

            await self._update_progress(
                research, 0.4,
                f"Found {len(search_results)} potential sources"
            )

            # Step 3: Fetch and classify sources (70%)
            sources_data = []
            for idx, result in enumerate(search_results):
                progress = 0.4 + (idx / len(search_results)) * 0.3
                await self._update_progress(
                    research, progress,
                    f"Analyzing source {idx+1}/{len(search_results)}"
                )

                # Create source record
                source = Source(
                    research_id=research.id,
                    title=result.get("title", "Untitled"),
                    url=result.get("url", ""),
                    source_type=SourceType.OTHER,
                    fetch_status="pending",
                )
                self.db.add(source)
                await self.db.commit()  # Get source ID

                # Goodreads supplies the individual review text directly.
                if result.get("goodreads_review"):
                    source.source_type = SourceType.READER_REVIEW
                    source.source_classification_reasoning = "Goodreads 用户发布的读者评论"
                    source.is_about_target_book = True
                    source.book_identity_reasoning = "书名和作者与 Goodreads 图书记录匹配"
                    source.fetch_status = "fetched"
                    source.fetched_at = datetime.utcnow()
                    source.raw_content = result["content"][:10000]
                    source.cleaned_content = result["content"][:5000]
                    await self.db.commit()
                    continue

                if result.get("book_source_kind"):
                    is_catalog = result["book_source_kind"] == "catalog"
                    source.source_type = SourceType.ENCYCLOPEDIA if is_catalog else SourceType.OTHER
                    source.source_classification_reasoning = "图书馆书目信息" if is_catalog else "公版书原文节选，并非完整正文"
                    source.is_about_target_book = True
                    source.book_identity_reasoning = "已核对作品书名和作者"
                    source.fetch_status = "fetched"
                    source.fetched_at = datetime.utcnow()
                    source.raw_content = result["content"][:15000]
                    source.cleaned_content = result["content"][:15000]
                    source.summary = result.get("description") if is_catalog else f"原文共约 {result['total_chars']} 字符，本研究取得 {result['excerpt_count']} 段节选，并非全文。"
                    await self.db.commit()
                    continue

                # Fetch full content
                content, error = await self.material_searcher.fetch_content(result["url"])

                if error:
                    source.fetch_status = "failed"
                    source.fetch_error = error
                    source.raw_content = result.get("content", "")  # Use search snippet
                    content_to_analyze = result.get("content", "")
                else:
                    source.fetch_status = "fetched"
                    source.fetched_at = datetime.utcnow()
                    source.raw_content = content[:10000]  # Store first 10k chars
                    content_to_analyze = content[:5000]  # Analyze first 5k

                # Classify and analyze
                if content_to_analyze:
                    try:
                        classification = await self.material_searcher.classify_and_analyze_source(
                            source_title=source.title,
                            source_url=source.url,
                            content=content_to_analyze,
                            book_title=book.title,
                            book_author=book.author,
                        )
                    except ValueError as error:
                        logger.warning('Source %s classification parse failed: %s', source.id, error)
                        source.fetch_status = 'parse_failed'
                        source.fetch_error = str(error)[:200]
                        source.is_about_target_book = None
                        source.cleaned_content = content_to_analyze
                        await self.db.commit()
                        continue

                    try:
                        source.source_type = SourceType(classification.get("source_type", "other"))
                    except ValueError:
                        source.source_type = SourceType.OTHER
                    source.source_classification_reasoning = classification.get("reasoning")
                    source.is_about_target_book = classification.get("is_about_target") is True
                    source.book_identity_reasoning = classification.get("identity_reasoning")
                    source.summary = classification.get("summary")
                    source.key_points = classification.get("key_points", [])
                    source.cleaned_content = content_to_analyze

                await self.db.commit()
                sources_data.append({
                    "id": source.id,
                    "source_type": source.source_type.value,
                    "is_about_target": source.is_about_target_book,
                })

            # Step 4: Detect duplicates (75%)
            await self._update_progress(research, 0.75, "Detecting duplicates")

            result = await self.db.execute(
                select(Source).where(Source.research_id == research.id)
            )
            sources = result.scalars().all()

            source_list = [{"url": s.url} for s in sources]
            duplicates = self.material_searcher.detect_duplicates(source_list)

            for dup_idx, orig_idx in duplicates:
                sources[dup_idx].is_duplicate = True
                sources[dup_idx].duplicate_of = sources[orig_idx].id

            await self.db.commit()
            await self._update_progress(
                research, 0.8,
                f"Found {len(duplicates)} duplicate sources"
            )

            # Step 5: Material assessment (90%)
            await self._update_progress(research, 0.85, "Assessing material sufficiency")

            # Count source types
            unique_sources = [s for s in sources if not s.is_duplicate and s.is_about_target_book]
            professional_reviews = sum(
                1 for s in unique_sources
                if s.source_type == SourceType.PROFESSIONAL_REVIEW
            )
            independent_reviews = sum(
                1 for s in unique_sources
                if s.source_type == SourceType.READER_REVIEW
            )

            # Check content availability
            has_plot = any(
                s.summary and len(s.summary) > 200
                for s in unique_sources
            )
            has_author_info = any(
                s.source_type == SourceType.AUTHOR_INTERVIEW
                for s in unique_sources
            )
            has_multiple_perspectives = len(unique_sources) >= 3

            # LLM assessment
            theme_result = await self.db.execute(
                select(ThemeMatch).where(ThemeMatch.research_id == research.id)
            )
            theme_data = [
                {
                    "theme": tm.theme,
                    "status": tm.status.value,
                    "reasoning": tm.reasoning,
                }
                for tm in theme_result.scalars().all()
            ]

            source_data = [
                {"source_type": s.source_type.value, "title": s.title,
                 "summary": (s.summary or "")[:400]}
                for s in unique_sources
            ]

            async def editor_agent(payload):
                return await self.llm_client.assess_material_sufficiency(
                    book_title=payload["title"], book_author=payload["author"],
                    theme_matches=payload["themes"], sources=payload["sources"],
                )

            if is_candidate:
                try:
                    assessment_result = await run_specialist(
                        "editor_agent", "评估证据和研究资料缺口",
                        {"title": book.title, "author": book.author, "themes": theme_data, "sources": source_data}, editor_agent,
                    )
                except Exception as error:
                    logger.warning("Research %s material assessment unavailable: %s", research.id, type(error).__name__)
                    assessment_result = {
                        "overall_assessment": "needs_review",
                        "reasoning": "资料已收集，但模型评估暂时不可用；请核对来源后再生成内容。",
                        "material_gaps": ["资料充分度尚未通过模型评估"] +
                                         (["缺少可核实的目标书籍资料"] if not unique_sources else []),
                        "suggested_searches": [],
                    }
            else:
                pending = any(tm["status"] == "pending" for tm in theme_matches)
                assessment_result = {
                    "overall_assessment": "needs_review" if pending else "no_theme_evidence",
                    "reasoning": ("部分主题证据不足，需进一步核实。" if pending else "当前检索资料未显示足够的主题匹配证据。") + " 已继续收集图书资料供一般书评使用。",
                    "material_gaps": ["指定主题的匹配证据不足"],
                    "suggested_searches": [],
                }

            # Create material assessment
            material_assessment = MaterialAssessment(
                research_id=research.id,
                book_identity_confirmed=len(unique_sources) > 0,
                has_plot_summary=has_plot,
                has_independent_reviews=independent_reviews > 0,
                has_author_background=has_author_info,
                has_multiple_perspectives=has_multiple_perspectives,
                professional_review_count=professional_reviews,
                independent_review_count=independent_reviews,
                total_unique_sources=len(unique_sources),
                source_diversity_score=min(1.0, len(set(s.source_type for s in unique_sources)) / 5),
                content_depth_score=min(1.0, len(unique_sources) / 10),
                identified_gaps=assessment_result.get("material_gaps", []),
                suggested_searches=assessment_result.get("suggested_searches", []),
            )
            self.db.add(material_assessment)

            # Update research with final assessment
            research.overall_assessment = SufficiencyLevel(
                assessment_result.get("overall_assessment", "needs_review")
            )
            research.assessment_reasoning = assessment_result.get("reasoning", "")
            research.material_gaps = assessment_result.get("material_gaps", [])
            research.status = "completed"
            research.completed_at = datetime.utcnow()
            research.progress = 1.0

            await self.db.commit()
            await self._update_progress(research, 1.0, "Research completed")

            return {
                "status": "completed",
                "assessment": research.overall_assessment.value,
                "reasoning": research.assessment_reasoning,
                "theme_matches": len(theme_matches),
                "unique_sources": len(unique_sources),
            }

        except Exception as e:
            research.status = "failed"
            research.error_message = str(e)
            await self.db.commit()
            return {"status": "failed", "error": str(e)}
