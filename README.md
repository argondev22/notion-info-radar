# info-radar

AWS と Claude の最新情報を自動収集して Notion データベースに登録する仕組み。
GitHub Actions で毎朝定期実行する（v1 は AI 処理なし・RSS/スクレイプのみ）。

## パイプライン

```
収集(RSS/スクレイプ) → 重複除去(state/seen.json) → Notionにダイジェスト1ページ作成
```

毎回の実行で「その日の新着」を AWS / Claude のセクションに分けた 1 ページにまとめ、
「ダイジェスト」データベースに 1 行として追加する。

## ソース（5本）

| ソース | CATEGORY | 方式 |
| --- | --- | --- |
| AWS What's New | AWS | RSS |
| AWS News Blog | AWS | RSS |
| Claude Code CHANGELOG | Claude | GitHub raw |
| Anthropic Newsroom | Claude | スクレイプ |
| Claude Platform release notes | Claude | スクレイプ |

## Notion 側の準備

1. インテグレーションを作成 → トークン（`ntn_...`）を取得
2. 「ダイジェスト」データベースを作成し、次のプロパティを用意する
   - `NAME`（タイトル）… 例「情報ダイジェスト 2026-07-20（AWS 12 / Claude 3）」
   - `DATE`（**日付型**）… 一覧をソートするための日付
   - 各記事はページ本文に AWS / Claude のセクション＋箇条書きリンクで入る
3. DB の「…」→「コネクト」から作成したインテグレーションを接続
4. DB の URL から DATABASE_ID（32桁）を控える

## ローカル実行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # NOTION_TOKEN と NOTION_DATABASE_ID を記入

python -m src.main --dry-run   # 登録候補を表示（書き込みなし・トークン不要）
python -m src.main --seed      # 既存記事を「取り込み済み」に（初回の氾濫防止）
python -m src.main             # 本番登録
```

## GitHub Actions

- スケジュール：毎朝 07:00 JST（`.github/workflows/collect.yml` の cron は UTC）
- リポジトリの Secrets に `NOTION_TOKEN` と `NOTION_DATABASE_ID` を登録
- 実行後 `state/seen.json` を自動 commit（重複防止＋スケジュール自動停止の回避）

## 調整ポイント

- `.env` の `LOOKBACK_DAYS` / `MAX_PER_SOURCE` で流入量を調整
- ソースの増減は `src/sources.py`
- 将来 Claude で「関心スコア／要約」を足す場合は収集と登録の間に処理を挟む
