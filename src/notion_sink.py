"""Notion への登録：1回の実行 = 1枚のダイジェストページ。"""
from datetime import date
from typing import Optional

from notion_client import Client

from . import config
from .models import Item

# 表示順とラベル
CATEGORY_ORDER = [("AWS", "☁️ AWS"), ("Claude", "🤖 Claude")]


def get_client() -> Client:
    return Client(auth=config.NOTION_TOKEN)


def _text(content: str, link: Optional[str] = None) -> dict:
    node = {"type": "text", "text": {"content": content[: config.NOTION_TEXT_LIMIT]}}
    if link:
        node["text"]["link"] = {"url": link}
    return node


def _heading(content: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [_text(content)]},
    }


def _bullet(item: Item) -> dict:
    rich = [_text(item.title, link=item.url)]
    if item.summary:
        rich.append(_text(" — " + item.summary[:200]))
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich},
    }


def build_blocks(groups: dict[str, list[Item]]) -> list[dict]:
    blocks: list[dict] = []
    for key, label in CATEGORY_ORDER:
        entries = groups.get(key, [])
        if not entries:
            continue
        blocks.append(_heading(f"{label} ({len(entries)})"))
        blocks.extend(_bullet(e) for e in entries)
    return blocks


def create_digest(
    client: Client,
    database_id: str,
    title: str,
    digest_date: date,
    groups: dict[str, list[Item]],
) -> dict:
    blocks = build_blocks(groups)
    props = {
        "NAME": {"title": [{"text": {"content": title}}]},
        "DATE": {"date": {"start": digest_date.isoformat()}},
    }
    # Notion は pages.create / append とも 1 リクエスト 100 ブロックまで
    page = client.pages.create(
        parent={"database_id": database_id},
        properties=props,
        children=blocks[:100],
    )
    for i in range(100, len(blocks), 100):
        client.blocks.children.append(block_id=page["id"], children=blocks[i : i + 100])
    return page
