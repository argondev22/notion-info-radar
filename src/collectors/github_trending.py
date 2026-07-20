"""GitHub Trending スクレイパー（kind: scrape_github_trending）。

公式RSS/APIが無いためHTMLをスクレイプする。上位のみ拾う（氾濫防止）。
"""
from bs4 import BeautifulSoup

from .. import config
from ..models import Item
from ..sources import Source
from . import register
from .common import WS, http_get

_MAX_TRENDING = 10  # トレンドは上位のみ


@register("scrape_github_trending")
def collect_github_trending(src: Source) -> list[Item]:
    soup = BeautifulSoup(http_get(src.url).text, "html.parser")
    items: list[Item] = []
    for art in soup.select("article.Box-row"):
        a = art.select_one("h2 a")
        if not a or not a.get("href"):
            continue
        repo = a["href"].strip("/")  # "owner/repo"
        url = "https://github.com/" + repo
        p = art.select_one("p")
        desc = WS.sub(" ", p.get_text(" ")).strip() if p else ""
        items.append(
            Item(
                title=repo,
                url=url,
                summary=desc[: config.NOTION_TEXT_LIMIT],
                published=None,
                category=src.category,
                source_name=src.name,
            )
        )
        if len(items) >= _MAX_TRENDING:
            break
    return items
