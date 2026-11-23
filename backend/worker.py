"""RQ worker entry point.

Run this with:
    python worker.py

Or with multiple workers:
    rq worker research --url redis://localhost:6379/0
"""

import sys
import argparse
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from rq import Worker, SimpleWorker

from app.core.config import settings
from app.core.queue import redis_conn
from app.core.database import engine
from app.models.research import Research
from app.models.theme_search import ThemeSearch
from app.models.podcast_run import PodcastRun

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def mark_failed_job(job, exc_type, exc_value, traceback):
    """Keep API task status in sync when RQ aborts a job, including timeouts."""
    tasks = {
        'app.tasks.research_tasks.run_research_task': (Research, 'status', 'error_message'),
        'app.tasks.theme_search_tasks.run_theme_search_task': (ThemeSearch, 'status', 'error_message'),
        'app.tasks.podcast_tasks.run_podcast_task': (PodcastRun, 'status', 'error_message'),
        'app.tasks.podcast_audio_tasks.run_podcast_audio_task': (PodcastRun, 'audio_status', 'audio_error'),
    }
    task = tasks.get(job.func_name)
    if not task or not job.args:
        return True

    async def update():
        model, status_field, error_field = task
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sessions() as db:
            row = await db.get(model, job.args[0])
            if row and getattr(row, status_field) in ('queued', 'running'):
                setattr(row, status_field, 'failed')
                setattr(row, error_field, '后台任务超时或意外终止，请检查服务日志后重试。')
                await db.commit()

    try:
        asyncio.run(update())
    except Exception:
        logger.exception('Could not update failed job %s', job.id)
    return True


def main():
    """Start a dedicated RQ worker for research, podcast writing, or audio."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue', choices=('research', 'podcast', 'audio'), default='research')
    queue = parser.parse_args().queue
    logger.info("Starting RQ worker for %s queue", queue)
    logger.info(f"Redis URL: {settings.REDIS_URL}")

    # Create Redis connection

    # Create and start worker
    worker_class = SimpleWorker if sys.platform == "win32" else Worker
    worker = worker_class(
        [queue],
        connection=redis_conn,
        log_job_description=True,
        exception_handlers=[mark_failed_job],
    )

    worker.work(with_scheduler=sys.platform != "win32")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)
