"""収集対象ソースの定義（確定した5本）。"""
from dataclasses import dataclass


@dataclass
class Source:
    key: str
    name: str
    category: str  # "AWS" | "Claude"
    kind: str      # "rss" | "github_changelog" | "scrape_anthropic_news" | "scrape_claude_relnotes"
    url: str


SOURCES = [
    Source(
        key="aws_whatsnew",
        name="AWS What's New",
        category="AWS",
        kind="rss",
        url="https://aws.amazon.com/about-aws/whats-new/recent/feed/",
    ),
    Source(
        key="aws_news_blog",
        name="AWS News Blog",
        category="AWS",
        kind="rss",
        url="https://aws.amazon.com/blogs/aws/feed/",
    ),
    Source(
        key="claude_code",
        name="Claude Code CHANGELOG",
        category="Claude",
        kind="github_changelog",
        url="https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md",
    ),
    Source(
        key="anthropic_news",
        name="Anthropic Newsroom",
        category="Claude",
        kind="scrape_anthropic_news",
        url="https://www.anthropic.com/news",
    ),
    Source(
        key="claude_relnotes",
        name="Claude Platform release notes",
        category="Claude",
        kind="scrape_claude_relnotes",
        url="https://platform.claude.com/docs/en/release-notes/overview",
    ),
]

# ソース定義から自動導出する表示順。
# 新カテゴリのソースを SOURCES に足せば、ここに自動で含まれる（他ファイルの変更不要）。
CATEGORY_ORDER = list(dict.fromkeys(s.category for s in SOURCES))
