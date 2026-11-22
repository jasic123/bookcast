"""Use the locally installed Open Library and Gutenberg MCP servers."""
import asyncio
import json
import logging
import os
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import settings
from app.services.goodreads import _title, _words

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2] / "mcp-servers" / "node_modules"
OPEN_LIBRARY = ROOT / "mcp-open-library" / "build" / "index.js"
GUTENBERG = ROOT / "@cyanheads" / "gutenberg-mcp-server" / "dist" / "index.js"


def _env():
    env = os.environ.copy()
    if settings.GOODREADS_PROXY:
        env.update({"HTTP_PROXY": settings.GOODREADS_PROXY, "HTTPS_PROXY": settings.GOODREADS_PROXY, "NODE_USE_ENV_PROXY": "1"})
    env.setdefault("LOG_LEVEL", "error")
    return env


async def _call(session, name, arguments):
    response = await asyncio.wait_for(session.call_tool(name, arguments), timeout=25)
    if response.isError:
        raise RuntimeError(f"{name} returned an error")
    if response.structuredContent is not None:
        data = response.structuredContent
    else:
        data = json.loads(response.content[0].text)
    if not isinstance(data, dict) or "error" in data:
        raise RuntimeError(f"{name} returned invalid data")
    return data


async def open_library_book(title, author):
    """Return verified work metadata and Project Gutenberg edition IDs."""
    if not author:
        return None
    async with stdio_client(StdioServerParameters(command="node", args=[str(OPEN_LIBRARY)], env=_env())) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=15)
            found = await _call(session, "search_books", {"title": _title(title), "author": author, "limit": 10})
            match = next((item for item in found.get("results", [])
                          if _title(item.get("title") or "") == _title(title)
                          and any(_words(a) == _words(author) for a in item.get("authors", []))), None)
            if not match:
                return None
            key = match.get("open_library_work_key", "")
            if not key.startswith("/works/OL") or not key.endswith("W"):
                raise ValueError("Invalid Open Library work ID")
            work = await _call(session, "get_work", {"work_key": key})

    # The Open Library MCP omits this search field; request it from the same
    # public API and require the identical verified work key before using IDs.
    gutenberg_ids = []
    try:
        transport = httpx.AsyncHTTPTransport(proxy=settings.GOODREADS_PROXY) if settings.GOODREADS_PROXY else None
        async with httpx.AsyncClient(timeout=12, transport=transport) as client:
            response = await client.get("https://openlibrary.org/search.json", params={
                "title": _title(title), "author": author, "limit": 10,
                "fields": "key,id_project_gutenberg",
            })
            response.raise_for_status()
            row = next((x for x in response.json().get("docs", []) if x.get("key") == key), {})
            gutenberg_ids = [int(x) for x in row.get("id_project_gutenberg", []) if str(x).isdigit()][:3]
    except (httpx.HTTPError, ValueError, KeyError):
        logger.warning("Open Library Gutenberg identifiers unavailable")
    description = work.get("description") or ""
    subjects = work.get("subjects") or []
    text = f"书名：{match['title']}\n作者：{author}\n"
    if description:
        text += "简介：" + description + "\n"
    if subjects:
        text += "馆藏主题：" + ", ".join(str(x) for x in subjects[:20])
    return {"title": "Open Library 图书资料：" + match["title"], "url": "https://openlibrary.org" + key,
            "content": text, "description": description, "gutenberg_ids": gutenberg_ids}


async def gutenberg_excerpts(title, book_ids):
    """Read three labelled excerpts from a verified Gutenberg edition."""
    if not book_ids:
        return None
    async with stdio_client(StdioServerParameters(command="node", args=[str(GUTENBERG)], env=_env())) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=15)
            for book_id in book_ids:
                first = await _call(session, "gutenberg_get_text", {"id": book_id, "limit": 4500})
                if _title(first.get("title") or "") != _title(title):
                    continue
                total = int(first.get("totalChars") or 0)
                chunks = [(0, first.get("text") or "")]
                for offset in sorted({total // 2, max(0, total - 5000)} - {0}):
                    part = await _call(session, "gutenberg_get_text", {"id": book_id, "offset": offset, "limit": 4500})
                    chunks.append((offset, part.get("text") or ""))
                content = "\n\n".join(f"[正文节选，字符位置 {offset}]\n{text}" for offset, text in chunks if text)
                if content:
                    return {"title": "Project Gutenberg 原文节选：" + first["title"],
                            "url": f"https://www.gutenberg.org/ebooks/{book_id}", "content": content,
                            "total_chars": total, "excerpt_count": len(chunks)}
    return None
