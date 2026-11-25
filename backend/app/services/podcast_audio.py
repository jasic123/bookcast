"""Render role-labelled scripts into a playable WAV episode."""
import asyncio
import audioop
import hashlib
import io
import json
import re
import time
import uuid
import wave
from pathlib import Path

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI

from app.core.config import settings

DEFAULT_VOICES = {
    '主持人': 'FunAudioLLM/CosyVoice2-0.5B:bella',
    '嘉宾': 'FunAudioLLM/CosyVoice2-0.5B:anna',
}
TTS_BATCH_SIZE = 3
TTS_TURN_LENGTH = 120
ENGLISH_TURN_LENGTH = 240
MAX_VOICE_SAMPLE_BYTES = 10 * 1024 * 1024
VOICE_SAMPLE_TYPES = {'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav'}


def tts_pronunciation(text, rules=None):
    """Apply a user's spoken forms without changing the displayed script."""
    for original, spoken in sorted(rules or [], key=lambda pair: len(pair[0]), reverse=True):
        before = r'(?<![A-Za-z0-9])' if original[0].isascii() and original[0].isalnum() else ''
        after = r'(?![A-Za-z0-9])' if original[-1].isascii() and original[-1].isalnum() else ''
        text = re.sub(before + re.escape(original) + after,
                      lambda _: spoken, text, flags=re.I)
    return text


def speaker_labels(count: int) -> list[str]:
    if count not in (1, 2, 3, 4):
        raise ValueError('播客人数必须为 1–4 人。')
    if count == 1:
        return ['主持人']
    if count == 2:
        return ['主持人', '嘉宾']
    return ['主持人'] + [f'嘉宾{index}' for index in range(1, count)]


async def create_custom_voice(sample: bytes, filename: str, mime_type: str, transcript: str, name: str, *, client=None):
    """Send an authorized sample to SiliconFlow and return its voice URI."""
    if not sample or len(sample) > MAX_VOICE_SAMPLE_BYTES or mime_type not in VOICE_SAMPLE_TYPES:
        raise ValueError('请上传不超过 10 MB 的 MP3 或 WAV 录音。')
    if not 1 <= len(transcript.strip()) <= 500:
        raise ValueError('请填写与录音一致的示例文字（最多 500 字）。')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,30}', name):
        raise ValueError('音色名称只能使用 1–30 个英文字母、数字、下划线或连字符。')
    key = settings.TTS_API_KEY or (settings.LLM_API_KEY if 'siliconflow' in settings.LLM_BASE_URL else '')
    if not key:
        raise ValueError('请先配置 SiliconFlow 的 TTS_API_KEY。')
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=90)
    try:
        response = await client.post(
            settings.TTS_BASE_URL.rstrip('/') + '/uploads/audio/voice',
            headers={'Authorization': f'Bearer {key}'},
            data={'model': settings.TTS_MODEL, 'customName': name, 'text': transcript.strip()},
            files={'file': (filename, sample, mime_type)},
        )
        if response.is_error:
            raise ValueError(f'音色创建失败（服务端 HTTP {response.status_code}）；请检查录音时长、格式和余额。')
        voice = response.json().get('uri')
        if not isinstance(voice, str) or not voice:
            raise ValueError('语音服务未返回音色 ID。')
        return voice
    finally:
        if owns_client:
            await client.aclose()


def script_segments(script, speakers=None):
    """Keep every spoken line in short, naturally punctuated TTS turns."""
    speakers = speaker_labels(2) if speakers is None else speakers
    role_pattern = '|'.join(re.escape(role) for role in sorted(speakers, key=len, reverse=True))
    turns = []
    current_speaker = None
    for line_number, line in enumerate(script.splitlines(), 1):
        match = re.match(rf'^\s*({role_pattern})\s*[：:]\s*(.+)', line)
        if match:
            speaker, content = match.groups()
            current_speaker = speaker
        else:
            stripped = line.strip()
            if not stripped or re.match(r'^#{1,6}\s', stripped) or \
                    re.fullmatch(r'[（(].*[）)]', stripped) or \
                    re.fullmatch(r'(?:\[\d+\])+', stripped) or \
                    re.fullmatch(r'\[\d+(?:\s*[,，、]\s*\d+)*\]', stripped):
                continue
            if current_speaker is None or re.match(r'^(?:[\u4e00-\u9fff]{1,12}|(?:Host|Guest|Narrator|Speaker)\d*)\s*[：:]', stripped, re.I):
                raise ValueError(f'文稿第 {line_number} 行无法分配角色：{stripped[:80]}')
            speaker, content = current_speaker, stripped
        content = re.sub(r'\[\d+\]', '', content).strip()
        if not content:
            continue
        turn_length = TTS_TURN_LENGTH if re.search(r'[\u3400-\u9fff]', content) else ENGLISH_TURN_LENGTH
        while len(content) > turn_length:
            cut = max(content.rfind(mark, 0, turn_length + 1) for mark in '。！？；.!?;') + 1
            if cut < 40:
                cut = max(content.rfind(mark, 0, turn_length + 1) for mark in '，、,') + 1
            if cut < 40:
                # Keep English words intact when the turn has little punctuation.
                space = content.rfind(' ', 40, turn_length + 1)
                cut = space + 1 if space >= 40 else turn_length
            turns.append((speaker, content[:cut].strip()))
            content = content[cut:].strip()
        if content:
            turns.append((speaker, content))
    if not turns or {speaker for speaker, _ in turns} != set(speakers):
        raise ValueError('文稿需要以下角色的台词：' + '、'.join(speakers))
    return turns


def join_wav(chunks, destination, speakers=None):
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
                if index and (speakers is None or speakers[index] != speakers[index - 1]):
                    output.writeframes(b'\0' * (current[0] * current[1] * current[2] // 4))
                frames = segment.readframes(segment.getnframes())
                rms = audioop.rms(frames, current[1])
                peak = audioop.max(frames, current[1])
                if rms and peak:
                    ceiling = (2 ** (current[1] * 8 - 1)) - 1
                    gain = min(3.0, 0.13 * ceiling / rms, 0.95 * ceiling / peak)
                    frames = audioop.mul(frames, current[1], gain)
                output.writeframes(frames)
    return destination


async def render_audio(script, run_id, *, voices=None, speakers=None, pronunciation_rules=None, client=None, on_step=None):
    speakers = speaker_labels(2) if speakers is None else speakers
    voices = voices or DEFAULT_VOICES
    if not all(voices.get(role) for role in speakers):
        raise ValueError('请为每位播客角色选择音色。')
    key = settings.TTS_API_KEY or (settings.LLM_API_KEY if 'siliconflow' in settings.LLM_BASE_URL else '')
    if not key and client is None:
        raise ValueError('请配置 TTS_API_KEY 后再生成音频。')
    client = client or AsyncOpenAI(api_key=key, base_url=settings.TTS_BASE_URL, timeout=60, max_retries=0)
    output_dir = Path(__file__).resolve().parents[2] / 'generated_audio'
    output_dir.mkdir(exist_ok=True)
    cache_dir = output_dir / 'segments'
    cache_dir.mkdir(exist_ok=True)
    cutoff = time.time() - 7 * 86400
    for cached in cache_dir.glob('*.wav'):
        try:
            if cached.stat().st_mtime < cutoff:
                cached.unlink()
        except (FileNotFoundError, PermissionError):
            pass
    destination = output_dir / f'podcast-{run_id}-{uuid.uuid4().hex}.wav'
    temporary = destination.with_suffix('.part.wav')
    turns = script_segments(script, speakers)
    limiter = asyncio.Semaphore(TTS_BATCH_SIZE)
    progress_lock = asyncio.Lock()
    chunks = [b''] * len(turns)
    completed = 0

    async def synthesize(index, speaker, content):
        nonlocal completed
        spoken = tts_pronunciation(content, pronunciation_rules)
        cache_key = hashlib.sha256(json.dumps([settings.TTS_MODEL, voices[speaker], spoken], ensure_ascii=False).encode()).hexdigest()
        cache_file = cache_dir / f'{cache_key}.wav'
        async with limiter:
            if cache_file.is_file():
                chunks[index] = cache_file.read_bytes()
            else:
                for attempt in range(3):
                    try:
                        response = await asyncio.wait_for(client.audio.speech.create(
                            model=settings.TTS_MODEL, voice=voices[speaker], input=spoken, response_format='wav',
                        ), timeout=90)
                        with wave.open(io.BytesIO(response.content), 'rb') as wav:
                            if not wav.getnframes():
                                raise ValueError('语音服务返回了空音频。')
                        chunks[index] = response.content
                        temporary_cache = cache_dir / f'{cache_key}.{uuid.uuid4().hex}.part'
                        temporary_cache.write_bytes(response.content)
                        try:
                            temporary_cache.replace(cache_file)
                        except PermissionError:
                            if not cache_file.is_file():
                                raise
                            temporary_cache.unlink(missing_ok=True)
                        break
                    except (APIConnectionError, APIStatusError, asyncio.TimeoutError) as error:
                        if isinstance(error, APIStatusError) and error.status_code < 500 or attempt == 2:
                            raise
                        await asyncio.sleep(2 ** attempt)
        async with progress_lock:
            completed += 1
            if on_step and (completed % TTS_BATCH_SIZE == 0 or completed == len(turns)):
                await on_step(f'配音：已完成 {completed}/{len(turns)} 段')

    tasks = [asyncio.create_task(synthesize(index, speaker, content))
             for index, (speaker, content) in enumerate(turns)]
    try:
        await asyncio.gather(*tasks)
    except Exception:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    try:
        join_wav(chunks, temporary, [speaker for speaker, _ in turns])
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination
