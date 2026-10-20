# PWA 기반 작업(앱 1단계) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 영양제.kr 사이트를 홈 화면에 설치할 수 있는 PWA 로 만들고(매니페스트·앱 아이콘·서비스워커·오프라인 안내·설치 배너), 스토어 제출에 필요한 개인정보처리방침 페이지를 추가한다.

**Architecture:** 정적 사이트 구조를 유지한다. 앱 아이콘은 Pillow 스크립트가 PNG 로 생성해 커밋하고, PWA 메타태그는 `build_site.py` 가 모든 HTML 의 `<link rel="icon">` 뒤 마커 블록에 넣는다. 서비스워커 `sw.js` 는 `scripts/sw_template.js` 에 빌드가 미리 받을 자산 목록(해시 포함)과 버전을 채워 생성하며, 페이지·데이터는 네트워크 우선, 해시 자산은 캐시 우선, 오프라인이면 `offline.html` 을 보여 준다. 등록과 설치 배너는 `layout.js` 가 맡는다.

**Tech Stack:** 정적 HTML + Vanilla JS, Python 3.11 + Pillow(아이콘 생성), `unittest`(파이썬 테스트), Node 24 내장 `node --test`(서비스워커 라우팅 테스트). 새 의존성 없음.

**Spec:** `docs/superpowers/specs/2026-10-20-mobile-app-reminders-design.md` (4절 1항 "사이트를 PWA 로", 6절 개인정보처리방침, 9절 1단계)

**분할 안내:** 설계 문서의 9절 다섯 단계 중 이 계획은 1단계만 다룬다. 2단계(내 영양제·시간표·기록·내보내기), 3단계(Capacitor 안드로이드 + 알림), 4~5단계(스토어·iOS CI)는 각각 별도 계획으로 세운다. 이 계획만으로도 배포 가능한 결과물(설치형 사이트)이 나온다.

## Global Constraints

- 스택: 정적 HTML + Tailwind 정적 빌드 + Vanilla JS. 프레임워크·번들러·런타임 CDN 추가 금지. 1st-party 스크립트는 `defer`.
- 새 Tailwind 클래스를 쓰지 않는다(쓰면 `npm run css` 필요). 새 스타일은 `assets/css/style.css` 에 일반 CSS 로.
- 생성 파일(`i/*.html`, `guide/*.html`, `guides.html`, `sitemap.xml`, `data/meta.json`, `data/guides-index.json`, 그리고 이 계획이 추가하는 `sw.js`)은 손으로 고치지 않고 `python scripts/build_site.py` 로 만든다. JS·CSS 를 고친 뒤에도 빌드한다(`?v=` 해시).
- 주소: canonical·OG 는 퓨니코드 `https://xn--og5b1hx9c.kr`, 확장자 없는 형태. 내부 링크는 `.html` 유지. 매니페스트의 `start_url`·`scope`·바로가기 주소는 배포 환경 기준(확장자 없는 절대 경로 `/`, `/compatibility`).
- 브랜드 색: `theme_color` `#246d4b`(index.html 의 기존 theme-color), `background_color` `#f8faf5`(푸터 배경). 아이콘 배경 `#3a7d44`, 잎 `#ffffff`, 잎맥 `#9cc6a4`(favicon.svg 값).
- 앱 이름 "영양제.kr", 짧은 이름 "영양제".
- 응답·커밋 메시지·주석·문서는 한국어. 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- 각 작업 끝: `python scripts/build_site.py && python scripts/check_site.py`(실패 0) 뒤 커밋. 푸시는 Task 6 에서 한 번(푸시 = 배포).
- 로컬 확인용 `.claude/launch.json` 은 커밋 전에 지운다. 모바일 뷰포트 확인 뒤 데스크톱으로 되돌린다.
- 건강 정보 표현은 식약처 기능성 범위. 이 계획의 문구(오프라인 안내·설치 배너·개인정보처리방침)에 효능 표현을 넣지 않는다.

## Review Focus

1. 배포 직후 옛 서비스워커가 옛 JS/CSS 를 돌려줘 새 HTML 과 어긋나는 상황 — 자산이 하나라도 바뀌면 `sw.js` 버전이 바뀌고, 새 버전 활성화 때 옛 캐시를 지워야 한다. → Task 3 `test_sw_version_changes_when_precache_changes`, `sw.test.mjs` "캐시 이름에 버전이 들어간다".
2. 분석(googletagmanager)·제휴(link.coupang 등)·비-GET 요청이 서비스워커를 거치면 안 된다(캐시되거나 막히면 통계·수수료가 깨짐). → Task 3 `sw.test.mjs` bypass 테스트 3건.
3. 오프라인에서 한 번도 안 연 페이지로 이동하면 브라우저 오류 화면이 아니라 `offline.html` 이 나와야 한다. → Task 3 Step 10 로컬 서버를 끄고 확인.
4. 하위 폴더 페이지(`i/`·`guide/`, `data-root="../"`)에서 매니페스트·아이콘 경로가 루트로 풀려야 한다. → Task 2 `test_ensure_pwa_tags_uses_root_prefix`, `check_site.py` 매니페스트 아이콘 존재 검사.
5. iOS 홈 화면 아이콘은 투명 배경·둥근 모서리 PNG 면 검게 보인다. 또 이미 설치한 사용자(standalone)에게 설치 배너가 다시 뜨면 안 된다. → Task 1 `test_apple_touch_icon_is_opaque_square`, Task 4 `shouldShowInstallBanner` 브라우저 검증.

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `scripts/build_app_icons.py` (신규) | favicon.svg 의 잎 도형을 Pillow 로 그려 앱 아이콘 PNG 5종 생성 |
| `assets/images/app/*.png` (생성·커밋) | `icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `apple-touch-icon.png`(180), `icon-1024.png`(스토어용) |
| `manifest.webmanifest` (신규) | 웹 앱 매니페스트 |
| `scripts/build_site.py` (수정) | `asset_digest()` 분리, PWA 태그 마커 주입, 미리 받을 자산 목록, `sw.js` 생성, `STATIC_PAGES` 에 `privacy.html` |
| `scripts/sw_template.js` (신규) → `sw.js` (생성) | 서비스워커. 라우팅 판단 함수는 순수 함수로 두어 Node 테스트 |
| `offline.html` (신규) | 오프라인 안내 페이지(외부 자산 없음, noindex) |
| `privacy.html` (신규) | 개인정보처리방침 |
| `assets/js/layout.js` (수정) | 서비스워커 등록, 설치 배너, 푸터에 개인정보처리방침 링크 |
| `assets/css/style.css` (수정) | 설치 배너 스타일 |
| `scripts/check_site.py` (수정) | 매니페스트 아이콘 존재·모든 색인 페이지의 manifest 링크 검사 |
| `_headers` (수정) | `sw.js` no-cache, 매니페스트 1시간 캐시 |
| `tests/test_app_icons.py`, `tests/test_build_site.py`, `tests/sw.test.mjs` (신규) | 테스트. 실행: `python -m unittest discover -s tests -v`, `node --test tests/` |
| `CLAUDE.md`, `docs/PROJECT-STATUS.md` (수정) | 생성 파일 목록·명령·이력 |

---

### Task 1: 앱 아이콘 생성 스크립트

**Files:**
- Create: `scripts/build_app_icons.py`
- Create: `tests/test_app_icons.py`
- Create(생성물): `assets/images/app/icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `apple-touch-icon.png`, `icon-1024.png`

**Interfaces:**
- Produces: `draw_icon(size: int, *, rounded: bool, scale: float = 1.0, opaque: bool = False) -> PIL.Image.Image` — favicon.svg 와 같은 도형을 `size` 픽셀로. `rounded` 면 모서리 반지름 `size/4`(SVG rx 16/64)에 바깥은 투명, 아니면 꽉 찬 사각 배경. `scale` 은 잎·잎맥을 중심 기준으로 축소하는 비율(maskable 안전 영역용 0.8). `opaque` 면 RGB 로 반환.
- Produces: `build(out_dir: Path) -> list[Path]` — 위 5개 파일을 쓰고 경로 목록 반환. `main()` 은 `assets/images/app/` 에 생성.
- 도형 정의(64 단위 좌표, favicon.svg 그대로): 배경 `#3a7d44`; 잎 `M14 40 C 20 20, 40 12, 52 16 C 50 36, 34 50, 14 40 Z` 채움 `#ffffff`; 잎맥 `M18 38 C 28 30, 38 24, 48 20` 선 `#9cc6a4`, 굵기 3, 둥근 끝. 곡선은 3차 베지어를 40점씩 샘플해 다각형·선으로 그리고, 4배 크기로 그린 뒤 LANCZOS 로 줄여 계단 현상을 없앤다.
- 파일별 인자: `icon-192`·`icon-512`: rounded, scale 1.0 / `icon-maskable-512`: rounded 아님, scale 0.8, opaque / `apple-touch-icon`(180): rounded 아님, scale 1.0, opaque / `icon-1024`: rounded 아님, opaque.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_app_icons.py`

```python
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_app_icons as B

class AppIconTests(unittest.TestCase):
    def test_build_writes_five_files_with_sizes(self):
        with tempfile.TemporaryDirectory() as d:
            files = {p.name: p for p in B.build(Path(d))}
            from PIL import Image
            self.assertEqual(set(files), {"icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png", "icon-1024.png"})
            self.assertEqual(Image.open(files["icon-192.png"]).size, (192, 192))
            self.assertEqual(Image.open(files["apple-touch-icon.png"]).size, (180, 180))
            self.assertEqual(Image.open(files["icon-1024.png"]).size, (1024, 1024))

    def test_rounded_icon_has_transparent_corner(self):
        im = B.draw_icon(512, rounded=True)
        self.assertEqual(im.mode, "RGBA")
        self.assertEqual(im.getpixel((2, 2))[3], 0)
        self.assertEqual(im.getpixel((256, 256))[:3], (255, 255, 255))   # 중앙은 흰 잎

    def test_maskable_keeps_safe_zone_background(self):
        im = B.draw_icon(512, rounded=False, scale=0.8, opaque=True)
        self.assertEqual(im.mode, "RGB")
        for xy in ((2, 2), (509, 509), (51, 51), (460, 51)):   # 모서리와 안전 영역 밖 10% 지점은 배경색
            self.assertEqual(im.getpixel(xy), (58, 125, 68))

    def test_apple_touch_icon_is_opaque_square(self):
        im = B.draw_icon(180, rounded=False, opaque=True)
        self.assertEqual(im.mode, "RGB")
        self.assertEqual(im.getpixel((1, 1)), (58, 125, 68))
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m unittest tests.test_app_icons -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_app_icons'`

- [ ] **Step 3: `scripts/build_app_icons.py` 구현** — 위 Interfaces 의 두 함수와 `main()`. 모듈 docstring 에 용도와 실행법(`python scripts/build_app_icons.py`)을 적는다. 베지어 샘플링은 `bezier(p0, p1, p2, p3, n=40) -> list[tuple[float, float]]` 하나로.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m unittest tests.test_app_icons -v`
Expected: `OK` (4 tests)

- [ ] **Step 5: 아이콘 생성 후 눈으로 확인**

Run: `python scripts/build_app_icons.py && ls assets/images/app`
Expected: 5개 PNG. Read 도구로 `icon-512.png`·`icon-maskable-512.png` 를 열어 잎이 중앙에 있고 maskable 은 가장자리에 여백이 있는지 본다.

- [ ] **Step 6: 커밋**

```bash
git add scripts/build_app_icons.py tests/test_app_icons.py assets/images/app
git commit -m "feat(pwa): 앱 아이콘 PNG 세트 생성 스크립트(Pillow, favicon 잎 도형)와 아이콘 5종"
```

---

### Task 2: 매니페스트와 PWA 메타태그 주입

**Files:**
- Create: `manifest.webmanifest`
- Modify: `scripts/build_site.py` (`head_html`, 새 함수 3개, `main()`)
- Modify: `index.html:6` (손으로 넣은 `theme-color` 줄 삭제 — 주입 블록이 대신 넣음)
- Modify: `scripts/check_site.py` (`check_html`)
- Create: `tests/test_build_site.py`

**Interfaces:**
- Consumes: Task 1 의 아이콘 파일 경로.
- Produces(`scripts/build_site.py`):
  - `PWA_START = "<!-- pwa:start -->"`, `PWA_END = "<!-- pwa:end -->"`
  - `pwa_tags(root: str) -> str` — 줄바꿈으로 이은 6줄: `<link rel="manifest" href="{root}manifest.webmanifest">`, `<link rel="apple-touch-icon" href="{root}assets/images/app/apple-touch-icon.png">`, `<meta name="theme-color" content="#246d4b">`, `<meta name="mobile-web-app-capable" content="yes">`, `<meta name="apple-mobile-web-app-title" content="영양제.kr">`, `<meta name="apple-mobile-web-app-status-bar-style" content="default">`.
  - `ensure_pwa_tags(html: str, root: str) -> str` — 마커 블록이 있으면 내용을 `pwa_tags(root)` 로 갱신, 없으면 `<link rel="icon"` 이 있는 줄 바로 뒤에 `\n  {PWA_START}\n  <각 줄 앞 2칸>\n  {PWA_END}` 를 삽입, 둘 다 없으면 그대로 반환. 멱등.
  - `inject_pwa_tags() -> None` — 루트 `*.html` + `i/*.html` + `guide/*.html` 각각의 `data-root="…"` 값(없으면 `./`)으로 `ensure_pwa_tags` 를 적용해 바뀐 파일만 쓴다. `main()` 에서 `inject_verification(cfg)` 다음, `stamp_assets()` 전에 호출.
  - `head_html()` 의 `<link rel="icon" …>` 줄 다음에 `{PWA_START}`·`pwa_tags(root)`·`{PWA_END}` 블록을 직접 넣는다(생성 페이지는 주입 없이도 완전).
- Produces(`manifest.webmanifest`, JSON): `name` "영양제.kr — 영양제 궁합·복용 가이드", `short_name` "영양제", `id` "/", `start_url` "/?source=pwa", `scope` "/", `display` "standalone", `lang` "ko", `dir` "ltr", `background_color` "#f8faf5", `theme_color` "#246d4b", `description` = config.js 의 `description` 문장, `categories` ["health","lifestyle"], `icons` [192 any, 512 any, 512 maskable — `src` 는 `/assets/images/app/…`], `shortcuts` [{"name":"궁합 체크","url":"/compatibility"},{"name":"성분 사전","url":"/ingredients"},{"name":"영양제 가이드","url":"/guides"}].
- Produces(`scripts/check_site.py`): `check_html()` 끝에 — `manifest.webmanifest` 가 없으면 실패; JSON 파싱 실패면 실패; 각 `icons[].src`(앞 `/` 제거)가 파일로 없으면 실패; noindex·404·naver 확인 페이지를 뺀 모든 HTML 에 `rel="manifest"` 가 없으면 실패. docstring 검사 항목에 추가.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_build_site.py`

```python
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site as B

HEAD = '<head>\n  <meta charset="UTF-8">\n  <link rel="icon" href="../assets/images/favicon.svg" type="image/svg+xml">\n  <link rel="stylesheet" href="../assets/css/style.css">\n</head>'

class PwaTagTests(unittest.TestCase):
    def test_ensure_pwa_tags_uses_root_prefix(self):
        out = B.ensure_pwa_tags(HEAD, "../")
        self.assertIn('<link rel="manifest" href="../manifest.webmanifest">', out)
        self.assertIn('href="../assets/images/app/apple-touch-icon.png"', out)
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m unittest tests.test_build_site -v`
Expected: FAIL — `AttributeError: module 'build_site' has no attribute 'ensure_pwa_tags'`

- [ ] **Step 3: `build_site.py` 에 상수·`pwa_tags`·`ensure_pwa_tags`·`inject_pwa_tags` 구현, `head_html` 에 블록 추가, `main()` 에 호출 추가**

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m unittest tests.test_build_site -v`
Expected: `OK` (3 tests)

- [ ] **Step 5: `manifest.webmanifest` 작성, `index.html` 의 손으로 넣은 theme-color 줄 삭제, `check_site.py` 검사 추가**

- [ ] **Step 6: 빌드·점검으로 전 페이지 주입 확인**

Run: `python scripts/build_site.py && python scripts/check_site.py --quiet && grep -L 'rel="manifest"' *.html i/*.html guide/*.html`
Expected: 점검 `결과: 실패 0 · 경고 0`. grep 은 `404.html`·`naver….html` 정도만 출력(둘은 `<link rel="icon"` 이 없으면 주입되지 않아도 됨; 있다면 주입되어도 무방). `index.html` 에 `theme-color` 가 정확히 1개: `grep -c theme-color index.html` → `1`.

- [ ] **Step 7: 커밋**

```bash
git add manifest.webmanifest scripts/build_site.py scripts/check_site.py tests/test_build_site.py index.html i guide *.html
git commit -m "feat(pwa): 웹 앱 매니페스트와 PWA 메타태그(마커 블록) 빌드 주입, check_site 매니페스트 검사"
```

---

### Task 3: 서비스워커·오프라인 페이지·등록

**Files:**
- Create: `scripts/sw_template.js`, `offline.html`, `tests/sw.test.mjs`
- Modify: `scripts/build_site.py` (`asset_digest` 분리, `precache_urls`, `sw_version`, `build_sw`, `main()`), `tests/test_build_site.py`(테스트 추가)
- Modify: `assets/js/layout.js` (등록), `_headers`
- Create(생성물): `sw.js`

**Interfaces:**
- Consumes: Task 2 의 매니페스트·아이콘 경로.
- Produces(`build_site.py`):
  - `asset_digest(path: Path) -> str` — `stamp_assets()` 안의 `digest` 를 모듈 함수로 꺼낸 것(CRLF→LF 정규화 sha1 앞 8자, 없으면 "0"). `stamp_assets()` 는 이것을 쓴다.
  - `precache_urls() -> list[str]` — 정렬된 절대 경로 목록: `assets/css/*.css` 와 `assets/js/**/*.js` 는 `/assets/…?v={asset_digest}`, 그리고 `/offline.html`, `/manifest.webmanifest`, `/assets/images/favicon.svg`, `/assets/images/home/leaf.webp`, `/assets/images/app/icon-192.png`, `/assets/images/app/icon-512.png`.
  - `sw_version(template: str, urls: list[str]) -> str` — 템플릿 본문과 목록을 합친 sha1 앞 8자.
  - `build_sw() -> None` — `scripts/sw_template.js` 를 읽어 `"__VERSION__"` 을 버전으로, `/*__PRECACHE__*/[]` 를 JSON 배열로 바꿔 루트 `sw.js` 에 LF 로 쓴다. `main()` 에서 `stamp_assets()` 직전에 호출.
- Produces(`scripts/sw_template.js`, 템플릿 자체가 유효한 JS):
  - 상단 주석: 생성 파일 안내(`sw.js` 는 빌드가 만듦, 직접 고치지 않음).
  - `var VERSION = "__VERSION__"; var PRECACHE = /*__PRECACHE__*/[];`
  - 캐시 이름: `"static-" + VERSION`, `"pages-" + VERSION`, `"data-" + VERSION`, 폰트는 `"fonts-v1"`(버전과 무관).
  - `function strategyFor(url, method, mode, origin)` → `"bypass" | "page" | "asset" | "data" | "font"`. 규칙 순서: `method !== "GET"` → bypass; `mode === "navigate"` 는 같은 origin 이면 page, 아니면 bypass; 같은 origin 이고 pathname 이 `/assets/` 로 시작 → asset; `/data/` 로 시작 → data; host 가 `cdn.jsdelivr.net`·`fonts.googleapis.com`·`fonts.gstatic.com` 중 하나 → font; 그 밖(googletagmanager, google-analytics, link.coupang, click.linkprice 등 모든 타 origin) → bypass.
  - 전략: page = 네트워크 우선(성공하면 `pages-` 에 저장) → 캐시 → `/offline.html`; asset = 캐시 우선(없으면 네트워크 후 `static-` 저장); data = 네트워크 우선(성공 시 `data-` 저장) → 캐시; font = 캐시가 있으면 즉시 주고 뒤에서 갱신, 없으면 네트워크 후 저장.
  - install: `PRECACHE` 를 `static-` 에 `addAll`, `skipWaiting()`. activate: 이름이 `static-|pages-|data-` 로 시작하되 VERSION 이 다른 캐시 삭제, `clients.claim()`.
  - 끝에 `if (typeof module !== "undefined") module.exports = { strategyFor: strategyFor, VERSION: VERSION };`. `self.addEventListener` 호출은 `typeof self !== "undefined" && self.addEventListener` 일 때만.
- Produces(`offline.html`): 외부 CSS·JS·폰트 없음(인라인 스타일만, 시스템 글꼴). `<meta name="robots" content="noindex">`, `<title>오프라인 — 영양제.kr</title>`. 본문: 잎 이모지 없이 텍스트 "지금은 인터넷에 연결되어 있지 않아요", 설명 "연결되면 자동으로 다시 열립니다. 이미 열어 본 페이지는 오프라인에서도 볼 수 있어요.", 버튼 "다시 시도"(`location.reload()`), 홈 링크 `/`. 배경 `#f8faf5`, 글자 `#1b2a22`, 버튼 `#246d4b`.
- Produces(`layout.js`): DOMContentLoaded 리스너 앞에 `/* PWA 서비스워커 등록 … */` 블록 — `"serviceWorker" in navigator && /^https?:$/.test(location.protocol)` 일 때 `window.addEventListener("load", …)` 안에서 `navigator.serviceWorker.register(D.url("sw.js")).catch(function () {})`.
- Produces(`_headers`): 추가 2블록 — `/sw.js` → `Cache-Control: no-cache`, `/manifest.webmanifest` → `Cache-Control: public, max-age=3600`.

- [ ] **Step 1: 실패하는 Node 테스트 작성** — `tests/sw.test.mjs`

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const { strategyFor, VERSION } = createRequire(import.meta.url)("../scripts/sw_template.js");
const O = "https://xn--og5b1hx9c.kr";

test("같은 origin 페이지 이동은 page", () => assert.equal(strategyFor(O + "/i/zinc", "GET", "navigate", O), "page"));
test("해시 자산은 asset", () => assert.equal(strategyFor(O + "/assets/js/data.js?v=abc12345", "GET", "no-cors", O), "asset"));
test("데이터 JSON 은 data", () => assert.equal(strategyFor(O + "/data/ingredients.json", "GET", "cors", O), "data"));
test("폰트 CDN 은 font", () => assert.equal(strategyFor("https://fonts.gstatic.com/s/x.woff2", "GET", "cors", O), "font"));
test("POST 는 bypass", () => assert.equal(strategyFor(O + "/data/x.json", "POST", "cors", O), "bypass"));
test("분석 스크립트는 bypass", () => assert.equal(strategyFor("https://www.googletagmanager.com/gtag/js?id=G-X", "GET", "no-cors", O), "bypass"));
test("제휴 링크는 bypass", () => assert.equal(strategyFor("https://link.coupang.com/a/x", "GET", "navigate", O), "bypass"));
test("템플릿의 버전 자리표시자", () => assert.equal(VERSION, "__VERSION__"));
```

- [ ] **Step 2: Node 테스트가 실패하는지 확인**

Run: `node --test tests/`
Expected: 실패 — `Cannot find module '../scripts/sw_template.js'`

- [ ] **Step 3: `scripts/sw_template.js` 구현**

- [ ] **Step 4: Node 테스트 통과 확인**

Run: `node --test tests/`
Expected: `# pass 8`, `# fail 0`

- [ ] **Step 5: 실패하는 파이썬 테스트 추가** — `tests/test_build_site.py` 에 클래스 추가

```python
class ServiceWorkerBuildTests(unittest.TestCase):
    def test_precache_urls_are_absolute_and_hashed(self):
        urls = B.precache_urls()
        self.assertIn("/offline.html", urls)
        self.assertIn("/manifest.webmanifest", urls)
        self.assertTrue(any(u.startswith("/assets/js/data.js?v=") and len(u.split("?v=")[1]) == 8 for u in urls))
        self.assertTrue(all(u.startswith("/") for u in urls))
        self.assertEqual(urls, sorted(urls))

    def test_sw_version_changes_when_precache_changes(self):
        t = "var x;"
        self.assertNotEqual(B.sw_version(t, ["/a?v=1"]), B.sw_version(t, ["/a?v=2"]))
        self.assertEqual(len(B.sw_version(t, ["/a"])), 8)

    def test_build_sw_fills_placeholders(self):
        B.build_sw()
        sw = (B.ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertNotIn("__VERSION__", sw)
        self.assertNotIn("/*__PRECACHE__*/", sw)
        self.assertIn('"/offline.html"', sw)
```

- [ ] **Step 6: 테스트 실패 확인**

Run: `python -m unittest tests.test_build_site -v`
Expected: 새 3개 FAIL(`AttributeError`), 기존 3개 OK

- [ ] **Step 7: `build_site.py` 에 `asset_digest`·`precache_urls`·`sw_version`·`build_sw` 구현, `main()` 호출, `offline.html` 작성, `layout.js` 등록, `_headers` 추가**

- [ ] **Step 8: 테스트·빌드·점검**

Run: `python -m unittest discover -s tests -v && node --test tests/ && python scripts/build_site.py && node --check sw.js && python scripts/check_site.py --quiet`
Expected: 파이썬 6 tests OK, Node pass 8, `sw.js` 문법 OK, 점검 `실패 0 · 경고 0`(offline.html 은 noindex 라 sitemap 검사에서 제외됨).

- [ ] **Step 9: 브라우저에서 등록·캐시 확인** — `.claude/launch.json`(name `static`, `python -m http.server 8080`) 만들고 `preview_start name=static`. `http://localhost:8080/index.html` 을 연 뒤 `javascript_tool` 로:

```js
(async () => { const r = await navigator.serviceWorker.ready; const keys = await caches.keys(); const c = await caches.open(keys.find(k => k.startsWith("static-"))); return { active: !!r.active, keys, cached: (await c.keys()).length }; })()
```
Expected: `active: true`, `keys` 에 `static-<8자>` 포함, `cached` 가 `sw.js` 의 PRECACHE 길이와 같음. 콘솔 오류 없음.

- [ ] **Step 10: 오프라인 폴백 확인** — `i/zinc.html` 을 한 번 연 뒤 `preview_stop` 으로 서버를 끄고, 같은 탭에서 `i/zinc.html` 로 이동 → 페이지가 캐시에서 열림(제목에 "아연"). 이어 `guide/does-not-exist.html` 로 이동 → "지금은 인터넷에 연결되어 있지 않아요" 가 보임. 확인 뒤 `preview_start` 로 서버를 다시 띄워 `offline.html` 대신 정상 페이지가 열리는지 본다. 끝나면 서버를 내리고 `.claude/launch.json` 삭제.

- [ ] **Step 11: 커밋**

```bash
git add scripts/sw_template.js scripts/build_site.py sw.js offline.html assets/js/layout.js _headers tests/sw.test.mjs tests/test_build_site.py i guide *.html
git commit -m "feat(pwa): 서비스워커(빌드 생성 sw.js, 자산 캐시·페이지/데이터 네트워크 우선·오프라인 안내)와 등록, _headers 캐시 규칙"
```

---

### Task 4: 홈 화면 설치 배너

**Files:**
- Modify: `assets/js/layout.js` (새 함수 2개, DOMContentLoaded 에서 호출, `window.Layout` 에 노출)
- Modify: `assets/css/style.css` (`.pwa-banner` 스타일)

**Interfaces:**
- Produces(`layout.js`):
  - `shouldShowInstallBanner(standalone: boolean, dismissedAt: number | null, now: number) -> boolean` — 순수 함수. `standalone` 이면 false; `dismissedAt` 이 있고 `now - dismissedAt < 30일(ms)` 이면 false; 그 밖 true.
  - `initInstallBanner() -> void` — standalone 여부는 `matchMedia("(display-mode: standalone)").matches || navigator.standalone === true`, `dismissedAt` 은 `localStorage.pwaBannerDismissedAt`(숫자, 읽기·쓰기 모두 try/catch). 안드로이드·데스크톱 Chrome: `beforeinstallprompt` 를 받으면 `preventDefault()` 후 배너 표시, "설치" 버튼이 `prompt()` 호출. iOS(`/iPhone|iPad/.test(navigator.userAgent)` 이고 standalone 아님): 바로 배너 표시하되 버튼 대신 안내 "Safari 공유 버튼 → '홈 화면에 추가'". 그 밖 브라우저는 표시하지 않음. "닫기" 는 `dismissedAt = Date.now()` 저장 후 제거. `appinstalled` 이벤트에 `window.gtag` 가 있으면 `gtag("event", "pwa_install")`.
  - 배너 마크업: `<div class="pwa-banner" role="dialog" aria-label="홈 화면에 설치">` 안에 아이콘(`assets/images/app/icon-192.png`, 40px), 문구 "영양제.kr 을 홈 화면에 설치하면 앱처럼 바로 열려요", 버튼 `설치` / `닫기`. 문구에 효능 표현 없음.
  - `window.Layout` 에 `shouldShowInstallBanner` 추가(브라우저 검증용).
- Produces(`style.css`): `.pwa-banner` — `position: fixed; left: 12px; right: 12px; bottom: calc(var(--tabbar-h, 64px) + 12px); z-index: 60;` 흰 배경, 둥근 모서리 16px, 그림자, `@media (min-width: 768px)` 에서는 `left: auto; width: 360px; bottom: 24px; right: 24px`. 모바일 탭 바 높이 변수가 `style.css` 에 이미 있으면 그 이름을 쓰고, 없으면 탭 바 실제 높이를 재서 `--tabbar-h` 기본값에 넣는다.

- [ ] **Step 1: 구현** — 위 두 함수와 스타일. 배너는 `renderTabbar()` 뒤에 `initInstallBanner()` 로 붙인다.

- [ ] **Step 2: 순수 함수 검증(브라우저)** — 빌드 후 로컬 서버에서 `index.html` 을 열고 `javascript_tool`:

```js
[Layout.shouldShowInstallBanner(true, null, 1e12), Layout.shouldShowInstallBanner(false, 1e12 - 86400000, 1e12), Layout.shouldShowInstallBanner(false, 1e12 - 31 * 86400000, 1e12), Layout.shouldShowInstallBanner(false, null, 1e12)]
```
Expected: `[false, false, true, true]`

- [ ] **Step 3: 모바일 화면 확인** — `resize_window preset=mobile` 뒤 `javascript_tool` 로 `document.body.insertAdjacentHTML("beforeend", <배너 마크업>)` 을 실행해 배너를 강제로 띄우고, 스크린샷으로 탭 바와 겹치지 않는지와 가로 스크롤이 없는지(`document.documentElement.scrollWidth === 375`) 본다. 확인 뒤 `resize_window preset=desktop`.

- [ ] **Step 4: 빌드·점검·커밋**

Run: `python scripts/build_site.py && python scripts/check_site.py --quiet`
Expected: `실패 0 · 경고 0`

```bash
git add assets/js/layout.js assets/css/style.css sw.js i guide *.html
git commit -m "feat(pwa): 홈 화면 설치 배너(Chrome beforeinstallprompt·iOS 공유 안내, 30일 닫기 기억)"
```

---

### Task 5: 개인정보처리방침 페이지

**Files:**
- Create: `privacy.html`
- Modify: `scripts/build_site.py:27` (`STATIC_PAGES` 에 `"privacy.html"` 추가 — `terms.html` 뒤)
- Modify: `assets/js/layout.js` 푸터(이용약관 링크 옆에 ` · <a …href="' + D.url("privacy.html") + '">개인정보처리방침</a>`)
- Modify: `terms.html` 제12조 끝에 한 문장: "자세한 내용은 <a href="privacy.html">개인정보처리방침</a>에서 볼 수 있습니다."

**Interfaces:**
- Produces(`privacy.html`): `terms.html` 과 같은 뼈대(동일 head 자산, `data-page="privacy" data-path="privacy.html"`, `.page-hero` + `.eyebrow-kicker`/`.page-title`/`.page-lead`, 본문 `article` 카드, 마지막 버튼 2개). `<title>개인정보처리방침 | 영양제.kr</title>`, description 50자 이상, canonical `https://xn--og5b1hx9c.kr/privacy`, robots index. 시행일 2026년 10월 20일.
  - 조문(제목 고정, 본문은 빌더가 작성하되 아래 사실만 담는다):
    1. 수집하는 개인정보 — 회원가입·로그인이 없어 이름·연락처 등 직접 수집 항목 없음. 자동 수집: Google Analytics 4 를 통한 방문 통계(방문 페이지·시각, 기기·브라우저 종류, 대략적 지역, 쿠키 식별자). IP 는 익명화 설정(`anonymize_ip`).
    2. 이용 목적 — 어떤 페이지가 읽히는지 파악해 콘텐츠를 개선. 광고·프로필 작성 없음.
    3. 보관 기간 — Google Analytics 의 데이터 보존 기간 설정을 따름(기본 2개월). 직접 보관하는 개인정보 없음.
    4. 처리 위탁·국외 이전 — Google LLC(미국)가 방문 통계를 처리. 이전 항목·목적·보유 기간을 표로.
    5. 앱·브라우저에 저장되는 정보 — 내 영양제 목록·알림 설정·복용 기록 같은 기능 데이터는 사용자의 기기 안(브라우저 저장소·앱 저장소)에만 저장되며 서버로 전송하지 않음. 삭제는 앱 삭제·브라우저 데이터 삭제·화면의 지우기 기능으로.
    6. 쿠키와 거부 방법 — 브라우저 쿠키 차단, Google Analytics 차단 부가기능 링크(`https://tools.google.com/dlpage/gaoptout`).
    7. 외부 링크·제휴 링크 — 쇼핑몰·제휴 링크를 누르면 해당 사이트의 정책이 적용됨. 사이트는 구매 정보를 받지 않음.
    8. 정보주체의 권리와 문의 — 열람·삭제 요청과 문의는 `help@usdt.io.kr`(config.js `contactEmail` 와 같은 값).
    9. 개인정보 보호책임자 — "운영자"와 위 이메일(실명은 사용자가 뒤에 채움).
    10. 변경 고지 — 바뀌면 이 페이지에 시행일과 함께 공지.
- 푸터·약관 링크는 위 Files 참고.

- [ ] **Step 1: `privacy.html` 작성, `STATIC_PAGES`·푸터·약관 링크 수정**

- [ ] **Step 2: 빌드·점검**

Run: `python scripts/build_site.py && python scripts/check_site.py --quiet && grep -c "privacy" sitemap.xml`
Expected: `실패 0 · 경고 0`, sitemap 에 `privacy` 1건(주소는 `https://xn--og5b1hx9c.kr/privacy`).

- [ ] **Step 3: 브라우저 확인** — 로컬 서버에서 `privacy.html` 을 열어 헤더·푸터가 그려지고 푸터에 "개인정보처리방침" 링크가 있는지, 모바일 폭에서 가로 스크롤이 없는지 확인. 확인 뒤 서버 종료·`.claude/launch.json` 삭제.

- [ ] **Step 4: 커밋**

```bash
git add privacy.html scripts/build_site.py assets/js/layout.js terms.html sitemap.xml sw.js i guide *.html
git commit -m "feat(privacy): 개인정보처리방침 페이지 신설(GA4 방문 통계·기기 내 저장·제휴 링크 고지), 푸터·약관 링크, sitemap 등록"
```

---

### Task 6: 문서 갱신·푸시·배포 확인

**Files:**
- Modify: `CLAUDE.md` — "생성 파일" 목록에 `sw.js`(`scripts/sw_template.js` 에서 생성) 추가; "자주 쓰는 명령"에 `python scripts/build_app_icons.py`(앱 아이콘 재생성)와 테스트 명령 `python -m unittest discover -s tests` / `node --test tests/` 추가; 구조 요약 `assets/js/` 항목에 `layout.js` 가 서비스워커 등록·설치 배너를 맡는다는 한 문장.
- Modify: `docs/PROJECT-STATUS.md` — 작업 이력에 10-20 행(PWA 화·개인정보처리방침·아이콘, 설계 문서·계획 경로), 7절에 "앱 프로젝트: 1단계 완료 → 다음은 계획 2(내 영양제·시간표·기록·내보내기)" 항목, 사용자 몫에 "privacy.html 보호책임자 실명 확인".

- [ ] **Step 1: 문서 수정 후 전체 테스트·빌드·점검**

Run: `python -m unittest discover -s tests && node --test tests/ && python scripts/build_site.py && python scripts/check_site.py --quiet && test ! -e .claude/launch.json && git status --short`
Expected: 테스트 통과, `실패 0 · 경고 0`, launch.json 없음, 변경 파일이 문서 2개(+ 빌드 산출물)뿐.

- [ ] **Step 2: 커밋·푸시**

```bash
git add -A
git commit -m "docs: PWA 1단계 완료 기록(생성 파일 sw.js·아이콘 스크립트·테스트 명령), 다음 단계 안내"
git show --stat --format='%h %s' HEAD | tail -5
git push origin HEAD
```

- [ ] **Step 3: 배포 확인(푸시 2~3분 뒤)**

Run: `curl -sI https://xn--og5b1hx9c.kr/sw.js | grep -i "cache-control\|HTTP/" && curl -s https://xn--og5b1hx9c.kr/manifest.webmanifest | python -c "import json,sys; m=json.load(sys.stdin); print(m['short_name'], len(m['icons']))"`
Expected: `HTTP/2 200`, `cache-control: no-cache`, `영양제 3`. 이어 앱 안 브라우저로 `https://xn--og5b1hx9c.kr/` 를 열고 Task 3 Step 9 의 스크립트로 `active: true` 확인.

- [ ] **Step 4: 사용자에게 보고** — 아이폰 Safari 에서 공유 → "홈 화면에 추가" 로 아이콘·이름이 "영양제" 로 뜨는지, 안드로이드 Chrome 에서 설치 배너가 뜨는지 확인을 요청. 다음 계획(내 영양제) 안내.

---

## 자가 점검 기록

- 사양 대조: 설계 4절 1항(매니페스트·아이콘·서비스워커·iOS 메타) → Task 1~3, 설치 유도 → Task 4, 6절 개인정보처리방침 → Task 5, 9절 1단계 → 전체. 앱 ID·Capacitor·알림·내 영양제는 다음 계획.
- 이름 일치: `ensure_pwa_tags`·`pwa_tags`·`inject_pwa_tags`·`asset_digest`·`precache_urls`·`sw_version`·`build_sw`·`strategyFor`·`shouldShowInstallBanner`·`initInstallBanner` 가 Interfaces·테스트·단계에서 같은 이름으로 쓰임.
- Review Focus 5건 모두 소유 작업에 테스트 또는 검증 단계가 있음.
