# 성분 비교 내부 링크 + 제형·형태 비교 3편(비타민K·홍삼 제형·유산균) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) 성분 비교 31편(성분 대 성분 20 + 제형 11)은 허브·성분 페이지 칩·푸터에서만 들어갈 수 있고 가이드 87편·기능성 허브 31장에는 링크가 없다(10-22 점검: `guide/*.html`·`function/*.html` 의 `compare/` 링크 0건). 가이드·기능성 페이지에 '관련 비교 글' 섹션을 넣어 비교 페이지의 내부 링크를 늘린다. (2) `docs/PROJECT-STATUS.md` 7절 10-③ "표기가 쌓이면 유비퀴놀·메틸코발라민 편 추가"는 신고 제품 표기를 세어 보니 유비퀴놀 1건·메틸코발라민 0건이라 아직 쓸 수 없다. 대신 표기가 충분한 비타민K(K1 필로퀴논 434·K2 메나퀴논 268·표기 없음 64), 홍삼 제형(액상 868·캡슐 220·정 182·분말 107·젤리 84·환 64), 유산균(분말 1,475·캡슐 707·정 275·사균·열처리 97)으로 제형·형태 비교 3편을 더한다(11→14편).

**Architecture:**
- 내부 링크: `build_site.py` 에 `related_compares(core, ids, slug)` 헬퍼 — `core["compares"]`(성분 대 성분 `items` + 제형 `forms`)에서 ① `related` 가이드에 이 페이지 slug 가 있거나 ② 성분 대 성분은 `ids` 가 모두 페이지 성분에 들어 있거나 ③ 제형 비교는 기준 성분이 페이지 성분에 있는 것을 고르고(관련 가이드 명시 → 성분 겹침 수 → 제목 순, 최대 6편) `cmp-card` 카드(허브와 같은 모양)로 `render_guide`(함께 보면 좋은 가이드 앞, 탐색 칩 '비교 글')·`render_function`(관련 가이드 앞)에 넣는다. `core["compares"]` 가 없으면(테스트) 섹션을 빼고 그린다.
- 제형 매칭: `form_compare_model` 이 정규식을 맞추는 문자열에 식약처 신고 제형(`shape`)을 `제형:<값>` 으로 덧붙여(`제품명 | 원재료명 | 제형:액상`) 정규식이 `제형:(액상|겔)` 처럼 제형으로도 나눌 수 있게 한다(기존 11편은 제형 토큰과 무관한 정규식이라 결과가 바뀌지 않음 — 빌드 전후 제품 수 대조).
- 데이터 `data/form-compares.json` 3편:

| slug | id | forms | 근거 |
|---|---|---|---|
| vitamin-k-forms | vitamin-k | K1(필로퀴논) · K2(메나퀴논, MK-7 포함) · 표기 없음(rest) | 인정 기능성은 같음(정상적인 혈액응고·뼈의 구성에 필요, 충분섭취량 65~75㎍) — 유래·라벨 표기·와파린 주의만 비교, 혈관 건강 등 인정되지 않은 효능은 FAQ 에서 구분 |
| red-ginseng-forms | red-ginseng | 농축액·스틱(액상·겔·시럽) · 정·캡슐·환 · 분말·과립 · 젤리·기타(rest) | 지표성분(진세노사이드 Rg1+Rb1+Rg3 합 3~80mg)은 제형과 무관 — 농축액은 '홍삼정'(농축)과 희석 스틱의 당류·첨가물 확인, 정·캡슐은 분말 압축, 젤리·캔디는 당류 |
| probiotics-forms | probiotics | 분말·스틱(분말·과립) · 캡슐 · 정·츄어블(정·환·젤리) · 사균·열처리(이름·원재료명) · 액상·기타(rest) | 고시형 프로바이오틱스 기능성은 생균(1억~100억 CFU)에만, 사균·열처리배양건조물은 원료별 개별인정(면역·배변·콜레스테롤·피부 등, mg 기준 — `materials.json`) |

**Tech Stack:** 파이썬 빌드 + 데이터 JSON. 새 CSS·아이콘 없음(`cmp-card` 재사용, `scale` 아이콘은 번들에 있음).

## Global Constraints

- 식약처 인정 범위 안의 사실 관계만: 비타민K2 '혈관 건강', 사균 '면역' 같은 표현은 인정 원료·문구가 있는 경우에만 그 원료 기준으로 쓰고, 흡수율 수치·가격·우열 단정은 쓰지 않는다.
- 생성 파일은 빌드로만, `check_site.py` 실패 0·경고 0, 푸시 전 `npm run assets`.
- 응답·커밋·주석·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 기존 제형 비교 11편의 형태별 제품 수가 `shape` 토큰 추가 전후로 같아야 한다(정규식이 '제형:' 토큰에 걸리지 않음).
2. 관련 비교 글은 가이드 성분과 무관한 비교를 끌어오지 않아야 한다(성분 대 성분은 ids 전부 포함 조건).
3. `render_guide`·`render_function` 이 `core["compares"]` 없이도(단위 테스트) 그려져야 한다.

---

### Task 1: 코드

- [x] `form_compare_model` 매칭 문자열에 `제형:<shape>`, `related_compares`·`compare_cards_html` 헬퍼, `render_guide`·`render_function` 섹션·탐색 칩, 테스트(가이드·기능성 페이지 링크, 제형 토큰 매칭, 없는 core 처리).

### Task 2: 데이터

- [x] `data/form-compares.json` 3편 + `_meta.note` 에 제형 토큰 설명, CLAUDE.md·README 의 매칭 설명 갱신.

### Task 3: 재생성·점검·문서·커밋

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` 실패 0·경고 0 → `unittest`·`node --test` → 브라우저 확인(가이드·기능성 페이지의 비교 카드, 새 제형 비교 3편 데스크톱·모바일) → PROJECT-STATUS(페이지 표 14편, 이력, 7절 ③ 유비퀴놀·메틸코발라민 보류 사유) → 커밋 → `git show --stat` → 리베이스 → 푸시.
