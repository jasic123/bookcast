"""Background execution for the podcast production graph."""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import engine
from app.models.book import Book
from app.models.podcast_run import PodcastRun
from app.models.research import Research, Source
from app.services.podcast_agents import run_podcast_flow

logger = logging.getLogger(__name__)


async def _run_podcast_async(run_id):
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sessions() as db:
        run = await db.get(PodcastRun, run_id)
        if not run:
            return {'status': 'failed', 'error': 'Podcast run not found'}
        try:
            run.status = 'running'
            await db.commit()
            research = await db.get(Research, run.research_id)
            book = await db.get(Book, research.book_id)
            rows = (await db.execute(select(Source).where(
                Source.research_id == research.id, Source.is_duplicate == 0, Source.is_about_target_book == 1,
            ).order_by(Source.id))).scalars().all()
            sources = [{'source_id': s.id, 'title': s.title, 'url': s.url,
                        'source_type': s.source_type.value, 'basis': 'page' if s.fetch_status == 'fetched' else 'search_snippet',
                        'summary': (s.summary or s.cleaned_content or '')[:1000],
                        'excerpt': (s.cleaned_content or '')[:1800], 'points': s.key_points or []}
                       for s in rows if s.summary or s.cleaned_content][:20]
            user_input = run.request or {}
            reference = (user_input.get('reference_text') or '').strip()
            if reference:
                sources.append({'source_id': max([s['source_id'] for s in sources] or [0]) + 1,
                                'title': '用户提供的参考文章', 'url': '', 'source_type': 'user_reference',
                                'basis': 'user_reference', 'summary': reference[:1000],
                                'excerpt': reference[:5000], 'points': []})
            if not sources:
                raise ValueError('没有可用资料，请重新研究或提供参考文章。')
            request = {'book': {'title': book.title, 'author': book.author},
                       'theme': user_input.get('theme') or book.title,
                       'speaker_count': user_input.get('speaker_count', 2),
                       'language': user_input.get('language', 'zh'),
                       'duration': user_input.get('duration', 5), 'style': user_input.get('style', '自然对谈'),
                       'audience': user_input.get('audience', '普通读者'), 'sources': sources}

            async def on_step(step):
                run.current_step = step
                await db.commit()

            async def on_checkpoint(_stage, checkpoint):
                run.result = checkpoint
                await db.commit()

            result = await run_podcast_flow(request, checkpoint=run.result, on_step=on_step,
                                            on_checkpoint=on_checkpoint)
            run.result = result
            run.status = 'completed' if result['decision'] == 'approved' else 'needs_revision'
            run.current_step = '评审通过' if run.status == 'completed' else '评审未通过，请选择修改意见或确认后试听'
            run.completed_at = datetime.utcnow()
            await db.commit()
            return {'status': run.status, 'run_id': run.id}
        except Exception as error:
            logger.exception('Podcast production failed for run %s', run_id)
            await db.rollback()
            run = await db.get(PodcastRun, run_id)
            if run:
                run.status = 'failed'
                run.error_message = '播客任务未能完成：' + str(error)[:200]
                run.completed_at = datetime.utcnow()
                await db.commit()
            return {'status': 'failed', 'run_id': run_id}


def run_podcast_task(run_id):
    return asyncio.run(_run_podcast_async(run_id))
