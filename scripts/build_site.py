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
from drug_ingr_ko import to_korean  # noqa: E402
from common import DATA_DIR, KST, ROOT, env, log, now_iso, read_json, write_json  # noqa: E402

OUT_DIR = ROOT / "i"
GUIDE_DIR = ROOT / "guide"
STATIC_PAGES = ["index.html", "ingredients.html", "compatibility.html", "compatibility-chart.html", "timing-chart.html", "finder.html", "functions.html", "compare.html", "drug-guides.html", "glossary.html", "guides.html", "products.html", "news.html", "materials.html", "about.html", "terms.html", "privacy.html"]   # compatibility-chart·timing-chart 는 build_charts() 가 생성


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


_DIGEST_CACHE: dict[tuple[str, int, int], str] = {}   # (경로, 수정 시각 ns, 크기) → 해시


def asset_digest(path: Path) -> str:
    """자산 파일 내용 해시 앞 8자 (?v= 스탬프와 서비스워커 precache 가 같은 값을 쓴다). 없는 파일은 "0".
    줄끝을 LF 로 맞춘 뒤 해시: Windows 의 core.autocrlf 로 CRLF 가 된 체크아웃에서도 CI(Linux) 와 같은 값이 나오게.
    캐시 키에 수정 시각·크기를 넣어, 빌드 중 다시 쓰인 파일(?v= 스탬프된 my.html 등)은 옛 해시가 아니라 새 내용으로 다시 해시한다."""
    import hashlib
    if not path.exists():
        return "0"
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key not in _DIGEST_CACHE:
        _DIGEST_CACHE[key] = hashlib.sha1(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:8]
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


def build_sw(out_path: Path | None = None) -> str:
    """scripts/sw_template.js 에 버전과 precache 목록을 채워 루트 sw.js 를 생성한다 (sw.js 는 생성 파일). out_path 를 주면 그 파일에 쓴다(테스트). 버전을 돌려준다."""
    template = SW_TEMPLATE.read_text(encoding="utf-8")
    urls = precache_urls()
    ver = sw_version(template, urls, precache_extra_digests())
    out = template.replace('"__VERSION__"', json.dumps(ver)).replace("/*__PRECACHE__*/[]", json.dumps(urls, ensure_ascii=False))
    with open(out_path or (ROOT / "sw.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    log.info("sw.js 생성: precache %d개, 버전 %s", len(urls), ver)
    return ver


def stamp_and_build_sw(sw_out: Path | None = None) -> str:
    """HTML 의 ?v= 스탬프를 먼저 마친 뒤 서비스워커를 만든다 — 이 순서가 중요하다.
    sw 버전은 my.html·offline.html 의 내용 해시를 섞는데, 스탬프 전에 만들면 자산이 바뀐 커밋마다 로컬(스탬프 전 파일로 계산)과
    CI(스탬프된 커밋을 받아 계산)의 VERSION 이 갈려 CI 가 sw.js 커밋을 올리고 pull --rebase 가 충돌했다(10-22, 테스트가 지킨다)."""
    stamp_assets()
    return build_sw(sw_out)


def stamp_assets() -> None:
    """모든 HTML 의 assets/js·css 링크에 내용 해시(?v=…)를 붙여, 배포 후 브라우저가 예전 캐시 대신 새 파일을 받게 합니다.
    (Cloudflare Pages + 휴대폰 브라우저에서 새 HTML 과 옛 JS/CSS 가 섞여 동작이 깨지는 문제 방지)"""
    files = sorted(ROOT.glob("*.html")) + sorted(OUT_DIR.glob("*.html")) + sorted((ROOT / "guide").glob("*.html")) + sorted((ROOT / "function").glob("*.html")) + sorted((ROOT / "compare").glob("*.html")) + sorted((ROOT / "drug-guide").glob("*.html")) + sorted((ROOT / "term").glob("*.html"))
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
ICON_V = "2"   # 아이콘 파일 주소에 붙는 버전 — /assets/images/* 는 7일 캐시(_headers)라 아이콘을 바꾸면 올려서 엣지·브라우저 캐시를 피한다 (manifest.webmanifest·index.html·layout.js 의 ?v= 도 함께)


def pwa_tags(root: str) -> str:
    """홈 화면 설치(PWA)용 head 태그 7줄 — 매니페스트·iOS 아이콘·테마색·홈 화면 앱 메타. root 는 페이지의 data-root('./'·'../'·'/')."""
    return "\n".join([
        f'<link rel="manifest" href="{root}manifest.webmanifest">',
        f'<link rel="apple-touch-icon" href="{root}assets/images/app/apple-touch-icon.png?v={ICON_V}">',
        f'<meta name="theme-color" content="{PWA_THEME}">',
        '<meta name="mobile-web-app-capable" content="yes">',
        '<meta name="apple-mobile-web-app-capable" content="yes">',   # iOS 16.4 미만 Safari 는 manifest 의 display 대신 이 메타로 홈 화면 앱(전체 화면)을 판단 (Chrome 은 위 표준 메타가 함께 있으면 경고하지 않음)
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
    files = sorted(ROOT.glob("*.html")) + sorted(OUT_DIR.glob("*.html")) + sorted(GUIDE_DIR.glob("*.html")) + sorted((ROOT / "function").glob("*.html")) + sorted((ROOT / "compare").glob("*.html")) + sorted((ROOT / "drug-guide").glob("*.html")) + sorted((ROOT / "term").glob("*.html"))
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


def ul(items: list[str], cls: str, render=None) -> str:
    if not items:
        return '<p class="text-sm text-ink-400">해당 없음</p>'
    return f'<ul class="{cls} text-[15px] text-ink-700">' + "".join(f"<li>{(render(x) if render else esc(x))}</li>" for x in items) + "</ul>"


def render_page(it: dict, core: dict, cfg: dict) -> str:
    cats = core["categories"]
    cat = cats.get(it["category"], {})
    title = f"{it['name']} 효능·권장량·궁합·먹는 시간 | {cfg['name']}"
    fn_model = core.get("functions") or {}
    fn_meta = {e["fn"]["id"]: e["fn"] for e in fn_model.get("items", [])}
    fns = [f for f in (fn_model.get("by_ingredient") or {}).get(it["id"], []) if f in fn_meta]
    cmp_model = core.get("compares") or {}
    cmp_meta = {e["cmp"]["slug"]: e["cmp"] for e in cmp_model.get("items", [])} | {e["fc"]["slug"]: e["fc"] for e in cmp_model.get("forms", [])}   # 성분 대 성분 + 제형·형태 비교
    cmps = [s for s in (cmp_model.get("by_ingredient") or {}).get(it["id"], []) if s in cmp_meta]
    cmp_chips = ('<div class="mt-2 flex flex-wrap items-center gap-2"><span class="text-xs font-bold text-ink-500">비교 글:</span>' + "".join(f'<a class="chart-chip" href="../compare/{esc(s)}.html"><i data-lucide="scale" class="h-3.5 w-3.5"></i>{esc(_cmp_short_title(cmp_meta[s]))}</a>' for s in cmps) + '</div>') if cmps else ""
    dgs = ((core.get("drug_guides") or {}).get("by_ingredient") or {}).get(it["id"], [])
    dg_chips = ('<div class="mt-2 flex flex-wrap items-center gap-2"><span class="text-xs font-bold text-ink-500">약과 함께:</span>' + "".join(f'<a class="chart-chip chart-chip-{"synergy" if d["kind"] == "good" else "caution"}" href="../drug-guide/{esc(d["id"])}.html"><i data-lucide="pill" class="h-3.5 w-3.5"></i>{esc(d["short"])}</a>' for d in dgs) + '</div>') if dgs else ""
    fn_chips = ('<div class="mt-3 flex flex-wrap items-center gap-2"><span class="text-xs font-bold text-ink-500">기능성별 페이지:</span>' + "".join(f'<a class="chart-chip" href="../function/{esc(f)}.html"><i data-lucide="{esc(fn_meta[f]["icon"])}" class="h-3.5 w-3.5"></i>{esc(fn_meta[f]["label"])}</a>' for f in fns) + '</div>') if fns else ""
    desc = it["summary"][:150]
    st = {"used": set(), "exclude": set()}   # 용어 자동 링크 상태 (페이지 순서대로: 요약 → 권장량 메모 → 시간 메모 → 주의 → FAQ)
    summary_html = term_html(core, it["summary"], st)
    dnote_html = term_html(core, it["dosage"].get("note", ""), st)
    tnote_html = term_html(core, it["timing"].get("note", ""), st)
    caut_html = ul(it.get("cautions", []), "list-warn", render=lambda s: term_html(core, s, st))
    dcaut_html = ul(it.get("drugCautions", []), "list-warn", render=lambda s: term_html(core, s, st))
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

    faq_html = "".join(f'<details class="border-b border-ink-100 py-3"><summary class="cursor-pointer font-bold text-ink-900">Q. {esc(f["q"])}</summary><p class="mt-2 text-sm text-ink-600">{term_html(core, f["a"], st)}</p></details>' for f in it.get("faq", []))

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
      <p class="mt-3 text-[15px] text-ink-700">{summary_html}</p>
      <h2 class="mt-8 text-lg font-extrabold">식약처 인정 기능성</h2><p class="mt-2 text-sm text-ink-700">{esc(it.get("mfdsFunction") or "고시형 기능성 원료 아님")}</p>{fn_chips}{cmp_chips}{dg_chips}
      <h2 class="mt-6 text-lg font-extrabold">기대 효과</h2>{ul(it.get("benefits", []), "list-check")}
      <h2 class="mt-6 text-lg font-extrabold">권장 섭취량</h2><p class="text-sm text-ink-700">하루 권장: {esc(it["dosage"].get("daily"))} · 상한: {esc(it["dosage"].get("upper"))}</p><p class="text-sm text-ink-600">{dnote_html}</p>
      <h2 class="mt-6 text-lg font-extrabold">{esc(it["name"])} 먹는 시간</h2><p class="text-sm text-ink-700">{esc(it["timing"].get("label"))} — {tnote_html}</p><p class="mt-1 text-xs"><a class="font-bold text-brand-700 hover:underline" href="../timing-chart.html#{esc(it["id"])}">영양제 복용 시간표에서 다른 성분과 비교 →</a></p>
      <h2 class="mt-6 text-lg font-extrabold">이런 분께 추천</h2>{ul(it.get("whoFor", []), "list-dot")}
      <h2 class="mt-6 text-lg font-extrabold">주의사항</h2>{caut_html}{('<h3 class="mt-3 text-sm font-bold text-rose-700">약과 함께 먹을 때</h3>' + dcaut_html) if it.get("drugCautions") else ""}
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
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
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
  <link rel="icon" href="../assets/images/favicon.svg?v={ICON_V}" type="image/svg+xml">
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
  <script src="../assets/js/terms.js" defer></script>
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
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
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
  <link rel="icon" href="{root}assets/images/favicon.svg?v={ICON_V}" type="image/svg+xml">
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


RELATED_COMPARES_MAX = 6   # 가이드·기능성 페이지에 보여 주는 관련 비교 글 수


def related_compares(core: dict, ids, slug: str | None = None, limit: int = RELATED_COMPARES_MAX) -> list[dict]:
    """페이지(가이드·기능성 허브)의 성분 id 목록과 slug 로 관련 비교 글을 고른다: ① 비교의 related 가이드에 slug 가 있거나 ② 성분 대 성분 비교는 ids 가
    모두 페이지 성분에 들어 있거나 ③ 제형·형태 비교는 기준 성분이 페이지 성분에 있는 것. 관련 가이드 명시 → 겹치는 성분 수 → 제목 순, 최대 limit 편.
    core["compares"](compare_model + forms) 가 없으면 빈 목록이라 단위 테스트처럼 비교 모델 없이도 페이지를 그릴 수 있다."""
    model = core.get("compares") or {}
    have = set(ids or [])
    out: list[dict] = []
    for e in model.get("items") or []:
        cmp_ids = list(e["cmp"].get("ids") or [])
        rel = bool(slug) and slug in (e["cmp"].get("related") or [])
        inside = bool(cmp_ids) and all(i in have for i in cmp_ids)
        if not (rel or inside):
            continue
        out.append({"slug": e["cmp"]["slug"], "h1": e["cmp"]["h1"], "desc": e["cmp"].get("description") or "", "kind": "pair",
                    "names": [i["name"] for i in e.get("ingredients") or []], "score": (10 if rel else 0) + len(have & set(cmp_ids))})
    for e in model.get("forms") or []:
        fc = e["fc"]
        rel = bool(slug) and slug in (fc.get("related") or [])
        inside = fc.get("id") in have
        if not (rel or inside):
            continue
        out.append({"slug": fc["slug"], "h1": fc["h1"], "desc": fc.get("description") or "", "kind": "form",
                    "names": [(e.get("ingredient") or {}).get("name") or fc.get("id") or ""], "n_forms": len(e.get("forms") or []), "score": (10 if rel else 0) + (1 if inside else 0)})
    out.sort(key=lambda x: (-x["score"], x["h1"]))
    return out[:limit]


def compare_cards_html(entries: list[dict], root: str = "../") -> str:
    """관련 비교 글 카드 — 허브(compare.html)의 cmp-card 와 같은 모양. entries 는 related_compares() 결과."""
    cards = []
    for x in entries:
        names = (" <em>vs</em> ".join(esc(n) for n in x["names"])) if x["kind"] == "pair" else f'{esc(x["names"][0])} <em>·</em> 형태 {x.get("n_forms", 0)}가지'
        cards.append(f'<a class="cmp-card" href="{root}compare/{esc(x["slug"])}.html"><span class="cmp-card-names">{names}</span>'
                     f'<span class="mt-2 block text-base font-extrabold text-ink-900">{esc(x["h1"])}</span><span class="mt-1 line-clamp-2 block text-sm text-ink-500">{esc(x["desc"])}</span></a>')
    return "".join(cards)


def related_compares_section(cmps_html: str, lead: str) -> str:
    return (f'<section id="compares" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">관련 비교 글</h2><p class="mt-1 text-sm text-ink-500">{lead}</p>'
            f'<div class="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{cmps_html}</div></section>') if cmps_html else ""


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
    st = {"used": set(), "exclude": set()}   # 용어 자동 링크 상태 (페이지당 첫 등장만)
    intro_html = term_html(core, gd["intro"], st)
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
                     f'<p class="mt-2 text-sm leading-relaxed text-ink-700">{term_html(core, x["why"], st)}</p>'
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
                       f'<h3 class="mt-2 font-extrabold text-ink-900">{esc(" + ".join(names))}</h3><p class="mt-1 text-sm text-ink-700">{term_html(core, c["note"], st)}</p>'
                       f'<a href="../compatibility.html?items={",".join(c["ids"])}" class="mt-3 inline-flex items-center gap-1 text-sm font-bold text-brand-700 hover:underline">궁합 체크에서 자세히 <i data-lucide="arrow-right" class="h-4 w-4"></i></a></div>')

    sections_html = "".join(f'<section class="rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="text-lg font-extrabold text-ink-900">{esc(sec["h2"])}</h2><p class="mt-3 whitespace-pre-line text-[15px] leading-relaxed text-ink-700">{term_html(core, sec["body"], st)}</p></section>' for sec in gd.get("sections", []))
    tips_html = ul(gd["tips"], "list-check", render=lambda s: term_html(core, s, st))
    caut_html = ul(gd["cautions"], "list-warn", render=lambda s: term_html(core, s, st))
    faq_html = "".join(f'<details class="group border-b border-ink-100 py-3 last:border-0"><summary class="flex cursor-pointer list-none items-center justify-between gap-3 font-bold text-ink-900"><span>Q. {esc(f["q"])}</span><i data-lucide="chevron-down" class="h-4 w-4 shrink-0 text-ink-400 transition group-open:rotate-180"></i></summary><p class="mt-2 text-sm leading-relaxed text-ink-600">{term_html(core, f["a"], st)}</p></details>' for f in gd["faq"])
    shop_html = "".join(f'<div class="flex flex-col gap-2 rounded-xl border border-ink-100 bg-white p-4 sm:flex-row sm:items-center sm:justify-between"><div><p class="font-bold text-ink-900">{esc(by_id[x["id"]]["name"])}</p><p class="text-xs text-ink-500">검색어: {esc(by_id[x["id"]]["shopQuery"])}</p></div><div class="js-shop" data-query="{esc(by_id[x["id"]]["shopQuery"])}"></div></div>' for x in gd["ingredients"][:3] if x["id"] in by_id)
    related = [guides["by_id"][r] for r in gd.get("related", []) if r in guides["by_id"]]
    cmps_html = compare_cards_html(related_compares(core, [x["id"] for x in gd["ingredients"]], gd["slug"]), "../")   # 관련 비교 글 (core["compares"] 가 없으면 빈 문자열)
    related_html = "".join(guide_card(r, types, "../") for r in related)
    all_ids = ",".join(x["id"] for x in gd["ingredients"][:6])
    nav_chips = "".join(f'<a href="#{a}" class="chip">{b}</a>' for a, b in (("ingredients", "핵심 성분"), ("combos", "추천 조합")) if (a != "combos" or combo_html)) + ("".join(f'<a href="#sec-{i}" class="chip">{esc(sec["h2"][:14])}</a>' for i, sec in enumerate(gd.get("sections", [])[:0]))) + '<a href="#tips" class="chip">이렇게 드세요</a><a href="#faq" class="chip">FAQ</a>' + ('<a href="#compares" class="chip">비교 글</a>' if cmps_html else '')

    body = f"""
<body data-page="guides" data-path="{path}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-5xl px-4 pb-10 pt-8 sm:px-6 sm:pt-12">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="../index.html">홈</a> › <a class="hover:text-brand-700" href="../guides.html">영양제 가이드</a> › <a class="hover:text-brand-700" href="../guides.html#{gd['type']}">{esc(t.get('short', ''))}</a> › <span class="text-ink-800">{esc(gd['h1'])}</span></nav>
      <span class="mt-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ring-1 {TYPE_STYLE.get(gd['type'], '')}"><i data-lucide="{esc(gd['icon'])}" class="h-3.5 w-3.5"></i>{esc(t.get('label', ''))}</span>
      <h1 class="page-title mt-3">{esc(gd['h1'])}</h1>
      <p class="page-lead mt-4 max-w-3xl">{intro_html}</p>
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
      {related_compares_section(cmps_html, "이 가이드의 성분을 비슷한 성분·다른 형태와 식약처 인정 기능성·권장량·먹는 시간 기준으로 나란히 비교한 글입니다.")}
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
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">가이드를 읽는 법</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li>'추천 성분'은 식약처가 인정한 기능성과 결핍 가능성을 기준으로 고른 것이며 특정 제품·브랜드를 보증하지 않습니다.</li><li>건강기능식품은 질병의 예방·치료 목적이 아닙니다. 증상이 지속되면 진료가 먼저입니다.</li><li>약을 복용 중이라면 <a class="font-bold text-brand-700 underline" href="guide/with-medication.html">약과 영양제 가이드</a>를 먼저 읽고 약사·의사와 상의하세요.</li><li>표로 한눈에 보려면 <a class="font-bold text-brand-700 underline" href="compatibility-chart.html">영양제 궁합표</a>와 <a class="font-bold text-brand-700 underline" href="timing-chart.html">영양제 복용 시간표</a>를, 식약처 인정 기능성 문구로 찾으려면 <a class="font-bold text-brand-700 underline" href="functions.html">기능성별 영양제</a>를, 헷갈리는 두 성분은 <a class="font-bold text-brand-700 underline" href="compare.html">성분 비교</a>를, 약을 먹는 중이면 <a class="font-bold text-brand-700 underline" href="drug-guides.html">약별 영양제 가이드</a>를 참고하세요. 라벨·가이드의 낯선 말은 <a class="font-bold text-brand-700 underline" href="glossary.html">영양제 용어 사전</a>에서 찾을 수 있습니다.</li></ul></section>
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


def faq_block(items: list[tuple[str, str]], heading: str = "자주 묻는 질문", render=None) -> tuple[str, dict]:
    """보이는 FAQ 섹션 HTML 과 같은 내용의 FAQPage JSON-LD (구글은 보이는 본문과 구조화 데이터가 같아야 한다)."""
    html_ = f'<section id="faq" class="scroll-mt-24 rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="text-lg font-extrabold text-ink-900">{esc(heading)}</h2><div class="mt-2 divide-y divide-ink-100">' + \
        "".join(f'<details class="group py-3"><summary class="cursor-pointer list-none font-bold text-ink-900">{esc(q)}</summary><p class="mt-2 text-sm leading-relaxed text-ink-700">{(render(a) if render else esc(a))}</p></details>' for q, a in items) + "</div></section>"
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
    """data/finder.json 무결성: 질문·옵션 id 중복, 규칙이 가리키는 질문·옵션·가이드 slug, restrictTo, avoid(추천 제외 성분 id), 인기 성분 id. 어긋나면 빌드 실패."""
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
        for i in r.get("avoid", []):
            if i not in valid_ids:
                raise SystemExit(f"finder.json: 규칙 {n} 의 avoid 에 없는 성분 id {i}")
        if not r.get("guides") and not r.get("flags"):
            raise SystemExit(f"finder.json: 규칙 {n} 에 guides 또는 flags 가 필요")
    log.info("셀프체크 규칙 검증 통과: 질문 %d개 · 규칙 %d개", len(qs), len(data.get("rules", [])))


def render_finder(data: dict, core: dict, cfg: dict) -> str:
    """나에게 맞는 영양제 찾기 — 질문 폼은 정적 HTML(검색엔진·JS 없는 환경), 결과는 pages/finder.js 가 그린다."""
    by_id = core["by_id"]
    questions = data.get("questions", [])
    title = f"나에게 맞는 영양제 추천 — 1분 셀프체크로 성분·궁합·복용 시간표까지 | {cfg['name']}"
    desc = (f"연령·성별·고민·생활 습관·복용 중인 약·이미 먹는 영양제를 고르면 가이드 {len(core.get('guides') or [])}편의 핵심 성분에서 나에게 맞는 영양제 성분을 추천하고, "
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


TIP_FORBIDDEN = ("치료", "예방", "완치", "진단", "AI가 분석")


def validate_tips(data: dict) -> None:
    """오늘의 한 줄 일반 팁(data/tips.json): 비어 있지 않고, 각 문장은 10~120자, 금칙어(질병 치료·예방·완치·진단, 'AI가 분석')가 없어야 한다."""
    items = (data or {}).get("items") or []
    if not items:
        raise ValueError("data/tips.json: items 가 비어 있습니다")
    for i, t in enumerate(items):
        text = str((t or {}).get("text", "")).strip()
        if not 10 <= len(text) <= 120:
            raise ValueError(f"data/tips.json[{i}]: 문장은 10~120자여야 합니다: {text[:30]}")
        for w in TIP_FORBIDDEN:
            if w in text:
                raise ValueError(f"data/tips.json[{i}]: 금칙어 '{w}' 가 들어 있습니다: {text[:30]}")
        if not str((t or {}).get("source", "")).strip():
            raise ValueError(f"data/tips.json[{i}]: source 가 없습니다")


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
    st = {"used": set(), "exclude": set()}
    intro_html = term_html(core, it["intro"], st)
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
    cmps_html = compare_cards_html(related_compares(core, [i["id"] if isinstance(i, dict) else i for i in ings]), "../")   # 관련 비교 글 (core["compares"] 가 없으면 빈 문자열)
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
      <p class="page-lead mt-4 max-w-3xl">{intro_html}</p>
      <ul class="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm text-ink-600">
        <li class="inline-flex items-center gap-1.5"><i data-lucide="leaf" class="h-4 w-4 text-brand-600"></i>성분 사전 <strong>{n_i}종</strong></li>
        <li class="inline-flex items-center gap-1.5"><i data-lucide="microscope" class="h-4 w-4 text-brand-600"></i>개별인정 원료 <strong>{n_m}종</strong></li>
        <li class="inline-flex items-center gap-1.5"><i data-lucide="package" class="h-4 w-4 text-brand-600"></i>신고 제품 <strong>{n_p:,}건</strong></li>
      </ul>
      <div class="mt-5 flex flex-wrap gap-2"><a href="#ingredients" class="chip">성분</a><a href="#materials" class="chip">인정 원료</a><a href="#products" class="chip">신고 제품</a>{'<a href="#compares" class="chip">비교 글</a>' if cmps_html else ""}{'<a href="#guides" class="chip">가이드</a>' if rel_guides else ""}<a href="#faq" class="chip">자주 묻는 질문</a></div>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      <section id="ingredients" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">이 기능성이 인정된 성분 {n_i}종</h2><p class="mt-1 text-sm text-ink-500">성분 사전에 있는 성분 가운데 식약처 인정 기능성 내용에 이 문구가 들어간 성분입니다. 성분을 누르면 효능·권장량·궁합·먹는 시간을 봅니다.</p><div class="mt-4">{ings_html}</div></section>
      <section id="materials" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">식약처 개별인정 원료 {n_m}종</h2><p class="mt-1 text-sm text-ink-500">식품안전나라 기능성 원료 인정현황에서 이 기능성이 인정된 원료입니다. 인정 업체가 많은 순으로 정렬했습니다.</p><div class="mt-4">{mats_html}</div></section>
      <section id="products" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">이 기능성을 표시한 신고 제품</h2><div class="mt-2">{prods_html}</div></section>
      {pairs_html}
      {timing_html}
      {related_compares_section(cmps_html, "이 기능성의 성분을 비슷한 성분·다른 형태와 나란히 비교한 글입니다.")}
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
    core["products_detail"] = products   # 제형·형태 비교(prepare_form_compares)가 재사용
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
        "_meta": {"updatedAt": data_stamp(model["data"], default=core.get("updated_at") or now_iso()[:10]), "note": "functions.json 의 요약 색인 — scripts/build_site.py 가 생성, 직접 수정하지 않음 (성분 페이지의 기능성 칩용)"},
        "items": [{"id": e["fn"]["id"], "label": e["fn"]["label"], "claim": _fn_claim_short(e["fn"]), "group": e["fn"]["group"], "icon": e["fn"]["icon"], "ingredients": [i["id"] for i in e["ingredients"]],
                   "counts": {"ingredients": len(e["ingredients"]), "materials": len(e["materials"]), "products": e["products"]["total"]}} for e in model["items"]],
    }, compact=True, quiet=True)
    log.info("기능성별 허브 생성: %s + function/ %d장", FUNCTIONS_HUB, len(wanted))
    return [e["fn"]["id"] for e in model["items"]]


def data_stamp(*datas, default: str = "") -> str:
    """생성 색인의 _meta.updatedAt — 빌드 시각 대신 원본 데이터 _meta.updatedAt 가운데 가장 최신 값을 쓴다. 내용이 같으면 파일도 같아져
    CI(build-assets.yml)가 시각만 바뀐 색인을 매번 커밋하는 일을 막는다. 원본에 값이 없으면 default(데이터 기준일)."""
    stamps = [str((d.get("_meta") or {}).get("updatedAt") or "") for d in datas if isinstance(d, dict)]
    return max(stamps) if any(stamps) else default


def photo_img(category: str) -> str:
    """분류별 알약 사진 — assets/js/illus.js 의 photoFor(category) 와 같은 파일 대응표."""
    file = {"vitamin": "capsule-yellow", "mineral": "tablet-beige", "fatty-acid": "softgel-amber", "probiotic": "capsule-blue", "herbal": "capsule-green", "amino": "capsule-violet", "joint": "capsule-orange", "beauty": "capsule-pink"}.get(category, "tablet-beige")
    return f'<img src="../assets/images/home/{file}.webp" alt="" width="56" height="56" loading="lazy" decoding="async" class="h-full w-full object-cover">'


# ---------------------------------------------------------------- 성분 비교 (compare.html · compare/<slug>.html — data/compares.json 수동 본문 + 성분 사전·집계 자동 행)
COMPARE_DIR = ROOT / "compare"
COMPARES_HUB = "compare.html"


def validate_compares(data: dict, valid_ids: set[str], guide_slugs: set[str]) -> None:
    """data/compares.json 무결성: 필수 필드, slug 형식·중복, ids(성분 사전)·points·rows 참조, related 가이드 slug."""
    seen: set[str] = set()
    for it in data.get("items", []):
        for k in ("slug", "ids", "title", "h1", "description", "intro", "verdict", "points", "faq"):
            if not it.get(k):
                raise SystemExit(f"compares.json: '{it.get('slug') or it.get('title')}' 에 {k} 가 없음")
        if not re.fullmatch(r"[a-z0-9-]+", it["slug"]) or it["slug"] in seen:
            raise SystemExit(f"compares.json: slug 형식 오류 또는 중복 {it['slug']}")
        seen.add(it["slug"])
        ids = it["ids"]
        if len(ids) < 2 or len(ids) != len(set(ids)):
            raise SystemExit(f"compares.json: '{it['slug']}' 의 ids 는 서로 다른 성분 2개 이상이어야 함")
        for i in ids:
            if i not in valid_ids:
                raise SystemExit(f"compares.json: '{it['slug']}' 이 없는 성분 id {i} 를 참조")
        for p in it["points"]:
            if p.get("id") not in ids:
                raise SystemExit(f"compares.json: '{it['slug']}' 의 points 에 ids 밖 성분 {p.get('id')}")
        for r in it.get("rows", []):
            for k in (r.get("cells") or {}):
                if k not in ids:
                    raise SystemExit(f"compares.json: '{it['slug']}' 의 rows '{r.get('label')}' 에 ids 밖 성분 {k}")
        for s in it.get("related", []):
            if s not in guide_slugs:
                raise SystemExit(f"compares.json: '{it['slug']}' 이 없는 가이드 slug {s} 를 참조")
    log.info("성분 비교 데이터 검증 통과: %d편", len(seen))


def compare_model(data: dict, core: dict, guides: list[dict]) -> dict:
    """비교마다 성분·비교표 행(수동 행 + 사전·집계 자동 행)·성분 쌍 궁합(데이터 쌍만)·관련 가이드·상위 제품을 모으고 성분→비교 역색인을 만든다."""
    by_id, cats = core["by_id"], core["categories"]
    fn = core.get("functions") or {}
    fn_meta = {e["fn"]["id"]: e["fn"] for e in fn.get("items", [])}
    pair_index = {frozenset(p["pair"]): p for p in core.get("pairs", [])}
    guide_by_slug = {g["slug"]: g for g in guides}
    top_cache: dict[str, dict] = {}

    def top(iid: str) -> dict:
        if iid not in top_cache:
            top_cache[iid] = read_json(DATA_DIR / "products" / "top" / f"{iid}.json", {}) or {}
        return top_cache[iid]

    out = []
    by_ing: dict[str, list[str]] = {}
    for it in data.get("items", []):
        ings = [by_id[i] for i in it["ids"]]
        ids = set(it["ids"])

        def cell(f):
            return {i["id"]: f(i) for i in ings}

        rows = [{"label": "식약처 인정 기능성", "cells": cell(lambda i: i.get("mfdsFunction") or "고시형 기능성 원료 아님")}]
        for r in it.get("rows", []):
            rows.append({"label": r["label"], "cells": {i["id"]: (r.get("cells") or {}).get(i["id"], "—") for i in ings}})
        rows += [
            {"label": "성분 분류", "cells": cell(lambda i: cats.get(i["category"], {}).get("label", i["category"]))},
            {"label": "하루 권장 섭취량", "cells": cell(lambda i: (i.get("dosage") or {}).get("daily") or "—")},
            {"label": "상한·기준", "cells": cell(lambda i: (i.get("dosage") or {}).get("upper") or "—")},
            {"label": "먹는 시간", "cells": cell(lambda i: ((i.get("timing") or {}).get("label") or "—") + (" · 지용성(지방 포함 식사)" if i.get("fatSoluble") else ""))},
            {"label": "주의할 점", "cells": cell(lambda i: " / ".join((i.get("cautions") or [])[:2]) or "—")},
            {"label": "이런 분께", "cells": cell(lambda i: " / ".join((i.get("whoFor") or [])[:2]) or "—")},
            {"label": "신고 제품 수 (수집 범위)", "cells": cell(lambda i: f"{int((top(i['id']).get('_meta') or {}).get('total') or 0):,}건")},
            {"label": "기능성별 페이지", "html": True, "cells": {i["id"]: ("".join(f'<a class="chart-chip" href="../function/{esc(f)}.html">{esc(fn_meta[f]["label"])}</a>' for f in (fn.get("by_ingredient") or {}).get(i["id"], []) if f in fn_meta) or "—") for i in ings}},
        ]
        pairs = []
        for x in range(len(ings)):
            for y in range(x + 1, len(ings)):
                pairs.append({"a": ings[x], "b": ings[y], "p": pair_index.get(frozenset((ings[x]["id"], ings[y]["id"])))})
        manual = [guide_by_slug[s] for s in it.get("related", []) if s in guide_by_slug]
        auto = [g for g in sorted(guides, key=lambda g: (-len(ids & {x["id"] for x in g.get("ingredients", [])}), g["slug"]))
                if g["slug"] not in it.get("related", []) and len(ids & {x["id"] for x in g.get("ingredients", [])}) >= 2]
        for i in ings:
            by_ing.setdefault(i["id"], []).append(it["slug"])
        out.append({"cmp": it, "ingredients": ings, "rows": rows, "pairs": pairs, "guides": (manual + auto)[:4],
                    "products": {i["id"]: (top(i["id"]).get("items") or [])[:3] for i in ings}})
    return {"items": out, "by_ingredient": by_ing}


def _cmp_short_title(it: dict) -> str:
    return it["title"].split(":")[0].strip()


def render_compare(entry: dict, core: dict, cfg: dict, guides_types: dict, updated: str) -> str:
    it, ings, rows, pairs, rel_guides, products = entry["cmp"], entry["ingredients"], entry["rows"], entry["pairs"], entry["guides"], entry["products"]
    by_id, cats, types = core["by_id"], core["categories"], core["types"]
    path = f"compare/{it['slug']}.html"
    title = f"{it['title']} | {cfg['name']}"
    ids = [i["id"] for i in ings]
    names = [i["name"] for i in ings]
    _, faq_ld = faq_block([(f["q"], f["a"]) for f in it["faq"]])
    st = {"used": set(), "exclude": set()}   # 용어 자동 링크 상태 (소개 → 핵심 차이 → 이런 분은 → 같이 먹기 → FAQ)
    intro_html = term_html(core, it["intro"], st)
    verdict_html = term_html(core, it["verdict"], st)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "성분 비교", "item": page_url(cfg, COMPARES_HUB)},
            {"@type": "ListItem", "position": 3, "name": _cmp_short_title(it), "item": page_url(cfg, path)}]},
        {"@type": "Article", "headline": it["h1"], "description": it["description"], "url": page_url(cfg, path), "dateModified": updated, "inLanguage": "ko",
         "author": {"@type": "Organization", "name": cfg["name"]}, "about": [{"@type": "Thing", "name": i["name"], "url": page_url(cfg, f"i/{i['id']}.html")} for i in ings]},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=it["description"], path=path, root="../", keywords=", ".join(it.get("keywords", [])), og_type="article",
                     extra_scripts='<script src="../assets/js/pages/compare.js" defer></script>', ld=ld)
    points = {p["id"]: p for p in it["points"]}

    def mini(i: dict) -> str:
        cat = cats.get(i["category"], {})
        return (f'<a class="cmp-mini" href="../i/{esc(i["id"])}.html"><span class="finder-thumb">{photo_img(i["category"])}</span><span class="min-w-0"><span class="badge {cat_class(cat.get("color", ""))}">{esc(cat.get("label", ""))}</span>'
                f'<span class="mt-1 block text-base font-extrabold text-ink-900">{esc(i["name"])}</span><span class="mt-0.5 block text-sm text-ink-600">{esc(points.get(i["id"], {}).get("line", i.get("summary", "")))}</span></span></a>')
    head_cells = "".join(f'<th scope="col"><a href="../i/{esc(i["id"])}.html">{esc(i["name"])}</a></th>' for i in ings)
    body_rows = "".join(
        f'<tr><th scope="row">{esc(r["label"])}</th>' + "".join(f'<td>{(r["cells"].get(i["id"]) if r.get("html") else esc(r["cells"].get(i["id"], "—")))}</td>' for i in ings) + "</tr>"
        for r in rows)
    table_html = f'<div class="timing-table-wrap"><table class="timing-table cmp-table"><caption class="sr-only">{esc(" vs ".join(names))} 비교표</caption><thead><tr><th scope="col">항목</th>{head_cells}</tr></thead><tbody>{body_rows}</tbody></table></div>'

    picks_html = "".join(
        f'<article class="finder-card"><div class="flex items-start gap-3"><span class="finder-thumb">{photo_img(i["category"])}</span><div class="min-w-0 flex-1"><h3 class="text-base font-extrabold text-ink-900"><a class="hover:text-brand-700" href="../i/{esc(i["id"])}.html">{esc(i["name"])}</a></h3>'
        f'<p class="mt-1 text-sm text-ink-600">{term_html(core, points.get(i["id"], {}).get("line", ""), st)}</p><ul class="list-check mt-2 text-sm text-ink-700">{"".join(f"<li>{term_html(core, w, st)}</li>" for w in points.get(i["id"], {}).get("pick", []))}</ul>'
        f'<div class="mt-3 flex flex-wrap gap-2"><a class="btn-outline btn-sm" href="../i/{esc(i["id"])}.html">자세히</a><button type="button" class="btn-outline btn-sm" data-my-add="{esc(i["id"])}"><i data-lucide="plus"></i>내 영양제에 추가</button></div></div></div></article>'
        for i in ings)

    pair_rows = ""
    for pr in pairs:
        p = pr["p"]
        if p:
            t = types.get(p["type"], {})
            pair_rows += (f'<li class="finder-pair finder-pair-{esc(p["type"])}"><span class="badge badge-{esc(p["type"])}">{esc(t.get("short", p["type"]))}</span><div><p class="font-bold text-ink-900">{esc(pr["a"]["name"])} + {esc(pr["b"]["name"])}{" · " + str(p["separateHours"]) + "시간 간격" if p.get("separateHours") else ""}</p>'
                          f'<p class="text-sm text-ink-600">{esc(p.get("title", ""))}{" — " + esc(p["tip"]) if p.get("tip") else ""}</p></div></li>')
        else:
            pair_rows += (f'<li class="finder-pair" style="border-color:#e2e8f0;background:#f8fafc"><span class="badge badge-neutral">데이터 없음</span><div><p class="font-bold text-ink-900">{esc(pr["a"]["name"])} + {esc(pr["b"]["name"])}</p>'
                          f'<p class="text-sm text-ink-600">궁합 데이터에 등록된 조합이 아니라 아래 안내를 따르고, 궁합 체크에서 규칙 판정을 확인하세요.</p></div></li>')
    together_html = (f'<ul class="space-y-2">{pair_rows}</ul><p class="mt-4 text-sm leading-relaxed text-ink-700">{term_html(core, it.get("together", ""), st)}</p>'
                     f'<div class="mt-4 flex flex-wrap gap-2"><a href="../compatibility.html?items={esc(",".join(ids))}" class="btn-primary"><i data-lucide="heart-handshake"></i>궁합 체크에서 시간표까지 보기 <i data-lucide="arrow-right"></i></a><a href="../compatibility-chart.html" class="btn-outline"><i data-lucide="table"></i>영양제 궁합표</a></div>')

    timing_rows = "".join(f'<tr><th scope="row"><a href="../i/{esc(i["id"])}.html">{esc(i["name"])}</a></th><td>{esc((i.get("timing") or {}).get("label", ""))}</td><td class="timing-note">{esc((i.get("timing") or {}).get("note", ""))}</td></tr>' for i in ings)
    timing_html = f'<div class="timing-table-wrap"><table class="timing-table"><caption class="sr-only">먹는 시간</caption><thead><tr><th scope="col">성분</th><th scope="col">권장 시간</th><th scope="col">메모</th></tr></thead><tbody>{timing_rows}</tbody></table></div>'

    def shop_card(i: dict) -> str:
        tops = "".join(f'<li><a class="hover:text-brand-700" href="../product.html?id={esc(p["id"])}">{esc(p["name"])}</a><span class="ml-1 text-xs text-ink-400">{esc(p.get("company") or "")}</span></li>' for p in products.get(i["id"], []))
        return (f'<div class="rounded-2xl border border-ink-100 bg-white p-5 shadow-card"><h3 class="font-extrabold text-ink-900">{esc(i["name"])}</h3><p class="mt-1 text-xs text-ink-500">쇼핑몰 검색어: {esc(i.get("shopQuery") or i["name"])}</p>'
                f'<div class="app-hide mt-3" data-query="{esc(i.get("shopQuery") or i["name"])}"></div>'
                + (f'<p class="mt-3 text-xs font-bold text-ink-500">최근 신고 제품</p><ul class="list-dot mt-1 text-sm text-ink-700">{tops}</ul>' if tops else "")
                + f'<a class="mt-3 inline-flex items-center gap-1 text-sm font-bold text-brand-700 hover:underline" href="../products.html?ingredient={esc(i["id"])}">제품 찾기에서 전체 보기 <i data-lucide="arrow-right" class="h-4 w-4"></i></a></div>')
    shop_html = f'<div class="grid gap-4 md:grid-cols-{min(len(ings), 3)}">{"".join(shop_card(i) for i in ings)}</div><p id="compare-disclosure" class="app-hide mt-3 text-[11px] text-ink-400"></p>'

    guides_html = f'<div class="grid gap-4 md:grid-cols-2">{"".join(guide_card(g, guides_types, "../") for g in rel_guides)}</div>' if rel_guides else ""
    faq_html, _ = faq_block([(f["q"], f["a"]) for f in it["faq"]], render=lambda s: term_html(core, s, st))
    chips = [("table", "비교표"), ("verdict", "핵심 차이"), ("picks", "이런 분은"), ("together", "같이 먹어도 될까"), ("timing", "먹는 시간"), ("shop", "제품 보기"), ("faq", "자주 묻는 질문")]
    body = f"""
<body data-page="ingredients" data-path="{path}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="../index.html">홈</a> › <a class="hover:text-brand-700" href="../{COMPARES_HUB}">성분 비교</a> › <span class="text-ink-800">{esc(_cmp_short_title(it))}</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="scale"></i> 성분 비교</p>
      <h1 class="page-title mt-3">{esc(it["h1"])}</h1>
      <p class="page-lead mt-4 max-w-3xl">{intro_html}</p>
      <div class="mt-6 grid gap-3 md:grid-cols-{min(len(ings), 3)}">{"".join(mini(i) for i in ings)}</div>
      <div class="mt-5 flex flex-wrap gap-2">{"".join(f'<a href="#{a}" class="chip">{b}</a>' for a, b in chips)}</div>
      <p class="mt-4 text-xs text-ink-400">식약처 인정 기능성 표현을 기준으로 정리한 일반 건강 정보이며 의학적 조언이 아닙니다 · 최종 수정 {esc(updated)}</p>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      <section id="table" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">한눈에 비교</h2><p class="mt-1 text-sm text-ink-500">인정 기능성·권장량·먹는 시간·주의·추천 대상은 성분 사전에서, 신고 제품 수는 식약처 품목신고 수집분(2021-04 이후)에서 가져옵니다.</p><div class="mt-4">{table_html}</div></section>
      <section id="verdict" class="scroll-mt-24 rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">핵심 차이</h2><p class="mt-3 text-[15px] leading-relaxed text-ink-800">{verdict_html}</p></section>
      <section id="picks" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">이런 분은 이걸</h2><div class="mt-4 grid gap-4 md:grid-cols-{min(len(ings), 3)}">{picks_html}</div></section>
      <section id="together" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">같이 먹어도 될까</h2><div class="mt-4">{together_html}</div></section>
      <section id="timing" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">먹는 시간</h2><div class="mt-4">{timing_html}</div><p class="mt-2 text-xs text-ink-500">전체 성분은 <a class="font-bold text-brand-700 underline" href="../timing-chart.html">영양제 복용 시간표</a>에서 보세요.</p></section>
      <section id="shop" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">제품 보기</h2><p class="mt-1 text-sm text-ink-500">성분별 쇼핑몰 검색 결과와 최근 신고 제품으로 바로 이동합니다. 함량·형태·보장균수 등은 제품 라벨을 꼭 확인하세요.</p><div class="mt-4">{shop_html}</div></section>
      {('<section id="guides" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">관련 가이드</h2><div class="mt-4">' + guides_html + '</div></section>') if guides_html else ""}
      {faq_html}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">함께 보면 좋은 페이지</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li><a class="font-bold text-brand-700 underline" href="../{COMPARES_HUB}">성분 비교 전체 목록</a></li><li><a class="font-bold text-brand-700 underline" href="../finder.html">나에게 맞는 영양제 찾기</a> — 고민과 상황으로 성분 추천</li><li><a class="font-bold text-brand-700 underline" href="../functions.html">기능성별 영양제</a> · <a class="font-bold text-brand-700 underline" href="../compatibility-chart.html">영양제 궁합표</a> · <a class="font-bold text-brand-700 underline" href="../timing-chart.html">영양제 복용 시간표</a></li></ul></section>
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def render_compare_hub(model: dict, data: dict, core: dict, cfg: dict) -> str:
    items = model["items"]
    forms = model.get("forms") or []
    n, nf = len(items), len(forms)
    title = f"영양제 성분 비교 — 비슷한 성분, 무엇이 다를까 ({n + nf}편) | {cfg['name']}"
    desc = "홍삼과 인삼, 글루코사민·콘드로이친·MSM, 스피루리나와 클로렐라, 루테인과 아스타잔틴처럼 헷갈리는 성분을 식약처 인정 기능성·권장량·먹는 시간·주의사항 기준으로 나란히 비교하고 상황별로 무엇을 고를지 정리했습니다. rTG 오메가3·리포좀 비타민C·헴철·마그네슘 염처럼 같은 성분의 다른 형태도 원료·표기·먹는 법 기준으로 비교합니다."
    faq_html, faq_ld = faq_block([
        ("비교표의 기준은 무엇인가요?", "식약처가 인정한 기능성 문구, 고시·개별인정 기준 섭취량, 성분 사전의 먹는 시간·주의사항·추천 대상, 그리고 식약처 품목신고 수집분의 제품 수입니다. 가격이나 효과의 우열은 비교하지 않습니다."),
        ("두 성분을 같이 먹어도 되나요?", "비교 글마다 '같이 먹어도 될까' 항목에 궁합 데이터의 판정과 안내를 적었습니다. 데이터에 없는 조합은 궁합 체크에서 규칙으로 판정합니다."),
        ("같은 성분의 형태(rTG·리포좀·헴철 등) 차이도 비교하나요?", "제형·형태 비교 묶음에서 오메가3·비타민C·철분·마그네슘·칼슘·엽산·비타민D·글루코사민·비타민E·아연·콜라겐의 형태를 원료·제조·표기·먹는 법 기준으로 비교하고, 식약처 신고 제품을 제품명·원재료명 표기로 걸러 형태별 제품 수와 예시를 보여 줍니다. 흡수율 수치나 가격은 비교하지 않습니다."),
        ("비교하고 싶은 성분이 없어요.", "성분 사전에서 두 성분을 각각 보거나 궁합 체크에서 함께 골라 비교할 수 있습니다. 비교 글은 검색 요청이 많은 조합부터 추가합니다."),
    ])
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"}, {"@type": "ListItem", "position": 2, "name": "성분 비교", "item": page_url(cfg, COMPARES_HUB)}]},
        {"@type": "CollectionPage", "name": "영양제 성분 비교", "url": page_url(cfg, COMPARES_HUB), "hasPart": [{"@type": "Article", "headline": e["cmp"]["h1"], "url": page_url(cfg, f"compare/{e['cmp']['slug']}.html")} for e in items] + [{"@type": "Article", "headline": e["fc"]["h1"], "url": page_url(cfg, f"compare/{e['fc']['slug']}.html")} for e in forms]},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=desc, path=COMPARES_HUB, root="./", keywords="영양제 성분 비교, 영양제 차이, 홍삼 인삼 차이, 글루코사민 MSM 차이, 스피루리나 클로렐라 차이, rTG 오메가3 차이, 리포좀 비타민C 차이, 헴철 비헴철 차이, 영양제 추천", og_type="website", ld=ld)
    cards = "".join(
        f'<a class="cmp-card" href="compare/{esc(e["cmp"]["slug"])}.html"><span class="cmp-card-names">{" <em>vs</em> ".join(esc(i["name"]) for i in e["ingredients"])}</span><span class="mt-2 block text-base font-extrabold text-ink-900">{esc(e["cmp"]["h1"])}</span><span class="mt-1 line-clamp-2 block text-sm text-ink-500">{esc(e["cmp"]["intro"])}</span></a>'
        for e in items)
    forms_html = ""
    if forms:
        fcards = "".join(
            f'<a class="cmp-card" href="compare/{esc(e["fc"]["slug"])}.html"><span class="cmp-card-names">{esc(e["ingredient"]["name"])} <em>·</em> 형태 {len(e["forms"])}가지</span><span class="mt-2 block text-base font-extrabold text-ink-900">{esc(e["fc"]["h1"])}</span><span class="mt-1 line-clamp-2 block text-sm text-ink-500">{esc(e["fc"]["intro"])}</span></a>'
            for e in forms)
        forms_html = (f'<section id="forms" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">제형·형태 비교 {nf}편</h2><p class="mt-1 text-sm text-ink-500">같은 성분의 다른 형태(rTG·리포좀·헴철·마그네슘 염 등)를 원료·제조·표기·먹는 법 기준으로 비교하고, 식약처 신고 제품을 제품명·원재료명 표기로 걸러 형태별 제품 수와 예시를 보여 줍니다.</p>'
                      f'<div class="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{fcards}</div></section>')
    body = f"""
<body data-page="ingredients" data-path="{COMPARES_HUB}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="index.html">홈</a> › <span class="text-ink-800">성분 비교</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="scale"></i> 성분 비교</p>
      <h1 class="page-title mt-3">영양제 성분 비교: 비슷한 성분, 무엇이 다를까</h1>
      <p class="page-lead mt-4 max-w-3xl">이름이 비슷하거나 같은 고민에 함께 나오는 성분을 식약처 인정 기능성·권장량·먹는 시간·주의사항 기준으로 나란히 놓고, 어떤 상황에 무엇을 고를지와 같이 먹어도 되는지까지 정리했습니다. 가격이나 효과의 우열은 비교하지 않습니다. 같은 성분이라도 rTG·리포좀·헴철처럼 형태가 다른 제품은 아래 <a class="font-bold text-brand-700 underline" href="#forms">제형·형태 비교</a>에서 다룹니다.</p>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      <section id="pairs" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">성분 대 성분 비교 {n}편</h2><div class="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{cards}</div></section>
      {forms_html}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">읽는 법</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li>비교표의 기능성 문구는 식약처 인정 문구를 그대로 인용하며, 성분 사전과 같은 값입니다.</li><li>'이런 분은 이걸'은 인정 기능성과 주의사항 기준의 일반적인 선택 기준이지 진단이 아닙니다. 약을 복용 중이면 <a class="font-bold text-brand-700 underline" href="guide/with-medication.html">약과 영양제 가이드</a>를 먼저 보세요.</li><li>제형·형태 비교의 제품 수는 식약처 신고 제품의 제품명·원재료명 표기로 거른 값이라 표기가 없는 제품은 '기타·표기 없음' 묶음에 들어가고, 한 제품이 두 형태에 함께 셀 수 있습니다.</li><li>고민에서 출발하려면 <a class="font-bold text-brand-700 underline" href="finder.html">나에게 맞는 영양제 찾기</a>, 기능성 문구로 찾으려면 <a class="font-bold text-brand-700 underline" href="functions.html">기능성별 영양제</a>가 빠릅니다.</li></ul></section>
      {faq_html}
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def prepare_compares(core: dict, guides_items: list[dict]) -> dict | None:
    """data/compares.json 을 읽어 검증하고 모델을 만든다 (성분 페이지의 '비교 글' 칩이 먼저 필요하므로 main() 앞부분에서, 기능성 모델 뒤에 호출)."""
    data = read_json(DATA_DIR / "compares.json", None)
    if not data:
        log.warning("data/compares.json 이 없어 성분 비교 페이지를 만들지 않습니다")
        return None
    validate_compares(data, set(core["by_id"].keys()), {g["slug"] for g in guides_items})
    model = compare_model(data, core, guides_items)
    model["data"] = data
    core["compares"] = model
    return model


def write_compares(core: dict, cfg: dict, guides: dict) -> list[str]:
    """compare/<slug>.html · compare.html · data/compares-index.json 생성, 오래된 파일 정리. 생성한 slug 목록을 돌려준다(사이트맵)."""
    model = core.get("compares")
    if not model:
        return []
    COMPARE_DIR.mkdir(exist_ok=True)
    types = guides.get("_meta", {}).get("types", {})
    updated = (model["data"].get("_meta") or {}).get("updatedAt") or now_iso()[:10]
    wanted = set()
    for e in model["items"]:
        p = COMPARE_DIR / f"{e['cmp']['slug']}.html"
        p.write_text(render_compare(e, core, cfg, types, updated), encoding="utf-8")
        wanted.add(p.name)
    f_updated = ((model.get("forms_data") or {}).get("_meta") or {}).get("updatedAt") or updated
    for e in model.get("forms") or []:
        p = COMPARE_DIR / f"{e['fc']['slug']}.html"
        p.write_text(render_form_compare(e, core, cfg, types, f_updated), encoding="utf-8")
        wanted.add(p.name)
    for stale in COMPARE_DIR.glob("*.html"):
        if stale.name not in wanted:
            stale.unlink()
            log.info("삭제된 비교 페이지 정리: %s", stale.name)
    (ROOT / COMPARES_HUB).write_text(render_compare_hub(model, model["data"], core, cfg), encoding="utf-8")
    write_json(DATA_DIR / "compares-index.json", {
        "_meta": {"updatedAt": data_stamp(model["data"], model.get("forms_data"), default=core.get("updated_at") or now_iso()[:10]), "note": "compares.json(성분 대 성분)·form-compares.json(kind: form, 제형·형태) 의 요약 색인 — scripts/build_site.py 가 생성, 직접 수정하지 않음 (성분 페이지의 '비교 글' 칩용)"},
        "items": [{"slug": e["cmp"]["slug"], "title": _cmp_short_title(e["cmp"]), "ids": [i["id"] for i in e["ingredients"]]} for e in model["items"]]
                 + [{"slug": e["fc"]["slug"], "title": _cmp_short_title(e["fc"]), "ids": [e["fc"]["id"]], "kind": "form"} for e in (model.get("forms") or [])],
    }, compact=True, quiet=True)
    log.info("성분 비교 생성: %s + compare/ %d편 (제형·형태 비교 %d편 포함)", COMPARES_HUB, len(wanted), len(model.get("forms") or []))
    return [e["cmp"]["slug"] for e in model["items"]] + [e["fc"]["slug"] for e in (model.get("forms") or [])]


# ---------- 제형·형태 비교 (compare/<slug>.html, 성분 비교 허브의 두 번째 묶음) ----------
FORM_COMPARE_TOP = 8   # 형태별로 보여 주는 대표 제품 수 (브랜드 가중치 → 신고일 순, 같은 이름은 한 번)


def validate_form_compares(data: dict, valid_ids: set[str], guide_slugs: set[str], term_slugs: set[str], taken_slugs: set[str]) -> None:
    """data/form-compares.json 무결성: 필수 필드, slug 형식·중복(성분 비교 slug 와도 겹치지 않음), 기준 성분 id, forms(키가 다른 2개 이상·rest 최대 1·정규식 컴파일),
    rows 의 cells 키 = forms 키, faq q/a, related 가이드 slug, terms 용어 slug."""
    seen: set[str] = set()
    for it in data.get("items", []):
        tag = it.get("slug") or it.get("title")
        for k in ("slug", "id", "title", "h1", "description", "intro", "forms", "rows", "verdict", "label", "faq"):
            if not it.get(k):
                raise SystemExit(f"form-compares.json: '{tag}' 에 {k} 가 없음")
        slug = it["slug"]
        if not re.fullmatch(r"[a-z0-9-]+", slug) or slug in seen or slug in taken_slugs:
            raise SystemExit(f"form-compares.json: slug 형식 오류·중복 또는 성분 비교 slug 와 겹침 {slug}")
        seen.add(slug)
        if it["id"] not in valid_ids:
            raise SystemExit(f"form-compares.json: '{slug}' 이 없는 성분 id {it['id']} 를 참조")
        keys = [f.get("key") for f in it["forms"]]
        if len(keys) < 2 or not all(keys) or len(set(keys)) != len(keys):
            raise SystemExit(f"form-compares.json: '{slug}' 의 forms 는 key 가 서로 다른 2개 이상이어야 함")
        if sum(1 for f in it["forms"] if f.get("rest")) > 1:
            raise SystemExit(f"form-compares.json: '{slug}' 에 rest 형태가 둘 이상")
        for f in it["forms"]:
            for k in ("label", "short", "shopQuery", "line"):
                if not f.get(k):
                    raise SystemExit(f"form-compares.json: '{slug}' 형태 '{f.get('key')}' 에 {k} 가 없음")
            if f.get("rest"):
                continue
            if not f.get("match"):
                raise SystemExit(f"form-compares.json: '{slug}' 형태 '{f['key']}' 에 match 정규식이 없음 (rest 가 아니면 필수)")
            try:
                re.compile(f["match"], re.I)
            except re.error as e:
                raise SystemExit(f"form-compares.json: '{slug}' 형태 '{f['key']}' 의 정규식 오류: {e}") from None
        for r in it["rows"]:
            if not r.get("label") or set((r.get("cells") or {}).keys()) != set(keys):
                raise SystemExit(f"form-compares.json: '{slug}' 의 rows '{r.get('label')}' 셀 키가 forms 키와 다름")
        for f in it["faq"]:
            if not f.get("q") or not f.get("a"):
                raise SystemExit(f"form-compares.json: '{slug}' 의 faq 에 q/a 가 없음")
        for s in it.get("related", []):
            if s not in guide_slugs:
                raise SystemExit(f"form-compares.json: '{slug}' 이 없는 가이드 slug {s} 를 참조")
        for s in it.get("terms", []):
            if s not in term_slugs:
                raise SystemExit(f"form-compares.json: '{slug}' 이 없는 용어 slug {s} 를 참조")
    log.info("제형·형태 비교 데이터 검증 통과: %d편", len(seen))


def form_match_text(p: dict) -> str:
    """제형·형태 비교 정규식이 보는 문자열: '제품명 | 원재료명 | 제형:<식약처 신고 제형>'(액상·정·캡슐·분말·젤리·환·과립…).
    정규식이 '제형:(액상|겔)' 처럼 신고 제형으로도 형태를 가를 수 있다(홍삼 농축액·유산균 분말 등). 이름·원재료명에는 '제형:' 글자가 없어 기존 정규식과 충돌하지 않는다."""
    return f"{p.get('name') or ''} | {p.get('rawMaterials') or ''} | 제형:{(p.get('shape') or '').strip()}"


def form_compare_model(data: dict, core: dict, products: list[dict], guides: list[dict], glossary: dict | None, weight=None) -> list[dict]:
    """형태 비교마다 기준 성분의 신고 제품(상세 조각)을 제품명+원재료명+신고 제형(form_match_text 의 '제형:액상' 토큰) 정규식으로 형태별로 나누고(rest = 어느 형태에도 안 걸린 나머지; 한 제품이 여러 형태에 들어갈 수 있음),
    형태별 제품 수·대표 제품(브랜드 가중치 → 신고일 순, 같은 이름은 한 번)·관련 가이드·용어를 모은다. weight(name, company) 는 brand_priority 의 가중치."""
    by_id = core["by_id"]
    guide_by_slug = {g["slug"]: g for g in guides}
    by_slug = (glossary or {}).get("by_slug") or {}
    wcache: dict[str, int] = {}

    def w(p: dict) -> int:
        if p["id"] not in wcache:
            wcache[p["id"]] = int(weight(p.get("name"), p.get("company"))) if weight else 0
        return wcache[p["id"]]

    out = []
    for it in data.get("items", []):
        iid = it["id"]
        base = [p for p in products if iid in (p.get("ingredients") or [])]
        matched: set[str] = set()
        forms = []
        for f in it["forms"]:
            if f.get("rest"):
                forms.append({"f": f, "hits": None})
                continue
            rx = re.compile(f["match"], re.I)
            hits = [p for p in base if rx.search(form_match_text(p))]
            matched.update(p["id"] for p in hits)
            forms.append({"f": f, "hits": hits})
        for fm in forms:
            hits = fm.pop("hits")
            if hits is None:
                hits = [p for p in base if p["id"] not in matched]
            hits.sort(key=lambda p: (w(p), p.get("registeredAt") or ""), reverse=True)
            top, names = [], set()
            for p in hits:
                nm = (p.get("name") or "").strip()
                if not nm or nm in names:
                    continue
                names.add(nm)
                top.append({"id": p["id"], "name": nm, "company": p.get("company") or "", "registeredAt": p.get("registeredAt") or ""})
                if len(top) >= FORM_COMPARE_TOP:
                    break
            fm["total"] = len(hits)
            fm["ids"] = {p["id"] for p in hits}
            fm["top"] = top
        rel = [guide_by_slug[s] for s in it.get("related", []) if s in guide_by_slug]
        terms = [by_slug[s]["t"] for s in it.get("terms", []) if s in by_slug]
        out.append({"fc": it, "ingredient": by_id[iid], "forms": forms, "base_total": len(base), "guides": rel, "terms": terms})
    return out


def render_form_compare(entry: dict, core: dict, cfg: dict, guides_types: dict, updated: str) -> str:
    it, ing, forms, rel_guides, terms = entry["fc"], entry["ingredient"], entry["forms"], entry["guides"], entry["terms"]
    cats = core["categories"]
    cat = cats.get(ing["category"], {})
    path = f"compare/{it['slug']}.html"
    title = f"{it['title']} | {cfg['name']}"
    short_title = _cmp_short_title(it)
    _, faq_ld = faq_block([(f["q"], f["a"]) for f in it["faq"]])
    st = {"used": set(), "exclude": set()}   # 용어 자동 링크 상태 (소개 → 핵심 차이 → 이런 분은 → 라벨에서 보는 법 → FAQ)
    intro_html = term_html(core, it["intro"], st)
    verdict_html = term_html(core, it["verdict"], st)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "성분 비교", "item": page_url(cfg, COMPARES_HUB)},
            {"@type": "ListItem", "position": 3, "name": short_title, "item": page_url(cfg, path)}]},
        {"@type": "Article", "headline": it["h1"], "description": it["description"], "url": page_url(cfg, path), "dateModified": updated, "inLanguage": "ko",
         "author": {"@type": "Organization", "name": cfg["name"]}, "about": [{"@type": "Thing", "name": ing["name"], "url": page_url(cfg, f"i/{ing['id']}.html")}]},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=it["description"], path=path, root="../", keywords=", ".join(it.get("keywords", [])), og_type="article",
                     extra_scripts='<script src="../assets/js/pages/compare.js" defer></script>', ld=ld)
    keys = [fm["f"]["key"] for fm in forms]
    mini = (f'<a class="cmp-mini" href="../i/{esc(ing["id"])}.html"><span class="finder-thumb">{photo_img(ing["category"])}</span><span class="min-w-0"><span class="badge {cat_class(cat.get("color", ""))}">{esc(cat.get("label", ""))}</span>'
            f'<span class="mt-1 block text-base font-extrabold text-ink-900">{esc(ing["name"])} 성분 사전</span><span class="mt-0.5 block text-sm text-ink-600">효능·권장량·궁합·먹는 시간 — 형태와 관계없이 같은 기준 · 수집 제품 {entry["base_total"]:,}건</span></span></a>')
    head_cells = "".join(f'<th scope="col">{esc(fm["f"]["label"])}</th>' for fm in forms)
    body_rows = "".join(f'<tr><th scope="row">{esc(r["label"])}</th>' + "".join(f'<td>{esc((r.get("cells") or {}).get(k, "—"))}</td>' for k in keys) + "</tr>" for r in it["rows"])
    body_rows += '<tr><th scope="row">수집 제품 수 (표기 기준)</th>' + "".join(f'<td>{fm["total"]:,}건</td>' for fm in forms) + "</tr>"
    table_html = f'<div class="timing-table-wrap"><table class="timing-table cmp-table"><caption class="sr-only">{esc(ing["name"])} 형태 비교표</caption><thead><tr><th scope="col">항목</th>{head_cells}</tr></thead><tbody>{body_rows}</tbody></table></div>'

    picks_html = "".join(
        f'<article class="finder-card"><h3 class="text-base font-extrabold text-ink-900">{esc(fm["f"]["label"])}</h3><p class="mt-1 text-sm text-ink-600">{term_html(core, fm["f"]["line"], st)}</p>'
        f'<ul class="list-check mt-2 text-sm text-ink-700">{"".join(f"<li>{term_html(core, p, st)}</li>" for p in fm["f"].get("pick", []))}</ul></article>'
        for fm in forms)
    label_html = term_html(core, it["label"], st)

    def product_card(fm: dict) -> str:
        f = fm["f"]
        chips = "".join(f'<li><a class="hover:text-brand-700" href="../product.html?id={esc(p["id"])}">{esc(p["name"])}</a><span class="ml-1 text-xs text-ink-400">{esc(p["company"])}</span></li>' for p in fm["top"])
        return (f'<div class="rounded-2xl border border-ink-100 bg-white p-5 shadow-card"><h3 class="font-extrabold text-ink-900">{esc(f["label"])}</h3><p class="mt-1 text-sm text-ink-600">{esc(f["short"])}</p>'
                f'<p class="mt-2 text-xs text-ink-500">수집 제품 {fm["total"]:,}건 · 쇼핑몰 검색어: {esc(f["shopQuery"])}</p><div class="app-hide mt-3" data-query="{esc(f["shopQuery"])}"></div>'
                + (f'<p class="mt-3 text-xs font-bold text-ink-500">표기로 걸러낸 신고 제품</p><ul class="list-dot mt-1 text-sm text-ink-700">{chips}</ul>' if chips else '<p class="mt-3 text-xs text-ink-400">수집분에서 이 표기가 적힌 제품이 없습니다.</p>')
                + "</div>")
    products_html = (f'<div class="grid gap-4 md:grid-cols-2">{"".join(product_card(fm) for fm in forms)}</div>'
                     f'<p class="mt-3 text-sm text-ink-600">제품명과 원재료명의 표기로 나눈 것이라 표기가 없는 제품은 \'{esc(next((fm["f"]["label"] for fm in forms if fm["f"].get("rest")), "기타"))}\' 묶음에 들어가고, 한 제품이 두 형태에 함께 셀 수 있습니다. '
                     f'<a class="font-bold text-brand-700 underline" href="../products.html?ingredient={esc(ing["id"])}">{esc(ing["name"])} 제품 전체 보기</a></p><p id="compare-disclosure" class="app-hide mt-3 text-[11px] text-ink-400"></p>')
    terms_html = "".join(f'<a class="chart-chip" href="../term/{esc(t["slug"])}.html" title="{esc(t.get("short", ""))}"><i data-lucide="book-open" class="h-3.5 w-3.5"></i>{esc(t["term"])}</a>' for t in terms)
    guides_html = f'<div class="grid gap-4 md:grid-cols-2">{"".join(guide_card(g, guides_types, "../") for g in rel_guides)}</div>' if rel_guides else ""
    faq_html, _ = faq_block([(f["q"], f["a"]) for f in it["faq"]], render=lambda s: term_html(core, s, st))
    chips = [("table", "비교표"), ("verdict", "핵심 차이"), ("picks", "이런 분은"), ("label", "라벨에서 보는 법"), ("products", "형태별 제품"), ("faq", "자주 묻는 질문")]
    body = f"""
<body data-page="ingredients" data-path="{path}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="../index.html">홈</a> › <a class="hover:text-brand-700" href="../{COMPARES_HUB}">성분 비교</a> › <span class="text-ink-800">{esc(short_title)}</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="scale"></i> 성분 비교 · 제형·형태</p>
      <h1 class="page-title mt-3">{esc(it["h1"])}</h1>
      <p class="page-lead mt-4 max-w-3xl">{intro_html}</p>
      <div class="mt-6 grid gap-3 md:grid-cols-2">{mini}<div class="cmp-mini" style="cursor:default"><span class="min-w-0"><span class="text-xs font-bold text-ink-500">이 글의 형태 {len(forms)}가지</span><span class="mt-1 block text-sm leading-relaxed text-ink-800">{" · ".join(esc(fm["f"]["label"]) for fm in forms)}</span><span class="mt-1 block text-xs text-ink-500">식약처 신고 제품의 제품명·원재료명 표기로 걸러 형태별 제품 수와 예시를 보여 줍니다.</span></span></div></div>
      <div class="mt-5 flex flex-wrap gap-2">{"".join(f'<a href="#{a}" class="chip">{b}</a>' for a, b in chips)}</div>
      <p class="mt-4 text-xs text-ink-400">식약처 인정 기능성 표현을 기준으로 정리한 일반 건강 정보이며 의학적 조언이 아닙니다 · 최종 수정 {esc(updated)}</p>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      <section id="table" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">형태별 한눈에 비교</h2><p class="mt-1 text-sm text-ink-500">원료·제조·표기·먹는 법 같은 사실 관계만 비교합니다. 흡수율 수치·가격·효과의 우열은 적지 않으며, 기능성과 섭취량 기준은 형태와 관계없이 <a class="font-bold text-brand-700 underline" href="../i/{esc(ing["id"])}.html">{esc(ing["name"])} 성분 사전</a>과 같습니다.</p><div class="mt-4">{table_html}</div></section>
      <section id="verdict" class="scroll-mt-24 rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">핵심 차이</h2><p class="mt-3 text-[15px] leading-relaxed text-ink-800">{verdict_html}</p></section>
      <section id="picks" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">이런 분은 이 형태</h2><div class="mt-4 grid gap-4 md:grid-cols-2">{picks_html}</div></section>
      <section id="label" class="scroll-mt-24 rounded-3xl border border-ink-100 bg-white p-6 shadow-card sm:p-8"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">라벨에서 보는 법</h2><p class="mt-3 text-[15px] leading-relaxed text-ink-800">{label_html}</p></section>
      <section id="products" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">형태별 제품 보기</h2><p class="mt-1 text-sm text-ink-500">식약처 품목신고 수집분(2021-04 이후)에서 제품명·원재료명 표기로 걸러낸 제품과 쇼핑몰 검색 결과입니다. 함량·형태·원료는 제품 라벨에서 꼭 확인하세요.</p><div class="mt-4">{products_html}</div></section>
      {('<section id="terms" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">관련 용어</h2><div class="mt-4 flex flex-wrap gap-2">' + terms_html + '</div></section>') if terms_html else ""}
      {('<section id="guides" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">관련 가이드</h2><div class="mt-4">' + guides_html + '</div></section>') if guides_html else ""}
      {faq_html}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">함께 보면 좋은 페이지</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li><a class="font-bold text-brand-700 underline" href="../{COMPARES_HUB}">성분 비교 전체 목록</a> — 성분 대 성분 비교와 다른 형태 비교</li><li><a class="font-bold text-brand-700 underline" href="../i/{esc(ing["id"])}.html">{esc(ing["name"])} 성분 사전</a> — 효능·권장량·궁합·먹는 시간</li><li><a class="font-bold text-brand-700 underline" href="../glossary.html">영양제 용어 사전</a> · <a class="font-bold text-brand-700 underline" href="../finder.html">나에게 맞는 영양제 찾기</a> · <a class="font-bold text-brand-700 underline" href="../timing-chart.html">영양제 복용 시간표</a></li></ul></section>
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def prepare_form_compares(core: dict, guides_items: list[dict]) -> list[dict] | None:
    """data/form-compares.json 을 읽어 검증하고 모델을 만들어 성분 비교 모델(core["compares"])에 forms 로 더한다 (용어 사전·기능성 모델 뒤, 성분 페이지 앞)."""
    data = read_json(DATA_DIR / "form-compares.json", None)
    if not data:
        log.warning("data/form-compares.json 이 없어 제형·형태 비교 페이지를 만들지 않습니다")
        return None
    cmp_model = core.get("compares")
    if not cmp_model:
        cmp_model = {"items": [], "by_ingredient": {}, "data": {"_meta": {}}}
        core["compares"] = cmp_model
    taken = {e["cmp"]["slug"] for e in cmp_model.get("items", [])}
    glossary = core.get("glossary")
    validate_form_compares(data, set(core["by_id"].keys()), {g["slug"] for g in guides_items}, set((glossary or {}).get("by_slug") or {}), taken)
    products = core.get("products_detail")
    if products is None:
        products = load_products_detail()
        core["products_detail"] = products
    try:
        weight = load_brand_priority().weight
    except Exception:  # noqa: BLE001
        weight = None
    forms = form_compare_model(data, core, products, guides_items, glossary, weight)
    cmp_model["forms"] = forms
    cmp_model["forms_data"] = data
    for e in forms:
        cmp_model.setdefault("by_ingredient", {}).setdefault(e["fc"]["id"], []).append(e["fc"]["slug"])
    return forms


# ---------- 약별 영양제 가이드 (drug-guides.html · drug-guide/<id>.html) ----------
DRUG_GUIDE_DIR = ROOT / "drug-guide"
DRUG_GUIDES_HUB = "drug-guides.html"
DRUG_GUIDE_TOP = 8   # 분류별로 보여 주는 대표 의약품 수 (브랜드 가중치 순)
DRUG_EXTERNAL_RE = re.compile(r"연고|크림|로션|패취|패치|플라스타|카타플라스마|좌제|점안|점비|점이|외용|스프레이|가글|구강용|습포|테이프|밴드|소독|파스|샴푸|비누|세정제|관장|질정|주사|수액|좌약|두피|겔(제|$|\(|\d)")   # assets/js/data.js drugPairingFor 의 external 정규식과 같아야 함 (tests/test_build_site.py 가 대조)
DRUG_EXTERNAL_USAGE_RE = re.compile(r"바릅니다|바르십시오|도포")   # 사용법이 '바릅니다' 면 외용제 (data.js 와 같은 규칙)


def drug_is_external(name: str, usage: str = "") -> bool:
    """외용제(연고·파스·두피액 등) 판정 — oralOnly 규칙(먹는 약 전용)에서 뺀다."""
    return bool(DRUG_EXTERNAL_RE.search(name or "")) or bool(DRUG_EXTERNAL_USAGE_RE.search(usage or ""))


def drug_rule_hits(rule: dict, drug: dict) -> bool:
    """assets/js/data.js 의 drugPairingFor 와 같은 판정: 주성분 영문(없으면 한글) 부분 일치 · 분류(cls) · 제품명 키워드(names). oralOnly 규칙은 외용제 제외."""
    if rule.get("oralOnly") and drug_is_external(str(drug.get("name") or ""), str(drug.get("usage") or "")):
        return False
    tokens = [str(t).lower() for t in (drug.get("ingrEn") if drug.get("ingrEn") else (drug.get("ingr") or []))]
    cls = str(drug.get("cls") or "")
    name = str(drug.get("name") or "")
    return (any(any(k.lower() in t for t in tokens) for k in (rule.get("ingr") or []))
            or any(bool(cls) and (cls == c or c in cls) for c in (rule.get("cls") or []))
            or any(n in name for n in (rule.get("names") or [])))


def load_drugs_detail() -> list[dict]:
    """의약품 상세 조각 전체 (data/drugs/detail/*.json, 수집 전이면 빈 목록)."""
    items: list[dict] = []
    for f in sorted((DATA_DIR / "drugs" / "detail").glob("*.json")):
        items += (read_json(f, {}) or {}).get("items", [])
    return items


def validate_drug_guides(data: dict, rules: list[dict], valid_ids: set[str], guide_slugs: set[str]) -> None:
    """data/drug-guides.json: 규칙 id 와 1:1, 필수 항목, related 가이드 slug, 규칙의 성분 id 를 확인한다."""
    rule_ids = [r.get("id") for r in rules]
    seen: set[str] = set()
    for it in data.get("items") or []:
        i = it.get("id")
        if not i or i not in rule_ids:
            raise SystemExit(f"drug-guides.json: drug-pairings.json 에 없는 규칙 id {i!r}")
        if i in seen:
            raise SystemExit(f"drug-guides.json: 중복 id {i}")
        seen.add(i)
        for k in ("short", "title", "h1", "description", "intro"):
            if not str(it.get(k) or "").strip():
                raise SystemExit(f"drug-guides.json[{i}]: {k} 가 비어 있음")
        for k in ("keywords", "drugs", "timing", "faq", "related"):
            if not isinstance(it.get(k), list):
                raise SystemExit(f"drug-guides.json[{i}]: {k} 는 목록이어야 함")
        if not it["drugs"] or not it["timing"] or not it["faq"]:
            raise SystemExit(f"drug-guides.json[{i}]: drugs·timing·faq 는 비울 수 없음")
        if any(not (f.get("q") and f.get("a")) for f in it["faq"]):
            raise SystemExit(f"drug-guides.json[{i}]: faq 항목에 q·a 가 필요")
        bad = [s for s in it["related"] if s not in guide_slugs]
        if bad:
            raise SystemExit(f"drug-guides.json[{i}]: 없는 가이드 slug {bad}")
    missing = [r for r in rule_ids if r not in seen]
    if missing:
        raise SystemExit(f"drug-guides.json: 규칙에 본문이 없음 {missing}")
    bad_ids = [(r.get("id"), x.get("id")) for r in rules for k in ("good", "caution") for x in r.get(k, []) if x.get("id") not in valid_ids]
    if bad_ids:
        raise SystemExit(f"drug-pairings.json 에 없는 성분 id: {bad_ids}")


def drug_guide_model(data: dict, rules: list[dict], core: dict, drugs: list[dict], guides: list[dict], weight=None, kw_weight=None) -> dict:
    """규칙(좋은/주의 성분·간격·메모) + 수동 본문 + 의약품 상세 조각(분류별 약 수·대표 제품) + 가이드를 묶는다."""
    by_id = core["by_id"]
    rules_by = {r["id"]: r for r in rules}
    g_by = {g["slug"]: g for g in guides}
    items: list[dict] = []
    by_ing: dict[str, list[dict]] = {}
    for it in data["items"]:
        r = rules_by[it["id"]]
        good = [{"id": g["id"], "name": by_id[g["id"]]["name"], "why": g.get("why", ""), "hours": g.get("hours")} for g in r.get("good", []) if g["id"] in by_id]
        caution = [{"id": c["id"], "name": by_id[c["id"]]["name"], "why": c.get("why", ""), "hours": c.get("hours")} for c in r.get("caution", []) if c["id"] in by_id]
        matched = [d for d in drugs if drug_rule_hits(r, d)]
        inn_ko = [k for k in (to_korean(x) for x in (r.get("ingr") or [])) if re.search(r"[가-힣]", k)]   # 대표 제품 고르기: 브랜드 가중치 → 브랜드 키워드 → 성분명이 안 들어간 짧은 이름 우선

        def rank(d: dict) -> tuple:
            name = str(d.get("name") or "")
            base = re.split(r"[(\[]", name)[0]
            generic = any(k in base for k in inn_ko)   # '경남나프록센연질캡슐' 처럼 이름에 성분명이 든 제네릭은 뒤로
            n_ingr = len(d.get("ingrEn") or d.get("ingr") or [])   # 단일 성분 제품(우루사정·리피토정)을 복합제(베아제·로수바미브)보다 먼저 — 분류를 대표하는 약
            return (-(kw_weight(name) if kw_weight else 0), -(weight(name, d.get("company") or "") if weight else 0), generic, n_ingr, len(base), name)   # 브랜드명이 이름에 드러난 제품(우루사·타이레놀·리피토…)을 제조사 가중치보다 먼저 — 대형 제약사 제네릭이 대표 자리를 차지하지 않게
        buckets: dict[str, list[dict]] = {}   # 제조사별로 묶어 돌아가며 뽑는다 — 한 브랜드(이지엔6 6종…)가 목록을 독점하지 않게
        seen_names: set[str] = set()
        for d in sorted(matched, key=rank):
            nm = str(d.get("name") or "")
            if nm in seen_names:
                continue
            seen_names.add(nm)
            buckets.setdefault(str(d.get("company") or ""), []).append({"id": d["id"], "name": nm, "company": d.get("company") or "", "otc": d.get("otc") or ""})
        top: list[dict] = []
        while len(top) < DRUG_GUIDE_TOP and any(buckets.values()):
            for lst in buckets.values():
                if lst and len(top) < DRUG_GUIDE_TOP:
                    top.append(lst.pop(0))
        entry = {"dg": it, "rule": r, "good": good, "caution": caution, "note": str(r.get("note") or "").strip(),
                 "drugs": {"total": len(matched), "otc": sum(1 for d in matched if "일반" in str(d.get("otc") or "")), "top": top},
                 "guides": [g_by[s] for s in it.get("related", []) if s in g_by]}
        items.append(entry)
        for g in good:
            by_ing.setdefault(g["id"], []).append({"id": it["id"], "short": it["short"], "kind": "good"})
        for c in caution:
            by_ing.setdefault(c["id"], []).append({"id": it["id"], "short": it["short"], "kind": "caution"})
    return {"items": items, "by_ingredient": by_ing}


def _dg_hours(h) -> str:
    return f"{h}시간 이상 간격" if h else ""


def render_drug_guide(entry: dict, core: dict, cfg: dict, guides_types: dict, updated: str) -> str:
    dg, rule, good, caution = entry["dg"], entry["rule"], entry["good"], entry["caution"]
    by_id, cats = core["by_id"], core["categories"]
    path = f"drug-guide/{dg['id']}.html"
    rx = bool(dg.get("rx"))
    n_drugs = entry["drugs"]["total"]
    title = f"{dg['title']} | {cfg['name']}"
    desc = dg["description"][:300]
    _, faq_ld = faq_block([(f["q"], f["a"]) for f in dg["faq"]])
    st = {"used": set(), "exclude": set()}   # 용어 자동 링크 상태 (소개 → 요약 표 → 좋은/주의 → 복용 요령 → FAQ)
    intro_html = term_html(core, dg["intro"], st)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "약별 영양제 가이드", "item": page_url(cfg, DRUG_GUIDES_HUB)},
            {"@type": "ListItem", "position": 3, "name": dg["short"], "item": page_url(cfg, path)}]},
        {"@type": "Article", "headline": dg["h1"], "description": desc, "url": page_url(cfg, path), "inLanguage": "ko", "dateModified": updated,
         "about": {"@type": "Thing", "name": rule.get("label") or dg["short"]},
         "author": {"@type": "Organization", "name": cfg["name"], "url": f"{cfg['url']}/"}, "publisher": {"@type": "Organization", "name": cfg["name"], "url": f"{cfg['url']}/"}},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=desc, path=path, root="../", keywords=", ".join(dg.get("keywords") or []), og_type="article", ld=ld)
    ingr_ko: list[str] = []
    for k in rule.get("ingr") or []:
        ko = to_korean(k)
        if ko and ko not in ingr_ko:
            ingr_ko.append(ko)
    ingr_ko = ingr_ko[:8]

    rows = [('<span class="badge badge-synergy">함께 챙기면 좋아요</span>', g) for g in good] + [('<span class="badge badge-caution">주의</span>', c) for c in caution]
    summary_html = (f'<div class="timing-table-wrap"><table class="timing-table dg-table"><caption class="sr-only">{esc(dg["short"])}와 영양 성분 조합 요약</caption><thead><tr><th scope="col">영양 성분</th><th scope="col">판정</th><th scope="col">간격</th><th scope="col">이유</th></tr></thead><tbody>'
                    + "".join(f'<tr><th scope="row"><a href="../i/{esc(x["id"])}.html">{esc(x["name"])}</a></th><td>{badge}</td><td>{esc(_dg_hours(x.get("hours")) or "—")}</td><td class="timing-note">{term_html(core, x["why"], st)}</td></tr>' for badge, x in rows)
                    + '</tbody></table></div>') if rows else \
        '<p class="rounded-2xl border border-dashed border-ink-200 bg-white p-5 text-sm leading-relaxed text-ink-600">이 분류의 약과 특별히 겹치거나 시간을 띄워야 하는 영양 성분으로 정리된 것은 없습니다. 아래 복용 요령과 성분 사전의 주의사항을 확인하고, 약을 복용 중이면 새 영양제를 시작하기 전에 약사·의사와 상의하세요.</p>'

    def good_card(g: dict) -> str:
        i = by_id[g["id"]]
        cat = cats.get(i["category"], {})
        return (f'<article class="ing-card"><div class="flex items-start gap-3"><span class="finder-thumb">{photo_img(i["category"])}</span><div class="min-w-0 flex-1">'
                f'<span class="badge {cat_class(cat.get("color", ""))}">{esc(cat.get("label", ""))}</span><h3 class="mt-1 text-base font-extrabold text-ink-900"><a class="hover:text-brand-700" href="../i/{esc(i["id"])}.html">{esc(i["name"])}</a></h3>'
                f'<p class="mt-1.5 text-sm leading-relaxed text-ink-700">{term_html(core, g["why"], st)}</p>'
                + (f'<p class="mt-1 text-xs font-bold text-amber-700">{esc(_dg_hours(g["hours"]))}</p>' if g.get("hours") else "")
                + f'<p class="mt-2 text-xs text-ink-500"><i data-lucide="badge-check" class="inline h-3.5 w-3.5 text-brand-600"></i> {esc(i.get("mfdsFunction") or "")}</p>'
                f'<div class="mt-3 flex flex-wrap gap-2"><button type="button" class="btn-outline" data-my-add="{esc(i["id"])}"><i data-lucide="plus"></i>내 영양제에 추가</button></div>'
                f'</div></div></article>')
    good_html = (f'<section id="good" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">함께 챙기면 좋은 영양 성분</h2><p class="mt-1 text-sm text-ink-500">이 약을 오래 먹을 때 부족해지기 쉽거나 같은 목적으로 흔히 함께 챙기는 성분입니다. 시작 전에 의사·약사와 상의하세요.</p>'
                 f'<div class="mt-4 grid gap-4 md:grid-cols-2">{"".join(good_card(g) for g in good)}</div></section>') if good else ""
    caution_html = (f'<section id="caution" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">같이 먹을 때 주의할 영양 성분</h2><p class="mt-1 text-sm text-ink-500">흡수를 방해하거나 작용이 겹치는 성분입니다. 간격이 적힌 것은 시간을 띄우면 되고, 나머지는 용량·검사·상담이 필요합니다.</p><ul class="mt-3 space-y-2">'
                    + "".join(f'<li class="finder-pair finder-pair-caution"><span class="badge badge-caution">주의</span><div><p class="font-bold text-ink-900"><a class="hover:text-brand-700" href="../i/{esc(c["id"])}.html">{esc(c["name"])}</a>{(" · " + esc(_dg_hours(c["hours"]))) if c.get("hours") else ""}</p><p class="text-sm text-ink-600">{term_html(core, c["why"], st)}</p></div></li>' for c in caution)
                    + '</ul></section>') if caution else ""
    howto_html = ('<ul class="list-dot mt-3 space-y-2 text-[15px] leading-relaxed text-ink-800">' + "".join(f"<li>{term_html(core, t, st)}</li>" for t in dg["timing"]) + "</ul>"
                  + (f'<div class="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950"><strong>메모</strong> — {esc(entry["note"])}</div>' if entry["note"] else ""))
    drugs_list = '<ul class="list-dot mt-3 text-sm leading-relaxed text-ink-700">' + "".join(f"<li>{esc(x)}</li>" for x in dg["drugs"]) + "</ul>"
    top = entry["drugs"]["top"]
    if top:
        first_ko = ingr_ko[0] if ingr_ko else dg["short"]
        drug_rows = "".join(f'<li class="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between"><div class="min-w-0"><a class="font-bold text-ink-900 hover:text-brand-700" href="../drug.html?id={esc(d["id"])}">{esc(d["name"])}</a><span class="ml-2 text-xs font-semibold text-ink-500">{esc(d["company"])}</span></div><span class="badge badge-neutral">{esc(d["otc"] or "의약품")}</span></li>' for d in top)
        drugs_html = (drugs_list + f'<h3 class="mt-6 text-base font-extrabold text-ink-900">식약처 허가 의약품 {n_drugs:,}건 중 대표 제품</h3><p class="mt-1 text-xs text-ink-500">식약처 허가 의약품(일반의약품은 e약은요 등록분, 전문의약품은 분류별 허가 목록 수집분) 가운데 주성분·분류가 이 규칙에 해당하는 제품입니다. 알려진 브랜드 순으로 {len(top)}건을 보여 주며, 의약품은 구매 링크를 제공하지 않습니다. 전문의약품 상세는 허가정보(주성분·분류·허가일)와 의약품안전나라 링크만 표시합니다.</p>'
                      f'<ul class="mt-2 divide-y divide-ink-100">{drug_rows}</ul><p class="mt-3 text-sm"><a class="font-bold text-brand-700 underline" href="../search.html?q={esc(first_ko)}">‘{esc(first_ko)}’ 의약품 더 찾기 →</a></p>')
    else:
        drugs_html = drugs_list + '<p class="mt-4 rounded-xl border border-dashed border-ink-200 bg-white p-4 text-sm leading-relaxed text-ink-600">이 분류에 해당하는 식약처 허가 제품이 아직 수집되지 않았습니다. 전문의약품 목록은 허가정보에서 분류별 주성분으로 매일 새벽 수집해 채워지며, 복용 중인 약은 처방전·약봉투의 성분명으로 확인하세요.</p>'
    faq_html, _ = faq_block([(f["q"], f["a"]) for f in dg["faq"]], render=lambda s: term_html(core, s, st))
    rel = entry["guides"]
    guides_html = (f'<section id="guides" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">관련 가이드</h2><p class="mt-1 text-sm text-ink-500">약 복용자 상황별로 어떤 성분을 어떻게 조합할지는 가이드에서 자세히 설명합니다.</p><div class="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{"".join(guide_card(g, guides_types, "../") for g in rel)}</div></section>') if rel else ""
    chips = ('<div class="mt-4 flex flex-wrap items-center gap-2"><span class="text-xs font-bold text-ink-400">대표 성분</span>' + "".join(f'<span class="chip cursor-default">{esc(k)}</span>' for k in ingr_ko) + '</div>') if ingr_ko else ""
    nav_chips = ('<a href="#summary" class="chip">한눈에 보기</a>' + ('<a href="#good" class="chip">좋은 성분</a>' if good else "") + ('<a href="#caution" class="chip">주의 성분</a>' if caution else "")
                 + '<a href="#howto" class="chip">복용 요령</a><a href="#drugs" class="chip">이 분류의 약</a>' + ('<a href="#guides" class="chip">가이드</a>' if rel else "") + '<a href="#faq" class="chip">자주 묻는 질문</a>')
    drugs_stat = f'<li class="inline-flex items-center gap-1.5"><i data-lucide="pill-bottle" class="h-4 w-4 text-brand-600"></i>식약처 허가 의약품 <strong>{n_drugs:,}건</strong></li>' if n_drugs else '<li class="inline-flex items-center gap-1.5"><i data-lucide="pill-bottle" class="h-4 w-4 text-brand-600"></i>처방약 — <strong>성분명으로 확인</strong></li>'
    body = f"""
<body data-page="guides" data-path="{path}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="../index.html">홈</a> › <a class="hover:text-brand-700" href="../{DRUG_GUIDES_HUB}">약별 영양제 가이드</a> › <span class="text-ink-800">{esc(dg["short"])}</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="pill"></i> 약별 영양제 가이드 · {"처방약(전문의약품) 중심" if rx else "일반의약품"}</p>
      <h1 class="page-title mt-3">{esc(dg["h1"])}</h1>
      <p class="page-lead mt-4 max-w-3xl">{intro_html}</p>
      {chips}
      <ul class="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm text-ink-600">
        <li class="inline-flex items-center gap-1.5"><i data-lucide="heart-handshake" class="h-4 w-4 text-brand-600"></i>함께 챙기면 좋은 성분 <strong>{len(good)}</strong></li>
        <li class="inline-flex items-center gap-1.5"><i data-lucide="triangle-alert" class="h-4 w-4 text-amber-600"></i>주의할 성분 <strong>{len(caution)}</strong></li>
        {drugs_stat}
      </ul>
      <div class="mt-6 flex flex-wrap items-center gap-3"><a href="#summary" class="btn-primary"><i data-lucide="table"></i>조합 한눈에 보기 <i data-lucide="arrow-right"></i></a><a href="../compatibility.html" class="btn-outline"><i data-lucide="heart-handshake"></i>영양제끼리 궁합 체크</a></div>
      <div class="mt-5 flex flex-wrap gap-2">{nav_chips}</div>
      <p class="mt-4 text-xs text-ink-400">식약처 허가정보·e약은요와 널리 알려진 상호작용 안내를 바탕으로 정리한 일반 정보이며 의학적 조언이 아닙니다. 약을 복용 중이면 영양제를 더하기 전에 의사·약사와 상담하세요 · 최종 수정 {esc(updated)}</p>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      <section id="summary" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">한눈에 보기</h2><p class="mt-1 text-sm text-ink-500">{esc(rule.get("label") or dg["short"])} 분류의 주성분 기준으로 정리한 영양 성분 조합입니다. 성분을 누르면 효능·권장량·먹는 시간을 봅니다.</p><div class="mt-4">{summary_html}</div></section>
      {good_html}
      {caution_html}
      <section id="howto" class="scroll-mt-24 rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">복용 요령</h2>{howto_html}</section>
      <section id="drugs" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">이 분류의 약</h2><p class="mt-1 text-sm text-ink-500">대표 성분과 제품 예시입니다. 의약품은 약사·의사의 안내에 따라 사용하며, 이 사이트는 의약품 구매 링크를 제공하지 않습니다.</p><div class="mt-2">{drugs_html}</div></section>
      {guides_html}
      {faq_html}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">함께 보면 좋은 페이지</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li><a class="font-bold text-brand-700 underline" href="../{DRUG_GUIDES_HUB}">약별 영양제 가이드 전체 목록</a></li><li><a class="font-bold text-brand-700 underline" href="../guide/with-medication.html">약과 영양제 같이 먹어도 될까</a> — 약 종류별 주의 성분 총정리</li><li><a class="font-bold text-brand-700 underline" href="../compatibility.html">영양제 궁합 체크</a> · <a class="font-bold text-brand-700 underline" href="../timing-chart.html">영양제 복용 시간표</a></li><li><a class="font-bold text-brand-700 underline" href="../ingredients.html">성분 사전</a> — 성분별 '약과 함께 먹을 때' 주의사항</li></ul></section>
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def render_drug_guides_hub(model: dict, data: dict, core: dict, cfg: dict) -> str:
    items = model["items"]
    n = len(items)
    otc = [e for e in items if not e["dg"].get("rx")]
    rx = [e for e in items if e["dg"].get("rx")]
    title = f"약별 영양제 가이드 — 약 먹을 때 같이 먹어도 되는 영양제·주의 성분·간격 {n}종 | {cfg['name']}"
    desc = "타이레놀·소염진통제·제산제·위산억제제·감기약·변비약·피임약 같은 일반의약품부터 스타틴·갑상선약·와파린·항생제·골다공증약·메트포르민·이뇨제·스테로이드 같은 처방약까지, 약 분류별로 함께 챙기면 좋은 영양 성분, 시간을 띄워야 하는 성분, 복용 요령, 해당 식약처 허가 의약품을 정리했습니다."
    faq_items = [
        ("약을 먹는 동안 영양제를 아예 끊어야 하나요?", "대부분은 아닙니다. 흡수를 방해하는 조합은 시간을 띄우면 되고, 작용이 겹치는 조합만 용량을 조정하거나 피합니다. 다만 와파린·갑상선약·메토트렉세이트처럼 민감한 약은 새 영양제를 시작하기 전에 반드시 의사·약사와 상의하세요."),
        ("'간격'은 어떻게 지키나요?", "약을 먼저 먹고 적힌 시간(대개 2~4시간) 뒤에 영양제를 먹는 것이 기본입니다. 아침 공복 약(갑상선약·골다공증약)이라면 미네랄 영양제를 점심·저녁 식후로 옮기면 자연히 간격이 생깁니다. 내 영양제 시간표 기능으로 시간대를 나눠 두면 편합니다."),
        ("처방약 제품 목록은 어디서 오나요?", "일반의약품은 식약처 e약은요 등록분을, 전문의약품(처방약)은 식약처 의약품 제품 허가정보에서 분류별 주성분으로 수집한 허가 목록을 씁니다. 처방약은 e약은요 설명이 없어 의약품 페이지에 허가정보(주성분·분류·허가일)와 의약품안전나라 링크만 보여 주며, 아직 수집 전이거나 분류에 제품이 없으면 대표 성분·제품 예시를 보고 처방전·약봉투의 성분명으로 확인하세요."),
    ]
    faq_html, faq_ld = faq_block(faq_items)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"}, {"@type": "ListItem", "position": 2, "name": "약별 영양제 가이드", "item": page_url(cfg, DRUG_GUIDES_HUB)}]},
        {"@type": "CollectionPage", "name": "약별 영양제 가이드", "url": page_url(cfg, DRUG_GUIDES_HUB), "description": desc,
         "hasPart": [{"@type": "WebPage", "name": e["dg"]["title"], "url": page_url(cfg, f"drug-guide/{e['dg']['id']}.html")} for e in items]},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=desc, path=DRUG_GUIDES_HUB, root="./", keywords="약과 영양제 같이, 약 먹을 때 영양제, 약별 영양제 가이드, 영양제 복용 간격, 약 영양제 궁합, 처방약 영양제", og_type="website", ld=ld)

    def card(e: dict) -> str:
        dg, total = e["dg"], e["drugs"]["total"]
        kind = ("처방약" if dg.get("rx") else "일반의약품") + (f" · 약 {total:,}건" if total else "")
        chips = "".join(f'<span class="chart-chip chart-chip-synergy">{esc(g["name"])}</span>' for g in e["good"][:3]) + "".join(f'<span class="chart-chip chart-chip-caution">{esc(c["name"])}</span>' for c in e["caution"][:4])
        more = len(e["good"][3:]) + len(e["caution"][4:])
        if more:
            chips += f'<span class="chart-chip">+{more}</span>'
        if not chips:
            chips = '<span class="chart-chip">정리된 조합 없음 · 복용 요령 참고</span>'
        return (f'<a class="dg-card" href="drug-guide/{esc(dg["id"])}.html"><span class="dg-card-kind">{esc(kind)}</span><span class="block text-base font-extrabold text-ink-900">{esc(dg["short"])}</span>'
                f'<span class="mt-1 line-clamp-2 block text-sm text-ink-600">{esc(dg["h1"])}</span><span class="mt-3 flex flex-wrap gap-1.5">{chips}</span></a>')

    def group(gid: str, label: str, lead: str, es: list[dict]) -> str:
        return f'<section id="{gid}" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">{esc(label)} <span class="text-base font-bold text-ink-400">{len(es)}종</span></h2><p class="mt-1 text-ink-500">{esc(lead)}</p><div class="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{"".join(card(e) for e in es)}</div></section>'
    secs = group("otc", "약국에서 사는 일반의약품", "진통제·감기약·위장약처럼 처방 없이 사는 약입니다. 분류별로 식약처 허가 제품 목록까지 함께 보여 줍니다.", otc) + group("rx", "처방약(전문의약품)", "스타틴·갑상선약·항응고제·당뇨약처럼 처방전이 필요한 약입니다. 간격·검사·상담이 필요한 조합을 정리했고, 제품 목록은 식약처 허가정보(전문의약품)에서 분류별로 수집합니다.", rx)
    gap_rows = sorted(((x.get("hours") or 0, e["dg"]["short"], e["dg"]["id"], x["name"], x["id"], x["why"]) for e in items for x in e["good"] + e["caution"] if x.get("hours")), key=lambda t: (-t[0], t[1], t[3]))
    gap_html = (f'<section id="gaps" class="scroll-mt-24"><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">복용 간격 한눈에</h2><p class="mt-1 text-ink-500">약과 영양제를 같은 시간에 먹으면 흡수가 줄어 시간을 띄워야 하는 조합입니다. 약을 먼저 먹고 적힌 시간 뒤에 영양제를 드세요.</p>'
                f'<div class="timing-table-wrap mt-4"><table class="timing-table dg-table"><caption class="sr-only">약과 영양제 복용 간격</caption><thead><tr><th scope="col">약</th><th scope="col">영양 성분</th><th scope="col">간격</th><th scope="col">이유</th></tr></thead><tbody>'
                + "".join(f'<tr><th scope="row"><a href="drug-guide/{esc(did)}.html">{esc(short)}</a></th><td><a href="i/{esc(iid)}.html">{esc(name)}</a></td><td class="font-bold text-amber-700">{h}시간+</td><td class="timing-note">{esc(why)}</td></tr>' for h, short, did, name, iid, why in gap_rows)
                + '</tbody></table></div></section>') if gap_rows else ""
    body = f"""
<body data-page="guides" data-path="{DRUG_GUIDES_HUB}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="index.html">홈</a> › <span class="text-ink-800">약별 영양제 가이드</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="pill"></i> 약 기준으로 보는 영양제 궁합</p>
      <h1 class="page-title mt-3">약별 영양제 가이드: 약 먹을 때 영양제, 같이 먹어도 될까</h1>
      <p class="page-lead mt-4 max-w-3xl">영양제끼리의 궁합보다 중요한 것이 약과의 궁합입니다. 약 분류 {n}가지마다 함께 챙기면 좋은 성분, 시간을 띄우거나 피해야 할 성분, 복용 요령, 해당 식약처 허가 의약품을 한 장에 정리했습니다. 복용 중인 약 이름으로 <a class="font-bold text-brand-700 underline" href="search.html">검색</a>하면 그 약의 상세 페이지에서도 같은 조합을 볼 수 있습니다.</p>
      <div class="mt-5 flex flex-wrap gap-2"><a href="#otc" class="chip">일반의약품</a><a href="#rx" class="chip">처방약</a><a href="#gaps" class="chip">복용 간격표</a><a href="#faq" class="chip">자주 묻는 질문</a></div>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      {secs}
      {gap_html}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">읽는 법</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li>'함께 챙기면 좋아요'는 그 약을 오래 먹을 때 부족해지기 쉽거나 같은 목적으로 흔히 함께 챙기는 성분이고, '주의'는 흡수를 방해하거나 작용이 겹치는 성분입니다. 둘 다 의사·약사와 상의한 뒤 결정하세요.</li><li>'약 N건'은 이 사이트의 의약품 검색(식약처 e약은요·허가정보, 일반의약품 중심)에서 주성분·분류가 해당 규칙에 맞는 제품 수입니다. 처방약 분류는 목록 대신 대표 성분·제품명을 적었습니다.</li><li>약 복용자 상황별 긴 설명은 <a class="font-bold text-brand-700 underline" href="guide/with-medication.html">약과 영양제 가이드</a>와 각 페이지의 관련 가이드에서, 영양제끼리의 조합은 <a class="font-bold text-brand-700 underline" href="compatibility.html">궁합 체크</a>에서 보세요.</li></ul></section>
      {faq_html}
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def prepare_drug_guides(core: dict, guides_items: list[dict]) -> dict | None:
    """data/drug-guides.json + drug-pairings.json 을 읽어 검증하고 모델을 만든다 (성분 페이지의 '약과 함께' 칩이 먼저 쓰므로 main() 앞부분에서 호출)."""
    data = read_json(DATA_DIR / "drug-guides.json", None)
    rules_data = read_json(DATA_DIR / "drug-pairings.json", None)
    if not data or not rules_data:
        log.warning("data/drug-guides.json 또는 drug-pairings.json 이 없어 약별 영양제 가이드를 만들지 않습니다")
        return None
    rules = rules_data.get("rules", [])
    validate_drug_guides(data, rules, set(core["by_id"]), {g["slug"] for g in guides_items})
    drugs = load_drugs_detail()
    try:
        bp = load_brand_priority()
        weight, kw_weight = bp.weight, bp.keyword_weight
    except Exception:  # noqa: BLE001
        weight = kw_weight = None
    model = drug_guide_model(data, rules, core, drugs, guides_items, weight, kw_weight)
    model["data"] = data
    core["drug_guides"] = model
    log.info("약별 영양제 가이드 데이터 검증 통과: %d편 (의약품 상세 %s건 대조)", len(model["items"]), f"{len(drugs):,}")
    return model


def write_drug_guides(core: dict, cfg: dict, guides: dict) -> list[str]:
    """drug-guide/<id>.html · drug-guides.html · data/drug-guides-index.json 생성, 오래된 파일 정리. 생성한 id 목록을 돌려준다(사이트맵)."""
    model = core.get("drug_guides")
    if not model:
        return []
    DRUG_GUIDE_DIR.mkdir(exist_ok=True)
    types = guides.get("_meta", {}).get("types", {})
    updated = (model["data"].get("_meta") or {}).get("updatedAt") or core.get("updated_at") or now_iso()[:10]
    wanted = set()
    for e in model["items"]:
        p = DRUG_GUIDE_DIR / f"{e['dg']['id']}.html"
        p.write_text(render_drug_guide(e, core, cfg, types, updated), encoding="utf-8")
        wanted.add(p.name)
    for stale in DRUG_GUIDE_DIR.glob("*.html"):
        if stale.name not in wanted:
            stale.unlink()
            log.info("삭제된 약별 가이드 정리: %s", stale.name)
    (ROOT / DRUG_GUIDES_HUB).write_text(render_drug_guides_hub(model, model["data"], core, cfg), encoding="utf-8")
    write_json(DATA_DIR / "drug-guides-index.json", {
        "_meta": {"updatedAt": data_stamp(model["data"], default=core.get("updated_at") or now_iso()[:10]), "note": "drug-guides.json 의 요약 색인 — scripts/build_site.py 가 생성, 직접 수정하지 않음 (성분 페이지의 '약과 함께' 칩용)"},
        "items": [{"id": e["dg"]["id"], "short": e["dg"]["short"], "title": e["dg"]["title"], "rx": bool(e["dg"].get("rx")), "good": [g["id"] for g in e["good"]], "caution": [c["id"] for c in e["caution"]], "drugs": e["drugs"]["total"]} for e in model["items"]],
    }, compact=True, quiet=True)
    log.info("약별 영양제 가이드 생성: %s + drug-guide/ %d편", DRUG_GUIDES_HUB, len(wanted))
    return [e["dg"]["id"] for e in model["items"]]


# ---------- 영양제 용어 사전 (glossary.html · term/<slug>.html) + 본문 용어 자동 링크 ----------
TERM_DIR = ROOT / "term"
GLOSSARY_HUB = "glossary.html"
TERM_LINK_MAX = 12   # 페이지당 자동 링크 최대 수 (assets/js/terms.js 의 MAX 와 같아야 함)
_CHOSEONG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_CHOSEONG_BASE = {"ㄲ": "ㄱ", "ㄸ": "ㄷ", "ㅃ": "ㅂ", "ㅆ": "ㅅ", "ㅉ": "ㅈ"}
_INITIAL_ORDER = ["ㄱ", "ㄴ", "ㄷ", "ㄹ", "ㅁ", "ㅂ", "ㅅ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ", "A"]


def term_initial(term: str) -> str:
    """용어 첫 글자의 초성(ㄱ~ㅎ, 된소리는 예사소리로) — 한글이 아니면 'A'(영문·숫자·기호 묶음)."""
    ch = (term or "").strip()[:1]
    if "가" <= ch <= "힣":
        c = _CHOSEONG[(ord(ch) - 0xAC00) // 588]
        return _CHOSEONG_BASE.get(c, c)
    return "A"


def _alias_pattern(alias: str) -> str:
    """영문·숫자로 시작하는 별칭은 앞이, 끝나는 별칭은 뒤가 영문·숫자가 아닐 때만, 한글로 시작하는 별칭은 앞이 한글이 아닐 때만 맞춘다('헴철'이 '비헴철' 안에서 걸리지 않게; 뒤의 조사는 허용)."""
    head = r"(?<![A-Za-z0-9])" if re.match(r"[A-Za-z0-9]", alias) else r"(?<![가-힣])"
    tail = r"(?![A-Za-z0-9])" if re.search(r"[A-Za-z0-9]$", alias) else ""
    return head + re.escape(alias) + tail


class TermLinker:
    """HTML 이스케이프된 본문 조각에서 용어 별칭의 첫 등장만 term/<slug>.html 링크로 바꾼다 (assets/js/terms.js 와 같은 규칙).
    별칭은 긴 것부터 맞추고 대소문자를 무시한다. state = {"used": set(), "exclude": set()} 를 페이지마다 하나 만들어 넘기면
    페이지당 용어마다 한 번, 최대 TERM_LINK_MAX 개만 링크하며 exclude 의 용어(자기 페이지)는 건너뛴다. 태그가 든 문자열에는 쓰지 않는다."""

    def __init__(self, items: list[dict]):
        self.by_alias: dict[str, tuple[str, str]] = {}
        aliases: list[str] = []
        for it in items:
            for a in it.get("aliases") or []:
                a_esc = esc(a)
                key = a_esc.lower()
                if key in self.by_alias:
                    continue
                self.by_alias[key] = (it["slug"], it.get("short") or "")
                aliases.append(a_esc)
        aliases.sort(key=len, reverse=True)
        self.re = re.compile("|".join(_alias_pattern(a) for a in aliases), re.IGNORECASE) if aliases else None

    def link(self, text_esc: str, root: str, state: dict) -> str:
        if not self.re or not text_esc:
            return text_esc
        used = state.setdefault("used", set())
        exclude = state.get("exclude") or set()
        if len(used) >= TERM_LINK_MAX:
            return text_esc

        def rep(m: re.Match) -> str:
            hit = self.by_alias.get(m.group(0).lower())
            if not hit:
                return m.group(0)
            slug, short = hit
            if slug in exclude or slug in used or len(used) >= TERM_LINK_MAX:
                return m.group(0)
            used.add(slug)
            return f'<a class="term-link" href="{root}term/{slug}.html" title="{esc(short)}">{m.group(0)}</a>'
        return self.re.sub(rep, text_esc)


def term_html(core: dict, text, state: dict, root: str = "../") -> str:
    """esc() + 용어 자동 링크. 제목·칩·버튼이 아닌 본문 조각에만 쓴다 (용어 사전이 없으면 esc 와 같다)."""
    s = esc(text)
    linker = core.get("term_linker")
    return linker.link(s, root, state) if linker else s


def validate_glossary(data: dict, valid_ids: set[str], guide_slugs: set[str]) -> None:
    """data/glossary.json: slug 형식·중복, 필수 항목, 분류, 별칭(2자 이상·용어 간 중복 금지), related 용어·성분 id·가이드 slug 를 확인한다."""
    cats = (data.get("_meta") or {}).get("categories") or {}
    items = data.get("items") or []
    slugs = [it.get("slug") for it in items]
    if len(set(slugs)) != len(slugs):
        raise SystemExit("glossary.json: 중복 slug " + str(sorted({s for s in slugs if slugs.count(s) > 1})))
    alias_owner: dict[str, str] = {}
    for it in items:
        slug = it.get("slug") or ""
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            raise SystemExit(f"glossary.json: slug 형식 오류 {slug!r}")
        for k in ("term", "short", "body", "category"):
            if not str(it.get(k) or "").strip():
                raise SystemExit(f"glossary.json[{slug}]: {k} 가 비어 있음")
        if it["category"] not in cats:
            raise SystemExit(f"glossary.json[{slug}]: 없는 분류 {it['category']!r}")
        aliases = it.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            raise SystemExit(f"glossary.json[{slug}]: aliases(자동 링크 표기)가 필요")
        for a in aliases:
            a = str(a)
            if len(a.strip()) < 2:
                raise SystemExit(f"glossary.json[{slug}]: 별칭이 너무 짧음 {a!r}")
            key = a.strip().lower()
            if alias_owner.get(key, slug) != slug:
                raise SystemExit(f"glossary.json: 별칭 {a!r} 이 {alias_owner[key]} 와 {slug} 에 중복")
            alias_owner[key] = slug
        bad = [s for s in it.get("related", []) if s not in slugs]
        if bad:
            raise SystemExit(f"glossary.json[{slug}]: 없는 관련 용어 {bad}")
        bad = [i for i in it.get("ingredients", []) if i not in valid_ids]
        if bad:
            raise SystemExit(f"glossary.json[{slug}]: 없는 성분 id {bad}")
        bad = [g for g in it.get("guides", []) if g not in guide_slugs]
        if bad:
            raise SystemExit(f"glossary.json[{slug}]: 없는 가이드 slug {bad}")


def glossary_model(data: dict, core: dict, guides: list[dict]) -> dict:
    by_id = core["by_id"]
    g_by = {g["slug"]: g for g in guides}
    cats = data["_meta"]["categories"]
    by_slug_raw = {it["slug"]: it for it in data["items"]}
    order = list(cats.keys())
    entries = []
    for it in data["items"]:
        entries.append({"t": it, "initial": term_initial(it["term"]),
                        "related": [by_slug_raw[s] for s in it.get("related", []) if s in by_slug_raw],
                        "ingredients": [by_id[i] for i in it.get("ingredients", []) if i in by_id],
                        "guides": [g_by[s] for s in it.get("guides", []) if s in g_by]})
    entries.sort(key=lambda e: (order.index(e["t"]["category"]) if e["t"]["category"] in order else 99, e["t"]["term"]))
    return {"items": entries, "categories": cats, "by_slug": {e["t"]["slug"]: e for e in entries}}


def _term_search_key(t: dict) -> str:
    return re.sub(r"[\s·\-()（）.,/]+", "", " ".join([t["term"], t.get("en") or "", " ".join(t.get("aliases") or []), t.get("short") or ""])).lower()


def render_term(entry: dict, model: dict, core: dict, cfg: dict, guides_types: dict, updated: str) -> str:
    t = entry["t"]
    cats = model["categories"]
    cat = cats.get(t["category"], {})
    path = f"term/{t['slug']}.html"
    en = (t.get("en") or "").strip()
    title = f"{t['term']} 뜻 · 영양제 용어 사전 | {cfg['name']}"
    paras = [p.strip() for p in str(t["body"]).split("\n\n") if p.strip()]
    first = re.split(r"(?<=[.다])\s", paras[0], maxsplit=1)[0] if paras else ""
    desc = (t["short"] + " " + first)[:300]
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"},
            {"@type": "ListItem", "position": 2, "name": "영양제 용어 사전", "item": page_url(cfg, GLOSSARY_HUB)},
            {"@type": "ListItem", "position": 3, "name": t["term"], "item": page_url(cfg, path)}]},
        {"@type": "DefinedTerm", "name": t["term"], "alternateName": [x for x in [en] + list(t.get("aliases") or []) if x and x != t["term"]], "description": t["short"], "url": page_url(cfg, path),
         "inDefinedTermSet": {"@type": "DefinedTermSet", "name": "영양제 용어 사전", "url": page_url(cfg, GLOSSARY_HUB)}},
    ]}
    head = head_html(cfg, title=title, desc=desc, path=path, root="../", keywords=", ".join([f"{t['term']} 뜻", f"{t['term']}이란"] + ([en] if en else []) + ["영양제 용어"]), og_type="article", ld=ld)
    st = {"used": set(), "exclude": {t["slug"]}}   # 자기 자신은 링크하지 않는다
    body_html = "".join(f'<p class="text-[15px] leading-relaxed text-ink-800">{term_html(core, p, st)}</p>' for p in paras)
    label_html = f'<section id="label" class="scroll-mt-24 rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="tags" class="h-5 w-5 text-brand-600"></i>라벨·검사지에서 보는 법</h2><p class="mt-2 text-[15px] leading-relaxed text-ink-700">{term_html(core, t["label"], st)}</p></section>' if t.get("label") else ""
    rel_terms = entry["related"]
    rel_html = (f'<section id="related" class="scroll-mt-24"><h2 class="text-lg font-extrabold text-ink-900">관련 용어</h2><div class="mt-3 flex flex-wrap gap-2">' + "".join(f'<a class="chart-chip" href="../term/{esc(r["slug"])}.html" title="{esc(r.get("short") or "")}"><i data-lucide="book-open" class="h-3.5 w-3.5"></i>{esc(r["term"])}</a>' for r in rel_terms) + '</div></section>') if rel_terms else ""
    ings = entry["ingredients"]
    cats_i = core["categories"]
    ing_html = (f'<section id="ingredients" class="scroll-mt-24"><h2 class="text-lg font-extrabold text-ink-900">관련 성분</h2><div class="mt-3 grid gap-3 md:grid-cols-2">' + "".join(
        f'<a class="cmp-mini" href="../i/{esc(i["id"])}.html"><span class="finder-thumb">{photo_img(i["category"])}</span><span class="min-w-0"><span class="badge {cat_class(cats_i.get(i["category"], {}).get("color", ""))}">{esc(cats_i.get(i["category"], {}).get("label", ""))}</span><span class="mt-1 block text-base font-extrabold text-ink-900">{esc(i["name"])}</span><span class="mt-0.5 line-clamp-2 block text-sm text-ink-600">{esc(i.get("mfdsFunction") or i.get("summary") or "")}</span></span></a>'
        for i in ings) + '</div></section>') if ings else ""
    gds = entry["guides"]
    guides_html = (f'<section id="guides" class="scroll-mt-24"><h2 class="text-lg font-extrabold text-ink-900">관련 가이드</h2><div class="mt-3 grid gap-4 md:grid-cols-2 lg:grid-cols-3">{"".join(guide_card(g, guides_types, "../") for g in gds)}</div></section>') if gds else ""
    body = f"""
<body data-page="ingredients" data-path="{path}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-5xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="../index.html">홈</a> › <a class="hover:text-brand-700" href="../{GLOSSARY_HUB}">영양제 용어 사전</a> › <a class="hover:text-brand-700" href="../{GLOSSARY_HUB}#{esc(t["category"])}">{esc(cat.get("label", ""))}</a> › <span class="text-ink-800">{esc(t["term"])}</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="book-open"></i> 영양제 용어 사전 · {esc(cat.get("label", ""))}</p>
      <h1 class="page-title mt-3">{esc(t["term"])}</h1>
      {('<p class="mt-1.5 text-sm font-medium text-ink-400">' + esc(en) + '</p>') if en else ""}
      <p class="page-lead mt-4 max-w-3xl">{esc(t["short"])}</p>
      <p class="mt-4 text-xs text-ink-400">제도·단위·사실 관계를 설명하는 일반 정보이며 의학적 조언이 아닙니다. 기능성 표현은 식약처 인정 범위를 따릅니다 · 최종 수정 {esc(updated)}</p>
    </div></section>
    <div class="mx-auto max-w-5xl space-y-8 px-4 py-10 sm:px-6">
      <section id="meaning" class="scroll-mt-24 rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="text-lg font-extrabold text-ink-900">뜻</h2><div class="mt-3 space-y-3">{body_html}</div></section>
      {label_html}
      {rel_html}
      {ing_html}
      {guides_html}
      <section class="rounded-2xl border border-ink-100 bg-cream-200 p-5"><h2 class="text-base font-extrabold text-ink-900">함께 보면 좋은 페이지</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li><a class="font-bold text-brand-700 underline" href="../{GLOSSARY_HUB}">영양제 용어 사전 전체</a> — 분류·초성으로 찾기</li><li><a class="font-bold text-brand-700 underline" href="../ingredients.html">성분 사전</a> · <a class="font-bold text-brand-700 underline" href="../compatibility.html">영양제 궁합 체크</a></li><li><a class="font-bold text-brand-700 underline" href="../guide/daily-limit.html">영양제 하루 권장량과 상한섭취량</a> · <a class="font-bold text-brand-700 underline" href="../guide/with-medication.html">약과 영양제 같이 먹어도 될까</a></li></ul></section>
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def render_glossary_hub(model: dict, cfg: dict) -> str:
    items = model["items"]
    cats = model["categories"]
    n = len(items)
    title = f"영양제 용어 사전 — rTG·생체이용률·상한섭취량·보장균수 등 용어 {n}개 뜻 | {cfg['name']}"
    desc = f"영양제 라벨과 가이드에 나오는 용어 {n}개를 제형·흡수, 성분 형태, 섭취 기준·라벨, 제도·인증, 작용·상호작용, 검사·수치로 나눠 한 줄 뜻과 자세한 설명, 라벨에서 보는 법, 관련 성분·가이드로 정리했습니다."
    faq_items = [
        ("영양제 라벨에서 가장 먼저 봐야 할 용어는 무엇인가요?", "기능성 내용(식약처 인정 문구), 1일 섭취량(기능성 원료 기준 범위), 지표성분 함량, 상한섭취량과의 비교입니다. 이 네 가지만 읽어도 광고 문구와 실제 함량을 구분할 수 있습니다."),
        ("흡수율이 높다는 제품이 꼭 좋은가요?", "흡수율(생체이용률)은 형태·제형·식사에 따라 달라지지만 '○배 흡수' 같은 광고 수치는 조건이 제각각입니다. 식약처 1일 섭취량을 채우고 먹는 시간을 지키는 것이 먼저이고, 형태(헴철·구연산칼슘·rTG 등)는 그다음 기준입니다."),
        ("본문의 점선 밑줄 링크는 무엇인가요?", "가이드·성분·비교·약별 페이지의 본문에 처음 나오는 용어를 이 사전으로 자동 연결한 것입니다. 마우스를 올리면 한 줄 뜻이 보이고, 누르면 자세한 설명과 관련 성분·가이드로 이동합니다."),
    ]
    faq_html, faq_ld = faq_block(faq_items)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "홈", "item": f"{cfg['url']}/"}, {"@type": "ListItem", "position": 2, "name": "영양제 용어 사전", "item": page_url(cfg, GLOSSARY_HUB)}]},
        {"@type": "DefinedTermSet", "name": "영양제 용어 사전", "url": page_url(cfg, GLOSSARY_HUB), "description": desc,
         "hasDefinedTerm": [{"@type": "DefinedTerm", "name": e["t"]["term"], "description": e["t"]["short"], "url": page_url(cfg, f"term/{e['t']['slug']}.html")} for e in items]},
        faq_ld,
    ]}
    head = head_html(cfg, title=title, desc=desc, path=GLOSSARY_HUB, root="./", keywords="영양제 용어, 영양제 용어 사전, 생체이용률 뜻, rTG 뜻, 상한섭취량, 보장균수, 지표성분, 개별인정형 고시형", og_type="website",
                     extra_scripts='<script src="assets/js/pages/glossary.js" defer></script>', ld=ld)
    present = {e["initial"] for e in items}
    chips = "".join(f'<button type="button" class="chip term-initial" data-initial-chip="{esc(i)}" aria-pressed="false">{"A-Z·숫자" if i == "A" else esc(i)}</button>' for i in _INITIAL_ORDER if i in present)
    secs = ""
    for ck, c in cats.items():
        es = [e for e in items if e["t"]["category"] == ck]
        if not es:
            continue
        cards = "".join(
            f'<a class="term-card" data-term-card data-initial="{esc(e["initial"])}" data-search="{esc(_term_search_key(e["t"]))}" href="term/{esc(e["t"]["slug"])}.html"><span class="term-card-name">{esc(e["t"]["term"])}</span>'
            + (f'<span class="term-card-en">{esc(e["t"]["en"])}</span>' if e["t"].get("en") else "") + f'<span class="term-card-short">{esc(e["t"]["short"])}</span></a>'
            for e in es)
        secs += f'<section id="{esc(ck)}" class="scroll-mt-24" data-term-section><h2 class="text-2xl font-extrabold tracking-tight text-ink-900">{esc(c.get("label", ck))} <span class="text-base font-bold text-ink-400">{len(es)}</span></h2><p class="mt-1 text-ink-500">{esc(c.get("desc", ""))}</p><div class="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{cards}</div></section>'
    cat_chips = "".join(f'<a href="#{esc(k)}" class="chip">{esc(c.get("label", k))}</a>' for k, c in cats.items() if any(e["t"]["category"] == k for e in items))
    body = f"""
<body data-page="ingredients" data-path="{GLOSSARY_HUB}" class="min-h-screen antialiased">
  {SKIP_LINK}
  <main id="main">
    <section class="page-hero"><div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">
      <nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="index.html">홈</a> › <span class="text-ink-800">영양제 용어 사전</span></nav>
      <p class="eyebrow-kicker mt-4"><i data-lucide="book-open"></i> 라벨·가이드의 낯선 말 {n}개</p>
      <h1 class="page-title mt-3">영양제 용어 사전: 라벨과 가이드에 나오는 말 뜻 풀이</h1>
      <p class="page-lead mt-4 max-w-3xl">rTG·생체이용률·상한섭취량·보장균수·지표성분·개별인정형처럼 영양제를 고를 때 마주치는 용어를 분류별로 모았습니다. 한 줄 뜻을 보고, 자세한 설명과 관련 성분·가이드로 이어집니다. 가이드·성분 페이지 본문의 점선 밑줄 링크가 이 사전으로 연결됩니다.</p>
      <div class="mt-6 max-w-xl"><label for="term-filter" class="sr-only">용어 검색</label><input id="term-filter" type="search" placeholder="용어·영문·설명으로 찾기 (예: rTG, 상한, 보장균수)" autocomplete="off" class="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-[15px] shadow-card focus:border-brand-600 focus:outline-none"></div>
      <div class="mt-4 flex flex-wrap gap-2">{chips}</div>
      <div class="mt-4 flex flex-wrap gap-2">{cat_chips}</div>
      <p class="mt-4 text-xs text-ink-400">표시 <span id="term-count">{n}</span> / {n} · 제도·단위·사실 관계를 설명하는 일반 정보이며 의학적 조언이 아닙니다</p>
    </div></section>
    <div class="mx-auto max-w-7xl space-y-14 px-4 py-12 sm:px-6">
      <p id="term-empty" class="hidden rounded-2xl border border-dashed border-ink-200 bg-white p-6 text-sm text-ink-600">검색어에 맞는 용어가 없습니다. 성분 이름은 <a class="font-bold text-brand-700 underline" href="ingredients.html">성분 사전</a>에서, 제품·의약품은 <a class="font-bold text-brand-700 underline" href="search.html">통합 검색</a>에서 찾아보세요.</p>
      {secs}
      <section class="rounded-3xl bg-cream-200 p-6 sm:p-8"><h2 class="text-lg font-extrabold text-ink-900">읽는 법</h2><ul class="list-dot mt-3 text-sm text-ink-700"><li>성분 이름(비타민D·오메가3 등)은 <a class="font-bold text-brand-700 underline" href="ingredients.html">성분 사전</a>이 맡고, 여기서는 제형·형태·기준·제도·상호작용·검사처럼 성분을 둘러싼 말을 다룹니다.</li><li>기능성 표현은 식약처 인정 문구 범위에서만 쓰며, 검사 수치의 기준값은 널리 쓰이는 일반 기준이라 검사 기관·개인에 따라 다를 수 있습니다.</li><li>약을 복용 중이면 <a class="font-bold text-brand-700 underline" href="drug-guides.html">약별 영양제 가이드</a>와 <a class="font-bold text-brand-700 underline" href="guide/with-medication.html">약과 영양제 가이드</a>를 함께 보세요.</li></ul></section>
      {faq_html}
    </div>
  </main>
  <div id="site-footer"></div>
</body>
</html>
"""
    return head + body


def prepare_glossary(core: dict, guides_items: list[dict]) -> dict | None:
    """data/glossary.json 을 읽어 검증·모델을 만들고 본문 자동 링크기(core['term_linker'])를 둔다 — 가이드·성분·비교·약별 페이지보다 먼저 호출."""
    data = read_json(DATA_DIR / "glossary.json", None)
    if not data:
        log.warning("data/glossary.json 이 없어 용어 사전과 본문 자동 링크를 만들지 않습니다")
        return None
    validate_glossary(data, set(core["by_id"]), {g["slug"] for g in guides_items})
    model = glossary_model(data, core, guides_items)
    model["data"] = data
    core["glossary"] = model
    core["term_linker"] = TermLinker(data["items"])
    log.info("용어 사전 데이터 검증 통과: %d개 (별칭 %d개)", len(model["items"]), len(core["term_linker"].by_alias))
    return model


def write_glossary(core: dict, cfg: dict, guides: dict) -> list[str]:
    """term/<slug>.html · glossary.html · data/glossary-index.json 생성, 오래된 파일 정리. 생성한 slug 목록을 돌려준다(사이트맵)."""
    model = core.get("glossary")
    if not model:
        return []
    TERM_DIR.mkdir(exist_ok=True)
    types = guides.get("_meta", {}).get("types", {})
    updated = (model["data"].get("_meta") or {}).get("updatedAt") or core.get("updated_at") or now_iso()[:10]
    wanted = set()
    for e in model["items"]:
        p = TERM_DIR / f"{e['t']['slug']}.html"
        p.write_text(render_term(e, model, core, cfg, types, updated), encoding="utf-8")
        wanted.add(p.name)
    for stale in TERM_DIR.glob("*.html"):
        if stale.name not in wanted:
            stale.unlink()
            log.info("삭제된 용어 페이지 정리: %s", stale.name)
    (ROOT / GLOSSARY_HUB).write_text(render_glossary_hub(model, cfg), encoding="utf-8")
    write_json(DATA_DIR / "glossary-index.json", {
        "_meta": {"updatedAt": data_stamp(model["data"], default=core.get("updated_at") or now_iso()[:10]), "note": "glossary.json 의 요약 색인 — scripts/build_site.py 가 생성, 직접 수정하지 않음 (검색·성분 페이지 본문 자동 링크용)"},
        "items": [{"slug": e["t"]["slug"], "term": e["t"]["term"], "en": e["t"].get("en") or "", "aliases": e["t"].get("aliases") or [], "short": e["t"]["short"], "category": e["t"]["category"]} for e in model["items"]],
    }, compact=True, quiet=True)
    log.info("용어 사전 생성: %s + term/ %d개", GLOSSARY_HUB, len(wanted))
    return [e["t"]["slug"] for e in model["items"]]


def build_charts(core: dict, cfg: dict) -> None:
    """영양제 궁합표·복용 시간표 정적 페이지 생성 (루트, sitemap 은 STATIC_PAGES 로)."""
    (ROOT / CHART_PATH).write_text(render_compat_chart(core, cfg), encoding="utf-8")
    (ROOT / TIMING_PATH).write_text(render_timing_chart(core, cfg), encoding="utf-8")
    log.info("영양제 궁합표·복용 시간표 생성 (%s · %s)", CHART_PATH, TIMING_PATH)


def build_sitemap(ingredients: list[dict], cfg: dict, data_date: str, guides: dict | None = None, functions: list[str] | None = None, compares: list[str] | None = None, drug_guides: list[str] | None = None, terms: list[str] | None = None) -> None:
    today = now_iso()[:10]
    dynamic = ("index.html", "news.html", "products.html")
    # 주소는 Cloudflare Pages 가 실제로 서비스하는 확장자 없는 형태(홈은 /) — .html 주소는 리다이렉트되어 색인에 불리하다
    urls = [(page_url(cfg, p), "daily" if p in dynamic else "monthly", "1.0" if p == "index.html" else "0.8", today if p in dynamic else data_date) for p in STATIC_PAGES]
    urls += [(page_url(cfg, f"i/{it['id']}.html"), "monthly", "0.7", data_date) for it in ingredients]
    gdate = (guides or {}).get("_meta", {}).get("updatedAt") or data_date
    urls += [(page_url(cfg, f"guide/{g['slug']}.html"), "monthly", "0.8", gdate) for g in (guides or {}).get("items", [])]
    urls += [(page_url(cfg, f"function/{fid}.html"), "monthly", "0.7", data_date) for fid in (functions or [])]
    urls += [(page_url(cfg, f"compare/{s}.html"), "monthly", "0.7", data_date) for s in (compares or [])]
    urls += [(page_url(cfg, f"drug-guide/{i}.html"), "monthly", "0.7", data_date) for i in (drug_guides or [])]
    urls += [(page_url(cfg, f"term/{s}.html"), "monthly", "0.5", data_date) for s in (terms or [])]
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
    prepare_compares(core, core["guides"])    # 성분 비교 모델 (성분 페이지의 비교 글 칩, 기능성 모델 뒤)
    prepare_drug_guides(core, core["guides"])  # 약별 영양제 가이드 모델 (성분 페이지의 '약과 함께' 칩)
    prepare_glossary(core, core["guides"])     # 용어 사전 모델 + 본문 자동 링크기 (가이드·성분·비교·약별·기능성 페이지가 쓴다)
    prepare_form_compares(core, core["guides"])  # 제형·형태 비교 모델 — 성분 비교 모델에 forms 로 더함 (용어 사전 뒤, 성분 페이지 앞)

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
    tips = read_json(DATA_DIR / "tips.json", None)
    if tips:
        validate_tips(tips)   # 오늘 홈의 일반 팁 — 금칙어·길이 검사
    else:
        log.warning("data/tips.json 이 없어 오늘의 한 줄 일반 팁 검증을 건너뜁니다")
    function_ids = write_functions(core, cfg, guides)
    compare_slugs = write_compares(core, cfg, guides)
    drug_guide_ids = write_drug_guides(core, cfg, guides)
    term_slugs = write_glossary(core, cfg, guides)
    build_sitemap(ingredients["items"], cfg, data_date, guides, function_ids, compare_slugs, drug_guide_ids, term_slugs)
    inject_verification(cfg)
    inject_pwa_tags()
    build_product_names()
    validate_drug_pairings(set(core["by_id"].keys()))
    ensure_drug_index()
    check_icons()
    stamp_and_build_sw()
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
