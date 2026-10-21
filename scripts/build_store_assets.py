"""플레이 콘솔 그래픽 생성 — 피처 그래픽(1024×500)·플레이 아이콘(512×512)·스크린샷 9:16 맞춤.

플레이 콘솔은 피처 그래픽에 알파 채널이 있으면 거부하므로 RGB 로 저장하고, 스크린샷은 긴 변이 짧은 변의 2배를 넘으면
(요즘 폰 캡처 1080×2400) 거부하므로 1080×1920 캔버스에 비율을 유지해 넣고 남는 곳은 브랜드 배경색으로 채운다.
글자는 넣지 않는다(폰트 의존이 없고, 플레이도 글자 적은 그래픽을 권장). 잎 도형은 scripts/build_app_icons.py 와 같다.

App Store(iOS)는 기기 칸마다 크기가 정해져 있다: 아이폰 6.9형 칸은 1320×2868·아이패드 13형 칸은 2064×2752, 기기당 최대 10장.
아이폰 15 Pro Max 캡처(1290×2796)나 아이패드 12.9형 캡처(2048×2732)를 그대로 올리면 거부되므로 같은 방식으로 맞춘다.
갤러리를 거친 캡처는 EXIF 회전 태그로 눕혀 저장되기도 하므로 먼저 바로 세운다(ImageOps.exif_transpose).

실행: python scripts/build_store_assets.py [--screens 캡처폴더] [--ios-phone 캡처폴더] [--ios-pad 캡처폴더]
  → app/store/feature-graphic.png, app/store/play-icon-512.png,
     --screens   → app/store/screenshots/01.png, 02.png …      (플레이, 1080×1920)
     --ios-phone → app/store/ios/iphone/01.png …                (App Store 아이폰 6.9형, 1320×2868)
     --ios-pad   → app/store/ios/ipad/01.png …                  (App Store 아이패드, 2064×2752)
     캡처 폴더의 *.png/*.jpg/*.jpeg 를 파일 이름순으로 번호 매김 — 촬영 목록·순서는 docs/app-release.md 6절(iOS 는 docs/app-release-ios.md 7절).
테스트: python -m unittest tests.test_store_assets -v
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_app_icons as B  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "app/store"
FEATURE_SIZE = (1024, 500)
FEATURE_ICON = 360            # 피처 그래픽 가운데 잎 아이콘 한 변
SCREEN_SIZE = (1080, 1920)    # 플레이 휴대전화 스크린샷 9:16
IOS_PHONE_SIZE = (1320, 2868) # App Store 아이폰 6.9형(필수 칸; 작은 기기 칸은 애플이 자동 축소)
IOS_PAD_SIZE = (2064, 2752)   # App Store 아이패드 13형
SCREEN_EXTS = {".png", ".jpg", ".jpeg"}


def feature_graphic() -> Image.Image:
    """1024×500 RGB — 배경색 위에 같은 배경색의 정사각 아이콘을 가운데 붙여 이음새 없이 잎만 보인다."""
    im = Image.new("RGB", FEATURE_SIZE, B.BG)
    icon = B.draw_icon(FEATURE_ICON, rounded=False, opaque=True)
    im.paste(icon, ((FEATURE_SIZE[0] - FEATURE_ICON) // 2, (FEATURE_SIZE[1] - FEATURE_ICON) // 2))
    return im


def play_icon() -> Image.Image:
    """512×512 불투명 정사각(모서리는 플레이가 둥글림) — 32비트 PNG 규격에 맞춰 RGBA 로 돌려준다."""
    return B.draw_icon(512, rounded=False, opaque=True).convert("RGBA")


def fit_screenshot(im: Image.Image, size: tuple[int, int] = SCREEN_SIZE) -> Image.Image:
    """비율을 유지해 size 안에 맞추고(확대·축소 모두) 남는 곳은 배경색, 가운데 정렬. 항상 RGB. EXIF 회전 태그가 있으면 먼저 바로 세운다."""
    im = ImageOps.exif_transpose(im) or im
    W, H = size
    w, h = im.size
    k = min(W / w, H / h)
    nw, nh = max(1, round(w * k)), max(1, round(h * k))
    scaled = im.convert("RGB").resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGB", size, B.BG)
    out.paste(scaled, ((W - nw) // 2, (H - nh) // 2))
    return out


def build_screens(src_dir: Path, out_dir: Path, size: tuple[int, int]) -> list[Path]:
    """src_dir 의 캡처를 이름순으로 size 에 맞춰 out_dir/01.png, 02.png… 로 저장(out_dir 는 비우고 다시 만듦). 만든 파일 목록을 돌려준다."""
    shots = sorted(f for f in src_dir.iterdir() if f.is_file() and f.suffix.lower() in SCREEN_EXTS)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    written: list[Path] = []
    for i, f in enumerate(shots, 1):
        with Image.open(f) as im:
            q = out_dir / ("%02d.png" % i)
            fit_screenshot(im, size).save(q, optimize=True)
            written.append(q)
    return written


def build(out_dir: Path, screens_dir: Path | None = None) -> list[Path]:
    """그래픽 두 장을 out_dir 에, screens_dir 가 있으면 플레이용 캡처를 out_dir/screenshots/01.png… 로 맞춰 저장. 만든 파일 경로 목록을 돌려준다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, im in (("feature-graphic.png", feature_graphic()), ("play-icon-512.png", play_icon())):
        p = out_dir / name
        im.save(p, optimize=True)
        written.append(p)
    if screens_dir is not None:
        written += build_screens(screens_dir, out_dir / "screenshots", SCREEN_SIZE)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="플레이 콘솔·App Store 그래픽 생성 (app/store/)")
    ap.add_argument("--screens", type=Path, help="안드로이드 폰 캡처 폴더 — 1080×1920 으로 맞춰 screenshots/ 에 저장")
    ap.add_argument("--ios-phone", type=Path, help="아이폰 캡처 폴더 — 1284×2778 로 맞춰 ios/iphone/ 에 저장")
    ap.add_argument("--ios-pad", type=Path, help="아이패드 캡처 폴더 — 2064×2752 로 맞춰 ios/ipad/ 에 저장")
    args = ap.parse_args()
    for d in (args.screens, args.ios_phone, args.ios_pad):
        if d is not None and not d.is_dir():
            print("캡처 폴더가 없습니다: %s" % d, file=sys.stderr)
            return 1
    written = build(OUT_DIR, args.screens)
    if args.ios_phone is not None:
        written += build_screens(args.ios_phone, OUT_DIR / "ios/iphone", IOS_PHONE_SIZE)
    if args.ios_pad is not None:
        written += build_screens(args.ios_pad, OUT_DIR / "ios/ipad", IOS_PAD_SIZE)
    for p in written:
        print(p.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
