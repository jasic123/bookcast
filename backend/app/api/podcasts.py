"""Queue and retrieve podcast drafting runs."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.queue import enqueue_podcast, enqueue_podcast_audio
from app.models.podcast_run import PodcastRun
from app.models.research import Research
from app.services.podcast_audio import DEFAULT_VOICES

router = APIRouter(prefix='/podcasts', tags=['podcasts'])


class PodcastCreate(BaseModel):
    research_id: int
    theme: str = Field(default='', max_length=200)
    duration: int = Field(default=5, ge=2, le=20)
    style: str = Field(default='自然对谈', max_length=100)
    audience: str = Field(default='普通读者', max_length=100)
    reference_text: str = Field(default='', max_length=20000)


class PodcastAudioCreate(BaseModel):
    host_voice: str = Field(default=DEFAULT_VOICES['主持人'], min_length=1, max_length=200)
    guest_voice: str = Field(default=DEFAULT_VOICES['嘉宾'], min_length=1, max_length=200)
    accept_review_issues: bool = False


def _response(run):
    return {'id': run.id, 'research_id': run.research_id, 'status': run.status,
            'current_step': run.current_step, 'error_message': run.error_message,
            'result': run.result, 'created_at': run.created_at,
            'audio_status': run.audio_status, 'audio_step': run.audio_step,
            'audio_error': run.audio_error,
            'audio_voices': run.audio_voices,
            'audio_url': f'/api/podcasts/{run.id}/audio' if run.audio_status == 'completed' else None}


@router.post('/')
async def create_podcast(request: PodcastCreate, db: AsyncSession = Depends(get_db)):
    research = await db.get(Research, request.research_id)
    if not research:
        raise HTTPException(status_code=404, detail='研究记录不存在。')
    if research.status != 'completed':
        raise HTTPException(status_code=400, detail='请等待研究完成后再生成播客稿。')
    run = PodcastRun(research_id=research.id, status='queued', request=request.model_dump(exclude={'research_id'}))
    db.add(run)
    await db.commit()
    await db.refresh(run)
    try:
        enqueue_podcast(run.id)
    except RedisError:
        run.status = 'failed'
        run.error_message = '无法连接任务队列，请检查 Redis 服务。'
        await db.commit()
        raise HTTPException(status_code=503, detail=run.error_message)
    return _response(run)


@router.get('/research/{research_id}')
async def latest_podcast(research_id: int, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(select(PodcastRun).where(PodcastRun.research_id == research_id).order_by(PodcastRun.id.desc()).limit(1))).scalar_one_or_none()
    return _response(run) if run else None


@router.get('/{run_id}')
async def get_podcast(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(PodcastRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail='播客任务不存在。')
    return _response(run)


@router.post('/{run_id}/audio')
async def create_podcast_audio(run_id: int, request: PodcastAudioCreate, db: AsyncSession = Depends(get_db)):
    run = await db.get(PodcastRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail='播客任务不存在。')
    reviews = (run.result or {}).get('reviews') or []
    if run.status not in ('completed', 'needs_revision') or not (run.result or {}).get('drafts') or not reviews:
        raise HTTPException(status_code=400, detail='请先完成播客文稿和评审。')
    if not reviews[-1].get('approved') and not request.accept_review_issues:
        raise HTTPException(status_code=400, detail='文稿未通过 AI 评审，请确认评审意见后再生成试听音频。')
    if run.audio_status in ('queued', 'running'):
        raise HTTPException(status_code=409, detail='音频正在生成。')
    run.audio_status = 'queued'
    run.audio_step = '等待配音任务'
    run.audio_error = None
    run.audio_voices = {'主持人': request.host_voice, '嘉宾': request.guest_voice}
    await db.commit()
    try:
        enqueue_podcast_audio(run_id)
    except RedisError:
        run.audio_status = 'failed'
        run.audio_error = '无法连接任务队列，请检查 Redis 服务。'
        await db.commit()
        raise HTTPException(status_code=503, detail=run.audio_error)
    return _response(run)


@router.get('/{run_id}/audio')
async def get_podcast_audio(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(PodcastRun, run_id)
    if not run or run.audio_status != 'completed':
        raise HTTPException(status_code=404, detail='音频尚未生成。')
    path = Path(__file__).resolve().parents[2] / 'generated_audio' / f'podcast-{run_id}.wav'
    if not path.is_file():
        raise HTTPException(status_code=404, detail='音频文件不存在。')
    return FileResponse(path, media_type='audio/wav', filename=path.name, content_disposition_type='inline')
