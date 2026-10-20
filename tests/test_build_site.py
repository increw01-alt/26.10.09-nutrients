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


class ServiceWorkerBuildTests(unittest.TestCase):
    def test_precache_urls_are_absolute_and_hashed(self):
        urls = B.precache_urls()
        self.assertIn("/offline.html", urls)
        self.assertNotIn("/manifest.webmanifest", urls)   # 매니페스트 요청은 서비스워커가 건드리지 않으므로 미리 받지 않는다
        self.assertTrue(any(u.startswith("/assets/js/data.js?v=") and len(u.split("?v=")[1]) == 8 for u in urls))
        self.assertTrue(all(u.startswith("/") for u in urls))
        self.assertEqual(urls, sorted(urls))

    def test_sw_version_changes_when_precache_changes(self):
        t = "var x;"
        self.assertNotEqual(B.sw_version(t, ["/a?v=1"]), B.sw_version(t, ["/a?v=2"]))
        self.assertEqual(len(B.sw_version(t, ["/a"])), 8)

    def test_sw_version_changes_when_unhashed_precache_content_changes(self):
        # offline.html·아이콘처럼 URL 에 해시가 없는 파일은 내용 해시를 따로 섞어야 바뀐 내용이 배포된다
        t = "var x;"
        self.assertNotEqual(B.sw_version(t, ["/offline.html"], ["aaaaaaaa"]), B.sw_version(t, ["/offline.html"], ["bbbbbbbb"]))

    def test_precache_extra_digests_cover_every_unhashed_url(self):
        urls = B.precache_urls()
        unhashed = [u for u in urls if "?v=" not in u]
        self.assertEqual(len(B.precache_extra_digests()), len(unhashed))
        self.assertTrue(all(len(d) == 8 for d in B.precache_extra_digests()))

    def test_build_sw_fills_placeholders(self):
        B.build_sw()
        sw = (B.ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertNotIn("__VERSION__", sw)
        self.assertNotIn("/*__PRECACHE__*/", sw)
        self.assertIn('"/offline.html"', sw)


if __name__ == "__main__":
    unittest.main()
