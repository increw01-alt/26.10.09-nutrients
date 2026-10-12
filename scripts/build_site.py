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
GUIDE_DIR = ROOT / "guide"
STATIC_PAGES = ["index.html", "ingredients.html", "compatibility.html", "guides.html", "products.html", "news.html", "materials.html", "about.html"]


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def site_config() -> dict:
    """assets/js/config.js 에서 name/url/description 을 읽어옵니다 (정규식 추출)."""
    src = (ROOT / "assets/js/config.js").read_text(encoding="utf-8")
    def grab(key: str, default: str = "") -> str:
        m = re.search(rf'{key}:\s*"([^"]*)"', src)
        return m.group(1) if m else default
    return {"name": grab("name", "영양제.kr"), "url": (env("SITE_URL") or grab("url")).rstrip("/"), "description": grab("description"),
            "googleSiteVerification": grab("googleSiteVerification"), "naverSiteVerification": grab("naverSiteVerification")}


VERIFY_START, VERIFY_END = "<!-- site-verification:start", "<!-- site-verification:end -->"


ASSET_LINK_RE = re.compile(r'(?P<pre>(?:src|href)=")(?P<path>/?(?:\.\./|\./)*assets/(?:js|css)/[A-Za-z0-9_./-]+\.(?:js|css))(?:\?v=[0-9a-f]+)?(?P<post>")')


def stamp_assets() -> None:
    """모든 HTML 의 assets/js·css 링크에 내용 해시(?v=…)를 붙여, 배포 후 브라우저가 예전 캐시 대신 새 파일을 받게 합니다.
    (Cloudflare Pages + 휴대폰 브라우저에서 새 HTML 과 옛 JS/CSS 가 섞여 동작이 깨지는 문제 방지)"""
    import hashlib
    cache: dict[str, str] = {}

    def digest(path: Path) -> str:
        key = str(path)
        if key not in cache:
            cache[key] = hashlib.sha1(path.read_bytes()).hexdigest()[:8] if path.exists() else "0"
        return cache[key]

    files = sorted(ROOT.glob("*.html")) + sorted(OUT_DIR.glob("*.html")) + sorted((ROOT / "guide").glob("*.html"))
    changed = 0
    for html_path in files:
        src = html_path.read_text(encoding="utf-8")

        def repl(m: re.Match) -> str:
            rel = m.group("path")
            target = (ROOT / rel.lstrip("/")).resolve() if rel.startswith("/") else (html_path.parent / rel).resolve()
            return f'{m.group("pre")}{m.group("path")}?v={digest(target)}{m.group("post")}'

        out = ASSET_LINK_RE.sub(repl, src)
        if out != src:
            html_path.write_text(out, encoding="utf-8"); changed += 1
    log.info("자산 버전 스탬프: HTML %d개 갱신", changed)


def check_icons() -> None:
    """HTML·JS·데이터에서 쓰는 lucide 아이콘 이름이 assets/js/icons.js 번들에 모두 있는지 확인 (없으면 `npm run icons`)."""
    bundle = ROOT / "assets/js/icons.js"
    if not bundle.exists():
        log.warning("assets/js/icons.js 가 없습니다. `npm run icons` 로 생성하세요."); return
    have = set(re.findall(r'"([a-z0-9-]+)":\[\[', bundle.read_text(encoding="utf-8")))
    used: set[str] = set()
    srcs = list(ROOT.glob("*.html")) + list((ROOT / "assets/js").rglob("*.js")) + [ROOT / "scripts/build_site.py"]
    for f in srcs:
        if f.name == "icons.js":
            continue
        t = f.read_text(encoding="utf-8")
        used |= set(re.findall(r'data-lucide="([a-z0-9-]+)"', t)) | set(re.findall(r'icon:\s*"([a-z0-9-]+)"', t))
    for f in ("ingredients.json", "interactions.json", "guides.json"):
        used |= set(re.findall(r'"icon":\s*"([a-z0-9-]+)"', (DATA_DIR / f).read_text(encoding="utf-8")))
    missing = sorted(used - have)
    if missing:
        log.warning("아이콘 번들에 없는 이름 %d개 (표시되지 않음 → `npm run icons` 실행): %s", len(missing), ", ".join(missing))
    else:
        log.info("아이콘 번들 점검 OK (%d개 사용)", len(used))


def inject_verification(cfg: dict) -> None:
    """config.js 의 소유 확인 코드를 index.html <head> 의 마커 사이에 정적 메타태그로 넣습니다.
    (검색엔진 소유 확인 크롤러는 JS 를 실행하지 않으므로 원본 HTML 에 있어야 합니다.)"""
    path = ROOT / "index.html"
    html_src = path.read_text(encoding="utf-8")
    a, b = html_src.find(VERIFY_START), html_src.find(VERIFY_END)
    if a < 0 or b < 0 or b < a:
        log.warning("index.html 에 site-verification 마커가 없어 소유 확인 태그를 넣지 못했습니다.")
        return
    head_end = html_src.find("-->", a) + 3            # 시작 마커 주석의 끝
    tags = []
    if cfg.get("googleSiteVerification"):
        tags.append(f'  <meta name="google-site-verification" content="{esc(cfg["googleSiteVerification"])}">')
    if cfg.get("naverSiteVerification"):
        tags.append(f'  <meta name="naver-site-verification" content="{esc(cfg["naverSiteVerification"])}">')
    block = "\n" + "".join(t + "\n" for t in tags) + "  "   # 끝 마커의 들여쓰기 유지
    new_src = html_src[:head_end] + block + html_src[b:]
    if new_src != html_src:
        path.write_text(new_src, encoding="utf-8")
        log.info("index.html 소유 확인 메타태그 %d개 반영", len(tags))


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

    rel_guides = [g for g in core.get("guides", []) if any(x["id"] == it["id"] for x in g["ingredients"])]
    guides_html = ""
    if rel_guides:
        guides_html = '<h2 class="mt-6 text-lg font-extrabold">이 성분이 등장하는 가이드</h2><ul class="list-dot text-sm text-ink-700">' + "".join(f'<li><a class="font-semibold text-brand-700" href="../guide/{esc(g["slug"])}.html">{esc(g["h1"])}</a></li>' for g in rel_guides[:8]) + "</ul>"

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
      {guides_html}
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
  <link rel="stylesheet" href="../assets/css/style.css">
  <link rel="stylesheet" href="../assets/css/tailwind.css">
  <script src="../assets/js/icons.js" defer></script>
  <script src="../assets/js/config.js" defer></script>
  <script src="../assets/js/data.js" defer></script>
  <script src="../assets/js/affiliate.js" defer></script>
  <script src="../assets/js/layout.js" defer></script>
  <script>window.__INGREDIENT_ID = {json.dumps(it["id"])};</script>
  <script src="../assets/js/illus.js" defer></script>
  <script src="../assets/js/pages/ingredient.js" defer></script>
  <script type="application/ld+json" id="ld-ingredient">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body data-page="ingredients" data-path="i/{esc(it["id"])}.html" class="min-h-screen antialiased">
  <a href="#main" class="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:font-bold focus:text-brand-700">본문으로 건너뛰기</a>
  <div id="site-header"></div>
  <main id="main">
    <div id="ingredient-app" class="hidden">
      <div id="ingredient-hero" class="page-hero"></div>
      <div class="mx-auto max-w-7xl px-4 pb-8 sm:px-6">
      <div id="ingredient-quick"></div>
      <div class="mt-8 grid gap-6 lg:grid-cols-12">
        <div id="ingredient-main" class="space-y-6 lg:col-span-8"></div>
        <aside id="ingredient-side" class="lg:col-span-4"></aside>
      </div>
      </div>
    </div><div class="mx-auto max-w-7xl px-4 py-8 sm:px-6">{ssr}</div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
'''


def head_html(cfg: dict, *, title: str, desc: str, path: str, root: str, keywords: str = "", og_type: str = "article", extra_scripts: str = "", ld: dict | None = None) -> str:
    url = f"{cfg['url']}/{path}"
    return f"""<!DOCTYPE html>
<html lang="ko" data-root="{root}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  {('<meta name="keywords" content="' + esc(keywords) + '">') if keywords else ''}
  <meta name="robots" content="index,follow">
  <link rel="canonical" href="{esc(url)}">
  <meta property="og:type" content="{og_type}">
  <meta property="og:site_name" content="{esc(cfg['name'])}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:url" content="{esc(url)}">
  <meta property="og:image" content="{esc(cfg['url'])}/assets/images/og-default.svg">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="{root}assets/images/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
  <link rel="stylesheet" href="{root}assets/css/style.css">
  <link rel="stylesheet" href="{root}assets/css/tailwind.css">
  <script src="{root}assets/js/icons.js" defer></script>
  <script src="{root}assets/js/config.js" defer></script>
  <script src="{root}assets/js/data.js" defer></script>
  <script src="{root}assets/js/affiliate.js" defer></script>
  <script src="{root}assets/js/layout.js" defer></script>
  {extra_scripts}
  {('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + '</script>') if ld else ''}
</head>"""


SKIP_LINK = '<a href="#main" class="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:font-bold focus:text-brand-700">본문으로 건너뛰기</a>\n  <div id="site-header"></div>'
TYPE_STYLE = {"concern": "bg-brand-50 text-brand-700 ring-brand-200", "target": "bg-violet-50 text-violet-700 ring-violet-200", "howto": "bg-amber-50 text-amber-700 ring-amber-200"}


def cat_class(color: str) -> str:
    return {"amber": "bg-amber-50 text-amber-700 ring-amber-200", "sky": "bg-sky-50 text-sky-700 ring-sky-200", "blue": "bg-blue-50 text-blue-700 ring-blue-200",
            "lime": "bg-lime-50 text-lime-700 ring-lime-200", "emerald": "bg-emerald-50 text-emerald-700 ring-emerald-200", "violet": "bg-violet-50 text-violet-700 ring-violet-200",
            "orange": "bg-orange-50 text-orange-700 ring-orange-200", "pink": "bg-pink-50 text-pink-700 ring-pink-200"}.get(color, "bg-slate-100 text-slate-600 ring-slate-200")


def guide_card(gd: dict, types: dict, root: str) -> str:
    t = types.get(gd["type"], {})
    return (f'<a href="{root}guide/{esc(gd["slug"])}.html" class="card-hover flex gap-4 rounded-2xl border border-[#e3ebdc] bg-white p-5 shadow-card">'
            f'<span class="grid h-11 w-11 shrink-0 place-items-center rounded-xl ring-1 {TYPE_STYLE.get(gd["type"], "")}"><i data-lucide="{esc(gd["icon"])}" class="h-5 w-5"></i></span>'
            f'<span class="min-w-0"><span class="text-[11px] font-bold text-ink-400">{esc(t.get("short", ""))}</span><span class="block font-extrabold leading-snug text-ink-900">{esc(gd["h1"])}</span>'
            f'<span class="mt-1 line-clamp-2 block text-sm text-ink-500">{esc(gd["intro"][:90])}…</span></span></a>')


def render_guide(gd: dict, guides: dict, core: dict, cfg: dict) -> str:
    types = guides["_meta"]["types"]
    t = types.get(gd["type"], {})
    by_id = core["by_id"]
    cats = core["categories"]
    path = f"guide/{gd['slug']}.html"
    url = f"{cfg['url']}/{path}"
    desc = gd["description"]
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "영양제 가이드", "item": f"{cfg['url']}/guides.html"},
            {"@type": "ListItem", "position": 3, "name": gd["h1"], "item": url}]},
        {"@type": "Article", "headline": gd["title"], "description": desc, "mainEntityOfPage": url, "keywords": ", ".join(gd["keywords"]),
         "author": {"@type": "Organization", "name": cfg["name"]}, "publisher": {"@type": "Organization", "name": cfg["name"]}, "dateModified": guides["_meta"].get("updatedAt", "")},
        {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in gd["faq"]]},
    ]}
    head = head_html(cfg, title=f"{gd['title']} | {cfg['name']}", desc=desc, path=path, root="../", keywords=", ".join(gd["keywords"]),
                     extra_scripts='<script src="../assets/js/pages/guide.js" defer></script>', ld=ld)

    # 핵심 성분
    ing_html = ""
    for x in gd["ingredients"]:
        it = by_id.get(x["id"])
        if not it:
            continue
        cat = cats.get(it["category"], {})
        ing_html += (f'<div class="flex gap-4 rounded-2xl border border-ink-100 bg-white p-5 shadow-card"><a href="../i/{esc(it["id"])}.html" class="grid h-12 w-12 shrink-0 place-items-center rounded-xl ring-1 {cat_class(cat.get("color", ""))}"><i data-lucide="{esc(it.get("icon") or cat.get("icon", "pill"))}" class="h-6 w-6"></i></a>'
                     f'<div class="min-w-0"><a href="../i/{esc(it["id"])}.html" class="font-extrabold text-ink-900 hover:text-brand-700">{esc(it["name"])}</a>'
                     f'<p class="mt-0.5 text-xs text-brand-800">{esc((it.get("mfdsFunction") or "")[:70])}{"…" if len(it.get("mfdsFunction") or "") > 70 else ""}</p>'
                     f'<p class="mt-2 text-sm leading-relaxed text-ink-700">{esc(x["why"])}</p>'
                     f'<p class="mt-2 text-xs text-ink-500"><i data-lucide="clock" class="mr-1 inline h-3.5 w-3.5 align-text-bottom"></i>{esc(it["timing"]["label"])} · 하루 {esc(it["dosage"]["daily"][:40])}</p></div></div>')

    # 조합
    combo_html = ""
    for c in gd["combos"]:
        names = [by_id[i]["name"] for i in c["ids"] if i in by_id]
        p = None
        if len(c["ids"]) == 2:
            a, b = sorted(c["ids"])
            p = next((pp for pp in core["pairs"] if sorted(pp["pair"]) == [a, b]), None)
        ptype = p["type"] if p else ("synergy" if len(c["ids"]) > 2 else "neutral")
        tlabel = core["types"].get(ptype, {}).get("short", "")
        combo_html += (f'<div class="rounded-2xl border p-5 card-{ptype}"><div class="flex flex-wrap items-center gap-2"><span class="badge badge-{ptype}">{esc(tlabel)}</span>'
                       + (f'<span class="text-xs font-bold text-amber-700">{p["separateHours"]}시간 이상 간격</span>' if p and p.get("separateHours") else "") + "</div>"
                       f'<h3 class="mt-2 font-extrabold text-ink-900">{esc(" + ".join(names))}</h3><p class="mt-1 text-sm text-ink-700">{esc(c["note"])}</p>'
                       f'<a href="../compatibility.html?items={",".join(c["ids"])}" class="mt-3 inline-flex items-center gap-1 text-sm font-bold text-brand-700 hover:underline">궁합 체크에서 자세히 <i data-lucide="arrow-right" class="h-4 w-4"></i></a></div>')

    sections_html = "".join(f'<section class="rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="text-lg font-extrabold text-ink-900">{esc(sec["h2"])}</h2><p class="mt-3 whitespace-pre-line text-[15px] leading-relaxed text-ink-700">{esc(sec["body"])}</p></section>' for sec in gd.get("sections", []))
    tips_html = ul(gd["tips"], "list-check")
    caut_html = ul(gd["cautions"], "list-warn")
    faq_html = "".join(f'<details class="group border-b border-ink-100 py-3 last:border-0"><summary class="flex cursor-pointer list-none items-center justify-between gap-3 font-bold text-ink-900"><span>Q. {esc(f["q"])}</span><i data-lucide="chevron-down" class="h-4 w-4 shrink-0 text-ink-400 transition group-open:rotate-180"></i></summary><p class="mt-2 text-sm leading-relaxed text-ink-600">{esc(f["a"])}</p></details>' for f in gd["faq"])
    shop_html = "".join(f'<div class="flex flex-col gap-2 rounded-xl border border-ink-100 bg-white p-4 sm:flex-row sm:items-center sm:justify-between"><div><p class="font-bold text-ink-900">{esc(by_id[x["id"]]["name"])}</p><p class="text-xs text-ink-500">검색어: {esc(by_id[x["id"]]["shopQuery"])}</p></div><div class="js-shop" data-query="{esc(by_id[x["id"]]["shopQuery"])}"></div></div>' for x in gd["ingredients"][:3] if x["id"] in by_id)
    related = [guides["by_id"][r] for r in gd.get("related", []) if r in guides["by_id"]]
    related_html = "".join(guide_card(r, types, "../") for r in related)
    all_ids = ",".join(x["id"] for x in gd["ingredients"][:6])
    nav_chips = "".join(f'<a href="#{a}" class="chip">{b}</a>' for a, b in (("ingredients", "핵심 성분"), ("combos", "추천 조합")) if (a != "combos" or combo_html)) + ("".join(f'<a href="#sec-{i}" class="chip">{esc(sec["h2"][:14])}</a>' for i, sec in enumerate(gd.get("sections", [])[:0]))) + '<a href="#tips" class="chip">이렇게 드세요</a><a href="#faq" class="chip">FAQ</a>'

    body = f"""
<body data-page="guides" data-path="{path}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-5xl px-4 pb-10 pt-8 sm:px-6 sm:pt-12">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="../index.html">홈</a> › <a class="hover:text-brand-700" href="../guides.html">영양제 가이드</a> › <a class="hover:text-brand-700" href="../guides.html#{gd['type']}">{esc(t.get('short', ''))}</a> › <span class="text-ink-800">{esc(gd['h1'])}</span></nav>
      <span class="mt-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ring-1 {TYPE_STYLE.get(gd['type'], '')}"><i data-lucide="{esc(gd['icon'])}" class="h-3.5 w-3.5"></i>{esc(t.get('label', ''))}</span>
      <h1 class="page-title mt-3">{esc(gd['h1'])}</h1>
      <p class="page-lead mt-4 max-w-3xl">{esc(gd['intro'])}</p>
      <div class="mt-5 flex flex-wrap gap-2 text-xs">{nav_chips}</div>
      <p class="mt-4 text-xs text-ink-400">식약처 인정 기능성 표현을 기준으로 작성한 일반 건강 정보이며 의학적 조언이 아닙니다 · 최종 수정 {esc(guides['_meta'].get('updatedAt', ''))}</p>
    </div></section>
    <div class="mx-auto max-w-5xl space-y-8 px-4 py-10 sm:px-6">
      <section id="ingredients" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">핵심 성분</h2><p class="mt-1 text-sm text-ink-500">각 성분을 누르면 효능·권장량·주의사항과 함유 제품을 볼 수 있습니다.</p><div class="mt-4 grid gap-4 md:grid-cols-2">{ing_html}</div>
        <a href="../compatibility.html?items={all_ids}" class="btn-primary mt-4"><i data-lucide="heart-handshake"></i>이 성분들로 궁합·복용 시간표 만들기 <i data-lucide="arrow-right"></i></a></section>
      {('<section id="combos" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">함께 먹으면 좋은 조합</h2><div class="mt-4 grid gap-4 md:grid-cols-2">' + combo_html + '</div></section>') if combo_html else ''}
      {sections_html}
      <section id="tips" class="scroll-mt-24 grid gap-4 md:grid-cols-2"><div class="rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="lightbulb" class="h-5 w-5 text-amber-500"></i>이렇게 드세요</h2><div class="mt-3">{tips_html}</div></div><div class="rounded-2xl border border-amber-100 bg-white p-6 shadow-card"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="triangle-alert" class="h-5 w-5 text-amber-600"></i>주의할 점</h2><div class="mt-3">{caut_html}</div></div></section>
      <section id="faq" class="scroll-mt-24 rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="text-lg font-extrabold text-ink-900">자주 묻는 질문</h2><div class="mt-2">{faq_html}</div></section>
      {('<section class="rounded-2xl border border-ink-100 bg-ink-50 p-6"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="shopping-cart" class="h-5 w-5 text-brand-600"></i>관련 제품 찾기</h2><p class="mt-1 text-sm text-ink-500">쇼핑몰 검색 결과로 이동합니다. 함량·형태는 제품 라벨을 확인하세요.</p><div class="mt-4 grid gap-3">' + shop_html + '</div><p class="mt-3 text-[11px] text-ink-400">이 사이트는 쿠팡 파트너스 및 링크프라이스 등 제휴 마케팅 활동의 일환으로, 구매 시 일정액의 수수료를 제공받을 수 있습니다.</p></section>') if shop_html else ''}
      {('<section><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">함께 보면 좋은 가이드</h2><div class="mt-4 grid gap-4 md:grid-cols-3">' + related_html + '</div></section>') if related_html else ''}
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def render_guides_hub(guides: dict, cfg: dict) -> str:
    types = guides["_meta"]["types"]
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"}, {"@type": "ListItem", "position": 2, "name": "영양제 가이드", "item": f"{cfg['url']}/guides.html"}]},
        {"@type": "CollectionPage", "name": "영양제 추천 가이드", "url": f"{cfg['url']}/guides.html", "hasPart": [{"@type": "Article", "headline": g["title"], "url": f"{cfg['url']}/guide/{g['slug']}.html"} for g in guides["items"]]},
    ]}
    head = head_html(cfg, title=f"영양제 추천 가이드 — 고민별·대상별·복용법 총정리 | {cfg['name']}",
                     desc="피로·눈·간·관절·수면·면역 등 고민별, 20대부터 50대 이상·임산부·수험생·어린이까지 대상별 영양제 추천 성분과 조합, 먹는 시간·조합·권장량·약물 상호작용 가이드를 한곳에 모았습니다.",
                     path="guides.html", root="./", keywords="영양제 추천, 영양제 조합, 영양제 먹는 시간, 고민별 영양제, 대상별 영양제", og_type="website", ld=ld)
    secs = ""
    for key, t in types.items():
        cards = "".join(guide_card(g, types, "./") for g in guides["items"] if g["type"] == key)
        secs += f'<section id="{key}" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">{esc(t["label"])}</h2><p class="mt-1 text-ink-500">{esc(t["desc"])}</p><div class="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{cards}</div></section>'
    body = f"""
<body data-page="guides" data-path="guides.html" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="index.html">홈</a> › <span class="text-ink-800">영양제 가이드</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="leaf"></i> 영양제 추천 가이드</p>
      <h1 class="page-title mt-3">고민과 상황에서 출발하는 영양제 가이드</h1>
      <p class="page-lead mt-4 max-w-2xl">특정 제품이 아니라 <strong>성분과 조합</strong>을 추천합니다. 각 가이드는 식약처 인정 기능성 표현을 기준으로 핵심 성분, 함께 먹으면 좋은 조합, 섭취 시간, 주의할 점을 정리하고 성분 사전·궁합 체크·제품 찾기로 연결됩니다.</p>
      <div class="mt-5 flex flex-wrap gap-2">{''.join(f'<a href="#{k}" class="chip">{esc(t["short"])}</a>' for k, t in types.items())}</div>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">{secs}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">가이드를 읽는 법</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li>'추천 성분'은 식약처가 인정한 기능성과 결핍 가능성을 기준으로 고른 것이며 특정 제품·브랜드를 보증하지 않습니다.</li><li>건강기능식품은 질병의 예방·치료 목적이 아닙니다. 증상이 지속되면 진료가 먼저입니다.</li><li>약을 복용 중이라면 <a class="font-bold text-brand-700 underline" href="guide/with-medication.html">약과 영양제 가이드</a>를 먼저 읽고 약사·의사와 상의하세요.</li></ul></section>
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def build_guides(core: dict, cfg: dict) -> dict:
    guides = read_json(DATA_DIR / "guides.json", {"_meta": {"types": {}}, "items": []})
    guides["by_id"] = {g["id"]: g for g in guides["items"]}
    GUIDE_DIR.mkdir(exist_ok=True)
    wanted = set()
    for gd in guides["items"]:
        path = GUIDE_DIR / f"{gd['slug']}.html"
        path.write_text(render_guide(gd, guides, core, cfg), encoding="utf-8")
        wanted.add(path.name)
    for stale in GUIDE_DIR.glob("*.html"):
        if stale.name not in wanted:
            stale.unlink()
    (ROOT / "guides.html").write_text(render_guides_hub(guides, cfg), encoding="utf-8")
    log.info("가이드 페이지 %d개 + guides.html 생성", len(wanted))
    return guides


def build_sitemap(ingredients: list[dict], cfg: dict, data_date: str, guides: dict | None = None) -> None:
    today = now_iso()[:10]
    dynamic = ("index.html", "news.html", "products.html")
    urls = [(f"{cfg['url']}/{p}", "daily" if p in dynamic else "monthly", "1.0" if p == "index.html" else "0.8", today if p in dynamic else data_date) for p in STATIC_PAGES]
    urls += [(f"{cfg['url']}/i/{it['id']}.html", "monthly", "0.7", data_date) for it in ingredients]
    gdate = (guides or {}).get("_meta", {}).get("updatedAt") or data_date
    urls += [(f"{cfg['url']}/guide/{g['slug']}.html", "monthly", "0.8", gdate) for g in (guides or {}).get("items", [])]
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

    guides_data = read_json(DATA_DIR / "guides.json", {"_meta": {"types": {}}, "items": []})
    core["guides"] = guides_data.get("items", [])

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

    guides = build_guides(core, cfg)
    build_sitemap(ingredients["items"], cfg, data_date, guides)
    inject_verification(cfg)
    check_icons()
    stamp_assets()
    products = read_json(DATA_DIR / "products.json", {"_meta": {}, "items": []})
    news = read_json(DATA_DIR / "news.json", {"_meta": {}, "items": []})
    materials = read_json(DATA_DIR / "materials.json", {"_meta": {}, "items": []})
    write_json(DATA_DIR / "meta.json", {
        "builtAt": now_iso(),
        "ingredients": len(ingredients["items"]),
        "pairs": len(interactions["pairs"]),
        "guides": len(guides.get("items", [])),
        "products": {"source": products.get("_meta", {}).get("source", "sample"), "updatedAt": products.get("_meta", {}).get("updatedAt"), "total": len(products.get("items", []))},
        "news": {"source": news.get("_meta", {}).get("source", "sample"), "updatedAt": news.get("_meta", {}).get("updatedAt"), "total": len(news.get("items", []))},
        "materials": {"source": materials.get("_meta", {}).get("source", "sample"), "updatedAt": materials.get("_meta", {}).get("updatedAt"), "total": len(materials.get("items", [])), "matched": materials.get("_meta", {}).get("matched", 0),
                      "ingredients": sorted(f.stem for f in (DATA_DIR / "materials").glob("*.json"))},
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
