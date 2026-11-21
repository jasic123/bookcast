"""Theme screening service - determines if books match user themes."""

from typing import List, Dict, Any, Optional
from app.services.llm_client import LLMClient
from app.services.search_client import SearchClient


class ThemeScreenerService:
    """Screens books against user-specified themes."""

    def __init__(self):
        self.llm_client = LLMClient()
        self.search_client = SearchClient()

    async def screen_book_for_themes(
        self,
        book_title: str,
        book_author: Optional[str],
        book_description: Optional[str],
        themes: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Screen a book against multiple themes.

        Returns list of theme match results, one per theme.
        Each result contains:
        - theme: str
        - status: "candidate", "pending", "no_evidence"
        - reasoning: str
        - evidence: List[str]
        - source_indices: List[int]
        """
        theme_matches = []
        for theme in themes:
            author_part = f" {book_author}" if book_author else ""
            query = f'"{book_title}"{author_part} {theme} book themes review'
            try:
                search_results = await self.search_client.search(query, raise_errors=True)
                search_error = None
            except Exception:
                search_results = []
                search_error = "主题搜索失败，无法核实匹配情况。"

            match_result = await self.llm_client.analyze_theme_match(
                book_title=book_title,
                book_author=book_author,
                book_description=book_description,
                theme=theme,
                search_results=search_results,
            )
            status = match_result.get("status", "pending")
            if status not in ("candidate", "pending", "no_evidence"):
                status = "pending"
            reasoning = match_result.get("reasoning")
            if not isinstance(reasoning, str) or not reasoning.strip():
                status, reasoning = "pending", "AI 未能提供有效的主题判断，请重试。"
            if not search_results:
                status = "pending"
                reason = search_error or "主题搜索没有返回结果，证据不足，暂无法判断是否匹配。"
                reasoning = reason + " " + reasoning
            suggestions = match_result.get("suggested_themes", [])
            if not isinstance(suggestions, list):
                suggestions = []
            suggestions = [x.strip()[:50] for x in suggestions if isinstance(x, str) and x.strip()][:3]
            if not search_results:
                suggestions = []
            theme_matches.append({
                "theme": theme, "status": status, "reasoning": reasoning,
                "evidence": match_result.get("evidence", []),
                "source_indices": match_result.get("source_indices", []),
                "suggested_themes": suggestions,
                "search_sources": [{"title": r.get("title", ""), "url": r.get("url", "")} for r in search_results[:5]],
            })

        return theme_matches

    def aggregate_matches(
        self,
        theme_matches: List[Dict[str, Any]],
        match_mode: str = "any",
    ) -> tuple[bool, str]:
        """
        Aggregate theme matches based on mode.

        Args:
            theme_matches: List of theme match results
            match_mode: "any" or "all"

        Returns:
            (is_candidate, reasoning)
        """
        candidate_themes = [
            tm for tm in theme_matches
            if tm.get("status") == "candidate"
        ]

        if match_mode == "all":
            if len(candidate_themes) == len(theme_matches):
                return True, "All themes have supporting evidence"
            else:
                missing = [
                    tm["theme"] for tm in theme_matches
                    if tm.get("status") != "candidate"
                ]
                return False, f"Missing evidence for: {', '.join(missing)}"
        else:  # any
            if candidate_themes:
                matched = [tm["theme"] for tm in candidate_themes]
                return True, f"Found evidence for: {', '.join(matched)}"
            else:
                return False, "No themes have sufficient evidence"
