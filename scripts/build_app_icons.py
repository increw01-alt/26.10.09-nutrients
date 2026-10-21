"""앱 아이콘 PNG 세트 생성 — assets/images/favicon.svg(캡슐과 잎, 1024 단위 좌표)의 도형을 읽어 Pillow 로 그려 PWA·스토어·안드로이드용 아이콘을 만든다.

  python scripts/build_app_icons.py      # assets/images/app/ 에 PWA 아이콘 5종 + app/assets/ 에 Capacitor 원본 + 안드로이드 상태바 아이콘 (결과는 커밋)

PWA(assets/images/app/): icon-192.png · icon-512.png(둥근 모서리, 투명 바깥) · icon-maskable-512.png(안전 영역용 77% 축소, 꽉 찬 배경)
          · apple-touch-icon.png(180, 꽉 찬 배경 — iOS 가 모서리를 깎음) · icon-1024.png(스토어 등록용)
Capacitor(app/assets/, `@capacitor/assets` 가 읽음): icon-only.png(1024) · icon-foreground.png(1024, 투명 배경에 도형만 66%) · icon-background.png(1024, 단색) · splash.png(2732)
안드로이드 알림 상태바 아이콘(app/android/app/src/main/res/drawable-{dpi}/ic_stat_leaf.png): 흰 실루엣, 24dp(mdpi 24 ~ xxxhdpi 96).
  파일 이름 ic_stat_leaf 는 capacitor.config.json 의 smallIcon 과 맞물려 있어 도형이 바뀌어도 유지한다.
도형·색은 favicon.svg 에서 읽는다(<rect fill> 배경색, <g transform="translate() scale()"> 안의 <path fill d> 들 — M/L/C/Z 절대 좌표만).
4배 크기로 그린 뒤 LANCZOS 로 줄여 계단 현상을 없앤다. 외부 의존성은 Pillow 뿐. 원본 패키지 설명은 assets/images/brand/README-source.md."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets/images/favicon.svg"
OUT_DIR = ROOT / "assets/images/app"
APP_ASSETS = ROOT / "app/assets"
ANDROID_RES = ROOT / "app/android/app/src/main/res"

SUPER = 4                   # 슈퍼샘플 배율
CORNER = 244 / 1024         # 둥근 모서리 반지름(한 변 대비) — favicon.svg 의 rx
WHITE = (255, 255, 255)
STAT_NAME = "ic_stat_leaf"

FILES = [   # (파일명, 크기, rounded, scale, opaque)
    ("icon-192.png", 192, True, 1.0, False),
    ("icon-512.png", 512, True, 1.0, False),
    ("icon-maskable-512.png", 512, False, 0.77, True),
    ("apple-touch-icon.png", 180, False, 1.0, True),
    ("icon-1024.png", 1024, False, 1.0, True),
]
STAT_DPI = [("mdpi", 24), ("hdpi", 36), ("xhdpi", 48), ("xxhdpi", 72), ("xxxhdpi", 96)]


def bezier(p0, p1, p2, p3, n: int = 24) -> list[tuple[float, float]]:
    """3차 베지어 곡선을 n+1 개 점으로 샘플한다 (양 끝점 포함)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0]
        y = u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]
        pts.append((x, y))
    return pts


def _hex(s: str) -> tuple[int, int, int]:
    return int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)


def flatten_path(d: str) -> list[list[tuple[float, float]]]:
    """SVG path 의 M/L/C/Z(절대 좌표, 명령 글자가 매번 있는 형식)를 폴리곤 목록으로 편다."""
    tokens = re.findall(r"[MLCZ]|-?\d*\.?\d+", d)
    polys: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    pos = (0.0, 0.0)
    i = 0
    while i < len(tokens):
        t = tokens[i]
        i += 1
        if t == "M":
            if cur:
                polys.append(cur)
            pos = (float(tokens[i]), float(tokens[i + 1]))
            i += 2
            cur = [pos]
        elif t == "L":
            pos = (float(tokens[i]), float(tokens[i + 1]))
            i += 2
            cur.append(pos)
        elif t == "C":
            p1 = (float(tokens[i]), float(tokens[i + 1]))
            p2 = (float(tokens[i + 2]), float(tokens[i + 3]))
            p3 = (float(tokens[i + 4]), float(tokens[i + 5]))
            i += 6
            cur.extend(bezier(pos, p1, p2, p3)[1:])
            pos = p3
        elif t == "Z":
            if cur:
                polys.append(cur)
            cur = []
    if cur:
        polys.append(cur)
    return polys


def parse_svg(path: Path):
    """(한 변 단위, 배경색, [(색, [폴리곤…]), …]) — 그룹 transform(translate·scale)을 좌표에 적용한다."""
    text = path.read_text(encoding="utf-8")
    unit = float(re.search(r'viewBox="0 0 ([\d.]+) [\d.]+"', text).group(1))
    bg = _hex(re.search(r'<rect[^>]*fill="(#[0-9A-Fa-f]{6})"', text).group(1))
    m = re.search(r'<g transform="translate\(([-\d.]+) ([-\d.]+)\) scale\(([-\d.]+)\)"', text)
    tx, ty, s = (float(m.group(1)), float(m.group(2)), float(m.group(3))) if m else (0.0, 0.0, 1.0)
    shapes = []
    for fill, d in re.findall(r'<path fill="(#[0-9A-Fa-f]{6})" d="([^"]+)"', text):
        shapes.append((_hex(fill), [[(x * s + tx, y * s + ty) for x, y in poly] for poly in flatten_path(d)]))
    return unit, bg, shapes


UNIT, BG, SHAPES = parse_svg(SVG)


def _render(size: int, *, background, rounded: bool, scale: float, opaque: bool, silhouette=None) -> Image.Image:
    """공통 렌더. background 가 None 이면 투명 배경, silhouette 이 있으면 모든 도형을 그 색(상태바용 흰 실루엣)으로."""
    big = size * SUPER
    k = big / UNIT                      # SVG 단위 → 픽셀
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if background is not None:
        if rounded:
            d.rounded_rectangle((0, 0, big - 1, big - 1), radius=big * CORNER, fill=background + (255,))
        else:
            d.rectangle((0, 0, big - 1, big - 1), fill=background + (255,))

    def px(p):   # SVG 좌표 → 중심 기준 scale 적용 → 픽셀
        return ((p[0] - UNIT / 2) * scale + UNIT / 2) * k, ((p[1] - UNIT / 2) * scale + UNIT / 2) * k

    for color, polys in SHAPES:
        for poly in polys:
            d.polygon([px(p) for p in poly], fill=(silhouette or color) + (255,))

    out = im.resize((size, size), Image.LANCZOS)
    if opaque:
        rgb = Image.new("RGB", (size, size), background or BG)
        rgb.paste(out, mask=out.split()[3])
        return rgb
    return out


def draw_icon(size: int, *, rounded: bool, scale: float = 1.0, opaque: bool = False) -> Image.Image:
    """favicon.svg 와 같은 아이콘을 size 픽셀 정사각형으로 그린다.
    rounded: 모서리를 둥글게(바깥 투명). scale: 도형을 중심 기준으로 축소(maskable 안전 영역용). opaque: RGB 로 반환."""
    return _render(size, background=BG, rounded=rounded, scale=scale, opaque=opaque)


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
    save("icon-foreground.png", _render(1024, background=None, rounded=False, scale=0.66, opaque=False))   # 적응형 아이콘 전경: 안전 영역 안에 도형만
    save("icon-background.png", Image.new("RGB", (1024, 1024), BG))
    save("splash.png", _render(2732, background=BG, rounded=False, scale=0.3, opaque=True))   # 스플래시: 단색 배경 중앙에 아이콘(폭 약 650px)
    for dpi, size in STAT_DPI:   # 알림 상태바 아이콘: 흰 실루엣 + 투명 배경 (안드로이드가 알파만 쓴다)
        save(f"{STAT_NAME}-{dpi}.png", _render(size, background=None, rounded=False, scale=1.0, opaque=False, silhouette=WHITE))
    return paths


def main() -> int:
    for p in build(OUT_DIR):
        print(f"{p.relative_to(ROOT).as_posix()}  {p.stat().st_size:,} bytes")
    for p in build_app_sources(APP_ASSETS):
        if p.name.startswith(STAT_NAME + "-"):
            dpi = p.stem.split("-", 1)[1]
            if ANDROID_RES.exists():   # android 프로젝트가 생성된 뒤에만 (npx cap add android)
                dst = ANDROID_RES / f"drawable-{dpi}" / f"{STAT_NAME}.png"
                dst.parent.mkdir(parents=True, exist_ok=True)
                p.replace(dst)
                print(f"{dst.relative_to(ROOT).as_posix()}")
            continue
        print(f"{p.relative_to(ROOT).as_posix()}  {p.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
