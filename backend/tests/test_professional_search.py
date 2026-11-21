import asyncio
from unittest.mock import AsyncMock
from app.services.material_searcher import MaterialSearcherService


def test_professional_results_are_reserved_verified_and_deduplicated():
    async def check():
        service = MaterialSearcherService()
        async def search(query, **kwargs):
            if 'kirkusreviews.com' in query:
                return [{'url': 'https://evil.example/x', 'title': 'Target Book Jane Doe', 'content': ''},
                        {'url': 'https://www.kirkusreviews.com/review?ref=x', 'title': 'Target Book by Jane Doe review', 'content': ''}]
            if 'publishersweekly.com' in query:
                return [{'url': 'https://www.publishersweekly.com/news', 'title': 'Different Book', 'content': 'another author'}]
            return []
        service.search_client.search = AsyncMock(side_effect=search)
        service.search_client.search_book_info = AsyncMock(return_value=[{'url': 'http://kirkusreviews.com/review', 'title': 'duplicate'}, {'url': 'https://general.example/x', 'title': 'general'}])
        service.search_client.search_book_reviews = AsyncMock(return_value=[])
        results = await service.search_materials('Target Book', 'Jane Doe', ['death'])
        assert [r['url'] for r in results] == ['https://www.kirkusreviews.com/review?ref=x', 'https://general.example/x']
    asyncio.run(check())
