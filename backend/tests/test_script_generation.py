"""Test script generation functionality."""

import pytest
from app.services.script_generator import PodcastScriptGenerator


@pytest.fixture
def sample_research_data():
    """Sample research data for testing."""
    return {
        "book_title": "The Midnight Library",
        "book_author": "Matt Haig",
        "book_description": "A novel about a library between life and death where every book is a different life you could have lived.",
        "theme_matches": [
            {
                "theme": "death",
                "status": "candidate",
                "reasoning": "The book explores themes of life, death, and suicide. The protagonist attempts suicide and finds herself in a liminal space.",
            },
            {
                "theme": "parallel worlds",
                "status": "candidate",
                "reasoning": "The library contains infinite books, each representing a different life path - essentially parallel universes.",
            }
        ],
        "sources": [
            {
                "title": "The Guardian Review",
                "source_type": "professional_review",
                "summary": "A thought-provoking exploration of regret, choice, and the search for meaning.",
                "key_points": [
                    "Explores existential questions about life choices",
                    "Protagonist Nora Seed navigates infinite possibilities",
                    "Ultimately affirms the value of life"
                ],
                "is_about_target": True,
            },
            {
                "title": "Goodreads Reader Review",
                "source_type": "reader_review",
                "summary": "A heartfelt story that resonated deeply with me about mental health and finding purpose.",
                "key_points": [
                    "Relatable protagonist struggling with depression",
                    "Creative concept execution",
                    "Emotional and uplifting ending"
                ],
                "is_about_target": True,
            }
        ],
        "material_assessment": {
            "total_unique_sources": 8,
            "professional_review_count": 3,
            "independent_review_count": 5,
        }
    }


@pytest.mark.asyncio
async def test_chinese_script_generation(sample_research_data):
    """Test generating a Chinese podcast script."""
    generator = PodcastScriptGenerator()

    result = await generator.generate_and_validate(
        book_title=sample_research_data["book_title"],
        book_author=sample_research_data["book_author"],
        book_description=sample_research_data["book_description"],
        theme_matches=sample_research_data["theme_matches"],
        sources=sample_research_data["sources"],
        material_assessment=sample_research_data["material_assessment"],
        language="zh",
        style="conversational",
        target_duration=25,
    )

    # Verify structure
    assert "content" in result
    assert "word_count" in result
    assert "estimated_minutes" in result
    assert "is_sufficient" in result

    # Verify content
    content = result["content"]
    assert len(content) > 100
    assert "Midnight Library" in content or "午夜图书馆" in content

    # Check if it mentions themes
    assert "death" in content.lower() or "死亡" in content

    # Verify word count is reasonable
    assert result["word_count"] > 2000  # Should have substantial content

    print(f"\n=== Generated Chinese Script ===")
    print(f"Word count: {result['word_count']}")
    print(f"Estimated duration: {result['estimated_minutes']} minutes")
    print(f"Is sufficient: {result['is_sufficient']}")
    print(f"\nFirst 500 characters:")
    print(content[:500])


@pytest.mark.asyncio
async def test_english_script_generation(sample_research_data):
    """Test generating an English podcast script."""
    generator = PodcastScriptGenerator()

    result = await generator.generate_and_validate(
        book_title=sample_research_data["book_title"],
        book_author=sample_research_data["book_author"],
        book_description=sample_research_data["book_description"],
        theme_matches=sample_research_data["theme_matches"],
        sources=sample_research_data["sources"],
        material_assessment=sample_research_data["material_assessment"],
        language="en",
        style="conversational",
        target_duration=25,
    )

    # Verify structure
    assert "content" in result
    content = result["content"]

    # Should be in English
    assert "The Midnight Library" in content
    assert "Matt Haig" in content

    # Check themes
    assert "death" in content.lower() or "life" in content.lower()

    print(f"\n=== Generated English Script ===")
    print(f"Word count: {result['word_count']}")
    print(f"Estimated duration: {result['estimated_minutes']} minutes")
    print(f"\nFirst 500 characters:")
    print(content[:500])


@pytest.mark.asyncio
async def test_different_styles(sample_research_data):
    """Test different writing styles."""
    generator = PodcastScriptGenerator()

    styles = ["conversational", "formal", "casual"]

    for style in styles:
        result = await generator.generate_and_validate(
            book_title=sample_research_data["book_title"],
            book_author=sample_research_data["book_author"],
            book_description=sample_research_data["book_description"],
            theme_matches=sample_research_data["theme_matches"],
            sources=sample_research_data["sources"],
            material_assessment=sample_research_data["material_assessment"],
            language="en",
            style=style,
            target_duration=25,
        )

        assert result["content"]
        print(f"\n=== Style: {style} ===")
        print(f"Word count: {result['word_count']}")
        print(f"First 200 chars: {result['content'][:200]}")


@pytest.mark.asyncio
async def test_custom_sections(sample_research_data):
    """Test generating script with custom sections."""
    generator = PodcastScriptGenerator()

    result = await generator.generate_and_validate(
        book_title=sample_research_data["book_title"],
        book_author=sample_research_data["book_author"],
        book_description=sample_research_data["book_description"],
        theme_matches=sample_research_data["theme_matches"],
        sources=sample_research_data["sources"],
        material_assessment=sample_research_data["material_assessment"],
        language="zh",
        style="conversational",
        target_duration=25,
        include_sections=["introduction", "summary", "themes", "conclusion"],
    )

    content = result["content"]

    # Should have clear structure
    assert "#" in content  # Markdown headers

    print(f"\n=== Custom Sections Script ===")
    print(content[:1000])


@pytest.mark.asyncio
async def test_validation_report(sample_research_data):
    """Test that validation report is included."""
    generator = PodcastScriptGenerator()

    result = await generator.generate_and_validate(
        book_title=sample_research_data["book_title"],
        book_author=sample_research_data["book_author"],
        book_description=sample_research_data["book_description"],
        theme_matches=sample_research_data["theme_matches"],
        sources=sample_research_data["sources"],
        material_assessment=sample_research_data["material_assessment"],
        language="zh",
        target_duration=25,
    )

    # Should have validation report
    assert "validation_report" in result
    report = result["validation_report"]

    assert "播客稿评估报告" in report or "基础指标" in report
    assert str(result["word_count"]) in report

    print(f"\n=== Validation Report ===")
    print(report)


if __name__ == "__main__":
    import asyncio

    # Quick manual test
    sample_data = {
        "book_title": "The Midnight Library",
        "book_author": "Matt Haig",
        "book_description": "A novel about a library between life and death.",
        "theme_matches": [
            {
                "theme": "death",
                "status": "candidate",
                "reasoning": "Explores themes of life and death.",
            }
        ],
        "sources": [
            {
                "title": "Sample Review",
                "source_type": "professional_review",
                "summary": "A thought-provoking book.",
                "key_points": ["Meaningful", "Well-written"],
                "is_about_target": True,
            }
        ],
        "material_assessment": {
            "total_unique_sources": 5,
            "professional_review_count": 2,
            "independent_review_count": 3,
        }
    }

    async def quick_test():
        generator = PodcastScriptGenerator()
        result = await generator.generate_and_validate(**sample_data, language="zh")
        print(result["validation_report"])
        print("\n" + "="*80 + "\n")
        print(result["content"][:1000])

    asyncio.run(quick_test())
