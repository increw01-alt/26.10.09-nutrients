"""사이트·데이터 점검 (읽기 전용). 빌드 뒤에 실행해 깨진 곳과 빈틈을 한 번에 본다.

  python scripts/check_site.py            # 전체 점검 — 실패(exit 1)는 즉시 고칠 것, 경고는 검토 대상
  python scripts/check_site.py --quiet    # 실패·경고 요약만

검사 항목
  [실패] 내부 링크(href·src)가 가리키는 파일 존재 · sitemap.xml ↔ 생성 HTML 일치(noindex 제외) · JSON-LD 파싱 · 제목 중복
         · 홈 탭(home.js GUIDE_GROUPS)이 모든 가이드를 포함 · data/guides-index.json 이 guides.json 과 같은 수
         · manifest.webmanifest 존재·파싱·아이콘 파일 존재 · 색인 페이지마다 rel="manifest" 링크(build_site.py 가 주입)
  [경고] <title> 95자 초과 · meta description 없음 또는 50자 미만(noindex 제외) · 가이드 핵심 성분에 한 번도 연결되지 않은 성분
         · 궁합 3쌍 이하 성분 · 다른 가이드의 related 에 한 번도 등장하지 않는 가이드 · 숫자로 끝나는 성분명의 조사(Q10는·B6는·D3는·B1는)
         · '미인정·기능성 원료 아님·인정한 원료 없음' 단정 문장 중 식약처 인정현황(data/materials.json)에 이름이 보이는 것
점검 기준은 docs/PROJECT-STATUS.md '다음 할 일' 6번 참고. 새 점검을 추가하면 이 docstring 도 함께 고친다."""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, ROOT, read_json  # noqa: E402

QUIET = "--quiet" in sys.argv
FAIL: list[str] = []
WARN: list[str] = []


def fail(msg: str) -> None:
    FAIL.append(msg)


def warn(msg: str) -> None:
    WARN.append(msg)


def html_files() -> list[Path]:
    return sorted([*ROOT.glob("*.html"), *(ROOT / "i").glob("*.html"), *(ROOT / "guide").glob("*.html"), *(ROOT / "function").glob("*.html"), *(ROOT / "compare").glob("*.html")])


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


# ---------------------------------------------------------------- HTML
def check_html() -> None:
    files = html_files()
    titles: dict[str, list[str]] = {}
    noindex: set[str] = set()
    for h in files:
        s = h.read_text(encoding="utf-8")
        name = rel(h)
        if "noindex" in s:
            noindex.add(name[:-5])
        for m in re.finditer(r'(?:href|src)="([^"#?]+)(?:[#?][^"]*)?"', s):
            u = m.group(1)
            if re.match(r"^(https?:|mailto:|tel:|data:|//)", u) or u.startswith("/"):
                continue
            t = (h.parent / u).resolve()
            if not t.exists():
                fail(f"깨진 내부 링크: {name} → {u}")
        t = re.search(r"<title>(.*?)</title>", s, re.S)
        title = t.group(1).strip() if t else ""
        titles.setdefault(title, []).append(name)
        if len(title) > 95:
            warn(f"제목 95자 초과({len(title)}): {name}")
        d = re.search(r'<meta name="description" content="([^"]*)"', s)
        if name[:-5] not in noindex and name != "404.html" and not name.startswith("naver"):
            if not d:
                warn(f"meta description 없음: {name}")
            elif len(d.group(1)) < 50:
                warn(f"meta description 50자 미만({len(d.group(1))}): {name}")
        for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', s, re.S):
            try:
                json.loads(m.group(1))
            except Exception as e:  # noqa: BLE001
                fail(f"JSON-LD 파싱 오류: {name} — {str(e)[:60]}")
    for title, names in titles.items():
        if len(names) > 1 and title:
            fail(f"중복 제목: {title[:40]}… ← {', '.join(names)}")
    # sitemap ↔ 파일
    sm_path = ROOT / "sitemap.xml"
    if sm_path.exists():
        sm = set(re.findall(r"<loc>https://[^/]+/([^<]*)</loc>", sm_path.read_text(encoding="utf-8")))
        pages = {(rel(h)[:-5] if rel(h) != "index.html" else "") for h in files}
        for u in sorted(sm - pages):
            fail(f"sitemap 에 있으나 파일 없음: {u}")
        for p in sorted(pages - sm):
            if p in noindex or p in ("404",) or p.startswith("naver"):
                continue
            fail(f"파일은 있으나 sitemap 에 없음: {p}")
    else:
        fail("sitemap.xml 이 없음 (build_site.py 를 먼저 실행)")
    # 웹 앱 매니페스트 ↔ 아이콘 파일, 색인 페이지의 manifest 링크(build_site.py 가 주입)
    mf = ROOT / "manifest.webmanifest"
    if not mf.exists():
        fail("manifest.webmanifest 이 없음")
    else:
        try:
            for ic in json.loads(mf.read_text(encoding="utf-8")).get("icons", []):
                if not (ROOT / str(ic.get("src", "")).lstrip("/")).exists():
                    fail(f"매니페스트 아이콘 파일 없음: {ic.get('src')} — python scripts/build_app_icons.py")
        except Exception as e:  # noqa: BLE001
            fail(f"manifest.webmanifest 파싱 오류: {str(e)[:60]}")
    for h in files:
        name = rel(h)
        if name[:-5] in noindex or name == "404.html" or name.startswith("naver"):
            continue
        if 'rel="manifest"' not in h.read_text(encoding="utf-8"):
            fail(f"PWA 매니페스트 링크 없음: {name} — build_site.py 재실행")
    if not QUIET:
        print(f"HTML {len(files)}개 · noindex {len(noindex)}개 검사")


# ---------------------------------------------------------------- 데이터
def check_data() -> None:
    ing = read_json(DATA_DIR / "ingredients.json", {"items": []})["items"]
    guides = read_json(DATA_DIR / "guides.json", {"items": []})["items"]
    inter = read_json(DATA_DIR / "interactions.json", {"pairs": []})["pairs"]
    ids = {i["id"] for i in ing}
    ref = Counter(x["id"] for g in guides for x in g.get("ingredients", []))
    pairs = Counter(i for p in inter for i in p["pair"])
    for i in ing:
        if ref[i["id"]] == 0:
            warn(f"가이드 핵심 성분에 연결되지 않은 성분: {i['id']}")
        if pairs[i["id"]] <= 3:
            warn(f"궁합 3쌍 이하 성분: {i['id']} ({pairs[i['id']]}쌍)")
    inbound = Counter(r for g in guides for r in g.get("related", []))
    for g in guides:
        if inbound[g["id"]] == 0:
            warn(f"다른 가이드의 related 에 없는 가이드: {g['id']}")
    # 홈 탭 포함 여부
    home_js = (ROOT / "assets/js/pages/home.js").read_text(encoding="utf-8")
    m = re.search(r"var GUIDE_GROUPS = \{.*?\n  \};", home_js, re.S)
    if m:
        tab_slugs = set(re.findall(r'slug: "([^"]+)"', m.group(0)))
        for g in guides:
            if g["slug"] not in tab_slugs:
                fail(f"홈 탭(home.js GUIDE_GROUPS)에 없는 가이드: {g['slug']} — scripts/home_tabs.py 의 SHORT·ORDER 에 추가 후 실행")
    else:
        fail("home.js 에서 GUIDE_GROUPS 블록을 찾지 못함")
    # 요약 색인
    idx = read_json(DATA_DIR / "guides-index.json", {"items": []})
    if len(idx.get("items", [])) != len(guides):
        fail(f"data/guides-index.json 항목 수({len(idx.get('items', []))})가 guides.json({len(guides)})과 다름 — build_site.py 재실행")
    # 조사 표기 (숫자로 끝나는 이름)
    blob = json.dumps({"i": ing, "g": guides, "p": inter}, ensure_ascii=False)
    for mm in re.finditer(r"(Q10|B6|D3|B1)(는|가|와|를)(?![가-힣])", blob):
        warn(f"조사 표기 의심: '{mm.group(0)}' — {mm.group(1)}은/이/과/을 로 고치기 (숫자로 끝나는 이름)")
    # '미인정' 단정 문장 ↔ 인정현황
    mats = read_json(DATA_DIR / "materials.json", {"items": []}).get("items", [])
    mat_names = "\n".join(it.get("name", "") for it in mats).lower()   # 기능성 문구가 아니라 원료 이름에서만 찾는다 (인슐린·추출물 같은 일반어 오탐 방지)
    own = set()   # 우리 사전에 있는(=인정 원료인) 이름·별칭은 제외 — 문장이 '일반식품 형태는 미인정'을 말하는 경우가 대부분
    for i in ing:
        for nm in [i["name"], *i.get("aliases", [])]:
            own.add(re.sub(r"\s*\(.*?\)", "", nm).replace(" ", "").lower())
    generic = {"추출물", "추출분말", "복합물", "가수분해물", "발효물", "분말", "농축액", "함유", "유지", "오일"}
    pat = re.compile(r"[^.\"]*?(미인정|기능성 원료가 아|기능성 원료 아님|인정한 (?:[가-힣 ]+)?원료는 없|인정받지 않|인정되지 않|국내 건강기능식품 원료가 아|기능성을 인정한 것은 없)[^.\"]*")
    n_claims = 0
    for src, items in (("guides", guides), ("ingredients", ing), ("interactions", inter)):
        for it in items:
            txt = json.dumps(it, ensure_ascii=False)
            for mm in pat.finditer(txt):
                n_claims += 1
                sent = mm.group(0)
                hits = set()
                for t in re.findall(r"[가-힣]{3,}|[A-Za-z][A-Za-z0-9\-]{2,}", sent):
                    t = re.sub(r"(은|는|이|가|을|를|과|와|도|로|의|에)$", "", t)   # 조사 제거
                    tl = t.lower()
                    if len(t) < 3 or t in generic or tl in own or any(o.startswith(tl) or tl.startswith(o) for o in own if len(o) >= 3):
                        continue
                    if tl in mat_names:
                        hits.add(t)
                if hits:
                    key = it.get("slug") or it.get("id") or "/".join(it.get("pair", []))
                    warn(f"'미인정' 단정 문장에 인정현황 원료 이름이 보임({src}:{key}): {sorted(hits)} ← {sent.strip()[:90]}")
    if not QUIET:
        print(f"성분 {len(ing)} · 궁합 {len(inter)} · 가이드 {len(guides)} · 단정 문장 {n_claims}건 검사")


def main() -> int:
    check_html()
    check_data()
    for m in FAIL:
        print("[실패]", m)
    for m in WARN:
        print("[경고]", m)
    print(f"결과: 실패 {len(FAIL)} · 경고 {len(WARN)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
