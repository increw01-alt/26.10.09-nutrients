"""App Store 문구(app/store/listing.ios.ko.md)·iOS 출시 문서(docs/app-release-ios.md) 검사. 실행: python -m unittest tests.test_store_listing_ios -v"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LISTING = ROOT / "app/store/listing.ios.ko.md"
DOC = ROOT / "docs/app-release-ios.md"
WORKFLOW = ROOT / ".github/workflows/release-ios.yml"
LIMITS = {"이름": 30, "부제": 30, "프로모션 텍스트": 170, "설명": 4000, "키워드": 100, "새로운 기능": 4000}   # App Store Connect 글자 수 상한
BANNED = ("치료", "예방", "완치", "효능", "질병", "의학적")   # 식약처 범위 밖 표현


def sections(text):
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


class IosListingTests(unittest.TestCase):
    def test_sections_within_limits_and_without_disease_claims(self):
        sec = sections(LISTING.read_text(encoding="utf-8"))
        self.assertEqual(set(LIMITS), set(sec))
        for name, limit in LIMITS.items():
            self.assertLessEqual(len(sec[name]), limit, name)
            for w in BANNED:
                self.assertNotIn(w, sec[name], "%s 에 금칙어 %s" % (name, w))
        self.assertEqual(sec["이름"], "영양제.kr")
        self.assertNotIn(" ", sec["키워드"])   # 쉼표만, 공백 없음(공백도 글자 수에 들어감)

    def test_urls_are_ascii_punycode(self):
        for f in (LISTING, DOC):
            for host in re.findall(r"https?://([^/\s)`\]]+)", f.read_text(encoding="utf-8")):
                self.assertTrue(host.isascii(), "%s: %s" % (f.name, host))

    def test_secret_names_match_workflow(self):
        names = set(re.findall(r"secrets\.([A-Z0-9_]+)", WORKFLOW.read_text(encoding="utf-8")))
        self.assertEqual(names, {"ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_PRIVATE_KEY_BASE64", "APPLE_TEAM_ID"})
        doc = DOC.read_text(encoding="utf-8")
        for n in names:
            self.assertIn("gh secret set %s" % n, doc)

    def test_doc_requires_admin_key_role(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("Admin", doc)   # App Manager 키는 클라우드 서명 권한 오류
        self.assertIn("release-ios", doc)
        self.assertIn("build_store_assets.py --ios-phone", doc)
