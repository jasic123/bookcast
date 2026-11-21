"""Podcast script validator - validates if script is sufficient for 20-30 minute audio."""

import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class ScriptAnalysis:
    """Analysis results for a podcast script."""
    total_words: int
    total_chars: int
    estimated_minutes: float
    is_sufficient: bool
    sections: List[Dict[str, Any]]
    issues: List[str]
    recommendations: List[str]


class PodcastScriptValidator:
    """Validates podcast scripts for length and structure."""

    # Average speaking rates (words per minute)
    WPM_SLOW = 120      # Slow, explanatory speech
    WPM_NORMAL = 150    # Normal conversational pace
    WPM_FAST = 180      # Fast, energetic delivery

    # Target duration
    TARGET_MIN_MINUTES = 20
    TARGET_MAX_MINUTES = 30
    IDEAL_MINUTES = 25

    def __init__(self, speaking_rate: str = "normal"):
        """
        Initialize validator.

        Args:
            speaking_rate: "slow", "normal", or "fast"
        """
        self.wpm = {
            "slow": self.WPM_SLOW,
            "normal": self.WPM_NORMAL,
            "fast": self.WPM_FAST,
        }.get(speaking_rate, self.WPM_NORMAL)

    def count_words(self, text: str) -> int:
        """Count words in text, excluding pure punctuation."""
        # Remove common markdown/formatting
        text = re.sub(r'[#*_~`]', '', text)
        # Split and count
        words = [w for w in text.split() if re.search(r'\w', w)]
        return len(words)

    def estimate_duration(self, word_count: int) -> float:
        """
        Estimate speaking duration in minutes.

        Includes buffer for pauses, transitions, music.
        """
        base_minutes = word_count / self.wpm
        # Add 10% buffer for natural pauses
        return base_minutes * 1.1

    def detect_sections(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect major sections in the script.

        Returns list of sections with title, word count, estimated duration.
        """
        sections = []

        # Split by markdown headers or clear section markers
        lines = text.split('\n')
        current_section = {"title": "Introduction", "content": []}

        for line in lines:
            # Check for section headers (##, ###, or "Section:", "Part:")
            header_match = re.match(r'^#{2,3}\s+(.+)$', line)
            keyword_match = re.match(r'^(Introduction|Part|Section|Segment|Opening|Discussion|Analysis|Conclusion|Closing)[\s:]+(.+)$', line, re.IGNORECASE)

            if header_match or keyword_match:
                # Save previous section
                if current_section["content"]:
                    content_text = '\n'.join(current_section["content"])
                    word_count = self.count_words(content_text)
                    sections.append({
                        "title": current_section["title"],
                        "word_count": word_count,
                        "duration_minutes": self.estimate_duration(word_count),
                    })

                # Start new section
                title = header_match.group(1) if header_match else (keyword_match.group(2) or keyword_match.group(1))
                current_section = {"title": title.strip(), "content": []}
            else:
                current_section["content"].append(line)

        # Add final section
        if current_section["content"]:
            content_text = '\n'.join(current_section["content"])
            word_count = self.count_words(content_text)
            sections.append({
                "title": current_section["title"],
                "word_count": word_count,
                "duration_minutes": self.estimate_duration(word_count),
            })

        return sections

    def analyze_structure(self, sections: List[Dict[str, Any]]) -> List[str]:
        """Analyze script structure and identify issues."""
        issues = []

        if not sections:
            issues.append("No clear sections detected - consider adding structure")
            return issues

        # Check for unbalanced sections
        durations = [s["duration_minutes"] for s in sections]
        max_duration = max(durations)
        min_duration = min(durations)

        if max_duration > min_duration * 5 and len(sections) > 1:
            issues.append(f"Unbalanced sections: longest is {max_duration:.1f}min, shortest is {min_duration:.1f}min")

        # Check for very short sections
        short_sections = [s for s in sections if s["duration_minutes"] < 1.0]
        if short_sections:
            issues.append(f"{len(short_sections)} section(s) under 1 minute - may need expansion")

        # Check for very long sections
        long_sections = [s for s in sections if s["duration_minutes"] > 10.0]
        if long_sections:
            issues.append(f"{len(long_sections)} section(s) over 10 minutes - consider breaking down")

        return issues

    def generate_recommendations(
        self,
        total_words: int,
        estimated_minutes: float,
        sections: List[Dict[str, Any]],
        issues: List[str],
    ) -> List[str]:
        """Generate recommendations for improving the script."""
        recommendations = []

        # Duration recommendations
        if estimated_minutes < self.TARGET_MIN_MINUTES:
            shortage = self.TARGET_MIN_MINUTES - estimated_minutes
            words_needed = int(shortage * self.wpm / 1.1)
            recommendations.append(
                f"Add approximately {words_needed} words ({shortage:.1f} minutes) to reach minimum duration"
            )
            recommendations.append(
                "Consider expanding: analysis depth, examples, context, or author background"
            )

        elif estimated_minutes > self.TARGET_MAX_MINUTES:
            excess = estimated_minutes - self.TARGET_MAX_MINUTES
            words_to_cut = int(excess * self.wpm / 1.1)
            recommendations.append(
                f"Consider cutting approximately {words_to_cut} words ({excess:.1f} minutes) to fit target duration"
            )
            recommendations.append(
                "Focus on key themes, remove redundancy, or split into multiple episodes"
            )

        else:
            recommendations.append(
                f"Duration is within target range ({self.TARGET_MIN_MINUTES}-{self.TARGET_MAX_MINUTES} minutes) ✓"
            )

        # Structure recommendations
        if not sections or len(sections) < 3:
            recommendations.append(
                "Consider adding clear sections: Introduction, Main Discussion, Conclusion"
            )

        if "unbalanced" in ' '.join(issues).lower():
            recommendations.append(
                "Rebalance sections for better pacing and listener engagement"
            )

        # Content recommendations based on word count
        if total_words < 2000:
            recommendations.append(
                "Script may lack depth - ensure sufficient analysis and examples"
            )

        return recommendations

    def validate(self, script_content: str) -> ScriptAnalysis:
        """
        Validate a podcast script.

        Args:
            script_content: Full script text

        Returns:
            ScriptAnalysis with detailed assessment
        """
        # Basic counts
        total_words = self.count_words(script_content)
        total_chars = len(script_content)
        estimated_minutes = self.estimate_duration(total_words)

        # Detect sections
        sections = self.detect_sections(script_content)

        # Analyze structure
        structural_issues = self.analyze_structure(sections)

        # Duration check
        is_sufficient = (
            self.TARGET_MIN_MINUTES <= estimated_minutes <= self.TARGET_MAX_MINUTES
        )

        issues = []
        if not is_sufficient:
            if estimated_minutes < self.TARGET_MIN_MINUTES:
                issues.append(
                    f"Script is too short: {estimated_minutes:.1f} min (target: {self.TARGET_MIN_MINUTES}-{self.TARGET_MAX_MINUTES} min)"
                )
            else:
                issues.append(
                    f"Script is too long: {estimated_minutes:.1f} min (target: {self.TARGET_MIN_MINUTES}-{self.TARGET_MAX_MINUTES} min)"
                )

        issues.extend(structural_issues)

        # Generate recommendations
        recommendations = self.generate_recommendations(
            total_words, estimated_minutes, sections, issues
        )

        return ScriptAnalysis(
            total_words=total_words,
            total_chars=total_chars,
            estimated_minutes=round(estimated_minutes, 1),
            is_sufficient=is_sufficient,
            sections=sections,
            issues=issues,
            recommendations=recommendations,
        )

    def format_report(self, analysis: ScriptAnalysis) -> str:
        """Format analysis results as a readable report."""
        report_lines = [
            "# 播客稿评估报告",
            "",
            "## 基础指标",
            f"- 总字数: {analysis.total_words:,} 词",
            f"- 总字符数: {analysis.total_chars:,}",
            f"- 预估时长: **{analysis.estimated_minutes} 分钟** (基于 {self.wpm} 词/分钟)",
            f"- 目标时长: {self.TARGET_MIN_MINUTES}-{self.TARGET_MAX_MINUTES} 分钟",
            "",
            f"## 时长评估: {'✅ 合格' if analysis.is_sufficient else '❌ 不合格'}",
            "",
        ]

        # Sections
        if analysis.sections:
            report_lines.extend([
                "## 内容结构",
                "",
                "| 章节 | 字数 | 预估时长 |",
                "|------|------|---------|",
            ])
            for section in analysis.sections:
                report_lines.append(
                    f"| {section['title']} | {section['word_count']} | {section['duration_minutes']:.1f} 分钟 |"
                )
            report_lines.append("")

        # Issues
        if analysis.issues:
            report_lines.extend([
                "## ⚠️ 发现的问题",
                "",
            ])
            for issue in analysis.issues:
                report_lines.append(f"- {issue}")
            report_lines.append("")

        # Recommendations
        if analysis.recommendations:
            report_lines.extend([
                "## 💡 改进建议",
                "",
            ])
            for rec in analysis.recommendations:
                report_lines.append(f"- {rec}")
            report_lines.append("")

        return '\n'.join(report_lines)
