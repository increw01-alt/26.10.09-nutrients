"""scripts/fetch_drugs.py 의 전문의약품(처방약) 허가 목록 수집 — 가짜 클라이언트로 후보 파라미터·필터 미적용 감지·페이지·예산 재개·정규화·상한을 검사한다 (API 호출 없음)."""
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    import requests  # noqa: F401
except ImportError:   # 수집기는 requests 를 호출 시점에만 쓰므로 테스트 환경에 없으면 빈 모듈로 대신한다
    sys.modules["requests"] = types.ModuleType("requests")
import fetch_drugs as F  # noqa: E402


def row(seq, name, ingr, company="제약사", otc="전문의약품", cls="[02180]동맥경화용제", date="20200101", cancel="정상"):
    return {"ITEM_SEQ": seq, "ITEM_NAME": name, "ITEM_INGR_NAME": ingr, "ENTP_NAME": company, "SPCLTY_PBLC": otc, "PRDUCT_TYPE": cls, "ITEM_PERMIT_DATE": date, "CANCEL_NAME": cancel, "BIG_PRDT_IMG_URL": ""}


class FakeClient:
    """허가 목록 API 흉내: pages[(파라미터, 값)] = 행 목록. unsupported 파라미터는 필터를 무시해 전체(total_rx)를 돌려주고, errors 는 HTTP 400 처럼 예외."""

    def __init__(self, pages, total_rx=20000, unsupported=(), errors=()):
        self.pages, self.total_rx, self.unsupported, self.errors = pages, total_rx, set(unsupported), set(errors)
        self.calls = 0
        self.budget = 10_000
        self.log = []

    def get(self, service, retries=3, **params):
        if self.calls >= self.budget:   # 실제 Client 처럼 예산을 넘기면 QuotaExceeded
            raise F.QuotaExceeded(f"실행당 호출 예산({self.budget}회) 소진")
        self.calls += 1
        self.log.append(dict(params))
        n = int(params.get("numOfRows", F.PAGE)); page = int(params.get("pageNo", 1))
        key = [(k, v) for k, v in params.items() if k in ("item_ingr_name", "item_name")]
        if not key:                       # 경로 확인·전체 건수
            return [row("x", "x", "x")][:n], self.total_rx
        k = key[0]
        if k in self.errors:
            raise RuntimeError("HTTP 400 Bad Request")
        if k[0] in self.unsupported:      # 필터 무시 → 전체 목록
            rows = [row(f"u{i}", f"아무약{i}", "Anything") for i in range(250)]
            return rows[(page - 1) * n: page * n], self.total_rx
        rows = self.pages.get(k, [])
        return rows[(page - 1) * n: page * n], len(rows)


ATOR = [row(f"a{i}", f"아토르바정{i}mg", "Atorvastatin Calcium Trihydrate", date=f"2021{(i % 12) + 1:02d}01") for i in range(120)]
ROSU = [row(f"r{i}", f"로수바정{i}mg", "Rosuvastatin Calcium") for i in range(5)]
LEVO = [row(f"l{i}", f"레보티록신정{i}", "Levothyroxine Sodium Hydrate", cls="[02430]갑상선, 부갑상선호르몬제") for i in range(3)]
RULES = [{"id": "statin", "ingr": ["atorvastatin", "rosuvastatin"]}, {"id": "thyroid", "ingr": ["levothyroxine"]}]


class FetchRxTests(unittest.TestCase):
    def setUp(self):
        F.PAUSE_BETWEEN_CALLS = 0
        F._PERMIT_RESOLVED.clear()

    def test_rx_queries_candidates(self):
        self.assertEqual(F.rx_queries("atorvastatin"), [("item_ingr_name", "Atorvastatin"), ("item_ingr_name", "atorvastatin"), ("item_name", "아토르바스타틴")])
        self.assertEqual(F.rx_queries("mefenamic acid")[0], ("item_ingr_name", "Mefenamic Acid"))
        self.assertTrue(all(p != "item_name" or any("가" <= ch <= "힣" for ch in v) for p, v in F.rx_queries("zzqx")))   # 사전에 없으면 한글 후보 없음

    def test_fetch_rx_paginates_and_falls_back(self):
        c2 = FakeClient({("item_ingr_name", "Atorvastatin"): ATOR, ("item_name", "로수바스타틴"): ROSU, ("item_name", "레보티록신"): LEVO})
        cache = {}
        st = F.fetch_rx(c2, "svc", RULES, cache, budget=100)
        self.assertTrue(cache["statin"]["done"] and cache["thyroid"]["done"])
        self.assertEqual(len(cache["statin"]["rows"]), 125)          # 아토르바 120 + 로수바 5(영문 두 후보 0건 → 한글 제품명)
        self.assertEqual(len(cache["thyroid"]["rows"]), 3)
        self.assertEqual(st["rules"], 2)
        self.assertEqual(st["calls"], 2 + 3 + 3)                     # ator p1·p2 / rosu 후보 3 / levo 후보 3(영문 2개 0건 → 한글)
        self.assertEqual(cache["statin"]["rows"]["a0"]["company"], "제약사")
        self.assertEqual(cache["statin"]["rows"]["a0"]["cls"], "동맥경화용제")   # [코드] 접두 제거
        # 필터가 안 먹는 파라미터는 전체 건수와 같아 버리고 다시 쓰지 않는다
        c3 = FakeClient({("item_name", "레보티록신"): LEVO}, unsupported=("item_ingr_name",))
        cache3 = {}
        F.fetch_rx(c3, "svc", [RULES[1]], cache3, budget=100)
        self.assertEqual(cache3["thyroid"]["bad"], ["item_ingr_name"])
        self.assertEqual(len(cache3["thyroid"]["rows"]), 3)
        self.assertEqual(sum(1 for q in c3.log if "item_ingr_name" in q), 1)   # 한 번만 시도
        # 첫 페이지부터 거부되는 후보는 다음 후보로
        c4 = FakeClient({("item_ingr_name", "levothyroxine"): LEVO}, errors=(("item_ingr_name", "Levothyroxine"),))
        cache4 = {}
        F.fetch_rx(c4, "svc", [RULES[1]], cache4, budget=100)
        self.assertTrue(cache4["thyroid"]["done"]); self.assertEqual(len(cache4["thyroid"]["rows"]), 3)

    def test_fetch_rx_budget_resume_and_refresh(self):
        pages = {("item_ingr_name", "Atorvastatin"): ATOR, ("item_name", "로수바스타틴"): ROSU, ("item_name", "레보티록신"): LEVO}
        cache = {}
        st1 = F.fetch_rx(FakeClient(pages), "svc", RULES, cache, budget=3)     # ator p1·p2 + rosu 후보 1 → 예산 소진
        self.assertEqual(st1["calls"], 3)
        self.assertFalse(cache["statin"]["done"]); self.assertEqual(len(cache["statin"]["rows"]), 120)
        self.assertEqual((cache["statin"]["term"], cache["statin"]["cand"], cache["statin"]["page"]), (1, 1, 1))
        self.assertNotIn("thyroid", cache)
        st2 = F.fetch_rx(FakeClient(pages), "svc", RULES, cache, budget=100)   # 이어서 완료
        self.assertTrue(cache["statin"]["done"] and cache["thyroid"]["done"])
        self.assertEqual(len(cache["statin"]["rows"]), 125)
        self.assertEqual(st2["calls"], 2 + 3)
        # 완료된 규칙은 30일 안에는 호출 없이 건너뛴다
        c = FakeClient(pages)
        st3 = F.fetch_rx(c, "svc", RULES, cache, budget=100)
        self.assertEqual((c.calls, st3["rules"]), (0, 0))
        # 오래된 완료 규칙은 다시 받되 이전 행은 완료될 때까지 prev 로 남는다
        cache["statin"]["at"] = "2020-01-01T00:00:00+09:00"
        F.fetch_rx(FakeClient(pages), "svc", RULES, cache, budget=1)
        self.assertFalse(cache["statin"]["done"]); self.assertEqual(len(cache["statin"]["prev"]), 125)
        recs = F.rx_records(cache, set(), per_rule=500)
        self.assertEqual(len(recs), 125 + 3)                                   # prev + 진행 중 행 + 갑상선

    def test_normalize_rx_and_records(self):
        valid = {"vitamin-c", "vitamin-d"}
        e = F.permit_entry(row("1", "비타씨플러스정(아스코르브산)", "Ascorbic Acid/Atorvastatin Calcium", company="(주)테스트제약", date="20230505"))
        rec = F.normalize_rx("1", e, valid)
        self.assertEqual((rec["id"], rec["otc"], rec["company"], rec["permitDate"], rec["source"]), ("1", "전문의약품", "(주)테스트제약", "2023-05-05", "mfds-permit"))
        self.assertIn("vitamin-c", rec["ingredients"])
        self.assertEqual(rec["efficacy"], ""); self.assertEqual(rec["usage"], "")
        self.assertNotIn("cancel", rec)
        self.assertEqual(len(rec["ingr"]), 2)
        gone = F.normalize_rx("2", F.permit_entry(row("2", "취하약", "Atorvastatin", cancel="취하")), valid)
        self.assertEqual(gone["cancel"], "취하")
        cache = {"statin": {"done": True, "rows": {
            "1": F.permit_entry(row("1", "리피토정10mg", "Atorvastatin", company="비아트리스", date="20100101")),
            "2": F.permit_entry(row("2", "취하정", "Atorvastatin", cancel="취하", date="20250101")),
            "3": F.permit_entry(row("3", "새약정", "Atorvastatin", date="20240101")),
            "4": F.permit_entry(row("4", "옛약정", "Atorvastatin", date="20150101")),
        }}, "other": {"done": True, "rows": {"3": F.permit_entry(row("3", "새약정", "Atorvastatin", date="20240101"))}}}
        recs = F.rx_records(cache, valid, per_rule=2, weight=lambda n, c: 3 if "리피토" in n else 0)
        self.assertEqual([r["id"] for r in sorted(recs, key=lambda r: r["permitDate"], reverse=True)], ["3", "1"])   # 가중치 → 최신, 취하 제외, 상한 2, 중복 한 번
        self.assertEqual(len(recs), 2)

    def test_rx_records_prefers_brand_keywords_and_caps_company(self):
        rows = {}
        for i in range(15):   # 대형 제약사(가중치 3) 제네릭 15건 — 상한(12)을 넘는 만큼은 뒤로
            rows[f"a{i}"] = F.permit_entry(row(f"a{i}", f"유한아토르바정{i}", "Atorvastatin Calcium Trihydrate", company="(주)유한양행", date=f"2024{(i % 12) + 1:02d}01"))
        rows["lip"] = F.permit_entry(row("lip", "리피토정10밀리그램", "Atorvastatin Calcium Trihydrate", company="비아트리스코리아(주)", date="20041025"))
        rows["c"] = F.permit_entry(row("c", "씨약정", "Atorvastatin Calcium", company="C제약", date="20250101"))
        cache = {"statin": {"done": True, "rows": rows}}
        recs = F.rx_records(cache, set(), per_rule=14, weight=lambda n, c: 3 if "유한" in c else 0, kw_weight=lambda n: 2 if "리피토" in n else 0)
        ids = {r["id"] for r in recs}
        self.assertIn("lip", ids); self.assertIn("c", ids)                                   # 브랜드 키워드·다른 제조사가 먼저 들어간다
        self.assertEqual(sum(1 for r in recs if r["company"] == "(주)유한양행"), 12)          # 제조사당 상한
        self.assertEqual(len(recs), 14)
        self.assertEqual(next(r for r in recs if r["id"] == "lip")["ingr"], ["아토르바스타틴칼슘삼수화물"])   # 칼슘염 한글 표기
        small = F.rx_records(cache, set(), per_rule=16, weight=lambda n, c: 3 if "유한" in c else 0, kw_weight=None)
        self.assertEqual(len(small), 16)                                                    # 자리가 남으면 상한 너머도 채운다

    def test_fetch_rx_keeps_progress_when_quota_runs_out(self):
        pages = {("item_ingr_name", "Atorvastatin"): ATOR, ("item_name", "로수바스타틴"): ROSU, ("item_name", "레보티록신"): LEVO}
        c = FakeClient(pages); c.budget = 3   # 경로 확인·전체 건수·1페이지 뒤 QuotaExceeded
        cache = {}
        st = F.fetch_rx(c, "svc", RULES, cache, budget=100)
        self.assertTrue(st.get("stopped"))
        self.assertFalse(cache["statin"]["done"]); self.assertEqual(len(cache["statin"]["rows"]), 100)
        self.assertEqual((cache["statin"]["term"], cache["statin"]["page"]), (0, 2))
        self.assertNotIn("thyroid", cache)

    def test_rebuild_rows_and_real_rules(self):
        prev = {"a": {"id": "a", "name": "A", "source": "mfds-drug"}, "b": {"id": "b", "name": "B", "source": "mfds-permit"}}
        self.assertEqual([r["itemSeq"] for r in F.rebuild_rows(prev)], ["a"])
        rules = F.load_rx_rules()
        self.assertGreaterEqual(len(rules), 10)
        self.assertTrue(all(r.get("ingr") for r in rules))
        self.assertIn("statin", {r["id"] for r in rules})
        self.assertNotIn("nsaid", {r["id"] for r in rules})



class RxRuleLoadTests(unittest.TestCase):
    def test_load_rx_rules_includes_new_prescription_rules(self):
        ids = {r["id"] for r in F.load_rx_rules()}
        self.assertTrue({"statin", "antihypertensive", "antidepressant", "anticonvulsant"} <= ids)
        import drug_ingr_ko as K
        for r in F.load_rx_rules():
            for term in r["ingr"]:
                self.assertTrue(any(k.startswith(term.lower()) or term.lower().startswith(k) for k in K.KO), f"KO 사전에 없는 주성분 {term}")

if __name__ == "__main__":
    unittest.main()
