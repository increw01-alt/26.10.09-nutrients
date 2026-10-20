"""스토어 그래픽 생성 스크립트(scripts/build_store_assets.py) 테스트. 실행: python -m unittest tests.test_store_assets -v"""
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_app_icons as B  # noqa: E402
import build_store_assets as S  # noqa: E402


class StoreAssetTests(unittest.TestCase):
    def test_feature_graphic_is_opaque_rgb(self):
        im = S.feature_graphic()
        self.assertEqual((im.size, im.mode), ((1024, 500), "RGB"))
        self.assertEqual(im.getpixel((5, 5)), B.BG)
        self.assertEqual(im.getpixel((512, 250)), (255, 255, 255))   # 가운데는 흰 잎

    def test_play_icon_is_full_square_opaque(self):
        im = S.play_icon()
        self.assertEqual(im.size, (512, 512))
        self.assertEqual(im.getpixel((2, 2))[:3], B.BG)
        self.assertEqual(im.getpixel((2, 2))[3], 255)

    def test_fit_screenshot_pads_tall_phone_to_9_16(self):
        out = S.fit_screenshot(Image.new("RGB", (1080, 2400), (255, 0, 0)))
        self.assertEqual((out.size, out.mode), ((1080, 1920), "RGB"))
        self.assertEqual(out.getpixel((0, 0)), B.BG)          # 좌우 여백
        self.assertEqual(out.getpixel((540, 960)), (255, 0, 0))

    def test_fit_screenshot_scales_exact_ratio_without_padding(self):
        out = S.fit_screenshot(Image.new("RGBA", (720, 1280), (0, 0, 255, 255)))
        self.assertEqual((out.size, out.mode), ((1080, 1920), "RGB"))
        self.assertEqual(out.getpixel((0, 0)), (0, 0, 255))

    def test_build_writes_graphics_and_numbered_screenshots(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            Image.new("RGB", (1080, 2400)).save(src / "b.png")
            Image.new("RGB", (1080, 2400)).save(src / "a.jpg")
            files = sorted(p.relative_to(d).as_posix() for p in S.build(Path(d), src))
            self.assertEqual(files, ["feature-graphic.png", "play-icon-512.png", "screenshots/01.png", "screenshots/02.png"])
            self.assertEqual(Image.open(Path(d) / "screenshots/01.png").size, (1080, 1920))
