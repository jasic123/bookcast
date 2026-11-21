"""RQ worker entry point.

Run this with:
    python worker.py

Or with multiple workers:
    rq worker research --url redis://localhost:6379/0
"""

import sys
import logging
from rq import Worker, SimpleWorker

from app.core.config import settings
from app.core.queue import redis_conn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Start the RQ worker."""
    logger.info("Starting RQ worker for research queue")
    logger.info(f"Redis URL: {settings.REDIS_URL}")

    # Create Redis connection

    # Create and start worker
    worker_class = SimpleWorker if sys.platform == "win32" else Worker
    worker = worker_class(
        ["research"],
        connection=redis_conn,
        log_job_description=True,
        exception_handlers=[],  # Can add custom exception handlers here
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
