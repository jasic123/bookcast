import asyncio
from unittest.mock import patch

import httpx

from app.core.config import settings
from app.services.search_client import SearchClient


def test_searchinfinity_results_and_error_fallback():
    async def check():
        requests = []

        def response(request):
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(200, json={"Result": {"WebResults": [{
                    "Title": "A review", "Url": "https://example.com/review", "Summary": "Useful evidence",
                }]}})
            return httpx.Response(200, json={"ResponseMetadata": {"Error": {"Code": "10403"}}})

        original = httpx.AsyncClient
        client = SearchClient()
        client.client.search = lambda **kwargs: {"results": [{"title": "fallback", "url": "https://example.com", "content": "snippet"}]}
        with patch.object(settings, "DOUBAO_SEARCH_API_KEY", "test-key"), patch.object(settings, "DOUBAO_SEARCH_BASE_URL", "https://open.feedcoopapi.com"), patch("app.services.search_client.httpx.AsyncClient", side_effect=lambda **kwargs: original(transport=httpx.MockTransport(response))):
            result = await client.search("a book", max_results=2)
            assert result[0]["content"] == "Useful evidence"
            assert requests[0].url.path == "/search_api/web_search"
            assert requests[0].headers["Authorization"] == "Bearer test-key"
            assert (await client.search("a book"))[0]["title"] == "fallback"
    asyncio.run(check())
