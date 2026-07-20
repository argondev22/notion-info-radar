"""収集 → 重複除去 → DB_APPLICATION_PAGES にカテゴリ別・日次ダイジェストを作成。

毎日 カテゴリごとに1ページ（新着があるカテゴリのみ）。対象カテゴリは
src/sources.py の SOURCES から自動導出されるので、カテゴリ追加は sources.py への
ソース追加＋Notionでのタグ作成だけで済む。

使い方:
  python -m src.main --dry-run   # 書き込まず、各ページに入る内容を表示
  python -m src.main --seed      # 現在の記事を全て「取り込み済み」に（初回の氾濫防止）
  python -m src.main --limit N   # 動作確認用に候補を N 件に絞る
  python -m src.main             # ダイジェストページを作成
"""
import argparse
import logging
from datetime import datetime, timedelta, timezone

from . import config
from .collect import collect_source
from .models import Item
from .sources import CATEGORY_ORDER, SOURCES
from .state import load_seen, save_seen

log = logging.getLogger("info-radar")

JST = timezone(timedelta(hours=9))


def within_window(item: Item) -> bool:
    if item.published is None:
        return True  # 日付なしは dedup と件数上限に任せる
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.LOOKBACK_DAYS)
    return item.published >= cutoff


def _sort_key(item: Item) -> datetime:
    return item.published or datetime.min.replace(tzinfo=timezone.utc)


def collect_all() -> list[Item]:
    items: list[Item] = []
    for src in SOURCES:
        try:
            got = collect_source(src)
            log.info("collected %2d from %s", len(got), src.name)
            items.extend(got)
        except Exception as e:  # ソース単位で握りつぶして継続
            log.warning("source failed: %s (%s)", src.name, e)
    return items


def select_candidates(items: list[Item], seen: set[str]) -> list[Item]:
    dedup: dict[str, Item] = {}
    for i in items:
        if i.url in seen or not within_window(i):
            continue
        dedup.setdefault(i.url, i)
    return sorted(dedup.values(), key=_sort_key, reverse=True)


def group_by_category(items: list[Item]) -> dict[str, list[Item]]:
    groups: dict[str, list[Item]] = {}
    for i in items:
        groups.setdefault(i.category, []).append(i)
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description="AWS/Claude 情報収集 → Notion カテゴリ別日次ダイジェスト")
    parser.add_argument("--dry-run", action="store_true", help="書き込まず、内容を表示")
    parser.add_argument("--seed", action="store_true",
                        help="現在の記事を全て『取り込み済み』にする（登録はしない）")
    parser.add_argument("--limit", type=int, default=None, help="候補を N 件に絞る（動作確認用）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    seen_list = load_seen()
    seen = set(seen_list)

    items = collect_all()
    candidates = select_candidates(items, seen)
    if args.limit:
        candidates = candidates[: args.limit]
    groups = group_by_category(candidates)
    log.info("candidates: %d  内訳: %s", len(candidates),
             {c: len(groups.get(c, [])) for c in CATEGORY_ORDER})

    if args.seed:
        seen_list.extend(c.url for c in candidates)
        save_seen(seen_list)
        log.info("seeded %d urls as seen (no page created)", len(candidates))
        return

    digest_date = datetime.now(JST).date()

    if args.dry_run:
        for cat in CATEGORY_ORDER:
            entries = groups.get(cat, [])
            if not entries:
                continue
            print(f"\n=== {cat} ページ  タイトル:{digest_date.isoformat()}  (TAG={cat}, NOTE=ニュース) ===")
            for c in entries:
                d = c.published.date().isoformat() if c.published else "----------"
                print(f"  - [{d}] {c.title}")
        print(f"\n作成予定ページ数: {sum(1 for cat in CATEGORY_ORDER if groups.get(cat))}")
        return

    if not candidates:
        log.info("no new items; nothing to create")
        return

    if not config.NOTION_TOKEN or not config.NOTION_DATABASE_ID:
        raise SystemExit("NOTION_TOKEN / NOTION_DATABASE_ID が未設定です (.env を確認)")

    from .notion_sink import NotionTarget, get_client

    target = NotionTarget(get_client(), config.NOTION_DATABASE_ID)
    created = 0
    for cat in CATEGORY_ORDER:
        entries = groups.get(cat, [])
        if not entries:
            continue
        try:
            page, tid = target.create_category_digest(cat, digest_date, entries)
            if tid is None:
                log.warning("  ! %s: タグ未検出のため TAG 未設定で作成。"
                            "Notionの『ニュース』ノート配下に『%s』タグを作ると次回から付きます。", cat, cat)
            seen_list.extend(e.url for e in entries)
            created += 1
            log.info("  + %s ページ作成 (%d件)  %s", cat, len(entries), page.get("url", ""))
        except Exception as e:
            log.warning("%s ページ作成失敗: %s", cat, e)
    save_seen(seen_list)
    log.info("done. %d ページ作成", created)


if __name__ == "__main__":
    main()
