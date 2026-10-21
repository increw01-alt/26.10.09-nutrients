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
        self.assertEqual(im.getpixel((480, 316)), (252, 247, 235))   # 가운데 아이콘의 아래 캡슐은 크림색

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

    def test_ios_phone_and_pad_screens_fit(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            Image.new("RGB", (1170, 2532), (255, 0, 0)).save(src / "a.png")     # 아이폰 6.1형 캡처
            Image.new("RGB", (2048, 2732), (0, 0, 255)).save(src / "b.png")     # 아이패드 12.9형 캡처
            phone = S.build_screens(src, Path(d) / "iphone", S.IOS_PHONE_SIZE)
            pad = S.build_screens(src, Path(d) / "ipad", S.IOS_PAD_SIZE)
            self.assertEqual([p.name for p in phone], ["01.png", "02.png"])
            self.assertEqual(Image.open(phone[0]).size, (1320, 2868))   # 아이폰 6.9형 규격
            self.assertEqual(Image.open(pad[1]).size, (2064, 2752))
            self.assertEqual(Image.open(phone[0]).getpixel((660, 1434)), (255, 0, 0))

    def test_build_keeps_android_output_names(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            Image.new("RGB", (1080, 2400)).save(src / "a.png")
            files = [p.relative_to(d).as_posix() for p in S.build(Path(d), src)]
            self.assertIn("screenshots/01.png", files)

    def test_fit_screenshot_applies_exif_orientation(self):
        # 갤러리를 거친 캡처는 EXIF 회전 태그로 눕혀 저장되기도 한다 — 바로 세운 뒤 맞춘다
        im = Image.new("RGB", (2400, 1080), (0, 255, 0))
        exif = Image.Exif()
        exif[274] = 6   # Orientation 6 = 시계 방향 90° 회전해서 봐야 함 → 1080×2400 세로
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rot.png"
            im.save(p, exif=exif)
            with Image.open(p) as src:
                out = S.fit_screenshot(src)
        self.assertEqual(out.size, (1080, 1920))
        self.assertEqual(out.getpixel((0, 0)), B.BG)            # 세로로 세워져 좌우 여백
        self.assertEqual(out.getpixel((540, 200)), (0, 255, 0))  # 회전을 무시하면 가로 그림이 가운데 띠로 들어가 이 자리는 여백이 됨
