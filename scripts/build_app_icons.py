"""앱 아이콘 PNG 세트 생성 — assets/images/favicon.svg 의 잎 도형을 Pillow 로 그려 PWA·스토어·안드로이드용 아이콘을 만든다.

  python scripts/build_app_icons.py      # assets/images/app/ 에 PWA 아이콘 5종 + app/assets/ 에 Capacitor 원본 + 안드로이드 상태바 아이콘 (결과는 커밋)

PWA(assets/images/app/): icon-192.png · icon-512.png(둥근 모서리, 투명 바깥) · icon-maskable-512.png(안전 영역용 80% 축소, 꽉 찬 배경)
          · apple-touch-icon.png(180, 꽉 찬 배경 — iOS 가 모서리를 깎음) · icon-1024.png(스토어 등록용)
Capacitor(app/assets/, `@capacitor/assets` 가 읽음): icon-only.png(1024) · icon-foreground.png(1024, 투명 배경에 잎만 66%) · icon-background.png(1024, 단색) · splash.png(2732)
안드로이드 알림 상태바 아이콘(app/android/app/src/main/res/drawable-{dpi}/ic_stat_leaf.png): 흰 잎 실루엣, 24dp(mdpi 24 ~ xxxhdpi 96)
도형은 favicon.svg 와 같은 64 단위 좌표를 쓰고, 4배 크기로 그린 뒤 LANCZOS 로 줄여 계단 현상을 없앤다. 외부 의존성은 Pillow 뿐."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets/images/app"
APP_ASSETS = ROOT / "app/assets"
ANDROID_RES = ROOT / "app/android/app/src/main/res"

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
STAT_DPI = [("mdpi", 24), ("hdpi", 36), ("xhdpi", 48), ("xxhdpi", 72), ("xxxhdpi", 96)]


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


def _render(size: int, *, background, rounded: bool, scale: float, leaf, vein, opaque: bool) -> Image.Image:
    """공통 렌더. background 가 None 이면 투명 배경, vein 이 None 이면 잎맥 생략(실루엣)."""
    big = size * SUPER
    k = big / UNIT                      # 64 단위 → 픽셀
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if background is not None:
        if rounded:
            d.rounded_rectangle((0, 0, big - 1, big - 1), radius=big / 4, fill=background + (255,))
        else:
            d.rectangle((0, 0, big - 1, big - 1), fill=background + (255,))

    def px(p):   # 64 단위 좌표 → 중심 기준 scale 적용 → 픽셀
        return ((p[0] - UNIT / 2) * scale + UNIT / 2) * k, ((p[1] - UNIT / 2) * scale + UNIT / 2) * k

    outline = [px(p) for curve in LEAF_CURVES for p in bezier(*curve)]
    d.polygon(outline, fill=leaf + (255,))
    if vein is not None:
        pts = [px(p) for p in bezier(*VEIN_CURVE)]
        w = max(1, round(VEIN_WIDTH * scale * k))
        d.line(pts, fill=vein + (255,), width=w, joint="curve")
        r = w / 2
        for x, y in (pts[0], pts[-1]):    # 둥근 끝
            d.ellipse((x - r, y - r, x + r, y + r), fill=vein + (255,))

    out = im.resize((size, size), Image.LANCZOS)
    if opaque:
        rgb = Image.new("RGB", (size, size), background or BG)
        rgb.paste(out, mask=out.split()[3])
        return rgb
    return out


def draw_icon(size: int, *, rounded: bool, scale: float = 1.0, opaque: bool = False) -> Image.Image:
    """favicon.svg 와 같은 아이콘을 size 픽셀 정사각형으로 그린다.
    rounded: 모서리 반지름 size/4, 바깥은 투명. scale: 잎·잎맥을 중심 기준으로 축소(maskable 안전 영역용). opaque: RGB 로 반환."""
    return _render(size, background=BG, rounded=rounded, scale=scale, leaf=LEAF, vein=VEIN, opaque=opaque)


def build(out_dir: Path) -> list[Path]:
    """PWA 아이콘 5개 파일을 out_dir 에 쓰고 경로 목록을 돌려준다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, size, rounded, scale, opaque in FILES:
        p = out_dir / name
        draw_icon(size, rounded=rounded, scale=scale, opaque=opaque).save(p, optimize=True)
        paths.append(p)
    return paths


def build_app_sources(out_dir: Path) -> list[Path]:
    """Capacitor 용 원본(icon-only·icon-foreground·icon-background·splash)과 상태바 아이콘(ic_stat_leaf-{dpi}.png)을 out_dir 에 쓴다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    def save(name: str, im: Image.Image) -> None:
        p = out_dir / name
        im.save(p, optimize=True)
        paths.append(p)

    save("icon-only.png", draw_icon(1024, rounded=False, opaque=True))
    save("icon-foreground.png", _render(1024, background=None, rounded=False, scale=0.66, leaf=LEAF, vein=VEIN, opaque=False))   # 적응형 아이콘 전경: 안전 영역 안에 잎만
    save("icon-background.png", Image.new("RGB", (1024, 1024), BG))
    # 스플래시: 2732 단색 배경 중앙에 흰 잎(폭 약 600px). 잎의 64 단위 폭 38 → 2732 * 38/64 * scale ≈ 600 → scale 0.37
    save("splash.png", _render(2732, background=BG, rounded=False, scale=0.37, leaf=LEAF, vein=VEIN, opaque=True))
    for dpi, size in STAT_DPI:   # 알림 상태바 아이콘: 흰 실루엣 + 투명 배경 (안드로이드가 알파만 쓴다)
        save(f"ic_stat_leaf-{dpi}.png", _render(size, background=None, rounded=False, scale=1.0, leaf=LEAF, vein=None, opaque=False))
    return paths


def main() -> int:
    for p in build(OUT_DIR):
        print(f"{p.relative_to(ROOT).as_posix()}  {p.stat().st_size:,} bytes")
    for p in build_app_sources(APP_ASSETS):
        if p.name.startswith("ic_stat_leaf-"):
            dpi = p.stem.split("-", 1)[1]
            if ANDROID_RES.exists():   # android 프로젝트가 생성된 뒤에만 (npx cap add android)
                dst = ANDROID_RES / f"drawable-{dpi}" / "ic_stat_leaf.png"
                dst.parent.mkdir(parents=True, exist_ok=True)
                p.replace(dst)
                print(f"{dst.relative_to(ROOT).as_posix()}")
            continue
        print(f"{p.relative_to(ROOT).as_posix()}  {p.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
