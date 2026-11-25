import asyncio
import io
import wave
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import APIStatusError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.services.podcast_audio import create_custom_voice, join_wav, render_audio, script_segments, speaker_labels, tts_pronunciation


def _wav(value):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(bytes([value, 0]) * 240)
    return buffer.getvalue()


def test_standalone_citation_line_is_not_a_speaker():
    script = '\u4e3b\u6301\u4eba\uff1aA claim.[238]\n[238][240][242]\n\u5609\u5bbe\uff1aA response.[240]'
    assert script_segments(script) == [('\u4e3b\u6301\u4eba', 'A claim.'), ('\u5609\u5bbe', 'A response.')]


def test_long_english_turn_splits_at_word_boundaries():
    sentence = 'This English sentence has several distinct words without punctuation '
    script = '主持人：' + sentence * 5
    turns = script_segments(script, ['主持人'])
    assert len(turns) > 1
    assert max(len(content) for _, content in turns) > 120
    assert ' '.join(content for _, content in turns) == script.split('：', 1)[1].strip()


def test_tested_pronunciations_change_only_tts_input():
    script = '主持人：A groundbreaking novel by Cixin Liu.'
    spoken = tts_pronunciation(script, [('groundbreaking', 'ground breaking'), ('Cixin Liu', 'Tsee shin Lyoo')])
    assert spoken == '主持人：A ground breaking novel by Tsee shin Lyoo.'
    assert script == '主持人：A groundbreaking novel by Cixin Liu.'
    assert tts_pronunciation('主持人：这本书讲述刘慈欣的故事。', [('刘慈欣', '刘磁心')]) == '主持人：这本书讲述刘磁心的故事。'


def test_wav_pause_only_when_speaker_changes(tmp_path):
    path = join_wav([_wav(1)] * 3, tmp_path / 'episode.wav', ['主持人', '主持人', '嘉宾'])
    with wave.open(str(path), 'rb') as audio:
        assert audio.getnframes() == 3 * 240 + 24000 // 4


def test_speech_calls_overlap_but_audio_keeps_script_order():
    async def check():
        active = peak = 0

        async def create(self, *, input, **kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            index = int(input.split(':', 1)[0])
            await asyncio.sleep(.04 if index == 1 else .005)
            active -= 1
            return type('Response', (), {'content': _wav(index)})()

        speech = type('Speech', (), {'create': create})()
        client = type('Client', (), {'audio': type('Audio', (), {'speech': speech})()})()
        nonce = uuid.uuid4().hex
        script = chr(10).join(f'{"主持人" if i % 2 else "嘉宾"}：{i}:{nonce}' for i in range(1, 5))
        path = await render_audio(script, 'async-test', client=client)
        try:
            with wave.open(str(path), 'rb') as audio:
                frames = audio.readframes(audio.getnframes())
            assert peak == 3
            assert [frames[i * 12480] for i in range(4)] == [3, 6, 9, 12]
        finally:
            path.unlink(missing_ok=True)

    asyncio.run(check())


def test_regeneration_does_not_replace_open_audio_file():
    async def check():
        calls = 0
        async def create(self, **kwargs):
            nonlocal calls
            calls += 1
            return type('Response', (), {'content': _wav(3)})()

        speech = type('Speech', (), {'create': create})()
        client = type('Client', (), {'audio': type('Audio', (), {'speech': speech})()})()
        nonce = uuid.uuid4().hex
        script = f'主持人：第一句{nonce}。\n嘉宾：第二句{nonce}。'
        first = await render_audio(script, 'repeat-test', client=client)
        try:
            with first.open('rb') as playing:
                second = await render_audio(script, 'repeat-test', client=client)
                try:
                    assert first != second
                    assert playing.read(4) == b'RIFF'
                    assert second.is_file()
                    assert calls == 2
                finally:
                    second.unlink(missing_ok=True)
        finally:
            first.unlink(missing_ok=True)

    asyncio.run(check())


def test_tts_retries_timeout_and_reuses_cached_segments():
    async def check():
        calls = {}
        async def create(self, *, input, **kwargs):
            calls[input] = calls.get(input, 0) + 1
            if input.startswith('first') and calls[input] == 1:
                raise asyncio.TimeoutError()
            return type('Response', (), {'content': _wav(7)})()

        speech = type('Speech', (), {'create': create})()
        client = type('Client', (), {'audio': type('Audio', (), {'speech': speech})()})()
        nonce = uuid.uuid4().hex
        script = f'主持人：first{nonce}\n嘉宾：second{nonce}'
        with patch('app.services.podcast_audio.asyncio.sleep', new_callable=AsyncMock):
            first = await render_audio(script, 'cache-test', client=client)
        second = await render_audio(script, 'cache-test', client=client)
        try:
            assert sum(calls.values()) == 3
            assert first != second
        finally:
            first.unlink(missing_ok=True)
            second.unlink(missing_ok=True)

    asyncio.run(check())


def test_tts_does_not_retry_client_error():
    async def check():
        calls = {}
        async def create(self, *, input, **kwargs):
            calls[input] = calls.get(input, 0) + 1
            response = httpx.Response(400, request=httpx.Request('POST', 'https://example.org/audio'))
            raise APIStatusError('bad request', response=response, body=None)

        speech = type('Speech', (), {'create': create})()
        client = type('Client', (), {'audio': type('Audio', (), {'speech': speech})()})()
        nonce = uuid.uuid4().hex
        with pytest.raises(APIStatusError):
            await render_audio(f'主持人：first{nonce}\n嘉宾：second{nonce}', 'client-error-test', client=client)
        assert calls and all(count == 1 for count in calls.values())

    asyncio.run(check())


def test_failed_tts_run_reuses_successful_segments_on_next_attempt():
    async def check():
        calls = {}
        fail = True
        async def create(self, *, input, **kwargs):
            calls[input] = calls.get(input, 0) + 1
            if input.startswith('second') and fail:
                raise asyncio.TimeoutError()
            return type('Response', (), {'content': _wav(7)})()

        speech = type('Speech', (), {'create': create})()
        client = type('Client', (), {'audio': type('Audio', (), {'speech': speech})()})()
        nonce = uuid.uuid4().hex
        script = f'主持人：first{nonce}\n嘉宾：second{nonce}'
        with patch('app.services.podcast_audio.asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(asyncio.TimeoutError):
                await render_audio(script, 'resume-test', client=client)
        assert calls[f'first{nonce}'] == 1
        assert calls[f'second{nonce}'] == 3
        fail = False
        path = await render_audio(script, 'resume-test', client=client)
        try:
            assert calls[f'first{nonce}'] == 1
            assert calls[f'second{nonce}'] == 4
        finally:
            path.unlink(missing_ok=True)

    asyncio.run(check())


def test_long_dialogue_splits_on_punctuation():
    script = '主持人：' + '这段话应该自然停顿，' * 14 + '\n嘉宾：确实如此。'
    turns = script_segments(script)
    assert len(turns) > 2
    assert all(len(text) <= 120 for _, text in turns)
    assert ''.join(text for speaker, text in turns if speaker == '主持人') == ('这段话应该自然停顿，' * 14)


def test_stage_directions_are_skipped_but_unknown_lines_report_location():
    script = '## 开场\n主持人：欢迎。[1]\n（此处停顿两秒）\n[1]\n嘉宾：你好。'
    assert script_segments(script) == [('主持人', '欢迎。'), ('嘉宾', '你好。')]
    with pytest.raises(ValueError, match='第 2 行.*无法分配角色'):
        script_segments('主持人：欢迎。\n旁白：突然响起音乐。\n嘉宾：你好。')


def test_unlabelled_paragraphs_continue_the_previous_speaker():
    script = '主持人：Opening.\n\nA longer explanation follows.\n嘉宾：Reply.\nAnother point.'
    assert script_segments(script) == [
        ('主持人', 'Opening.'), ('主持人', 'A longer explanation follows.'),
        ('嘉宾', 'Reply.'), ('嘉宾', 'Another point.'),
    ]


def test_solo_and_panel_audio_use_selected_roles_and_voices():
    async def check():
        calls = []

        async def create(self, *, voice, **kwargs):
            calls.append(voice)
            return type('Response', (), {'content': _wav(5)})()

        speech = type('Speech', (), {'create': create})()
        client = type('Client', (), {'audio': type('Audio', (), {'speech': speech})()})()
        nonce = uuid.uuid4().hex
        solo = f'主持人：单人讲述{nonce}。'
        assert script_segments(solo, speaker_labels(1)) == [('主持人', f'单人讲述{nonce}。')]
        first = await render_audio(solo, 'solo-test', speakers=speaker_labels(1),
                                   voices={'主持人': 'voice-host'}, client=client)
        panel = f'主持人：开场{nonce}。\n嘉宾1：第一点{nonce}。\n嘉宾2：第二点{nonce}。'
        second = await render_audio(panel, 'panel-test', speakers=speaker_labels(3),
                                    voices={'主持人': 'voice-host', '嘉宾1': 'voice-one', '嘉宾2': 'voice-two'},
                                    client=client)
        try:
            assert first.is_file() and second.is_file()
            assert calls == ['voice-host', 'voice-host', 'voice-one', 'voice-two']
        finally:
            first.unlink(missing_ok=True)
            second.unlink(missing_ok=True)
        with pytest.raises(ValueError, match='嘉宾2'):
            script_segments(f'主持人：开场。\n嘉宾1：回答。', speaker_labels(3))

    asyncio.run(check())


def test_voice_upload_requires_consent_and_matches_provider_contract():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async def test_db():
            async with sessions() as session:
                yield session
        app.dependency_overrides[get_db] = test_db
        def provider(request):
            assert request.url.path == '/v1/uploads/audio/voice'
            assert b'customName' in request.content and b'file' in request.content
            return httpx.Response(200, json={'uri': 'speech:test:voice'})

        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as provider_client:
                assert await create_custom_voice(b'RIFFdata', 'voice.wav', 'audio/wav', 'hello', 'sample', client=provider_client) == 'speech:test:voice'

            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                payload = {'data': {'name': 'sample', 'transcript': 'hello', 'consent': 'false'},
                           'files': {'sample': ('voice.wav', b'RIFFdata', 'audio/wav')}}
                with patch('app.api.podcasts.create_custom_voice', new_callable=AsyncMock) as upload:
                    assert (await client.post('/api/podcasts/voices', **payload)).status_code == 400
                    upload.assert_not_awaited()
                    payload['data']['consent'] = 'true'
                    upload.return_value = 'speech:test:voice'
                    assert (await client.post('/api/podcasts/voices', **payload)).json()['voice_id'] == 'speech:test:voice'
                payload['data']['name'] = 'large-sample'
                payload['files'] = {'sample': ('voice.wav', b'0' * (10 * 1024 * 1024 + 1), 'audio/wav')}
                assert (await client.post('/api/podcasts/voices', **payload)).status_code == 413
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()

    asyncio.run(check())
