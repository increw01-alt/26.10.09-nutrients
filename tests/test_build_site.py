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

    def test_rx_guide_lists_permit_only_drugs(self):
        """fetch_drugs.py 가 더하는 허가정보 전용 레코드(source mfds-permit, 본문 없음)가 처방약 가이드의 '이 분류의 약' 목록에 실린다."""
        fake = [{"id": "rx1", "name": "리피토정10밀리그램", "company": "비아트리스코리아", "otc": "전문의약품", "cls": "동맥경화용제", "ingr": ["아토르바스타틴칼슘삼수화물"], "ingrEn": ["Atorvastatin Calcium Trihydrate"], "ingredients": [], "usage": "", "source": "mfds-permit"},
                {"id": "rx2", "name": "아토르바정20밀리그램", "company": "유한양행", "otc": "전문의약품", "cls": "동맥경화용제", "ingr": ["아토르바스타틴칼슘삼수화물"], "ingrEn": ["Atorvastatin Calcium Trihydrate"], "ingredients": [], "usage": "", "source": "mfds-permit"}]
        model = B.drug_guide_model(self.data, self.rules, self.core, self.drugs + fake, self.guides["items"], weight=lambda n, c: 3 if "리피토" in n else 0)
        e = next(x for x in model["items"] if x["dg"]["id"] == "statin")
        self.assertGreaterEqual(e["drugs"]["total"], 2)
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
        if self.drugs:   # 의약품 수집분이 있을 때만: 일반의약품 분류는 약이 잡히고 처방약 분류는 0건
            nsaid = next(e for e in self.model["items"] if e["dg"]["id"] == "nsaid")
            statin = next(e for e in self.model["items"] if e["dg"]["id"] == "statin")
            self.assertGreater(nsaid["drugs"]["total"], 0)
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
        for page in ("index.html", "my.html"):
            self.assertIn("viewport-fit=cover", (B.ROOT / page).read_text(encoding="utf-8"))

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
