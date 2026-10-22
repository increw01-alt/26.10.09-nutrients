"""scripts/fetch_products.py 의 제품-성분 매칭 규칙 — 키워드 검사(kw_in)와 새 원료 규칙이 원하는 제품만 잡는지 (API 호출 없음)."""
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    import requests  # noqa: F401
except ImportError:
    sys.modules["requests"] = types.ModuleType("requests")
import fetch_products as P  # noqa: E402


def row(name, raw="", func=""):
    return {"PRDLST_NM": name, "RAWMTRL_NM": raw, "PRIMARY_FNCLTY": func}


class KeywordTests(unittest.TestCase):
    def test_kw_in_regex_prefix_and_boundaries(self):
        self.assertTrue(P.kw_in("re:글루타민(?!산)", "l-글루타민 분말"))
        self.assertFalse(P.kw_in("re:글루타민(?!산)", "l-글루타민산 유래 gaba 함유 분말"))
        self.assertTrue(P.kw_in("epa", "epa 및 dha 함유 유지"))
        self.assertFalse(P.kw_in("epa", "hepazone"))
        self.assertTrue(P.kw_in("비타민b1", "비타민b1 질산염"))
        self.assertFalse(P.kw_in("비타민b1", "비타민b12"))

    def test_new_herbal_rules_match_expected_products(self):
        matchers = (P.NUTRIENT_RULES, P.HERBAL_RULES)
        ids = lambda r: set(P.match_ingredients(r, matchers))  # noqa: E731
        self.assertIn("glutamine", ids(row("L-글루타민 파우더", "L-글루타민(개별인정형), 결정셀룰로스")))
        self.assertNotIn("glutamine", ids(row("가바 분말", "L-글루타민산 유래 GABA 함유 분말(개별인정형)")))
        self.assertIn("lycopene", ids(row("토마토 리코펜", "토마토추출물(개별인정형), 올리브유")))
        self.assertIn("bilberry", ids(row("눈건강 루테인빌베리", "마리골드꽃추출물(고시형), 빌베리추출물(개별인정형)")))
        self.assertIn("nattokinase", ids(row("혈행케어", "HK나토배양물(개별인정형)")))
        self.assertIn("hovenia", ids(row("간편한간", "헛개나무과병추출분말(개별인정형)")))
        self.assertIn("lactoferrin", ids(row("락토페린 300", "락토페린(우유정제단백질)(개별인정형)")))
        for iid in ("lycopene", "bilberry", "glutamine", "nattokinase", "hovenia", "lactoferrin"):
            self.assertIn(iid, P.HERBAL_RULES)


if __name__ == "__main__":
    unittest.main()
