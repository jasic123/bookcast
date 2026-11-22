"""Render two-speaker scripts into a playable WAV episode."""
import asyncio
import io
import re
import wave
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import settings

DEFAULT_VOICES = {
    '主持人': 'FunAudioLLM/CosyVoice2-0.5B:alex',
    '嘉宾': 'FunAudioLLM/CosyVoice2-0.5B:anna',
}
TTS_BATCH_SIZE = 3


def script_segments(script):
    """Keep every spoken line while splitting long turns at punctuation."""
    turns = []
    for line in script.splitlines():
        match = re.match(r'^\s*(主持人|嘉宾)\s*[：:]\s*(.+)', line)
        if not match:
            if line.strip():
                raise ValueError('文稿包含无法分配角色的台词，请先修正文稿。')
            continue
        speaker, content = match.groups()
        content = re.sub(r'\[\d+\]', '', content).strip()
        if not content:
            continue
        while len(content) > 900:
            cut = max(content.rfind(mark, 0, 900) for mark in '。！？；.!?;') + 1
            cut = cut if cut > 200 else 900
            turns.append((speaker, content[:cut].strip()))
            content = content[cut:].strip()
        if content:
            turns.append((speaker, content))
    if not turns or {speaker for speaker, _ in turns} != {'主持人', '嘉宾'}:
        raise ValueError('文稿需要主持人和嘉宾两种台词。')
    return turns


def join_wav(chunks, destination):
    params = None
    with wave.open(str(destination), 'wb') as output:
        for index, raw in enumerate(chunks):
            with wave.open(io.BytesIO(raw), 'rb') as segment:
                current = (segment.getnchannels(), segment.getsampwidth(), segment.getframerate())
                if params is None:
                    params = current
                    output.setnchannels(current[0])
                    output.setsampwidth(current[1])
                    output.setframerate(current[2])
                elif current != params:
                    raise ValueError('语音片段的采样参数不一致，无法合成。')
                if index:
                    output.writeframes(b'\0' * (current[0] * current[1] * current[2] // 4))
                output.writeframes(segment.readframes(segment.getnframes()))
    return destination


async def render_audio(script, run_id, *, voices=None, client=None, on_step=None):
    voices = voices or DEFAULT_VOICES
    if not all(voices.get(role) for role in ('主持人', '嘉宾')):
        raise ValueError('请为主持人和嘉宾分别选择音色。')
    key = settings.TTS_API_KEY or (settings.LLM_API_KEY if 'siliconflow' in settings.LLM_BASE_URL else '')
    if not key and client is None:
        raise ValueError('请配置 TTS_API_KEY 后再生成音频。')
    client = client or AsyncOpenAI(api_key=key, base_url=settings.TTS_BASE_URL, timeout=60)
    output_dir = Path(__file__).resolve().parents[2] / 'generated_audio'
    output_dir.mkdir(exist_ok=True)
    destination = output_dir / f'podcast-{run_id}.wav'
    temporary = output_dir / f'podcast-{run_id}.part.wav'
    turns = script_segments(script)
    async def synthesize(speaker, content):
        response = await asyncio.wait_for(client.audio.speech.create(
            model=settings.TTS_MODEL, voice=voices[speaker], input=content, response_format='wav',
        ), timeout=90)
        return response.content

    chunks = []
    for start in range(0, len(turns), TTS_BATCH_SIZE):
        batch = turns[start:start + TTS_BATCH_SIZE]
        chunks.extend(await asyncio.gather(*(synthesize(speaker, content) for speaker, content in batch)))
        if on_step:
            await on_step(f'配音：已完成 {len(chunks)}/{len(turns)} 段')
    try:
        join_wav(chunks, temporary)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination
