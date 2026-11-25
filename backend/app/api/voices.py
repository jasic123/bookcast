"""Saved custom voices and per-user pronunciation overrides."""
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user
from app.core.database import get_db
from app.models.user import PronunciationRule, SavedVoice, User

router = APIRouter(prefix='/voices', tags=['voices'], dependencies=[Depends(current_user)])


class RuleInput(BaseModel):
    original: str = Field(min_length=1, max_length=80)
    spoken: str = Field(min_length=1, max_length=120)


class LegacyVoiceInput(BaseModel):
    voice_id: str = Field(min_length=1, max_length=200)


@router.get('')
async def list_voices(db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    rows = (await db.execute(select(SavedVoice).where(SavedVoice.user_id == user.id)
                             .order_by(SavedVoice.id.desc()))).scalars().all()
    return [{'id': row.id, 'name': row.name, 'voice_id': row.voice_id,
             'language': row.language} for row in rows]


@router.post('/restore')
async def restore_voice(data: LegacyVoiceInput, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    from app.models.book import Book, BookList
    from app.models.research import Research
    from app.models.podcast_run import PodcastRun

    voice_id = data.voice_id.strip()
    if not voice_id.startswith('speech:'):
        raise HTTPException(status_code=400, detail='只有历史自制音色可以恢复。')
    existing = (await db.execute(select(SavedVoice).where(SavedVoice.user_id == user.id,
        SavedVoice.voice_id == voice_id))).scalar_one_or_none()
    if existing:
        return {'id': existing.id, 'name': existing.name, 'voice_id': existing.voice_id, 'language': existing.language}
    runs = (await db.execute(select(PodcastRun.audio_voices, PodcastRun.request)
        .join(Research, PodcastRun.research_id == Research.id)
        .join(Book, Research.book_id == Book.id).join(BookList, Book.book_list_id == BookList.id)
        .where(BookList.user_id == user.id, PodcastRun.audio_voices.is_not(None)))).all()
    matching = next(((request or {}).get('language', 'zh') for mapping, request in runs
                     if voice_id in (mapping or {}).values()), None)
    if matching is None:
        raise HTTPException(status_code=404, detail='当前账号没有使用过此音色。')
    row = SavedVoice(user_id=user.id, name=f'restored_{secrets.token_hex(4)}', voice_id=voice_id,
                     language=matching if matching in ('zh', 'en') else 'zh')
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {'id': row.id, 'name': row.name, 'voice_id': row.voice_id, 'language': row.language}


@router.delete('/saved/{voice_id}')
async def delete_voice(voice_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    voice = await db.get(SavedVoice, voice_id)
    if not voice or voice.user_id != user.id:
        raise HTTPException(status_code=404, detail='音色不存在。')
    await db.delete(voice)
    await db.commit()
    return {'ok': True}


@router.get('/pronunciations')
async def list_rules(db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    rows = (await db.execute(select(PronunciationRule).where(PronunciationRule.user_id == user.id)
                             .order_by(PronunciationRule.id))).scalars().all()
    return [{'id': row.id, 'original': row.original, 'spoken': row.spoken} for row in rows]


@router.post('/pronunciations')
async def save_rule(data: RuleInput, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    original, spoken = data.original.strip(), data.spoken.strip()
    if not original or not spoken or original.casefold() == spoken.casefold() or not re.fullmatch(r'[\w -]+', original):
        raise HTTPException(status_code=422, detail='请填写有效的原词和替代读法。')
    row = (await db.execute(select(PronunciationRule).where(
        PronunciationRule.user_id == user.id, PronunciationRule.original == original))).scalar_one_or_none()
    if row:
        row.spoken = spoken
    else:
        row = PronunciationRule(user_id=user.id, original=original, spoken=spoken)
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return {'id': row.id, 'original': row.original, 'spoken': row.spoken}


@router.delete('/pronunciations/{rule_id}')
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)):
    row = await db.get(PronunciationRule, rule_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail='读音规则不存在。')
    await db.delete(row)
    await db.commit()
    return {'ok': True}
