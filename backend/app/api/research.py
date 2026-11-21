"""Research API routes."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from redis.exceptions import RedisError
from typing import List
import json
import re
import asyncio
import logging

from app.core.database import get_db
from app.core.queue import enqueue_research, get_job_status
from app.models.research import Research, ThemeMatch, Source, SourceType, ReviewDigest, ReviewArticle
from app.models.book import Book
from app.schemas.research import ResearchCreate, ResearchResponse
from app.services.llm_client import LLMClient

router = APIRouter(prefix="/research", tags=["research"])
logger = logging.getLogger(__name__)


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
            selectinload(Research.theme_matches).selectinload(ThemeMatch.details), selectinload(Research.sources),
            selectinload(Research.material_assessment),
        ).where(Research.id == research_id)
    )
    research = result.scalar_one_or_none()

    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    return research


@router.get("/{research_id}/reviews")
async def get_review_digest(research_id: int, db: AsyncSession = Depends(get_db)):
    """Summarize identifiable reviews using only collected source content."""
    research = await db.get(Research, research_id)
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    if research.status != "completed":
        raise HTTPException(status_code=400, detail="研究完成后才能整理书评。")
    cached = await db.get(ReviewDigest, research_id)
    if cached:
        return {"reviews": cached.reviews, "incomplete": False}
    book = await db.get(Book, research.book_id)
    sources = (await db.execute(select(Source).where(
        Source.research_id == research_id, Source.is_duplicate == 0,
        Source.is_about_target_book == 1,
    ).order_by(Source.id))).scalars().all()
    candidates = [s for s in sources if s.cleaned_content and (
        s.source_type in (SourceType.PROFESSIONAL_REVIEW, SourceType.READER_REVIEW)
        or "review" in s.title.lower() or "书评" in s.title
    )]
    client = LLMClient()
    semaphore = asyncio.Semaphore(3)

    async def summarize(source):
        payload = {"id": source.id, "title": source.title, "text": source.cleaned_content[:2000]}
        prompt = '根据资料用中文概括这篇书评的观点，仅依据资料，不得编造。如果不是目标书籍的书评或没有足够内容则跳过。只输出JSON对象：{"summary":"简短概述","points":["要点"]}；跳过时输出 {"summary":"","points":[]}。'
        async with semaphore:
            for _ in range(2):
                try:
                    response = await asyncio.wait_for(client.chat_completion([
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": json.dumps({"book": book.title, "author": book.author, "source": payload}, ensure_ascii=False)},
                    ], temperature=0.2, max_tokens=600), timeout=60)
                    item = json.loads(response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
                    if not isinstance(item, dict) or not isinstance(item.get("summary"), str):
                        raise ValueError("Invalid review response")
                    if not item["summary"].strip():
                        return None
                    points = item.get("points", [])
                    if not isinstance(points, list):
                        points = []
                    return {"source_id": source.id, "title": source.title, "url": source.url,
                        "basis": "page" if source.fetch_status == "fetched" else "search_snippet",
                        "summary": item["summary"].strip(),
                        "points": [p.strip() for p in points if isinstance(p, str) and p.strip()][:3]}
                except Exception:
                    logger.warning("Could not summarize review source %s", source.id)
            return False

    results = await asyncio.gather(*(summarize(source) for source in candidates))
    reviews = [item for item in results if isinstance(item, dict)]
    incomplete = any(item is False for item in results)
    if not incomplete:
        db.add(ReviewDigest(research_id=research_id, reviews=reviews))
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            cached = await db.get(ReviewDigest, research_id)
            if cached:
                return {"reviews": cached.reviews, "incomplete": False}
            raise
    return {"reviews": reviews, "incomplete": incomplete}


@router.post("/{research_id}/review-article")
async def create_review_article(research_id: int, db: AsyncSession = Depends(get_db)):
    """Synthesize collected reviews and retain source attribution."""
    research = await db.get(Research, research_id)
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    if research.status != "completed":
        raise HTTPException(status_code=400, detail="研究完成后才能生成综合书评。")
    cached = await db.get(ReviewArticle, research_id)
    if cached and cached.article.get("version") == 3:
        return cached.article
    digest = await db.get(ReviewDigest, research_id)
    if not digest or not digest.reviews:
        raise HTTPException(status_code=400, detail="请先完成书评整理；可用书评不足时无法生成。")
    book = await db.get(Book, research.book_id)
    sources = digest.reviews[:12]
    permitted = {str(item["source_id"]): item for item in sources}
    source_rows = (await db.execute(select(Source).where(Source.id.in_([x["source_id"] for x in sources])))).scalars().all()
    excerpts = {row.id: (row.cleaned_content or "")[:1600] for row in source_rows}
    payload = {"book": book.title, "author": book.author,
               "reviews": [{"source_id": x["source_id"], "basis": x["basis"], "summary": x["summary"],
                            "points": x["points"], "excerpt": excerpts.get(x["source_id"], "")} for x in sources]}
    sections = [
        ("作品与背景", "介绍书籍与故事背景，说明已有资料覆盖什么；不要虚构情节。"),
        ("主题与人物", "分析评论中有依据的主题和人物选择，解释其意义；不要推断资料没有支持的细节。"),
        ("写作特色与评论", "比较书评对叙事、人物和写作手法的具体评价；只有资料明确提及才能写批评或分歧。"),
        ("综合评价与讨论", "结合评论总结阅读价值与讨论问题，并明确指出资料不足和需要核实的地方。"),
    ]
    client = LLMClient()
    async def write_section(section):
        heading, instruction = section
        prompt = ('你是书评编辑，只使用提供的书评摘要、观点和摘录写中文综合书评的一个章节。'
                  '区分评论意见与事实，避免重复和空话，不要假装读过原书，不得编造情节、引文、评论、分歧或来源。'
                  '每章必须写两段，每章不少于450个汉字。用具体分析展开观点，比较多个来源的共同点与差异；每段约200至300字。证据不足时明确写出哪些观点无法判断，但仍须具体说明已有来源能支持什么、不能支持什么，禁止用重复套话补字数。'
                  '搜索摘要不是原文全文，不能据此声称已读全文。每一段必须列出支持该段的来源 source_id。'
                  '仅输出 JSON 对象：{"paragraphs":[{"text":"一段中文","source_ids":[1,2]}]}，不要输出其他内容；只引用提供的 id。')
        for _ in range(2):
            try:
                response = await asyncio.wait_for(client.chat_completion([
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps({"section": heading, "instruction": instruction, **payload}, ensure_ascii=False)},
                ], temperature=0.2, max_tokens=2200), timeout=90)
                cleaned = response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                cleaned = re.sub(r'([,{]\s*)source_ids\s*:', r'\1"source_ids":', cleaned)
                data = json.loads(cleaned)
                if not isinstance(data, dict) or not isinstance(data.get("paragraphs"), list):
                    raise ValueError("Invalid section")
                paragraphs = []
                for part in data["paragraphs"]:
                    if not isinstance(part, dict) or not isinstance(part.get("text"), str) or not part["text"].strip() or not isinstance(part.get("source_ids"), list):
                        raise ValueError("Invalid paragraph")
                    ids = list(dict.fromkeys(str(value) for value in part["source_ids"]))
                    ids = [value for value in ids if value in permitted]
                    if not ids:
                        raise ValueError("Invalid source reference")
                    paragraphs.append({"text": part["text"].strip(), "source_ids": [int(value) for value in ids], "section": heading})
                if sum(len(part["text"]) for part in paragraphs) < 80:
                    raise ValueError("Section is too short")
                return paragraphs
            except Exception as error:
                logger.warning("Could not generate review section for research %s: %s", research_id, type(error).__name__)
        summary = "；".join(item["summary"] for item in sources[:5] if item.get("summary"))
        if not summary:
            raise ValueError("No source summaries available")
        source_ids = [item["source_id"] for item in sources[:5] if item.get("summary")]
        return [{"text": f"本章资料有限，暂不能形成充分的深入分析。现有书评资料提到：{summary}。这些内容只能作为后续阅读和核实的线索。", "source_ids": source_ids, "section": heading}]
    chunks = await asyncio.gather(*(write_section(section) for section in sections), return_exceptions=True)
    paragraphs = [part for chunk in chunks if isinstance(chunk, list) for part in chunk]
    if not paragraphs:
        raise HTTPException(status_code=502, detail="综合书评生成失败，请重试。")
    cited_ids = {i for part in paragraphs for i in part["source_ids"]}
    article = {"version": 3, "title": f"《{book.title}》综合书评", "paragraphs": paragraphs,
               "sources": [{"source_id": item["source_id"], "title": item["title"], "url": item["url"], "basis": item["basis"]} for item in sources if item["source_id"] in cited_ids]}
    if cached:
        cached.article = article
    else:
        db.add(ReviewArticle(research_id=research_id, article=article))
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        existing = await db.get(ReviewArticle, research_id)
        if existing and existing.article.get("version") == 3:
            return existing.article
        raise
    return article


@router.get("/book/{book_id}", response_model=List[ResearchResponse])
async def list_research_for_book(
    book_id: int,
    db: AsyncSession = Depends(get_db)
):
    """List all research sessions for a book."""
    result = await db.execute(
        select(Research)
        .options(selectinload(Research.theme_matches).selectinload(ThemeMatch.details), selectinload(Research.sources),
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
