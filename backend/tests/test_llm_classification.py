import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services.llm_client import LLMClient


def test_source_classification_parses_wrapped_json_and_never_marks_parse_failure_irrelevant():
    async def check():
        client = LLMClient()
        valid = '''Here is the classification:\n```json\n{"classification":{"source_type":"professional_review","reasoning":"review","is_about_target":true,"identity_reasoning":"title and author","summary":"about the book","key_points":["point"]}}\n```'''
        client.chat_completion = AsyncMock(return_value=valid)
        kwargs = dict(source_title='Review', source_url='https://example.org/review', content='Content',
                      book_title='Book', book_author='Author')
        assert (await client.classify_source(**kwargs))['is_about_target'] is True
        client.chat_completion = AsyncMock(side_effect=['bad response', 'still bad'])
        with pytest.raises(ValueError, match='来源分类解析失败'):
            await client.classify_source(**kwargs)
        assert client.chat_completion.await_count == 2

    asyncio.run(check())
