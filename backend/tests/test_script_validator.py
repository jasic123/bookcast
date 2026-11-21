"""Test script validator."""

import pytest
from app.services.script_validator import PodcastScriptValidator


@pytest.fixture
def validator():
    return PodcastScriptValidator(speaking_rate="normal")


def test_word_count():
    validator = PodcastScriptValidator()

    text = "This is a simple test with ten words here."
    assert validator.count_words(text) == 10

    # Should ignore pure punctuation
    text_with_punct = "Hello, world! This is a test... right?"
    assert validator.count_words(text_with_punct) == 7


def test_duration_estimation():
    validator = PodcastScriptValidator(speaking_rate="normal")  # 150 wpm

    # 1500 words should be ~11 minutes (1500/150 * 1.1 = 11)
    duration = validator.estimate_duration(1500)
    assert 10 < duration < 12


def test_short_script():
    validator = PodcastScriptValidator()

    short_script = "This is a very short script. " * 100  # ~700 words, ~5 min
    analysis = validator.validate(short_script)

    assert not analysis.is_sufficient
    assert analysis.estimated_minutes < 20
    assert any("too short" in issue.lower() for issue in analysis.issues)
    assert any("add" in rec.lower() for rec in analysis.recommendations)


def test_sufficient_script():
    validator = PodcastScriptValidator()

    # Generate ~3750 words for 25 minutes
    sufficient_script = "This is a sufficient length script with adequate content. " * 375
    analysis = validator.validate(sufficient_script)

    assert analysis.is_sufficient
    assert 20 <= analysis.estimated_minutes <= 30


def test_long_script():
    validator = PodcastScriptValidator()

    # Generate ~6000 words for 40+ minutes
    long_script = "This is an overly long script with too much content here. " * 600
    analysis = validator.validate(long_script)

    assert not analysis.is_sufficient
    assert analysis.estimated_minutes > 30
    assert any("too long" in issue.lower() for issue in analysis.issues)
    assert any("cut" in rec.lower() for rec in analysis.recommendations)


def test_section_detection():
    validator = PodcastScriptValidator()

    script_with_sections = """
# Introduction

Welcome to the podcast. This is the opening section with some introductory content.

## Main Discussion

Here we discuss the main themes of the book. This section contains detailed analysis
and multiple perspectives on the central arguments.

### Key Points

First key point with explanation.
Second key point with examples.

## Conclusion

Wrapping up our discussion with final thoughts and recommendations.
"""

    sections = validator.detect_sections(script_with_sections)

    assert len(sections) >= 3
    assert any("introduction" in s["title"].lower() for s in sections)
    assert any("discussion" in s["title"].lower() for s in sections)
    assert all(s["word_count"] > 0 for s in sections)


def test_report_formatting(validator):
    script = "Test content for report formatting. " * 300  # ~25 minutes
    analysis = validator.validate(script)
    report = validator.format_report(analysis)

    assert "播客稿评估报告" in report
    assert "基础指标" in report
    assert "时长评估" in report
    assert str(analysis.total_words) in report
    assert str(analysis.estimated_minutes) in report


def test_different_speaking_rates():
    slow_validator = PodcastScriptValidator(speaking_rate="slow")
    normal_validator = PodcastScriptValidator(speaking_rate="normal")
    fast_validator = PodcastScriptValidator(speaking_rate="fast")

    script = "Test content. " * 1000  # 2000 words

    slow_duration = slow_validator.estimate_duration(2000)
    normal_duration = normal_validator.estimate_duration(2000)
    fast_duration = fast_validator.estimate_duration(2000)

    # Slower rate = longer duration
    assert slow_duration > normal_duration > fast_duration


@pytest.mark.parametrize("word_count,expected_sufficient", [
    (1000, False),   # ~7 min - too short
    (3000, True),    # ~20 min - sufficient
    (3750, True),    # ~25 min - ideal
    (4500, True),    # ~30 min - sufficient
    (6000, False),   # ~40 min - too long
])
def test_sufficiency_boundaries(validator, word_count, expected_sufficient):
    script = "Word " * word_count
    analysis = validator.validate(script)
    assert analysis.is_sufficient == expected_sufficient
