"""Background rendering of a reviewed script."""
import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import engine
from app.models.podcast_run import PodcastRun
from app.services.podcast_audio import render_audio

logger = logging.getLogger(__name__)


async def _run_podcast_audio_async(run_id):
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sessions() as db:
        run = await db.get(PodcastRun, run_id)
        if not run or run.audio_status != 'queued':
            return {'status': 'skipped', 'run_id': run_id}
        run.audio_status = 'running'
        await db.commit()
        try:
            async def on_step(step):
                run.audio_step = step
                await db.commit()

            draft = (run.result or {}).get('drafts', [])[-1]['content']
            await render_audio(draft, run_id, voices=run.audio_voices, on_step=on_step)
            run.audio_status = 'completed'
            run.audio_step = '音频已生成'
            await db.commit()
            return {'status': 'completed', 'run_id': run_id}
        except Exception as error:
            logger.exception('Podcast audio failed for run %s', run_id)
            run.audio_status = 'failed'
            run.audio_error = str(error)[:200]
            await db.commit()
            return {'status': 'failed', 'run_id': run_id}


def run_podcast_audio_task(run_id):
    return asyncio.run(_run_podcast_audio_async(run_id))
