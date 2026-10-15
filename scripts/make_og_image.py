#!/usr/bin/env python3
"""소셜 공유 썸네일(assets/images/og-default.png, 1200x630) 생성.

예전 SVG 썸네일 디자인(크림→민트 그라데이션, 잎 마크, 헤드라인)을 PNG 로 렌더링한다. 카카오톡·페이스북 등 대부분의
미리보기 크롤러가 SVG 를 지원하지 않아 PNG 가 필요하다. 2배 크기로 그린 뒤 축소해 글자·곡선을 매끈하게 만든다.

사용: python scripts/make_og_image.py            # Pillow 필요 (pip install Pillow), Pretendard 폰트(Windows 폰트 폴더 또는 --font-dir)
      python scripts/make_og_image.py --font-dir /path/to/fonts --headline "영양제로 건강한 변화를" "시작하세요."
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    sys.exit("Pillow 가 필요합니다: pip install Pillow")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "images" / "og-default.png"
S = 2                                   # 슈퍼샘플링 배율
W, H = 1200 * S, 630 * S
FONT_DIRS = [Path("C:/Windows/Fonts"), Path.home() / "AppData/Local/Microsoft/Windows/Fonts", Path("/usr/share/fonts"), Path("/Library/Fonts"), Path.home() / "Library/Fonts"]


def hexc(h: str, a: int = 255) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def bezier(p0, p1, p2, p3, n: int = 40) -> list[tuple[float, float]]:
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
        pts.append((x, y))
    return pts


def sc(pts, ox: float = 0, oy: float = 0):
    return [((x + ox) * S, (y + oy) * S) for x, y in pts]


def find_font(name: str, extra: Path | None) -> Path:
    for d in ([extra] if extra else []) + FONT_DIRS:
        for ext in ("otf", "ttf"):
            p = d / f"{name}.{ext}"
            if p.exists():
                return p
    sys.exit(f"폰트를 찾지 못했습니다: {name} (Pretendard 를 설치하거나 --font-dir 로 폴더를 지정하세요)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-dir", type=Path, help="Pretendard-ExtraBold/Medium 폰트 파일이 있는 폴더")
    ap.add_argument("--headline", nargs=2, default=["영양제로 건강한 변화를", "시작하세요."], metavar=("LINE1", "LINE2"))
    ap.add_argument("--sub", default="영양제 추천 성분 · 궁합 · 먹는 시간 · 식약처 제품 정보")
    ap.add_argument("--brand", default="영양제.kr")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    # 배경: 대각 그라데이션 #fbfaf6 → #e2efe4
    grad = Image.new("RGB", (2, 2))
    grad.putpixel((0, 0), hexc("#fbfaf6")[:3]); grad.putpixel((1, 0), hexc("#eff5ed")[:3])
    grad.putpixel((0, 1), hexc("#eff5ed")[:3]); grad.putpixel((1, 1), hexc("#e2efe4")[:3])
    img = grad.resize((W, H), Image.BILINEAR).convert("RGBA")

    # 장식 원 (반투명)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([(1040 - 220) * S, (110 - 220) * S, (1040 + 220) * S, (110 + 220) * S], fill=hexc("#c5dfc9", int(255 * .6)))
    d.ellipse([(120 - 180) * S, (560 - 180) * S, (120 + 180) * S, (560 + 180) * S], fill=hexc("#fbe9dc", int(255 * .8)))
    img = Image.alpha_composite(img, layer)

    # 잎 마크 (favicon 과 같은 곡선): M0 60 C 30 0, 110 -10, 140 40 C 105 80, 35 90, 0 60 Z  (translate 90,150)
    d = ImageDraw.Draw(img)
    leaf = bezier((0, 60), (30, 0), (110, -10), (140, 40)) + bezier((140, 40), (105, 80), (35, 90), (0, 60))
    d.polygon(sc(leaf, 90, 150), fill=hexc("#3a7d44"))
    d.line(sc(bezier((8, 56), (50, 30), (95, 20), (132, 38)), 90, 150), fill=(255, 255, 255, int(255 * .6)), width=4 * S, joint="curve")

    # 글자 (왼쪽 기준선 기준 좌표)
    xb = ImageFont.truetype(str(find_font("Pretendard-ExtraBold", args.font_dir)), 64 * S)
    hl = ImageFont.truetype(str(find_font("Pretendard-ExtraBold", args.font_dir)), 72 * S)
    md = ImageFont.truetype(str(find_font("Pretendard-Medium", args.font_dir)), 32 * S)
    d.text((260 * S, 215 * S), args.brand, font=xb, fill=hexc("#1f4027"), anchor="ls")
    d.text((90 * S, 360 * S), args.headline[0], font=hl, fill=hexc("#1c1b18"), anchor="ls")
    d.text((90 * S, 450 * S), args.headline[1], font=hl, fill=hexc("#1c1b18"), anchor="ls")
    d.text((90 * S, 540 * S), args.sub, font=md, fill=hexc("#3a7d44"), anchor="ls")

    out = img.resize((1200, 630), Image.LANCZOS).convert("RGB")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.save(args.out, "PNG", optimize=True)
    print(f"저장: {args.out} {out.size[0]}x{out.size[1]} {args.out.stat().st_size / 1024:.0f}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
