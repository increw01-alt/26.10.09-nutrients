# 장기 복용 점검 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 오래 먹는 영양제 가운데 근거 있는 '점검 시점'이 있는 성분을, 그 시점이 지나면 내 영양제·오늘 홈에서 위화감 없이 알려 주고 잠시 쉬기·계속 먹기·다른 성분 보기를 고를 수 있게 한다.

**Architecture:** 근거 표는 수동 데이터 `data/longterm.json`(성분 id·종류·주 수·안내 문장·출처)에 두고 빌드가 검증한다. 판정은 순수 모듈 `assets/js/longterm.js`(`check`)가 저장 상태(항목 `addedAt`·`pausedAt`·`ltCheckedAt`)로 계산하고, 화면은 `pages/my.js`(점검 카드·쉬는 중 표시)와 `pages/today.js`(한 줄 안내)가 그린다. '쉬기'는 `store.js` 의 `pauseItem`(시간표·알림에서 빠짐), '다시 먹기'는 `resumeItem`(시작일 갱신), '계속 먹기'는 `markChecked`(다음 점검을 미룸).

**Tech Stack:** Vanilla JS(ES5) + Node 테스트, Python 빌드 검증.

**Spec (요약 — 사용자 결정 2026-10-23):** 복용 기간과 쉬는 시점은 자료에서 찾은 것만 쓰고(알로에 전잎 2주: WHO·EMA 생약 기준·한국소비자원 / 글루코사민·콘드로이친 12주 효과 판단: 영국 NHS 환자 안내 / 비타민 B6·아연·비타민 A·D·철분·칼슘·나이아신·망간·몰리브덴·셀레늄: 고용량 장기 주의가 있어 12주마다 상한(한국인 영양소 섭취기준) 확인 — '12주마다'는 사이트의 점검 주기이지 의학 규칙이 아니므로 문구도 '점검'으로), 문구는 위화감 없이('점검해 보세요', '쉬어 가도 괜찮아요'; '중단하세요' 금지). 다른 영양제 추천은 처방이 아니라 '같은 고민의 다른 성분 보기'(맞춤 추천 페이지 링크).

## Global Constraints
- `CLAUDE.md` 규칙 전부(건강 표현 범위, 빌드·검사, 한국어 커밋). 금칙어: 치료·예방·완치·진단, "중단하세요".
- 기간은 `data/longterm.json` 에 출처(`_meta.sources`)와 함께만 둔다. 출처 없는 기간을 만들지 않는다.
- 쉬는 항목은 시간표·알림·오늘 홈 타임라인에서 빠지고 목록에는 '쉬는 중'으로 남는다. 옮기기 코드에는 쉬는 상태를 담지 않는다(단순화).
- 스키마는 v2 그대로(항목에 선택 필드 `pausedAt`·`ltCheckedAt` 추가, `load()` 가 보존).

## Review Focus
1. 제품(센트룸 등) 안에 든 성분(B6·아연)에도 점검이 뜨되, 함량을 모르므로 '라벨 확인' 문구로만. (Task 3 테스트)
2. 쉬는 항목이 시간표·알림·오늘 홈에서 빠지고, '다시 먹기' 뒤 시작일이 갱신되어 바로 다시 점검이 뜨지 않는다. (Task 2·3 테스트)
3. '계속 먹기'를 누르면 같은 항목이 `weeks` 뒤에 다시 뜬다. (Task 3 테스트)
4. 알로에 **겔** 제품에는 전잎 기준이 붙지 않도록 문구가 '전잎 제품이라면'으로 조건을 단다. (Task 1 데이터)
5. 성분 사전에서 사라진 id 가 데이터에 있으면 빌드가 실패한다. (Task 1 테스트)

---

### Task 1: 근거 데이터 + 빌드 검증
**Files:** Create `data/longterm.json`; Modify `scripts/build_site.py`(`validate_longterm`, `main`), `assets/js/data.js`(`longterm()` 로더); Test `tests/test_build_site.py`.
- `validate_longterm(data, valid_ids)`: `items` 비어 있지 않음, 각 `id` 가 사전에 있음, `kind ∈ {limit, review, upper}`, `weeks` 1~52 정수, `note` 20~200자·금칙어 없음, `source` 가 `_meta.sources[].id` 에 있음. 위반 시 `ValueError`.
- [ ] 테스트 → 실패 확인 → 구현 → 통과 → 커밋

### Task 2: `store.js` 쉬기·다시 먹기·점검 기록
**Produces:** `Store.pauseItem(state, id, nowIso)`, `Store.resumeItem(state, id, nowIso)`(`pausedAt` 삭제 + `addedAt`=now + `ltCheckedAt` 삭제), `Store.markChecked(state, id, nowIso)`, `Store.isPaused(item)`, `entries(state)` 와 `ingredientIds(state)` 는 쉬는 항목 제외, `load()` 가 두 필드(ISO 문자열) 보존.
- [ ] 테스트 → 실패 → 구현 → 통과 → 커밋

### Task 3: `longterm.js` 판정
**Produces:** `LongTerm.check(state, rules, core, now) → [{ key, name, viaProduct?: 제품명, id: 성분id, kind, weeks, elapsedWeeks, note, sourceId, sourceTitle }]` — 항목마다 시작 = `ltCheckedAt || addedAt`, 경과 주 ≥ `weeks` 면 포함, 쉬는 항목 제외, 제품은 `ings` 의 각 성분을 검사(같은 성분이 따로도 있으면 한 번만). `LongTerm.weeksBetween(a, b)`.
- [ ] 테스트(`tests/longterm.test.mjs`) → 실패 → 구현 → 통과 → 커밋

### Task 4: 화면
`pages/my.js` `sectionLongTerm`(점검 카드: "{이름}을(를) {n}주째 먹고 있어요" + 안내 + 출처 + 버튼 [잠시 쉬기]·[계속 먹기 · {weeks}주 뒤 다시 점검]·[다른 성분 보기 → recommend.html]), 목록의 쉬는 항목(칩 '쉬는 중 · n일째', 버튼 '다시 먹기', 시간대 선택 비활성), `pages/today.js` 안내 한 줄(점검 n건 → 내 영양제), `help.html` 10항목, CSS. 브라우저 확인.
- [ ] 구현 → 브라우저 확인(?app=1) → 커밋

### Task 5: 문서·빌드·배포
CLAUDE.md·PROJECT-STATUS, `npm run assets` → build → check → 커밋·푸시.
