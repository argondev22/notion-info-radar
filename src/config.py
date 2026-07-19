"""環境変数の読み込みと定数。"""
import os

from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# 何日前までの記事を取り込むか（日付ありソースに適用）
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "2"))

# 1ソースあたりの最大取得件数（日付なしソースの氾濫防止）
MAX_PER_SOURCE = int(os.getenv("MAX_PER_SOURCE", "30"))

# Notion の title / rich_text は 1 ブロックあたり最大 2000 文字
NOTION_TEXT_LIMIT = 2000

USER_AGENT = "info-radar/0.1 (+https://github.com/argondev22)"
