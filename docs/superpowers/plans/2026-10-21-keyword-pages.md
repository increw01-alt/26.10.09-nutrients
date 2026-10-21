# 핵심 키워드 페이지(영양제 궁합표·복용 시간표)와 제목·메뉴 정비 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사이트의 핵심 검색어(영양제 궁합·영양제 추천·영양제 복용 시간)를 정면으로 받는 정적 페이지 두 장을 기존 데이터만으로 빌드가 생성하게 하고, 메뉴·푸터·성분 페이지 제목·가이드 키워드를 같은 키워드로 정비한다. 186개 페이지 중 제목에 '영양제 궁합'이 들어간 페이지가 2개뿐이고 '궁합표'·'복용 시간표' 의도를 받는 페이지가 없는 상태를 고친다.

**Architecture:** `scripts/build_site.py` 에 순수 함수 `chart_model(core)`(성분별 상대 목록 + 자주 찾는 성분 행렬)과 `timing_model(ingredients)`(시간대별 묶음 + 성분별 행)를 두고, 렌더러 `render_compat_chart`·`render_timing_chart` 가 `compatibility-chart.html`·`timing-chart.html` 을 루트에 쓴다. 시간대 이름·순서·설명은 `assets/js/schedule.js` 의 `SLOT_ORDER`·`SLOT_META` 를 파이썬에 옮긴 상수로 쓰고, 테스트가 두 파일을 대조해 어긋나면 실패한다. 새 페이지는 JS 없이 읽히는 정적 본문(검색엔진용)이며, 상호작용이 필요한 조합은 기존 도구(`compatibility.html?items=`, `my.html`)로 보낸다. 데이터에 없는 쌍은 표에서 '–'로 두고 규칙 판정(`resolvePair`)은 도구에 맡긴다(파이썬에 규칙을 복제하지 않는다).

**Tech Stack:** 정적 HTML + Tailwind 정적 빌드(새 유틸리티는 `npm run assets` 로 반영) + `assets/css/style.css` 의 `.chart-*` 일반 CSS, 파이썬 빌드·`unittest`, 점검 `scripts/check_site.py`.

**Spec:** 2026-10-21 분석(채팅): 5개 콘텐츠 작업 중 1번 — 궁합표·시간표 페이지와 라벨·제목 정비. 2~6번(셀프체크·기능성 허브·성분 비교·약별 가이드·용어 사전)은 `docs/PROJECT-STATUS.md` 다음 할 일에 순서만 적어 둔다.

## Global Constraints

- CLAUDE.md 규칙 그대로: 생성 파일은 빌드로만, JS·CSS 수정 뒤 `python scripts/build_site.py`, 점검 `python scripts/check_site.py` 실패 0, 푸시 전 `npm run assets` 로 `tailwind.css`·`icons.js` 를 CI 와 맞춤.
- canonical·og:url·sitemap 은 확장자 없는 주소(`page_url()`); 내부 링크는 `.html`.
- 건강 정보 표현은 식약처 인정 범위. 새 페이지의 설명 문장은 궁합 데이터의 `title`·`tip`, 성분의 `timing.label`·`timing.note` 와 데이터 집계 수치만 쓰고 새 효능 서술을 만들지 않는다.
- 한 검색 의도에 한 페이지: 궁합 체크(도구)·궁합표(표)·조합 원칙 가이드(설명)의 제목을 서로 다르게 유지한다. 모든 제목에 '영양제 궁합'을 반복하지 않는다.
- 응답·커밋·주석·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 시간대 상수가 `schedule.js` 와 어긋나면 시간표 페이지와 내 영양제 시간표가 다른 말을 한다. → Task 1 `test_slot_meta_matches_schedule_js`.
2. 궁합표의 성분별 목록은 쌍 방향 모두에 같은 판정이 나와야 한다(a 의 좋은 궁합에 b 가 있으면 b 에도 a). → Task 1 `test_chart_model_is_symmetric`.
3. 데이터에 없는 쌍을 '무난'으로 보이게 하면 안 된다. 행렬에서는 '–'와 "궁합 체크에서 규칙으로 판정" 안내. → Task 2 렌더 확인.
4. 성분 페이지 제목을 바꿔도 `check_site.py` 의 중복 제목·조사 경고가 없어야 하고, 상세 탭 라벨이 길어지지 않아야 한다. → Task 3.
5. 메뉴 라벨이 길어져 데스크톱 헤더가 줄바꿈되거나 모바일 탭 바가 바뀌면 안 된다(탭 바는 그대로). → Task 3 브라우저 확인.

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `scripts/build_site.py` (수정) | `SLOT_ORDER`·`SLOT_META`·`CHART_POPULAR`, `chart_model`, `timing_model`, `render_compat_chart`, `render_timing_chart`, `STATIC_PAGES` 추가, `main()` 에서 두 페이지 생성, 성분 페이지 제목·섹션 제목·링크, 가이드 페이지 '바로 보는 표' 링크 |
| `compatibility-chart.html`, `timing-chart.html` (생성) | 영양제 궁합표 · 영양제 복용 시간표 |
| `assets/css/style.css` (수정) | `.chart-*` 표·칩 스타일 |
| `assets/js/layout.js` (수정) | 메뉴 라벨 '영양제 궁합'·'영양제 추천', 푸터에 궁합표·시간표 링크 |
| `compatibility.html`, `index.html` (수정) | 궁합표·시간표 진입 링크 |
| `data/guides.json` (수정) | 복용법 가이드 keywords 에 '복용 시간' 계열 보강 |
| `tests/test_build_site.py` (수정) | 모델·상수 대조 테스트 |
| `CLAUDE.md`, `README.md`, `docs/PROJECT-STATUS.md` (수정) | 생성 파일 목록·구조·이력·다음 할 일 |

---

### Task 1: 모델 함수와 상수 + 테스트

**Files:** `scripts/build_site.py`, `tests/test_build_site.py`

- [x] `SLOT_ORDER`·`SLOT_META`(label·sub·icon) 를 `schedule.js` 와 같은 값으로 추가, `CHART_POPULAR` 12종(비타민 D·오메가3·프로바이오틱스·마그네슘·칼슘·철분·아연·비타민 C·비타민 B군·루테인·코엔자임Q10·밀크씨슬).
- [x] `chart_model(core, popular=None) -> {partners, matrix{ids, cells}, counts, total}`: 성분별 상대를 type 별로 모으고 level 내림차순·이름순 정렬, 행렬 셀은 쌍 type 또는 None, 대각선 "self".
- [x] `timing_model(ingredients, categories) -> {rows, slots, fat}`: 분류 순서·이름순 행, 시간대별 묶음, 지용성 목록. `timing.slot` 이 없거나 모르는 값이면 `morning_after`.
- [x] 테스트: 상수 대조(정규식으로 `schedule.js` 파싱), 대칭성, 행렬 None/self, 시간표 행 수 = 성분 수, 모든 slot 이 `SLOT_ORDER` 안.

### Task 2: 두 페이지 렌더러와 생성

**Files:** `scripts/build_site.py`, `assets/css/style.css`

- [x] `render_compat_chart`: 히어로(제목 '영양제 궁합표: 같이 먹어도 되는 조합, 나눠 먹어야 하는 조합', 집계 수치, 궁합 체크·복용 시간표 버튼) → 자주 찾는 성분 12종 행렬(셀은 `compatibility.html?items=a,b` 링크, 범례) → 분류별 성분 블록(좋은 궁합·주의(간격 시간 표시)·피함 칩, 무난은 `<details>` 텍스트) → 읽는 법·FAQ(보이는 본문 + FAQPage JSON-LD) → 관련 가이드 링크.
- [x] `render_timing_chart`: 히어로(제목 '영양제 복용 시간표: 성분별 먹는 시간 한눈에', 내 영양제·먹는 시간 가이드·궁합표 버튼) → 시간대별 6칸 → 성분별 표(권장 시간·기본 시간대·대체 시간대·메모·지용성) → 원칙 상자(지용성·공복·취침 전·식전 목록은 데이터에서) → FAQ.
- [x] `STATIC_PAGES` 에 두 파일 추가(사이트맵 priority 0.8), `main()` 에서 `build_sitemap` 전에 생성. JSON-LD 는 BreadcrumbList + FAQPage.
- [x] `style.css` 에 `.chart-matrix`(가로 스크롤, 첫 열 고정, type 별 색), `.chart-row`, `.chart-chip-*`, `.timing-table`.

### Task 3: 메뉴·푸터·성분 페이지·가이드·홈 연결

**Files:** `assets/js/layout.js`, `scripts/build_site.py`, `compatibility.html`, `index.html`

- [x] NAV 라벨 '궁합 체크'→'영양제 궁합', '가이드'→'영양제 추천'(푸터는 '영양제 추천 가이드'), 푸터 바로가기에 '영양제 궁합표'·'영양제 복용 시간표'. 모바일 탭 바는 그대로.
- [x] 성분 페이지: 제목 `{성분} 효능·권장량·궁합·먹는 시간`, 섭취 시간 섹션에 시간표 링크(`timing-chart.html#id`), 궁합 섹션 제목에 '같이 먹으면 좋은 영양제와 주의할 조합' 덧붙이고 궁합표 링크(`compatibility-chart.html#id`). 상세 탭 라벨은 짧게 유지.
- [x] 가이드 페이지 FAQ 앞에 '바로 보는 표' 상자(궁합표·시간표 링크), 가이드 허브 안내 상자에도 링크.
- [x] `compatibility.html` 히어로 아래 '선택 없이 전체 궁합표 보기', `index.html` 빠른 체크 하단에 '전체 궁합표 · 복용 시간표'.

### Task 4: 가이드 키워드·문서

**Files:** `data/guides.json`, `CLAUDE.md`, `README.md`, `docs/PROJECT-STATUS.md`

- [x] 복용법 가이드 keywords 보강: when-to-take(영양제 복용 시간·영양제 복용 시간표), multivitamin-guide(종합비타민 먹는 시간), zinc-guide(아연 먹는 시간), probiotics-guide(유산균 먹는 시간), with-medication(약과 영양제 복용 간격).
- [x] CLAUDE.md 생성 파일 목록·구조 요약, README 페이지 안내, PROJECT-STATUS 페이지 구성·이력·다음 할 일(5개 콘텐츠 작업 순서).

### Task 5: 빌드·점검·테스트·커밋

- [x] `npm run assets` → `python scripts/build_site.py` → `python scripts/check_site.py`(실패 0) → `python -m unittest discover -s tests` → `node --test tests/*.mjs`.
- [x] 브라우저 확인: 두 페이지 데스크톱·모바일(행렬 가로 스크롤, 앵커 이동, 콘솔 오류 없음), 헤더 라벨 줄바꿈 없음, 성분 페이지 링크.
- [x] 커밋(한국어 메시지) → `git show --stat` 확인 → 푸시.
