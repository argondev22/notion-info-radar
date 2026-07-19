"""取り込み済みURLの記憶（重複防止）。state/seen.json に保存する。"""
import json
from pathlib import Path

SEEN_PATH = Path(__file__).resolve().parent.parent / "state" / "seen.json"

# 肥大化防止：直近この件数だけ保持
MAX_SEEN = 5000


def load_seen() -> list[str]:
    if SEEN_PATH.exists():
        try:
            data = json.loads(SEEN_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def save_seen(seen_list: list[str]) -> None:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    trimmed = seen_list[-MAX_SEEN:]
    SEEN_PATH.write_text(
        json.dumps(trimmed, ensure_ascii=False, indent=0) + "\n", encoding="utf-8"
    )
