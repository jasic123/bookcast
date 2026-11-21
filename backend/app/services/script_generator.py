"""Podcast script generator - creates Chinese or English podcast scripts."""

from typing import Dict, Any, List, Optional
from app.services.llm_client import LLMClient
from app.services.script_validator import PodcastScriptValidator


class PodcastScriptGenerator:
    """Generates podcast scripts from research materials."""

    def __init__(self):
        self.llm_client = LLMClient()
        self.validator = PodcastScriptValidator()

    def _build_research_context(
        self,
        book_title: str,
        book_author: Optional[str],
        book_description: Optional[str],
        theme_matches: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        material_assessment: Dict[str, Any],
    ) -> str:
        """Build context summary from research materials."""
        author_info = f" by {book_author}" if book_author else ""

        # Book info
        context_parts = [
            f"## Book Information",
            f"**Title**: {book_title}{author_info}",
        ]

        if book_description:
            context_parts.append(f"**Description**: {book_description[:500]}")

        # Theme matches
        context_parts.append("\n## Theme Analysis")
        for tm in theme_matches:
            context_parts.append(
                f"- **{tm['theme']}**: {tm['status']} - {tm['reasoning'][:200]}"
            )

        # Key sources
        context_parts.append("\n## Key Sources")
        professional_reviews = [
            s for s in sources
            if s.get('source_type') == 'professional_review' and s.get('is_about_target')
        ][:3]

        reader_reviews = [
            s for s in sources
            if s.get('source_type') == 'reader_review' and s.get('is_about_target')
        ][:3]

        if professional_reviews:
            context_parts.append("\n### Professional Reviews")
            for source in professional_reviews:
                context_parts.append(f"- **{source['title']}**")
                if source.get('summary'):
                    context_parts.append(f"  {source['summary'][:300]}")
                if source.get('key_points'):
                    for point in source['key_points'][:2]:
                        context_parts.append(f"  • {point}")

        if reader_reviews:
            context_parts.append("\n### Reader Perspectives")
            for source in reader_reviews:
                context_parts.append(f"- **{source['title']}**")
                if source.get('summary'):
                    context_parts.append(f"  {source['summary'][:200]}")

        # Material assessment
        context_parts.append("\n## Material Assessment")
        context_parts.append(f"- Total unique sources: {material_assessment.get('total_unique_sources', 0)}")
        context_parts.append(f"- Professional reviews: {material_assessment.get('professional_review_count', 0)}")
        context_parts.append(f"- Independent reviews: {material_assessment.get('independent_review_count', 0)}")

        return "\n".join(context_parts)

    async def generate_script(
        self,
        book_title: str,
        book_author: Optional[str],
        book_description: Optional[str],
        theme_matches: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        material_assessment: Dict[str, Any],
        language: str = "zh",
        style: str = "conversational",
        target_duration: int = 25,
        include_sections: List[str] = None,
    ) -> str:
        """
        Generate a podcast script.

        Args:
            book_title: Book title
            book_author: Book author
            book_description: Book description
            theme_matches: List of theme match results
            sources: List of source materials
            material_assessment: Material assessment summary
            language: "zh" or "en"
            style: "conversational", "formal", or "casual"
            target_duration: Target duration in minutes
            include_sections: List of sections to include

        Returns:
            Generated script as markdown text
        """
        if include_sections is None:
            include_sections = ["introduction", "summary", "analysis", "conclusion"]

        # Build research context
        research_context = self._build_research_context(
            book_title, book_author, book_description,
            theme_matches, sources, material_assessment
        )

        # Calculate target word count
        # Normal speaking rate: 150 wpm, with 10% buffer
        target_words = int(target_duration * 150 / 1.1)

        # Build prompt based on language
        if language == "zh":
            prompt = self._build_chinese_prompt(
                book_title, book_author, research_context,
                style, target_words, include_sections
            )
        else:
            prompt = self._build_english_prompt(
                book_title, book_author, research_context,
                style, target_words, include_sections
            )

        # Generate script
        messages = [
            {
                "role": "system",
                "content": "You are an expert podcast scriptwriter creating engaging book review content."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        script = await self.llm_client.chat_completion(
            messages,
            temperature=0.7,
            max_tokens=8000,
        )

        return script

    def _build_chinese_prompt(
        self,
        book_title: str,
        book_author: Optional[str],
        research_context: str,
        style: str,
        target_words: int,
        include_sections: List[str],
    ) -> str:
        """Build prompt for Chinese script generation."""
        author_info = f"作者：{book_author}" if book_author else ""

        style_guide = {
            "conversational": "对话式，亲切自然，像朋友间的读书分享",
            "formal": "正式专业，适合学术或专业受众",
            "casual": "轻松随意，富有个人特色和观点"
        }.get(style, "对话式，自然流畅")

        sections_guide = []
        if "introduction" in include_sections:
            sections_guide.append("**开场**：简短介绍书籍和本期主题（~500字）")
        if "summary" in include_sections:
            sections_guide.append("**内容梗概**：介绍故事背景、主要情节或核心观点（~800字）")
        if "analysis" in include_sections:
            sections_guide.append("**深度解读**：分析主题、人物、写作手法或引发的思考（~1200字）")
        if "themes" in include_sections:
            sections_guide.append("**主题探讨**：结合用户关注的主题深入讨论（~800字）")
        if "conclusion" in include_sections:
            sections_guide.append("**总结推荐**：总结要点，给出阅读建议（~400字）")

        return f"""基于以下资料，为英文书籍《{book_title}》{author_info}生成一篇中文播客稿。

{research_context}

## 创作要求

1. **目标字数**：约 {target_words} 字（目标时长对应）
2. **语言风格**：{style_guide}
3. **结构要求**：
{chr(10).join(f'   {s}' for s in sections_guide)}

## 内容准则

✅ **必须做到**：
- 所有观点必须有来源支持，引用时标注来源
- 区分故事情节与评论观点
- 区分专业书评与读者评论
- 明确标注不确定的信息
- 保持客观，呈现不同视角

❌ **不得**：
- 不得编造书中情节或评论内容
- 不得把出版社简介当作独立书评
- 不得过度概括或夸大评价
- 不得使用未提供来源的信息

## 引用格式
- 直接引用：「……」（来源：XXX）
- 间接引用：根据XXX的评论，……

## 输出格式
使用 Markdown 格式，清晰的章节标题，自然的段落划分。

请生成播客稿："""

    def _build_english_prompt(
        self,
        book_title: str,
        book_author: Optional[str],
        research_context: str,
        style: str,
        target_words: int,
        include_sections: List[str],
    ) -> str:
        """Build prompt for English script generation."""
        author_info = f" by {book_author}" if book_author else ""

        style_guide = {
            "conversational": "Conversational and engaging, like a book club discussion",
            "formal": "Formal and professional, suitable for academic or professional audiences",
            "casual": "Casual and personal, with strong opinions and personality"
        }.get(style, "Conversational and natural")

        sections_guide = []
        if "introduction" in include_sections:
            sections_guide.append("**Introduction**: Brief book intro and episode theme (~300 words)")
        if "summary" in include_sections:
            sections_guide.append("**Summary**: Plot overview or main arguments (~500 words)")
        if "analysis" in include_sections:
            sections_guide.append("**Analysis**: Deep dive into themes, characters, or writing (~700 words)")
        if "themes" in include_sections:
            sections_guide.append("**Theme Discussion**: Explore user-specified themes (~500 words)")
        if "conclusion" in include_sections:
            sections_guide.append("**Conclusion**: Wrap up and recommendations (~250 words)")

        return f"""Based on the following research materials, generate an English podcast script for the book "{book_title}"{author_info}.

{research_context}

## Requirements

1. **Target Length**: Approximately {target_words} words (for target duration)
2. **Style**: {style_guide}
3. **Structure**:
{chr(10).join(f'   {s}' for s in sections_guide)}

## Content Guidelines

✅ **Must**:
- Support all claims with source attribution
- Distinguish plot summary from critical analysis
- Distinguish professional reviews from reader opinions
- Mark uncertain information clearly
- Present multiple perspectives when available

❌ **Must Not**:
- Fabricate plot details or review content
- Treat publisher descriptions as independent reviews
- Overgeneralize or exaggerate assessments
- Use information without source support

## Citation Format
- Direct quote: "..." (Source: XXX)
- Paraphrase: According to XXX's review, ...

## Output Format
Use Markdown with clear section headings and natural paragraph flow.

Generate the podcast script:"""

    async def generate_and_validate(
        self,
        book_title: str,
        book_author: Optional[str],
        book_description: Optional[str],
        theme_matches: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        material_assessment: Dict[str, Any],
        language: str = "zh",
        style: str = "conversational",
        target_duration: int = 25,
        include_sections: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate script and validate it.

        Returns dict with:
        - content: Generated script
        - word_count: Word count
        - estimated_minutes: Estimated duration
        - is_sufficient: Whether it meets duration target
        - validation_issues: List of issues
        - validation_report: Full validation report
        """
        # Generate script
        script = await self.generate_script(
            book_title, book_author, book_description,
            theme_matches, sources, material_assessment,
            language, style, target_duration, include_sections
        )

        # Validate
        analysis = self.validator.validate(script)
        report = self.validator.format_report(analysis)

        return {
            "content": script,
            "word_count": analysis.total_words,
            "estimated_minutes": analysis.estimated_minutes,
            "is_sufficient": analysis.is_sufficient,
            "validation_issues": analysis.issues,
            "validation_report": report,
        }
