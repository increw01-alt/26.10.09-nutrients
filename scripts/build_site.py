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
import unicodedata
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datetime import datetime  # noqa: E402
from brand_priority import load_brand_priority  # noqa: E402
from common import DATA_DIR, KST, ROOT, env, log, now_iso, read_json, write_json  # noqa: E402

OUT_DIR = ROOT / "i"
GUIDE_DIR = ROOT / "guide"
STATIC_PAGES = ["index.html", "ingredients.html", "compatibility.html", "compatibility-chart.html", "timing-chart.html", "finder.html", "functions.html", "guides.html", "products.html", "news.html", "materials.html", "about.html", "terms.html", "privacy.html"]   # compatibility-chart·timing-chart 는 build_charts() 가 생성


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def page_url(cfg: dict, path: str) -> str:
    """사이트 상대 경로(index.html, i/vitamin-d.html …) → 검색엔진에 알릴 정식 주소.
    Cloudflare Pages 는 `/foo.html` 요청을 `/foo` 로, `/index.html` 을 `/` 로 리다이렉트하고 확장자 없는 주소로 서비스하므로
    canonical·og:url·sitemap·구조화 데이터는 그 형태를 써야 한다 (내부 링크는 로컬 http.server 확인을 위해 .html 유지)."""
    p = path.strip("/")
    if p.endswith(".html"):
        p = p[:-5]
    if p == "index" or p.endswith("/index"):
        p = p[:-5]
    return f"{cfg['url']}/{p}"


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


_DIGEST_CACHE: dict[str, str] = {}


def asset_digest(path: Path) -> str:
    """자산 파일 내용 해시 앞 8자 (?v= 스탬프와 서비스워커 precache 가 같은 값을 쓴다). 없는 파일은 "0".
    줄끝을 LF 로 맞춘 뒤 해시: Windows 의 core.autocrlf 로 CRLF 가 된 체크아웃에서도 CI(Linux) 와 같은 값이 나오게."""
    import hashlib
    key = str(path)
    if key not in _DIGEST_CACHE:
        _DIGEST_CACHE[key] = hashlib.sha1(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:8] if path.exists() else "0"
    return _DIGEST_CACHE[key]


SW_TEMPLATE = ROOT / "scripts/sw_template.js"
PRECACHE_EXTRA = ["offline.html", "my.html", "assets/images/favicon.svg", "assets/images/home/leaf.webp",   # URL 에 해시가 없는 파일 — 내용 해시는 sw_version 에 섞는다 (my.html 은 앱의 첫 화면이라 오프라인에서도 열리게)
                  "assets/images/app/icon-192.png", "assets/images/app/icon-512.png"]            # (manifest 는 서비스워커가 건드리지 않아 뺌)


def precache_urls() -> list[str]:
    """서비스워커가 설치 때 미리 받을 절대 경로 목록(정렬). CSS·JS 는 stamp_assets 와 같은 ?v= 해시를 붙이고, 페이지가 싣지 않는 *.src.css 는 뺀다."""
    files = [p for p in (ROOT / "assets/css").glob("*.css") if not p.name.endswith(".src.css")] + \
        [p for p in (ROOT / "assets/js").rglob("*.js") if "vendor/capacitor" not in p.as_posix()]   # 앱 전용 런타임은 앱이 필요할 때만 받는다
    urls = [f"/{p.relative_to(ROOT).as_posix()}?v={asset_digest(p)}" for p in files]
    urls += [f"/{p}" for p in PRECACHE_EXTRA if (ROOT / p).exists()]
    return sorted(urls)


def precache_extra_digests() -> list[str]:
    """해시 없는 precache 파일들의 내용 해시 — 버전 계산에 섞어 offline.html·아이콘이 바뀌어도 새 서비스워커가 배포되게."""
    return [asset_digest(ROOT / p) for p in PRECACHE_EXTRA if (ROOT / p).exists()]


def sw_version(template: str, urls: list[str], extra_digests: list[str] | None = None) -> str:
    """템플릿 본문 + precache 목록 + 해시 없는 파일의 내용 해시를 합친 sha1 앞 8자 — 무엇이든 바뀌면 버전이 바뀌어 옛 캐시를 버린다."""
    import hashlib
    return hashlib.sha1((template.replace("\r\n", "\n") + "\n".join(urls) + "\n".join(extra_digests or [])).encode("utf-8")).hexdigest()[:8]


def build_sw() -> None:
    """scripts/sw_template.js 에 버전과 precache 목록을 채워 루트 sw.js 를 생성한다 (sw.js 는 생성 파일)."""
    template = SW_TEMPLATE.read_text(encoding="utf-8")
    urls = precache_urls()
    ver = sw_version(template, urls, precache_extra_digests())
    out = template.replace('"__VERSION__"', json.dumps(ver)).replace("/*__PRECACHE__*/[]", json.dumps(urls, ensure_ascii=False))
    with open(ROOT / "sw.js", "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    log.info("sw.js 생성: precache %d개, 버전 %s", len(urls), ver)


def stamp_assets() -> None:
    """모든 HTML 의 assets/js·css 링크에 내용 해시(?v=…)를 붙여, 배포 후 브라우저가 예전 캐시 대신 새 파일을 받게 합니다.
    (Cloudflare Pages + 휴대폰 브라우저에서 새 HTML 과 옛 JS/CSS 가 섞여 동작이 깨지는 문제 방지)"""
    files = sorted(ROOT.glob("*.html")) + sorted(OUT_DIR.glob("*.html")) + sorted((ROOT / "guide").glob("*.html")) + sorted((ROOT / "function").glob("*.html"))
    changed = 0
    for html_path in files:
        src = html_path.read_text(encoding="utf-8")

        def repl(m: re.Match) -> str:
            rel = m.group("path")
            target = (ROOT / rel.lstrip("/")).resolve() if rel.startswith("/") else (html_path.parent / rel).resolve()
            return f'{m.group("pre")}{m.group("path")}?v={asset_digest(target)}{m.group("post")}'

        out = ASSET_LINK_RE.sub(repl, src)
        if out != src:
            html_path.write_text(out, encoding="utf-8"); changed += 1
    log.info("자산 버전 스탬프: HTML %d개 갱신", changed)


SEARCH_RECENT_YEARS = 3        # 검색 색인 1단(names.json)에 담을 신고 연도 범위(올해 포함 약 3년). 그보다 오래된 제품은 names-old.json 으로 (검색창이 먼저 1단으로 결과를 보여주고 뒤이어 불러와 합친다)


def build_product_names() -> None:
    """제품 검색용 경량 색인: 상세 조각(data/products/detail/*.json, 매칭된 전체 제품)에서 id·이름·성분 번호·제조사 번호만 뽑아
    data/products/names.json(최근 SEARCH_RECENT_YEARS 년) 과 names-old.json(그 이전) 으로 나눠 저장한다. 두 파일은 같은 성분·제조사 목록을 공유한다."""
    products = read_json(DATA_DIR / "products.json", {"_meta": {}, "items": []}) or {}
    items: dict[str, dict] = {}
    for f in sorted((DATA_DIR / "products" / "detail").glob("*.json")):
        for it in (read_json(f, {}) or {}).get("items", []):
            items.setdefault(it["id"], it)
    if not items:   # 상세 조각이 없으면(샘플 상태) 목록 파일로
        items = {it["id"]: it for it in products.get("items", [])}
    rows = sorted(items.values(), key=lambda it: it.get("registeredAt") or "", reverse=True)
    ids = sorted({i for it in rows for i in it.get("ingredients", [])})
    idx = {i: n for n, i in enumerate(ids)}
    companies = sorted({(it.get("company") or "").strip() for it in rows} - {""})
    cidx = {c: n for n, c in enumerate(companies)}
    cutoff = f"{datetime.now(KST).year - SEARCH_RECENT_YEARS + 1}-01-01"
    bp = load_brand_priority()

    def entry(it: dict) -> list:   # [제품id, 이름, [성분번호], 제조사번호, (브랜드 가중치 1~3 — 0 이면 생략)]
        company = (it.get("company") or "").strip()
        row = [it["id"], it["name"], [idx[i] for i in it.get("ingredients", []) if i in idx], cidx.get(company, -1)]
        w = bp.weight(it["name"], company)
        return row + [w] if w else row
    recent = [entry(it) for it in rows if (it.get("registeredAt") or "9999") >= cutoff]
    older = [entry(it) for it in rows if (it.get("registeredAt") or "9999") < cutoff]
    updated = products.get("_meta", {}).get("updatedAt")
    write_json(DATA_DIR / "products" / "names.json", {"_meta": {"updatedAt": updated, "total": len(recent), "old": len(older), "cutoff": cutoff}, "i": ids, "c": companies, "p": recent}, compact=True, quiet=True)
    old_path = DATA_DIR / "products" / "names-old.json"
    if older:
        write_json(old_path, {"_meta": {"updatedAt": updated, "total": len(older), "before": cutoff}, "i": ids, "c": companies, "p": older}, compact=True, quiet=True)
    elif old_path.exists():
        old_path.unlink()
    weighted = sum(1 for e in recent + older if len(e) > 4)
    log.info("제품 검색 색인: 최근 %s건 + 과거 %s건 (data/products/names.json%s) · 브랜드 가중치 %s건", f"{len(recent):,}", f"{len(older):,}", " · names-old.json" if older else "", f"{weighted:,}")


def validate_drug_pairings(valid_ids: set[str]) -> None:
    """data/drug-pairings.json (의약품별 함께 챙기면 좋은/주의할 영양 성분) 의 성분 id 가 성분 사전에 있는지 확인."""
    data = read_json(DATA_DIR / "drug-pairings.json", None)
    if not data:
        return
    bad = [(r.get("id"), x.get("id")) for r in data.get("rules", []) for k in ("good", "caution") for x in r.get(k, []) if x.get("id") not in valid_ids]
    if bad:
        raise SystemExit(f"drug-pairings.json 에 없는 성분 id: {bad}")
    log.info("의약품 영양 성분 규칙 검증 통과: %d개 규칙", len(data.get("rules", [])))


def stamp_drug_weights() -> None:
    """의약품 검색 색인(data/drugs/names.json) 의 각 항목에 브랜드 가중치(p[6]) 를 싣는다 — fetch_drugs.py 도 같은 규칙으로 쓰지만,
    규칙 파일(data/brand-priority.json)만 고친 뒤 빌드해도 반영되도록 여기서 다시 맞춘다 (바뀐 게 없으면 파일을 건드리지 않음)."""
    path = DATA_DIR / "drugs" / "names.json"
    data = read_json(path, None)
    if not data or not data.get("p"):
        return
    bp = load_brand_priority()
    companies = data.get("c", [])
    changed = 0
    for row in data["p"]:
        company = companies[row[5]] if len(row) > 5 and isinstance(row[5], int) and 0 <= row[5] < len(companies) else ""
        w = bp.weight(row[1], company)
        cur = row[6] if len(row) > 6 else 0
        if w != cur:
            changed += 1
            del row[6:]
            if w:
                row.append(w)
    if changed:
        write_json(path, data, compact=True, quiet=True)
        log.info("의약품 검색 색인 브랜드 가중치 갱신: %s건 변경", f"{changed:,}")


def ensure_drug_index() -> None:
    """의약품 검색 색인(scripts/fetch_drugs.py 가 생성)이 아직 없으면 빈 색인을 둔다 — 검색 스크립트가 404 를 만나지 않도록."""
    path = DATA_DIR / "drugs" / "names.json"
    if path.exists():
        stamp_drug_weights()
        return
    write_json(path, {"_meta": {"source": "none", "total": 0, "updatedAt": None, "note": "DATA_GO_KR_KEY 를 등록하고 scripts/fetch_drugs.py 를 실행하면 채워집니다"}, "i": [], "p": []}, compact=True, quiet=True)
    log.info("의약품 검색 색인이 없어 빈 색인 생성 (data/drugs/names.json) — DATA_GO_KR_KEY 등록 후 fetch_drugs.py 로 수집")


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
    # 홈 메타 설명의 성분 수('NN가지 성분')는 ingredients.json 기준으로 빌드가 갱신 (손으로 고치지 않음)
    n_ing = len(read_json(DATA_DIR / "ingredients.json", {"items": []}).get("items", []))
    new_src, n_rep = re.subn(r"\d+가지 성분", f"{n_ing}가지 성분", new_src)
    if new_src != html_src:
        path.write_text(new_src, encoding="utf-8")
        log.info("index.html 소유 확인 메타태그 %d개 반영, 성분 수 표기 %d곳 → %d가지", len(tags), n_rep, n_ing)


PWA_START, PWA_END = "<!-- pwa:start -->", "<!-- pwa:end -->"
PWA_THEME = "#246d4b"


def pwa_tags(root: str) -> str:
    """홈 화면 설치(PWA)용 head 태그 6줄 — 매니페스트·iOS 아이콘·테마색. root 는 페이지의 data-root('./'·'../'·'/')."""
    return "\n".join([
        f'<link rel="manifest" href="{root}manifest.webmanifest">',
        f'<link rel="apple-touch-icon" href="{root}assets/images/app/apple-touch-icon.png">',
        f'<meta name="theme-color" content="{PWA_THEME}">',
        '<meta name="mobile-web-app-capable" content="yes">',
        '<meta name="apple-mobile-web-app-title" content="영양제.kr">',
        '<meta name="apple-mobile-web-app-status-bar-style" content="default">',
    ])


def pwa_block(root: str, indent: str = "  ") -> str:
    """마커로 감싼 PWA 태그 블록 (끝에 줄바꿈 없음)."""
    return f"{indent}{PWA_START}\n" + "".join(f"{indent}{t}\n" for t in pwa_tags(root).split("\n")) + f"{indent}{PWA_END}"


def ensure_pwa_tags(html_src: str, root: str) -> str:
    """마커 블록이 있으면 내용을 갱신하고, 없으면 <link rel="icon"> 줄 바로 뒤에 넣는다. 둘 다 없으면 그대로. 멱등."""
    a, b = html_src.find(PWA_START), html_src.find(PWA_END)
    if a >= 0 and b > a:
        line_start = html_src.rfind("\n", 0, a) + 1
        indent = html_src[line_start : a]   # 띄어쓰기 유지: 붙여 쓰면 Tailwind 가 임의값 클래스로 읽어 쓰레기 규칙을 만든다
        return html_src[:line_start] + pwa_block(root, indent) + html_src[b + len(PWA_END):]
    m = re.search(r'^([ \t]*)<link rel="icon"[^>]*>[ \t]*$', html_src, re.M)
    if not m:
        return html_src
    return html_src[:m.end()] + "\n" + pwa_block(root, m.group(1)) + html_src[m.end():]


def inject_pwa_tags() -> None:
    """모든 HTML(루트·i/·guide/)의 <link rel="icon"> 뒤 마커 블록에 PWA 태그를 넣거나 갱신한다 (경로는 각 페이지의 data-root 기준)."""
    files = sorted(ROOT.glob("*.html")) + sorted(OUT_DIR.glob("*.html")) + sorted(GUIDE_DIR.glob("*.html")) + sorted((ROOT / "function").glob("*.html"))
    changed = 0
    for p in files:
        src = p.read_text(encoding="utf-8")
        m = re.search(r'data-root="([^"]*)"', src)
        out = ensure_pwa_tags(src, m.group(1) if m else "./")
        if out != src:
            p.write_text(out, encoding="utf-8"); changed += 1
    log.info("PWA 태그 주입: HTML %d개 갱신", changed)


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
    title = f"{it['name']} 효능·권장량·궁합·먹는 시간 | {cfg['name']}"
    fn_model = core.get("functions") or {}
    fn_meta = {e["fn"]["id"]: e["fn"] for e in fn_model.get("items", [])}
    fns = [f for f in (fn_model.get("by_ingredient") or {}).get(it["id"], []) if f in fn_meta]
    fn_chips = ('<div class="mt-3 flex flex-wrap items-center gap-2"><span class="text-xs font-bold text-ink-500">기능성별 페이지:</span>' + "".join(f'<a class="chart-chip" href="../function/{esc(f)}.html"><i data-lucide="{esc(fn_meta[f]["icon"])}" class="h-3.5 w-3.5"></i>{esc(fn_meta[f]["label"])}</a>' for f in fns) + '</div>') if fns else ""
    desc = it["summary"][:150]
    url = page_url(cfg, f"i/{it['id']}.html")
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
            {"@type": "ListItem", "position": 2, "name": "성분 사전", "item": page_url(cfg, "ingredients.html")},
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
      <h2 class="mt-8 text-lg font-extrabold">식약처 인정 기능성</h2><p class="mt-2 text-sm text-ink-700">{esc(it.get("mfdsFunction") or "고시형 기능성 원료 아님")}</p>{fn_chips}
      <h2 class="mt-6 text-lg font-extrabold">기대 효과</h2>{ul(it.get("benefits", []), "list-check")}
      <h2 class="mt-6 text-lg font-extrabold">권장 섭취량</h2><p class="text-sm text-ink-700">하루 권장: {esc(it["dosage"].get("daily"))} · 상한: {esc(it["dosage"].get("upper"))}</p><p class="text-sm text-ink-600">{esc(it["dosage"].get("note", ""))}</p>
      <h2 class="mt-6 text-lg font-extrabold">{esc(it["name"])} 먹는 시간</h2><p class="text-sm text-ink-700">{esc(it["timing"].get("label"))} — {esc(it["timing"].get("note", ""))}</p><p class="mt-1 text-xs"><a class="font-bold text-brand-700 hover:underline" href="../timing-chart.html#{esc(it["id"])}">영양제 복용 시간표에서 다른 성분과 비교 →</a></p>
      <h2 class="mt-6 text-lg font-extrabold">이런 분께 추천</h2>{ul(it.get("whoFor", []), "list-dot")}
      <h2 class="mt-6 text-lg font-extrabold">주의사항</h2>{ul(it.get("cautions", []), "list-warn")}{('<h3 class="mt-3 text-sm font-bold text-rose-700">약과 함께 먹을 때</h3>' + ul(it.get("drugCautions", []), "list-warn")) if it.get("drugCautions") else ""}
      {mat_html}
      {guides_html}
      <h2 class="mt-6 text-lg font-extrabold">{esc(it["name"])} 궁합</h2><p class="mb-2 text-sm text-ink-500">같이 먹으면 좋은 영양제와 시간을 나눠야 할 조합입니다. 전체는 <a class="font-bold text-brand-700 hover:underline" href="../compatibility-chart.html#{esc(it["id"])}">영양제 궁합표</a>에서 볼 수 있습니다.</p>{rel_html or '<p class="text-sm text-ink-400">등록된 궁합 정보가 없습니다.</p>'}
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
  <meta property="og:image" content="{esc(cfg["url"])}/assets/images/og-default.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="../assets/images/favicon.svg" type="image/svg+xml">
{pwa_block("../")}
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
  <link rel="stylesheet" href="../assets/css/style.css">
  <link rel="stylesheet" href="../assets/css/tailwind.css">
  <script src="../assets/js/icons.js" defer></script>
  <script src="../assets/js/config.js" defer></script>
  <script src="../assets/js/app.js" defer></script>
  <script src="../assets/js/data.js" defer></script>
  <script src="../assets/js/affiliate.js" defer></script>
  <script src="../assets/js/layout.js" defer></script>
  <script src="../assets/js/store.js" defer></script>
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
    url = page_url(cfg, path)
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
  <meta property="og:image" content="{esc(cfg['url'])}/assets/images/og-default.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="{root}assets/images/favicon.svg" type="image/svg+xml">
{pwa_block(root)}
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
  <link rel="stylesheet" href="{root}assets/css/style.css">
  <link rel="stylesheet" href="{root}assets/css/tailwind.css">
  <script src="{root}assets/js/icons.js" defer></script>
  <script src="{root}assets/js/config.js" defer></script>
  <script src="{root}assets/js/app.js" defer></script>
  <script src="{root}assets/js/data.js" defer></script>
  <script src="{root}assets/js/affiliate.js" defer></script>
  <script src="{root}assets/js/layout.js" defer></script>
  <script src="{root}assets/js/store.js" defer></script>
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
    url = page_url(cfg, path)
    desc = gd["description"]
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "영양제 가이드", "item": page_url(cfg, "guides.html")},
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
        <button type="button" class="btn-outline mt-4" data-my-add="{all_ids}"><i data-lucide="plus"></i>이 성분들을 내 영양제에 추가</button>
        <a href="../compatibility.html?items={all_ids}" class="btn-primary mt-4"><i data-lucide="heart-handshake"></i>이 성분들로 궁합·복용 시간표 만들기 <i data-lucide="arrow-right"></i></a></section>
      {('<section id="combos" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">함께 먹으면 좋은 조합</h2><div class="mt-4 grid gap-4 md:grid-cols-2">' + combo_html + '</div></section>') if combo_html else ''}
      {sections_html}
      <section id="tips" class="scroll-mt-24 grid gap-4 md:grid-cols-2"><div class="rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="lightbulb" class="h-5 w-5 text-amber-500"></i>이렇게 드세요</h2><div class="mt-3">{tips_html}</div></div><div class="rounded-2xl border border-amber-100 bg-white p-6 shadow-card"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="triangle-alert" class="h-5 w-5 text-amber-600"></i>주의할 점</h2><div class="mt-3">{caut_html}</div></div></section>
      <section class="rounded-2xl border border-ink-100 bg-cream-200 p-5"><h2 class="text-base font-extrabold text-ink-900">바로 보는 표</h2><p class="mt-1 text-sm text-ink-700">선택 없이 전체를 훑어보려면 <a class="font-bold text-brand-700 underline" href="../compatibility-chart.html">영양제 궁합표</a>와 <a class="font-bold text-brand-700 underline" href="../timing-chart.html">영양제 복용 시간표</a>를 참고하세요.</p></section>
      <section id="faq" class="scroll-mt-24 rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="text-lg font-extrabold text-ink-900">자주 묻는 질문</h2><div class="mt-2">{faq_html}</div></section>
      {('<section class="app-hide rounded-2xl border border-ink-100 bg-ink-50 p-6"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="shopping-cart" class="h-5 w-5 text-brand-600"></i>관련 제품 찾기</h2><p class="mt-1 text-sm text-ink-500">쇼핑몰 검색 결과로 이동합니다. 함량·형태는 제품 라벨을 확인하세요.</p><div class="mt-4 grid gap-3">' + shop_html + '</div><p class="mt-3 text-[11px] text-ink-400">이 사이트는 쿠팡 파트너스 및 링크프라이스 등 제휴 마케팅 활동의 일환으로, 구매 시 일정액의 수수료를 제공받을 수 있습니다.</p></section>') if shop_html else ''}
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
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"}, {"@type": "ListItem", "position": 2, "name": "영양제 가이드", "item": page_url(cfg, "guides.html")}]},
        {"@type": "CollectionPage", "name": "영양제 추천 가이드", "url": page_url(cfg, "guides.html"), "hasPart": [{"@type": "Article", "headline": g["title"], "url": page_url(cfg, f"guide/{g['slug']}.html")} for g in guides["items"]]},
    ]}
    head = head_html(cfg, title=f"영양제 추천 가이드 — 고민별·대상별·복용법 총정리 | {cfg['name']}",
                     desc="피로·눈·간·관절·수면·면역 등 고민별, 20대부터 50대 이상·임산부·수험생·어린이까지 대상별 영양제 추천 성분과 조합, 먹는 시간·조합·권장량·약물 상호작용 가이드를 한곳에 모았습니다.",
                     path="guides.html", root="./", keywords="영양제 추천, 영양제 조합, 영양제 먹는 시간, 고민별 영양제, 대상별 영양제", og_type="website",
                     extra_scripts='<script src="assets/js/pages/guides.js" defer></script>', ld=ld)
    def search_text(g: dict) -> str:   # 허브 검색용: 제목·h1·키워드·설명·분류를 공백·구분자 없이 소문자로 (guides.js 의 norm 과 같은 규칙)
        t = types.get(g["type"], {})
        raw = " ".join([g["slug"], g["title"], g["h1"], " ".join(g.get("keywords", [])), g.get("description", ""), t.get("label", ""), t.get("short", "")])
        return re.sub(r"[\s·\-]+", "", unicodedata.normalize("NFKC", raw)).lower()
    secs = ""
    for key, t in types.items():
        cards = "".join(guide_card(g, types, "./").replace("<a ", f'<a data-search="{esc(search_text(g))}" ', 1) for g in guides["items"] if g["type"] == key)
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
      <p class="mt-5"><a href="finder.html" class="btn-primary"><i data-lucide="sparkles"></i>나에게 맞는 영양제 찾기 — 1분 셀프체크 <i data-lucide="arrow-right"></i></a></p>
      <div class="mt-5 flex flex-wrap gap-2">{''.join(f'<a href="#{k}" class="chip">{esc(t["short"])}</a>' for k, t in types.items())}</div>
      <form class="relative mt-6 w-full lg:w-96" role="search" onsubmit="return false;"><label for="guide-search" class="sr-only">가이드 검색</label><i data-lucide="search" class="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"></i><input id="guide-search" type="search" placeholder="가이드 검색 (예: 혈압약, 철분, 수면)" autocomplete="off" class="w-full rounded-full border border-ink-200 bg-white py-3 pl-11 pr-4 text-sm shadow-card outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-100"></form>
      <p id="guide-count" class="mt-3 text-sm text-ink-600" aria-live="polite">가이드 {len(guides["items"])}편</p>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      <p id="guide-empty" class="hidden rounded-2xl border border-dashed border-ink-200 bg-white p-6 text-sm text-ink-600">일치하는 가이드가 없습니다. 다른 말로 검색하거나 <a class="font-bold text-brand-700 underline" href="search.html">통합 검색</a>에서 성분·제품·의약품까지 찾아보세요.</p>
      {secs}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">가이드를 읽는 법</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li>'추천 성분'은 식약처가 인정한 기능성과 결핍 가능성을 기준으로 고른 것이며 특정 제품·브랜드를 보증하지 않습니다.</li><li>건강기능식품은 질병의 예방·치료 목적이 아닙니다. 증상이 지속되면 진료가 먼저입니다.</li><li>약을 복용 중이라면 <a class="font-bold text-brand-700 underline" href="guide/with-medication.html">약과 영양제 가이드</a>를 먼저 읽고 약사·의사와 상의하세요.</li><li>표로 한눈에 보려면 <a class="font-bold text-brand-700 underline" href="compatibility-chart.html">영양제 궁합표</a>와 <a class="font-bold text-brand-700 underline" href="timing-chart.html">영양제 복용 시간표</a>를, 식약처 인정 기능성 문구로 찾으려면 <a class="font-bold text-brand-700 underline" href="functions.html">기능성별 영양제</a>를 참고하세요.</li></ul></section>
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def write_guides_index(guides: dict) -> None:
    """검색·자동완성·성분 페이지가 쓰는 경량 색인 (data/guides-index.json). 본문(sections·tips·faq)을 뺀 요약 필드만 담아
    guides.json(약 600KB)을 페이지마다 내려받지 않게 한다. 필드를 바꾸면 data.js 의 guides() 소비처(home.js·search.js·ingredient.js)도 확인."""
    items = [{"id": g["id"], "slug": g["slug"], "type": g["type"], "icon": g.get("icon", "book-open"), "title": g["title"], "h1": g["h1"],
              "keywords": g.get("keywords", []), "description": g.get("description", ""), "intro": g.get("intro", ""),
              "ingredients": [{"id": x["id"]} for x in g.get("ingredients", [])]} for g in guides["items"]]
    meta = {k: v for k, v in guides.get("_meta", {}).items() if k in ("updatedAt", "types")}
    meta["note"] = "guides.json 의 요약 색인 — scripts/build_site.py 가 생성, 직접 수정하지 않음"
    write_json(DATA_DIR / "guides-index.json", {"_meta": meta, "items": items}, compact=True, quiet=True)


def build_guides(core: dict, cfg: dict) -> dict:
    guides = read_json(DATA_DIR / "guides.json", {"_meta": {"types": {}}, "items": []})
    guides["by_id"] = {g["id"]: g for g in guides["items"]}
    write_guides_index(guides)
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


# ---------------------------------------------------------------- 영양제 궁합표 · 복용 시간표 (핵심 키워드 정적 페이지)
SLOT_ORDER = ["morning_empty", "morning_after", "before_meal", "lunch_after", "evening_after", "bedtime"]   # assets/js/schedule.js 의 SLOT_ORDER 와 같아야 함 (tests/test_build_site.py 가 대조)
SLOT_META = {   # assets/js/schedule.js 의 SLOT_META 와 같은 값
    "morning_empty": {"label": "아침 공복", "sub": "기상 직후, 식사 30분 전", "icon": "sunrise"},
    "morning_after": {"label": "아침 식후", "sub": "아침 식사 직후", "icon": "coffee"},
    "before_meal": {"label": "식전", "sub": "점심·저녁 식사 30분 전", "icon": "timer"},
    "lunch_after": {"label": "점심 식후", "sub": "점심 식사 직후", "icon": "utensils"},
    "evening_after": {"label": "저녁 식후", "sub": "저녁 식사 직후", "icon": "sunset"},
    "bedtime": {"label": "취침 전", "sub": "잠들기 30~60분 전", "icon": "bed"},
}
CHART_POPULAR = ["vitamin-d", "omega-3", "probiotics", "magnesium", "calcium", "iron", "zinc", "vitamin-c", "vitamin-b-complex", "lutein", "coq10", "milk-thistle"]   # 한눈에 보는 궁합표의 성분 (자주 찾는 순)
CHART_TYPES = ["synergy", "caution", "avoid", "neutral"]
CHART_SYMBOL = {"synergy": "●", "caution": "▲", "avoid": "✕", "neutral": "○"}
CHART_PATH = "compatibility-chart.html"
TIMING_PATH = "timing-chart.html"


def short_name(name: str) -> str:
    """'프로바이오틱스 (유산균)' → '프로바이오틱스' (행렬 머리글용)."""
    return re.sub(r"\s*\(.*?\)\s*", " ", str(name or "")).strip()


def chart_model(core: dict, popular: list[str] | None = None) -> dict:
    """궁합표 자료: 성분별 상대 목록(좋은·주의·피함·무난, 강한 쌍부터)과 자주 찾는 성분 행렬.
    데이터(interactions.json)에 있는 쌍만 쓴다 — 없는 쌍은 None 으로 두고 규칙 판정은 궁합 체크(data.js resolvePair)에 맡긴다."""
    by_id = core["by_id"]
    partners: dict[str, dict[str, list[dict]]] = {i: {t: [] for t in CHART_TYPES} for i in by_id}
    lookup: dict[frozenset, dict] = {}
    counts = {t: 0 for t in CHART_TYPES}
    for p in core["pairs"]:
        a, b = p["pair"]
        if a not in by_id or b not in by_id or p.get("type") not in counts:
            continue
        lookup[frozenset((a, b))] = p
        counts[p["type"]] += 1
        for x, y in ((a, b), (b, a)):
            partners[x][p["type"]].append({"id": y, "name": by_id[y]["name"], "level": p.get("level", 0), "hours": p.get("separateHours"), "title": p.get("title", "")})
    for groups in partners.values():
        for lst in groups.values():
            lst.sort(key=lambda r: (-r["level"], r["name"]))
    ids = [i for i in (popular or CHART_POPULAR) if i in by_id]
    cells = {a: {b: ("self" if a == b else (lookup.get(frozenset((a, b)), {}).get("type"))) for b in ids} for a in ids}
    return {"partners": partners, "matrix": {"ids": ids, "cells": cells}, "counts": counts, "total": len(lookup)}


def timing_model(ingredients: list[dict], categories: dict | None = None) -> dict:
    """복용 시간표 자료: 성분별 행(권장 시간·기본 시간대·대체 시간대·메모·지용성)과 시간대별 묶음, 지용성 목록."""
    cat_order = list((categories or {}).keys())

    def key(it: dict):
        return (cat_order.index(it["category"]) if it["category"] in cat_order else 99, it["name"])

    rows = []
    for it in sorted(ingredients, key=key):
        t = it.get("timing") or {}
        slot = t.get("slot") if t.get("slot") in SLOT_META else "morning_after"
        rows.append({"id": it["id"], "name": it["name"], "category": it["category"], "label": t.get("label") or SLOT_META[slot]["label"], "slot": slot,
                     "alts": [s for s in (t.get("altSlots") or []) if s in SLOT_META and s != slot], "note": t.get("note", ""), "fat": bool(it.get("fatSoluble"))})
    slots = [dict(key=s, **SLOT_META[s], items=[r for r in rows if r["slot"] == s]) for s in SLOT_ORDER]
    return {"rows": rows, "slots": slots, "fat": [r for r in rows if r["fat"]]}


def faq_block(items: list[tuple[str, str]], heading: str = "자주 묻는 질문") -> tuple[str, dict]:
    """보이는 FAQ 섹션 HTML 과 같은 내용의 FAQPage JSON-LD (구글은 보이는 본문과 구조화 데이터가 같아야 한다)."""
    html_ = f'<section id="faq" class="scroll-mt-24 rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="text-lg font-extrabold text-ink-900">{esc(heading)}</h2><div class="mt-2 divide-y divide-ink-100">' + \
        "".join(f'<details class="group py-3"><summary class="cursor-pointer list-none font-bold text-ink-900">{esc(q)}</summary><p class="mt-2 text-sm leading-relaxed text-ink-700">{esc(a)}</p></details>' for q, a in items) + "</div></section>"
    ld = {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items]}
    return html_, ld


def render_compat_chart(core: dict, cfg: dict) -> str:
    """영양제 궁합표 — 궁합 데이터 전체를 성분별로 펼친 정적 페이지 ('영양제 궁합표'·'같이 먹으면 안되는 영양제 표' 검색용)."""
    m = chart_model(core)
    by_id, cats, types = core["by_id"], core["categories"], core["types"]
    n, total = m["counts"], m["total"]
    tool = "compatibility.html"
    title = f"영양제 궁합표 — 같이 먹으면 좋은 조합·시간을 나눠야 할 조합 한눈에 | {cfg['name']}"
    desc = (f"성분 {len(by_id)}종 사이 조합 {total}쌍의 영양제 궁합표. 함께 먹으면 좋은 궁합 {n['synergy']}쌍, 시간을 띄우거나 용량에 주의할 궁합 {n['caution']}쌍을 "
            f"한눈에 보는 표와 성분별 목록으로 정리했습니다. 칼슘과 철분, 비타민 D와 칼슘처럼 자주 묻는 조합을 바로 확인하고 궁합 체크로 이어집니다.")
    faq_items = [
        ("영양제 궁합표는 어떤 기준으로 만들었나요?", f"성분 사전 {len(by_id)}종 사이의 조합을 흡수 경쟁, 기능 보완, 중복 섭취 가능성을 기준으로 '함께 먹으면 좋아요', '시간을 띄우거나 용량 주의', '특별한 상호작용 없음'으로 나눴습니다. 현재 {total}쌍이 등록되어 있으며, 식약처 인정 기능성 범위의 일반 정보이고 의학적 조언이 아닙니다."),
        ("'주의'로 표시된 영양제는 아예 같이 먹으면 안 되나요?", "대부분은 같은 시간에 먹으면 흡수가 줄어드는 조합이라, 표에 적힌 간격(보통 2시간)을 두거나 끼니를 나누면 됩니다. 궁합 체크에서 성분을 고르면 간격을 고려한 하루 복용 시간표를 자동으로 만들어 줍니다."),
        ("표에 없는 조합은 어떻게 확인하나요?", "표의 '–'는 아직 데이터에 없는 조합입니다. 궁합 체크에서 두 성분을 고르면 식이섬유 계열의 간격, 종합비타민과의 중복, 지용성 성분의 식후 섭취 같은 규칙으로 판정해 보여줍니다."),
    ]
    faq_html, faq_ld = faq_block(faq_items)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "영양제 궁합 체크", "item": page_url(cfg, tool)},
            {"@type": "ListItem", "position": 3, "name": "영양제 궁합표", "item": page_url(cfg, CHART_PATH)}]},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=desc, path=CHART_PATH, root="./", keywords="영양제 궁합표, 영양제 궁합, 같이 먹으면 안되는 영양제, 같이 먹으면 좋은 영양제, 영양제 조합표", og_type="website", ld=ld)

    # 1) 자주 찾는 성분 행렬
    ids = m["matrix"]["ids"]
    cells = m["matrix"]["cells"]
    head_row = "".join(f'<th scope="col"><a href="#{esc(b)}">{esc(short_name(by_id[b]["name"]))}</a></th>' for b in ids)
    body_rows = ""
    for a in ids:
        tds = ""
        for b in ids:
            t = cells[a][b]
            if t == "self":
                tds += '<td class="chart-self" aria-hidden="true"></td>'
            elif t:
                label = types.get(t, {}).get("label", t)
                tds += f'<td class="chart-cell chart-{esc(t)}"><a href="{tool}?items={esc(a)},{esc(b)}" title="{esc(short_name(by_id[a]["name"]))} + {esc(short_name(by_id[b]["name"]))}: {esc(label)}">{CHART_SYMBOL[t]}<span class="sr-only"> {esc(label)}</span></a></td>'
            else:
                tds += f'<td class="chart-cell chart-none"><a href="{tool}?items={esc(a)},{esc(b)}" title="데이터에 없는 조합 — 궁합 체크에서 규칙으로 판정">–<span class="sr-only"> 데이터 없음</span></a></td>'
        body_rows += f'<tr><th scope="row"><a href="#{esc(a)}">{esc(short_name(by_id[a]["name"]))}</a></th>{tds}</tr>'
    legend = "".join(f'<span class="chart-legend-item"><span class="chart-cell chart-{t}">{CHART_SYMBOL[t]}</span>{esc(types.get(t, {}).get("label", t))}</span>' for t in ("synergy", "caution", "neutral")) + \
        '<span class="chart-legend-item"><span class="chart-cell chart-none">–</span>데이터 없음 (궁합 체크에서 규칙으로 판정)</span>'
    matrix_html = (f'<section id="matrix" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">한눈에 보는 영양제 궁합표 — 자주 찾는 성분 {len(ids)}종</h2>'
                   f'<p class="mt-1 text-sm text-ink-500">칸을 누르면 그 조합의 이유와 복용 시간표를 궁합 체크에서 바로 볼 수 있습니다. 행·열 이름을 누르면 아래 성분별 목록으로 이동합니다.</p>'
                   f'<div class="chart-matrix-wrap mt-4"><table class="chart-matrix"><caption class="sr-only">자주 찾는 영양제 성분 {len(ids)}종의 궁합 행렬</caption><thead><tr><th scope="col"><span class="sr-only">성분</span></th>{head_row}</tr></thead><tbody>{body_rows}</tbody></table></div>'
                   f'<p class="chart-legend mt-3">{legend}</p></section>')

    # 2) 분류별 성분 블록
    def chip(pid: str, p: dict, t: str) -> str:
        extra = f' · {p["hours"]}시간 간격' if t == "caution" and p.get("hours") else (" ★" if t == "synergy" and p.get("level", 0) >= 3 else "")
        return f'<a class="chart-chip chart-chip-{t}" href="{tool}?items={esc(pid)},{esc(p["id"])}" title="{esc(p["title"])}">{esc(p["name"])}{esc(extra)}</a>'

    blocks = ""
    for ckey, cat in cats.items():
        items = [it for it in by_id.values() if it["category"] == ckey]
        if not items:
            continue
        arts = ""
        for it in sorted(items, key=lambda x: x["name"]):
            g = m["partners"][it["id"]]
            groups = ""
            for t, label in (("synergy", "함께 먹으면 좋아요"), ("caution", "시간을 띄우거나 용량 주의"), ("avoid", "같이 먹지 않는 게 좋아요")):
                if g[t]:
                    groups += f'<div class="chart-group"><span class="badge badge-{t}">{esc(label)} {len(g[t])}</span><span class="chart-chips">{"".join(chip(it["id"], p, t) for p in g[t])}</span></div>'
            if g["neutral"]:
                groups += f'<details class="chart-neutral"><summary>특별한 상호작용 없음 {len(g["neutral"])}가지 — 같은 시간에 먹어도 무방</summary><p>{esc(", ".join(p["name"] for p in g["neutral"]))}</p></details>'
            if not groups:
                groups = '<p class="text-sm text-ink-400">등록된 궁합 정보가 없습니다. 궁합 체크에서 규칙으로 판정합니다.</p>'
            arts += (f'<article id="{esc(it["id"])}" class="chart-row scroll-mt-28"><h4 class="chart-row-title"><a href="i/{esc(it["id"])}.html">{esc(it["name"])}</a>'
                     f'<a class="chart-tool" href="{tool}?items={esc(it["id"])}">궁합 체크 <i data-lucide="arrow-right" class="h-3.5 w-3.5"></i></a></h4>{groups}</article>')
        blocks += f'<div id="cat-{esc(ckey)}" class="scroll-mt-24"><h3 class="mt-8 flex items-center gap-2 text-xl font-extrabold text-ink-900"><span class="badge {cat_class(cat.get("color", ""))}">{esc(cat.get("label", ckey))}</span><span class="text-sm font-semibold text-ink-400">{len(items)}종</span></h3><div class="mt-3 space-y-3">{arts}</div></div>'
    cat_chips = "".join(f'<a href="#cat-{esc(k)}" class="chip">{esc(c.get("label", k))}</a>' for k, c in cats.items() if any(it["category"] == k for it in by_id.values()))

    body = f"""
<body data-page="compat" data-path="{CHART_PATH}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="index.html">홈</a> › <a class="hover:text-brand-700" href="{tool}">영양제 궁합 체크</a> › <span class="text-ink-800">영양제 궁합표</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="heart-handshake"></i> 영양제 궁합표</p>
      <h1 class="page-title mt-3">영양제 궁합표: 같이 먹어도 되는 조합, 나눠 먹어야 하는 조합</h1>
      <p class="page-lead mt-4 max-w-3xl">성분 사전 <strong>{len(by_id)}종</strong> 사이의 조합 <strong>{total}쌍</strong>을 한 장에 펼쳤습니다. 함께 먹으면 좋은 궁합 {n['synergy']}쌍, 시간을 띄우거나 용량에 주의할 궁합 {n['caution']}쌍, 특별한 상호작용이 없는 조합 {n['neutral']}쌍입니다. 먹고 있는 영양제를 모두 고르려면 궁합 체크가, 성분 하나의 궁합을 훑어보려면 이 표가 빠릅니다.</p>
      <div class="mt-6 flex flex-wrap gap-3"><a href="{tool}" class="btn-primary"><i data-lucide="heart-handshake"></i>내 영양제로 궁합 체크 <i data-lucide="arrow-right"></i></a><a href="{TIMING_PATH}" class="btn-outline"><i data-lucide="calendar-days"></i>영양제 복용 시간표</a></div>
      <div class="mt-5 flex flex-wrap gap-2"><a href="#matrix" class="chip">한눈에 보기</a>{cat_chips}</div>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      {matrix_html}
      <section id="by-ingredient" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">성분별 영양제 궁합표 — 전체 {len(by_id)}종</h2>
        <p class="mt-1 text-sm text-ink-500">성분 이름을 누르면 효능·권장량·먹는 시간을, 조합 칩을 누르면 그 조합의 이유를 궁합 체크에서 봅니다. ★는 특히 잘 맞는 조합, '2시간 간격'은 같은 시간에 먹지 않는 것이 좋은 조합입니다.</p>
        {blocks}
      </section>
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">궁합표 읽는 법</h2><ul class="list-dot mt-3 text-sm text-ink-700">
        <li>'함께 먹으면 좋아요'는 흡수나 기능을 서로 돕는 조합입니다. 같은 시간, 같은 끼니에 드셔도 됩니다.</li>
        <li>'시간을 띄우거나 용량 주의'는 같은 시간에 먹으면 흡수가 줄거나 중복되는 조합입니다. 표에 적힌 간격만 지키면 두 가지 모두 드실 수 있습니다.</li>
        <li>'특별한 상호작용 없음'은 같은 시간에 먹어도 무방하다는 뜻이며, 효과를 보장한다는 뜻은 아닙니다.</li>
        <li>약을 복용 중이라면 <a class="font-bold text-brand-700 underline" href="guide/with-medication.html">약과 영양제 가이드</a>를 먼저 읽고 약사·의사와 상의하세요. 원칙은 <a class="font-bold text-brand-700 underline" href="guide/how-to-combine.html">영양제 조합 기본 원칙</a>과 <a class="font-bold text-brand-700 underline" href="guide/do-not-take-together.html">같이 먹으면 안되는 영양제 조합</a> 가이드에 있습니다.</li>
      </ul></section>
      {faq_html}
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def render_timing_chart(core: dict, cfg: dict) -> str:
    """영양제 복용 시간표 — 성분별 권장 시간대를 한 장에 모은 정적 페이지 ('영양제 복용 시간표'·'영양제 먹는 시간표' 검색용)."""
    by_id, cats = core["by_id"], core["categories"]
    tm = timing_model(list(by_id.values()), cats)
    rows, slots = tm["rows"], tm["slots"]
    title = f"영양제 복용 시간표 — 아침·점심·저녁·공복·식후, 성분별 먹는 시간 한눈에 | {cfg['name']}"
    desc = (f"성분 {len(rows)}종의 영양제 복용 시간표. 아침 공복·아침 식후·식전·점심 식후·저녁 식후·취침 전 여섯 시간대로 나눠 기본 시간대와 대체 시간대, 지용성 여부를 정리했습니다. "
            f"내 영양제에 저장하면 궁합 간격까지 반영한 하루 시간표가 만들어집니다.")

    def names(key: str) -> str:
        return ", ".join(r["name"] for r in rows if r["slot"] == key)

    faq_items = [
        ("영양제는 아침에 먹나요, 저녁에 먹나요?", f"성분마다 다릅니다. 지용성 성분(비타민 A·D·E·K, 오메가3, 루테인, 코엔자임Q10 등 {len(tm['fat'])}종)은 지방이 포함된 식사 직후가 흡수에 유리하고, 아침 공복이 기본인 성분은 {names('morning_empty') or '없음'}, 취침 전이 기본인 성분은 {names('bedtime') or '없음'}입니다. 표의 '기본 시간대'와 '대체 시간대' 안에서 생활 리듬에 맞춰 고르면 됩니다."),
        ("여러 영양제를 한 번에 먹어도 되나요?", "대부분은 같은 시간에 드셔도 되지만, 칼슘과 철분처럼 흡수를 서로 방해하는 조합은 2시간 정도 간격을 두는 것이 좋습니다. 어떤 조합이 그런지는 영양제 궁합표에서 확인할 수 있습니다."),
        ("내 영양제에 맞는 시간표를 자동으로 만들 수 있나요?", "네. 내 영양제에 먹는 성분을 저장하면 기본 시간대에 배치하고, 간격이 필요한 조합은 대체 시간대로 옮겨 하루 시간표를 만들어 줍니다. 앱에서는 시간대별 복용 알림도 받을 수 있습니다."),
    ]
    faq_html, faq_ld = faq_block(faq_items)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "영양제 추천 가이드", "item": page_url(cfg, "guides.html")},
            {"@type": "ListItem", "position": 3, "name": "영양제 복용 시간표", "item": page_url(cfg, TIMING_PATH)}]},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=desc, path=TIMING_PATH, root="./", keywords="영양제 복용 시간표, 영양제 먹는 시간표, 영양제 복용 시간, 영양제 먹는 시간, 공복 영양제, 식후 영양제", og_type="website", ld=ld)

    # 1) 시간대별
    slot_cards = ""
    for s in slots:
        chips = "".join(f'<a class="chart-chip chart-chip-slot" href="#{esc(r["id"])}" title="{esc(r["label"])}">{esc(r["name"])}</a>' for r in s["items"]) or '<span class="text-sm text-ink-400">기본 시간대로 둔 성분이 없습니다</span>'
        slot_cards += (f'<div class="timing-slot"><h3 class="flex items-center gap-2 text-base font-extrabold text-ink-900"><i data-lucide="{esc(s["icon"])}" class="h-5 w-5 text-brand-600"></i>{esc(s["label"])}<span class="text-xs font-semibold text-ink-400">{len(s["items"])}종</span></h3>'
                       f'<p class="mt-0.5 text-xs text-ink-500">{esc(s["sub"])}</p><div class="chart-chips mt-3">{chips}</div></div>')

    # 2) 성분별 표
    trs = ""
    cur = None
    for r in rows:
        if r["category"] != cur:
            cur = r["category"]
            c = cats.get(cur, {})
            trs += f'<tr class="timing-cat"><th colspan="5" scope="colgroup"><span class="badge {cat_class(c.get("color", ""))}">{esc(c.get("label", cur))}</span></th></tr>'
        alts = " · ".join(SLOT_META[a]["label"] for a in r["alts"]) or "—"
        fat = ' <span class="badge badge-neutral">지용성</span>' if r["fat"] else ""
        trs += (f'<tr id="{esc(r["id"])}" class="scroll-mt-28"><th scope="row"><a href="i/{esc(r["id"])}.html">{esc(r["name"])}</a>{fat}</th>'
                f'<td>{esc(r["label"])}</td><td><span class="chart-chip chart-chip-slot chart-chip-static">{esc(SLOT_META[r["slot"]]["label"])}</span></td><td>{esc(alts)}</td><td class="timing-note">{esc(r["note"])}</td></tr>')
    table_html = (f'<div class="timing-table-wrap"><table class="timing-table"><caption class="sr-only">성분별 영양제 복용 시간표</caption>'
                  f'<thead><tr><th scope="col">성분</th><th scope="col">권장 시간</th><th scope="col">기본 시간대</th><th scope="col">대체 시간대</th><th scope="col">메모</th></tr></thead><tbody>{trs}</tbody></table></div>')

    # 3) 원칙 상자 (데이터에서)
    def box(title_: str, body_: str, icon: str) -> str:
        return f'<div class="rounded-2xl border border-ink-100 bg-white p-5 shadow-card"><h3 class="flex items-center gap-2 text-base font-extrabold text-ink-900"><i data-lucide="{icon}" class="h-5 w-5 text-brand-600"></i>{esc(title_)}</h3><p class="mt-2 text-sm leading-relaxed text-ink-700">{body_}</p></div>'
    fat_names = ", ".join(r["name"] for r in tm["fat"])
    boxes = box(f"지용성 {len(tm['fat'])}종은 식후", f"지방이 포함된 식사 직후가 흡수에 유리합니다: {esc(fat_names)}.", "droplet") + \
        box("공복이 기본인 성분", f"{esc(names('morning_empty') or '없음')}. 속이 불편하면 각 성분 페이지의 대체 시간대를 참고하세요.", "sunrise") + \
        box("취침 전이 기본인 성분", f"{esc(names('bedtime') or '없음')}. 잠들기 30~60분 전에 드세요.", "bed") + \
        box("식전이 기본인 성분", f"{esc(names('before_meal') or '없음')}. 식사 30분 전, 물과 함께가 기본입니다.", "timer")

    body = f"""
<body data-page="guides" data-path="{TIMING_PATH}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="index.html">홈</a> › <a class="hover:text-brand-700" href="guides.html">영양제 추천 가이드</a> › <span class="text-ink-800">영양제 복용 시간표</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="calendar-days"></i> 영양제 복용 시간표</p>
      <h1 class="page-title mt-3">영양제 복용 시간표: 성분별 먹는 시간 한눈에</h1>
      <p class="page-lead mt-4 max-w-3xl">성분 <strong>{len(rows)}종</strong>을 아침 공복·아침 식후·식전·점심 식후·저녁 식후·취침 전 여섯 시간대로 나눴습니다. 기본 시간대와 대체 시간대, 지용성 여부를 보고 생활 리듬에 맞춰 고르세요. 먹는 성분을 내 영양제에 저장하면 궁합 간격까지 반영한 하루 시간표가 자동으로 만들어집니다.</p>
      <div class="mt-6 flex flex-wrap gap-3"><a href="my.html" class="btn-primary"><i data-lucide="pill"></i>내 영양제로 시간표 만들기 <i data-lucide="arrow-right"></i></a><a href="guide/when-to-take.html" class="btn-outline"><i data-lucide="clock"></i>영양제 먹는 시간 가이드</a><a href="{CHART_PATH}" class="btn-outline"><i data-lucide="heart-handshake"></i>영양제 궁합표</a></div>
      <div class="mt-5 flex flex-wrap gap-2"><a href="#by-slot" class="chip">시간대별</a><a href="#by-ingredient" class="chip">성분별 표</a><a href="#rules" class="chip">원칙</a><a href="#faq" class="chip">자주 묻는 질문</a></div>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      <section id="by-slot" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">시간대별 영양제 복용 시간표</h2><p class="mt-1 text-sm text-ink-500">각 성분의 기본 시간대입니다. 성분을 누르면 아래 표의 권장 시간·대체 시간대·메모로 이동합니다.</p><div class="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{slot_cards}</div></section>
      <section id="by-ingredient" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">성분별 영양제 복용 시간표 — 전체 {len(rows)}종</h2><p class="mt-1 text-sm text-ink-500">권장 시간은 성분 사전의 섭취 시간 안내와 같습니다. 대체 시간대는 궁합 간격이 필요하거나 생활 리듬이 다를 때 옮길 수 있는 시간대입니다.</p><div class="mt-4">{table_html}</div></section>
      <section id="rules" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">한눈에 보는 원칙</h2><div class="mt-4 grid gap-4 md:grid-cols-2">{boxes}</div></section>
      {faq_html}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">함께 보면 좋은 가이드</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li><a class="font-bold text-brand-700 underline" href="guide/when-to-take.html">영양제 먹는 시간 총정리</a> — 아침·저녁·공복·식후 원칙</li><li><a class="font-bold text-brand-700 underline" href="guide/empty-stomach.html">공복에 먹어도 되는 영양제</a> — 속쓰림 없이 먹는 법</li><li><a class="font-bold text-brand-700 underline" href="guide/how-to-combine.html">영양제 조합 기본 원칙</a> — 먹는 순서와 나눠 먹는 조합</li><li><a class="font-bold text-brand-700 underline" href="{CHART_PATH}">영양제 궁합표</a> — 간격이 필요한 조합 전체</li></ul></section>
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


# ---------------------------------------------------------------- 셀프체크 (finder.html — data/finder.json 의 질문으로 정적 폼 생성, 결과는 assets/js/pages/finder.js)
FINDER_PATH = "finder.html"


def validate_finder(data: dict, valid_ids: set[str], guide_slugs: set[str]) -> None:
    """data/finder.json 무결성: 질문·옵션 id 중복, 규칙이 가리키는 질문·옵션·가이드 slug, restrictTo, 인기 성분 id. 어긋나면 빌드 실패."""
    qs: dict[str, dict] = {}
    for q in data.get("questions", []):
        if q["id"] in qs:
            raise SystemExit(f"finder.json: 질문 id 중복 {q['id']}")
        qs[q["id"]] = q
        ids = [o["id"] for o in q.get("options", [])]
        if len(ids) != len(set(ids)):
            raise SystemExit(f"finder.json: 질문 {q['id']} 의 옵션 id 중복")
        for pid in q.get("popular", []):
            if pid not in valid_ids:
                raise SystemExit(f"finder.json: 질문 {q['id']} 의 popular 에 없는 성분 id {pid}")
    for n, r in enumerate(data.get("rules", [])):
        for qid, vals in (r.get("if") or {}).items():
            if qid not in qs:
                raise SystemExit(f"finder.json: 규칙 {n} 이 모르는 질문 {qid} 을 참조")
            ok = {o["id"] for o in qs[qid].get("options", [])}
            for v in vals:
                if v not in ok:
                    raise SystemExit(f"finder.json: 규칙 {n} 의 {qid} 에 없는 옵션 {v}")
        for s in list(r.get("guides", [])) + list(r.get("restrictTo", [])):
            if s not in guide_slugs:
                raise SystemExit(f"finder.json: 규칙 {n} 이 없는 가이드 slug {s} 를 참조")
        if not r.get("guides") and not r.get("flags"):
            raise SystemExit(f"finder.json: 규칙 {n} 에 guides 또는 flags 가 필요")
    log.info("셀프체크 규칙 검증 통과: 질문 %d개 · 규칙 %d개", len(qs), len(data.get("rules", [])))


def render_finder(data: dict, core: dict, cfg: dict) -> str:
    """나에게 맞는 영양제 찾기 — 질문 폼은 정적 HTML(검색엔진·JS 없는 환경), 결과는 pages/finder.js 가 그린다."""
    by_id = core["by_id"]
    questions = data.get("questions", [])
    title = f"나에게 맞는 영양제 추천 — 1분 셀프체크로 성분·궁합·복용 시간표까지 | {cfg['name']}"
    desc = ("연령·성별·고민·생활 습관·복용 중인 약·이미 먹는 영양제를 고르면 가이드 87편의 핵심 성분에서 나에게 맞는 영양제 성분을 추천하고, "
            "추천 조합의 궁합과 하루 복용 시간표까지 한 번에 보여줍니다. 답변은 저장되지 않으며 결과는 링크로 공유할 수 있습니다.")
    faq_items = [
        ("셀프체크는 어떤 기준으로 영양제를 추천하나요?", "답변을 고민별·대상별 가이드에 연결하고, 그 가이드들이 식약처 인정 기능성을 기준으로 꼽은 핵심 성분을 가중 합산해 상위 성분을 보여줍니다. 특정 제품이나 브랜드를 추천하지 않으며, 결과는 일반 건강 정보이고 의학적 진단·처방이 아닙니다."),
        ("임신 중이거나 약을 먹고 있어도 써도 되나요?", "임신·수유·어린이는 해당 가이드의 성분 범위 안에서만 추천하고, 약을 복용 중이면 약 복용자 가이드와 주의 안내를 함께 보여줍니다. 어떤 경우든 새 영양제를 시작하기 전에 의사·약사와 상의하세요."),
        ("답변이 저장되나요?", "아니요. 답변은 서버로 보내지 않고 결과 화면의 주소(링크)에만 담깁니다. 결과를 내 영양제에 추가하면 그 성분 목록만 이 기기의 브라우저에 저장됩니다."),
    ]
    faq_html, faq_ld = faq_block(faq_items)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "영양제 추천 가이드", "item": page_url(cfg, "guides.html")},
            {"@type": "ListItem", "position": 3, "name": "나에게 맞는 영양제 찾기", "item": page_url(cfg, FINDER_PATH)}]},
        {"@type": "WebApplication", "name": "나에게 맞는 영양제 찾기 (셀프체크)", "applicationCategory": "HealthApplication", "operatingSystem": "Web", "url": page_url(cfg, FINDER_PATH),
         "description": "질문 6개로 추천 성분·궁합·복용 시간표를 보여주는 영양제 셀프체크", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "KRW"}},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=desc, path=FINDER_PATH, root="./", keywords="영양제 추천, 나에게 맞는 영양제, 영양제 셀프체크, 영양제 테스트, 영양제 조합 추천, 영양제 궁합",
                     og_type="website", extra_scripts='<script src="assets/js/illus.js" defer></script><script src="assets/js/schedule.js" defer></script><script src="assets/js/finder.js" defer></script><script src="assets/js/pages/finder.js" defer></script>', ld=ld)

    def option(q: dict, o: dict) -> str:
        kind = "radio" if q.get("type") == "single" else "checkbox"
        ex = ' data-exclusive="1"' if o.get("exclusive") else ""
        return f'<label class="finder-opt"><input type="{kind}" name="{esc(q["id"])}" value="{esc(o["id"])}"{ex}><span>{esc(o["label"])}</span></label>'

    fields = ""
    for n, q in enumerate(questions, 1):
        hint = f'<p class="finder-hint">{esc(q["hint"])}</p>' if q.get("hint") else ""
        if q.get("type") == "ingredients":
            chips = "".join(f'<label class="finder-opt"><input type="checkbox" name="{esc(q["id"])}" value="{esc(i)}"><span>{esc(by_id[i]["name"])}</span></label>' for i in q.get("popular", []) if i in by_id)
            body = (f'<div class="finder-opts" id="have-opts">{chips}</div>'
                    f'<div class="finder-search mt-3"><label for="have-search" class="sr-only">다른 성분 검색</label><i data-lucide="search" class="finder-search-icon"></i>'
                    f'<input id="have-search" type="search" placeholder="다른 성분 검색해 추가 (예: 비오틴, 아르기닌)" autocomplete="off"><ul id="have-list" class="finder-search-list" role="listbox" hidden></ul></div>')
        else:
            body = f'<div class="finder-opts">{"".join(option(q, o) for o in q.get("options", []))}</div>'
        fields += (f'<fieldset class="finder-q" data-q="{esc(q["id"])}"{" data-max=" + chr(34) + str(q["max"]) + chr(34) if q.get("max") else ""}>'
                   f'<legend><span class="finder-num">{n}</span>{esc(q["title"])}{" <span class=" + chr(34) + "finder-req" + chr(34) + ">필수</span>" if q.get("required") else ""}</legend>{hint}{body}</fieldset>')

    body = f"""
<body data-page="guides" data-path="{FINDER_PATH}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="index.html">홈</a> › <a class="hover:text-brand-700" href="guides.html">영양제 추천 가이드</a> › <span class="text-ink-800">나에게 맞는 영양제 찾기</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="sparkles"></i> 영양제 셀프체크</p>
      <h1 class="page-title mt-3">나에게 맞는 영양제 추천, 1분 셀프체크</h1>
      <p class="page-lead mt-4 max-w-3xl">연령·고민·생활 습관·복용 중인 약을 고르면 가이드 <strong>{len(core.get("guides", []))}편</strong>이 꼽은 핵심 성분 가운데 나에게 맞는 성분을 추천하고, 추천 조합의 <strong>궁합</strong>과 <strong>하루 복용 시간표</strong>까지 한 번에 보여줍니다. 제품이 아니라 성분을 추천하며, 답변은 저장하지 않습니다.</p>
      <ul class="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm text-ink-500">
        <li class="inline-flex items-center gap-1.5"><i data-lucide="list-checks" class="h-4 w-4 text-brand-600"></i>질문 {len(questions)}개, 약 1분</li>
        <li class="inline-flex items-center gap-1.5"><i data-lucide="heart-handshake" class="h-4 w-4 text-brand-600"></i>추천 조합의 궁합·시간표 자동 생성</li>
        <li class="inline-flex items-center gap-1.5"><i data-lucide="share-2" class="h-4 w-4 text-brand-600"></i>결과를 링크로 공유, 내 영양제에 저장</li>
      </ul>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-12 px-4 py-12 sm:px-6">
      <form id="finder-form" method="get" action="{FINDER_PATH}" class="finder-form" novalidate>
        <div class="finder-progress" aria-live="polite"><div class="finder-progress-bar"><span id="finder-bar" style="width:0%"></span></div><p id="finder-progress-text" class="text-xs text-ink-500">질문 {len(questions)}개 중 0개 답함</p></div>
        {fields}
        <div class="finder-actions"><button type="submit" class="btn-primary"><i data-lucide="sparkles"></i>결과 보기 <i data-lucide="arrow-right"></i></button><button type="button" class="btn-outline" id="finder-reset"><i data-lucide="rotate-ccw"></i>처음부터</button><p id="finder-error" class="text-sm font-semibold text-rose-700" hidden></p></div>
      </form>
      <section id="result" class="finder-result scroll-mt-24" hidden aria-live="polite"></section>
      <section id="how" class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">어떻게 추천하나요</h2><ul class="list-dot mt-3 text-sm text-ink-700">
        <li>답변을 고민별·대상별 <a class="font-bold text-brand-700 underline" href="guides.html">영양제 추천 가이드</a>에 연결하고, 각 가이드가 식약처 인정 기능성을 기준으로 꼽은 핵심 성분을 가중 합산해 상위 성분을 보여줍니다.</li>
        <li>추천 성분과 이미 먹는 성분의 조합은 <a class="font-bold text-brand-700 underline" href="compatibility-chart.html">영양제 궁합표</a>와 같은 데이터로 판정하고, 하루 시간표는 <a class="font-bold text-brand-700 underline" href="timing-chart.html">영양제 복용 시간표</a>의 기본 시간대와 간격 규칙으로 만듭니다.</li>
        <li>어린이·청소년·임신·수유는 해당 가이드의 성분 범위 안에서만 추천하고, 약을 복용 중이면 약 복용자 가이드와 주의 안내를 함께 보여줍니다.</li>
        <li>건강기능식품은 질병의 예방·치료 목적이 아닙니다. 결과는 참고용 일반 정보이며, 새 영양제를 시작하기 전에 의사·약사와 상의하세요.</li>
      </ul></section>
      {faq_html}
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def build_finder(core: dict, cfg: dict, guides: dict) -> None:
    data = read_json(DATA_DIR / "finder.json", None)
    if not data:
        log.warning("data/finder.json 이 없어 셀프체크 페이지를 만들지 않습니다")
        return
    validate_finder(data, set(core["by_id"].keys()), {g["slug"] for g in guides.get("items", [])})
    (ROOT / FINDER_PATH).write_text(render_finder(data, core, cfg), encoding="utf-8")
    log.info("셀프체크 페이지 생성 (%s)", FINDER_PATH)


# ---------------------------------------------------------------- 기능성별 허브 (functions.html · function/<id>.html — data/functions.json 의 정규화 표로 성분·원료·제품을 묶는다)
FUNCTION_DIR = ROOT / "function"
FUNCTIONS_HUB = "functions.html"
FUNCTION_TOP_PRODUCTS = 12
FUNCTION_MAX_MATERIALS = 40


def _fn_norm(s) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def function_matcher(item: dict):
    """기능성 항목의 match(OR 정규식)·exclude 로 '공백을 뺀 문구'를 판정하는 함수. exclude 에 걸린 조각을 지운 뒤에도 match 가 남아야 참."""
    m = re.compile("|".join(item["match"]))
    x = re.compile("|".join(item["exclude"])) if item.get("exclude") else None

    def hit(text) -> bool:
        t = _fn_norm(text)
        if not t or not m.search(t):
            return False
        return bool(m.search(x.sub("", t))) if x else True
    return hit


def validate_functions(data: dict, guide_slugs: set[str]) -> None:
    """data/functions.json 무결성: 필수 필드·id 형식·중복·그룹·정규식·가이드 slug."""
    groups = (data.get("_meta") or {}).get("groups") or {}
    seen: set[str] = set()
    for it in data.get("items", []):
        for k in ("id", "group", "label", "claim", "icon", "match", "intro"):
            if not it.get(k):
                raise SystemExit(f"functions.json: '{it.get('id') or it.get('label')}' 에 {k} 가 없음")
        if not re.fullmatch(r"[a-z0-9-]+", it["id"]):
            raise SystemExit(f"functions.json: id 형식 오류 {it['id']}")
        if it["id"] in seen:
            raise SystemExit(f"functions.json: id 중복 {it['id']}")
        seen.add(it["id"])
        if it["group"] not in groups:
            raise SystemExit(f"functions.json: '{it['id']}' 의 group {it['group']} 이 _meta.groups 에 없음")
        try:
            function_matcher(it)
        except re.error as e:
            raise SystemExit(f"functions.json: '{it['id']}' 정규식 오류 — {e}") from e
        for s in it.get("guides", []):
            if s not in guide_slugs:
                raise SystemExit(f"functions.json: '{it['id']}' 이 없는 가이드 slug {s} 를 참조")
    log.info("기능성 정규화 표 검증 통과: %d개", len(seen))


def load_products_detail() -> list[dict]:
    items: dict[str, dict] = {}
    for f in sorted((DATA_DIR / "products" / "detail").glob("*.json")):
        for it in (read_json(f, {}) or {}).get("items", []):
            items.setdefault(it["id"], it)
    return list(items.values())


def function_model(data: dict, core: dict, materials: list[dict], products: list[dict], guides: list[dict], weight=None) -> dict:
    """기능성마다 성분(성분 사전 mfdsFunction)·개별인정 원료(function)·신고 제품(function)을 모으고 성분→기능성 역색인을 만든다.
    weight(name, company) 는 제품 상위 노출용 브랜드 가중치(없으면 신고일 순)."""
    by_id, cats = core["by_id"], core["categories"]
    cat_order = list(cats.keys())
    guide_by_slug = {g["slug"]: g for g in guides}
    wcache: dict[str, int] = {}

    def w(p: dict) -> int:
        if p["id"] not in wcache:
            wcache[p["id"]] = int(weight(p.get("name"), p.get("company"))) if weight else 0
        return wcache[p["id"]]

    out = []
    by_ing: dict[str, list[str]] = {}
    for it in data.get("items", []):
        hit = function_matcher(it)
        ings = sorted((i for i in by_id.values() if hit(i.get("mfdsFunction"))), key=lambda i: (cat_order.index(i["category"]) if i["category"] in cat_order else 99, i["name"]))
        ids = {i["id"] for i in ings}
        mats = sorted((m for m in materials if hit(m.get("function"))), key=lambda m: (-int(m.get("companyCount") or 0), str(m.get("name") or "")))
        prods = [p for p in products if hit(p.get("function"))]
        top = sorted(prods, key=lambda p: (w(p), p.get("registeredAt") or ""), reverse=True)[:FUNCTION_TOP_PRODUCTS]
        pairs = [p for p in core["pairs"] if p["pair"][0] in ids and p["pair"][1] in ids and p.get("type") in ("synergy", "caution", "avoid")]
        pairs.sort(key=lambda p: ({"synergy": 0, "caution": 1, "avoid": 2}[p["type"]], -p.get("level", 0)))
        manual = [guide_by_slug[s] for s in it.get("guides", []) if s in guide_by_slug]
        auto = sorted((g for g in guides if g["slug"] not in it.get("guides", [])), key=lambda g: (-len(ids & {x["id"] for x in g.get("ingredients", [])}), g["slug"]))
        auto = [g for g in auto if ids & {x["id"] for x in g.get("ingredients", [])}]
        rel_guides = (manual + auto)[:6]
        for i in ings:
            by_ing.setdefault(i["id"], []).append(it["id"])
        out.append({"fn": it, "ingredients": ings, "materials": mats, "products": {"total": len(prods), "top": top}, "pairs": pairs, "guides": rel_guides})
    return {"items": out, "by_ingredient": by_ing}


def _fn_claim_short(it: dict) -> str:
    return it["claim"].split(" · ")[0]


def render_function(entry: dict, model: dict, core: dict, cfg: dict, guides_types: dict) -> str:
    it, ings, mats, prods, pairs, rel_guides = entry["fn"], entry["ingredients"], entry["materials"], entry["products"], entry["pairs"], entry["guides"]
    by_id, cats, types = core["by_id"], core["categories"], core["types"]
    groups = (core.get("functions_meta") or {}).get("groups") or {}
    path = f"function/{it['id']}.html"
    n_i, n_m, n_p = len(ings), len(mats), prods["total"]
    title = f"{it['label']} 영양제 — 식약처 인정 기능성 성분·원료·신고 제품 총정리 | {cfg['name']}"
    desc = f"식약처 인정 기능성 '{_fn_claim_short(it)}'을 표시할 수 있는 성분 {n_i}종, 개별인정 원료 {n_m}종, 신고 제품 {n_p:,}건을 한 장에 정리했습니다. {it['intro']}"[:300]
    ids = [i["id"] for i in ings]
    faq_items = [
        (f"'{_fn_claim_short(it)}'은 어떤 의미인가요?", "식품의약품안전처가 과학적 근거를 심사해 인정한 기능성 문구로, 인정된 원료를 정해진 양 이상 넣은 건강기능식품에만 표시할 수 있습니다. 질병의 예방이나 치료 효과를 뜻하지 않으며, 개인차가 있습니다."),
        (f"{it['label']} 영양제는 어떻게 고르나요?", "제품 라벨의 '기능성 내용'에 이 문구가 있는지, 원료명과 1일 섭취량이 인정 기준에 맞는지 확인하세요. 같은 기능성이라도 원료마다 작용 방식과 주의사항이 다르므로 성분 사전의 권장 섭취량·주의사항을 함께 보세요."),
        ("약을 먹고 있는데 함께 먹어도 되나요?", "일부 성분은 약의 흡수나 작용에 영향을 줄 수 있습니다. 성분 사전의 '약과 함께 먹을 때' 항목과 약과 영양제 가이드를 확인하고, 새로 시작하기 전에 의사·약사와 상의하세요."),
    ]
    faq_html, faq_ld = faq_block(faq_items)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "기능성별 영양제", "item": page_url(cfg, FUNCTIONS_HUB)},
            {"@type": "ListItem", "position": 3, "name": f"{it['label']} 영양제", "item": page_url(cfg, path)}]},
        {"@type": "CollectionPage", "name": f"{it['label']} 영양제 — 식약처 인정 성분·원료·제품", "url": page_url(cfg, path), "description": desc,
         "hasPart": [{"@type": "Thing", "name": i["name"], "url": page_url(cfg, f"i/{i['id']}.html")} for i in ings]},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=desc, path=path, root="../", keywords=f"{it['label']} 영양제, {_fn_claim_short(it)}, {it['label']} 건강기능식품, {it['label']} 기능성 원료, 영양제 추천", og_type="article", ld=ld)

    def ing_card(i: dict) -> str:
        cat = cats.get(i["category"], {})
        t = (i.get("timing") or {}).get("label", "")
        return (f'<article class="ing-card"><div class="flex items-start gap-3"><span class="finder-thumb">{photo_img(i["category"])}</span><div class="min-w-0 flex-1">'
                f'<span class="badge {cat_class(cat.get("color", ""))}">{esc(cat.get("label", ""))}</span><h3 class="mt-1 text-base font-extrabold text-ink-900"><a class="hover:text-brand-700" href="../i/{esc(i["id"])}.html">{esc(i["name"])}</a></h3>'
                f'<p class="mt-1 text-sm text-ink-700">{esc(i.get("mfdsFunction") or "")}</p>'
                f'<p class="mt-2 text-xs text-ink-500"><i data-lucide="clock" class="inline h-3.5 w-3.5 text-brand-600"></i> {esc(t)}{" · " + esc((i.get("dosage") or {}).get("daily", "")) if (i.get("dosage") or {}).get("daily") else ""}</p>'
                f'</div></div></article>')
    ings_html = (f'<div class="grid gap-3 md:grid-cols-2">{"".join(ing_card(i) for i in ings)}</div>'
                 f'<div class="mt-4 flex flex-wrap gap-2"><a href="../compatibility.html?items={esc(",".join(ids[:8]))}" class="btn-primary"><i data-lucide="heart-handshake"></i>이 성분들로 궁합·시간표 만들기 <i data-lucide="arrow-right"></i></a>'
                 f'<button type="button" class="btn-outline" data-my-add="{esc(",".join(ids[:8]))}"><i data-lucide="plus"></i>내 영양제에 추가</button></div>') if ings else \
        '<p class="rounded-2xl border border-dashed border-ink-200 bg-white p-5 text-sm text-ink-600">성분 사전에 아직 이 기능성의 단일 성분 페이지가 없습니다. 아래 개별인정 원료와 신고 제품을 참고하세요.</p>'

    mat_rows = "".join(
        f'<tr><th scope="row">{esc(m.get("name") or "")}</th><td>{esc(m.get("type") or "")}</td><td>{esc(m.get("recognitionNo") or "")}</td><td>{esc((m.get("recognizedAt") or "")[:10])}</td><td class="timing-note">{esc(str(m.get("function") or "")[:140])}</td></tr>'
        for m in mats[:FUNCTION_MAX_MATERIALS])
    mats_html = (f'<div class="timing-table-wrap"><table class="timing-table"><caption class="sr-only">{esc(it["label"])} 기능성이 인정된 원료</caption><thead><tr><th scope="col">원료명</th><th scope="col">구분</th><th scope="col">인정번호</th><th scope="col">인정일</th><th scope="col">인정 기능성 내용</th></tr></thead><tbody>{mat_rows}</tbody></table></div>'
                 + (f'<p class="mt-2 text-xs text-ink-500">상위 {FUNCTION_MAX_MATERIALS}건만 표시 (전체 {n_m}건) — <a class="font-bold text-brand-700 underline" href="../materials.html">기능성 원료 인정현황</a>에서 검색하세요.</p>' if n_m > FUNCTION_MAX_MATERIALS else "")) if mats else \
        '<p class="text-sm text-ink-500">이 기능성으로 따로 인정된 개별인정 원료가 없습니다(비타민·미네랄 등 고시형 영양소 기능).</p>'

    def prod_row(p: dict) -> str:
        chips = "".join(f'<a class="chart-chip" href="../i/{esc(x)}.html">{esc(by_id[x]["name"])}</a>' for x in [x for x in (p.get("ingredients") or []) if x in by_id][:6])   # 성분 칩은 6개까지
        return (f'<li class="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between"><div class="min-w-0"><a class="font-bold text-ink-900 hover:text-brand-700" href="../product.html?id={esc(p["id"])}">{esc(p["name"])}</a>'
                f'<span class="ml-2 text-xs font-semibold text-ink-500">{esc(p.get("company") or "")}</span><span class="ml-2 text-xs text-ink-400">신고 {esc((p.get("registeredAt") or "")[:10])}</span></div><div class="chart-chips">{chips}</div></li>')
    first_ing = ids[0] if ids else ""
    prods_html = (f'<ul class="divide-y divide-ink-100">{"".join(prod_row(p) for p in prods["top"])}</ul>'
                  f'<p class="mt-3 text-xs text-ink-500">식약처 품목제조신고 가운데 이 기능성을 표시한 제품 {n_p:,}건(2021-04 이후 수집분) 중 알려진 브랜드·최근 신고 순으로 {len(prods["top"])}건을 보여줍니다.'
                  + (f' 성분별 전체 목록은 <a class="font-bold text-brand-700 underline" href="../products.html?ingredient={esc(first_ing)}">제품 찾기</a>에서 보세요.' if first_ing else "") + "</p>") if prods["top"] else \
        '<p class="text-sm text-ink-500">수집 범위에서 이 기능성을 표시한 신고 제품을 찾지 못했습니다.</p>'

    pairs_html = ""
    if pairs:
        rows = "".join(
            f'<li class="finder-pair finder-pair-{esc(p["type"])}" style="{"border-color:#a7f3d0;background:#ecfdf5" if p["type"] == "synergy" else ""}"><span class="badge badge-{esc(p["type"])}">{esc(types.get(p["type"], {}).get("short", p["type"]))}</span><div><p class="font-bold text-ink-900">{esc(by_id[p["pair"][0]]["name"])} + {esc(by_id[p["pair"][1]]["name"])}{" · " + str(p["separateHours"]) + "시간 간격" if p.get("separateHours") else ""}</p><p class="text-sm text-ink-600">{esc(p.get("title", ""))}</p></div></li>'
            for p in pairs[:10])
        pairs_html = f'<section class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">이 성분들끼리의 궁합</h2><p class="mt-1 text-sm text-ink-500">같은 기능성 성분을 함께 먹을 때 알아둘 조합입니다. 전체는 <a class="font-bold text-brand-700 underline" href="../compatibility-chart.html">영양제 궁합표</a>에서 보세요.</p><ul class="mt-3 space-y-2">{rows}</ul></section>'

    timing_rows = "".join(f'<tr><th scope="row"><a href="../i/{esc(i["id"])}.html">{esc(i["name"])}</a></th><td>{esc((i.get("timing") or {}).get("label", ""))}</td><td class="timing-note">{esc((i.get("timing") or {}).get("note", ""))}</td></tr>' for i in ings)
    timing_html = (f'<section class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">먹는 시간</h2><div class="timing-table-wrap mt-3"><table class="timing-table"><caption class="sr-only">{esc(it["label"])} 성분의 섭취 시간</caption><thead><tr><th scope="col">성분</th><th scope="col">권장 시간</th><th scope="col">메모</th></tr></thead><tbody>{timing_rows}</tbody></table></div>'
                   f'<p class="mt-2 text-xs text-ink-500">전체 성분은 <a class="font-bold text-brand-700 underline" href="../timing-chart.html">영양제 복용 시간표</a>에서 보세요.</p></section>') if ings else ""

    guides_html = (f'<section class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">관련 가이드</h2><p class="mt-1 text-sm text-ink-500">어떤 성분을 어떻게 조합할지는 가이드에서 설명합니다.</p><div class="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{"".join(guide_card(g, guides_types, "../") for g in rel_guides)}</div></section>') if rel_guides else ""
    grp = groups.get(it["group"], {})
    body = f"""
<body data-page="ingredients" data-path="{path}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="../index.html">홈</a> › <a class="hover:text-brand-700" href="../{FUNCTIONS_HUB}">기능성별 영양제</a> › <span class="text-ink-800">{esc(it["label"])}</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="{esc(it["icon"])}"></i> {esc(grp.get("label", "기능성별 영양제"))}</p>
      <h1 class="page-title mt-3">{esc(it["label"])} 영양제: 식약처 인정 기능성 성분·원료·제품</h1>
      <blockquote class="fn-claim mt-4"><i data-lucide="badge-check" class="h-5 w-5 shrink-0 text-brand-600"></i><span>식약처 인정 기능성 — <strong>{esc(it["claim"])}</strong></span></blockquote>
      <p class="page-lead mt-4 max-w-3xl">{esc(it["intro"])}</p>
      <ul class="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm text-ink-600">
        <li class="inline-flex items-center gap-1.5"><i data-lucide="leaf" class="h-4 w-4 text-brand-600"></i>성분 사전 <strong>{n_i}종</strong></li>
        <li class="inline-flex items-center gap-1.5"><i data-lucide="microscope" class="h-4 w-4 text-brand-600"></i>개별인정 원료 <strong>{n_m}종</strong></li>
        <li class="inline-flex items-center gap-1.5"><i data-lucide="package" class="h-4 w-4 text-brand-600"></i>신고 제품 <strong>{n_p:,}건</strong></li>
      </ul>
      <div class="mt-5 flex flex-wrap gap-2"><a href="#ingredients" class="chip">성분</a><a href="#materials" class="chip">인정 원료</a><a href="#products" class="chip">신고 제품</a>{'<a href="#guides" class="chip">가이드</a>' if rel_guides else ""}<a href="#faq" class="chip">자주 묻는 질문</a></div>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      <section id="ingredients" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">이 기능성이 인정된 성분 {n_i}종</h2><p class="mt-1 text-sm text-ink-500">성분 사전에 있는 성분 가운데 식약처 인정 기능성 내용에 이 문구가 들어간 성분입니다. 성분을 누르면 효능·권장량·궁합·먹는 시간을 봅니다.</p><div class="mt-4">{ings_html}</div></section>
      <section id="materials" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">식약처 개별인정 원료 {n_m}종</h2><p class="mt-1 text-sm text-ink-500">식품안전나라 기능성 원료 인정현황에서 이 기능성이 인정된 원료입니다. 인정 업체가 많은 순으로 정렬했습니다.</p><div class="mt-4">{mats_html}</div></section>
      <section id="products" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">이 기능성을 표시한 신고 제품</h2><div class="mt-2">{prods_html}</div></section>
      {pairs_html}
      {timing_html}
      {('<div id="guides" class="scroll-mt-24">' + guides_html + '</div>') if guides_html else ""}
      {faq_html}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">함께 보면 좋은 페이지</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li><a class="font-bold text-brand-700 underline" href="../{FUNCTIONS_HUB}">기능성별 영양제 전체 목록</a></li><li><a class="font-bold text-brand-700 underline" href="../finder.html">나에게 맞는 영양제 찾기</a> — 고민과 상황으로 성분 추천</li><li><a class="font-bold text-brand-700 underline" href="../compatibility-chart.html">영양제 궁합표</a> · <a class="font-bold text-brand-700 underline" href="../timing-chart.html">영양제 복용 시간표</a></li><li><a class="font-bold text-brand-700 underline" href="../guide/with-medication.html">약과 영양제 가이드</a></li></ul></section>
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def render_functions_hub(model: dict, data: dict, core: dict, cfg: dict) -> str:
    groups = (data.get("_meta") or {}).get("groups") or {}
    items = model["items"]
    n = len(items)
    title = f"기능성별 영양제 — 식약처 인정 기능성 {n}가지로 찾는 성분·원료·제품 | {cfg['name']}"
    desc = f"체지방 감소·혈당·콜레스테롤·간·장·면역·눈·피부·뼈·관절·수면·기억력 등 식약처 인정 기능성 {n}가지별로 성분 사전의 성분, 개별인정 원료, 신고 제품 수를 한눈에 보고 각 기능성 페이지로 이동합니다."
    faq_items = [
        ("기능성 문구가 같으면 제품도 같은 효과인가요?", "같은 기능성 문구라도 원료와 1일 섭취량, 작용 방식이 다릅니다. 라벨의 원료명과 함량이 인정 기준에 맞는지 확인하고, 성분 사전에서 권장 섭취량·주의사항을 보세요."),
        ("고시형과 개별인정형은 무엇이 다른가요?", "고시형은 식약처가 건강기능식품공전에 올려 누구나 쓸 수 있는 원료(비타민·미네랄·홍삼 등)이고, 개별인정형은 특정 업체가 자료를 제출해 개별로 인정받은 원료입니다. 인정 기간과 업체가 정해져 있어 인정현황에서 확인할 수 있습니다."),
        ("기능성이 있으면 병을 치료할 수 있나요?", "아니요. 건강기능식품의 기능성은 인체의 정상 기능 유지나 생리 기능 활성화에 도움을 줄 수 있다는 뜻이며, 질병의 예방·치료 효과를 뜻하지 않습니다. 증상이 있으면 진료가 먼저입니다."),
    ]
    faq_html, faq_ld = faq_block(faq_items)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"}, {"@type": "ListItem", "position": 2, "name": "기능성별 영양제", "item": page_url(cfg, FUNCTIONS_HUB)}]},
        {"@type": "CollectionPage", "name": "기능성별 영양제", "url": page_url(cfg, FUNCTIONS_HUB), "hasPart": [{"@type": "WebPage", "name": f"{e['fn']['label']} 영양제", "url": page_url(cfg, f"function/{e['fn']['id']}.html")} for e in items]},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=desc, path=FUNCTIONS_HUB, root="./", keywords="기능성별 영양제, 식약처 인정 기능성, 건강기능식품 기능성 종류, 기능성 원료, 영양제 추천", og_type="website", ld=ld)
    secs = ""
    for gk, g in groups.items():
        es = [e for e in items if e["fn"]["group"] == gk]
        if not es:
            continue
        cards = "".join(
            f'<a class="fn-card" href="function/{esc(e["fn"]["id"])}.html"><span class="fn-card-icon"><i data-lucide="{esc(e["fn"]["icon"])}" class="h-5 w-5"></i></span><span class="min-w-0"><span class="block text-base font-extrabold text-ink-900">{esc(e["fn"]["label"])}</span>'
            f'<span class="mt-1 line-clamp-2 block text-xs text-ink-500">{esc(_fn_claim_short(e["fn"]))}</span><span class="mt-2 block text-xs font-semibold text-ink-600">성분 {len(e["ingredients"])} · 원료 {len(e["materials"])} · 제품 {e["products"]["total"]:,}</span></span></a>'
            for e in es)
        secs += f'<section id="{esc(gk)}" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">{esc(g.get("label", gk))}</h2><p class="mt-1 text-ink-500">{esc(g.get("desc", ""))}</p><div class="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{cards}</div></section>'
    body = f"""
<body data-page="ingredients" data-path="{FUNCTIONS_HUB}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="index.html">홈</a> › <span class="text-ink-800">기능성별 영양제</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="badge-check"></i> 식약처 인정 기능성으로 찾기</p>
      <h1 class="page-title mt-3">기능성별 영양제: 인정 기능성 {n}가지로 성분·원료·제품 찾기</h1>
      <p class="page-lead mt-4 max-w-3xl">영양제 라벨의 '기능성 내용'은 식약처가 심사해 인정한 문구만 쓸 수 있습니다. 기능성 문구 {n}가지를 기준으로 성분 사전의 성분, 개별인정 원료, 신고 제품을 묶었습니다. 고민에서 출발하려면 <a class="font-bold text-brand-700 underline" href="guides.html">영양제 추천 가이드</a>나 <a class="font-bold text-brand-700 underline" href="finder.html">셀프체크</a>가 빠릅니다.</p>
      <div class="mt-5 flex flex-wrap gap-2">{''.join(f'<a href="#{esc(k)}" class="chip">{esc(g.get("label", k))}</a>' for k, g in groups.items() if any(e["fn"]["group"] == k for e in items))}</div>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      {secs}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">읽는 법</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li>'성분'은 성분 사전에 단일 페이지가 있는 성분, '원료'는 식약처 개별인정 원료, '제품'은 수집 범위(2021-04 이후 신고) 안에서 그 기능성을 표시한 신고 제품 수입니다.</li><li>비타민·미네랄의 '~에 필요'는 영양소 기능 표시이고, 원료의 '~에 도움을 줄 수 있음'은 생리활성 기능성 표시입니다. 둘 다 식약처가 정한 문구입니다.</li><li>건강기능식품은 질병의 예방·치료 목적이 아닙니다. 약을 복용 중이면 <a class="font-bold text-brand-700 underline" href="guide/with-medication.html">약과 영양제 가이드</a>를 먼저 보세요.</li></ul></section>
      {faq_html}
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def prepare_functions(core: dict, guides_items: list[dict]) -> dict | None:
    """data/functions.json 을 읽어 검증하고 모델을 만든다 (성분 페이지의 기능성 칩이 먼저 필요하므로 main() 앞부분에서 호출)."""
    data = read_json(DATA_DIR / "functions.json", None)
    if not data:
        log.warning("data/functions.json 이 없어 기능성별 허브를 만들지 않습니다")
        return None
    validate_functions(data, {g["slug"] for g in guides_items})
    materials = (read_json(DATA_DIR / "materials.json", {}) or {}).get("items", [])
    products = load_products_detail()
    try:
        weight = load_brand_priority().weight
    except Exception:  # noqa: BLE001
        weight = None
    model = function_model(data, core, materials, products, guides_items, weight)
    model["data"] = data
    core["functions"] = model
    core["functions_meta"] = data.get("_meta") or {}
    return model


def write_functions(core: dict, cfg: dict, guides: dict) -> list[str]:
    """function/<id>.html · functions.html · data/functions-index.json 생성, 오래된 파일 정리. 생성한 기능성 id 목록을 돌려준다(사이트맵)."""
    model = core.get("functions")
    if not model:
        return []
    FUNCTION_DIR.mkdir(exist_ok=True)
    types = guides.get("_meta", {}).get("types", {})
    wanted = set()
    for e in model["items"]:
        p = FUNCTION_DIR / f"{e['fn']['id']}.html"
        p.write_text(render_function(e, model, core, cfg, types), encoding="utf-8")
        wanted.add(p.name)
    for stale in FUNCTION_DIR.glob("*.html"):
        if stale.name not in wanted:
            stale.unlink()
            log.info("삭제된 기능성 페이지 정리: %s", stale.name)
    (ROOT / FUNCTIONS_HUB).write_text(render_functions_hub(model, model["data"], core, cfg), encoding="utf-8")
    write_json(DATA_DIR / "functions-index.json", {
        "_meta": {"updatedAt": now_iso(), "note": "functions.json 의 요약 색인 — scripts/build_site.py 가 생성, 직접 수정하지 않음 (성분 페이지의 기능성 칩용)"},
        "items": [{"id": e["fn"]["id"], "label": e["fn"]["label"], "claim": _fn_claim_short(e["fn"]), "group": e["fn"]["group"], "icon": e["fn"]["icon"], "ingredients": [i["id"] for i in e["ingredients"]],
                   "counts": {"ingredients": len(e["ingredients"]), "materials": len(e["materials"]), "products": e["products"]["total"]}} for e in model["items"]],
    }, compact=True, quiet=True)
    log.info("기능성별 허브 생성: %s + function/ %d장", FUNCTIONS_HUB, len(wanted))
    return [e["fn"]["id"] for e in model["items"]]


def photo_img(category: str) -> str:
    """분류별 알약 사진 — assets/js/illus.js 의 photoFor(category) 와 같은 파일 대응표."""
    file = {"vitamin": "capsule-yellow", "mineral": "tablet-beige", "fatty-acid": "softgel-amber", "probiotic": "capsule-blue", "herbal": "capsule-green", "amino": "capsule-violet", "joint": "capsule-orange", "beauty": "capsule-pink"}.get(category, "tablet-beige")
    return f'<img src="../assets/images/home/{file}.webp" alt="" width="56" height="56" loading="lazy" decoding="async" class="h-full w-full object-cover">'


def build_charts(core: dict, cfg: dict) -> None:
    """영양제 궁합표·복용 시간표 정적 페이지 생성 (루트, sitemap 은 STATIC_PAGES 로)."""
    (ROOT / CHART_PATH).write_text(render_compat_chart(core, cfg), encoding="utf-8")
    (ROOT / TIMING_PATH).write_text(render_timing_chart(core, cfg), encoding="utf-8")
    log.info("영양제 궁합표·복용 시간표 생성 (%s · %s)", CHART_PATH, TIMING_PATH)


def build_sitemap(ingredients: list[dict], cfg: dict, data_date: str, guides: dict | None = None, functions: list[str] | None = None) -> None:
    today = now_iso()[:10]
    dynamic = ("index.html", "news.html", "products.html")
    # 주소는 Cloudflare Pages 가 실제로 서비스하는 확장자 없는 형태(홈은 /) — .html 주소는 리다이렉트되어 색인에 불리하다
    urls = [(page_url(cfg, p), "daily" if p in dynamic else "monthly", "1.0" if p == "index.html" else "0.8", today if p in dynamic else data_date) for p in STATIC_PAGES]
    urls += [(page_url(cfg, f"i/{it['id']}.html"), "monthly", "0.7", data_date) for it in ingredients]
    gdate = (guides or {}).get("_meta", {}).get("updatedAt") or data_date
    urls += [(page_url(cfg, f"guide/{g['slug']}.html"), "monthly", "0.8", gdate) for g in (guides or {}).get("items", [])]
    urls += [(page_url(cfg, f"function/{fid}.html"), "monthly", "0.7", data_date) for fid in (functions or [])]
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
    prepare_functions(core, core["guides"])   # 기능성별 허브 모델 (성분 페이지의 기능성 칩이 먼저 쓴다)

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
    build_charts(core, cfg)
    build_finder(core, cfg, guides)
    function_ids = write_functions(core, cfg, guides)
    build_sitemap(ingredients["items"], cfg, data_date, guides, function_ids)
    inject_verification(cfg)
    inject_pwa_tags()
    build_product_names()
    validate_drug_pairings(set(core["by_id"].keys()))
    ensure_drug_index()
    check_icons()
    build_sw()
    stamp_assets()
    products = read_json(DATA_DIR / "products.json", {"_meta": {}, "items": []})
    news = read_json(DATA_DIR / "news.json", {"_meta": {}, "items": []})
    materials = read_json(DATA_DIR / "materials.json", {"_meta": {}, "items": []})
    drugs_meta = (read_json(DATA_DIR / "drugs" / "names.json", {}) or {}).get("_meta", {})
    write_json(DATA_DIR / "meta.json", {
        "builtAt": now_iso(),
        "ingredients": len(ingredients["items"]),
        "pairs": len(interactions["pairs"]),
        "guides": len(guides.get("items", [])),
        "products": {"source": products.get("_meta", {}).get("source", "sample"), "updatedAt": products.get("_meta", {}).get("updatedAt"), "total": products.get("_meta", {}).get("total") or len(products.get("items", []))},   # products.json 은 최신 일부만 싣고 total 은 _meta 에
        "news": {"source": news.get("_meta", {}).get("source", "sample"), "updatedAt": news.get("_meta", {}).get("updatedAt"), "total": len(news.get("items", []))},
        "drugs": {"source": drugs_meta.get("source", "none"), "updatedAt": drugs_meta.get("updatedAt"), "total": drugs_meta.get("total", 0), "withNutrients": drugs_meta.get("withNutrients", 0)},
        "materials": {"source": materials.get("_meta", {}).get("source", "sample"), "updatedAt": materials.get("_meta", {}).get("updatedAt"), "total": len(materials.get("items", [])), "matched": materials.get("_meta", {}).get("matched", 0),
                      "ingredients": sorted(f.stem for f in (DATA_DIR / "materials").glob("*.json"))},
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
