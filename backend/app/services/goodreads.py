"""Collect public Goodreads reader reviews; endpoints are unofficial.

Based on goodreads-mcp by Shreeya Chand (MIT), see THIRD_PARTY_NOTICES.
"""
import asyncio
import html
import logging
import re
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings

logger = logging.getLogger(__name__)
BASE = "https://www.goodreads.com"
BOOK_QUERY = "query($id: Int!){ getBookByLegacyId(legacyId:$id){ legacyId title work{ id } } }"
REVIEW_QUERY = """query($filters: BookReviewsFilterInput!, $pagination: PaginationInput){
  getReviews(filters:$filters, pagination:$pagination){ edges{ node{
    rating text spoilerStatus creator{ name } shelving{ webUrl }
  } } }
}"""


def _words(value):
    return " ".join(re.findall(r"[\w]+", value.casefold()))


def _title(value):
    value = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", value)
    parts = [p.strip() for p in value.split(":")]
    # Preserve a meaningful subtitle (e.g. Dog Man: A Sprinkle in Time).
    parts = parts[:2] if len(parts) > 1 and _words(parts[1]) not in {"a novel", "a graphic novel", "a memoir"} else parts[:1]
    return _words(" ".join(parts))


def select_book(items, title, author):
    """Require author and a close title match; never select a summary edition."""
    if not author or not _title(title):
        return None
    target, author_key = _title(title), _words(author)
    for item in items:
        name = item.get("title") or ""
        if re.search(r"\b(summary|analysis|study guide|unofficial)\b", name, re.I):
            continue
        if _words((item.get("author") or {}).get("name") or "") != author_key:
            continue
        candidate = _title(name)
        if candidate == target and str(item.get("bookId", "")).isdigit():
            return item
    return None


async def search_reviews(title, author):
    """Return up to six attributable reader reviews, or raise on source failure."""
    return await asyncio.wait_for(_search_reviews(title, author), timeout=45)


async def _search_reviews(title, author):
    if not author:
        return []
    transport = httpx.AsyncHTTPTransport(proxy=settings.GOODREADS_PROXY or None, retries=0) if settings.GOODREADS_PROXY else None
    async with httpx.AsyncClient(transport=transport, timeout=12, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as web:
        # Goodreads autocomplete often ranks summaries above the original when
        # the author is included in the query, so search by title then verify.
        response = await web.get(BASE + "/book/auto_complete", params={"format": "json", "q": _title(title)})
        response.raise_for_status()
        book = select_book(response.json(), title, author)
        if not book:
            return []
        page = await web.get(BASE + "/giveaway")
        page.raise_for_status()
        data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', page.text, re.S)
        app_match = re.search(r'src="(/_next/static/chunks/pages/_app-[0-9a-f]+\.js)"', page.text)
        if not data_match or not app_match:
            raise ValueError("Goodreads API configuration unavailable")
        import json
        key = json.loads(data_match.group(1)).get("props", {}).get("pageProps", {}).get("apiKey", "")
        if not re.fullmatch(r"da2-[a-z0-9]+", key):
            raise ValueError("Goodreads API configuration unavailable")
        bundle = await web.get(BASE + app_match.group(1))
        bundle.raise_for_status()
        endpoints = list(re.finditer(r'"endpoint":"(https://[a-z0-9-]+\.appsync-api\.[a-z0-9-]+\.amazonaws\.com/graphql)"', bundle.text))
        production = [m.group(1) for i, m in enumerate(endpoints)
                      if '"shortName":"Prod"' in bundle.text[m.end():endpoints[i + 1].start() if i + 1 < len(endpoints) else len(bundle.text)]]
        if len(set(production)) == 1:
            endpoint = production[0]
        elif len({m.group(1) for m in endpoints}) == 1:
            endpoint = endpoints[0].group(1)
        else:
            raise ValueError("Goodreads API endpoint unavailable or ambiguous")

        async def graphql(query, variables):
            payload = {"query": query, "variables": variables}
            headers = {"x-api-key": key}
            try:
                r = await web.post(endpoint, headers=headers, json=payload)
            except httpx.ConnectError:
                # Goodreads pages can require the proxy while AWS rejects it.
                async with httpx.AsyncClient(timeout=12, trust_env=False) as direct:
                    r = await direct.post(endpoint, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json().get("data")
            if data is None:
                raise ValueError("Goodreads review API returned no data")
            return data

        matched = (await graphql(BOOK_QUERY, {"id": int(book["bookId"])})).get("getBookByLegacyId") or {}
        work = (matched.get("work") or {}).get("id")
        if not work:
            raise ValueError("Goodreads book has no work identifier")
        data = await graphql(REVIEW_QUERY, {"filters": {"resourceType": "WORK", "resourceId": work}, "pagination": {"limit": 30}})
        nodes = [edge.get("node") or {} for edge in (data.get("getReviews") or {}).get("edges", []) if edge]
        reviews = []
        for node in nodes:
            url = (node.get("shelving") or {}).get("webUrl") or ""
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname != "www.goodreads.com" or not re.fullmatch(r"/review/show/\d+/?", parsed.path) or node.get("spoilerStatus"):
                continue
            content = BeautifulSoup(html.unescape(node.get("text") or ""), "html.parser").get_text(" ", strip=True)
            if not content:
                continue
            reviewer = (node.get("creator") or {}).get("name") or "Goodreads 读者"
            rating = node.get("rating")
            reviews.append({"title": f"Goodreads 读者评论：{reviewer}（{rating or '未评分'}/5）", "url": url, "content": content, "rating": rating})
        # Include both favourable and critical opinions when present.
        selected = [r for r in reviews if r["rating"] in (4, 5)][:3]
        selected += [r for r in reviews if r["rating"] in (1, 2)][:3]
        selected += [r for r in reviews if r not in selected][:max(0, 6 - len(selected))]
        return selected[:6]
