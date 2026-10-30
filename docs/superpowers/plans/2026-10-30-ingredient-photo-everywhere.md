# 성분 실사 사진 확장(성분 사전 B-1 카드·상세 상단·썸네일) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 분류별 알약 그림이 들어가던 모든 자리를 성분별 실사 사진으로 바꾼다(목록은 B-1 띠, 상세는 정사각형 사진 + 금색 한 줄, 작은 목록은 썸네일).

**Architecture:** 변환기가 사진 3종(640/360/160)을 만들고, SSR 은 `ing_thumb_img`(해시 포함)·`render_page` 의 data 속성으로, JS 는 `Illus.ingPhotoUrl/ingThumb/ingBand` 로 같은 파일을 가리킨다. CSS 는 `.ing-band*`·`.ing-card-photo`·`.ing-hero-photo*`.

**Tech Stack:** Python(Pillow 는 변환기만)·Vanilla JS·CSS. **Spec:** `docs/superpowers/specs/2026-10-30-ingredient-photo-everywhere-design.md`

## Global Constraints
- 생성 파일 직접 수정 금지, 빌드 뒤 `check_site.py`, 커밋 전 `npm run assets`, 응답·커밋은 한국어, 건강 표현은 claim 그대로(금칙어 검사 유지).
- JS 사진 주소에는 `?v=` 를 붙이지 않고, SSR 은 `asset_digest` 해시를 붙인다.

## Review Focus
- 사진 3종 중 하나라도 빠진 성분 → `_default` + 경고(목록·썸네일이 404 가 되지 않게).
- `#ingredient-hero` 에 data 속성이 없는 옛 HTML 에서도 hero 가 그려져야 함.
- 긴 성분명(예 '감마리놀렌산 (달맞이꽃종자유)')이 띠 안에서 두 줄로 접혀도 배지와 겹치지 않음.
- 모바일 1열에서 띠 높이·글자 크기.
- 검색 결과·셀프체크 `finder-thumb-xs`(2.1rem) 에서도 사진이 꽉 참(`object-fit: cover`).

---

### Task 1: 변환기 3종 출력
Files: `scripts/convert_photos.py`, `tests/test_convert_photos.py`
- [ ] 테스트: `test_main_writes_three_sizes` — out 에 `omega-3.webp`·`omega-3-m.webp`·`omega-3-s.webp`(각 640/360/160) 와 `_default*` 3종. RED → `SIZES = (("", 640), ("-m", 360), ("-s", 160))`, `main` 이 세 번 `convert_one` → GREEN.
- [ ] 원본 폴더로 전체 재변환: `python scripts/convert_photos.py "C:/Users/OK/Pictures/영양제kr-성분사진-원본"` → 264 파일.

### Task 2: 빌드 — prepare_photos 3종·SSR 썸네일·hero data 속성·순서
Files: `scripts/build_site.py`, `tests/test_build_site.py`
- [ ] 테스트 `IngredientPhotoTests`: (a) `prepare_photos` 는 3종이 다 있을 때만 `<id>.webp`, 하나 빠지면 `_default.webp` 이고 `missing_sizes` 에 id; (b) `ing_thumb_img({"id":"omega-3","category":"fatty-acid"}, photos)` 가 `omega-3-s.webp?v=` 를, `photos=None` 이면 `assets/images/home/softgel-amber.webp` 를 담음; (c) `render_page(it, core_with_photos, cfg)` 의 `#ingredient-hero` 에 `data-photo="omega-3.webp?v=`·`data-photo-claim="혈행 · 중성지질"`, `core["photos"]` 없으면 속성 없음. RED → 구현 → GREEN.
- [ ] `main()`: 사진 준비 블록을 성분 페이지 루프 앞으로 옮김. `photo_img` 호출 6곳을 `ing_thumb_img(i, core.get("photos"))` 로.
- [ ] `python -m unittest tests.test_build_site -q` GREEN.

### Task 3: illus.js 헬퍼 + Node 테스트
Files: `assets/js/illus.js`, `tests/illus.test.mjs`
- [ ] `module.exports` 가드(`window` 없을 때), `ingPhotoUrl(id, size)`(size ""|"m"|"s"), `ingThumb(it, cls)`(`-s`, width/height 160, lazy), `ingBand(it, opts)`(`opts.tag` h2|h3, `opts.href`, `opts.badge` HTML; `-m` src + srcset 640). 테스트 RED → GREEN. CLAUDE.md 의 node 테스트 목록에 추가.

### Task 4: 페이지 JS + CSS
Files: `assets/js/pages/{ingredients,product,drug,search,finder,ingredient}.js`, `assets/css/style.css`, `tests/test_build_site.py`(CSS 클래스)
- [ ] CSS 테스트: `.ing-band`, `.ing-band-title`, `.ing-card-photo`, `.ing-card-body`, `.ing-hero-photo`, `.ing-hero-claim` 존재. RED → CSS → GREEN.
- [ ] ingredients.js 카드 → `ing-card ing-card-photo` + `I.ingBand` + `.ing-card-body`; product/drug `ingCard` 같은 구조(h3 링크); search/finder → `I.ingThumb`; ingredient.js hero → `.ing-hero-photo`(dataset.photo || ingPhotoUrl) + claim + 작은 칸 첫 칸 썸네일, `photo-badge` 제거.
- [ ] 빌드 → 로컬 서버에서 목록·상세·검색·셀프체크·제품·기능성·비교 확인(데스크톱·모바일), 콘솔 404 없음.

### Task 5: 문서·자산·배포
- [ ] CLAUDE.md(실사 카드 단락·convert 명령·node 테스트 목록), PROJECT-STATUS 10-30 행·다음 할 일 ⑬.
- [ ] `npm run assets` → `python scripts/build_site.py` → `python scripts/check_site.py` → 전체 테스트 → 커밋·푸시 → `git show --stat`.
