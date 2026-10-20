"""앱 아이콘 PNG 세트 생성 — assets/images/favicon.svg 의 잎 도형을 Pillow 로 그려 PWA·스토어용 아이콘을 만든다.

  python scripts/build_app_icons.py      # assets/images/app/ 에 5개 PNG 생성 (결과는 커밋)

생성 파일: icon-192.png · icon-512.png(둥근 모서리, 투명 바깥) · icon-maskable-512.png(안전 영역용 80% 축소, 꽉 찬 배경)
          · apple-touch-icon.png(180, 꽉 찬 배경 — iOS 가 모서리를 깎음) · icon-1024.png(스토어 등록용)
도형은 favicon.svg 와 같은 64 단위 좌표를 쓰고, 4배 크기로 그린 뒤 LANCZOS 로 줄여 계단 현상을 없앤다. 외부 의존성은 Pillow 뿐."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets/images/app"

BG = (58, 125, 68)          # #3a7d44
LEAF = (255, 255, 255)      # #ffffff
VEIN = (156, 198, 164)      # #9cc6a4
UNIT = 64.0                 # favicon.svg viewBox
SUPER = 4                   # 슈퍼샘플 배율
# favicon.svg: M14 40 C 20 20, 40 12, 52 16 C 50 36, 34 50, 14 40 Z
LEAF_CURVES = [((14, 40), (20, 20), (40, 12), (52, 16)), ((52, 16), (50, 36), (34, 50), (14, 40))]
# favicon.svg: M18 38 C 28 30, 38 24, 48 20 (stroke-width 3, round cap)
VEIN_CURVE = ((18, 38), (28, 30), (38, 24), (48, 20))
VEIN_WIDTH = 3.0

FILES = [   # (파일명, 크기, rounded, scale, opaque)
    ("icon-192.png", 192, True, 1.0, False),
    ("icon-512.png", 512, True, 1.0, False),
    ("icon-maskable-512.png", 512, False, 0.8, True),
    ("apple-touch-icon.png", 180, False, 1.0, True),
    ("icon-1024.png", 1024, False, 1.0, True),
]


def bezier(p0, p1, p2, p3, n: int = 40) -> list[tuple[float, float]]:
    """3차 베지어 곡선을 n+1 개 점으로 샘플한다 (양 끝점 포함)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0]
        y = u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]
        pts.append((x, y))
    return pts


def draw_icon(size: int, *, rounded: bool, scale: float = 1.0, opaque: bool = False) -> Image.Image:
    """favicon.svg 와 같은 아이콘을 size 픽셀 정사각형으로 그린다.
    rounded: 모서리 반지름 size/4, 바깥은 투명. scale: 잎·잎맥을 중심 기준으로 축소(maskable 안전 영역용). opaque: RGB 로 반환."""
    big = size * SUPER
    k = big / UNIT                      # 64 단위 → 픽셀
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if rounded:
        d.rounded_rectangle((0, 0, big - 1, big - 1), radius=big / 4, fill=BG + (255,))
    else:
        d.rectangle((0, 0, big - 1, big - 1), fill=BG + (255,))

    def px(p):   # 64 단위 좌표 → 중심 기준 scale 적용 → 픽셀
        return ((p[0] - UNIT / 2) * scale + UNIT / 2) * k, ((p[1] - UNIT / 2) * scale + UNIT / 2) * k

    outline = [px(p) for curve in LEAF_CURVES for p in bezier(*curve)]
    d.polygon(outline, fill=LEAF + (255,))
    vein = [px(p) for p in bezier(*VEIN_CURVE)]
    w = max(1, round(VEIN_WIDTH * scale * k))
    d.line(vein, fill=VEIN + (255,), width=w, joint="curve")
    r = w / 2
    for x, y in (vein[0], vein[-1]):    # 둥근 끝
        d.ellipse((x - r, y - r, x + r, y + r), fill=VEIN + (255,))

    out = im.resize((size, size), Image.LANCZOS)
    if opaque:
        rgb = Image.new("RGB", (size, size), BG)
        rgb.paste(out, mask=out.split()[3])
        return rgb
    return out


def build(out_dir: Path) -> list[Path]:
    """5개 아이콘 파일을 out_dir 에 쓰고 경로 목록을 돌려준다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, size, rounded, scale, opaque in FILES:
        p = out_dir / name
        draw_icon(size, rounded=rounded, scale=scale, opaque=opaque).save(p, optimize=True)
        paths.append(p)
    return paths


def main() -> int:
    for p in build(OUT_DIR):
        print(f"{p.relative_to(ROOT).as_posix()}  {p.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
