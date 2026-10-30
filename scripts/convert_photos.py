"""성분 실사 사진 변환 — 원본 PNG(파일명 = 성분 id, 또는 _default) → assets/images/ingredients/<id>.webp 3종(품질 80).

사용: python scripts/convert_photos.py <원본 폴더> [--ids omega-3,zinc] [--out 폴더] [--quality 80]
- 한 원본에서 `<id>.webp`(640, 가이드 카드·성분 상세 상단), `<id>-m.webp`(360, 성분 사전 목록 띠), `<id>-s.webp`(160, 검색·셀프체크·작은 카드 썸네일)
  세 장을 만든다(SIZES). 빌드 prepare_photos 는 셋이 다 있어야 그 성분 사진을 쓰고, 하나라도 없으면 기본 사진 + 경고.
- 폴더의 *.png 가운데 이름이 data/ingredients.json 의 성분 id 이거나 `_default` 인 것만 변환하고, 모르는 이름은 건너뛰며 경고한다.
- 정사각형이 아니면 중앙을 정사각형으로 자른 뒤 LANCZOS 로 줄인다. Pillow 는 이 스크립트만 쓴다(빌드 build_site.py 는 파일 유무만 본다).
- 원본은 저장소 밖에 보관하고(장당 2MB), 변환본만 커밋한다. 변환 뒤 python scripts/build_site.py 로 페이지를 다시 만든다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "assets" / "images" / "ingredients"
SIZES = (("", 640), ("-m", 360), ("-s", 160))   # (파일명 접미사, 한 변 px) — build_site.py PHOTO_SIZES 와 같아야 한다


def known_ids(root: Path = ROOT) -> set[str]:
    data = json.loads((root / "data" / "ingredients.json").read_text(encoding="utf-8"))
    items = data["items"] if isinstance(data, dict) else data
    return {it["id"] for it in items} | {"_default"}


def convert_one(src: Path, dst: Path, size: int = 640, quality: int = 80) -> tuple[int, int]:
    """src 를 정사각형 size×size WebP 로 저장하고 원본 크기(w, h)를 돌려준다."""
    from PIL import Image
    im = Image.open(src).convert("RGB")
    w, h = im.size
    s = min(w, h)
    left, top = (w - s) // 2, (h - s) // 2
    im = im.crop((left, top, left + s, top + s)).resize((size, size), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "WEBP", quality=quality, method=6)
    return w, h


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="성분 실사 사진 PNG → 640 WebP")
    ap.add_argument("raw_dir", help="원본 PNG 폴더 (파일명 = 성분 id)")
    ap.add_argument("--ids", default="", help="쉼표로 구분한 id 만 변환 (기본: 폴더 전체)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="저장 폴더 (기본: assets/images/ingredients)")
    ap.add_argument("--quality", type=int, default=80)
    args = ap.parse_args(argv)
    raw, out = Path(args.raw_dir), Path(args.out)
    if not raw.is_dir():
        print(f"원본 폴더가 없습니다: {raw}", file=sys.stderr)
        return 2
    ids = known_ids()
    only = {x.strip() for x in args.ids.split(",") if x.strip()}
    done, skipped = [], []
    for src in sorted(raw.glob("*.png")):
        name = src.stem
        if only and name not in only:
            continue
        if name not in ids:
            skipped.append(name)
            continue
        kbs = []
        for suffix, size in SIZES:
            w, h = convert_one(src, out / f"{name}{suffix}.webp", size, args.quality)
            kbs.append((out / f"{name}{suffix}.webp").stat().st_size // 1024)
        done.append((name, w, h, kbs))
    for name, w, h, kbs in done:
        print(f"{name:24s} {w}x{h} → " + " · ".join(f"{size}px {kb}KB" for (_, size), kb in zip(SIZES, kbs)))
    if skipped:
        print(f"건너뜀(성분 id 아님): {', '.join(skipped)}", file=sys.stderr)
    print(f"변환 {len(done)}장 × {len(SIZES)}종 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
