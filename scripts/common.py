"""공통 유틸: 경로, JSON 입출력, 로깅, 시간."""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KST = timezone(timedelta(hours=9))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("yeongyangje")


def now_iso() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def read_json(path: Path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        log.error("JSON 파싱 실패 %s: %s", path, e)
        return default


def write_json(path: Path, data, compact: bool = False, quiet: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    if quiet:
        return
    try:
        shown = path.relative_to(ROOT)
    except ValueError:
        shown = path
    log.info("저장: %s", shown)


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def load_ingredients() -> list[dict]:
    data = read_json(DATA_DIR / "ingredients.json", {"items": []})
    return data.get("items", [])
