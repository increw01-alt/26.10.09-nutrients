"""scripts/build_site.py 의 PWA 관련 순수 함수 테스트. 실행: python -m unittest tests.test_build_site -v"""
import re
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
        self.assertIn('href="../assets/images/app/apple-touch-icon.png?v=%s"' % B.ICON_V, out)   # /assets/images/* 는 7일 캐시라 버전으로 캐시를 피함
        self.assertLess(out.index('rel="icon"'), out.index(B.PWA_START))
        self.assertLess(out.index(B.PWA_END), out.index('rel="stylesheet"'))

    def test_pwa_tags_include_both_web_app_metas(self):
        out = B.pwa_tags("./")
        self.assertIn('<meta name="mobile-web-app-capable" content="yes">', out)
        self.assertIn('<meta name="apple-mobile-web-app-capable" content="yes">', out)   # iOS 16.4 미만

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
        self.assertFalse(any("vendor/capacitor" in u for u in urls))   # 앱 전용 런타임은 웹 방문자에게 미리 받게 하지 않는다

    def test_build_sw_writes_to_given_path(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "sw.js"
            ver = B.build_sw(out)
            src = out.read_text(encoding="utf-8")
        self.assertRegex(ver, r"^[0-9a-f]{8}$")
        self.assertIn(f'var VERSION = "{ver}";', src)
        self.assertNotIn("__VERSION__", src); self.assertNotIn("/*__PRECACHE__*/[]", src)
        for must in ("/my.html", "/offline.html", "/assets/images/favicon.svg"):   # 앱 첫 화면·오프라인 안내·파비콘은 해시 없이 precache
            self.assertIn(f'"{must}"', src)
        self.assertIn('"static-" + version', src)

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

    def test_asset_digest_follows_rewritten_file(self):
        # 같은 경로의 파일이 빌드 중 다시 쓰이면(my.html 의 ?v= 스탬프 등) 캐시된 옛 해시가 아니라 새 내용의 해시를 돌려야 한다
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.css"
            p.write_bytes(b"a{}\n"); d1 = B.asset_digest(p)
            p.write_bytes(b"a{color:red}\n"); d2 = B.asset_digest(p)
        self.assertNotEqual(d1, d2)

    def test_sw_version_is_computed_from_stamped_html(self):
        """sw 버전은 ?v= 스탬프를 마친 뒤의 my.html·offline.html 내용으로 계산해야 한다. 스탬프 전 내용으로 계산하면 자산이 바뀐 커밋마다
        로컬(스탬프 전 파일로 빌드)과 CI(스탬프된 커밋을 받아 빌드)의 VERSION 이 갈려 CI 가 sw.js 커밋을 올리고 pull --rebase 가 충돌한다(10-22)."""
        import tempfile
        my = B.ROOT / "my.html"
        orig = my.read_bytes()
        try:
            dirty = re.sub(rb"\?v=[0-9a-f]{8}", b"?v=00000000", orig, count=1)   # 자산이 바뀐 뒤 아직 스탬프하지 않은 상태
            self.assertNotEqual(dirty, orig)
            my.write_bytes(dirty)
            B._DIGEST_CACHE.clear()
            with tempfile.TemporaryDirectory() as d:
                v1 = B.stamp_and_build_sw(Path(d) / "sw.js")
                v2 = B.stamp_and_build_sw(Path(d) / "sw.js")
            self.assertEqual(v1, v2, "같은 입력으로 다시 빌드하면 같은 버전이어야 한다")
            self.assertNotIn(b"?v=00000000", my.read_bytes())   # 스탬프가 돌아 bogus 해시가 바로잡혔다
            expect = B.sw_version(B.SW_TEMPLATE.read_text(encoding="utf-8"), B.precache_urls(), [B.asset_digest(B.ROOT / p) for p in B.PRECACHE_EXTRA if (B.ROOT / p).exists()])
            self.assertEqual(v1, expect, "버전은 디스크에 남는(스탬프된) 파일 내용과 맞아야 한다")
        finally:
            my.write_bytes(orig)
            B._DIGEST_CACHE.clear()

    def test_build_sw_fills_placeholders(self):
        B.build_sw()
        sw = (B.ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertNotIn("__VERSION__", sw)
        self.assertNotIn("/*__PRECACHE__*/", sw)
        self.assertIn('"/offline.html"', sw)


if __name__ == "__main__":
    unittest.main()


class ChartModelTests(unittest.TestCase):
    """영양제 궁합표·복용 시간표(compatibility-chart.html · timing-chart.html) 자료 함수."""

    CORE = {
        "by_id": {
            "a": {"id": "a", "name": "A 성분", "category": "vitamin", "timing": {"label": "식후", "slot": "morning_after", "altSlots": ["evening_after"]}, "fatSoluble": True},
            "b": {"id": "b", "name": "B 성분", "category": "mineral", "timing": {"label": "취침 전", "slot": "bedtime", "altSlots": ["bedtime", "evening_after"]}},
            "c": {"id": "c", "name": "C 성분 (별칭)", "category": "mineral", "timing": {}},
        },
        "pairs": [
            {"pair": ["a", "b"], "type": "synergy", "level": 3, "title": "a+b", "detail": "", "tip": ""},
            {"pair": ["c", "b"], "type": "caution", "level": 1, "separateHours": 2, "title": "c+b", "detail": "", "tip": ""},
            {"pair": ["x", "a"], "type": "synergy", "level": 1, "title": "없는 성분", "detail": "", "tip": ""},
        ],
        "categories": {"vitamin": {"label": "비타민"}, "mineral": {"label": "미네랄"}},
        "types": {},
    }

    def test_slot_meta_matches_schedule_js(self):
        js = (Path(__file__).resolve().parents[1] / "assets/js/schedule.js").read_text(encoding="utf-8")
        order = re.search(r"SLOT_ORDER = \[(.*?)\]", js).group(1)
        self.assertEqual(re.findall(r'"([a-z_]+)"', order), B.SLOT_ORDER)
        for key, meta in B.SLOT_META.items():
            m = re.search(key + r':\s*\{\s*label:\s*"([^"]+)",\s*sub:\s*"([^"]+)",\s*icon:\s*"([^"]+)"', js)
            self.assertIsNotNone(m, key)
            self.assertEqual((m.group(1), m.group(2), m.group(3)), (meta["label"], meta["sub"], meta["icon"]), key)

    def test_chart_model_is_symmetric_and_skips_unknown(self):
        m = B.chart_model(self.CORE, popular=["a", "b", "c", "zzz"])
        p = m["partners"]
        self.assertEqual([x["id"] for x in p["a"]["synergy"]], ["b"])
        self.assertEqual([x["id"] for x in p["b"]["synergy"]], ["a"])
        self.assertEqual(p["b"]["caution"][0]["hours"], 2)
        self.assertEqual(m["total"], 2)                      # 사전에 없는 성분(x)의 쌍은 제외
        self.assertEqual(m["counts"], {"synergy": 1, "caution": 1, "avoid": 0, "neutral": 0})
        self.assertEqual(m["matrix"]["ids"], ["a", "b", "c"])   # 모르는 id 는 행렬에서 제외
        cells = m["matrix"]["cells"]
        self.assertEqual(cells["a"]["a"], "self")
        self.assertEqual(cells["a"]["b"], "synergy")
        self.assertEqual(cells["b"]["c"], "caution")
        self.assertIsNone(cells["a"]["c"])                   # 데이터에 없는 쌍은 None (무난으로 보이면 안 됨)

    def test_chart_model_sorts_strong_pairs_first(self):
        core = dict(self.CORE, pairs=[
            {"pair": ["a", "c"], "type": "synergy", "level": 1, "title": "", "detail": "", "tip": ""},
            {"pair": ["a", "b"], "type": "synergy", "level": 3, "title": "", "detail": "", "tip": ""},
        ])
        self.assertEqual([x["id"] for x in B.chart_model(core)["partners"]["a"]["synergy"]], ["b", "c"])

    def test_timing_model_rows_and_slots(self):
        tm = B.timing_model(list(self.CORE["by_id"].values()), self.CORE["categories"])
        self.assertEqual([r["id"] for r in tm["rows"]], ["a", "b", "c"])       # 분류 순서 → 이름순
        self.assertTrue(all(r["slot"] in B.SLOT_META for r in tm["rows"]))
        c = next(r for r in tm["rows"] if r["id"] == "c")
        self.assertEqual((c["slot"], c["label"]), ("morning_after", "아침 식후"))   # timing 이 비면 기본값
        b = next(r for r in tm["rows"] if r["id"] == "b")
        self.assertEqual(b["alts"], ["evening_after"])                          # 기본 시간대와 같은 대체는 제외
        self.assertEqual([s["key"] for s in tm["slots"]], B.SLOT_ORDER)
        self.assertEqual([r["id"] for r in next(s for s in tm["slots"] if s["key"] == "bedtime")["items"]], ["b"])
        self.assertEqual([r["id"] for r in tm["fat"]], ["a"])

    def test_render_uses_real_data_once_per_ingredient(self):
        ingredients = B.read_json(B.DATA_DIR / "ingredients.json")
        interactions = B.read_json(B.DATA_DIR / "interactions.json")
        core = {"categories": ingredients["_meta"]["categories"], "by_id": {i["id"]: i for i in ingredients["items"]}, "pairs": interactions["pairs"], "types": interactions["_meta"]["types"]}
        cfg = {"name": "테스트", "url": "https://example.test"}
        chart = B.render_compat_chart(core, cfg)
        timing = B.render_timing_chart(core, cfg)
        for it in ingredients["items"]:
            self.assertEqual(chart.count(f'<article id="{it["id"]}"'), 1, it["id"])
            self.assertEqual(timing.count(f'<tr id="{it["id"]}"'), 1, it["id"])
        self.assertIn('rel="canonical" href="https://example.test/compatibility-chart"', chart)
        self.assertIn('rel="canonical" href="https://example.test/timing-chart"', timing)
        self.assertNotIn("inferred", chart)   # 규칙 판정은 파이썬에 복제하지 않는다


class FinderBuildTests(unittest.TestCase):
    """셀프체크(finder.html) — data/finder.json 검증과 정적 폼 생성."""

    @classmethod
    def setUpClass(cls):
        cls.data = B.read_json(B.DATA_DIR / "finder.json")
        ingredients = B.read_json(B.DATA_DIR / "ingredients.json")
        guides = B.read_json(B.DATA_DIR / "guides.json")
        cls.core = {"categories": ingredients["_meta"]["categories"], "by_id": {i["id"]: i for i in ingredients["items"]}, "guides": guides["items"], "pairs": [], "types": {}}
        cls.slugs = {g["slug"] for g in guides["items"]}
        cls.cfg = {"name": "테스트", "url": "https://example.test"}

    def test_validate_real_data(self):
        B.validate_finder(self.data, set(self.core["by_id"]), self.slugs)   # 예외 없이 통과

    def test_validate_rejects_unknown_guide_option_and_ingredient(self):
        import copy
        bad = copy.deepcopy(self.data); bad["rules"].append({"if": {"age": ["20s"]}, "guides": ["no-such-guide"]})
        with self.assertRaises(SystemExit):
            B.validate_finder(bad, set(self.core["by_id"]), self.slugs)
        bad = copy.deepcopy(self.data); bad["rules"].append({"if": {"age": ["no-such-option"]}, "guides": ["20s"]})
        with self.assertRaises(SystemExit):
            B.validate_finder(bad, set(self.core["by_id"]), self.slugs)
        bad = copy.deepcopy(self.data); [q for q in bad["questions"] if q["id"] == "have"][0]["popular"].append("no-such-ingredient")
        with self.assertRaises(SystemExit):
            B.validate_finder(bad, set(self.core["by_id"]), self.slugs)

    def test_validate_rejects_unknown_avoid_and_anticoagulant_covers_warfarin_cautions(self):
        import copy
        bad = copy.deepcopy(self.data); bad["rules"].append({"if": {"meds": ["surgery"]}, "guides": ["surgery"], "avoid": ["no-such-ingredient"]})
        with self.assertRaises(SystemExit):
            B.validate_finder(bad, set(self.core["by_id"]), self.slugs)
        rule = next(r for r in self.data["rules"] if (r.get("if") or {}).get("meds") == ["anticoagulant"])
        warfarin = next(r for r in B.read_json(B.DATA_DIR / "drug-pairings.json")["rules"] if r["id"] == "warfarin")
        self.assertTrue({c["id"] for c in warfarin["caution"]} <= set(rule["avoid"]))   # 와파린 규칙의 주의 성분은 모두 추천에서 뺀다
        self.assertIn("bleeding", rule["flags"])
        surgery = next(r for r in self.data["rules"] if (r.get("if") or {}).get("meds") == ["surgery"])
        self.assertTrue({"omega-3", "ginkgo", "garlic", "vitamin-e", "red-ginseng", "curcumin"} <= set(surgery["avoid"]))
        self.assertTrue({"memory", "bone", "blood-pressure"} <= {o["id"] for q in self.data["questions"] if q["id"] == "concern" for o in q["options"]})
        by_meds = {tuple((r.get("if") or {}).get("meds") or ()): r for r in self.data["rules"] if "meds" in (r.get("if") or {})}
        self.assertIn("potassium", by_meds[("hypertension",)]["avoid"])   # 혈압약(ACE 억제제·ARB·칼륨보존 이뇨제) — 칼륨 보충제 제외
        self.assertTrue({"potassium", "magnesium", "vitamin-a"} <= set(by_meds[("kidney",)]["avoid"]))

    def test_render_has_every_question_and_option_statically(self):
        html = B.render_finder(self.data, self.core, self.cfg)
        self.assertIn('id="finder-form"', html)
        self.assertIn('rel="canonical" href="https://example.test/finder"', html)
        for q in self.data["questions"]:
            self.assertIn(f'data-q="{q["id"]}"', html)
            for o in q.get("options", []):
                self.assertIn(f'name="{q["id"]}" value="{o["id"]}"', html)
            for pid in q.get("popular", []):
                self.assertIn(f'name="have" value="{pid}"', html)
        self.assertEqual(html.count('data-exclusive="1"'), sum(1 for q in self.data["questions"] for o in q.get("options", []) if o.get("exclusive")))
        self.assertIn("finder.html", B.STATIC_PAGES)


class FunctionHubTests(unittest.TestCase):
    """기능성별 허브(functions.html · function/<id>.html) — 정규화 표 검증·매칭·모델·렌더."""

    @classmethod
    def setUpClass(cls):
        cls.data = B.read_json(B.DATA_DIR / "functions.json")
        ingredients = B.read_json(B.DATA_DIR / "ingredients.json")
        interactions = B.read_json(B.DATA_DIR / "interactions.json")
        guides = B.read_json(B.DATA_DIR / "guides.json")
        cls.guides = guides
        cls.core = {"categories": ingredients["_meta"]["categories"], "by_id": {i["id"]: i for i in ingredients["items"]}, "guides": guides["items"], "pairs": interactions["pairs"], "types": interactions["_meta"]["types"]}
        cls.materials = (B.read_json(B.DATA_DIR / "materials.json", {}) or {}).get("items", [])
        cls.products = B.load_products_detail()
        cls.model = B.function_model(cls.data, cls.core, cls.materials, cls.products, guides["items"])
        cls.core["functions"] = cls.model
        cls.core["functions_meta"] = cls.data["_meta"]
        cls.cfg = {"name": "테스트", "url": "https://example.test"}

    def test_validate_real_data_and_rejects_bad(self):
        slugs = {g["slug"] for g in self.guides["items"]}
        B.validate_functions(self.data, slugs)
        import copy
        bad = copy.deepcopy(self.data); bad["items"][0]["guides"] = ["no-such-guide"]
        with self.assertRaises(SystemExit):
            B.validate_functions(bad, slugs)
        bad = copy.deepcopy(self.data); bad["items"][0]["match"] = ["("]
        with self.assertRaises(SystemExit):
            B.validate_functions(bad, slugs)
        bad = copy.deepcopy(self.data); bad["items"].append(dict(bad["items"][0]))
        with self.assertRaises(SystemExit):
            B.validate_functions(bad, slugs)

    def test_matcher_avoids_known_false_positives(self):
        by = {it["id"]: it for it in self.data["items"]}
        self.assertFalse(B.function_matcher(by["immunity"])("면역과민반응에 의한 피부상태 개선에 도움을 줄 수 있음"))
        self.assertTrue(B.function_matcher(by["immunity"])("면역력 증진에 도움을 줄 수 있음"))
        self.assertTrue(B.function_matcher(by["allergy"])("면역과민반응에 의한 피부상태 개선에 도움을 줄 수 있음"))
        self.assertFalse(B.function_matcher(by["fatigue"])("눈의 피로도 개선에 도움을 줄 수 있음"))
        self.assertTrue(B.function_matcher(by["eye"])("눈의 피로도 개선에 도움을 줄 수 있음"))
        self.assertFalse(B.function_matcher(by["growth"])("상피세포의 성장과 발달에 필요"))
        self.assertFalse(B.function_matcher(by["bone"])("관절 및 연골 건강에 도움을 줄 수 있음"))
        self.assertTrue(B.function_matcher(by["bone"])("뼈의 형성과 유지에 필요"))

    def test_model_every_function_has_content_and_expected_members(self):
        got = {e["fn"]["id"]: e for e in self.model["items"]}
        for fid, e in got.items():
            self.assertTrue(e["ingredients"] or e["materials"] or e["products"]["total"], fid)
            self.assertLessEqual(len(e["products"]["top"]), B.FUNCTION_TOP_PRODUCTS)
        ids = lambda fid: {i["id"] for i in got[fid]["ingredients"]}
        self.assertIn("garcinia", ids("body-fat"))
        self.assertIn("probiotics", ids("gut"))
        self.assertIn("vitamin-d", ids("bone"))
        self.assertIn("red-ginseng", ids("immunity")); self.assertIn("red-ginseng", ids("fatigue"))
        self.assertIn("milk-thistle", ids("liver"))
        self.assertNotIn("glucosamine", ids("bone"))
        self.assertIn("body-fat", self.model["by_ingredient"]["garcinia"])
        self.assertTrue(all(g["slug"] for g in got["body-fat"]["guides"]) and got["body-fat"]["guides"][0]["slug"] == "diet")

    def test_render_function_and_hub(self):
        entry = next(e for e in self.model["items"] if e["fn"]["id"] == "body-fat")
        html = B.render_function(entry, self.model, self.core, self.cfg, self.guides["_meta"]["types"])
        self.assertIn('rel="canonical" href="https://example.test/function/body-fat"', html)
        self.assertIn("체지방 감소에 도움을 줄 수 있음", html)
        for sec in ("ingredients", "materials", "products", "faq"):
            self.assertIn(f'id="{sec}"', html)
        self.assertIn('href="../i/garcinia.html"', html)
        hub = B.render_functions_hub(self.model, self.data, self.core, self.cfg)
        for e in self.model["items"]:
            self.assertIn(f'href="function/{e["fn"]["id"]}.html"', hub)
        self.assertIn("functions.html", B.STATIC_PAGES)

    def test_function_page_links_related_compares(self):
        cmp_model = B.compare_model(B.read_json(B.DATA_DIR / "compares.json"), self.core, self.guides["items"])
        entry = next(e for e in self.model["items"] if e["fn"]["id"] == "eye")
        fn_ids = {i["id"] if isinstance(i, dict) else i for i in entry["ingredients"]}
        expect = next(e["cmp"]["slug"] for e in cmp_model["items"] if all(i in fn_ids for i in e["cmp"]["ids"]))   # 성분이 모두 이 기능성에 있는 비교 (루테인 vs 아스타잔틴 등)
        html = B.render_function(entry, self.model, dict(self.core, compares=cmp_model), self.cfg, self.guides["_meta"]["types"])
        self.assertIn('id="compares"', html)
        self.assertIn(f'href="../compare/{expect}.html"', html)
        self.assertIn('href="#compares" class="chip">비교 글</a>', html)
        plain = B.render_function(entry, self.model, self.core, self.cfg, self.guides["_meta"]["types"])
        self.assertNotIn('id="compares"', plain)


class CompareTests(unittest.TestCase):
    """성분 비교(compare.html · compare/<slug>.html) — 데이터 검증·모델·렌더."""

    @classmethod
    def setUpClass(cls):
        cls.data = B.read_json(B.DATA_DIR / "compares.json")
        ingredients = B.read_json(B.DATA_DIR / "ingredients.json")
        interactions = B.read_json(B.DATA_DIR / "interactions.json")
        guides = B.read_json(B.DATA_DIR / "guides.json")
        cls.guides = guides
        cls.core = {"categories": ingredients["_meta"]["categories"], "by_id": {i["id"]: i for i in ingredients["items"]}, "guides": guides["items"], "pairs": interactions["pairs"], "types": interactions["_meta"]["types"]}
        cls.slugs = {g["slug"] for g in guides["items"]}
        cls.model = B.compare_model(cls.data, cls.core, guides["items"])
        cls.cfg = {"name": "테스트", "url": "https://example.test"}

    def test_validate_real_data_and_rejects_bad(self):
        B.validate_compares(self.data, set(self.core["by_id"]), self.slugs)
        import copy
        bad = copy.deepcopy(self.data); bad["items"][0]["ids"].append("no-such-ingredient")
        with self.assertRaises(SystemExit):
            B.validate_compares(bad, set(self.core["by_id"]), self.slugs)
        bad = copy.deepcopy(self.data); bad["items"][0]["related"] = ["no-such-guide"]
        with self.assertRaises(SystemExit):
            B.validate_compares(bad, set(self.core["by_id"]), self.slugs)
        bad = copy.deepcopy(self.data); bad["items"][0]["rows"] = [{"label": "x", "cells": {"zzz": "y"}}]
        with self.assertRaises(SystemExit):
            B.validate_compares(bad, set(self.core["by_id"]), self.slugs)
        bad = copy.deepcopy(self.data); bad["items"].append(dict(bad["items"][0]))
        with self.assertRaises(SystemExit):
            B.validate_compares(bad, set(self.core["by_id"]), self.slugs)

    def test_model_rows_cover_every_ingredient(self):
        for e in self.model["items"]:
            ids = [i["id"] for i in e["ingredients"]]
            labels = [r["label"] for r in e["rows"]]
            self.assertEqual(labels[0], "식약처 인정 기능성")
            for lab in ("하루 권장 섭취량", "먹는 시간", "신고 제품 수 (수집 범위)", "기능성별 페이지"):
                self.assertIn(lab, labels, e["cmp"]["slug"])
            for r in e["rows"]:
                for i in ids:
                    self.assertIn(i, r["cells"], f'{e["cmp"]["slug"]} {r["label"]}')
            self.assertEqual(len(e["pairs"]), len(ids) * (len(ids) - 1) // 2)
        self.assertIn("red-ginseng-vs-ginseng", self.model["by_ingredient"]["red-ginseng"])
        three = next(e for e in self.model["items"] if e["cmp"]["slug"] == "glucosamine-vs-chondroitin-vs-msm")
        self.assertEqual(len(three["ingredients"]), 3)
        self.assertEqual(len(three["pairs"]), 3)

    def test_render_compare_and_hub(self):
        entry = next(e for e in self.model["items"] if e["cmp"]["slug"] == "red-ginseng-vs-ginseng")
        html = B.render_compare(entry, self.core, self.cfg, self.guides["_meta"]["types"], "2026-10-22")
        self.assertIn('rel="canonical" href="https://example.test/compare/red-ginseng-vs-ginseng"', html)
        for sec in ("table", "verdict", "picks", "together", "timing", "shop", "faq"):
            self.assertIn(f'id="{sec}"', html)
        self.assertEqual(html.count("data-query="), 2)
        self.assertEqual(html.count('data-my-add="'), 2)
        self.assertIn('href="../i/red-ginseng.html"', html)
        self.assertIn("홍삼", html)
        hub = B.render_compare_hub(self.model, self.data, self.core, self.cfg)
        for e in self.model["items"]:
            self.assertIn(f'href="compare/{e["cmp"]["slug"]}.html"', hub)
        self.assertIn("compare.html", B.STATIC_PAGES)



    def test_related_compares_pick_and_rank(self):
        core = {"compares": {"items": [
            {"cmp": {"slug": "a-vs-b", "ids": ["a", "b"], "h1": "A vs B", "description": "", "related": ["g1"]}, "ingredients": [{"name": "A"}, {"name": "B"}]},
            {"cmp": {"slug": "a-vs-c", "ids": ["a", "c"], "h1": "A vs C", "description": "", "related": []}, "ingredients": [{"name": "A"}, {"name": "C"}]},
            {"cmp": {"slug": "b-vs-d", "ids": ["b", "d"], "h1": "B vs D", "description": "", "related": ["g2"]}, "ingredients": [{"name": "B"}, {"name": "D"}]}],
            "forms": [{"fc": {"slug": "a-forms", "id": "a", "h1": "A 형태", "description": "", "related": []}, "ingredient": {"name": "A"}, "forms": [1, 2]},
                      {"fc": {"slug": "e-forms", "id": "e", "h1": "E 형태", "description": "", "related": ["g1"]}, "ingredient": {"name": "E"}, "forms": [1, 2, 3]}]}}
        got = B.related_compares(core, ["a", "b"], "g1")
        self.assertEqual([x["slug"] for x in got], ["a-vs-b", "e-forms", "a-forms"])   # related 명시 → 성분 겹침 수 → 제목; c·d 가 없는 비교는 제외
        self.assertEqual([x["slug"] for x in B.related_compares(core, ["a", "b"], "g1", limit=2)], ["a-vs-b", "e-forms"])
        self.assertEqual(B.related_compares(core, ["a", "b"]), [x for x in B.related_compares(core, ["a", "b"]) if x["slug"] in ("a-vs-b", "a-forms")])   # slug 없으면 성분 포함 조건만
        self.assertEqual(B.related_compares({}, ["a", "b"], "g1"), [])
        html = B.compare_cards_html(got, "../")
        self.assertIn('href="../compare/a-vs-b.html"', html)
        self.assertIn("A <em>vs</em> B", html)
        self.assertIn("E <em>·</em> 형태 3가지", html)
        self.assertEqual(B.related_compares_section("", "x"), "")

    def test_guide_page_links_related_compares(self):
        guides = {"_meta": self.guides["_meta"], "items": self.guides["items"], "by_id": {g["id"]: g for g in self.guides["items"]}}
        gd = next(g for g in self.guides["items"] if g["slug"] == "eye-health")
        model = dict(self.model, forms=[{"fc": {"slug": "omega-3-forms", "id": "omega-3", "h1": "오메가3 형태", "description": "d", "related": []}, "ingredient": self.core["by_id"]["omega-3"], "forms": [1, 2, 3, 4]}])
        html = B.render_guide(gd, guides, dict(self.core, compares=model), self.cfg)
        self.assertIn('id="compares"', html)
        self.assertIn('href="../compare/lutein-vs-astaxanthin.html"', html)   # ids 가 모두 가이드 성분에 있음
        self.assertIn('href="../compare/omega-3-forms.html"', html)           # 기준 성분이 가이드 성분에 있음
        self.assertNotIn('href="../compare/omega-3-vs-gla.html"', html)       # 감마리놀렌산은 눈 가이드 성분이 아님
        self.assertIn('href="#compares" class="chip">비교 글</a>', html)
        plain = B.render_guide(gd, guides, self.core, self.cfg)               # 비교 모델 없이도 그려짐
        self.assertNotIn('id="compares"', plain)
        self.assertLessEqual(html.count('class="cmp-card"'), B.RELATED_COMPARES_MAX)


class FormCompareTests(unittest.TestCase):
    """제형·형태 비교(compare/<slug>.html, 성분 비교 허브의 두 번째 묶음) — 데이터 검증·모델(정규식 집계·rest·대표 제품)·렌더·허브·색인."""

    @classmethod
    def setUpClass(cls):
        cls.data = B.read_json(B.DATA_DIR / "form-compares.json")
        cls.cmp_data = B.read_json(B.DATA_DIR / "compares.json")
        ingredients = B.read_json(B.DATA_DIR / "ingredients.json")
        interactions = B.read_json(B.DATA_DIR / "interactions.json")
        guides = B.read_json(B.DATA_DIR / "guides.json")
        glossary = B.read_json(B.DATA_DIR / "glossary.json")
        cls.guides = guides
        cls.core = {"categories": ingredients["_meta"]["categories"], "by_id": {i["id"]: i for i in ingredients["items"]}, "guides": guides["items"], "pairs": interactions["pairs"], "types": interactions["_meta"]["types"]}
        cls.core["glossary"] = B.glossary_model(glossary, cls.core, guides["items"])
        cls.core["term_linker"] = B.TermLinker(glossary["items"])
        cls.slugs = {g["slug"] for g in guides["items"]}
        cls.term_slugs = {t["slug"] for t in glossary["items"]}
        cls.taken = {it["slug"] for it in cls.cmp_data["items"]}
        # 가짜 제품 조각: 이름·원재료명 표기로 형태를 가르고, 같은 이름(p5·p6)은 대표 제품에 한 번만, 가중치가 높은 회사(D)가 먼저
        cls.products = [
            {"id": "p1", "name": "알티지 오메가3", "company": "A", "registeredAt": "2026-01-01", "rawMaterials": "정제어유", "ingredients": ["omega-3"]},
            {"id": "p2", "name": "오메가3 1000", "company": "B", "registeredAt": "2025-01-01", "rawMaterials": "EPA 및 DHA 함유 유지(rTG)", "ingredients": ["omega-3"]},
            {"id": "p3", "name": "식물성 오메가3", "company": "C", "registeredAt": "2024-01-01", "rawMaterials": "미세조류유", "ingredients": ["omega-3", "vitamin-e"]},
            {"id": "p4", "name": "크릴오일 1000", "company": "D", "registeredAt": "2023-01-01", "rawMaterials": "크릴오일", "ingredients": ["omega-3"]},
            {"id": "p5", "name": "순수 오메가3", "company": "E", "registeredAt": "2022-01-01", "rawMaterials": "정제어유", "ingredients": ["omega-3"]},
            {"id": "p6", "name": "순수 오메가3", "company": "E", "registeredAt": "2021-01-01", "rawMaterials": "정제어유", "ingredients": ["omega-3"]},
            {"id": "p7", "name": "비타민C 1000", "company": "F", "registeredAt": "2022-01-01", "rawMaterials": "비타민C", "ingredients": ["vitamin-c"]},
        ]
        cls.model = B.form_compare_model(cls.data, cls.core, cls.products, guides["items"], cls.core["glossary"], weight=lambda n, c: 3 if (c or "") == "D" else 0)
        cls.cfg = {"name": "테스트", "url": "https://example.test"}

    def test_validate_real_data_and_rejects_bad(self):
        B.validate_form_compares(self.data, set(self.core["by_id"]), self.slugs, self.term_slugs, self.taken)
        import copy
        bad = copy.deepcopy(self.data); bad["items"][0]["forms"][0]["match"] = "("
        with self.assertRaises(SystemExit):
            B.validate_form_compares(bad, set(self.core["by_id"]), self.slugs, self.term_slugs, self.taken)
        bad = copy.deepcopy(self.data); bad["items"][0]["terms"] = ["no-such-term"]
        with self.assertRaises(SystemExit):
            B.validate_form_compares(bad, set(self.core["by_id"]), self.slugs, self.term_slugs, self.taken)
        bad = copy.deepcopy(self.data); bad["items"][0]["slug"] = next(iter(self.taken))   # 성분 비교 slug 와 겹침
        with self.assertRaises(SystemExit):
            B.validate_form_compares(bad, set(self.core["by_id"]), self.slugs, self.term_slugs, self.taken)
        bad = copy.deepcopy(self.data); bad["items"][0]["rows"][0]["cells"].pop(bad["items"][0]["forms"][0]["key"])
        with self.assertRaises(SystemExit):
            B.validate_form_compares(bad, set(self.core["by_id"]), self.slugs, self.term_slugs, self.taken)
        bad = copy.deepcopy(self.data); bad["items"][0]["forms"][1]["rest"] = True   # rest 둘
        with self.assertRaises(SystemExit):
            B.validate_form_compares(bad, set(self.core["by_id"]), self.slugs, self.term_slugs, self.taken)
        bad = copy.deepcopy(self.data); bad["items"][0]["id"] = "no-such-ingredient"
        with self.assertRaises(SystemExit):
            B.validate_form_compares(bad, set(self.core["by_id"]), self.slugs, self.term_slugs, self.taken)

    def test_model_splits_products_by_form_and_rest_is_disjoint(self):
        e = next(x for x in self.model if x["fc"]["slug"] == "omega-3-forms")
        self.assertEqual(e["ingredient"]["id"], "omega-3")
        self.assertEqual(e["base_total"], 6)   # 비타민C 제품은 기준 성분이 아님
        by_key = {fm["f"]["key"]: fm for fm in e["forms"]}
        self.assertEqual(set(by_key), {"rtg", "algae", "krill", "rest"})
        self.assertEqual(by_key["rtg"]["ids"], {"p1", "p2"})       # 이름 '알티지' + 원재료명 'rTG'
        self.assertEqual(by_key["algae"]["ids"], {"p3"})
        self.assertEqual(by_key["krill"]["ids"], {"p4"})
        self.assertEqual(by_key["rest"]["ids"], {"p5", "p6"})      # 다른 형태에 걸린 제품은 rest 에 없음
        matched = by_key["rtg"]["ids"] | by_key["algae"]["ids"] | by_key["krill"]["ids"]
        self.assertFalse(matched & by_key["rest"]["ids"])
        self.assertEqual(by_key["rest"]["total"], 2)
        self.assertEqual([p["name"] for p in by_key["rest"]["top"]], ["순수 오메가3"])   # 같은 이름은 한 번
        self.assertEqual(by_key["rtg"]["top"][0]["id"], "p1")      # 가중치 같으면 신고일 최신 순
        self.assertEqual(len(e["terms"]), len(e["fc"]["terms"]))
        self.assertTrue(all(g["slug"] in e["fc"]["related"] for g in e["guides"]))
        for x in self.model:   # 모든 편: rest 는 최대 하나, 전체 형태 합집합 ⊆ 기준 제품
            rests = [fm for fm in x["forms"] if fm["f"].get("rest")]
            self.assertLessEqual(len(rests), 1, x["fc"]["slug"])

    def test_shape_token_matching(self):
        self.assertEqual(B.form_match_text({"name": "n", "rawMaterials": "r", "shape": " 정 "}), "n | r | 제형:정")
        data = {"items": [{"slug": "x-forms", "id": "omega-3", "title": "t", "h1": "h", "description": "d", "intro": "i", "verdict": "v", "label": "l", "faq": [{"q": "q", "a": "a"}],
                           "forms": [{"key": "liquid", "label": "액상", "short": "s", "shopQuery": "q", "line": "l", "match": "제형:(액상|겔)"},
                                     {"key": "rest", "label": "나머지", "short": "s", "shopQuery": "q", "line": "l", "rest": True}],
                           "rows": [{"label": "r", "cells": {"liquid": "1", "rest": "2"}}]}]}
        products = [dict(p, shape=s) for p, s in zip(self.products[:4], ["액상", "정", "겔", ""])]
        by_key = {fm["f"]["key"]: fm for fm in B.form_compare_model(data, self.core, products, self.guides["items"], self.core["glossary"])[0]["forms"]}
        self.assertEqual(by_key["liquid"]["ids"], {"p1", "p3"})   # 신고 제형 토큰으로 가름
        self.assertEqual(by_key["rest"]["ids"], {"p2", "p4"})
        self.assertTrue({"vitamin-k-forms", "red-ginseng-forms", "probiotics-forms"} <= {it["slug"] for it in self.data["items"]})

    def test_top_products_prefer_brand_weight(self):
        products = [dict(p, ingredients=["omega-3"], rawMaterials="크릴오일", name=f"크릴 {i}", company=("D" if i == 3 else "Z"), registeredAt=f"2025-0{i}-01") for i, p in enumerate(self.products[:5], start=1)]
        model = B.form_compare_model(self.data, self.core, products, self.guides["items"], self.core["glossary"], weight=lambda n, c: 3 if c == "D" else 0)
        krill = next(fm for fm in next(x for x in model if x["fc"]["slug"] == "omega-3-forms")["forms"] if fm["f"]["key"] == "krill")
        self.assertEqual(krill["total"], 5)
        self.assertEqual(krill["top"][0]["name"], "크릴 3")   # 가중치 3 인 회사가 먼저
        self.assertEqual(krill["top"][1]["name"], "크릴 5")   # 그다음은 신고일 최신 순

    def test_render_form_compare_and_hub_and_index(self):
        e = next(x for x in self.model if x["fc"]["slug"] == "omega-3-forms")
        html = B.render_form_compare(e, self.core, self.cfg, self.guides["_meta"]["types"], "2026-10-23")
        self.assertIn('rel="canonical" href="https://example.test/compare/omega-3-forms"', html)
        for sec in ("table", "verdict", "picks", "label", "products", "terms", "guides", "faq"):
            self.assertIn(f'id="{sec}"', html)
        self.assertEqual(html.count("data-query="), 4)                  # 형태마다 쇼핑 버튼 자리 하나
        self.assertEqual(html.count('<th scope="col">'), 5)               # 항목 + 형태 4
        self.assertIn("수집 제품 수 (표기 기준)", html)
        self.assertIn('href="../product.html?id=p1"', html)
        self.assertIn('href="../term/rtg.html"', html)
        self.assertIn('href="../i/omega-3.html"', html)
        self.assertIn('"@type": "FAQPage"', html)
        import json as _json
        self.assertIsNone(re.search(r"흡수율\s*\d|\d+\s*배 (더|높|좋)|가격대", _json.dumps(self.data["items"], ensure_ascii=False)))   # (_meta 제외) 흡수율 수치·배수·가격대 표현 금지의 간단한 방어선
        # 허브: 성분 대 성분 묶음 + 제형·형태 묶음, 요약 색인·성분 페이지 칩은 write_compares/render_page 가 forms 를 읽음
        cmp_model = B.compare_model(self.cmp_data, self.core, self.guides["items"])
        cmp_model["forms"] = self.model
        hub = B.render_compare_hub(cmp_model, self.cmp_data, self.core, self.cfg)
        self.assertIn('href="compare/omega-3-forms.html"', hub)
        self.assertIn(f"제형·형태 비교 {len(self.model)}편", hub)
        self.assertIn(f"({len(cmp_model['items']) + len(self.model)}편)", hub)
        self.assertEqual(hub.count('class="cmp-card"'), len(cmp_model["items"]) + len(self.model))
        # 성분 페이지 칩: by_ingredient 에 형태 비교 slug 가 더해지면 '비교 글' 칩에 나온다
        cmp_model.setdefault("by_ingredient", {}).setdefault("omega-3", []).append("omega-3-forms")
        core = dict(self.core, compares=cmp_model)
        page = B.render_page(self.core["by_id"]["omega-3"], core, self.cfg)
        self.assertIn('href="../compare/omega-3-forms.html"', page)


class StampTests(unittest.TestCase):
    """생성 색인의 updatedAt 은 빌드 시각이 아니라 원본 데이터의 updatedAt(최신값) — 같은 데이터로 두 번 빌드해도 파일이 같아야 CI 자동 커밋이 반복되지 않는다."""

    def test_data_stamp_uses_source_updated_at(self):
        self.assertEqual(B.data_stamp({"_meta": {"updatedAt": "2026-10-22"}}, {"_meta": {"updatedAt": "2026-10-23"}}, default="2020-01-01"), "2026-10-23")
        self.assertEqual(B.data_stamp({"_meta": {}}, None, default="2020-01-01"), "2020-01-01")
        self.assertEqual(B.data_stamp({"_meta": {"updatedAt": "2026-10-22"}}, None), "2026-10-22")


class DrugGuideTests(unittest.TestCase):
    """약별 영양제 가이드(drug-guides.html · drug-guide/<id>.html) — 데이터 검증·의약품 판정·모델·렌더."""

    @classmethod
    def setUpClass(cls):
        cls.data = B.read_json(B.DATA_DIR / "drug-guides.json")
        cls.rules = B.read_json(B.DATA_DIR / "drug-pairings.json")["rules"]
        ingredients = B.read_json(B.DATA_DIR / "ingredients.json")
        interactions = B.read_json(B.DATA_DIR / "interactions.json")
        guides = B.read_json(B.DATA_DIR / "guides.json")
        cls.guides = guides
        cls.core = {"categories": ingredients["_meta"]["categories"], "by_id": {i["id"]: i for i in ingredients["items"]}, "guides": guides["items"], "pairs": interactions["pairs"], "types": interactions["_meta"]["types"]}
        cls.slugs = {g["slug"] for g in guides["items"]}
        cls.drugs = B.load_drugs_detail()
        cls.model = B.drug_guide_model(cls.data, cls.rules, cls.core, cls.drugs, guides["items"])
        cls.by_rule = {r["id"]: r for r in cls.rules}
        cls.cfg = {"name": "테스트", "url": "https://example.test"}

    def test_new_prescription_rules_grounded_in_dictionary(self):
        """혈압약·항우울제·항경련제 규칙(10-22): 성분 사전 drugCautions 근거 성분이 들어 있고 가이드 본문은 처방약(rx)."""
        by = {r["id"]: r for r in self.rules}
        self.assertTrue({"antihypertensive", "antidepressant", "anticonvulsant"} <= set(by))
        self.assertTrue({"potassium", "coq10", "garlic", "omega-3", "arginine", "theanine", "rhodiola", "red-ginseng"} <= {c["id"] for c in by["antihypertensive"]["caution"]})
        self.assertTrue({"rhodiola", "garcinia", "theanine", "ginkgo"} <= {c["id"] for c in by["antidepressant"]["caution"]})
        self.assertTrue({"glutamine", "vitamin-b6", "ginkgo"} <= {c["id"] for c in by["anticonvulsant"]["caution"]})
        self.assertTrue({"vitamin-d", "folate", "biotin"} <= {g["id"] for g in by["anticonvulsant"]["good"]})
        guides = {g["id"]: g for g in B.read_json(B.DATA_DIR / "drug-guides.json")["items"]}
        for rid in ("antihypertensive", "antidepressant", "anticonvulsant"):
            self.assertTrue(guides[rid].get("rx") and len(guides[rid]["drugs"]) >= 3 and len(guides[rid]["faq"]) >= 3, rid)
        hit = B.drug_rule_hits(by["antihypertensive"], {"name": "로제핀정", "ingrEn": ["Amlodipine Besylate", "Rosuvastatin Calcium", "Ezetimibe"]})
        self.assertTrue(hit)   # 암로디핀 복합제(허가 목록)도 혈압약 규칙에 걸린다
        self.assertFalse(B.drug_rule_hits(by["anticonvulsant"], {"name": "타이레놀정", "ingrEn": ["Acetaminophen"]}))
        self.assertTrue(B.drug_rule_hits(by["anticonvulsant"], {"name": "오르필서방정", "ingrEn": ["Sodium Valproate"]}))
        # 2차(10-22): 당뇨약·수면제·탈모약·통풍약
        self.assertTrue({"antidiabetic", "sleep-aid", "hair-loss", "gout"} <= set(by))
        self.assertTrue({"banaba", "bitter-melon", "chromium", "garcinia", "red-ginseng", "niacin"} <= {c["id"] for c in by["antidiabetic"]["caution"]})
        self.assertTrue({"theanine", "lactium", "ecklonia"} <= {c["id"] for c in by["sleep-aid"]["caution"]} and by["sleep-aid"].get("oralOnly"))
        self.assertIn("saw-palmetto", {c["id"] for c in by["hair-loss"]["caution"]})
        self.assertTrue({"niacin", "molybdenum"} <= {c["id"] for c in by["gout"]["caution"]})
        self.assertTrue(B.drug_rule_hits(by["sleep-aid"], {"name": "드림굿연질캡슐", "ingrEn": ["Diphenhydramine HCl"], "usage": "취침 전 복용"}))
        self.assertFalse(B.drug_rule_hits(by["sleep-aid"], {"name": "레스타민코와파우더크림", "ingrEn": ["Diphenhydramine HCl"], "usage": "환부에 바릅니다"}))   # 외용은 제외
        self.assertFalse(B.drug_rule_hits(by["hair-loss"], {"name": "동성미녹시딜액3%", "ingrEn": ["Minoxidil"]}))   # 외용 미녹시딜은 탈모약 규칙 밖
        self.assertTrue(B.drug_rule_hits(by["antidiabetic"], {"name": "자누메트정", "ingrEn": ["Sitagliptin", "Metformin HCl"]}) and B.drug_rule_hits(by["metformin"], {"name": "자누메트정", "ingrEn": ["Sitagliptin", "Metformin HCl"]}))
        # 3차(10-22): 일반의약품 빈틈 — 칼슘제·철분제·정장제 + 비타민제 분류명·주의 성분
        self.assertTrue({"calcium-drug", "iron-drug", "probiotic-drug"} <= set(by))
        self.assertTrue({"calcium", "iron", "zinc", "magnesium", "psyllium"} <= {c["id"] for c in by["calcium-drug"]["caution"]} and {"vitamin-d", "vitamin-k"} <= {g["id"] for g in by["calcium-drug"]["good"]})
        self.assertTrue({"iron", "calcium", "zinc", "green-tea-extract", "psyllium", "chitosan", "multivitamin"} <= {c["id"] for c in by["iron-drug"]["caution"]} and {"vitamin-c", "folate", "vitamin-b12"} <= {g["id"] for g in by["iron-drug"]["good"]})
        self.assertTrue({"probiotics"} == {c["id"] for c in by["probiotic-drug"]["caution"]} and {"fos", "psyllium"} <= {g["id"] for g in by["probiotic-drug"]["good"]})
        self.assertTrue({"multivitamin", "vitamin-b-complex", "vitamin-b6", "vitamin-a", "vitamin-d", "vitamin-e"} <= {c["id"] for c in by["vitamin-drug"]["caution"]})
        self.assertTrue(B.drug_rule_hits(by["calcium-drug"], {"name": "디카맥스디플러스정", "cls": "칼슘제", "ingrEn": ["Calcium Carbonate Granules 95%", "Cholecalciferol Concentrate Granules"]}))
        self.assertTrue(B.drug_rule_hits(by["calcium-drug"], {"name": "시트큐정", "cls": "기타의 비타민제", "ingrEn": ["Calcium Citrate Hydrate", "Cholecalciferol Concentrate Powder", "Folic Acid"]}))
        self.assertFalse(B.drug_rule_hits(by["calcium-drug"], {"name": "개비스콘더블액션현탁액", "cls": "소화성궤양용제", "ingrEn": ["Calcium Carbonate", "Sodium Alginate", "Sodium Bicarbonate"]}))   # 제산 용도 탄산칼슘은 칼슘제 규칙 밖
        self.assertFalse(B.drug_rule_hits(by["calcium-drug"], {"name": "임팩타민파워에이플러스정", "cls": "기타의 비타민제", "ingrEn": ["Anhydrous Dibasic Calcium Phosphate", "Benfotiamine"]}))   # 부형제성 인산칼슘도 제외
        self.assertTrue(B.drug_rule_hits(by["iron-drug"], {"name": "훼로바-유서방정(건조황산제일철)", "cls": "무기질제제", "ingrEn": ["Dried Ferrous Sulfate"]}))
        self.assertTrue(B.drug_rule_hits(by["iron-drug"], {"name": "훼럼포유연질캡슐", "cls": "무기질제제", "ingrEn": ["Ferric Hydroxide Polymaltose Complex", "Folic Acid"]}))
        self.assertFalse(B.drug_rule_hits(by["iron-drug"], {"name": "알닥톤필름코팅정", "cls": "이뇨제", "ingrEn": ["Spironolactone"]}))   # 'iron' 부분 문자열 오탐 방지
        self.assertTrue(B.drug_rule_hits(by["probiotic-drug"], {"name": "메디락에스장용캡슐", "cls": "정장제", "ingrEn": ["Bacillus Subtilis", "Enterococcus Faecium Culture"]}))
        self.assertTrue(B.drug_rule_hits(by["probiotic-drug"], {"name": "비오플250캡슐", "cls": "정장제", "ingrEn": ["Saccharomyces Boulardii"]}))
        self.assertFalse(B.drug_rule_hits(by["probiotic-drug"], {"name": "지엘로페라미드염산염캡슐", "cls": "정장제", "ingrEn": ["Loperamide Hydrochloride"]}))   # 비생균 정장제는 제외
        for cls in ("비타민 B제(비타민 B1을 제외)", "비타민 A 및 D제", "비타민 E 및 K제", "비타민 B1제", "비타민 C 및 P제", "저함량 비타민 및 미네랄 제제", "혼합비타민제(비타민AD 혼합제제를 제외)"):
            self.assertTrue(B.drug_rule_hits(by["vitamin-drug"], {"name": "임팩타민정", "cls": cls, "ingrEn": ["Calcium Pantothenate"]}), cls)
        guides = {g["id"]: g for g in B.read_json(B.DATA_DIR / "drug-guides.json")["items"]}
        for rid in ("calcium-drug", "iron-drug", "probiotic-drug"):
            self.assertTrue(not guides[rid].get("rx") and len(guides[rid]["drugs"]) >= 3 and len(guides[rid]["faq"]) >= 3, rid)

    def test_validate_real_data_and_rejects_bad(self):
        import copy
        B.validate_drug_guides(self.data, self.rules, set(self.core["by_id"]), self.slugs)
        bad = copy.deepcopy(self.data); bad["items"][0]["id"] = "no-such-rule"
        with self.assertRaises(SystemExit):
            B.validate_drug_guides(bad, self.rules, set(self.core["by_id"]), self.slugs)
        bad = copy.deepcopy(self.data); bad["items"].pop()   # 규칙에 본문이 없으면 실패
        with self.assertRaises(SystemExit):
            B.validate_drug_guides(bad, self.rules, set(self.core["by_id"]), self.slugs)
        bad = copy.deepcopy(self.data); bad["items"][0]["related"] = ["no-such-guide"]
        with self.assertRaises(SystemExit):
            B.validate_drug_guides(bad, self.rules, set(self.core["by_id"]), self.slugs)

    def test_brand_keywords_ignore_parenthetical_ingredients(self):
        """브랜드 키워드는 괄호 안 성분 표기(아토르바스타틴칼슘…)에 걸리지 않고, 리피토 같은 브랜드명은 잡힌다."""
        bp = B.load_brand_priority()
        self.assertEqual(bp.keyword_weight("휴니즈아토르바스타틴칼슘정5밀리그램(아토르바스타틴칼슘삼수화물)"), 0)
        self.assertEqual(bp.keyword_weight("제피토정10/5밀리그램(에제티미브,아토르바스타틴)"), 0)
        self.assertGreaterEqual(bp.keyword_weight("리피토정10밀리그램(아토르바스타틴칼슘삼수화물)"), 2)
        self.assertGreaterEqual(bp.weight("크레스토정10밀리그램(로수바스타틴칼슘)", "한국아스트라제네카(주)"), 2)

    def test_rx_guide_lists_permit_only_drugs(self):
        """fetch_drugs.py 가 더하는 허가정보 전용 레코드(source mfds-permit, 본문 없음)가 처방약 가이드의 '이 분류의 약' 목록에 실린다."""
        fake = [{"id": "rx1", "name": "리피토정10밀리그램", "company": "비아트리스코리아", "otc": "전문의약품", "cls": "동맥경화용제", "ingr": ["아토르바스타틴칼슘삼수화물"], "ingrEn": ["Atorvastatin Calcium Trihydrate"], "ingredients": [], "usage": "", "source": "mfds-permit"},
                {"id": "rx2", "name": "아토르바정20밀리그램", "company": "유한양행", "otc": "전문의약품", "cls": "동맥경화용제", "ingr": ["아토르바스타틴칼슘삼수화물"], "ingrEn": ["Atorvastatin Calcium Trihydrate"], "ingredients": [], "usage": "", "source": "mfds-permit"}]
        base = [d for d in self.drugs if d.get("source") != "mfds-permit"]   # 실제 수집된 처방약은 빼고 가짜 두 건만으로 본다
        model = B.drug_guide_model(self.data, self.rules, self.core, base + fake, self.guides["items"], weight=lambda n, c: 3 if "리피토" in n else 0)
        e = next(x for x in model["items"] if x["dg"]["id"] == "statin")
        self.assertEqual(e["drugs"]["total"], 2)
        self.assertEqual(e["drugs"]["top"][0]["id"], "rx1")
        self.assertIn("rx2", [d["id"] for d in e["drugs"]["top"]])
        html = B.render_drug_guide(e, self.core, self.cfg, self.guides["_meta"]["types"], "2026-10-23")
        self.assertIn('href="../drug.html?id=rx1"', html)
        self.assertIn("대표 제품", html)
        self.assertIn("전문의약품</span>", html)
        self.assertNotIn("아직 수집되지 않았습니다", html)
        hub = B.render_drug_guides_hub(model, self.data, self.core, self.cfg)
        self.assertIn("허가정보", hub)

    def test_external_regex_matches_data_js(self):
        js = (B.ROOT / "assets/js/data.js").read_text(encoding="utf-8")
        m = re.search(r"var external = /(.+?)/\.test\(name\)", js)
        self.assertIsNotNone(m, "data.js drugPairingFor 의 external 정규식을 찾지 못함")
        self.assertEqual(m.group(1), B.DRUG_EXTERNAL_RE.pattern)
        self.assertIn("바릅니다", js)
        self.assertTrue(B.drug_is_external("두피나액", ""))
        self.assertTrue(B.drug_is_external("무슨정", "1일 2회 환부에 바릅니다"))
        self.assertFalse(B.drug_is_external("타이레놀정", "1일 3회 복용"))

    def test_rule_hits_like_data_js(self):
        nsaid, steroid, antacid = self.by_rule["nsaid"], self.by_rule["steroid-oral"], self.by_rule["antacid"]
        self.assertTrue(B.drug_rule_hits(nsaid, {"name": "스피딕400연질캡슐(이부프로펜)", "ingrEn": ["Ibuprofen"], "cls": "해열.진통.소염제"}))
        self.assertFalse(B.drug_rule_hits(nsaid, {"name": "케토톱플라스타", "ingrEn": ["Ketoprofen"], "cls": ""}))   # oralOnly: 외용제 제외
        self.assertFalse(B.drug_rule_hits(steroid, {"name": "두피나액", "ingrEn": ["Prednisolone Valeroacetate"], "usage": "환부에 바릅니다"}))
        self.assertTrue(B.drug_rule_hits(antacid, {"name": "아무개정", "ingrEn": [], "cls": "제산제"}))   # 분류 일치
        self.assertFalse(B.drug_rule_hits(antacid, {"name": "아무개정", "ingrEn": ["Acetaminophen"], "cls": "해열.진통.소염제"}))

    def test_model_covers_every_rule(self):
        self.assertEqual({e["dg"]["id"] for e in self.model["items"]}, {r["id"] for r in self.rules})
        for e in self.model["items"]:
            for x in e["good"] + e["caution"]:
                self.assertTrue(x["name"] and x["why"], e["dg"]["id"])
            self.assertLessEqual(len(e["drugs"]["top"]), B.DRUG_GUIDE_TOP)
        self.assertIn("thyroid", [d["id"] for d in self.model["by_ingredient"]["calcium"]])
        if self.drugs:   # 의약품 수집분이 있을 때만: 일반의약품 분류는 e약은요에서, 처방약 분류는 허가 목록 수집분(mfds-permit)이 있을 때만 잡힌다
            nsaid = next(e for e in self.model["items"] if e["dg"]["id"] == "nsaid")
            statin = next(e for e in self.model["items"] if e["dg"]["id"] == "statin")
            self.assertGreater(nsaid["drugs"]["total"], 0)
            if any(d.get("source") == "mfds-permit" for d in self.drugs):
                self.assertGreater(statin["drugs"]["total"], 0)
                self.assertTrue(all(d["otc"] == "전문의약품" for d in statin["drugs"]["top"]))
            else:
                self.assertEqual(statin["drugs"]["total"], 0)

    def test_render_page_and_hub(self):
        types = self.guides["_meta"]["types"]
        udca = next(e for e in self.model["items"] if e["dg"]["id"] == "udca")
        html = B.render_drug_guide(udca, self.core, self.cfg, types, "2026-10-22")
        self.assertIn('rel="canonical" href="https://example.test/drug-guide/udca"', html)
        for sec in ("summary", "good", "howto", "drugs", "faq"):
            self.assertIn(f'id="{sec}"', html)
        self.assertEqual(html.count('data-my-add="'), len(udca["good"]))
        if udca["drugs"]["total"]:
            self.assertIn("../drug.html?id=", html)
        statin = next(e for e in self.model["items"] if e["dg"]["id"] == "statin")
        html2 = B.render_drug_guide(statin, self.core, self.cfg, types, "2026-10-22")
        if statin["drugs"]["total"]:   # 처방약 허가 목록이 수집된 뒤에는 대표 제품이 실리고, 전이면 성분명 안내만
            self.assertIn("../drug.html?id=", html2); self.assertIn("대표 제품", html2)
        else:
            self.assertNotIn("../drug.html?id=", html2)
        self.assertIn("처방전·약봉투", html2)
        self.assertIn('href="../i/red-yeast-rice.html"', html2)
        acet = next(e for e in self.model["items"] if e["dg"]["id"] == "acetaminophen")
        html3 = B.render_drug_guide(acet, self.core, self.cfg, types, "2026-10-22")
        self.assertIn("정리된 것은 없습니다", html3)
        hub = B.render_drug_guides_hub(self.model, self.data, self.core, self.cfg)
        for e in self.model["items"]:
            self.assertIn(f'href="drug-guide/{e["dg"]["id"]}.html"', hub)
        self.assertIn('id="gaps"', hub)
        self.assertIn("drug-guides.html", B.STATIC_PAGES)


class AppSafeAreaTests(unittest.TestCase):
    """앱(iOS 웹뷰)은 상태바 아래까지 그리므로 헤더 위에 안전 영역 여백이 필요하고, env() 가 0 이 아니려면 viewport-fit=cover 가 있어야 한다"""

    def test_every_viewport_meta_has_viewport_fit_cover(self):
        src = (B.ROOT / "scripts/build_site.py").read_text(encoding="utf-8")
        metas = [line for line in src.splitlines() if 'name="viewport"' in line]
        self.assertTrue(metas)
        for line in metas:
            self.assertIn("viewport-fit=cover", line)
        for page in sorted(B.ROOT.glob("*.html")):   # 직접 만든 정적 페이지(궁합 체크·약관·오프라인 안내 등)도 모두 — 빠지면 그 페이지에서만 상태바가 헤더를 덮는다
            html = page.read_text(encoding="utf-8")
            if 'name="viewport"' in html:
                self.assertIn("viewport-fit=cover", html, page.name)

    def test_app_mode_pads_header_by_safe_area(self):
        css = (B.ROOT / "assets/css/style.css").read_text(encoding="utf-8")
        self.assertIn("html.is-app #site-header", css)
        self.assertIn("env(safe-area-inset-top", css)
        self.assertIn("html.is-app { --header-h: calc(68px + env(safe-area-inset-top", css)


class GlossaryTests(unittest.TestCase):
    """용어 사전(glossary.html · term/<slug>.html) — 데이터 검증·본문 자동 링크·렌더 (tests/terms.test.mjs 와 같은 링크 사례)."""

    @classmethod
    def setUpClass(cls):
        cls.data = B.read_json(B.DATA_DIR / "glossary.json")
        ingredients = B.read_json(B.DATA_DIR / "ingredients.json")
        interactions = B.read_json(B.DATA_DIR / "interactions.json")
        guides = B.read_json(B.DATA_DIR / "guides.json")
        cls.guides = guides
        cls.core = {"categories": ingredients["_meta"]["categories"], "by_id": {i["id"]: i for i in ingredients["items"]}, "guides": guides["items"], "pairs": interactions["pairs"], "types": interactions["_meta"]["types"], "updated_at": "2026-10-22"}
        cls.slugs = {g["slug"] for g in guides["items"]}
        cls.model = B.glossary_model(cls.data, cls.core, guides["items"])
        cls.core["glossary"] = cls.model
        cls.core["term_linker"] = B.TermLinker(cls.data["items"])
        cls.cfg = {"name": "테스트", "url": "https://example.test"}
        cls.items = [
            {"slug": "heme-iron", "aliases": ["헴철"], "short": "동물성 철"},
            {"slug": "non-heme-iron", "aliases": ["비헴철"], "short": "식물성 철"},
            {"slug": "rtg", "aliases": ["rTG", "r-TG"], "short": '재에스테르화 "TG"'},
            {"slug": "ul", "aliases": ["상한섭취량", "UL"], "short": "상한"},
            {"slug": "cfu", "aliases": ["CFU", "보장균수"], "short": "균 수"},
        ]

    def test_validate_real_data_and_rejects_bad(self):
        import copy
        B.validate_glossary(self.data, set(self.core["by_id"]), self.slugs)
        self.assertGreaterEqual(len(self.data["items"]), 60)
        bad = copy.deepcopy(self.data); bad["items"][1]["aliases"].append(bad["items"][0]["aliases"][0])   # 다른 용어와 별칭 중복
        with self.assertRaises(SystemExit):
            B.validate_glossary(bad, set(self.core["by_id"]), self.slugs)
        bad = copy.deepcopy(self.data); bad["items"][0]["related"] = ["no-such-term"]
        with self.assertRaises(SystemExit):
            B.validate_glossary(bad, set(self.core["by_id"]), self.slugs)
        bad = copy.deepcopy(self.data); bad["items"][0]["ingredients"] = ["no-such-ingredient"]
        with self.assertRaises(SystemExit):
            B.validate_glossary(bad, set(self.core["by_id"]), self.slugs)

    def test_linker_first_occurrence_and_boundaries(self):
        T = B.TermLinker(self.items)
        out = T.link(B.esc("비헴철은 헴철보다 흡수가 낮고 rTG 오메가3 는 xrTGx 가 아니다. 헴철을 다시."), "../", {})
        self.assertRegex(out, r'<a class="term-link" href="\.\./term/non-heme-iron\.html" title="식물성 철">비헴철</a>은')
        self.assertRegex(out, r'href="\.\./term/heme-iron\.html"[^>]*>헴철</a>보다')
        self.assertRegex(out, r'href="\.\./term/rtg\.html" title="재에스테르화 &quot;TG&quot;">rTG</a> 오메가3')
        self.assertIn("xrTGx 가 아니다", out)
        self.assertEqual(out.count("term/heme-iron.html"), 1)
        T2 = B.TermLinker(self.items + [{"slug": "iu", "aliases": ["IU"], "short": "국제단위"}])
        out2 = T2.link("100억 cfu 와 4000IU, 그리고 IU 단위", "", {})
        self.assertRegex(out2, r'href="term/cfu\.html"[^>]*>cfu</a>')
        self.assertIn("4000IU,", out2)
        self.assertRegex(out2, r'그리고 <a class="term-link" href="term/iu\.html"[^>]*>IU</a> 단위')

    def test_linker_exclude_state_and_max(self):
        T = B.TermLinker(self.items)
        st = {"used": set(), "exclude": {"heme-iron"}}
        a = T.link("헴철과 비헴철", "../", st)
        b = T.link("비헴철 다시, 상한섭취량", "../", st)
        self.assertTrue("term/heme-iron.html" not in a and "term/non-heme-iron.html" in a)
        self.assertTrue("term/non-heme-iron.html" not in b and "term/ul.html" in b)
        many = [{"slug": f"t{i}", "aliases": ["용어" + chr(0xAC00 + i)], "short": ""} for i in range(20)]
        out = B.TermLinker(many).link(" ".join(m["aliases"][0] for m in many), "", {})
        self.assertEqual(out.count("term-link"), B.TERM_LINK_MAX)
        self.assertEqual(B.TermLinker(self.items).link("&lt;b&gt;굵게&lt;/b&gt;", "", {}), "&lt;b&gt;굵게&lt;/b&gt;")
        self.assertEqual(B.TermLinker([]).link("헴철", "", {}), "헴철")
        js = (B.ROOT / "assets/js/terms.js").read_text(encoding="utf-8")
        self.assertIn(f"var MAX = {B.TERM_LINK_MAX};", js)

    def test_term_initial(self):
        self.assertEqual(B.term_initial("생체이용률"), "ㅅ")
        self.assertEqual(B.term_initial("rTG(재에스테르화 중성지방)"), "A")
        self.assertEqual(B.term_initial("25(OH)D"), "A")
        self.assertEqual(B.term_initial("킬레이트"), "ㅋ")

    def test_render_term_hub_and_autolink_in_pages(self):
        types = self.guides["_meta"]["types"]
        e = self.model["by_slug"]["heme-iron"]
        html = B.render_term(e, self.model, self.core, self.cfg, types, "2026-10-22")
        self.assertIn('rel="canonical" href="https://example.test/term/heme-iron"', html)
        self.assertNotIn('href="../term/heme-iron.html"', html)   # 자기 자신은 링크하지 않음
        self.assertIn('href="../term/non-heme-iron.html"', html)
        self.assertIn("DefinedTerm", html)
        hub = B.render_glossary_hub(self.model, self.cfg)
        for x in self.model["items"]:
            self.assertIn(f'href="term/{x["t"]["slug"]}.html"', hub)
        self.assertIn('id="term-filter"', hub)
        self.assertIn("glossary.html", B.STATIC_PAGES)
        guides = {"_meta": self.guides["_meta"], "items": self.guides["items"], "by_id": {g["id"]: g for g in self.guides["items"]}}
        gd = next(g for g in self.guides["items"] if g["slug"] == "omega3-guide")
        ghtml = B.render_guide(gd, guides, self.core, self.cfg)
        self.assertIn('class="term-link"', ghtml)
        self.assertIn('href="../term/rtg.html"', ghtml)
        self.assertLessEqual(ghtml.count('class="term-link"'), B.TERM_LINK_MAX)
        it = self.core["by_id"]["iron"]
        ihtml = B.render_page(it, self.core, self.cfg)
        self.assertIn("assets/js/terms.js", ihtml)


class TipsTests(unittest.TestCase):
    """오늘의 한 줄 일반 팁(data/tips.json) 검증 — 금칙어·길이·개수."""

    def test_validate_tips_rejects_forbidden_words_and_accepts_data_file(self):
        import json
        with self.assertRaises(ValueError):
            B.validate_tips({"items": [{"text": "이 성분은 질병을 치료합니다", "source": "x"}]})
        with self.assertRaises(ValueError):
            B.validate_tips({"items": []})
        data = json.loads((B.ROOT / "data" / "tips.json").read_text(encoding="utf-8"))
        B.validate_tips(data)
        self.assertGreaterEqual(len(data["items"]), 10)
