"""Material searcher service - handles source discovery and content retrieval."""

import asyncio
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import httpx
from urllib.parse import urlsplit, urlunsplit
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
        # Reserve one result per professional outlet before filling the remaining slots.
        outlets = ["kirkusreviews.com", "publishersweekly.com", "booklistonline.com",
                   "libraryjournal.com", "theguardian.com", "nybooks.com", "lrb.co.uk"]
        author_part = f" {book_author}" if book_author else ""
        tasks = [self.search_client.search(
            f'site:{site} "{book_title}"{author_part} book review', max_results=5
        ) for site in outlets]
        tasks += [self.search_client.search_book_info(book_title, book_author),
                  self.search_client.search_book_reviews(book_title, book_author)]
        tasks += [self.search_client.search_book_reviews(book_title, book_author, theme)
                  for theme in themes[:3]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_results, seen = [], set()

        def add(item):
            url = item.get("url", "")
            try:
                parsed = urlsplit(url)
                host = (parsed.hostname or "").lower().removeprefix("www.")
                if parsed.scheme not in ("http", "https") or not host:
                    return False
                key = urlunsplit(("https", host, parsed.path.rstrip("/"), "", ""))
            except (ValueError, AttributeError):
                return False
            if key in seen:
                return False
            seen.add(key)
            all_results.append(item)
            return True

        # Site search can return unrelated domains; verify the domain before reserving it.
        for site, result in zip(outlets, results):
            if isinstance(result, list):
                title_terms = set(re.findall(r"[\w]+", book_title.lower()))
                author_terms = set(re.findall(r"[\w]+", (book_author or "").lower()))
                def score(item):
                    words = set(re.findall(r"[\w]+", (item.get("title", "") + " " + item.get("content", "")).lower()))
                    title_words = set(re.findall(r"[\w]+", item.get("title", "").lower()))
                    title_score = len(title_terms & title_words) / max(len(title_terms), 1)
                    author_score = len(author_terms & words) / max(len(author_terms), 1)
                    url = item.get("url", "").lower()
                    is_review = "review" in url or "review" in item.get("title", "").lower()
                    is_news = "/news" in url or "book pulse" in item.get("title", "").lower()
                    return title_score >= 0.6 and (not author_terms or author_score >= 0.5), is_review and not is_news, title_score, author_score
                ranked = sorted(result, key=score, reverse=True)
                for item in ranked:
                    try:
                        host = (urlsplit(item.get("url", "")).hostname or "").lower()
                    except (ValueError, AttributeError):
                        continue
                    _, _, title_score, author_score = score(item)
                    if title_score >= 0.6 and (not author_terms or author_score >= 0.5) and not urlsplit(item.get("url", "")).path.lower().endswith(".pdf") and (host == site or host.endswith("." + site)) and add(item):
                        break
        for result in results[len(outlets):]:
            if isinstance(result, list):
                for item in result:
                    add(item)
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
