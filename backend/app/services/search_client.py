"""Search client for finding sources via Tavily API."""

from tavily import TavilyClient
from typing import List, Dict, Any
from app.core.config import settings
import asyncio


class SearchClient:
    """Wrapper for Tavily search API."""

    def __init__(self):
        self.client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        self.max_results = settings.MAX_SEARCH_RESULTS_PER_QUERY
        self.timeout = settings.SEARCH_TIMEOUT_SECONDS

    async def search(
        self,
        query: str,
        search_depth: str = "advanced",
        max_results: int = None,
        raise_errors: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Perform a search query.

        Args:
            query: Search query string
            search_depth: "basic" or "advanced"
            max_results: Override default max results

        Returns:
            List of search results with title, url, content
        """
        max_results = max_results or self.max_results

        try:
            # Tavily client is synchronous, run in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.search(
                    query=query,
                    search_depth=search_depth,
                    max_results=max_results,
                )
            )

            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0.0),
                })

            return results

        except Exception:
            if raise_errors:
                raise
            return []

    async def search_book_info(
        self,
        book_title: str,
        author: str = None,
    ) -> List[Dict[str, Any]]:
        """Search for general book information."""
        author_part = f" by {author}" if author else ""
        query = f'"{book_title}"{author_part} book summary plot'
        return await self.search(query)

    async def search_book_reviews(
        self,
        book_title: str,
        author: str = None,
        theme: str = None,
    ) -> List[Dict[str, Any]]:
        """Search for book reviews."""
        author_part = f" by {author}" if author else ""
        theme_part = f" {theme}" if theme else ""
        query = f'"{book_title}"{author_part}{theme_part} book review'
        return await self.search(query)

    async def search_targeted_sites(
        self,
        book_title: str,
        author: str = None,
        sites: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search specific sites for book content."""
        if not sites:
            sites = [
                "kirkusreviews.com",
                "publishersweekly.com",
                "theguardian.com/books",
                "goodreads.com",
            ]

        author_part = f" by {author}" if author else ""
        site_part = " OR ".join([f"site:{site}" for site in sites])
        query = f'"{book_title}"{author_part} ({site_part})'

        return await self.search(query, max_results=self.max_results * 2)
