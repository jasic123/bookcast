"""LLM client wrapper for OpenAI-compatible APIs."""

from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional
from app.core.config import settings


class LLMClient:
    """Wrapper for LLM API calls."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Send chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Response content as string
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
        )
        return response.choices[0].message.content

    async def analyze_theme_match(
        self,
        book_title: str,
        book_author: Optional[str],
        book_description: Optional[str],
        theme: str,
        search_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze if a book matches a theme based on available information.

        Returns dict with:
        - status: "candidate", "pending", or "no_evidence"
        - reasoning: explanation
        - evidence: list of supporting quotes
        - sources: list of source indices
        """
        author_info = f" by {book_author}" if book_author else ""
        desc_info = f"\n\nBook description: {book_description}" if book_description else ""

        search_context = "\n\n".join([
            f"Source {i+1} ({result.get('title', 'Untitled')}), URL: {result.get('url', '')}:\n{result.get('content', '')[:500]}"
            for i, result in enumerate(search_results[:5])
        ])

        prompt = f"""Analyze whether the book "{book_title}"{author_info} relates to the theme: {theme}

{desc_info}

Available information from searches:
{search_context or "No search results available."}

Instructions:
1. Only judge based on actual evidence, not assumptions from the title
2. Distinguish between the target book and other works (series, adaptations, other books by same author)
3. Status should be:
   - "candidate": Clear evidence the book discusses this theme
   - "pending": Theme might be relevant but needs verification
   - "no_evidence": No evidence found for this theme

4. Provide specific reasoning and quote relevant passages
5. List which sources support your conclusion (zero-based indices)
6. Identify 1-3 alternative themes in Chinese that the supplied material actually describes, even when it does not support the requested theme. Only return an empty list if no alternative subject is supported by any supplied material.
7. Write the reasoning in Chinese and explain why the supplied material does or does not support the requested theme. Do not invent evidence or claim the book does not discuss a theme merely because the snippets do not mention it.

Respond in JSON format:
{{
  "status": "candidate|pending|no_evidence",
  "reasoning": "explanation here",
  "evidence": ["quote 1", "quote 2"],
  "source_indices": [0, 1],
  "suggested_themes": ["主题"]
}}"""

        messages = [
            {"role": "system", "content": "You are a literary research assistant analyzing book themes based on evidence."},
            {"role": "user", "content": prompt}
        ]

        response = await self.chat_completion(messages, temperature=0.3)

        # Parse JSON response
        import json
        try:
            result = json.loads(response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
            return result if isinstance(result, dict) else {}
        except json.JSONDecodeError:
            # Fallback if LLM doesn't return valid JSON
            return {
                "status": "pending",
                "reasoning": f"Analysis incomplete: {response[:200]}",
                "evidence": [],
                "source_indices": []
            }

    async def classify_source(
        self,
        source_title: str,
        source_url: str,
        content: str,
        book_title: str,
        book_author: Optional[str],
    ) -> Dict[str, Any]:
        """
        Classify a source and verify it's about the target book.

        Returns dict with:
        - source_type: classification
        - reasoning: explanation
        - is_about_target: bool
        - identity_reasoning: explanation
        - summary: brief summary
        - key_points: list of key points
        """
        author_info = f" by {book_author}" if book_author else ""

        prompt = f"""Classify this source material and verify it discusses the target book.

Target book: "{book_title}"{author_info}

Source title: {source_title}
Source URL: {source_url}
Content (first 2000 chars):
{content[:2000]}

Tasks:
1. Verify this source is about the TARGET BOOK, not:
   - Other books in the same series
   - Movie/TV adaptations
   - Other books by the same author
   - Books with similar titles

2. Classify the source type:
   - professional_review: A substantive review of the target book by a professional critic or review publication. A publisher site or news report alone is not a review.
   - reader_review: Independent reader review or blog
   - publisher_description: Publisher or bookstore description
   - author_interview: Interview with the author
   - news_article: News coverage
   - encyclopedia: Reference material
   - other: Other relevant content
   - irrelevant: Not about the target book or not useful

3. If the page is news, author interview, or a publisher description, use that type even when hosted on a review publication. If identity or review type is uncertain, use other and is_about_target=false.
4. Extract key information in Chinese; distinguish the available excerpt from full text.

Respond in JSON:
{{
  "source_type": "type from list above",
  "reasoning": "why this classification",
  "is_about_target": true/false,
  "identity_reasoning": "how you verified book identity",
  "summary": "2-3 sentence summary",
  "key_points": ["point 1", "point 2", "point 3"]
}}"""

        messages = [
            {"role": "system", "content": "You are a research librarian classifying source materials."},
            {"role": "user", "content": prompt}
        ]

        response = await self.chat_completion(messages, temperature=0.2)

        import json
        try:
            result = json.loads(response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
            if not isinstance(result, dict):
                raise ValueError("Invalid classification")
            return result
        except (json.JSONDecodeError, ValueError):
            return {
                "source_type": "other",
                "reasoning": "Classification incomplete",
                "is_about_target": False,
                "identity_reasoning": "Unable to verify",
                "summary": content[:200],
                "key_points": []
            }

    async def assess_material_sufficiency(
        self,
        book_title: str,
        book_author: Optional[str],
        theme_matches: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Assess whether collected materials are sufficient for a podcast episode.

        Returns dict with:
        - overall_assessment: "recommended", "insufficient", "needs_review", "no_theme_evidence"
        - reasoning: explanation
        - material_gaps: list of missing elements
        - suggested_searches: list of follow-up search suggestions
        """
        author_info = f" by {book_author}" if book_author else ""

        # Summarize theme matches
        theme_summary = "\n".join([
            f"- {tm['theme']}: {tm['status']} - {tm['reasoning'][:100]}"
            for tm in theme_matches
        ])

        # Count source types
        source_counts = {}
        for source in sources:
            st = source.get('source_type', 'other')
            source_counts[st] = source_counts.get(st, 0) + 1

        source_summary = "\n".join([
            f"- {st}: {count}" for st, count in source_counts.items()
        ])

        prompt = f"""Assess whether the collected materials are sufficient to produce a quality book podcast episode.

Book: "{book_title}"{author_info}

Theme Matches:
{theme_summary}

Source Breakdown:
{source_summary}
Total unique sources: {len(sources)}

Requirements for a podcast episode:
1. Book identity must be clear
2. Need credible plot/content summary
3. Need at least some independent analysis (not just publisher descriptions)
4. Preferably multiple perspectives
5. Theme relevance must be supported by evidence

Assessment levels:
- "recommended": Good theme match + sufficient diverse materials
- "insufficient": Theme may match but materials too limited
- "needs_review": Uncertainty in book identity or theme evidence
- "no_theme_evidence": No theme evidence found

Respond in JSON:
{{
  "overall_assessment": "one of the four levels above",
  "reasoning": "detailed explanation referencing specific gaps or strengths",
  "material_gaps": ["gap 1", "gap 2"],
  "suggested_searches": ["search suggestion 1", "search suggestion 2"]
}}"""

        messages = [
            {"role": "system", "content": "You are a podcast production editor assessing research materials."},
            {"role": "user", "content": prompt}
        ]

        response = await self.chat_completion(messages, temperature=0.3)

        import json
        try:
            result = json.loads(response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
            return result
        except json.JSONDecodeError:
            return {
                "overall_assessment": "needs_review",
                "reasoning": "Assessment incomplete",
                "material_gaps": ["Unable to complete automated assessment"],
                "suggested_searches": []
            }
