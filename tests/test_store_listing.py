"""플레이 등록 문구(app/store/listing.ko.md)·출시 문서(docs/app-release.md) 검사. 실행: python -m unittest tests.test_store_listing -v"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LISTING = ROOT / "app/store/listing.ko.md"
DOC = ROOT / "docs/app-release.md"
WORKFLOW = ROOT / ".github/workflows/release-android.yml"
LIMITS = {"앱 이름": 30, "짧은 설명": 80, "전체 설명": 4000, "출시 노트": 500}   # 플레이 콘솔 글자 수 상한
BANNED = ("치료", "예방", "완치", "효능", "질병", "의학적")   # 식약처 범위 밖 표현


def sections(text):
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


class ListingTests(unittest.TestCase):
    def test_listing_sections_within_limits_and_without_disease_claims(self):
        sec = sections(LISTING.read_text(encoding="utf-8"))
        self.assertEqual(set(LIMITS), set(sec))
        for name, limit in LIMITS.items():
            self.assertLessEqual(len(sec[name]), limit, name)
            for w in BANNED:
                self.assertNotIn(w, sec[name], "%s 에 금칙어 %s" % (name, w))
        self.assertEqual(sec["앱 이름"], "영양제.kr")

    def test_urls_are_ascii_punycode(self):
        # 호스트 부분만 본다 — 'https://영양제.kr/…' 처럼 한글 도메인을 쓰면 콘솔 입력란이 거부할 수 있다(뒤에 붙은 조사·괄호는 제외)
        for f in (LISTING, DOC):
            for host in re.findall(r"https?://([^/\s)`\]]+)", f.read_text(encoding="utf-8")):
                self.assertTrue(host.isascii(), "%s: %s" % (f.name, host))

    def test_secret_names_match_workflow(self):
        names = set(re.findall(r"secrets\.(ANDROID_[A-Z_]+)", WORKFLOW.read_text(encoding="utf-8")))
        self.assertEqual(len(names), 4)
        doc = DOC.read_text(encoding="utf-8")
        for n in names:
            self.assertIn("gh secret set %s" % n, doc)

    def test_doc_names_privacy_url_and_workflow(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("https://xn--og5b1hx9c.kr/privacy", doc)
        self.assertIn("release-android", doc)
        self.assertIn("build_store_assets.py --screens", doc)

    def test_doc_key_password_equals_keystore_password(self):
        # JDK 9+ keytool 의 기본 형식 PKCS12 는 키 비밀번호를 따로 두지 못한다(키스토어 비밀번호와 같음). 다른 값을 넣으면 Gradle 서명이 실패하므로 문서가 같은 값을 쓰라고 안내해야 한다
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("`ANDROID_KEY_PASSWORD` 에는 `ANDROID_KEYSTORE_PASSWORD` 와 같은 값", doc)
        self.assertNotIn("둘을 같게 두어도 된다", doc)
