"""앱 아이콘 생성 스크립트(scripts/build_app_icons.py) 테스트. 실행: python -m unittest tests.test_app_icons -v"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_app_icons as B  # noqa: E402


class AppIconTests(unittest.TestCase):
    def test_build_writes_five_files_with_sizes(self):
        with tempfile.TemporaryDirectory() as d:
            files = {p.name: p for p in B.build(Path(d))}
            from PIL import Image
            self.assertEqual(set(files), {"icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png", "icon-1024.png"})
            self.assertEqual(Image.open(files["icon-192.png"]).size, (192, 192))
            self.assertEqual(Image.open(files["apple-touch-icon.png"]).size, (180, 180))
            self.assertEqual(Image.open(files["icon-1024.png"]).size, (1024, 1024))

    def test_rounded_icon_has_transparent_corner(self):
        im = B.draw_icon(512, rounded=True)
        self.assertEqual(im.mode, "RGBA")
        self.assertEqual(im.getpixel((2, 2))[3], 0)
        self.assertEqual(im.getpixel((256, 256))[:3], (255, 255, 255))   # 중앙은 흰 잎

    def test_maskable_keeps_safe_zone_background(self):
        im = B.draw_icon(512, rounded=False, scale=0.8, opaque=True)
        self.assertEqual(im.mode, "RGB")
        for xy in ((2, 2), (509, 509), (51, 51), (460, 51)):   # 모서리와 안전 영역 밖 10% 지점은 배경색
            self.assertEqual(im.getpixel(xy), (58, 125, 68))

    def test_app_sources_sizes_and_transparency(self):
        with tempfile.TemporaryDirectory() as d:
            files = {p.name: p for p in B.build_app_sources(Path(d))}
            from PIL import Image
            self.assertEqual(Image.open(files["icon-foreground.png"]).size, (1024, 1024))
            self.assertEqual(Image.open(files["icon-foreground.png"]).getpixel((2, 2))[3], 0)      # 투명 배경
            self.assertEqual(Image.open(files["icon-background.png"]).getpixel((10, 10))[:3], (58, 125, 68))
            self.assertEqual(Image.open(files["splash.png"]).size, (2732, 2732))
            self.assertEqual(Image.open(files["ic_stat_leaf-xxxhdpi.png"]).size, (96, 96))
            self.assertEqual(Image.open(files["ic_stat_leaf-xxxhdpi.png"]).getpixel((48, 40))[:3], (255, 255, 255))   # 잎 중앙은 흰색

    def test_apple_touch_icon_is_opaque_square(self):
        im = B.draw_icon(180, rounded=False, opaque=True)
        self.assertEqual(im.mode, "RGB")
        self.assertEqual(im.getpixel((1, 1)), (58, 125, 68))


if __name__ == "__main__":
    unittest.main()
