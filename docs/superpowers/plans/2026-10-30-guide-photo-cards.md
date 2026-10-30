# 가이드 '핵심 성분' 실사 카드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 가이드 90편의 `#ingredients` 구역을 어두운 띠 안의 실사 사진 카드(금색 번호·성분명·금색 한 줄·설명·복용 메모·오른쪽 아래 사진)로 바꾸고, 성분 87종의 사진을 `assets/images/ingredients/<id>.webp` 로 관리한다(없으면 `_default.webp`).

**Architecture:** 수동 데이터 `data/ingredient-photos.json`(프롬프트 틀·급원·금색 한 줄 `claim`) → 빌드가 `validate_photos` 로 검증하고 `prepare_photos` 가 실제 WebP 파일 유무를 `core["photos"]` 에 담음 → `render_guide` 가 그 표만 보고 카드를 그림(순수). 원본 PNG 는 저장소 밖, `scripts/convert_photos.py` 가 640×640 WebP 로 변환(Pillow 는 이 스크립트만 사용). 스타일은 `assets/css/style.css` 의 `.pc-*` 커스텀 클래스.

**Tech Stack:** Python 3.11+(build_site.py, unittest), Pillow(변환 스크립트만), 정적 HTML/CSS(Tailwind 유틸리티 추가 없음).

**Spec:** `docs/superpowers/specs/2026-10-30-guide-photo-cards-design.md`

## Global Constraints
- 금색 한 줄·본문에 질병·효능 과장 어휘 금지: 금칙어 `("치료", "예방", "완치", "진단", "완화", "항염", "빈혈", "구내염", "비대", "골다공증", "암", "당뇨", "고혈압")` — `claim` 은 14자 이하.
- 사진은 640×640 WebP, 품질 80; `<img alt="" width="640" height="640" loading="lazy" decoding="async">`.
- `build_site.py` 는 Pillow 를 import 하지 않는다(CI `requirements.txt` 는 requests 만).
- 새 Tailwind 클래스·새 lucide 아이콘을 쓰지 않는다(`.pc-*` CSS 만). 그래도 푸시 전 `npm run assets` 한 번.
- 생성 파일(`guide/*.html`, `sw.js`, `?v=`)은 빌드가 만든다. 커밋·문서·응답은 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus
1. 사진 파일이 하나도 없는 체크아웃(새 PC·CI)에서 빌드가 깨지지 않고 모든 카드가 `_default.webp` 로 떨어져야 한다 → Task 1 `prepare_photos` 테스트(빈 폴더).
2. `_default.webp` 마저 없으면 `check_site` 가 실패하므로 빌드가 **경고**로 알려야 한다 → Task 1 테스트(`_default` 없음 → `prepare_photos` 가 `default_missing=True` 반환, main 이 warning).
3. 성분 이름이 긴 카드(예: "콜라겐 (저분자 콜라겐펩타이드)")가 모바일 1열에서 사진과 겹치지 않아야 한다 → Task 3 CSS `.pc-name` 줄바꿈 허용 + 브라우저 확인 540px.
4. 가이드의 성분이 사전에서 사라진 경우(`by_id` 에 없음)는 지금처럼 건너뛰고 번호가 이어져야 한다 → Task 3 렌더 테스트(없는 id 섞기).
5. 사진을 교체했을 때 서비스워커·브라우저 캐시가 새 사진을 받아야 한다 → Task 3 테스트(`?v=` 가 파일 내용 해시, 내용이 다르면 값이 다름).

---

### Task 1: 사진 데이터 표 + 검증 + 준비 함수

**Files:**
- Create: `data/ingredient-photos.json`
- Modify: `scripts/build_site.py` (validate_tips 근처에 `PHOTO_FORBIDDEN`, `validate_photos`, `prepare_photos`, `PHOTO_DIR`)
- Test: `tests/test_build_site.py` (`PhotoCardTests`)

**Interfaces:**
- Produces: `PHOTO_DIR = ROOT / "assets" / "images" / "ingredients"`; `PHOTO_FORBIDDEN: tuple[str, ...]`; `validate_photos(data: dict, valid_ids: set[str]) -> None`(문제 있으면 `ValueError`); `prepare_photos(data: dict, valid_ids: set[str], photo_dir: Path = PHOTO_DIR) -> dict` → `{"files": {id: "<id>.webp" | "_default.webp"}, "claims": {id: str}, "default_missing": bool}`.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_build_site.py` 끝에:

```python
class PhotoCardTests(unittest.TestCase):
    """가이드 핵심 성분 실사 카드 — 사진 표 검증·준비·렌더."""

    @classmethod
    def setUpClass(cls):
        ingredients = B.read_json(B.DATA_DIR / "ingredients.json")
        cls.ids = {i["id"] for i in ingredients["items"]}
        cls.data = B.read_json(B.DATA_DIR / "ingredient-photos.json")

    def test_validate_photos_accepts_data_and_rejects_bad(self):
        import copy
        B.validate_photos(self.data, self.ids)
        bad = copy.deepcopy(self.data); bad["items"][0]["id"] = "no-such"
        with self.assertRaises(ValueError):
            B.validate_photos(bad, self.ids)
        bad = copy.deepcopy(self.data); bad["items"].pop()          # 빠진 성분
        with self.assertRaises(ValueError):
            B.validate_photos(bad, self.ids)
        bad = copy.deepcopy(self.data); bad["items"][0]["claim"] = "관절 · 항염"
        with self.assertRaises(ValueError):
            B.validate_photos(bad, self.ids)
        bad = copy.deepcopy(self.data); bad["items"][0]["claim"] = "가나다라마바사아자차카타파하가"   # 15자
        with self.assertRaises(ValueError):
            B.validate_photos(bad, self.ids)

    def test_prepare_photos_falls_back_to_default(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            empty = B.prepare_photos(self.data, self.ids, p)
            self.assertTrue(empty["default_missing"])
            self.assertEqual(empty["files"]["omega-3"], "_default.webp")
            (p / "_default.webp").write_bytes(b"x"); (p / "omega-3.webp").write_bytes(b"y")
            got = B.prepare_photos(self.data, self.ids, p)
            self.assertFalse(got["default_missing"])
            self.assertEqual(got["files"]["omega-3"], "omega-3.webp")
            self.assertEqual(got["files"]["zinc"], "_default.webp")
            self.assertEqual(got["claims"]["omega-3"], "혈행 · 중성지질")
```

- [ ] **Step 2: 실패 확인** — Run: `PYTHONUTF8=1 python -m unittest tests.test_build_site.PhotoCardTests -v` — Expected: FAIL/ERROR (`ingredient-photos.json` 없음, `validate_photos` 없음).

- [ ] **Step 3: `data/ingredient-photos.json` 작성** — 구조: `_meta{updatedAt, note}`, `template`(스펙의 프롬프트 틀), `default{subject}`, `items[87]{id, subject, claim}`. `subject` 는 스크래치 초안(`scratchpad/photos/subjects-all.json`)을 옮기고, `claim` 은 성분마다 `mfdsFunction` 을 14자 이하로 줄인 인정 표현(예: omega-3 "혈행 · 중성지질", vitamin-d "뼈 건강 · 칼슘 흡수", calcium "뼈 · 치아 형성", iron "산소 운반 · 혈액 생성", probiotics "장 건강 · 배변", zinc "면역 · 정상 세포분열", vitamin-c "항산화 · 면역", folate "세포 · 혈액 생성", vitamin-b12 "엽산 대사 · 혈액"). 금칙어 금지.

- [ ] **Step 4: 빌드 함수 구현** — `scripts/build_site.py` 의 `validate_tips` 아래에 `PHOTO_DIR`, `PHOTO_FORBIDDEN`, `validate_photos`, `prepare_photos` 추가. `validate_photos`: items 의 id 가 전부 `valid_ids` 안에 있고(중복 없이) `valid_ids` 전부를 덮어야 하며, `subject` 비어 있지 않고 `claim` 은 1~14자·금칙어 없음, `template` 에 `{SUBJECT}` 포함, `default.subject` 존재. `prepare_photos`: `photo_dir / f"{id}.webp"` 가 있으면 그 이름, 없으면 `"_default.webp"`; `default_missing = not (photo_dir / "_default.webp").exists()`.

- [ ] **Step 5: 통과 확인** — Run: 같은 명령 — Expected: PASS 2/2.

- [ ] **Step 6: 커밋** — `git add data/ingredient-photos.json scripts/build_site.py tests/test_build_site.py && git commit -m "feat(photos): 성분 사진 표(data/ingredient-photos.json) + validate_photos/prepare_photos"`

### Task 2: 변환 스크립트 `scripts/convert_photos.py`

**Files:**
- Create: `scripts/convert_photos.py`
- Test: `tests/test_convert_photos.py`

**Interfaces:**
- Produces: `convert_one(src: Path, dst: Path, size: int = 640, quality: int = 80) -> tuple[int, int]`(원본 크기 반환; 정사각형이 아니면 중앙 크롭, LANCZOS 리사이즈, WebP method 6); `main(argv: list[str]) -> int`: `convert_photos.py <원본 폴더> [--ids a,b] [--out 폴더]` — 폴더의 `*.png` 가운데 이름이 `data/ingredients.json` 의 id 이거나 `_default` 인 것만 변환, 모르는 이름은 건너뛰고 경고, 결과 표 출력.

- [ ] **Step 1: 실패하는 테스트** — `tests/test_convert_photos.py`:

```python
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    from PIL import Image
except ImportError:  # CI 에는 Pillow 가 없다
    Image = None

@unittest.skipIf(Image is None, "Pillow 없음")
class ConvertPhotosTests(unittest.TestCase):
    def test_convert_one_makes_square_640_webp(self):
        import convert_photos as C
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "omega-3.png"; Image.new("RGB", (1254, 1000), (200, 80, 40)).save(src)
            w, h = C.convert_one(src, Path(d) / "omega-3.webp")
            out = Image.open(Path(d) / "omega-3.webp")
            self.assertEqual((w, h), (1254, 1000)); self.assertEqual(out.size, (640, 640)); self.assertEqual(out.format, "WEBP")

    def test_main_skips_unknown_ids(self):
        import convert_photos as C
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d) / "raw"; raw.mkdir(); out = Path(d) / "out"
            Image.new("RGB", (64, 64)).save(raw / "omega-3.png"); Image.new("RGB", (64, 64)).save(raw / "nope.png"); Image.new("RGB", (64, 64)).save(raw / "_default.png")
            self.assertEqual(C.main([str(raw), "--out", str(out)]), 0)
            self.assertEqual(sorted(p.name for p in out.glob("*.webp")), ["_default.webp", "omega-3.webp"])
```

- [ ] **Step 2: 실패 확인** — Run: `PYTHONUTF8=1 python -m unittest tests.test_convert_photos -v` — Expected: ERROR (`convert_photos` 모듈 없음).
- [ ] **Step 3: 구현** — `scripts/convert_photos.py`(argparse, `ROOT = Path(__file__).resolve().parents[1]`, 기본 `--out` = `ROOT/assets/images/ingredients`, id 집합은 `data/ingredients.json` 에서 읽음 + `_default`).
- [ ] **Step 4: 통과 확인** — Expected: PASS 2/2.
- [ ] **Step 5: 커밋** — `git add scripts/convert_photos.py tests/test_convert_photos.py && git commit -m "feat(photos): 원본 PNG → 640 WebP 변환 스크립트 convert_photos.py"`

### Task 3: 카드 렌더 + CSS

**Files:**
- Modify: `scripts/build_site.py` `render_guide`(628~640행 `ing_html` 블록, 680행 `#ingredients` 섹션), `main()`(`build_guides` 앞에 `core["photos"]` 준비)
- Modify: `assets/css/style.css`(`.pc-*` 블록, `@media print`)
- Test: `tests/test_build_site.py` `PhotoCardTests` 에 렌더 테스트 추가

**Interfaces:**
- Consumes: Task 1 `prepare_photos` 결과를 `core["photos"]` 로.
- Produces: 카드 마크업 `<div class="pc-band"><div class="pc-grid"><article class="pc-card">…</article>…</div></div>`; 카드 안 `img.pc-photo`(src `../assets/images/ingredients/<파일>?v=<asset_digest>`), `span.pc-num`(`01`…), `a.pc-name`, `p.pc-claim`, `p.pc-mfds`(기존 70자 식약처 문구), `p.pc-desc`(`term_html(core, x["why"], st)`), `p.pc-meta`. `core.get("photos")` 가 없으면 지금 흰 카드 그대로(테스트 호환).

- [ ] **Step 1: 실패하는 테스트** — `PhotoCardTests` 에 추가:

```python
    def test_render_guide_uses_photo_or_default_and_numbering(self):
        import tempfile
        guides = B.read_json(B.DATA_DIR / "guides.json"); interactions = B.read_json(B.DATA_DIR / "interactions.json")
        ingredients = B.read_json(B.DATA_DIR / "ingredients.json")
        core = {"categories": ingredients["_meta"]["categories"], "by_id": {i["id"]: i for i in ingredients["items"]}, "guides": guides["items"], "pairs": interactions["pairs"], "types": interactions["_meta"]["types"]}
        gmodel = {"by_id": {g["id"]: g for g in guides["items"]}, "items": guides["items"]}
        gd = dict(next(g for g in guides["items"] if g["slug"] == "50s-plus"))
        gd["ingredients"] = [{"id": "omega-3", "why": "혈행에 도움."}, {"id": "no-such", "why": "x"}, {"id": "zinc", "why": "면역에 필요."}]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p / "_default.webp").write_bytes(b"d1"); (p / "omega-3.webp").write_bytes(b"o1")
            core["photos"] = B.prepare_photos(self.data, self.ids, p); core["photos"]["dir"] = p
            html = B.render_guide(gd, gmodel, core, {"name": "테스트", "url": "https://example.test"})
            self.assertIn('class="pc-card"', html)
            self.assertIn('src="../assets/images/ingredients/omega-3.webp?v=', html)
            self.assertIn('src="../assets/images/ingredients/_default.webp?v=', html)
            self.assertIn('<span class="pc-num">01</span>', html); self.assertIn('<span class="pc-num">02</span>', html)
            self.assertNotIn('<span class="pc-num">03</span>', html)       # 사전에 없는 id 는 건너뛰고 번호가 이어진다
            self.assertIn("혈행 · 중성지질", html)
            v1 = html.split('omega-3.webp?v=')[1][:8]
            (p / "omega-3.webp").write_bytes(b"o2")
            html2 = B.render_guide(gd, gmodel, core, {"name": "테스트", "url": "https://example.test"})
            self.assertNotEqual(v1, html2.split('omega-3.webp?v=')[1][:8])  # 사진을 바꾸면 ?v= 가 바뀐다
        core.pop("photos")
        plain = B.render_guide(gd, gmodel, core, {"name": "테스트", "url": "https://example.test"})
        self.assertNotIn("pc-card", plain)                                   # photos 가 없으면 기존 카드

    def test_cards_have_no_forbidden_words_across_all_guides(self):
        css = (B.ROOT / "assets" / "css" / "style.css").read_text(encoding="utf-8")
        for cls in (".pc-band", ".pc-card", ".pc-photo", ".pc-num", ".pc-claim"):
            self.assertIn(cls, css)
        for it in self.data["items"]:
            for w in B.PHOTO_FORBIDDEN:
                self.assertNotIn(w, it["claim"], f"{it['id']}: {w}")
```

- [ ] **Step 2: 실패 확인** — Run: `PYTHONUTF8=1 python -m unittest tests.test_build_site.PhotoCardTests -v` — Expected: 새 테스트 2건 FAIL(`pc-card` 없음 / CSS 없음).
- [ ] **Step 3: `render_guide` 구현** — `photos = core.get("photos")`; 있으면 `ing_html` 을 `.pc-card` 마크업으로, 번호는 `by_id` 에 있는 항목만 세어 `f"{n:02d}"`; `?v=` 는 `asset_digest(photos.get("dir", PHOTO_DIR) / fname)`; 섹션 틀은 `<div class="mt-4 pc-band"><div class="pc-grid">{ing_html}</div></div>`; photos 없으면 기존 코드 그대로.
- [ ] **Step 4: `main()` 연결** — `build_guides(core, cfg)` 앞에: `photos_data = read_json(DATA_DIR / "ingredient-photos.json", None)`; 있으면 `validate_photos` → `core["photos"] = prepare_photos(photos_data, set(core["by_id"]))`, `default_missing` 이면 `log.warning("assets/images/ingredients/_default.webp 가 없어 check_site 가 실패합니다 — python scripts/convert_photos.py <원본 폴더>")`; 없으면 warning 후 기존 카드.
- [ ] **Step 5: CSS** — `assets/css/style.css` 의 푸터 블록 앞에 `.pc-*` 규칙(스펙 '스타일' 절 값: 띠 radial-gradient #1b1b1b→#0b0b0b, 카드 #141414/#3a3a3a, 사진 absolute 오른쪽 아래 60%×72% + 135deg 마스크, 금색 번호 원, `.pc-claim` #ffd466, `.pc-desc` #e9e4d6 max-width 58%, `.pc-name` 줄바꿈 허용, 768px 미만 1열·사진 52%, `@media print { .pc-band{background:#fff;color:#000} .pc-photo{display:none} }`).
- [ ] **Step 6: 통과 확인** — Expected: PhotoCardTests 4/4 PASS, 그리고 `PYTHONUTF8=1 python -m unittest discover -s tests` 전체 OK.
- [ ] **Step 7: 커밋** — `git add scripts/build_site.py assets/css/style.css tests/test_build_site.py && git commit -m "feat(guide): 핵심 성분을 실사 사진 카드(.pc-*)로 — 번호·금색 한 줄·사진, 없으면 기본 사진"`

### Task 4: 사진 자산 투입 + 빌드·확인·배포

**Files:**
- Create: `assets/images/ingredients/_default.webp` + 변환된 `<id>.webp`(1차 11장 + 2차 묶음 결과)
- Modify: `CLAUDE.md`(구조 요약에 사진 표·변환 스크립트·카드), `docs/PROJECT-STATUS.md`(작업 이력·다음 할 일: 남은 사진 묶음), `.gitignore` 불필요(원본은 저장소 밖)

- [ ] **Step 1: 원본 보관 폴더로 옮기기** — `mkdir -p "/c/Users/OK/Pictures/영양제kr-성분사진-원본"` 후 `scratchpad/photos/raw/*.png` 복사(원본은 저장소 밖에 보관).
- [ ] **Step 2: 변환** — Run: `PYTHONUTF8=1 python scripts/convert_photos.py "/c/Users/OK/Pictures/영양제kr-성분사진-원본"` — Expected: `_default.webp` 포함 변환 표 출력, 각 50~90KB. `_default.png` 가 아직 없으면 임시로 `assets/images/home/hand-softgel.webp` 를 640 중앙 크롭해 `_default.webp` 로 두고(Pillow 한 줄) 문서에 '임시'로 적는다.
- [ ] **Step 3: 빌드·점검** — Run: `npm run assets && PYTHONUTF8=1 python scripts/build_site.py && PYTHONUTF8=1 python scripts/check_site.py` — Expected: 실패 0.
- [ ] **Step 4: 브라우저 확인** — 로컬 서버로 `guide/50s-plus.html` 데스크톱·540px: 카드 2열/1열, 사진이 글과 겹치지 않음, 사진 없는 성분은 기본 사진, 성분명 링크 동작. 끝나면 뷰포트 데스크톱·launch.json 삭제.
- [ ] **Step 5: 문서** — CLAUDE.md 구조 요약(`data/`·`scripts/`·가이드 카드), PROJECT-STATUS 작업 이력 1행 + 7절 다음 할 일(남은 사진 묶음: `scratchpad` 가 아닌 `data/ingredient-photos.json` 기준으로 아직 WebP 가 없는 id 목록 명령 `python -c ...` 또는 빌드 경고).
- [ ] **Step 6: 커밋·푸시** — `git add -A && git commit -m "feat(guide): 성분 실사 사진 n장 + 기본 사진 투입, 문서" && git pull --rebase && git push`; `git show --stat HEAD` 확인.

### Task 5: 남은 사진 묶음(반복)

- [ ] 보조 에이전트로 20장씩 생성(묶음마다 채팅 승인 1회) → 원본 폴더로 복사 → `convert_photos.py` → Claude 가 축소 모음으로 검수(글자·이상한 물체면 그 id 만 재생성) → 사용자에게 모음 전송 → 빌드·점검·커밋·푸시(`feat(photos): 성분 사진 n장 추가`). 모두 끝나면 PROJECT-STATUS 의 '남은 사진' 항목 삭제.
