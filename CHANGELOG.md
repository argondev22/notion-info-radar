# Changelog

このプロジェクトの主な変更点を記録する。
書式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)、
版番号は [Semantic Versioning](https://semver.org/lang/ja/)（`MAJOR.MINOR.PATCH`）に従う。

- **MAJOR**: 互換性のない変更（例: Notionのスキーマ変更で既存DBが使えなくなる）
- **MINOR**: 後方互換のある機能追加（例: ソース追加、Claude要約の導入）
- **PATCH**: 後方互換のバグ修正・小改善

## [Unreleased]

## [0.3.0] - 2026-07-20
### Added
- **IT カテゴリを追加**（🔒 セキュリティ / 🤖 AI / 🛠 ツール の3 section）。海外中心の良質ソース10本。
- ソースの `section`（任意）でページ内の記事をグループ順に並べる（同じ section が固まって上から並ぶ）。
- GitHub Trending 用スクレイパー（`scrape_github_trending`）。
### Changed
- ソース定義を設定ファイル `sources.yaml` に外出し。RSSソース/カテゴリ/並び順の追加が **YAML編集だけ**で可能に（Python不要）。
- コレクタを **プラグイン化**（`src/collectors/`、1 kind = 1ファイル・`@register` で自動登録）。新しいスクレイパーは**新ファイルを置くだけ**で追加でき、既存コードを触らない。

## [0.2.1] - 2026-07-20
### Changed
- 定期実行を 07:00 JST → **06:00 JST** に変更（cron `0 21 * * *`）。
- README / CLAUDE.md の見出し階層を整理（H1 は先頭のみ、以降は H2 以下）。

## [0.2.0] - 2026-07-20
### Changed
- 登録形式を「1記事=1レコード」から **カテゴリ別・日次ダイジェストページ** に変更。
  毎日カテゴリごとに1ページ作成（タイトル=日付、本文=記事のリンク箇条書き）。
- 登録先を専用DBから既存の `DB_APPLICATION_PAGES` に変更。`NOTE`（ニュース）/ `TAG`（カテゴリ）リレーションを設定。
- 新しい Notion API（データソース構造）に対応（`pages.create` の parent を `data_source_id` 指定に）。
### Added
- 対象カテゴリを `sources.py` から自動導出（`CATEGORY_ORDER`）。
- `TAG` を「ニュースノート配下で名前がカテゴリ名と一致するタグ」から**実行時に自動解決**（IDのハードコード廃止）。
  → 新カテゴリの追加が「ソース1行 ＋ Notionでタグ作成」だけで済む。
- 運用ガイド（ソース/カテゴリの追加方法、任意サイトの扱い方 等）を README に追記。
### Removed
- ダイジェスト専用DB（NAME/DATE）前提の設計、および TAG ID のハードコード。

## [0.1.0] - 2026-07-20
### Added
- AWS/Claude の5ソースからの情報収集
  - AWS What's New / AWS News Blog（RSS）
  - Claude Code CHANGELOG（GitHub raw・最新版のみ）
  - Anthropic Newsroom / Claude Platform release notes（スクレイプ）
- 収集結果を Notion に「1実行=1ダイジェストページ」として登録（AWS/Claudeセクション＋リンク箇条書き）
- `state/seen.json` による重複防止
- `LOOKBACK_DAYS` / `MAX_PER_SOURCE` による流入量の調整
- `--dry-run` / `--seed` の実行モード
- GitHub Actions による毎朝（07:00 JST）の定期実行

[Unreleased]: https://github.com/argondev22/info-radar/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/argondev22/info-radar/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/argondev22/info-radar/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/argondev22/info-radar/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/argondev22/info-radar/releases/tag/v0.1.0
