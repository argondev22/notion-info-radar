# info-radar

AWS と Claude の最新情報を自動収集し、Notion に **カテゴリ別・日次ダイジェスト**として登録する仕組み。
GitHub Actions で毎朝定期実行する（v1 は AI 処理なし・RSS / スクレイプのみ）。

## 仕組み

```
収集(RSS/スクレイプ) → 重複除去(state/seen.json) → Notionにカテゴリ別ダイジェスト作成
```

毎回の実行で、**新着があるカテゴリごとに1ページ**を作る（例：AWSで1枚、Claudeで1枚 → 1日2ページ）。

- 登録先：Notion データベース `DB_APPLICATION_PAGES`
- 各ページ：**タイトル = 日付**（JST）、**TAG = カテゴリ**（AWS/Claude…）、**NOTE = 「ニュース」ノート**、本文 = その日その分野の記事のリンク箇条書き
- TAG は「ニュースノート配下で名前がカテゴリ名と一致するタグ」を**実行時に自動解決**（IDのハードコード不要）

## ソース（現在5本）

| ソース | カテゴリ | 取得方式(kind) |
| --- | --- | --- |
| AWS What's New | AWS | `rss` |
| AWS News Blog | AWS | `rss` |
| Claude Code CHANGELOG | Claude | `github_changelog`（最新版のみ） |
| Anthropic Newsroom | Claude | `scrape_anthropic_news` |
| Claude Platform release notes | Claude | `scrape_claude_relnotes` |

---

# 運用ガイド

## ソースを追加したい

### そもそも「何をソースにできる？」

| 追加したいもの | 追加のしやすさ | 方法 |
| --- | --- | --- |
| **RSS / Atom フィードがあるページ** | ◎ 1行 | `sources.py` に `kind="rss"` で追加するだけ |
| **GitHub 上のファイル**（CHANGELOG 等） | ○ | `kind="github_changelog"` を使う／類似関数を書く |
| **RSS が無い任意の Web ページ** | △ コード必要 | そのページ専用の**スクレイパー関数**を `collect.py` に書く（下記） |

> **要点**：RSS/Atom があるページは1行で追加できる。RSS が無い任意のサイトも**ソースにできるが**、
> HTML はサイトごとに構造が違うため「そのページ専用の抽出コード（スクレイパー）」が必要。
> 実装済みの `Anthropic Newsroom` / `Claude Platform release notes` の2つがスクレイパーの雛形になる。

### RSSソースを足す（1行）

`src/sources.py` の `SOURCES` に1行足すだけ：

```python
Source(
    key="aws_security_blog",          # 一意なキー（任意）
    name="AWS Security Blog",         # ログ表示名
    category="AWS",                   # カテゴリ（= TAG名）
    kind="rss",
    url="https://aws.amazon.com/blogs/security/feed/",
),
```

### RSSが無いページをスクレイプで足す

1. `src/collect.py` に取得関数を追加（`_collect_anthropic_news` を雛形に）：
   ```python
   def _collect_my_site(src: Source) -> list[Item]:
       soup = BeautifulSoup(_get(src.url).text, "html.parser")
       items = []
       for card in soup.select("……"):        # そのサイト固有のセレクタ
           items.append(Item(title=..., url=..., summary=..., published=...,
                             category=src.category, source_name=src.name))
       return items
   ```
2. `collect_source()` の分岐に `kind` を1つ追加：
   ```python
   if src.kind == "scrape_my_site":
       return _collect_my_site(src)
   ```
3. `sources.py` に `kind="scrape_my_site"` でソースを追加。

## カテゴリを追加したい（例：株式）

**コードは実質1行 ＋ Notion でタグ作成だけ**（ID を調べる必要なし）：

1. `src/sources.py` にそのカテゴリのソースを追加：
   ```python
   Source("kabu_reuters", "ロイター株式", "株式", "rss", "https://.../feed"),
   ```
2. Notion で「ニュース」ノートの配下に **`株式` という名前のタグ**を作る（`DB_APPLICATION_TAGS`）。

これで完了。`config.py` も `main.py` も触らなくてよい：

- 表示対象カテゴリは `SOURCES` から自動導出（`CATEGORY_ORDER`）
- TAG は「ニュース配下で名前が `株式` のタグ」を実行時に自動解決

> タグをまだ作っていない場合でもページ自体は作られる（TAG 未設定のまま）。ログで警告が出るので、
> その時にタグを作れば次回から自動で付く。

## 流入量の調整

`.env` で調整（GitHub Actions では env / secrets で指定）：

| 変数 | 意味 | 既定 |
| --- | --- | --- |
| `LOOKBACK_DAYS` | 何日前までの記事を対象にするか（日付ありソース） | `2` |
| `MAX_PER_SOURCE` | 1ソースあたりの最大取得件数 | `30` |

## ローカルでの実行

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # NOTION_TOKEN / NOTION_DATABASE_ID を記入

python -m src.main --dry-run        # 書き込まず、各ページに入る内容を表示
python -m src.main --seed           # 現在の記事を全て「取り込み済み」に（初回の氾濫防止）
python -m src.main --limit 5        # 動作確認用に候補を5件に絞る
python -m src.main                  # 本番（ダイジェストページ作成）
```

## スケジュール（実行タイミング）を変える

`.github/workflows/collect.yml` の cron を編集（**UTC** 表記）：

```yaml
on:
  schedule:
    - cron: "0 22 * * *"   # 07:00 JST（= 前日22:00 UTC）
```

## 重複防止の仕組み

- 取り込み済みの記事URLを `state/seen.json` に記録
- GitHub Actions は実行後に `state/seen.json` を**自動 commit**（重複防止＋スケジュール自動停止の回避を兼ねる）
- 同じ記事は二度登録されない。同日に2回走っても、新着が無ければページは作られない

---

# セットアップ

## Notion 側

- 登録先 DB：`DB_APPLICATION_PAGES`（`NAME`=title, `URL`=url, `SUMMARY`=text, `NOTE`=relation, `TAG`=relation）
- インテグレーションを作成し、**登録先DB・タグDB・ノートDB にアクセス権**を付与（コネクト）
- `NOTE` の紐付け先「ニュース」ノートの page_id は `src/config.py` の `NOTE_NEWS_ID`（別ノートにしたい場合は環境変数 `NOTE_NEWS_ID` で上書き可）

## GitHub Actions

リポジトリの Secrets に登録：

| Secret | 内容 |
| --- | --- |
| `NOTION_TOKEN` | インテグレーションのトークン（`ntn_...`） |
| `NOTION_DATABASE_ID` | `DB_APPLICATION_PAGES` のデータベースID（32桁） |

## リリース

セマンティックバージョニング（`vX.Y.Z`）で管理。変更は `CHANGELOG.md` に記録。

```bash
# 1. CHANGELOG.md の [Unreleased] に変更を書き、版番号セクションへ移す
# 2. main に反映
git add -A && git commit -m "chore: release vX.Y.Z" && git push
# 3. タグを打って push すると、release ワークフローが GitHub Release を自動作成
git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z
```

---

# トラブルシューティング

| 症状 | 原因 / 対処 |
| --- | --- |
| `object_not_found` | DBがインテグレーションに接続されていない → Notionで DB の「…」→「コネクト」 |
| `unauthorized` | `NOTION_TOKEN` が不正 |
| TAG が付かない（ログに警告） | 「ニュース」ノート配下にそのカテゴリ名のタグが無い → タグを作成 |
| 候補が少ない/0 | 直近に新着が無い、または `LOOKBACK_DAYS` が短い。`--dry-run` で確認 |
| ページが作られない | 全記事が `state/seen.json` に登録済み（＝重複防止が正常動作） |

## 構成ファイル

```
src/
├─ sources.py     # ソース定義（＋カテゴリ順を自動導出）
├─ collect.py     # 収集（RSS取得・GitHub・スクレイプ）
├─ notion_sink.py # Notion登録（タグ自動解決・ページ組み立て）
├─ main.py        # ①収集→②重複除去→③登録 のまとめ
├─ config.py      # 環境変数・定数
├─ models.py      # Item データ構造
└─ state.py       # 取り込み済みURLの記録
```
