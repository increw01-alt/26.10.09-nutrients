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
            out = Image.open(Path(d) / "omega-3.webp")
            self.assertEqual((w, h), (1254, 1000))
            self.assertEqual(out.size, (640, 640))
            self.assertEqual(out.format, "WEBP")

    def test_main_skips_unknown_ids(self):
        import convert_photos as C
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d) / "raw"; raw.mkdir(); out = Path(d) / "out"
            for name in ("omega-3", "nope", "_default"):
                Image.new("RGB", (64, 64)).save(raw / f"{name}.png")
            self.assertEqual(C.main([str(raw), "--out", str(out)]), 0)
            self.assertEqual(sorted(p.name for p in out.glob("*.webp")), ["_default.webp", "omega-3.webp"])


if __name__ == "__main__":
    unittest.main()
