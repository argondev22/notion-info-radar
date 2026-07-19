"""収集 → 重複除去 → Notion にダイジェスト1ページ作成。

使い方:
  python -m src.main --dry-run   # 書き込まず、ダイジェスト内容を表示
  python -m src.main --seed      # 現在の記事を全て「取り込み済み」に（初回の氾濫防止）
  python -m src.main             # ダイジェストページを作成
"""
import argparse
import logging
from datetime import datetime, timedelta, timezone

from . import config
from .collect import collect_source
from .models import Item
from .sources import SOURCES
from .state import load_seen, save_seen

log = logging.getLogger("info-radar")

JST = timezone(timedelta(hours=9))
CATEGORY_LABELS = [("AWS", "☁️ AWS"), ("Claude", "🤖 Claude")]


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
    parser = argparse.ArgumentParser(description="AWS/Claude 情報収集 → Notion ダイジェスト")
    parser.add_argument("--dry-run", action="store_true",
                        help="書き込まず、ダイジェスト内容を表示")
    parser.add_argument("--seed", action="store_true",
                        help="現在の記事を全て『取り込み済み』にする（登録はしない）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    seen_list = load_seen()
    seen = set(seen_list)

    items = collect_all()
    candidates = select_candidates(items, seen)
    log.info("candidates: %d (collected=%d)", len(candidates), len(items))

    if args.seed:
        seen_list.extend(c.url for c in candidates)
        save_seen(seen_list)
        log.info("seeded %d urls as seen (no page created)", len(candidates))
        return

    groups = group_by_category(candidates)
    digest_date = datetime.now(JST).date()
    aws_n = len(groups.get("AWS", []))
    claude_n = len(groups.get("Claude", []))
    title = f"情報ダイジェスト {digest_date.isoformat()}（AWS {aws_n} / Claude {claude_n}）"

    if args.dry_run:
        print(f"# {title}\n")
        for key, label in CATEGORY_LABELS:
            entries = groups.get(key, [])
            if not entries:
                continue
            print(f"## {label} ({len(entries)})")
            for c in entries:
                d = c.published.date().isoformat() if c.published else "----------"
                print(f"  - [{d}] {c.title}")
                print(f"    {c.url}")
            print()
        return

    if not candidates:
        log.info("no new items; digest not created")
        return

    if not config.NOTION_TOKEN or not config.NOTION_DATABASE_ID:
        raise SystemExit("NOTION_TOKEN / NOTION_DATABASE_ID が未設定です (.env を確認)")

    from .notion_sink import create_digest, get_client

    client = get_client()
    page = create_digest(client, config.NOTION_DATABASE_ID, title, digest_date, groups)
    seen_list.extend(c.url for c in candidates)
    save_seen(seen_list)
    log.info("created digest: %s (%d items)", page.get("url", "?"), len(candidates))


if __name__ == "__main__":
    main()
