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
        # If description is insufficient, search for book info
        search_results = []
        if not book_description or len(book_description) < 100:
            search_results = await self.search_client.search_book_info(
                book_title, book_author
            )

        # Analyze each theme
        theme_matches = []
        for theme in themes:
            match_result = await self.llm_client.analyze_theme_match(
                book_title=book_title,
                book_author=book_author,
                book_description=book_description,
                theme=theme,
                search_results=search_results,
            )

            theme_matches.append({
                "theme": theme,
                "status": match_result.get("status", "pending"),
                "reasoning": match_result.get("reasoning", ""),
                "evidence": match_result.get("evidence", []),
                "source_indices": match_result.get("source_indices", []),
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
