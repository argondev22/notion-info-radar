"""Notion への登録：DB_APPLICATION_PAGES にカテゴリ別・日次ダイジェストページを作る。

- 毎日 カテゴリごとに1ページ（新着があるカテゴリのみ）
- タイトル=日付 / TAG=カテゴリ（名前で自動解決）/ NOTE=ニュース / 本文=記事の箇条書き
- 新しい Notion API（データソース構造）に対応

拡張性:
- TAG は「ニュースノート配下で名前がカテゴリ名と一致するタグ」を実行時に解決するので、
  新カテゴリを足すときに ID を調べてハードコードする必要がない。
"""
from datetime import date
from typing import Optional

from notion_client import Client

from . import config
from .models import Item


def get_client() -> Client:
    return Client(auth=config.NOTION_TOKEN)


def _text(content: str, link: Optional[str] = None) -> dict:
    node = {"type": "text", "text": {"content": content[: config.NOTION_TEXT_LIMIT]}}
    if link:
        node["text"]["link"] = {"url": link}
    return node


def _bullet(item: Item) -> dict:
    rich = []
    if item.published:
        rich.append(_text(f"{item.published.date().isoformat()}  "))
    rich.append(_text(item.title, link=item.url))
    if item.summary:
        rich.append(_text(" — " + item.summary[:200]))
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich},
    }


class NotionTarget:
    """登録先DBと、その TAG リレーション先を解決して保持する。"""

    def __init__(self, client: Client, database_id: str):
        self.client = client
        db = client.databases.retrieve(database_id=database_id)
        sources = db.get("data_sources") or []
        if not sources:
            raise RuntimeError("data_sources が取得できません（Notion APIバージョンを確認）")
        self.data_source_id = sources[0]["id"]
        # TAG リレーションの参照先データソースを動的取得（ハードコード不要）
        ds = client.request(path=f"data_sources/{self.data_source_id}", method="GET")
        self.tags_ds = ds["properties"].get("TAG", {}).get("relation", {}).get("data_source_id")
        self._tag_cache: dict[str, Optional[str]] = {}

    def tag_id(self, category: str) -> Optional[str]:
        """「ニュースノート配下で NAME==category」のタグの page_id を返す。無ければ None。"""
        if category in self._tag_cache:
            return self._tag_cache[category]
        tid: Optional[str] = None
        if self.tags_ds:
            q = self.client.request(
                path=f"data_sources/{self.tags_ds}/query",
                method="POST",
                body={"filter": {"and": [
                    {"property": "NAME", "title": {"equals": category}},
                    {"property": "NOTE", "relation": {"contains": config.NOTE_NEWS_ID}},
                ]}},
            )
            results = q.get("results", [])
            if results:
                tid = results[0]["id"]
        self._tag_cache[category] = tid
        return tid

    def create_category_digest(
        self, category: str, digest_date: date, items: list[Item]
    ) -> tuple[dict, Optional[str]]:
        props = {
            "NAME": {"title": [{"text": {"content": digest_date.isoformat()}}]},
            "NOTE": {"relation": [{"id": config.NOTE_NEWS_ID}]},
        }
        tid = self.tag_id(category)
        if tid:
            props["TAG"] = {"relation": [{"id": tid}]}

        blocks = [_bullet(i) for i in items]
        page = self.client.pages.create(
            parent={"type": "data_source_id", "data_source_id": self.data_source_id},
            properties=props,
            children=blocks[:100],  # 1リクエスト100ブロックまで
        )
        for i in range(100, len(blocks), 100):
            self.client.blocks.children.append(block_id=page["id"], children=blocks[i : i + 100])
        return page, tid
