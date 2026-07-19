"""各ソースから記事を収集する。ソース単位で失敗しても全体は止めない設計。"""
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup

from . import config
from .models import Item
from .sources import Source

log = logging.getLogger(__name__)

_WS = re.compile(r"\s+")
_MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
_MONTHS = {}
for _i, _m in enumerate(_MONTH_NAMES, start=1):
    _MONTHS[_m] = _i        # フルネーム: July
    _MONTHS[_m[:3]] = _i    # 3文字略記: Jul


def _clean_text(raw: str) -> str:
    if not raw:
        return ""
    text = BeautifulSoup(raw, "html.parser").get_text(" ")
    return _WS.sub(" ", text).strip()[: config.NOTION_TEXT_LIMIT]


def _get(url: str) -> requests.Response:
    resp = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp


def _struct_to_dt(st) -> Optional[datetime]:
    if not st:
        return None
    try:
        return datetime(*st[:6], tzinfo=timezone.utc)
    except Exception:
        return None


def _parse_date_text(text: str) -> Optional[datetime]:
    """'July 15, 2026' のような英語日付を拾う。"""
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", text)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    try:
        return datetime(int(m.group(3)), month, int(m.group(2)), tzinfo=timezone.utc)
    except Exception:
        return None


def collect_source(src: Source) -> list[Item]:
    if src.kind == "rss":
        return _collect_rss(src)
    if src.kind == "github_changelog":
        return _collect_github_changelog(src)
    if src.kind == "scrape_anthropic_news":
        return _collect_anthropic_news(src)
    if src.kind == "scrape_claude_relnotes":
        return _collect_claude_relnotes(src)
    raise ValueError(f"unknown source kind: {src.kind}")


def _collect_rss(src: Source) -> list[Item]:
    feed = feedparser.parse(_get(src.url).content)
    items: list[Item] = []
    for e in feed.entries[: config.MAX_PER_SOURCE]:
        link = e.get("link")
        title = e.get("title")
        if not link or not title:
            continue
        summary = _clean_text(e.get("summary", "") or e.get("description", ""))
        published = _struct_to_dt(e.get("published_parsed") or e.get("updated_parsed"))
        items.append(
            Item(
                title=title.strip(),
                url=link,
                summary=summary,
                published=published,
                category=src.category,
                source_name=src.name,
            )
        )
    return items


def _collect_github_changelog(src: Source) -> list[Item]:
    text = _get(src.url).text
    items: list[Item] = []
    for block in re.split(r"^##\s+", text, flags=re.MULTILINE):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        version = lines[0].strip()
        if not re.match(r"^v?\d+\.\d+", version):
            continue
        body = _WS.sub(
            " ", " ".join(l.strip("-* ").strip() for l in lines[1:] if l.strip())
        )
        anchor = "v" + version.lstrip("v")
        url = f"https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#{anchor}"
        items.append(
            Item(
                title=f"Claude Code {version}",
                url=url,
                summary=body[: config.NOTION_TEXT_LIMIT],
                published=None,
                category=src.category,
                source_name=src.name,
            )
        )
        break  # 最新の1バージョンのみ（パッチ版の氾濫を防ぐ）
    return items


def _collect_anthropic_news(src: Source) -> list[Item]:
    soup = BeautifulSoup(_get(src.url).text, "html.parser")
    items: list[Item] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if not href.startswith("/news/") or href == "/news/":
            continue
        url = "https://www.anthropic.com" + href
        if url in seen:
            continue
        # カードは2種類: featured=<h2/h4>にタイトル / grid=<span>にタイトル
        time_el = a.find("time")
        cat_span = time_el.parent.find("span") if (time_el and time_el.parent) else None
        heading = a.find(["h1", "h2", "h3", "h4", "h5"])
        if heading is not None:
            title = _WS.sub(" ", heading.get_text(" ")).strip()
        else:
            title = ""
            for sp in a.find_all("span"):
                if sp is cat_span:  # カテゴリ(Product等)はスキップ
                    continue
                txt = _WS.sub(" ", sp.get_text(" ")).strip()
                if len(txt) >= 4:
                    title = txt
                    break
        if len(title) < 4:
            continue
        seen.add(url)
        published = _parse_date_text(time_el.get_text(" ")) if time_el else None
        p = a.find("p")
        summary = _clean_text(p.get_text(" ")) if p else ""
        items.append(
            Item(
                title=title[: config.NOTION_TEXT_LIMIT],
                url=url,
                summary=summary,
                published=published,
                category=src.category,
                source_name=src.name,
            )
        )
        if len(items) >= config.MAX_PER_SOURCE:
            break
    return items


def _collect_claude_relnotes(src: Source) -> list[Item]:
    soup = BeautifulSoup(_get(src.url).text, "html.parser")
    items: list[Item] = []
    for h in soup.find_all(["h2", "h3"]):
        heading = _WS.sub(" ", h.get_text(" ")).strip()
        dt = _parse_date_text(heading)
        if dt is None:
            continue
        parts = []
        for sib in h.find_next_siblings():
            if getattr(sib, "name", None) in ("h1", "h2", "h3"):
                break
            parts.append(sib.get_text(" ") if hasattr(sib, "get_text") else str(sib))
        summary = _WS.sub(" ", " ".join(parts)).strip()
        url = f"{src.url}#{dt.date().isoformat()}"
        items.append(
            Item(
                title=f"Claude Platform release notes ({dt.date().isoformat()})",
                url=url,
                summary=summary[: config.NOTION_TEXT_LIMIT],
                published=dt,
                category=src.category,
                source_name=src.name,
            )
        )
        if len(items) >= config.MAX_PER_SOURCE:
            break
    return items
