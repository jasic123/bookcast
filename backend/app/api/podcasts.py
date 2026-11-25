"""Queue and retrieve podcast drafting runs."""
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import current_user, owned_podcast, owned_research
from app.core.queue import creation_guard, enqueue_podcast, enqueue_podcast_audio
from app.models.podcast_run import PodcastRun
from app.models.research import Research
from app.models.user import SavedVoice, User
from app.services.podcast_audio import DEFAULT_VOICES, MAX_VOICE_SAMPLE_BYTES, create_custom_voice, script_segments, speaker_labels

router = APIRouter(prefix='/podcasts', tags=['podcasts'], dependencies=[Depends(current_user)])


class PodcastCreate(BaseModel):
    research_id: int
    speaker_count: int = Field(ge=1, le=4)
    language: Literal['zh', 'en'] = 'zh'
    theme: str = Field(default='', max_length=200)
    duration: int = Field(default=5, ge=2, le=20)
    style: str = Field(default='自然对谈', max_length=100)
    audience: str = Field(default='普通读者', max_length=100)
    reference_text: str = Field(default='', max_length=20000)


class PodcastAudioCreate(BaseModel):
    voices: dict[str, str]
    accept_review_issues: bool = False


class PodcastRevisionCreate(BaseModel):
    review_iteration: int
    issue_indices: list[int] = Field(min_length=1)


def _response(run):
    speakers = speaker_labels((run.request or {}).get('speaker_count', 2))
    return {'id': run.id, 'research_id': run.research_id, 'status': run.status,
            'language': (run.request or {}).get('language', 'zh'),
            'speaker_count': len(speakers), 'speakers': speakers,
            'current_step': run.current_step, 'error_message': run.error_message,
            'result': run.result, 'created_at': run.created_at,
            'audio_status': run.audio_status, 'audio_step': run.audio_step,
            'audio_error': run.audio_error,
            'audio_voices': run.audio_voices,
            'audio_url': f'/api/podcasts/{run.id}/audio?v={run.audio_file}' if run.audio_status == 'completed' and run.audio_file else
                         f'/api/podcasts/{run.id}/audio' if run.audio_status == 'completed' else None}


@router.post('/')
async def create_podcast(request: PodcastCreate, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    research = await owned_research(db, request.research_id, user)
    if not research:
        raise HTTPException(status_code=404, detail='研究记录不存在。')
    if research.status != 'completed':
        raise HTTPException(status_code=400, detail='请等待研究完成后再生成播客稿。')
    try:
        async with creation_guard(f'podcast:{research.id}'):
            existing = (await db.execute(select(PodcastRun).where(
                PodcastRun.research_id == research.id, PodcastRun.status.in_(['queued', 'running']),
            ).order_by(PodcastRun.id.desc()).limit(1))).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=409, detail={'message': '这项研究已有进行中的播客任务。', 'run_id': existing.id})
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
    except TimeoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RedisError:
        raise HTTPException(status_code=503, detail='无法连接任务队列，请检查 Redis 服务。')
    return _response(run)


@router.get('/research/{research_id}')
async def latest_podcast(research_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    await owned_research(db, research_id, user)
    run = (await db.execute(select(PodcastRun).where(PodcastRun.research_id == research_id).order_by(PodcastRun.id.desc()).limit(1))).scalar_one_or_none()
    return _response(run) if run else None


@router.post('/{run_id}/retry')
async def retry_podcast(run_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    run = await owned_podcast(db, run_id, user)
    if not run:
        raise HTTPException(status_code=404, detail='播客任务不存在。')
    if run.status != 'failed':
        raise HTTPException(status_code=409, detail='只有失败的播客任务可以续跑。')
    try:
        async with creation_guard(f'podcast:{run.research_id}'):
            existing = (await db.execute(select(PodcastRun).where(
                PodcastRun.research_id == run.research_id, PodcastRun.status.in_(['queued', 'running']),
                PodcastRun.id != run.id,
            ).limit(1))).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=409, detail={'message': '该研究已有进行中的播客任务。', 'run_id': existing.id})
            run.status = 'queued'
            run.error_message = None
            run.completed_at = None
            run.current_step = '正在从最近检查点续跑'
            await db.commit()
            try:
                enqueue_podcast(run.id)
            except RedisError as error:
                run.status = 'failed'
                run.error_message = '无法连接任务队列，请检查 Redis 服务。'
                await db.commit()
                raise HTTPException(status_code=503, detail=run.error_message) from error
    except TimeoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _response(run)


@router.post('/{run_id}/revise')
async def revise_podcast(run_id: int, request: PodcastRevisionCreate, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    run = await owned_podcast(db, run_id, user)
    if not run:
        raise HTTPException(status_code=404, detail='播客任务不存在。')
    try:
        async with creation_guard(f'podcast:{run.research_id}'):
            await db.refresh(run)
            result = run.result or {}
            reviews = result.get('reviews') or []
            drafts = result.get('drafts') or []
            if run.status != 'needs_revision' or not drafts or not reviews:
                raise HTTPException(status_code=409, detail='请等待当前文稿完成评审后再选择修改意见。')
            existing = (await db.execute(select(PodcastRun).where(
                PodcastRun.research_id == run.research_id, PodcastRun.status.in_(['queued', 'running']),
                PodcastRun.id != run.id,
            ).limit(1))).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=409, detail={'message': '该研究已有进行中的播客任务。', 'run_id': existing.id})
            latest = reviews[-1]
            issues = latest.get('issues') or []
            indices = request.issue_indices
            if (request.review_iteration != latest.get('iteration') or
                    len(indices) != len(set(indices)) or
                    any(index < 0 or index >= len(issues) for index in indices)):
                raise HTTPException(status_code=400, detail='评审意见已变化，请刷新后重新选择。')
            if run.audio_status in ('queued', 'running'):
                raise HTTPException(status_code=409, detail='请等待当前配音任务结束后再修改文稿。')
            selected = [issues[index] for index in indices]
            checkpoint = {**result, 'decision': 'revise', 'checkpoint_stage': 'reviewed',
                          'feedback': {'iteration': latest['iteration'], 'issues': selected,
                                       'selected_by_user': True},
                          'manual_revision_target': len(drafts) + 1}
            run.result = checkpoint
            run.status = 'queued'
            run.current_step = '等待按所选评审意见修改'
            run.error_message = None
            run.completed_at = None
            run.audio_status = None
            run.audio_step = None
            run.audio_file = None
            await db.commit()
            try:
                enqueue_podcast(run.id)
            except RedisError as error:
                run.status = 'failed'
                run.error_message = '无法连接任务队列，请检查 Redis 服务。'
                await db.commit()
                raise HTTPException(status_code=503, detail=run.error_message) from error
    except TimeoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RedisError as error:
        raise HTTPException(status_code=503, detail='无法连接任务队列，请检查 Redis 服务。') from error
    return _response(run)


@router.post('/voices')
async def upload_voice_sample(
    sample: UploadFile = File(...),
    transcript: str = Form(...),
    name: str = Form(...),
    consent: bool = Form(False),
    language: Literal['zh', 'en'] = Form('zh'),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    if not consent:
        raise HTTPException(status_code=400, detail='请先确认录音属于本人或已获得声音所有者授权。')
    if sample.size and sample.size > MAX_VOICE_SAMPLE_BYTES:
        raise HTTPException(status_code=413, detail='录音不能超过 10 MB。')
    existing = (await db.execute(select(SavedVoice).where(
        SavedVoice.user_id == user.id, SavedVoice.name == name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail='音色名称已存在，请直接从音色库选择，或换一个名称。')
    data = await sample.read(MAX_VOICE_SAMPLE_BYTES + 1)
    if len(data) > MAX_VOICE_SAMPLE_BYTES:
        await sample.close()
        raise HTTPException(status_code=413, detail='录音不能超过 10 MB。')
    try:
        uri = await create_custom_voice(data, sample.filename or 'sample.wav',
                                        sample.content_type or '', transcript, name)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        await sample.close()
    db.add(SavedVoice(user_id=user.id, name=name, voice_id=uri, language=language))
    await db.commit()
    return {'voice_id': uri}


@router.get('/{run_id}')
async def get_podcast(run_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    run = await owned_podcast(db, run_id, user)
    if not run:
        raise HTTPException(status_code=404, detail='播客任务不存在。')
    return _response(run)


@router.post('/{run_id}/audio')
async def create_podcast_audio(run_id: int, request: PodcastAudioCreate, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    run = await owned_podcast(db, run_id, user)
    if not run:
        raise HTTPException(status_code=404, detail='播客任务不存在。')
    reviews = (run.result or {}).get('reviews') or []
    if run.status not in ('completed', 'needs_revision') or not (run.result or {}).get('drafts') or not reviews:
        raise HTTPException(status_code=400, detail='请先完成播客文稿和评审。')
    if not reviews[-1].get('approved') and not request.accept_review_issues:
        raise HTTPException(status_code=400, detail='文稿未通过 AI 评审，请确认评审意见后再生成试听音频。')
    speakers = speaker_labels((run.request or {}).get('speaker_count', 2))
    try:
        script_segments((run.result or {}).get('drafts', [])[-1]['content'], speakers)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if set(request.voices) != set(speakers) or any(not request.voices[role].strip() or len(request.voices[role]) > 200 for role in speakers):
        raise HTTPException(status_code=400, detail='请为每位播客角色填写有效音色 ID。')
    saved_voices = (await db.execute(select(SavedVoice.voice_id).where(SavedVoice.user_id == user.id))).scalars().all()
    permitted = set(saved_voices) | set(DEFAULT_VOICES.values())
    if any(request.voices[role].strip() not in permitted for role in speakers):
        raise HTTPException(status_code=403, detail='只能使用当前账号保存的音色或默认音色。')
    if run.audio_status in ('queued', 'running'):
        raise HTTPException(status_code=409, detail='音频正在生成。')
    run.audio_status = 'queued'
    run.audio_step = '等待配音任务'
    run.audio_error = None
    run.audio_voices = {role: request.voices[role].strip() for role in speakers}
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
async def get_podcast_audio(run_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    run = await owned_podcast(db, run_id, user)
    if not run or (run.audio_status != 'completed' and not run.audio_file):
        raise HTTPException(status_code=404, detail='音频尚未生成。')
    filename = run.audio_file if run.audio_file and Path(run.audio_file).name == run.audio_file else f'podcast-{run_id}.wav'
    path = Path(__file__).resolve().parents[2] / 'generated_audio' / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail='音频文件不存在。')
    return FileResponse(path, media_type='audio/wav', filename=path.name, content_disposition_type='inline')
