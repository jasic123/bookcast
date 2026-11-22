"""Redis Queue configuration for background tasks."""

from redis import Redis
from rq import Queue
from app.core.config import settings


# Create Redis connection
redis_conn = Redis.from_url(
    settings.REDIS_URL,
    protocol=2
)

# Create RQ queue
research_queue = Queue(
    "research",
    connection=redis_conn,
    default_timeout=settings.MAX_TASK_EXECUTION_TIME
)


def enqueue_research(research_id: int) -> str:
    """
    Enqueue a research task.

    Args:
        research_id: ID of the research to run

    Returns:
        Job ID
    """
    from app.tasks.research_tasks import run_research_task

    job = research_queue.enqueue(
        run_research_task,
        research_id,
        job_timeout=settings.MAX_TASK_EXECUTION_TIME,
        result_ttl=3600,  # Keep result for 1 hour
        failure_ttl=86400,  # Keep failed job for 24 hours
    )

    return job.id


def enqueue_podcast(run_id: int) -> str:
    from app.tasks.podcast_tasks import run_podcast_task

    job = research_queue.enqueue(
        run_podcast_task, run_id,
        job_timeout=max(settings.MAX_TASK_EXECUTION_TIME, 1200),
        result_ttl=3600, failure_ttl=86400,
    )
    return job.id


def enqueue_podcast_audio(run_id: int) -> str:
    from app.tasks.podcast_audio_tasks import run_podcast_audio_task

    job = research_queue.enqueue(
        run_podcast_audio_task, run_id,
        job_timeout=3600, result_ttl=3600, failure_ttl=86400,
    )
    return job.id


def enqueue_theme_search(search_id: int) -> str:
    from app.tasks.theme_search_tasks import run_theme_search_task

    job = research_queue.enqueue(
        run_theme_search_task, search_id,
        job_timeout=max(settings.MAX_TASK_EXECUTION_TIME, 1200),
        result_ttl=3600, failure_ttl=86400,
    )
    return job.id


def get_job_status(job_id: str) -> dict:
    """
    Get the status of a job.

    Args:
        job_id: RQ job ID

    Returns:
        Dictionary with job status information
    """
    from rq.job import Job

    try:
        job = Job.fetch(job_id, connection=redis_conn)

        return {
            "job_id": job.id,
            "status": job.get_status(),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            "result": job.result,
            "exc_info": job.exc_info,
        }
    except Exception as e:
        return {
            "job_id": job_id,
            "status": "unknown",
            "error": str(e)
        }
