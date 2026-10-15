# -*- coding: utf-8 -*-
"""저작권 등록 제출용 복제물 번들 생성.

docs/copyright-registration/out/<YYYYMMDD>/ 에 다음을 만든다.
  program-source.zip            직접 작성한 소스(생성 파일·제3자 자산·데이터 제외)
  program-source-listing.txt    소스 전체를 파일 머리말·줄 번호와 함께 이어 붙인 목록(인쇄본 대용)
  database-copy.zip             수동 데이터 JSON 원본 + CSV 내보내기
  database-summary.txt          데이터베이스 수량·항목 요약
  program-spec.txt / database-spec.txt / README-신청정보.txt   명세서·설명서·안내의 .txt 사본
  MANIFEST.txt                  포함 파일 목록·줄 수·생성 시각·커밋 해시
  SHA256SUMS.txt                모든 산출물의 체크섬

사용: python scripts/make_copyright_bundle.py [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "copyright-registration"

# 프로그램 복제물에 넣는 것 (글롭은 ROOT 기준)
SOURCE_GLOBS = [
    "*.html",
    "assets/js/*.js",
    "assets/js/pages/*.js",
    "assets/css/style.css",
    "assets/css/home.css",
    "assets/css/tailwind.src.css",
    "scripts/*.py",
    "scripts/*.mjs",
    ".github/workflows/*.yml",
    "tailwind.config.cjs",
    "package.json",
    "requirements.txt",
    "_headers",
    "robots.txt",
    "config/.env.example",
    "dev.bat",
    "dev.ps1",
    "CLAUDE.md",
    "README.md",
    "LICENSE",
]
# 생성 파일·제3자 자산·검색엔진 확인 파일은 제외
SOURCE_EXCLUDE_NAMES = {"guides.html", "icons.js", "tailwind.css", "make_copyright_bundle.py"}
SOURCE_EXCLUDE_PREFIXES = ("naver",)

# 데이터베이스 복제물
DATABASE_FILES = [
    "data/ingredients.json",
    "data/interactions.json",
    "data/guides.json",
    "data/drug-pairings.json",
    "data/brand-priority.json",
]
META_KEYS = {"_meta", "_comment"}


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def collect_sources() -> list[Path]:
    seen: dict[str, Path] = {}
    for pattern in SOURCE_GLOBS:
        for p in sorted(ROOT.glob(pattern)):
            if not p.is_file():
                continue
            if p.name in SOURCE_EXCLUDE_NAMES or p.name.startswith(SOURCE_EXCLUDE_PREFIXES):
                continue
            seen[rel(p)] = p
    return [seen[k] for k in sorted(seen)]


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_head() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "(git 정보 없음)"


def write_listing(sources: list[Path], dest: Path) -> int:
    total = 0
    with dest.open("w", encoding="utf-8-sig", newline="\n") as f:
        f.write("영양제.kr 웹사이트 프로그램 — 소스코드 목록\n")
        f.write(f"생성 시각 {dt.datetime.now().isoformat(timespec='seconds')}  커밋 {git_head()}\n")
        f.write(f"파일 {len(sources)}개. 각 파일은 '==== 경로 ====' 머리말 뒤에 줄 번호와 함께 이어진다.\n\n")
        for p in sources:
            lines = read_text(p).splitlines()
            total += len(lines)
            f.write(f"\n==== {rel(p)} ({len(lines)}줄) ====\n")
            for i, line in enumerate(lines, 1):
                f.write(f"{i:5d}  {line}\n")
    return total


def main_list(data: dict):
    """최상위에서 메타 키를 제외한 첫 list 값을 소재 목록으로 본다. (키, 목록) 또는 None."""
    for k, v in data.items():
        if k in META_KEYS:
            continue
        if isinstance(v, list):
            return k, v
    return None


def flatten(record) -> dict:
    """CSV 용으로 1단계 평탄화: 스칼라는 그대로, 문자열 목록은 ' | ', 그 외는 JSON."""
    if not isinstance(record, dict):
        return {"value": json.dumps(record, ensure_ascii=False)}
    row = {}
    for k, v in record.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            row[k] = "" if v is None else v
        elif isinstance(v, list) and all(isinstance(x, str) for x in v):
            row[k] = " | ".join(v)
        else:
            row[k] = json.dumps(v, ensure_ascii=False)
    return row


def to_csv(records: list) -> bytes:
    rows = [flatten(r) for r in records]
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def build_database(out: Path) -> str:
    summary = io.StringIO()
    summary.write("영양제.kr 데이터베이스 — 수량·항목 요약\n")
    summary.write(f"생성 시각 {dt.datetime.now().isoformat(timespec='seconds')}  커밋 {git_head()}\n\n")
    zpath = out / "database-copy.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for relpath in DATABASE_FILES:
            p = ROOT / relpath
            if not p.exists():
                summary.write(f"[없음] {relpath}\n")
                continue
            raw = p.read_bytes()
            z.writestr(relpath, raw)
            data = json.loads(raw.decode("utf-8"))
            summary.write(f"## {relpath}  ({len(raw):,} bytes, sha256 {sha256_bytes(raw)[:16]}...)\n")
            found = main_list(data) if isinstance(data, dict) else ("items", data)
            if found:
                key, items = found
                summary.write(f"- 소재 목록 '{key}': {len(items)}건\n")
                keys: dict[str, int] = {}
                for it in items:
                    if isinstance(it, dict):
                        for k in it:
                            keys[k] = keys.get(k, 0) + 1
                if keys:
                    summary.write("- 항목: " + ", ".join(f"{k}({n})" for k, n in keys.items()) + "\n")
                    sample = json.dumps(items[0], ensure_ascii=False)
                    summary.write("- 첫 소재 예시: " + (sample[:300] + ("..." if len(sample) > 300 else "")) + "\n")
                z.writestr(relpath.replace("data/", "csv/").replace(".json", ".csv"), to_csv(items))
            # dict 형 보조 소재(brand-priority 의 weights 등)
            if isinstance(data, dict):
                for k, v in data.items():
                    if k in META_KEYS or (found and k == found[0]):
                        continue
                    if isinstance(v, (dict, list)):
                        summary.write(f"- 보조 소재 '{k}': {len(v)}건\n")
                meta = data.get("_meta")
                if isinstance(meta, dict):
                    for mk in ("description", "updatedAt"):
                        if mk in meta:
                            summary.write(f"- _meta.{mk}: {meta[mk]}\n")
            summary.write("\n")
    (out / "database-summary.txt").write_text(summary.getvalue(), encoding="utf-8-sig")
    return summary.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="출력 디렉터리 (기본: docs/copyright-registration/out/<YYYYMMDD>)")
    args = ap.parse_args()
    today = dt.date.today().strftime("%Y%m%d")
    out = Path(args.out) if args.out else DOCS / "out" / today
    out.mkdir(parents=True, exist_ok=True)

    sources = collect_sources()
    if not sources:
        print("소스 파일을 찾지 못했습니다.", file=sys.stderr)
        return 1

    # 1) 소스 zip
    with zipfile.ZipFile(out / "program-source.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sources:
            z.write(p, rel(p))
    # 2) 소스 목록
    total_lines = write_listing(sources, out / "program-source-listing.txt")
    # 3) 데이터베이스
    db_summary = build_database(out)
    # 4) 문서 .txt 사본
    for src, name in [("program-spec.md", "program-spec.txt"),
                      ("database-spec.md", "database-spec.txt"),
                      ("README.md", "README-신청정보.txt")]:
        p = DOCS / src
        if p.exists():
            (out / name).write_text(read_text(p), encoding="utf-8-sig")
    # 5) MANIFEST
    by_ext: dict[str, list[int]] = {}
    for p in sources:
        n = len(read_text(p).splitlines())
        key = p.suffix or p.name
        by_ext.setdefault(key, [0, 0])
        by_ext[key][0] += 1
        by_ext[key][1] += n
    man = io.StringIO()
    man.write("영양제.kr 저작권 등록 번들 MANIFEST\n")
    man.write(f"생성 시각 {dt.datetime.now().isoformat(timespec='seconds')}  커밋 {git_head()}\n")
    man.write(f"소스 파일 {len(sources)}개, 총 {total_lines:,}줄\n")
    for ext, (cnt, n) in sorted(by_ext.items()):
        man.write(f"  {ext:14s} {cnt:3d}개 {n:7,}줄\n")
    man.write("\n포함 소스:\n")
    for p in sources:
        man.write(f"  {rel(p)}\n")
    man.write("\n제외: i/, guide/, guides.html, sitemap.xml, data/meta.json(생성 파일) · "
              "assets/css/tailwind.css, assets/js/icons.js(생성·제3자) · assets/images, assets/fonts(제3자·사진) · "
              "data/(데이터베이스 번들로 분리) · naver*.html(검색엔진 확인 파일)\n")
    man.write("\n" + db_summary)
    (out / "MANIFEST.txt").write_text(man.getvalue(), encoding="utf-8-sig")
    # 6) 체크섬
    sums = []
    for p in sorted(out.iterdir()):
        if p.name == "SHA256SUMS.txt" or not p.is_file():
            continue
        sums.append(f"{sha256_bytes(p.read_bytes())}  {p.name}")
    (out / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")

    print(f"번들 생성: {out}")
    for line in sums:
        print("  " + line.split("  ", 1)[1])
    print(f"소스 {len(sources)}개 파일 {total_lines:,}줄")
    return 0


if __name__ == "__main__":
    sys.exit(main())
