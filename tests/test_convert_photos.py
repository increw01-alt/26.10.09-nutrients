"""scripts/convert_photos.py — 원본 PNG(성분 id 이름) → assets/images/ingredients/<id>.webp(640×640, 정사각형 아니면 중앙 크롭)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    from PIL import Image
except ImportError:  # CI(requirements.txt) 에는 Pillow 가 없다 — 변환은 로컬에서만
    Image = None


@unittest.skipIf(Image is None, "Pillow 없음")
class ConvertPhotosTests(unittest.TestCase):
    def test_convert_one_makes_square_640_webp(self):
        import convert_photos as C
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "omega-3.png"
            Image.new("RGB", (1254, 1000), (200, 80, 40)).save(src)
            w, h = C.convert_one(src, Path(d) / "omega-3.webp")
            with Image.open(Path(d) / "omega-3.webp") as out:   # with: Windows 에서 열린 파일은 임시 폴더 정리를 막는다
                size, fmt = out.size, out.format
            self.assertEqual((w, h), (1254, 1000))
            self.assertEqual(size, (640, 640))
            self.assertEqual(fmt, "WEBP")

    def test_main_skips_unknown_ids(self):
        import convert_photos as C
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d) / "raw"; raw.mkdir(); out = Path(d) / "out"
            for name in ("omega-3", "nope", "_default"):
                Image.new("RGB", (64, 64)).save(raw / f"{name}.png")
            self.assertEqual(C.main([str(raw), "--out", str(out)]), 0)
            self.assertEqual(sorted(p.name for p in out.glob("*.webp")),
                             ["_default-m.webp", "_default-s.webp", "_default.webp", "omega-3-m.webp", "omega-3-s.webp", "omega-3.webp"])

    def test_main_writes_three_sizes(self):
        """한 원본에서 640(가이드·상세)·360 `-m`(목록 띠)·160 `-s`(썸네일) 세 장을 만든다."""
        import convert_photos as C
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d) / "raw"; raw.mkdir(); out = Path(d) / "out"
            Image.new("RGB", (1254, 1254), (10, 120, 60)).save(raw / "omega-3.png")
            self.assertEqual(C.main([str(raw), "--out", str(out)]), 0)
            self.assertEqual(C.SIZES, (("", 640), ("-m", 360), ("-s", 160)))
            for suffix, size in C.SIZES:
                with Image.open(out / f"omega-3{suffix}.webp") as im:
                    self.assertEqual((im.size, im.format), ((size, size), "WEBP"), suffix)


if __name__ == "__main__":
    unittest.main()
