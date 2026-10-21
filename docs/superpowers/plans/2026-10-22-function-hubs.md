# 기능성별 허브 페이지(functions.html, function/<id>.html) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "체지방 감소 건강기능식품", "혈중 콜레스테롤 개선 원료", "수면의 질 개선 영양제"처럼 식약처 인정 기능성 문구 자체가 검색어인 의도를 받는 축을 만든다. 기능성 1개 = 페이지 1장(30장 안팎)으로, 그 기능성이 인정된 성분(성분 사전)·개별인정 원료(인정현황)·신고 제품(식약처 품목신고)·성분 간 궁합·복용 시간·관련 가이드를 한 장에 모은다. 거의 전부 기존 데이터라 작업량 대비 페이지 수가 가장 많고, 성분·제품·가이드 세 축을 잇는 내부 링크 허브가 된다.

**Architecture:** 정규화 표는 수동 데이터 `data/functions.json`(기능성 id·라벨·대표 인정 문구·정규식·그룹·아이콘·설명·관련 가이드)이다. 빌드의 `function_model()` 이 성분 사전의 `mfdsFunction`, 원료 인정현황의 `function`, 제품 상세 조각의 `function` 문구를 공백을 뺀 문자열로 정규식에 맞춰 기능성마다 성분·원료·제품을 모으고, `render_function()`·`render_functions_hub()` 가 `function/<id>.html` 과 `functions.html` 을 쓴다. 성분 페이지와 성분 상세 스크립트에는 "이 성분이 인정된 기능성" 칩을 붙여 역방향 링크를 만든다(클라이언트용 요약 색인 `data/functions-index.json` 생성). 궁합은 궁합 데이터(`interactions.json`)에 있는 쌍만 보여주고 규칙 판정은 궁합 체크에 맡긴다.

**Tech Stack:** 정적 HTML(빌드 생성) + 기존 CSS(`.chart-*` 재사용, `.fn-*` 소량 추가) + 파이썬 빌드·`unittest`, 점검 `check_site.py`(새 디렉터리 포함).

**Spec:** 2026-10-21 분석 1번(기능성별 허브). 키워드 잠식 방지: 고민별 가이드와 주제가 겹치므로 허브는 "식약처 인정 기능성 '…' — 성분·원료·제품 목록"이라는 자료 성격의 제목을 쓰고, 추천·조합 설명은 가이드로 보낸다.

## Global Constraints

- CLAUDE.md 규칙: 생성 파일은 빌드로만, 점검 실패 0, 푸시 전 `npm run assets`(새 아이콘은 허브 페이지에 나타나야 번들에 들어가므로 빌드 → `npm run icons` → 빌드 순).
- 기능성 문구는 식약처 인정 문구를 원문 그대로 인용하고, intro 는 치료·예방 표현 없이 중립적으로 쓴다. 제품 수는 "수집 범위(2021-04 이후 신고) 기준"임을 밝힌다.
- 한 검색 의도에 한 페이지: 제목 틀 "`{라벨}` 영양제 — 식약처 인정 기능성 '{문구}' 성분·원료·제품", 가이드 제목과 겹치지 않게.
- 응답·커밋·주석·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 정규식이 엉뚱한 문구를 잡으면 안 된다(예: '성장'이 '상피세포의 성장'을, '면역'이 '면역과민반응'을, '피로'가 '눈의 피로'를 잡는 것). → `exclude` 와 프로파일 테이블, 테스트.
2. 모든 기능성에 성분·원료·제품 중 하나 이상이 있어야 하고(빈 페이지 금지), 성분 사전 81종 가운데 어느 기능성에도 안 들어가는 성분은 설명 가능한 것(홍삼·프로바이오틱스처럼 들어가야 할 성분이 빠지면 안 됨). → `validate_functions` + 테스트.
3. 새 디렉터리 `function/` 을 사이트맵·스탬프·PWA 태그·점검(`check_site.py`)·Tailwind content 가 모두 포함해야 한다. → Task 2.
4. 제품 목록은 브랜드 가중치·신고일 순으로 12건만, 나머지는 건수로. 제품 링크는 noindex 상세(`product.html?id=`)라도 괜찮지만 구매 버튼은 넣지 않는다(앱 모드 고려).
5. 성분 페이지의 기능성 칩은 정적 SSR 과 JS 렌더 양쪽에 같은 내용이어야 한다. → `functions-index.json`.

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `data/functions.json` (신규, 수동) | 기능성 정규화 표 30장 안팎: id·group·label·claim·icon·match·exclude·intro·guides, `_meta.groups` |
| `scripts/build_site.py` (수정) | `validate_functions`, `function_model`, `render_function`, `render_functions_hub`, `build_functions`(디렉터리 정리·요약 색인), 사이트맵·스탬프·PWA 열거에 `function/` 추가, 성분 페이지 기능성 칩 |
| `function/<id>.html`, `functions.html`, `data/functions-index.json` (생성) | 기능성 페이지·허브·요약 색인 |
| `assets/js/pages/ingredient.js`, `assets/js/data.js` (수정) | 성분 상세의 '인정 기능성' 섹션에 기능성 칩(`D.functions()` 로더) |
| `assets/js/layout.js`, `ingredients.html`, `index.html`? (수정) | 푸터·성분 사전 허브 진입 링크 |
| `assets/css/style.css` (수정) | `.fn-*` 소량 |
| `scripts/check_site.py`, `tailwind.config.cjs` (수정) | `function/` 포함 |
| `tests/test_build_site.py` (수정) | 검증·모델·렌더 테스트 |
| `CLAUDE.md`, `README.md`, `docs/PROJECT-STATUS.md` (수정) | 구조·이력·다음 할 일 |

---

### Task 1: 정규화 표와 모델 + 테스트

- [x] `data/functions.json` 30장 안팎(체중·혈당·혈관 / 장·간·위·요로 / 면역·피로·항산화·에너지·혈액 / 눈·피부·뼈·관절·구강·모발·과민반응 / 기억력·수면·스트레스 / 운동·성장·갱년기·월경·전립선). 프로파일로 성분·원료·제품 수를 확인하고 오탐 정규식은 `exclude` 로 막는다.
- [x] `function_model(data, core, materials, products)` → 기능성마다 `{ingredients, materials, products(total, top 12), pairs(synergy·caution), guides}`; 성분→기능성 역색인.
- [x] `validate_functions`: id·group·아이콘 필수, 정규식 컴파일, 가이드 slug 존재, 빈 기능성 금지.
- [x] 테스트: 오탐 방지(면역과민·눈의 피로·상피세포 성장), 실데이터 전 기능성 비어 있지 않음, 홍삼·프로바이오틱스·비타민D 가 기대 기능성에 들어감.

### Task 2: 페이지 생성과 디렉터리 등록

- [x] `render_function`: 히어로(제목·인정 문구·집계), 성분 카드(궁합 체크·내 영양제 추가 버튼), 개별인정 원료 표(원료명·인정번호·인정일·문구), 신고 제품 12건 + 전체 건수, 성분 간 궁합(데이터 쌍), 복용 시간, 관련 가이드 카드, FAQ(FAQPage JSON-LD), 허브·궁합표·시간표·셀프체크 링크. BreadcrumbList·CollectionPage JSON-LD.
- [x] `render_functions_hub`: 그룹별 카드(아이콘·라벨·문구·성분/원료/제품 수), 설명, FAQ.
- [x] `build_functions`: `function/` 생성·오래된 파일 정리, `functions-index.json`(기능성 id·label·claim·성분 id 목록·수). 사이트맵(`functions.html` 0.8, `function/*` 0.7), `stamp_assets`·`inject_pwa_tags`·`check_site.html_files`·Tailwind content 에 `function/` 추가.

### Task 3: 역링크·진입점·문서

- [x] 성분 페이지 SSR '식약처 인정 기능성' 아래 기능성 칩(`../function/<id>.html`), `ingredient.js` 같은 섹션에 `D.functions()` 로 칩 렌더.
- [x] 푸터 '기능성별 영양제', 성분 사전 허브·가이드 허브에 링크, 궁합표·시간표 관련 링크 상자에 추가.
- [x] CLAUDE.md(생성 파일·구조), README 트리, PROJECT-STATUS(페이지 구성·이력·다음 할 일 ② 완료).

### Task 4: 빌드·점검·테스트·커밋

- [x] 빌드 → `npm run icons`(새 아이콘) → 빌드 → `check_site.py` 실패 0 → `unittest` → 브라우저(허브·기능성 페이지 데스크톱/모바일, 성분 페이지 칩, 콘솔 오류 없음) → 커밋 → `git show --stat` → 푸시.
