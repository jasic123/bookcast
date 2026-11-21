"""Service for fetching book lists from various sources."""

import csv
import io
import httpx
from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime
from app.schemas.book import BookCreate
from app.core.config import settings


class BookFetcherService:
    """Fetches book lists from Amazon and CSV uploads."""

    def __init__(self):
        self.max_books = settings.MAX_BOOKS_PER_LIST
        self.timeout = settings.SEARCH_TIMEOUT_SECONDS

    async def fetch_amazon_list(
        self,
        list_url: Optional[str] = None,
        list_name: str = "Amazon Best Sellers"
    ) -> tuple[List[BookCreate], str, Optional[str], Optional[datetime]]:
        """
        Fetch books from Amazon bestseller list.

        Returns:
            tuple: (books, source_url, error_message, list_date)
        """
        # Default to Amazon Best Sellers Books page
        url = list_url or "https://www.amazon.com/Best-Sellers-Books/zgbs/books"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Add user agent to avoid blocking
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            books = []

            # Amazon bestseller page structure
            # Note: This is based on current structure and may need updates
            items = soup.select("div.zg-grid-general-faceout")[:self.max_books]

            if not items:
                # Try alternative selector
                items = soup.select("div[data-asin]")[:self.max_books]

            if not items:
                return [], url, "Could not find book items on the page. Amazon structure may have changed.", None

            for idx, item in enumerate(items, 1):
                try:
                    # Extract title
                    title_elem = item.select_one("div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1")
                    if not title_elem:
                        title_elem = item.select_one("img")
                        title = title_elem.get("alt", "").strip() if title_elem else ""
                    else:
                        title = title_elem.get_text(strip=True)

                    if not title:
                        continue

                    # Extract author
                    author_elem = item.select_one("a.a-size-small")
                    author = author_elem.get_text(strip=True) if author_elem else None

                    # Extract ASIN (Amazon product ID)
                    asin = item.get("data-asin")

                    # Extract link
                    link_elem = item.select_one("a")
                    link = None
                    if link_elem and link_elem.get("href"):
                        href = link_elem.get("href")
                        if href.startswith("/"):
                            link = f"https://www.amazon.com{href}"
                        else:
                            link = href

                    books.append(BookCreate(
                        title=title,
                        author=author,
                        asin=asin,
                        rank=idx,
                        source_url=link,
                        platform_id=asin
                    ))

                except Exception as e:
                    # Skip individual items that fail
                    continue

            if not books:
                return [], url, "Successfully loaded page but could not extract any books. Amazon structure may have changed.", None

            # Amazon lists are typically current
            list_date = datetime.now()

            return books, url, None, list_date

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return [], url, "Access denied by Amazon. The site may be blocking automated requests.", None
            elif e.response.status_code == 404:
                return [], url, "Amazon page not found. Please check the URL.", None
            else:
                return [], url, f"HTTP error {e.response.status_code}: {str(e)}", None

        except httpx.TimeoutException:
            return [], url, f"Request timed out after {self.timeout} seconds.", None

        except Exception as e:
            return [], url, f"Unexpected error fetching Amazon list: {str(e)}", None

    async def parse_csv(
        self,
        csv_content: str,
        list_name: str
    ) -> tuple[List[BookCreate], Optional[str]]:
        """
        Parse CSV content into book list.

        Expected columns:
        - title (required)
        - author (optional)
        - isbn (optional)
        - description (optional)
        - list_name (optional)
        - rank (optional)
        - published_date (optional)

        Returns:
            tuple: (books, error_message)
        """
        try:
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)

            # Check for required column
            if not reader.fieldnames or "title" not in reader.fieldnames:
                return [], "CSV must contain a 'title' column"

            books = []
            for idx, row in enumerate(reader, 1):
                if idx > self.max_books:
                    break

                title = row.get("title", "").strip()
                if not title:
                    continue

                # Extract optional fields
                author = row.get("author", "").strip() or None
                isbn = row.get("isbn", "").strip() or None
                description = row.get("description", "").strip() or None
                rank_str = row.get("rank", "").strip()
                rank = int(rank_str) if rank_str and rank_str.isdigit() else idx

                books.append(BookCreate(
                    title=title,
                    author=author,
                    isbn=isbn,
                    description=description,
                    rank=rank
                ))

            if not books:
                return [], "No valid books found in CSV"

            return books, None

        except csv.Error as e:
            return [], f"CSV parsing error: {str(e)}"
        except Exception as e:
            return [], f"Unexpected error parsing CSV: {str(e)}"
