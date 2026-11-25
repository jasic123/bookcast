"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from sqlalchemy import text

from app.core.config import settings
from app.core.database import init_db
from app.core.database import engine
from app.core.queue import redis_conn
from rq import Worker
from app.services.podcast_audio import DEFAULT_VOICES
from app.api.books import router as books_router
from app.api.research import router as research_router
from app.api.podcasts import router as podcasts_router
from app.api.theme_search import router as theme_search_router
from app.api.auth import router as auth_router
from app.api.voices import router as voices_router
from app.core.auth import require_same_origin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)
@app.middleware('http')
async def same_origin_middleware(request, call_next):
    try:
        await require_same_origin(request)
    except Exception:
        return JSONResponse(status_code=403, content={'detail': '请求来源不可信。'})
    return await call_next(request)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(books_router, prefix="/api")
app.include_router(research_router, prefix="/api")
app.include_router(podcasts_router, prefix="/api")
app.include_router(theme_search_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(voices_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get('/api/config')
async def public_config():
    return {'default_voices': DEFAULT_VOICES}


@app.get('/health/deep')
@app.get('/api/health/deep', include_in_schema=False)
async def deep_health():
    checks = {}
    try:
        async def check_database():
            async with engine.connect() as conn:
                await conn.execute(text('SELECT 1'))
        await asyncio.wait_for(check_database(), timeout=3)
        checks['database'] = {'ok': True}
    except Exception as error:
        checks['database'] = {'ok': False, 'reason': type(error).__name__}

    try:
        def check_queue():
            redis_conn.ping()
            workers = Worker.all(connection=redis_conn)
            active = {queue.name for worker in workers if redis_conn.ttl(worker.key) > 0
                      for queue in worker.queues}
            return sorted(set(('research', 'podcast', 'audio')) - active)
        missing = await asyncio.wait_for(asyncio.to_thread(check_queue), timeout=3)
        checks['redis'] = {'ok': True}
        checks['workers'] = {'ok': not missing, 'missing': missing,
                             'reason': '缺少可用的 ' + ', '.join(missing) + ' Worker' if missing else None}
    except Exception as error:
        checks['redis'] = {'ok': False, 'reason': type(error).__name__}
        checks['workers'] = {'ok': False, 'reason': '无法读取 Worker 心跳'}
    healthy = all(item['ok'] for item in checks.values())
    return JSONResponse(status_code=200 if healthy else 503,
                        content={'status': 'healthy' if healthy else 'unhealthy', 'checks': checks})
