#!/usr/bin/env python3
"""
정적 페이지 빌드:
  1) data/ingredients.json, interactions.json 검증
  2) 성분별 정적 상세 페이지 i/<id>.html 생성 (검색엔진용 본문 + 메타 + JSON-LD 포함)
  3) sitemap.xml, data/meta.json 생성

사용법: python scripts/build_site.py
환경변수: SITE_URL (선택, 기본값은 assets/js/config.js 의 url)
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, ROOT, env, log, now_iso, read_json, write_json  # noqa: E402

OUT_DIR = ROOT / "i"
STATIC_PAGES = ["index.html", "ingredients.html", "compatibility.html", "products.html", "news.html", "materials.html", "about.html"]


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def site_config() -> dict:
    """assets/js/config.js 에서 name/url/description 을 읽어옵니다 (정규식 추출)."""
    src = (ROOT / "assets/js/config.js").read_text(encoding="utf-8")
    def grab(key: str, default: str = "") -> str:
        m = re.search(rf'{key}:\s*"([^"]*)"', src)
        return m.group(1) if m else default
    return {"name": grab("name", "서플노트"), "url": (env("SITE_URL") or grab("url")).rstrip("/"), "description": grab("description")}


def validate(ingredients: dict, interactions: dict) -> None:
    ids = {i["id"] for i in ingredients["items"]}
    required = ["id", "name", "en", "category", "summary", "benefits", "dosage", "timing", "cautions", "shopQuery", "tags"]
    for it in ingredients["items"]:
        for k in required:
            if k not in it:
                raise SystemExit(f"[검증 실패] 성분 {it.get('id')} 에 '{k}' 누락")
        if it["category"] not in ingredients["_meta"]["categories"]:
            raise SystemExit(f"[검증 실패] 성분 {it['id']} 의 category '{it['category']}' 미정의")
        if it["timing"].get("slot") not in ingredients["_meta"]["slots"]:
            raise SystemExit(f"[검증 실패] 성분 {it['id']} 의 timing.slot '{it['timing'].get('slot')}' 미정의")
    seen = set()
    for p in interactions["pairs"]:
        a, b = p["pair"]
        if a not in ids or b not in ids:
            raise SystemExit(f"[검증 실패] 궁합 쌍 {p['pair']} 에 알 수 없는 성분 ID")
        if a == b:
            raise SystemExit(f"[검증 실패] 궁합 쌍 {p['pair']} 는 동일 성분")
        key = tuple(sorted(p["pair"]))
        if key in seen:
            raise SystemExit(f"[검증 실패] 궁합 쌍 중복: {key}")
        seen.add(key)
        if p["type"] not in interactions["_meta"]["types"]:
            raise SystemExit(f"[검증 실패] 궁합 type '{p['type']}' 미정의 ({p['pair']})")
    log.info("데이터 검증 통과: 성분 %d · 궁합 %d", len(ids), len(interactions["pairs"]))


def ul(items: list[str], cls: str) -> str:
    if not items:
        return '<p class="text-sm text-ink-400">해당 없음</p>'
    return f'<ul class="{cls} text-[15px] text-ink-700">' + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>"


def render_page(it: dict, core: dict, cfg: dict) -> str:
    cats = core["categories"]
    cat = cats.get(it["category"], {})
    title = f"{it['name']} 효능·권장량·궁합 | {cfg['name']}"
    desc = it["summary"][:150]
    url = f"{cfg['url']}/i/{it['id']}.html"
    by_id = core["by_id"]

    # 궁합 목록 (정적)
    rel = []
    for p in core["pairs"]:
        if it["id"] in p["pair"]:
            other = by_id.get(p["pair"][1] if p["pair"][0] == it["id"] else p["pair"][0])
            if other:
                rel.append((p, other))
    order = {"avoid": 0, "caution": 1, "synergy": 2, "neutral": 3}
    rel.sort(key=lambda x: (order.get(x[0]["type"], 9), -(x[0].get("level") or 0)))
    types = core["types"]
    rel_html = ""
    for t in ("avoid", "caution", "synergy", "neutral"):
        group = [r for r in rel if r[0]["type"] == t]
        if not group:
            continue
        rel_html += f'<h3 class="mt-4 text-sm font-bold">{esc(types[t]["label"])}</h3><ul class="list-dot text-sm text-ink-700">'
        for p, other in group:
            rel_html += f'<li><a class="font-semibold text-brand-700" href="{esc(other["id"])}.html">{esc(other["name"])}</a> — {esc(p["title"])}' + (f' ({p["separateHours"]}시간 이상 간격)' if p.get("separateHours") else "") + "</li>"
        rel_html += "</ul>"

    # 식약처 인정 원료 (수집된 경우에만)
    mats = (read_json(DATA_DIR / "materials" / f"{it['id']}.json", {}) or {}).get("items", [])
    mat_html = ""
    if mats:
        mat_html = '<h2 class="mt-6 text-lg font-extrabold">식약처 인정 원료 데이터</h2><ul class="list-dot text-sm text-ink-700">' + "".join(
            f'<li><strong>{esc(g.get("name"))}</strong> ({esc(g.get("type", ""))}) — {esc(g.get("function", ""))}' + (f' · 1일 섭취량 {esc(g["intake"])}' if g.get("intake") else "") + "</li>" for g in mats[:8]
        ) + "</ul>"

    faq_html = "".join(f'<details class="border-b border-ink-100 py-3"><summary class="cursor-pointer font-bold text-ink-900">Q. {esc(f["q"])}</summary><p class="mt-2 text-sm text-ink-600">{esc(f["a"])}</p></details>' for f in it.get("faq", []))

    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "성분 사전", "item": f"{cfg['url']}/ingredients.html"},
            {"@type": "ListItem", "position": 3, "name": it["name"], "item": url}]},
        {"@type": "Article", "headline": f"{it['name']} 효능·권장량·궁합", "description": desc, "mainEntityOfPage": url,
         "author": {"@type": "Organization", "name": cfg["name"]}, "publisher": {"@type": "Organization", "name": cfg["name"]}, "dateModified": core.get("updated_at") or now_iso()[:10]},
    ]}
    if it.get("faq"):
        ld["@graph"].append({"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in it["faq"]]})

    ssr = f'''
    <div id="ssr">
      <nav class="text-xs text-ink-500" aria-label="경로"><a href="../index.html">홈</a> › <a href="../ingredients.html">성분 사전</a> › <span>{esc(it["name"])}</span></nav>
      <h1 class="mt-4 text-3xl font-extrabold text-ink-900">{esc(it["name"])} <span class="text-base font-medium text-ink-400">{esc(it["en"])}</span></h1>
      <p class="mt-3 text-[15px] text-ink-700">{esc(it["summary"])}</p>
      <h2 class="mt-8 text-lg font-extrabold">식약처 인정 기능성</h2><p class="mt-2 text-sm text-ink-700">{esc(it.get("mfdsFunction") or "고시형 기능성 원료 아님")}</p>
      <h2 class="mt-6 text-lg font-extrabold">기대 효과</h2>{ul(it.get("benefits", []), "list-check")}
      <h2 class="mt-6 text-lg font-extrabold">권장 섭취량</h2><p class="text-sm text-ink-700">하루 권장: {esc(it["dosage"].get("daily"))} · 상한: {esc(it["dosage"].get("upper"))}</p><p class="text-sm text-ink-600">{esc(it["dosage"].get("note", ""))}</p>
      <h2 class="mt-6 text-lg font-extrabold">섭취 시간</h2><p class="text-sm text-ink-700">{esc(it["timing"].get("label"))} — {esc(it["timing"].get("note", ""))}</p>
      <h2 class="mt-6 text-lg font-extrabold">이런 분께 추천</h2>{ul(it.get("whoFor", []), "list-dot")}
      <h2 class="mt-6 text-lg font-extrabold">주의사항</h2>{ul(it.get("cautions", []), "list-warn")}{('<h3 class="mt-3 text-sm font-bold text-rose-700">약과 함께 먹을 때</h3>' + ul(it.get("drugCautions", []), "list-warn")) if it.get("drugCautions") else ""}
      {mat_html}
      <h2 class="mt-6 text-lg font-extrabold">{esc(it["name"])} 궁합</h2>{rel_html or '<p class="text-sm text-ink-400">등록된 궁합 정보가 없습니다.</p>'}
      {('<h2 class="mt-6 text-lg font-extrabold">자주 묻는 질문</h2>' + faq_html) if faq_html else ""}
      <p class="mt-8 text-xs text-ink-400">이 정보는 일반적인 건강 정보이며 의학적 조언을 대신하지 않습니다.</p>
    </div>'''

    return f'''<!DOCTYPE html>
<html lang="ko" data-root="../">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <meta name="keywords" content="{esc(", ".join([it["name"]] + it.get("aliases", [])[:4] + it.get("tags", [])[:4] + [it["name"] + " 효능", it["name"] + " 궁합", it["name"] + " 복용법"]))}">
  <meta name="robots" content="index,follow">
  <link rel="canonical" href="{esc(url)}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="{esc(cfg["name"])}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:url" content="{esc(url)}">
  <meta property="og:image" content="{esc(cfg["url"])}/assets/images/og-default.svg">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="../assets/images/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="../assets/js/tailwind.config.js"></script>
  <link rel="stylesheet" href="../assets/css/style.css">
  <script src="https://unpkg.com/lucide@0.460.0/dist/umd/lucide.min.js" defer></script>
  <script src="../assets/js/config.js"></script>
  <script src="../assets/js/data.js"></script>
  <script src="../assets/js/affiliate.js"></script>
  <script src="../assets/js/layout.js"></script>
  <script>window.__INGREDIENT_ID = {json.dumps(it["id"])};</script>
  <script src="../assets/js/pages/ingredient.js"></script>
  <script type="application/ld+json" id="ld-ingredient">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body data-page="ingredients" data-path="i/{esc(it["id"])}.html" class="min-h-screen antialiased">
  <a href="#main" class="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:font-bold focus:text-brand-700">본문으로 건너뛰기</a>
  <div id="site-header"></div>
  <main id="main" class="mx-auto max-w-7xl px-4 py-8 sm:px-6">
    <div id="ingredient-app" class="hidden">
      <div id="ingredient-hero"></div>
      <div id="ingredient-quick" class="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"></div>
      <div class="mt-8 grid gap-6 lg:grid-cols-12">
        <div id="ingredient-main" class="space-y-6 lg:col-span-8"></div>
        <aside id="ingredient-side" class="lg:col-span-4"></aside>
      </div>
    </div>{ssr}
  </main>
  <div id="site-footer"></div>
</body>
</html>
'''


def build_sitemap(ingredients: list[dict], cfg: dict, data_date: str) -> None:
    today = now_iso()[:10]
    dynamic = ("index.html", "news.html", "products.html")
    urls = [(f"{cfg['url']}/{p}", "daily" if p in dynamic else "monthly", "1.0" if p == "index.html" else "0.8", today if p in dynamic else data_date) for p in STATIC_PAGES]
    urls += [(f"{cfg['url']}/i/{it['id']}.html", "monthly", "0.7", data_date) for it in ingredients]
    body = "".join(f"  <url><loc>{esc(u)}</loc><lastmod>{d}</lastmod><changefreq>{c}</changefreq><priority>{p}</priority></url>\n" for u, c, p, d in urls)
    (ROOT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n", encoding="utf-8")
    log.info("sitemap.xml: %d URL", len(urls))


def main() -> int:
    cfg = site_config()
    ingredients = read_json(DATA_DIR / "ingredients.json")
    interactions = read_json(DATA_DIR / "interactions.json")
    if not ingredients or not interactions:
        raise SystemExit("data/ingredients.json 또는 interactions.json 을 읽을 수 없습니다.")
    validate(ingredients, interactions)
    data_date = ingredients["_meta"].get("updatedAt") or now_iso()[:10]
    core = {"categories": ingredients["_meta"]["categories"], "by_id": {i["id"]: i for i in ingredients["items"]},
            "pairs": interactions["pairs"], "types": interactions["_meta"]["types"], "updated_at": data_date}

    OUT_DIR.mkdir(exist_ok=True)
    wanted = set()
    for it in ingredients["items"]:
        path = OUT_DIR / f"{it['id']}.html"
        path.write_text(render_page(it, core, cfg), encoding="utf-8")
        wanted.add(path.name)
    for stale in OUT_DIR.glob("*.html"):
        if stale.name not in wanted:
            stale.unlink()
            log.info("삭제된 성분 페이지 정리: %s", stale.name)
    log.info("성분 페이지 %d개 생성 (i/)", len(wanted))

    build_sitemap(ingredients["items"], cfg, data_date)
    products = read_json(DATA_DIR / "products.json", {"_meta": {}, "items": []})
    news = read_json(DATA_DIR / "news.json", {"_meta": {}, "items": []})
    materials = read_json(DATA_DIR / "materials.json", {"_meta": {}, "items": []})
    write_json(DATA_DIR / "meta.json", {
        "builtAt": now_iso(),
        "ingredients": len(ingredients["items"]),
        "pairs": len(interactions["pairs"]),
        "products": {"source": products.get("_meta", {}).get("source", "sample"), "updatedAt": products.get("_meta", {}).get("updatedAt"), "total": len(products.get("items", []))},
        "news": {"source": news.get("_meta", {}).get("source", "sample"), "updatedAt": news.get("_meta", {}).get("updatedAt"), "total": len(news.get("items", []))},
        "materials": {"source": materials.get("_meta", {}).get("source", "sample"), "updatedAt": materials.get("_meta", {}).get("updatedAt"), "total": len(materials.get("items", [])), "matched": materials.get("_meta", {}).get("matched", 0),
                      "ingredients": sorted(f.stem for f in (DATA_DIR / "materials").glob("*.json"))},
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
