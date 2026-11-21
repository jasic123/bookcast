"""Material searcher service - handles source discovery and content retrieval."""

import asyncio
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import httpx
from app.services.search_client import SearchClient
from app.services.llm_client import LLMClient
from app.core.config import settings


class MaterialSearcherService:
    """Searches and retrieves source materials for book research."""

    def __init__(self):
        self.search_client = SearchClient()
        self.llm_client = LLMClient()
        self.timeout = settings.SEARCH_TIMEOUT_SECONDS

    async def search_materials(
        self,
        book_title: str,
        book_author: Optional[str],
        themes: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Search for materials about a book and themes.

        Returns list of raw search results with title, url, content.
        """
        search_tasks = []

        # General book information
        search_tasks.append(
            self.search_client.search_book_info(book_title, book_author)
        )

        # Reviews
        search_tasks.append(
            self.search_client.search_book_reviews(book_title, book_author)
        )

        # Theme-specific searches
        for theme in themes[:3]:  # Limit to first 3 themes
            search_tasks.append(
                self.search_client.search_book_reviews(
                    book_title, book_author, theme
                )
            )

        # Targeted site searches
        search_tasks.append(
            self.search_client.search_targeted_sites(book_title, book_author)
        )

        # Execute all searches concurrently
        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Flatten and deduplicate
        all_results = []
        seen_urls = set()

        for result in results:
            if isinstance(result, Exception):
                continue
            if isinstance(result, list):
                for item in result:
                    url = item.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(item)

        return all_results

    async def fetch_content(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """
        Fetch and clean content from URL.

        Returns: (content, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()

            # Clean HTML
            soup = BeautifulSoup(response.text, "lxml")

            # Remove unwanted elements
            for element in soup.find_all(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
                element.decompose()

            # Get text content
            text = soup.get_text(separator="\n", strip=True)

            # Basic cleaning
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            content = "\n".join(lines)

            if len(content) < 100:
                return None, "Content too short after cleaning"

            return content, None

        except httpx.HTTPStatusError as e:
            return None, f"HTTP {e.response.status_code}"
        except httpx.TimeoutException:
            return None, "Timeout"
        except Exception as e:
            return None, f"Error: {str(e)[:100]}"

    async def classify_and_analyze_source(
        self,
        source_title: str,
        source_url: str,
        content: str,
        book_title: str,
        book_author: Optional[str],
    ) -> Dict[str, Any]:
        """
        Classify source type and analyze content.

        Returns dict with classification and analysis results.
        """
        return await self.llm_client.classify_source(
            source_title=source_title,
            source_url=source_url,
            content=content,
            book_title=book_title,
            book_author=book_author,
        )

    def detect_duplicates(self, sources: List[Dict[str, Any]]) -> List[tuple[int, int]]:
        """
        Detect duplicate sources.

        Returns list of (duplicate_idx, original_idx) tuples.
        """
        duplicates = []
        seen_urls = {}

        for idx, source in enumerate(sources):
            url = source.get("url", "")
            if not url:
                continue

            # Normalize URL
            normalized = url.lower().split("?")[0].split("#")[0]
            normalized = normalized.replace("http://", "https://")
            normalized = normalized.replace("www.", "")

            if normalized in seen_urls:
                duplicates.append((idx, seen_urls[normalized]))
            else:
                seen_urls[normalized] = idx

        return duplicates
