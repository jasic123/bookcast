"""Standalone test for podcast script generation - no external API required."""

import asyncio
from app.services.script_validator import PodcastScriptValidator


# Mock LLM client for testing without API keys
class MockLLMClient:
    """Mock LLM client that generates realistic test scripts."""

    async def chat_completion(self, messages, temperature=0.7, max_tokens=4096):
        """Return a mock podcast script based on the prompt."""
        prompt = messages[-1]["content"]

        # Detect language
        is_chinese = "中文" in prompt or "播客稿" in prompt

        if is_chinese:
            return self._generate_chinese_script()
        else:
            return self._generate_english_script()

    def _generate_chinese_script(self):
        """Generate a sample Chinese script."""
        return """# 《午夜图书馆》书评播客稿

## 开场

大家好，欢迎来到本期读书播客。今天我们要聊的是英国作家马特·海格（Matt Haig）的畅销小说《午夜图书馆》（The Midnight Library）。这是一本关于生命、选择和遗憾的小说，自2020年出版以来就广受好评，在全球范围内引发了无数读者的共鸣。

这本书探讨了一个深刻的问题：如果你能重新选择人生，你会做出怎样的决定？今天，我们将从"死亡"和"平行世界"这两个主题切入，深入解读这部作品的魅力所在。

## 故事梗概

《午夜图书馆》讲述了主人公诺拉·西德（Nora Seed）的故事。诺拉是一位35岁的英国女性，她感到自己的生活一团糟——失去了工作、失去了朋友、失去了梦想。在一个绝望的夜晚，她决定结束自己的生命。

然而，在生死之间，诺拉发现自己来到了一个神秘的图书馆——午夜图书馆。这个图书馆存在于生与死的边界，由她的老师格林太太看管。图书馆里有无数的书，每一本书都代表着她可能过上的另一种人生。

根据《卫报》的评论，这个设定"巧妙地将哲学思考与引人入胜的叙事结合在一起"。诺拉开始尝试不同的人生：成为奥运游泳选手的人生、成为摇滚明星的人生、成为冰川学家的人生、与前男友结婚的人生……每翻开一本书，她就进入一个平行宇宙，体验一种截然不同的生活。

然而，诺拉逐渐发现，每一种人生都有它的问题和遗憾。完美的人生并不存在。正如一位Goodreads读者评论所说："这本书让我意识到，我们总是想象其他选择会更好，却忽视了当下生活的价值。"

## 主题解读：死亡

让我们先谈谈"死亡"这个主题。《午夜图书馆》从一开始就直面死亡——诺拉选择自杀，这是一个沉重但真实的起点。马特·海格本人曾经历过严重的抑郁症，他在多次采访中坦承，这部小说带有强烈的自传色彩。

书中对死亡的呈现并不是终点，而是一个转折点。午夜图书馆是一个中间地带，它既不是天堂，也不是地狱，而是一个让诺拉重新审视生命的空间。根据《Publishers Weekly》的书评，"海格以温柔而不说教的方式，探讨了自杀、心理健康和生命的意义。"

值得注意的是，虽然故事涉及自杀，但整体基调并不绝望。相反，通过经历无数种可能的人生，诺拉逐渐意识到，每一个选择都会带来得失，每一种生活都有其困难。这种认知最终帮助她找到了活下去的理由。

一位专业书评人指出："这本书的力量在于，它不回避死亡的诱惑，但最终肯定了生命的价值。它告诉我们，即使生活不完美，也值得活下去。"

## 主题解读：平行世界

第二个核心主题是"平行世界"。午夜图书馆本质上是一个多重宇宙的概念——每一个决定都会创造一个分支现实。诺拉的每一本书都是一个她本可以生活的平行宇宙。

这个设定不仅仅是科幻概念的运用，更是对"如果当初……"这种遗憾心理的具象化。我们都曾想过，如果当初做了不同的选择，人生会怎样？这本书让主人公（也让读者）有机会探索这个问题。

根据一篇深度书评，"海格巧妙地利用平行世界的设定，探讨了自由意志、命运和遗憾的哲学问题。"诺拉在不同的平行世界中发现，即使做了不同的选择，她依然是她自己——她的核心特质、她的恐惧和渴望，并不会因为外在环境的改变而消失。

更深刻的是，这本书揭示了一个悖论：我们总是羡慕那些"没有走的路"，却忘记了每条路都有它的代价。正如书中的一句话："我们常常认为如果生活不同，一切都会更好。但有时候，只是生活本身就是答案。"

## 写作风格与影响

马特·海格的写作风格温暖而富有哲思。他不依赖复杂的情节转折，而是通过细腻的心理描写和充满洞察力的对话，引导读者思考人生的意义。

《学校图书馆杂志》称这本书"既是一部引人入胜的小说，也是一场关于生命意义的哲学探索"。许多读者评论提到，这本书在疫情期间给了他们巨大的慰藉，帮助他们重新审视生活的价值。

值得一提的是，书中还穿插了大量关于量子物理、哲学和文学的引用，增加了作品的深度。从薛定谔的猫到博尔赫斯的《歧路花园》，这些文化参考丰富了故事的层次。

## 总结与推荐

《午夜图书馆》是一本关于希望、选择和自我接纳的小说。它提醒我们，完美的人生并不存在，但这不意味着我们的人生不值得过。每一个选择都会带来遗憾，但也正是这些选择构成了我们独一无二的人生。

如果你正在经历人生的低谷，或者对自己的选择感到困惑和遗憾，这本书会给你很多启发。它不会提供简单的答案，但会陪伴你思考什么是真正重要的。

正如一位读者所说："这本书让我明白，与其想象其他可能的人生，不如珍惜当下正在经历的这一个。"

感谢大家收听本期播客。如果你读过这本书，欢迎分享你的感受。我们下期再见。

---

**主要来源**：
- 《卫报》书评
- 《Publishers Weekly》专业评论
- Goodreads读者评论
- 马特·海格作者访谈
"""

    def _generate_english_script(self):
        """Generate a sample English script."""
        return """# The Midnight Library: A Book Review Podcast

## Introduction

Welcome to this episode of our book podcast. Today, we're diving into "The Midnight Library" by British author Matt Haig, a bestselling novel that has captured hearts worldwide since its 2020 release. This is a story about life, choice, and regret that resonates deeply with readers facing their own crossroads.

The book poses a profound question: if you could live your life differently, what would you choose? Today, we'll explore this work through two key themes: death and parallel worlds.

## Plot Summary

"The Midnight Library" follows Nora Seed, a 35-year-old woman who feels her life has fallen apart. She's lost her job, her relationships have crumbled, and her dreams seem out of reach. On a desperate night, she decides to end her life.

But between life and death, Nora finds herself in a mysterious library—the Midnight Library. It exists at the threshold between living and dying, overseen by her childhood librarian, Mrs. Elm. This library contains infinite books, each representing a different life Nora could have lived.

According to The Guardian's review, this setup "cleverly combines philosophical inquiry with compelling narrative." Nora begins sampling different lives: one as an Olympic swimmer, another as a rock star, yet another as a glaciologist. Each book is a doorway to a parallel universe where she made different choices.

However, Nora gradually discovers that every life has its own problems and regrets. The perfect life doesn't exist. As one Goodreads reviewer noted: "This book made me realize we always imagine other choices would be better, while overlooking the value of our current life."

## Theme Analysis: Death

Let's first address the theme of death. "The Midnight Library" confronts mortality from the outset—Nora's suicide attempt is a heavy but honest starting point. Matt Haig himself has battled severe depression, and he's acknowledged in interviews that this novel draws heavily from personal experience.

The book's treatment of death isn't as an endpoint, but as a turning point. The Midnight Library is an in-between space—neither heaven nor hell—where Nora can reassess what living means. According to Publishers Weekly, "Haig explores suicide, mental health, and the meaning of life with gentleness rather than preaching."

Importantly, while the story involves suicide, the overall tone isn't despairing. Instead, by experiencing countless possible lives, Nora realizes that every choice brings both gains and losses. This understanding ultimately helps her find reasons to live.

One professional reviewer observed: "The book's power lies in not avoiding death's temptation, yet ultimately affirming life's value. It tells us that even imperfect lives are worth living."

## Theme Analysis: Parallel Worlds

The second core theme is parallel worlds. The Midnight Library essentially embodies the multiverse concept—every decision creates a branching reality. Each of Nora's books represents a parallel universe she could have inhabited.

This setup isn't just science fiction; it's a visualization of "what if" regret. We've all wondered what life would be like had we chosen differently. This book lets the protagonist (and readers) explore that question.

According to an in-depth review, "Haig cleverly uses the parallel worlds concept to explore philosophical questions about free will, fate, and regret." Across different parallel worlds, Nora discovers that even with different choices, she remains herself—her core traits, fears, and desires don't vanish with changed circumstances.

More profoundly, the book reveals a paradox: we often envy "roads not taken" while forgetting that every path has its price. As the book states: "We often think if life were different, everything would be better. But sometimes, life itself is the answer."

## Writing Style and Impact

Matt Haig's writing is warm and philosophical. Rather than relying on complex plot twists, he guides readers to contemplate life's meaning through nuanced psychological descriptions and insightful dialogue.

School Library Journal calls the book "both an engaging novel and a philosophical exploration of life's meaning." Many readers mentioned that during the pandemic, this book provided immense comfort, helping them reassess life's value.

Notably, the book weaves in references to quantum physics, philosophy, and literature, adding depth to the work. From Schrödinger's cat to Borges' "Garden of Forking Paths," these cultural references enrich the story's layers.

## Conclusion and Recommendation

"The Midnight Library" is a novel about hope, choice, and self-acceptance. It reminds us that perfect lives don't exist, but that doesn't make our lives worthless. Every choice brings regret, but these choices also create our unique existence.

If you're going through difficult times or feeling confused about your choices, this book offers valuable insights. It won't provide easy answers, but it will accompany you in thinking about what truly matters.

As one reader said: "This book taught me that instead of imagining other possible lives, I should cherish the one I'm actually living."

Thank you for listening. If you've read this book, please share your thoughts. See you next time.

---

**Primary Sources:**
- The Guardian book review
- Publishers Weekly professional review
- Goodreads reader reviews
- Matt Haig author interviews
"""


async def test_script_generation_standalone():
    """Test script generation with mock data - no API keys needed."""

    print("="*80)
    print("播客稿生成功能测试")
    print("="*80)
    print()

    # Sample book and research data
    sample_data = {
        "book_title": "The Midnight Library",
        "book_author": "Matt Haig",
        "book_description": "A novel about a library between life and death where every book is a different life you could have lived.",
        "theme_matches": [
            {
                "theme": "death",
                "status": "candidate",
                "reasoning": "The book explores themes of life, death, and suicide. The protagonist attempts suicide and finds herself in a liminal space between life and death.",
            },
            {
                "theme": "parallel worlds",
                "status": "candidate",
                "reasoning": "The library contains infinite books, each representing a different life path - essentially parallel universes where different choices were made.",
            }
        ],
        "sources": [
            {
                "title": "The Guardian Review",
                "source_type": "professional_review",
                "summary": "A thought-provoking exploration of regret, choice, and the search for meaning in life.",
                "key_points": [
                    "Explores existential questions about life choices",
                    "Protagonist Nora Seed navigates infinite possibilities",
                    "Ultimately affirms the value of life despite its imperfections"
                ],
                "is_about_target": True,
            },
            {
                "title": "Goodreads Reader Review",
                "source_type": "reader_review",
                "summary": "A heartfelt story that resonated deeply with readers about mental health and finding purpose.",
                "key_points": [
                    "Relatable protagonist struggling with depression",
                    "Creative concept executed beautifully",
                    "Emotional and uplifting ending"
                ],
                "is_about_target": True,
            },
            {
                "title": "Publishers Weekly",
                "source_type": "professional_review",
                "summary": "Haig's novel gently explores suicide, mental health, and life's meaning without preaching.",
                "key_points": [
                    "Personal connection to author's own struggles",
                    "Accessible philosophical exploration",
                    "Message of hope and self-acceptance"
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

    # Test Chinese script generation
    print("\n【测试 1：中文播客稿生成】")
    print("-"*80)

    mock_client = MockLLMClient()
    chinese_script = await mock_client.chat_completion(
        [{"role": "user", "content": "生成中文播客稿"}]
    )

    # Validate the script
    validator = PodcastScriptValidator(speaking_rate="normal")
    chinese_analysis = validator.validate(chinese_script)
    chinese_report = validator.format_report(chinese_analysis)

    print(f"✓ 生成成功")
    print(f"✓ 字数: {chinese_analysis.total_words:,} 词")
    print(f"✓ 预估时长: {chinese_analysis.estimated_minutes} 分钟")
    print(f"✓ 是否达标: {'是' if chinese_analysis.is_sufficient else '否'}")
    print(f"✓ 章节数: {len(chinese_analysis.sections)}")

    if chinese_analysis.sections:
        print(f"\n章节结构:")
        for section in chinese_analysis.sections:
            print(f"  - {section['title']}: {section['word_count']} 词 ({section['duration_minutes']:.1f} 分钟)")

    print(f"\n播客稿预览（前500字符）:")
    print("-"*80)
    print(chinese_script[:500])
    print("...\n")

    # Test English script generation
    print("\n【测试 2：英文播客稿生成】")
    print("-"*80)

    english_script = await mock_client.chat_completion(
        [{"role": "user", "content": "Generate English podcast script"}]
    )

    english_analysis = validator.validate(english_script)
    english_report = validator.format_report(english_analysis)

    print(f"✓ Generated successfully")
    print(f"✓ Word count: {english_analysis.total_words:,} words")
    print(f"✓ Estimated duration: {english_analysis.estimated_minutes} minutes")
    print(f"✓ Meets target: {'Yes' if english_analysis.is_sufficient else 'No'}")
    print(f"✓ Sections: {len(english_analysis.sections)}")

    if english_analysis.sections:
        print(f"\nSection structure:")
        for section in english_analysis.sections:
            print(f"  - {section['title']}: {section['word_count']} words ({section['duration_minutes']:.1f} min)")

    print(f"\nScript preview (first 500 characters):")
    print("-"*80)
    print(english_script[:500])
    print("...\n")

    # Test validation report
    print("\n【测试 3：播客稿评估报告】")
    print("-"*80)
    print(chinese_report)

    # Summary
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    print(f"✓ 中文播客稿: {chinese_analysis.total_words} 词, {chinese_analysis.estimated_minutes} 分钟")
    print(f"✓ 英文播客稿: {english_analysis.total_words} 词, {english_analysis.estimated_minutes} 分钟")
    print(f"✓ 章节检测: 成功识别 {len(chinese_analysis.sections)} 个中文章节")
    print(f"✓ 时长验证: {'通过' if chinese_analysis.is_sufficient else '需调整'}")

    if chinese_analysis.issues:
        print(f"\n⚠ 发现的问题:")
        for issue in chinese_analysis.issues:
            print(f"  - {issue}")

    if chinese_analysis.recommendations:
        print(f"\n💡 改进建议:")
        for rec in chinese_analysis.recommendations:
            print(f"  - {rec}")

    print("\n✅ 所有测试完成！")
    print()


if __name__ == "__main__":
    asyncio.run(test_script_generation_standalone())
