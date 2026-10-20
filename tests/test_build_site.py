"""scripts/build_site.py 의 PWA 관련 순수 함수 테스트. 실행: python -m unittest tests.test_build_site -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site as B  # noqa: E402

HEAD = '<head>\n  <meta charset="UTF-8">\n  <link rel="icon" href="../assets/images/favicon.svg" type="image/svg+xml">\n  <link rel="stylesheet" href="../assets/css/style.css">\n</head>'


class PwaTagTests(unittest.TestCase):
    def test_ensure_pwa_tags_uses_root_prefix(self):
        out = B.ensure_pwa_tags(HEAD, "../")
        self.assertIn('<link rel="manifest" href="../manifest.webmanifest">', out)
        self.assertIn('href="../assets/images/app/apple-touch-icon.png"', out)
        self.assertLess(out.index('rel="icon"'), out.index(B.PWA_START))
        self.assertLess(out.index(B.PWA_END), out.index('rel="stylesheet"'))

    def test_ensure_pwa_tags_is_idempotent_and_updates(self):
        once = B.ensure_pwa_tags(HEAD, "../")
        self.assertEqual(B.ensure_pwa_tags(once, "../"), once)
        self.assertEqual(once.count(B.PWA_START), 1)
        stale = once.replace("#246d4b", "#000000")
        self.assertIn("#246d4b", B.ensure_pwa_tags(stale, "../"))

    def test_ensure_pwa_tags_without_icon_link_is_unchanged(self):
        self.assertEqual(B.ensure_pwa_tags("<head></head>", "./"), "<head></head>")


if __name__ == "__main__":
    unittest.main()
