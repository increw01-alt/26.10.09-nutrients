# 성분 비교 페이지(compare.html, compare/<slug>.html) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "홍삼 인삼 차이", "글루코사민 콘드로이친 MSM", "스피루리나 클로렐라" 같은 비교형 검색(구매 직전 단계)을 받는 'A vs B' 페이지를 만든다. 비교표의 대부분(인정 기능성·권장량·먹는 시간·지용성·주의·추천 대상·신고 제품 수·기능성별 페이지)은 성분 사전과 집계 데이터에서 자동으로 채우고, 핵심 차이·상황별 추천·FAQ 만 수동으로 쓴다. 각 성분의 쇼핑 버튼(제휴 링크)과 제품 찾기로 이어져 제휴 전환을 노린다. 첫 묶음은 성분 사전에 모두 있는 성분 대 성분 14편이며, 제형 비교(rTG/EE·리포좀·헴철 등)는 뒤로 미룬다.

**Architecture:** 수동 데이터 `data/compares.json`(slug·ids·제목·설명·키워드·intro·verdict·성분별 요약·picks·수동 비교 행·together·faq·related)을 빌드의 `compare_model()` 이 성분 사전·`products/top/<id>.json` 의 `_meta.total`·기능성 모델(`core["functions"]`)·궁합 데이터(`findPair`)와 합쳐 `render_compare()` 로 `compare/<slug>.html` 을, `render_compare_hub()` 로 `compare.html` 을 쓴다. 성분 페이지에는 '비교 글' 칩(SSR + `pages/ingredient.js` 의 `D.compares()` 요약 색인)을 붙인다. 쇼핑 버튼은 정적 HTML 의 `[data-shop-query]` 자리에 `pages/compare.js` 가 `Affiliate.buttonsHtml()` 로 채우고, 앱 모드에서는 `.app-hide` 로 숨긴다. 궁합은 데이터 쌍이 없으면 수동 `together` 문장과 궁합 체크 링크로 대신한다.

**Tech Stack:** 정적 HTML(빌드 생성) + Vanilla JS 소량 + 기존 CSS(`.timing-table`·`.finder-*`·`.chart-chip` 재사용, `.cmp-*` 소량) + 파이썬 빌드·`unittest`, 점검 `check_site.py`(`compare/` 포함).

**Spec:** 2026-10-21 분석 3번(성분 비교). 가격대 행은 데이터가 없어 넣지 않고, 흡수율은 성분 사전에 이미 있는 정성 표현만 쓴다.

## Global Constraints

- CLAUDE.md 규칙: 생성 파일은 빌드로만, 점검 실패 0, 푸시 전 `npm run assets`.
- 수동 문장은 식약처 인정 범위 안에서: 각 성분의 기능성 문구는 사전의 `mfdsFunction` 을 그대로 인용하고, 비교 설명은 작용 방식·원료·인정 구분·주의처럼 사실 관계만 적는다. '더 효과적', '치료' 같은 표현과 근거 없는 수치는 쓰지 않는다.
- 한 검색 의도에 한 페이지: 제목 틀 "`{A} vs {B}`: 차이와 고르는 기준". 성분 페이지·기능성 페이지와 겹치지 않게 비교에만 집중한다.
- 응답·커밋·주석·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. ids 가 성분 사전에 없거나 related 가이드 slug 가 틀리면 빌드가 실패해야 한다. → `validate_compares`.
2. 비교표의 자동 행은 모든 성분 열에 값이 있어야 하고(빈 칸은 '—'), 3개 비교(글루코사민·콘드로이친·MSM, 다이어트 3종)도 표가 깨지지 않아야 한다. → 테스트·모바일 확인(첫 열 고정, 가로 스크롤).
3. 쇼핑 버튼은 앱 모드에서 숨겨지고, 의약품처럼 구매 링크를 넣으면 안 되는 성분은 없다(모두 건강기능식품 성분). → `.app-hide`.
4. 궁합 데이터가 없는 쌍에서 '무난'으로 단정하지 않는다. → 수동 `together` + 궁합 체크 링크.
5. 새 디렉터리 `compare/` 를 사이트맵·스탬프·PWA·점검·Tailwind 가 모두 포함한다.

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `data/compares.json` (신규, 수동) | 비교 14편의 본문 데이터 |
| `scripts/build_site.py` (수정) | `validate_compares`, `compare_model`, `render_compare`, `render_compare_hub`, `write_compares`, 사이트맵·스탬프·PWA 열거, 성분 페이지 '비교 글' 칩 |
| `compare/<slug>.html`, `compare.html`, `data/compares-index.json` (생성) | 비교 페이지·허브·요약 색인 |
| `assets/js/pages/compare.js` (신규) | 쇼핑 버튼·제휴 고지 채우기 |
| `assets/js/data.js`, `assets/js/pages/ingredient.js` (수정) | `compares()` 로더, 성분 상세 '비교 글' 칩 |
| `assets/js/layout.js`, 가이드 허브(빌드 템플릿) (수정) | 푸터·허브 진입 링크 |
| `scripts/check_site.py`, `tailwind.config.cjs`, `assets/css/style.css` (수정) | `compare/` 포함, `.cmp-*` |
| `tests/test_build_site.py` (수정) | 검증·모델·렌더 테스트 |
| `CLAUDE.md`, `README.md`, `docs/PROJECT-STATUS.md` (수정) | 구조·이력·다음 할 일 |

---

### Task 1: 비교 데이터 14편

- [x] 홍삼 vs 인삼 · 글루코사민 vs 콘드로이친 vs MSM · 스피루리나 vs 클로렐라 · 가르시니아 vs 녹차추출물 vs CLA · 루테인 vs 아스타잔틴 · 콜라겐 vs 히알루론산 · 테아닌 vs 락티움 · 차전자피 vs 난소화성말토덱스트린 · 바나바 vs 여주 · 홍국 vs 폴리코사놀 · 오메가3 vs 감마리놀렌산 · 밀크씨슬 vs 커큐민 · 프로바이오틱스 vs 프락토올리고당 · 크레아틴 vs 아르기닌.
- [x] 항목: slug·ids·title·h1·description·keywords·intro·verdict·points(성분별 한 줄 + 이런 분)·rows(수동 행: 원료·인정 구분·작용 방식 등)·together·faq·related.

### Task 2: 빌드

- [x] `validate_compares`(ids·slug 형식·중복·related slug), `compare_model`(자동 행 + 수동 행, 제품 수, 기능성 칩, 궁합 쌍), `render_compare`(히어로·성분 카드·비교표·핵심 차이·상황별 추천·같이 먹어도 될까·먹는 시간·쇼핑 버튼 자리·관련 가이드·FAQ, Article+FAQPage+Breadcrumb JSON-LD), `render_compare_hub`, `write_compares`(디렉터리 정리·요약 색인), 사이트맵, 성분 페이지 칩.
- [x] `compare/` 를 `stamp_assets`·`inject_pwa_tags`·`check_site.html_files`·Tailwind content 에 추가.

### Task 3: 스크립트·진입점·문서

- [x] `pages/compare.js` 쇼핑 버튼, `data.js` 로더, `ingredient.js` 칩, 푸터·가이드 허브 링크, `.cmp-*` CSS.
- [x] CLAUDE.md·README·PROJECT-STATUS(③ 완료).

### Task 4: 빌드·점검·테스트·커밋

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` 실패 0 → `unittest` → 브라우저(허브·비교 페이지 데스크톱/모바일, 쇼핑 버튼, 성분 페이지 칩, 콘솔 오류 없음) → 커밋 → `git show --stat` → 푸시.
