# 제형·형태 비교(compare/<slug>.html, 성분 비교 허브 두 번째 묶음) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "rTG 오메가3 vs 일반", "리포좀 비타민C 차이", "헴철 비헴철", "산화마그네슘 vs 구연산", "탄산칼슘 구연산칼슘", "활성엽산", "비타민D3 D2", "글루코사민 황산염 염산염", "천연 비타민E", "산화아연 글루콘산아연", "저분자 콜라겐" 같은 '같은 성분의 다른 형태' 검색을 받는 비교 글 11편을 만든다. 성분 대 성분 비교(14편)와 달리 기준 성분은 하나이고 열이 형태이며, 식약처 품목신고 제품의 원재료명·제품명 표기로 형태별 제품 수와 대표 제품을 걸러 보여 준다(제품명 색인에는 형태 표기가 드물어 상세 조각의 원재료명을 쓴다). 가격대·흡수율 수치·우열 단정은 쓰지 않는다.

**Architecture:** 수동 데이터 `data/form-compares.json`(slug·id(기준 성분)·title·h1·description·keywords·intro·forms[key·label·short·match(제품명+원재료명 정규식; `rest: true` 는 다른 형태에 걸리지 않은 나머지)·shopQuery·line·pick]·rows(수동 비교 행)·verdict·label(라벨에서 보는 법)·faq·related(가이드)·terms(용어 slug))을 `build_site.py` 의 `form_compare_model` 이 제품 상세 조각(`core["products_detail"]`, 기능성 허브가 읽은 것을 재사용)·브랜드 가중치·가이드·용어 사전과 합쳐 `render_form_compare` 로 `compare/<slug>.html` 을 쓴다(비교표 = 수동 행 + '수집 제품 수' 자동 행, 핵심 차이, 이런 분은, 라벨에서 보는 법, 형태별 제품 예시 + 쇼핑 버튼(`pages/compare.js` 재사용), 관련 용어·가이드, FAQ, Article+FAQPage+Breadcrumb JSON-LD, 본문 용어 자동 링크). 성분 비교 모델(`core["compares"]`)에 `forms` 로 더해져 허브 `compare.html` 의 두 번째 묶음, 요약 색인(`kind: "form"`), 성분 페이지 '비교 글' 칩, 사이트맵에 함께 들어간다.

**Tech Stack:** 정적 HTML(빌드 생성) + 기존 JS(`pages/compare.js`) + 기존 CSS(`.cmp-*`·`.timing-table`·`.finder-*`·`.chart-chip`) + 파이썬 빌드·`unittest`, 점검 `check_site.py`.

**Spec:** 2026-10-22 성분 비교 계획의 후속(제형 비교는 제품명 색인으로 제품만 걸러 보여 주고 설명은 수동). 원재료명 집계로 형태 표기가 잡히는 11개 성분만 다룬다(코엔자임Q10 유비퀴놀·B12 메틸코발라민·유산균 코팅은 수집분에서 표기가 거의 없어 제외).

## Global Constraints

- CLAUDE.md 규칙: 생성 파일은 빌드로만, 점검 실패 0, 푸시 전 `npm run assets`.
- 형태 설명은 원료·제조·표기·먹는 법 같은 사실 관계와 성분 사전의 식약처 인정 범위 안에서만 쓰고, '흡수율 ○배'·가격대·'더 효과적' 같은 표현은 쓰지 않는다. 함량 기준은 식약처 1일 섭취량·상한섭취량만 인용한다.
- 정규식은 제품명+원재료명에 대해 대소문자 무시로 맞추며, 한 제품이 여러 형태에 들어갈 수 있음을 표에 밝힌다. `rest` 형태는 한 편에 최대 하나.
- slug 는 성분 비교 14편과 겹치지 않아야 하고(빌드 검증), 제목 틀은 "`{성분} {형태A} vs {형태B}`: …".
- 응답·커밋·주석·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 기준 성분 id·가이드 slug·용어 slug·정규식 오류·행 셀 누락은 빌드가 실패해야 한다. → `validate_form_compares`.
2. `rest` 형태는 다른 형태에 걸린 제품을 포함하지 않는다. → 테스트.
3. 형태별 대표 제품은 브랜드 가중치 → 신고일 순이고 이름 중복이 없다.
4. 쇼핑 버튼은 형태마다 하나씩(`data-query`), 앱 모드에서 숨는다(`.app-hide`).
5. 허브·요약 색인·성분 페이지 칩·사이트맵에 형태 비교가 모두 들어간다.

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `data/form-compares.json` (신규, 수동) | 형태 비교 11편의 본문·형태 정규식 |
| `scripts/build_site.py` (수정) | `validate_form_compares`, `form_compare_model`, `render_form_compare`, `prepare_form_compares`, `write_compares`·`render_compare_hub`·요약 색인·성분 페이지 칩 확장, `prepare_functions` 가 제품 조각을 `core["products_detail"]` 에 둠 |
| `compare/<slug>.html` (생성 11편), `compare.html`·`data/compares-index.json` (갱신) | 형태 비교 페이지·허브·색인 |
| `tests/test_build_site.py` (수정) | 검증·모델·렌더 테스트 |
| `CLAUDE.md`, `README.md`, `docs/PROJECT-STATUS.md` (수정) | 구조·이력·다음 할 일(③ 제형 비교 완료) |

---

### Task 1: 데이터

- [x] `data/form-compares.json` 11편: 오메가3(rTG·식물성·크릴·일반 어유) · 비타민C(리포좀·서방·완충·일반) · 철분(헴철·푸마르산철·황산철·피로인산철) · 마그네슘(산화·유기산염·해조·염화) · 칼슘(탄산·구연산·해조·산호·난각·우유·기타 염) · 엽산(활성엽산·일반) · 비타민D(D3·D2) · 글루코사민(황산염·염산염) · 비타민E(천연·합성) · 아연(산화·글루콘산·효모) · 콜라겐(저분자 펩타이드·어류·일반).

### Task 2: 빌드

- [x] 검증·모델(제품 조각 정규식 집계, rest, 대표 제품)·렌더·허브 묶음·요약 색인·성분 페이지 칩·사이트맵.

### Task 3: 문서

- [x] CLAUDE.md·README·PROJECT-STATUS(③ 제형 비교 완료).

### Task 4: 빌드·점검·테스트·커밋

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` 실패 0 → `unittest` → 브라우저(허브 묶음·형태 비교 페이지 표·제품 칩·쇼핑 버튼·성분 페이지 칩, 데스크톱/모바일, 콘솔 오류 없음) → 커밋 → `git show --stat` → 푸시.
