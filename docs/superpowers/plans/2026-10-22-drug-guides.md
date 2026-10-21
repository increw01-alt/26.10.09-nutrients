# 약별 영양제 가이드(drug-guides.html, drug-guide/<id>.html) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "타이레놀 영양제 같이", "메트포르민 비타민B12", "갑상선약 칼슘 간격", "와파린 오메가3" 같은 '약 이름 + 영양제' 검색을 받는 약별 궁합 페이지를 만든다. 이미 있는 의약품 규칙 `data/drug-pairings.json`(21개 분류: 함께 챙기면 좋은/주의할 영양 성분·간격·메모)을 데이터 축으로 삼아, 분류마다 비교표(성분·판정·간격·이유)·좋은 성분 카드·주의 성분 목록·복용 요령·이 분류의 식약처 허가 의약품 목록(검색 색인과 같은 판정)·관련 가이드·FAQ 를 한 장에 모은다. 약 복용자 대상 장문 가이드(`guide/diabetes-meds.html` 등 15편)는 '설명', 이 페이지는 '약 기준 빠른 참조표'로 역할을 나눠 제목이 겹치지 않게 한다.

**Architecture:** 수동 본문 `data/drug-guides.json`(규칙 id 와 1:1 — short·title·h1·description·keywords·intro·drugs(대표 성분·제품)·rx(처방약 여부)·timing(복용 요령)·faq·related)을 빌드의 `drug_guide_model()` 이 규칙(좋은/주의 성분·간격·메모)·성분 사전·의약품 상세 조각(`data/drugs/detail/*.json`, `assets/js/data.js` 의 `drugPairingFor` 와 같은 판정 `drug_rule_hits` 로 분류별 약 수·대표 제품 — 브랜드 가중치 순)·가이드와 합쳐 `render_drug_guide()` 로 `drug-guide/<id>.html` 을, `render_drug_guides_hub()` 로 `drug-guides.html`(일반의약품/처방약 묶음 + 복용 간격 한눈에 표)을 쓴다. 성분 페이지에 '약과 함께' 칩(SSR + `pages/ingredient.js` 의 `D.drugGuides()` 요약 색인), 의약품 상세(`pages/drug.js`)의 영양제 조합 섹션에 해당 분류 가이드 링크(`drugPairingFor` 가 규칙 id 도 돌려줌), 푸터·가이드 허브 진입 링크를 둔다. 처방약 분류(스타틴·갑상선·와파린·항생제·골다공증약·메트포르민·이뇨제·레티노이드·MTX·스테로이드)는 e약은요 수집 범위(일반의약품 중심)에 약이 없으므로 약 목록 대신 대표 성분·제품명(수동)을 보여 주고 '전문의약품은 처방전·약봉투로 확인' 안내를 붙인다.

**Tech Stack:** 정적 HTML(빌드 생성) + Vanilla JS 소량 + 기존 CSS(`.timing-table`·`.finder-*`·`.chart-chip`·`.ing-card` 재사용, `.dg-*` 소량) + 파이썬 빌드·`unittest`, 점검 `check_site.py`(`drug-guide/` 포함).

**Spec:** 2026-10-21 분석 2번(약별 영양제 가이드: 일반의약품 규칙 허브부터, 처방약은 성분명 랜딩 수동 집필). 둘을 한 템플릿으로 합쳐 21편을 모두 만든다.

## Global Constraints

- CLAUDE.md 규칙: 생성 파일은 빌드로만, 점검 실패 0, 푸시 전 `npm run assets`.
- 건강 정보: 영양제 문구는 식약처 인정 범위(사전 `mfdsFunction`)만 인용하고, 약 설명은 '흡수·간격·검사·상담' 같은 사실 관계와 널리 알려진 상호작용 안내에 한정한다. 질병 치료·예방·완치 표현, 근거 없는 수치, 약을 줄이거나 끊으라는 식의 표현은 쓰지 않으며 모든 페이지에 '의사·약사와 상담' 안내를 둔다.
- 의약품에는 구매 링크를 넣지 않는다(온라인 판매 금지). 약 목록은 `drug.html?id=…` 상세와 통합 검색으로만 잇는다.
- 규칙 파일(`drug-pairings.json`)에 성분을 더할 때는 성분 사전의 `drugCautions` 에 이미 적힌 상호작용만 옮긴다(id 는 빌드가 검증).
- 한 검색 의도에 한 페이지: 제목 틀 "`{약}`과 영양제 궁합: …". 대상별 가이드와 제목이 겹치지 않게 한다.
- 응답·커밋·주석·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 규칙 id 와 수동 본문이 1:1 이 아니거나, related 가이드 slug·성분 id 가 틀리면 빌드가 실패해야 한다. → `validate_drug_guides`·`validate_drug_pairings`.
2. 약 목록 판정은 `data.js` 의 `drugPairingFor` 와 같아야 한다(외용제 제외 정규식·사용법 '바릅니다' 검사 포함). → 정규식 원문을 두 파일에서 대조하는 테스트.
3. 처방약 분류(약 0건)에서 페이지가 비지 않아야 한다. → 수동 `drugs` 목록 + 안내 문구, 허브는 '처방약' 묶음으로 분리.
4. 좋은 성분이 없는 분류(타이레놀·카페인 등)도 표가 깨지지 않고 '정리된 조합 없음' 문구를 보여 준다.
5. 새 디렉터리 `drug-guide/` 를 사이트맵·스탬프·PWA·점검·Tailwind 가 모두 포함한다.

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `data/drug-guides.json` (신규, 수동) | 21편의 본문 데이터(규칙 id 와 1:1) |
| `data/drug-pairings.json` (수정) | 스타틴·갑상선·와파린·항생제·골다공증약·메트포르민·이뇨제·레티노이드·MTX·제산제 규칙에 사전 `drugCautions` 근거의 성분 추가, 레티노이드 `oralOnly`, 감기약 비타민C 문구를 식약처 인정 기능 표현으로 교정 |
| `scripts/build_site.py` (수정) | `validate_drug_guides`, `drug_is_external`·`drug_rule_hits`·`load_drugs_detail`, `drug_guide_model`, `render_drug_guide`, `render_drug_guides_hub`, `prepare_drug_guides`, `write_drug_guides`, 사이트맵·스탬프·PWA 열거, 성분 페이지 '약과 함께' 칩, 가이드 허브 안내 |
| `drug-guide/<id>.html`, `drug-guides.html`, `data/drug-guides-index.json` (생성) | 약별 페이지·허브·요약 색인 |
| `assets/js/data.js` (수정) | `drugGuides()` 로더, `drugPairingFor` 가 규칙 `{id,label}` 도 반환, 외용제 판정에 `두피`·사용법 검사 추가 |
| `assets/js/pages/drug.js`, `assets/js/pages/ingredient.js`, `assets/js/layout.js` (수정) | 의약품 상세의 분류 가이드 링크, 성분 상세 '약과 함께' 칩, 푸터 링크 |
| `scripts/check_site.py`, `tailwind.config.cjs`, `assets/css/style.css` (수정) | `drug-guide/` 포함, `.dg-*` |
| `tests/test_build_site.py` (수정) | 검증·모델·정규식 대조·렌더 테스트 |
| `CLAUDE.md`, `README.md`, `docs/PROJECT-STATUS.md` (수정) | 구조·이력·다음 할 일(④ 완료) |

---

### Task 1: 데이터

- [x] `data/drug-guides.json` 21편: udca · nsaid · acetaminophen · antacid · acid-suppressant · laxative · cold · decongestant · caffeine · vitamin-drug (일반의약품) / statin · thyroid · warfarin · antibiotic-chelate · bisphosphonate · metformin · contraceptive · diuretic · retinoid · methotrexate · steroid-oral (처방약 중심).
- [x] `data/drug-pairings.json` 보강: 규칙별 성분 추가(사전 `drugCautions` 근거), `retinoid.oralOnly`, 비타민C 문구 교정.

### Task 2: 빌드

- [x] 검증·모델(규칙 + 사전 + 의약품 상세 조각 판정 + 브랜드 가중치 + 가이드)·렌더(히어로·요약 표·좋은 성분 카드·주의 성분·복용 요령·이 분류의 약·관련 가이드·FAQ, Article+FAQPage+Breadcrumb JSON-LD)·허브(일반의약품/처방약 묶음·복용 간격표·읽는 법·FAQ)·요약 색인·사이트맵·성분 페이지 칩.
- [x] `drug-guide/` 를 `stamp_assets`·`inject_pwa_tags`·`check_site.html_files`·Tailwind content 에 추가.

### Task 3: 스크립트·진입점·문서

- [x] `data.js`(로더·규칙 id·외용제 판정), `drug.js`(가이드 링크), `ingredient.js`(칩), `layout.js`(푸터), 가이드 허브 안내, `.dg-*` CSS.
- [x] CLAUDE.md·README·PROJECT-STATUS(④ 완료).

### Task 4: 빌드·점검·테스트·커밋

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` 실패 0 → `unittest` → 브라우저(허브·일반의약품 페이지·처방약 페이지 데스크톱/모바일, 의약품 상세 링크, 성분 페이지 칩, 콘솔 오류 없음) → 커밋 → `git show --stat` → 푸시.
