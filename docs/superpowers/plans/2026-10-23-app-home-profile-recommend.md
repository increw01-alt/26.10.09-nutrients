# 앱 홈·제품 추가·내 정보 맞춤 추천·사용 설명 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 앱이 '오늘' 홈으로 열리고, 내 영양제에 제품을 한 줄로 넣으면 추가 직후 궁합·배정 시간대 요약 창이 뜨며, 내 정보로 근거 칩이 붙은 맞춤 추천을 받고, 사용 설명 페이지가 있다.

**Architecture:** 새 로직은 전부 순수 모듈(`store.js` v2, `schedule.js` 제품 묶음, `addsummary.js`, `today.js`, `finder.js reasons`)에 두고 Node 로 테스트한다. 화면은 기존 패턴대로 `pages/*.js` 가 상태를 통째로 다시 그린다. 앱 시작 처리(복원·알림 정리·동기화)는 `app.js` 로 올려 모든 앱 화면에서 돈다. 새 정적 페이지 셋(`today.html`·`recommend.html`·`help.html`)은 `my.html` 틀을 따른다.

**Tech Stack:** 정적 HTML + Tailwind 정적 빌드 + Vanilla JS(ES5, IIFE + CommonJS 내보내기), Node 테스트(`node --test`), Python 빌드·테스트(`unittest`), Capacitor 설정 파일.

**Spec:** `docs/superpowers/specs/2026-10-23-app-home-profile-recommend-design.md`

## Global Constraints

- `CLAUDE.md` 규칙: 생성 파일은 직접 고치지 않는다. JS·CSS·HTML 을 고친 뒤 `python scripts/build_site.py`(`?v=` 스탬프·sw.js) → `python scripts/check_site.py`. 새 Tailwind 클래스·lucide 아이콘을 쓰면 `npm run assets` 뒤 다시 빌드. 커밋 메시지는 한국어, 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- 금칙어·표현: "AI가 분석", "AI 진단", "AI가 당신의 건강 상태를", 질병 치료·예방·완치. 허용 배지: "AI로 정리한 식약처 인정 기능성 데이터 기반". 추천·팁 문장은 성분 사전(`mfdsFunction`·`benefits`·`timing.note`·`dosage`·`whoFor`)·가이드 색인·궁합 데이터의 기존 문구만 조합한다.
- 내 정보(연령대·성별·고민·생활·약)는 localStorage `yj.my.v1` 와 옮기기 코드에만 담는다. 주소 쿼리·분석 이벤트에 넣지 않는다.
- 저장 키 `yj.my.v1` 유지, 스키마 `v: 2`; 옮기기 코드 접두사 `YJ1-` 유지, 페이로드 `v: 2`, v1 코드도 읽힌다.
- 한 제품의 성분은 한 시간대에만 배정된다(제품째 이동).
- `slotOn`·`weekends` 는 알림에만 관여한다(복용 여부·기록·홈 타임라인의 모집단은 시간표의 모든 시간대).
- 홈의 궁합 체크 바로가기는 `compat.js` 상한 8개까지만 담는다(따로 먹는 성분 → 제품 안 성분 순).
- 쿠팡: 앱에서 `SITE.appShopping` 이 꺼져 있으면 구매 자리에 '제품 찾기'(`products.html?ingredient=<id>`). 쇼핑 버튼이 보이면 `Affiliate.disclosure()` 고지도 함께.
- 시간대 상수 `SLOT_ORDER`·`SLOT_META`·`DEFAULT_TIMES` 는 `store.js`·`schedule.js`·`build_site.py` 가 같아야 한다(기존 테스트가 대조).
- 앱 시작 주소는 `https://xn--og5b1hx9c.kr/today`(`app/capacitor.config.json` + `app/android/app/src/main/assets/capacitor.config.json` 둘 다). `allowNavigation` 은 그대로.

## Review Focus

1. 성분이 연결되지 않은 제품(`ings: []`)을 추가·시간표·요약 창·홈·알림에 넣어도 예외 없이 "성분 정보 없음"으로 처리된다. (Task 2·3 테스트)
2. 옛 v1 옮기기 코드와, 제품이 든 v2 코드를 제품 색인이 없거나 색인에 없는 제품으로 가져올 때 — 성분 없이 넣고 안내한다. (Task 1 테스트, Task 4 브라우저)
3. 오늘 시간대를 다 먹었거나 전부 지났거나 하나뿐인 경우의 '다음 복용', 그리고 기록을 아직 켜지 않은 사용자(`logEnabled` null)에게 '먹었어요' 대신 '기록 켜기'. (Task 6 테스트)
4. 제품 안 성분이 따로 먹는 성분과 같거나 두 제품에 같은 성분 → '겹쳐요'가 '좋아요'보다 앞선다. (Task 3 테스트)
5. 재설치 뒤 웹뷰 저장소가 비어 있을 때 홈이 복원 전에 그려져 '저장한 영양제 없음'으로 뜨지 않는다. (Task 5 테스트: `restoreIfEmpty` 가 render 전에 끝남)

---

### Task 1: `store.js` 스키마 v2 — 제품 항목·내 정보·옮기기 코드

**Files:**
- Modify: `assets/js/store.js` (머리 주석의 스키마 설명, `empty`·`load`·`addItems`·`pruneUnknown`·`exportCode`·`importCode`·`merge`·내보내기 목록)
- Test: `tests/store.test.mjs` (끝에 추가)

**Interfaces:**
- Consumes: 없음(기존 `Store`).
- Produces:
  - 상태 `{ v: 2, items: [IngItem | ProductItem], settings, log, profile? }`. `IngItem = { id, addedAt, slot? }`, `ProductItem = { id: "p:<제품id>", name: string, ings: string[], addedAt, slot? }`, `profile = { age: string[], sex: string[], concern: string[], life: string[], meds: string[], updatedAt: ISO }`(답한 질문만 키가 있음).
  - `Store.isProduct(id: string): boolean` — `"p:"` 로 시작.
  - `Store.addItems(state, entries: Array<string | { id: string, name: string, ings?: string[] }>) → { state, added: string[] }` (중복은 id 기준, 제품 객체는 `isProduct(id)` 일 때만).
  - `Store.entries(state) → Array<string | { id, name, ings }>` — `Schedule.build` 에 그대로 넘기는 꼴.
  - `Store.ingredientIds(state) → string[]` — 따로 먹는 성분 id 먼저, 그다음 제품 안 성분, 중복 제거.
  - `Store.setProfile(state, profile, finderData) → state` — `finderData.questions`(`id`·`type`·`max`·`options[].id`) 로 검증: 모르는 질문·옵션 제거, `single` 은 1개, `max` 초과 자름, `have` 질문은 무시, 아무것도 안 남으면 `profile` 키 삭제. `updatedAt` 은 `new Date().toISOString()`.
  - `Store.profile(state) → profile | null`.
  - `exportCode` 페이로드 `{ v: 2, items: [[id, slot|0] | ["p:<id>", slot|0, name]], times, on, opts, profile? }`(profile 은 `updatedAt` 제외).
  - `importCode(text) → { items: [{ id, slot, name? }], times, slotOn, opts, profile: object|null } | null` — `v: 1` 과 `v: 2` 둘 다.
  - `merge(state, payload, mode, byId, opts?) → { state, added, skipped }` — `opts.productIngs: { "p:<id>": string[] }` 로 제품 성분을 채우고, 없으면 `ings: []`. 제품은 `byId` 검사 대상이 아니다(건너뛰지 않음). `payload.profile` 이 있으면 `setProfile` 과 같은 검증 없이 저장하되 모양(문자열 배열)만 맞춘다 — `opts.finderData` 가 있으면 `setProfile` 로 검증.
  - `pruneUnknown(state, byId)` — 성분 항목은 지금처럼 제거, 제품 항목은 `ings` 중 모르는 id 만 빼고 유지(`removed` 에는 성분 항목 id 만).
  - `load()` — `data.v` 가 1 또는 2 면 읽는다. 제품 항목은 `name` 이 문자열이고 `ings` 가 배열일 때만, `ings` 는 문자열만 남긴다. `profile` 은 값이 문자열 배열인 키만 남기고 `updatedAt` 은 문자열이면 유지; 남는 키가 없으면 `profile` 을 두지 않는다.

- [ ] **Step 1: 실패하는 테스트 쓰기** — `tests/store.test.mjs` 끝에:

```js
// ---- 스키마 v2: 제품 항목·내 정보·옮기기 코드 (10-23) ----
const FD = { questions: [{ id: "age", type: "single", options: [{ id: "40s" }, { id: "30s" }] }, { id: "concern", type: "multi", max: 3, options: [{ id: "eye" }, { id: "fatigue" }, { id: "sleep" }, { id: "skin" }] }, { id: "have", type: "ingredients" }] };
const P = { id: "p:1", name: "센트룸 맨", ings: ["vitamin-d", "zinc"] };
test("empty: v2", () => assert.equal(S.empty().v, 2));
test("addItems: 성분 id 와 제품 객체를 함께 받고 제품은 id·name·ings 로 저장", () => {
  const r = S.addItems(S.empty(), ["magnesium", P, "magnesium", { id: "x", name: "no" }]);
  assert.deepEqual(r.added, ["magnesium", "p:1"]);
  const p = r.state.items[1]; assert.equal(p.name, "센트룸 맨"); assert.deepEqual(p.ings, ["vitamin-d", "zinc"]); assert.ok(p.addedAt);
});
test("isProduct·entries·ingredientIds", () => {
  const s = S.addItems(S.empty(), ["magnesium", P, "zinc"]).state;
  assert.equal(S.isProduct("p:1"), true); assert.equal(S.isProduct("zinc"), false);
  assert.deepEqual(S.entries(s), ["magnesium", { id: "p:1", name: "센트룸 맨", ings: ["vitamin-d", "zinc"] }, "zinc"]);
  assert.deepEqual(S.ingredientIds(s), ["magnesium", "zinc", "vitamin-d"]);
});
test("load: v1 저장본을 그대로 읽고 v2 로 올린다", () => {
  const raw = JSON.stringify({ v: 1, items: [{ id: "magnesium", addedAt: "2026-10-01T00:00:00.000Z" }], settings: {}, log: {} });
  const s = S.load({ getItem: () => raw }); assert.equal(s.v, 2); assert.equal(s.items[0].id, "magnesium");
});
test("load: 제품 항목은 name·ings 가 맞을 때만, ings 는 문자열만", () => {
  const raw = JSON.stringify({ v: 2, items: [{ id: "p:1", name: "센트룸 맨", ings: ["zinc", 3] }, { id: "p:2", ings: [] }, { id: "p:3", name: "x" }], settings: {}, log: {} });
  const s = S.load({ getItem: () => raw }); assert.deepEqual(s.items.map(i => i.id), ["p:1"]); assert.deepEqual(s.items[0].ings, ["zinc"]);
});
test("setProfile: 질문·옵션 검증, single 1개, max 초과 자름, have 무시, 비면 삭제", () => {
  let s = S.setProfile(S.empty(), { age: ["40s", "30s"], concern: ["eye", "zzz", "fatigue", "sleep", "skin"], have: ["x"], bogus: ["1"] }, FD);
  assert.deepEqual(s.profile.age, ["40s"]); assert.deepEqual(s.profile.concern, ["eye", "fatigue", "sleep"]); assert.equal("have" in s.profile, false); assert.ok(s.profile.updatedAt);
  assert.deepEqual(S.profile(s).age, ["40s"]);
  s = S.setProfile(s, { age: ["zzz"] }, FD); assert.equal(S.profile(s), null); assert.equal("profile" in s, false);
});
test("load: profile 은 문자열 배열 값만 남긴다", () => {
  const raw = JSON.stringify({ v: 2, items: [], settings: {}, log: {}, profile: { age: ["40s"], concern: "eye", life: [1], updatedAt: "2026-10-23T00:00:00.000Z" } });
  assert.deepEqual(S.load({ getItem: () => raw }).profile, { age: ["40s"], updatedAt: "2026-10-23T00:00:00.000Z" });
});
test("exportCode ↔ importCode v2: 제품은 id·slot·name 만, profile 은 updatedAt 빼고", () => {
  let s = S.addItems(S.empty(), ["magnesium", P]).state; s = S.setSlot(s, "p:1", "evening_after"); s = S.setProfile(s, { age: ["40s"] }, FD);
  const code = S.exportCode(s); assert.ok(code.startsWith("YJ1-")); assert.equal(code.indexOf("zinc"), -1);
  const p = S.importCode(code);
  assert.deepEqual(p.items, [{ id: "magnesium", slot: null }, { id: "p:1", slot: "evening_after", name: "센트룸 맨" }]);
  assert.deepEqual(p.profile, { age: ["40s"] });
});
test("importCode: v1 코드도 읽는다(profile null)", () => {
  const v1 = "YJ1-" + Buffer.from(JSON.stringify({ v: 1, items: [["magnesium", 0]], times: {}, on: {}, opts: {} })).toString("base64url");
  const p = S.importCode(v1); assert.deepEqual(p.items, [{ id: "magnesium", slot: null }]); assert.equal(p.profile, null);
});
test("merge: 제품은 productIngs 로 성분을 채우고 없으면 빈 배열, 사전 검사 대상이 아니다", () => {
  const byId = { magnesium: {}, zinc: {} };
  const payload = { items: [{ id: "p:1", slot: null, name: "센트룸 맨" }, { id: "p:9", slot: "bedtime", name: "모름" }, { id: "nope", slot: null }], times: {}, slotOn: {}, opts: {}, profile: { age: ["40s"] } };
  const r = S.merge(S.empty(), payload, "merge", byId, { productIngs: { "p:1": ["zinc"] }, finderData: FD });
  assert.deepEqual(r.added, ["p:1", "p:9"]); assert.deepEqual(r.skipped, ["nope"]);
  assert.deepEqual(r.state.items[0].ings, ["zinc"]); assert.deepEqual(r.state.items[1].ings, []); assert.equal(r.state.items[1].slot, "bedtime");
  assert.deepEqual(r.state.profile.age, ["40s"]);
});
test("pruneUnknown: 제품은 남기고 안의 모르는 성분만 뺀다", () => {
  const s = S.addItems(S.empty(), [{ id: "p:1", name: "x", ings: ["zinc", "gone"] }, "gone"]).state;
  const r = S.pruneUnknown(s, { zinc: {} });
  assert.deepEqual(r.removed, ["gone"]); assert.deepEqual(r.state.items.map(i => i.id), ["p:1"]); assert.deepEqual(r.state.items[0].ings, ["zinc"]);
});
```

- [ ] **Step 2: 실패 확인** — Run: `node --test tests/store.test.mjs` — Expected: 위 테스트가 FAIL(`S.isProduct is not a function`, `v` 1≠2 등), 기존 테스트는 PASS. 기존 테스트 중 `empty: 스키마 v1`·`exportCode` 왕복이 `v` 값으로 깨지면 그 기대값을 2 로 고친다(동작 변경이 아니라 버전 표기).

- [ ] **Step 3: 구현** — `store.js` 에 `isProduct`, `entries`, `ingredientIds`, `setProfile`, `profile` 를 더하고 `empty/load/addItems/pruneUnknown/exportCode/importCode/merge` 를 Interfaces 대로 바꾼다. 머리 주석의 스키마 설명을 v2 로 고친다. `load` 의 `data.v !== 1` 검사는 `[1, 2].indexOf(data.v) < 0` 로.

- [ ] **Step 4: 통과 확인** — Run: `node --test tests/store.test.mjs tests/reminders.test.mjs tests/finder.test.mjs` — Expected: 전부 PASS.

- [ ] **Step 5: 커밋** — `git add assets/js/store.js tests/store.test.mjs && git commit -m "feat(store): 스키마 v2 — 제품 항목(p:id·name·ings)·내 정보 profile·옮기기 코드 v2(v1 호환)"`

---

### Task 2: `schedule.js` 제품 묶음 배정 + `resolvePair` 주입

**Files:**
- Modify: `assets/js/schedule.js`
- Modify: `assets/js/data.js:205` (`shortName` 이 제품 객체도 처리 — 이미 `it.name` 을 쓰므로 변경 없음을 확인만)
- Test: `tests/schedule.test.mjs` (신설), `tests/reminders.test.mjs` (끝에 1건)

**Interfaces:**
- Consumes: `Store.entries(state)` 의 꼴(Task 1).
- Produces:
  - `Schedule.build(entries, core, overrides, opts?) → { slots, assign, notes }`. `entries` 원소는 성분 id 문자열 또는 `{ id: "p:…", name, ings: string[] }`. `opts.resolvePair(core, a, b)` 가 있으면 그것을, 없으면 `window.Data.resolvePair` 를 쓴다. `slots[].items` 원소는 성분이면 `core.byId[id]`, 제품이면 `{ id, name, kind: "product", ings: [core.byId[...]…](모르는 id 제외) }`. `assign` 키는 성분 id 또는 `"p:…"`. `overrides` 키도 같다.
  - `Schedule.productSlot(ings: string[], core) → slot` — 성분들의 `timing.slot` 최빈값, 동률이면 `morning_after`, 성분이 없으면 `morning_after`.
  - 제품 대체 시간대: `["morning_after", "evening_after", "lunch_after"]` 에서 기본값을 뺀 순서.
  - 충돌: 두 항목의 성분 쌍 가운데 하나라도 `separateHours ≥ 1` 이면 충돌. 같은 제품 안 성분끼리는 검사하지 않는다. 메모 문장은 기존 꼴을 쓰되 제품은 `name` 으로.

- [ ] **Step 1: 실패하는 테스트 쓰기** — `tests/schedule.test.mjs`:

```js
// 복용 시간표(assets/js/schedule.js) 테스트 — resolvePair 는 가짜로 주입. 실행: node --test tests/schedule.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const Sch = createRequire(import.meta.url)("../assets/js/schedule.js");
const ing = (id, slot, alt) => ({ id, name: id, timing: { slot, altSlots: alt || [] } });
const core = { byId: { calcium: ing("calcium", "evening_after", ["lunch_after"]), magnesium: ing("magnesium", "bedtime", ["evening_after"]), iron: ing("iron", "morning_empty", ["before_meal"]), "vitamin-d": ing("vitamin-d", "morning_after"), zinc: ing("zinc", "morning_after") } };
const SEP = { "calcium|iron": 2, "calcium|zinc": 2 };
const resolvePair = (c, a, b) => { const k = [a, b].sort().join("|"); return SEP[k] ? { type: "caution", separateHours: SEP[k] } : { type: "neutral" }; };
const multi = { id: "p:1", name: "센트룸 맨", ings: ["vitamin-d", "zinc", "calcium"] };

test("productSlot: 최빈 시간대, 동률·빈 목록은 아침 식후", () => {
  assert.equal(Sch.productSlot(["vitamin-d", "zinc", "calcium"], core), "morning_after");
  assert.equal(Sch.productSlot(["calcium", "magnesium"], core), "morning_after");
  assert.equal(Sch.productSlot([], core), "morning_after");
});
test("build: 제품은 한 항목으로 한 시간대에, items 는 kind product 와 성분 객체 목록", () => {
  const r = Sch.build(["magnesium", multi], core, {}, { resolvePair });
  assert.equal(r.assign["p:1"], "morning_after"); assert.equal(r.assign.magnesium, "bedtime");
  const slot = r.slots.find(s => s.key === "morning_after"); assert.equal(slot.items.length, 1);
  assert.equal(slot.items[0].kind, "product"); assert.equal(slot.items[0].name, "센트룸 맨"); assert.deepEqual(slot.items[0].ings.map(i => i.id), ["vitamin-d", "zinc", "calcium"]);
});
test("build: 같은 제품 안 성분끼리(칼슘·아연)는 충돌이 아니다", () => {
  const r = Sch.build([multi], core, {}, { resolvePair }); assert.deepEqual(r.notes, []);
});
test("build: 제품 안 성분이 다른 항목과 간격이 필요하면 제품째 옮기고 메모에 제품명", () => {
  const r = Sch.build(["zinc", { id: "p:2", name: "칼슘제", ings: ["calcium"] }], core, { }, { resolvePair });
  // 칼슘제 기본은 저녁 식후, 아연은 아침 식후 → 충돌 없음. 아연을 저녁으로 고정하면 칼슘제가 통째로 옮겨진다
  const r2 = Sch.build(["zinc", { id: "p:2", name: "칼슘제", ings: ["calcium"] }], core, { zinc: "evening_after" }, { resolvePair });
  assert.equal(r.assign["p:2"], "evening_after"); assert.notEqual(r2.assign["p:2"], "evening_after");
  assert.ok(r2.notes.some(n => n.indexOf("칼슘제") >= 0));
});
test("build: 성분 정보 없는 제품(ings 빈 배열)도 아침 식후에 들어가고 예외 없음", () => {
  const r = Sch.build([{ id: "p:3", name: "이름만", ings: [] }], core, {}, { resolvePair });
  assert.equal(r.assign["p:3"], "morning_after"); assert.deepEqual(r.slots[0].items[0].ings, []);
});
test("build: 모르는 성분 id 는 건너뛴다(기존 동작 유지)", () => {
  const r = Sch.build(["nope", "magnesium"], core, {}, { resolvePair }); assert.deepEqual(Object.keys(r.assign), ["magnesium"]);
});
```

`tests/reminders.test.mjs` 끝에:

```js
test("plan: 제품 항목은 제품명으로 알림 본문에 들어간다", () => {
  const sch = { slots: [{ key: "morning_after", items: [{ id: "p:1", name: "센트룸 맨", kind: "product", ings: [] }, core.byId["vitamin-d"]] }] };
  const p = R.plan(on(), sch, { shortName: (it) => String(it.name).replace(/\s*\(.*$/, "") });
  assert.equal(p[0].body, "센트룸 맨 · 비타민 D");
});
```

- [ ] **Step 2: 실패 확인** — Run: `node --test tests/schedule.test.mjs tests/reminders.test.mjs` — Expected: schedule 테스트가 모듈 로드 단계(`window is not defined` 또는 `productSlot` 없음)에서 FAIL, reminders 새 테스트는 PASS 여도 무방(이미 `it.name` 을 쓰면). PASS 면 그대로 둔다(회귀 방지용).

- [ ] **Step 3: 구현** — `schedule.js` 에 CommonJS 내보내기(`if (typeof module !== "undefined") module.exports = Schedule`)와 `typeof window` 보호를 넣고, `build(entries, core, overrides, opts)` 로 바꾼다. 내부적으로 항목을 `{ key, ings: [id…], name, kind }` 로 정규화한 뒤 충돌 검사는 항목 쌍의 성분 쌍 전체를 돈다. 기존 호출처(`pages/my.js`·`app.js requestSync`·`pages/finder.js`·`pages/compat.js` 등 `Schedule.build(` 를 쓰는 4곳)는 문자열 배열을 그대로 넘겨도 동작해야 한다(성분 id 문자열은 그대로 지원).

- [ ] **Step 4: 통과 확인** — Run: `node --test tests/schedule.test.mjs tests/reminders.test.mjs tests/store.test.mjs` — Expected: 전부 PASS.

- [ ] **Step 5: 커밋** — `git add assets/js/schedule.js tests/schedule.test.mjs tests/reminders.test.mjs && git commit -m "feat(schedule): 제품 묶음 배정(제품째 한 시간대·같은 제품 안 성분은 비충돌)·resolvePair 주입·Node 테스트"`

---

### Task 3: `addsummary.js` — 추가 직후 요약(배정 이유·궁합 분류)

**Files:**
- Create: `assets/js/addsummary.js`
- Test: `tests/addsummary.test.mjs`

**Interfaces:**
- Consumes: `Store.entries(state)`(Task 1), `Schedule.build` 결과(Task 2), `core.byId[id].timing/dosage/name`, `resolvePair(core, a, b) → { type: "synergy"|"caution"|"avoid"|"neutral", separateHours?, title?, tip? }`.
- Produces: `AddSummary.build(core, entries, key, sched, opts) → Summary`
  - `opts = { resolvePair, times: { slot: "HH:MM" }, slotLabel: { slot: label } }`.
  - `Summary = { title, subtitle, slotKey, slotLabel, time, reason, pairs: Pair[], okNames: string[] }`.
  - `title` = "{이름}을(를) 추가했어요"(조사는 `opts.josa(name, "을를")` 가 있으면 그것, 없으면 "{이름}을(를)"); `subtitle` = 제품이면 "제품 · 한 알에 n가지", 성분 정보 없으면 "제품 · 성분 정보 없음", 성분이면 "".
  - `reason`: `sched.notes` 중 이 항목 이름이 들어간 첫 문장 → 없으면 성분은 `timing.note` 가 있으면 그것, 없으면 "{timing.label} 권장" → 제품은 "한 알에 든 성분은 나누지 않고 제품째로 배정해요. {기본 시간대 라벨} 권장이 가장 많아요."(성분 없으면 "한 알에 든 성분은 나누지 않고 제품째로 배정해요.").
  - `Pair = { key, name, kind: "dup"|"care"|"good"|"ok", title, detail }`. 분류 우선순위 dup > care > good > ok. `dup`: 새 항목과 상대가 같은 성분을 가짐(성분 vs 제품, 제품 vs 제품; 성분 vs 성분은 id 가 다르므로 해당 없음) — `title` "{상대} — 같은 성분이 겹쳐요", `detail` "{성분명}이(가) 둘 다 들어 있어요" + 그 성분 `dosage.upper` 가 있으면 " · 합쳐서 상한({upper}) 안이면 괜찮아요". `care`: 성분 쌍 중 `caution`/`avoid` — `title` "{상대} — {separateHours}시간 간격" (시간 없으면 "{상대} — 주의"), `detail` 은 쌍의 `title` 또는 `tip`(있는 것), 제품이면 어떤 성분 때문인지 "({a}·{b})" 를 덧붙인다. `good`: `synergy` — "{상대} — 함께 먹으면 좋아요". `ok`: 그 밖. 상대가 성분 정보 없는 제품이면 `kind: "ok"`, `title` "{상대} — 성분 정보 없음".
  - `pairs` 는 dup·care·good 만 담고 ok 는 `okNames` 로 모은다. 순서: dup → care → good.

- [ ] **Step 1: 실패하는 테스트 쓰기** — `tests/addsummary.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const A = createRequire(import.meta.url)("../assets/js/addsummary.js");
const ing = (id, name, slot, extra) => Object.assign({ id, name, timing: { slot, label: slot === "bedtime" ? "취침 전" : "아침 식후", note: id === "magnesium" ? "근육 이완·수면 목적이면 저녁 권장" : "" } }, extra);
const core = { byId: { magnesium: ing("magnesium", "마그네슘", "bedtime"), calcium: ing("calcium", "칼슘", "morning_after"), "vitamin-d": ing("vitamin-d", "비타민 D", "morning_after", { dosage: { upper: "4,000 IU" } }), "omega-3": ing("omega-3", "오메가3", "morning_after") } };
const PAIRS = { "calcium|magnesium": { type: "caution", separateHours: 2, title: "칼슘과 마그네슘은 흡수가 서로 방해돼요" }, "magnesium|vitamin-d": { type: "synergy", title: "마그네슘은 비타민 D 활성화에 관여" } };
const resolvePair = (c, a, b) => PAIRS[[a, b].sort().join("|")] || { type: "neutral" };
const opts = { resolvePair, times: { bedtime: "22:30", morning_after: "08:00" }, slotLabel: { bedtime: "취침 전", morning_after: "아침 식후" } };
const sched = { assign: { magnesium: "bedtime", calcium: "morning_after", "vitamin-d": "morning_after", "omega-3": "morning_after" }, notes: [] };

test("성분 추가: 배정 시간대·이유(timing.note)·궁합 분류와 순서", () => {
  const s = A.build(core, ["vitamin-d", "calcium", "omega-3", "magnesium"], "magnesium", sched, opts);
  assert.equal(s.title, "마그네슘을(를) 추가했어요"); assert.equal(s.subtitle, ""); assert.equal(s.slotKey, "bedtime"); assert.equal(s.slotLabel, "취침 전"); assert.equal(s.time, "22:30");
  assert.equal(s.reason, "근육 이완·수면 목적이면 저녁 권장");
  assert.deepEqual(s.pairs.map(p => p.kind + ":" + p.key), ["care:calcium", "good:vitamin-d"]);
  assert.equal(s.pairs[0].title, "칼슘 — 2시간 간격"); assert.deepEqual(s.okNames, ["오메가3"]);
});
test("이유: 시간표 메모에 이 항목이 옮겨진 기록이 있으면 그 문장", () => {
  const s = A.build(core, ["calcium", "magnesium"], "magnesium", { assign: { calcium: "bedtime", magnesium: "evening_after" }, notes: ["마그네슘은(는) 칼슘과(와) 간격을 두기 위해 저녁 식후(으)로 옮겼습니다."] }, Object.assign({}, opts, { times: { evening_after: "19:00" }, slotLabel: { evening_after: "저녁 식후" } }));
  assert.equal(s.slotLabel, "저녁 식후"); assert.ok(s.reason.indexOf("옮겼습니다") > 0);
});
test("제품 추가: 부제·제품째 배정 이유·겹쳐요(상한 안내)가 좋아요보다 앞", () => {
  const prod = { id: "p:1", name: "센트룸 맨", ings: ["vitamin-d", "magnesium"] };
  const s = A.build(core, ["vitamin-d", prod], "p:1", { assign: { "vitamin-d": "morning_after", "p:1": "morning_after" }, notes: [] }, opts);
  assert.equal(s.subtitle, "제품 · 한 알에 2가지"); assert.ok(s.reason.indexOf("제품째로") >= 0);
  assert.equal(s.pairs[0].kind, "dup"); assert.equal(s.pairs[0].key, "vitamin-d"); assert.ok(s.pairs[0].detail.indexOf("4,000 IU") > 0);
});
test("제품끼리 같은 성분이면 겹쳐요, 제품 안 성분과 상대 성분의 주의는 어떤 성분 때문인지 적는다", () => {
  const a = { id: "p:1", name: "A", ings: ["vitamin-d", "magnesium"] }, b = { id: "p:2", name: "B", ings: ["vitamin-d"] };
  const s = A.build(core, [a, b, "calcium"], "p:1", { assign: { "p:1": "morning_after", "p:2": "morning_after", calcium: "morning_after" }, notes: [] }, opts);
  assert.deepEqual(s.pairs.map(p => p.kind + ":" + p.key), ["dup:p:2", "care:calcium"]);
  assert.ok(s.pairs[1].detail.indexOf("마그네슘") >= 0);
});
test("성분 정보 없는 제품: 부제·ok 로 '성분 정보 없음'", () => {
  const s = A.build(core, [{ id: "p:9", name: "이름만", ings: [] }, "magnesium"], "magnesium", { assign: { "p:9": "morning_after", magnesium: "bedtime" }, notes: [] }, opts);
  assert.deepEqual(s.pairs, []); assert.deepEqual(s.okNames, ["이름만"]);
  const s2 = A.build(core, [{ id: "p:9", name: "이름만", ings: [] }], "p:9", { assign: { "p:9": "morning_after" }, notes: [] }, opts);
  assert.equal(s2.subtitle, "제품 · 성분 정보 없음");
});
```

- [ ] **Step 2: 실패 확인** — Run: `node --test tests/addsummary.test.mjs` — Expected: 모듈을 찾지 못해 FAIL.

- [ ] **Step 3: 구현** — `assets/js/addsummary.js`(IIFE, `window.AddSummary` + `module.exports`) 에 `build` 를 Interfaces 대로. 브라우저에서는 `opts.resolvePair` 가 없으면 `window.Data.resolvePair`, `opts.josa` 가 없으면 `window.Data.josa` 를 쓴다(Node 테스트는 둘 다 없이 돈다).

- [ ] **Step 4: 통과 확인** — Run: `node --test tests/addsummary.test.mjs` — Expected: PASS 5/5.

- [ ] **Step 5: 커밋** — `git add assets/js/addsummary.js tests/addsummary.test.mjs && git commit -m "feat: 추가 직후 요약 모듈(addsummary.js) — 배정 이유·궁합 네 분류(겹쳐요·간격·좋아요·무난)"`

---

### Task 4: 내 영양제 화면 — 제품 검색·추가·요약 창·제품 행·가져오기·내 정보 링크

**Files:**
- Modify: `assets/js/pages/my.js` (검색·`add`·`sectionList`·`schedule()`·가져오기 미리보기·`applyImport`·옮기기 설명·바텀 시트)
- Modify: `my.html` (스크립트 `assets/js/addsummary.js` 추가, `#my-sheet` 자리)
- Modify: `assets/css/style.css` (`.my-sheet*`·제품 행 칩·분류 색)
- Test: 브라우저 확인(Node 테스트는 Task 1~3 이 맡음)

**Interfaces:**
- Consumes: `Store.addItems/entries/ingredientIds/isProduct/merge(opts.productIngs)`, `Schedule.build(entries…)`, `AddSummary.build`, `D.productNames()`·`D.productMatcher(n)`(홈 `loadExtra` 와 같은 방식: `n.i`·`n.c`·`n.p[i] = [제품id, 이름, [성분번호], 제조사번호]`, `n.more`), `D.productUrl`.
- Produces: 화면 동작만.

- [ ] **Step 1: 검색에 제품 합치기** — `searchHits()` 가 `{ kind: "ing", it }` 와 `{ kind: "prod", id, name, maker, ings }` 를 섞어 돌려준다(성분 최대 6, 제품 최대 4). 제품 색인은 검색창에 처음 입력할 때 `D.productNames()` 로 받고(`extra.products`·`prodMatch = D.productMatcher`), `n.more` 가 끝나면 다시 그린다. 제품 행 부제: "제품 · 성분 n가지" + 제조사(있으면). 이미 담긴 제품은 `is-added`. `data-add` 값은 성분은 id, 제품은 `p:<id>`.

- [ ] **Step 2: 추가 + 요약 창** — `add(key)`: 성분이면 `S.addItems(state, [id])`, 제품이면 색인 행에서 `{ id: "p:<id>", name, ings }` 를 만들어 `S.addItems`. 추가되면 `commit` 뒤 `ui.sheet = key` 로 바텀 시트를 연다. `renderSheet()` 는 `AddSummary.build(core, S.entries(state), key, schedule(), { times: state.settings.times, slotLabel: S.SLOT_LABEL })` 결과를 `#my-sheet`(`role="dialog" aria-modal="true" aria-labelledby`)에 그린다: 제목·부제, 배정 카드(라벨·시각·이유), 분류별 줄(`dup` 빨강 `.is-dup`, `care` 주황 `.is-care`, `good` 초록 `.is-good`), `okNames` 가 있으면 "나머지 n개 — 무난해요"(1개면 "{이름} — 무난해요"), 버튼 '시간대 바꾸기'(`data-sheet-slot`)·'확인'(`data-sheet-close`). 열리면 '확인' 버튼에 포커스, 배경 클릭·Esc·확인으로 닫힘(`ui.sheet = null`), '시간대 바꾸기'는 닫은 뒤 그 항목 행의 `select.my-slot` 으로 `scrollIntoView({ block: "center" })` + `focus()`.

- [ ] **Step 3: 목록·시간표의 제품 행** — `sectionList`: 제품 행은 병 그림 대신 제품 아이콘(`package`), 이름 아래 성분 칩(앞 6개 + "+n"), 시간대 선택은 성분과 같은 `select.my-slot`(권장 표시는 `Schedule.productSlot`). `schedule()` 은 `S.entries(state)` 를 넘긴다. `sectionSchedule`·알림 이름·기록은 `slots[].items` 의 `name` 을 그대로 쓴다(제품 객체도 `name` 이 있음). `defaultSlot(it)` 호출처가 제품을 만나면 `Schedule.productSlot(ings)` 를 쓴다.

- [ ] **Step 4: 가져오기** — `previewCard` 가 제품을 "제품 n개" 로 세어 보여 주고, `applyImport` 는 payload 에 제품이 있으면 `D.productNames()`(과거분 `n.more` 까지 기다림) 에서 `p[0] === 제품id` 인 행의 성분 id 목록을 `opts.productIngs` 로 넘긴다. 못 찾은 제품이 있으면 토스트에 " · 성분 정보 없는 제품 n개(다시 검색해 추가하면 채워져요)". `profile` 은 `opts.finderData = D.finder()` 결과로 검증해 들어간다.

- [ ] **Step 5: 내 정보 링크 행** — `sectionList` 위(또는 `sectionAskLog` 아래)에 "내 정보 · 맞춤 추천 ›" 행: `S.profile(state)` 가 있으면 `Finder.summary` 없이 답 개수만 "연령대·고민 등 n개 저장됨", 없으면 "연령대·고민을 저장하면 맞춤 추천을 받아요". 링크는 `recommend.html`.

- [ ] **Step 6: 옮기기 문구** — `sectionTransfer` 부제: "내 영양제 목록(제품 포함)·알림 설정·내 정보를 링크·QR·텍스트 코드로 옮길 수 있어요. 복용 기록은 포함되지 않습니다."

- [ ] **Step 7: 브라우저 확인** — `python -m http.server 8080` 띄우고 `my.html?app=1`(`window.__devPlugins` 가짜 LocalNotifications·Preferences)에서: '센트룸' 검색 → 제품 행 → 추가 → 시트(부제 "제품 · 한 알에 n가지", 배정 아침 식후, 겹침/주의/좋아요 줄) → '시간대 바꾸기' 포커스 이동 → 목록에 제품 행·칩 → 옮기기 코드에 제품 이름만 → 가져오기(바꾸기)로 성분이 채워짐. 모바일 뷰포트 확인 뒤 데스크톱으로 복귀, 끝나면 `?app=0`.
  Expected: 예외 없음(콘솔 에러 0), 위 흐름이 모두 보임.

- [ ] **Step 8: 커밋** — `git add assets/js/pages/my.js my.html assets/css/style.css && git commit -m "feat(my): 제품 검색·추가(한 줄·제품째 배정)·추가 직후 요약 창·가져오기 제품 성분 복원·내 정보 링크"`

---

### Task 5: `app.js` 앱 시작 처리 — 복원·알림 정리·버튼 등록·동기화를 모든 앱 화면으로

**Files:**
- Modify: `assets/js/app.js` (`restoreIfEmpty`, `startup`, `ready()`)
- Modify: `assets/js/pages/my.js` (DOMContentLoaded 의 복원 분기와 `initAppReminders` 의 ensureChannel·clearDelivered·registerActionTypes·열 때 sync 제거 — 알림 동작 처리(`yj:notification-action`·pendingAction)는 남긴다)
- Test: `tests/app.test.mjs`

**Interfaces:**
- Consumes: `AppBridge.restore()`·`plugin()`·`mirror()`, `Store.load/save/KEY`, `Reminders.ensureChannel/clearDelivered/actionTypes/sync`, `Schedule.build`, `Store.entries`.
- Produces:
  - `AppBridge.restoreIfEmpty(env) → Promise<boolean>` — 순수: `env = { hasLocal: () => boolean, restore: () => Promise<string|null>, write: (json) => void }`. `hasLocal()` 이 true 면 false 로 resolve; 아니면 `restore()` 결과가 있으면 `write(json)` 하고 true.
  - `AppBridge.ready()` — 앱 모드(native·dev)에서 런타임 로드 → `restoreIfEmpty({ hasLocal: localStorage 에 Store.KEY 존재, restore: AppBridge.restore, write: localStorage.setItem(Store.KEY, json) })` 까지 끝난 뒤 resolve(`window.Store` 가 없으면 복원은 건너뜀).
  - `AppBridge.startup()` — `ready()` 뒤 LocalNotifications 플러그인이 있으면: `Reminders.ensureChannel(LN)`, `registerActionTypes(Reminders.actionTypes())`, `Reminders.clearDelivered(LN)` + `visibilitychange`(visible) 때 다시, 그리고 `window.Store`·`window.Schedule`·`window.Reminders`·`window.Data` 가 모두 있고 `remindersOn` 이면 `requestSync()` 한 번. `DOMContentLoaded` 에 앱 모드일 때 자동 호출. 같은 페이지에서 두 번 부르지 않게 플래그.
  - `requestSync()` 는 `Schedule.build(window.Store.entries(st), …)` 를 쓴다(Task 1·2).

- [ ] **Step 1: 실패하는 테스트 쓰기** — `tests/app.test.mjs` 끝에:

```js
// ---- 앱 시작: 웹뷰 저장소가 비면 앱 저장소 복제본에서 복원 (10-23) ----
test("restoreIfEmpty: 로컬에 있으면 복원하지 않는다", async () => {
  let wrote = null; const ok = await A.restoreIfEmpty({ hasLocal: () => true, restore: async () => "{}", write: (j) => { wrote = j; } });
  assert.equal(ok, false); assert.equal(wrote, null);
});
test("restoreIfEmpty: 비어 있고 복제본이 있으면 써 넣고 true", async () => {
  let wrote = null; const ok = await A.restoreIfEmpty({ hasLocal: () => false, restore: async () => '{"v":2}', write: (j) => { wrote = j; } });
  assert.equal(ok, true); assert.equal(wrote, '{"v":2}');
});
test("restoreIfEmpty: 복제본이 없거나 restore 가 실패해도 false 로 끝난다", async () => {
  assert.equal(await A.restoreIfEmpty({ hasLocal: () => false, restore: async () => null, write: () => {} }), false);
  assert.equal(await A.restoreIfEmpty({ hasLocal: () => { throw new Error("x"); }, restore: async () => { throw new Error("y"); }, write: () => {} }), false);
});
```

- [ ] **Step 2: 실패 확인** — Run: `node --test tests/app.test.mjs` — Expected: 새 3건 FAIL(`restoreIfEmpty is not a function`).

- [ ] **Step 3: 구현** — `app.js` 에 `restoreIfEmpty`·`startup` 을 더하고 `ready()` 의 흐름을 Interfaces 대로 바꾼다. `my.js` 에서 복원 분기·`initAppReminders` 의 채널·정리·등록·열 때 sync 를 지운다(이제 `app.js` 가 함). `my.js` 는 여전히 `AppBridge.ready()` 를 기다린 뒤 `S.load()` 한다.

- [ ] **Step 4: 통과 확인** — Run: `node --test tests/app.test.mjs tests/reminders.test.mjs` — Expected: PASS. 브라우저: `my.html?app=1` 에서 localStorage 의 `yj.my.v1` 을 지우고 `window.__devPlugins.Preferences.get` 이 복제본을 돌려주게 한 뒤 새로고침 → 목록이 복원되고 콘솔에 `createChannel`·`getDeliveredNotifications` 호출이 보인다.

- [ ] **Step 5: 커밋** — `git add assets/js/app.js assets/js/pages/my.js tests/app.test.mjs && git commit -m "feat(app): 앱 시작 처리(복원·알림창 정리·버튼 등록·동기화)를 app.js 로 — 홈이 /today 가 돼도 모든 앱 화면에서 실행"`

---

### Task 6: `today.js` 순수 로직 + `data/tips.json` + 빌드 검증

**Files:**
- Create: `assets/js/today.js`, `data/tips.json`
- Modify: `scripts/build_site.py` (`validate_tips`, `main` 에서 호출)
- Test: `tests/today.test.mjs`, `tests/test_build_site.py`(1건)

**Interfaces:**
- Consumes: `Store` 상태(`settings.times`·`settings.slotOn`·`log[dateKey]`·`Store.dateKey`), `Schedule.build` 결과, `core.byId`, `resolvePair`(팁의 시너지 문장용, 주입).
- Produces (`window.Today` + CommonJS):
  - `Today.greeting(date) → string` — 05~10시 "좋은 아침이에요", 11~16시 "좋은 오후예요", 17~21시 "좋은 저녁이에요", 그 밖 "늦은 시간이에요".
  - `Today.dateLabel(date) → "10월 23일 목요일"`.
  - `Today.nextDose(state, sched, now) → { status: "none"|"upcoming"|"missed"|"all-done", slot?: key, time?: "HH:MM", names?: string[] }` — 시간표의 모든 시간대가 모집단, 먹음 여부는 `state.log[dateKey(now)].done[slot]`. `upcoming` = 안 먹은 것 중 `times[slot]` 이 `now` 이후인 가장 이른 것, 없으면 `missed` = 안 먹은 것 중 가장 늦은 것, 시간대가 없으면 `none`, 다 먹었으면 `all-done`.
  - `Today.timeline(state, sched, now) → [{ key, label, time, names, done, isNext, reminderOff }]` — 시간대 순서, `isNext` 는 `nextDose` 의 slot, `reminderOff = settings.slotOn[key] === false`.
  - `Today.tip(entries, core, date, general, opts) → { text, source }` — 후보: 성분마다 `timing.note` → "{이름}: {timing.label} — {note}", `dosage.note` → "{이름}: {note}", `benefits[0]` → "{이름}은(는) {benefit}"(`opts.josa` 없으면 "은(는)"), 사용자 성분 쌍의 `synergy` 에 `tip` 이 있으면 그 `tip`. 제품은 `ings` 의 성분으로 푼다. 후보가 없으면 `general`(배열 `[{ text, source }]`)에서. 선택은 `index = (date.getFullYear() * 366 + dayOfYear) % 후보수`. `source` 는 성분 후보면 "내 영양제 기준 · 식약처 인정 기능성 자료", 일반 팁은 항목의 `source`.
  - `data/tips.json`: `{ "_meta": { "updatedAt": "2026-10-23", "note": "…" }, "items": [{ "text": "…", "source": "영양 상식" }, …] }` 12개 안팎. 금칙어 없이, 예: "영양제는 '많이'보다 '맞게'. 먹는 것부터 적어 두면 겹치는 성분이 보여요.", "지용성 비타민(A·D·E·K)은 기름기 있는 식사와 함께 먹으면 흡수에 도움이 돼요.", "같은 성분이 든 제품을 둘 이상 먹고 있다면 라벨의 함량을 합쳐서 확인해 보세요."
  - `build_site.validate_tips(data)` — `items` 가 비어 있지 않고 각 `text` 가 10~120자, 금칙어(`치료`·`예방`·`완치`·`진단`·`AI가 분석`) 없으면 통과, 아니면 `ValueError`.

- [ ] **Step 1: 실패하는 테스트 쓰기** — `tests/today.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const req = createRequire(import.meta.url);
const S = req("../assets/js/store.js"), T = req("../assets/js/today.js");
const ing = (id, name, slot, note) => ({ id, name, timing: { slot, label: "아침 식후", note }, benefits: [name + " 기능"] });
const core = { byId: { "vitamin-d": ing("vitamin-d", "비타민 D", "morning_after", "지방이 있는 식사와 함께"), magnesium: ing("magnesium", "마그네슘", "bedtime", "") } };
const sched = { slots: [{ key: "morning_after", meta: {}, items: [core.byId["vitamin-d"]] }, { key: "bedtime", meta: {}, items: [core.byId.magnesium] }] };
const base = () => S.addItems(S.empty(), ["vitamin-d", "magnesium"]).state;   // times 08:00 / 22:30
const at = (h, m) => new Date(2026, 9, 23, h, m);

test("greeting·dateLabel", () => {
  assert.equal(T.greeting(at(7, 0)), "좋은 아침이에요"); assert.equal(T.greeting(at(13, 0)), "좋은 오후예요"); assert.equal(T.greeting(at(19, 0)), "좋은 저녁이에요"); assert.equal(T.greeting(at(23, 30)), "늦은 시간이에요");
  assert.equal(T.dateLabel(at(9, 0)), "10월 23일 금요일");
});
test("nextDose: 다가오는 것 → 놓친 것 → 다 챙김 → 없음", () => {
  assert.deepEqual(T.nextDose(base(), sched, at(7, 0)), { status: "upcoming", slot: "morning_after", time: "08:00", names: ["비타민 D"] });
  assert.equal(T.nextDose(base(), sched, at(23, 0)).status, "missed"); assert.equal(T.nextDose(base(), sched, at(23, 0)).slot, "bedtime");
  let s = S.markDue(base(), "2026-10-23", ["morning_after", "bedtime"]); s = S.toggleDone(s, "2026-10-23", "morning_after", true);
  assert.equal(T.nextDose(s, sched, at(9, 0)).slot, "bedtime");
  s = S.toggleDone(s, "2026-10-23", "bedtime", true); assert.equal(T.nextDose(s, sched, at(9, 0)).status, "all-done");
  assert.equal(T.nextDose(S.empty(), { slots: [] }, at(9, 0)).status, "none");
});
test("timeline: 순서·done·isNext·알림 꺼짐 표시(모집단은 모든 시간대)", () => {
  let s = S.setSlotOn(base(), "bedtime", false); s = S.markDue(s, "2026-10-23", ["morning_after", "bedtime"]); s = S.toggleDone(s, "2026-10-23", "morning_after", true);
  const t = T.timeline(s, sched, at(9, 0));
  assert.deepEqual(t.map(r => r.key), ["morning_after", "bedtime"]); assert.equal(t[0].done, true); assert.equal(t[1].isNext, true); assert.equal(t[1].reminderOff, true); assert.equal(t[1].time, "22:30");
});
test("tip: 내 성분에서 날짜별로 결정적으로 고르고, 성분이 없으면 일반 팁", () => {
  const general = [{ text: "일반 하나", source: "영양 상식" }, { text: "일반 둘", source: "영양 상식" }];
  const a = T.tip(["vitamin-d", "magnesium"], core, at(9, 0), general, {}), b = T.tip(["vitamin-d", "magnesium"], core, at(21, 0), general, {});
  assert.deepEqual(a, b); assert.equal(a.source, "내 영양제 기준 · 식약처 인정 기능성 자료"); assert.ok(a.text.length > 5);
  assert.equal(T.tip([], core, at(9, 0), general, {}).source, "영양 상식");
  assert.notEqual(T.tip([], core, new Date(2026, 9, 24), general, {}).text, T.tip([], core, new Date(2026, 9, 23), general, {}).text);
});
test("tip: 제품 항목은 안의 성분으로 푼다, 성분 정보 없으면 일반 팁", () => {
  const general = [{ text: "일반", source: "영양 상식" }];
  assert.equal(T.tip([{ id: "p:1", name: "x", ings: ["vitamin-d"] }], core, at(9, 0), general, {}).source, "내 영양제 기준 · 식약처 인정 기능성 자료");
  assert.equal(T.tip([{ id: "p:1", name: "x", ings: [] }], core, at(9, 0), general, {}).text, "일반");
});
```

`tests/test_build_site.py` 에 (기존 클래스 패턴대로):

```python
class TipsTests(unittest.TestCase):
    def test_validate_tips_rejects_forbidden_words_and_accepts_data_file(self):
        with self.assertRaises(ValueError):
            B.validate_tips({"items": [{"text": "이 성분은 질병을 치료합니다", "source": "x"}]})
        with self.assertRaises(ValueError):
            B.validate_tips({"items": []})
        data = json.loads((B.ROOT / "data" / "tips.json").read_text(encoding="utf-8"))
        B.validate_tips(data)
        self.assertGreaterEqual(len(data["items"]), 10)
```

- [ ] **Step 2: 실패 확인** — Run: `node --test tests/today.test.mjs` 와 `python -m unittest tests.test_build_site.TipsTests` — Expected: 둘 다 FAIL(모듈·함수 없음).

- [ ] **Step 3: 구현** — `assets/js/today.js`, `data/tips.json`, `build_site.py` 의 `validate_tips` + `main()` 에서 `data/tips.json` 을 읽어 호출(`validate_finder` 가 불리는 자리 옆).

- [ ] **Step 4: 통과 확인** — Run: `node --test tests/today.test.mjs` → PASS 5/5; `python -m unittest tests.test_build_site` → OK.

- [ ] **Step 5: 커밋** — `git add assets/js/today.js data/tips.json scripts/build_site.py tests/today.test.mjs tests/test_build_site.py && git commit -m "feat: 오늘 홈 로직(today.js — 인사·다음 복용·타임라인·오늘의 한 줄) + 일반 팁 데이터·금칙어 검증"`

---

### Task 7: `today.html` 홈 화면·탭 바·앱 시작 주소

**Files:**
- Create: `today.html`, `assets/js/pages/today.js`
- Modify: `assets/js/layout.js:60-70`(탭 바), `assets/js/app.js`(홈 키 매핑 주석), `assets/css/style.css`(`.today-*`), `scripts/build_site.py:81`(`PRECACHE_EXTRA` 에 `today.html`), `app/capacitor.config.json`, `app/android/app/src/main/assets/capacitor.config.json`, `app/www/index.html`(문구에 '내 영양제'가 있으면 '홈')
- Test: `tests/test_ios_project.py`(server.url), `tests/test_build_site.py`(precache)

**Interfaces:**
- Consumes: `Today.*`(Task 6), `Store`(entries·markDue·toggleDone·dateKey·profile), `Schedule.build`, `D.core()`·`D.tips()`(새 로더: `load("tips")`), `AppBridge.ready()/startup()`(Task 5).
- Produces: `today.html`(`data-page="today"`, `<meta name="robots" content="noindex">`, 스크립트: icons·config·app·data·affiliate·layout·illus·store·schedule·reminders·today·pages/today). 탭 바 앱 모드 `TABS[0] = { key: "home", label: "홈", href: "today.html", icon: "house" }` 이고 활성 판정은 `data-page="today"` 를 `home` 으로 본다. `D.tips()` 추가.

- [ ] **Step 1: 테스트 쓰기** — `tests/test_ios_project.py` 의 `server.url` 을 다루는 테스트에 `self.assertTrue(cfg["server"]["url"].endswith("/today"))` 를 더하고, 안드로이드 복사본(`app/android/app/src/main/assets/capacitor.config.json`)도 같은 `server.url` 인지 비교하는 테스트 1건. `tests/test_build_site.py` 의 precache 테스트에 `"/today.html" in B.precache_urls()`.

- [ ] **Step 2: 실패 확인** — Run: `python -m unittest tests.test_ios_project tests.test_build_site` — Expected: 새 단언 FAIL.

- [ ] **Step 3: 구현** — 설정 두 파일의 `server.url` 을 `https://xn--og5b1hx9c.kr/today`, `PRECACHE_EXTRA` 에 `today.html`. `today.html` 은 `my.html` 의 head·header·footer 틀을 복사하고 본문은 `<main id="main"><div id="today-app">`. `pages/today.js`: `D.core()` + `D.tips()` + `AppBridge.ready()` 뒤 `S.load()`, 두 상태 렌더(4.1 의 순서), '먹었어요'(`logEnabled === true` 일 때만 버튼; 누르면 `markDue` + `toggleDone` + `persist` + 앱이면 `AppBridge.mirror`), 궁합 체크 바로가기 href = `compatibility.html?items=` + `S.ingredientIds(state).slice(0, 8)` + 부제 "앞 8개"(9개 이상일 때), 자정·`visibilitychange`·`storage` 이벤트에 다시 그리기(`my.js` 와 같은 방식). 웹에서도 열리지만 헤더 메뉴에는 넣지 않는다.

- [ ] **Step 4: 통과 확인** — `python -m unittest tests.test_ios_project tests.test_build_site` → OK. 브라우저 `today.html?app=1`: 저장한 영양제 없음 → 시작 안내; 데모 가져오기 링크로 목록을 넣은 뒤 → 인사·다음 복용·타임라인·한 줄·바로가기, 탭 바 첫 탭이 홈이고 활성. 모바일 뷰포트 캡처 뒤 데스크톱 복귀.

- [ ] **Step 5: 커밋** — `git add today.html assets/js/pages/today.js assets/js/layout.js assets/js/app.js assets/js/data.js assets/css/style.css scripts/build_site.py app/capacitor.config.json app/android/app/src/main/assets/capacitor.config.json app/www/index.html tests/test_ios_project.py tests/test_build_site.py && git commit -m "feat(app): 오늘 홈(today.html) — 다음 복용·타임라인·오늘의 한 줄·바로가기, 앱 시작 주소 /today, 탭 바에 홈"`

---

### Task 8: 내 정보 + 맞춤 추천 `recommend.html`, `Finder.reasons`, 처리방침 제5조

**Files:**
- Create: `recommend.html`, `assets/js/pages/recommend.js`
- Modify: `assets/js/finder.js`(`reasons`), `privacy.html:121-123`, `scripts/build_site.py`(`PRECACHE_EXTRA` 에 `recommend.html` 은 넣지 않음 — 온라인 전용; STATIC_PAGES 에도 넣지 않음(noindex))
- Test: `tests/finder.test.mjs`

**Interfaces:**
- Consumes: `Store.profile/setProfile/ingredientIds`, `Finder.score/summary`, `D.finder()`·`D.guides()`·`D.core()`, `Affiliate.buttonsHtml(query)`·`Affiliate.disclosure()`, `AppBridge.hideShopping()`, `[data-my-add]` 공통 처리(`layout.js`).
- Produces: `Finder.reasons(answers, data, slugs: string[]) → string[]` — `data.rules` 중 `matches(r.if, answers)` 이고 `r.guides` 가 `slugs` 와 겹치는 규칙들의 `if` 에서, 사용자가 답한 옵션의 라벨(질문 순서 → 옵션 순서, 중복 제거, `exclusive` 옵션 제외).

- [ ] **Step 1: 실패하는 테스트 쓰기** — `tests/finder.test.mjs` 끝에(기존 테스트가 `data`·`guides` 픽스처를 어떻게 만드는지 따라):

```js
test("reasons: 추천 가이드를 고른 규칙의 조건 가운데 내가 답한 라벨만, 질문 순서로 중복 없이", () => {
  const data = { questions: [{ id: "age", type: "single", options: [{ id: "40s", label: "40대" }] }, { id: "concern", type: "multi", options: [{ id: "eye", label: "눈 건강" }, { id: "sleep", label: "수면" }] }],
    rules: [{ if: { concern: ["eye"] }, guides: ["eye"] }, { if: { age: ["40s"], concern: ["eye", "sleep"] }, guides: ["eye", "aging"] }, { if: { concern: ["sleep"] }, guides: ["sleep"] }] };
  assert.deepEqual(F.reasons({ age: ["40s"], concern: ["eye"] }, data, ["eye"]), ["40대", "눈 건강"]);
  assert.deepEqual(F.reasons({ age: ["40s"], concern: ["sleep"] }, data, ["sleep"]), ["수면"]);   // 수면 가이드를 고른 규칙은 셋째뿐
});
```

- [ ] **Step 2: 실패 확인** — Run: `node --test tests/finder.test.mjs` — Expected: `F.reasons is not a function`.

- [ ] **Step 3: `reasons` 구현** → Run: `node --test tests/finder.test.mjs` → PASS.

- [ ] **Step 4: 페이지 구현** — `recommend.html`(noindex, `data-page="recommend"`, 스크립트: icons·config·app·data·affiliate·layout·illus·store·finder·pages/recommend). `pages/recommend.js`: `D.finder()`·`D.guides()`·`D.core()` → 폼은 `finder.json` 의 질문(`have` 제외)을 `type`(`single` 라디오, `multi` 체크박스 + `max`)대로 그리고 아래 고지 "내 정보는 이 기기에만 저장되고 서버로 보내지 않아요. 다른 기기로 옮기기 코드에는 함께 담겨요." + 저장 버튼 → `S.setProfile` + `S.save` + 앱이면 `AppBridge.mirror`. 저장된 profile 이 있으면 폼을 접고 칩 요약(`Finder.summary`) + '수정'. 결과: `F.score(Object.assign({}, profile, { have: S.ingredientIds(state) }), data, guides, core)` → `recommended.slice(0, 8)` 카드(이름·분류 라벨, 왜 칩 = `F.reasons(answers, data, ingredients[].from).slice(0, 3)`, 식약처 칩 = `mfdsFunction` 첫 문구, 본문 한 줄 = `whoFor[0]` 또는 `summary` 첫 문장, 버튼 `[data-my-add]` + 구매(`AppBridge.hideShopping()` 이면 `<a href="products.html?ingredient=<id>">제품 찾기</a>`, 아니면 `Affiliate.buttonsHtml(it.shopQuery)`)), `have` 중 점수 있는 것 2개까지 흐리게 "이미 먹고 있어요", `avoided`·`flags` 는 `pages/finder.js` 의 문구를 재사용(공통 상수로 뽑아도 됨). 머리: 배지·설명 한 줄·고지(참고 정보 + 쇼핑 버튼이 보이면 `Affiliate.disclosure()`). 금칙어를 쓰지 않는다.

- [ ] **Step 5: 처리방침** — `privacy.html` 제5조 첫 문단의 열거에 "저장한 제품 목록(제품명과 그 안의 성분)", "내 정보(연령대·성별·건강 고민·생활 상황·복용 중인 약의 분류 — 추천 계산에만 쓰임)" 를 더하고, 둘째 문단에 옮기기 코드에 내 정보도 담긴다는 문장을 넣는다. 날짜 표기가 있으면 갱신.

- [ ] **Step 6: 브라우저 확인** — `recommend.html?app=1`: 폼 저장 → 칩 요약 → 카드에 왜/식약처 칩 → 구매 자리가 '제품 찾기' → `?app=0` 웹에서는 쿠팡 버튼 + 고지. 주소에 답이 실리지 않음(쿼리 없음) 확인.

- [ ] **Step 7: 커밋** — `git add recommend.html assets/js/pages/recommend.js assets/js/finder.js privacy.html tests/finder.test.mjs && git commit -m "feat: 내 정보 + 맞춤 추천(recommend.html) — 근거 칩(왜·식약처 인정 기능성), AI 정리 데이터 배지, 처리방침 제5조 갱신"`

---

### Task 9: 사용 설명 `help.html` + 연결

**Files:**
- Create: `help.html`
- Modify: `scripts/build_site.py:28`(`STATIC_PAGES` 에 `help.html`), `assets/js/layout.js`(헤더 `NAV` 는 그대로 두고 푸터 링크에 '사용 설명' 추가, 모바일 메뉴에도), `my.html`(상단 안내 문장에 "사용 설명 보기 ›" 링크), `today.html`(바로가기는 Task 7 에서 이미 연결)
- Test: `tests/test_build_site.py`(`"help.html" in B.STATIC_PAGES`), `check_site.py` 통과

- [ ] **Step 1: 테스트** — `tests/test_build_site.py` 에 `self.assertIn("help.html", B.STATIC_PAGES)` 1건 → Run → FAIL.
- [ ] **Step 2: 구현** — `help.html`(색인됨, `.page-hero` 틀, 제목 "영양제.kr 앱 사용 설명", 설계 4.5 의 9항목을 `<section id="help-…">` 로, 각 항목 2~4문장 + CSS 로 그린 작은 예시 상자(브레인스토밍 시안의 카드·타임라인·요약 창을 단순화). 끝에 "참고 정보 고지"). `STATIC_PAGES` 추가, 푸터·모바일 메뉴 링크, `my.html` 링크.
- [ ] **Step 3: 확인** — `python -m unittest tests.test_build_site` → OK; 빌드 뒤 `check_site.py` 가 sitemap 에 `help` 를 포함하고 실패 0.
- [ ] **Step 4: 커밋** — `git add help.html scripts/build_site.py assets/js/layout.js my.html tests/test_build_site.py && git commit -m "feat: 사용 설명 페이지(help.html) + 푸터·메뉴·내 영양제·홈 연결"`

---

### Task 10: 문서·자산·빌드·점검·배포

**Files:**
- Modify: `CLAUDE.md`(구조 요약: `today.js`·`addsummary.js`·`recommend`·`help`·스키마 v2·탭·앱 시작 처리·`data/tips.json`), `docs/PROJECT-STATUS.md`(작업 이력 행 + 다음 할 일: 새 AAB·TestFlight 빌드가 필요(시작 주소), 플레이 데이터 안전·App Privacy 답안 재확인, 쿠팡 승인 뒤 `appShopping`), `docs/app-release.md`·`docs/app-release-ios.md`(시작 주소 `/today` 는 다음 빌드부터)
- 생성: `npm run assets` → `python scripts/build_site.py` → `python scripts/check_site.py`

- [ ] **Step 1: 전체 테스트** — Run: `node --test tests/sw.test.mjs tests/store.test.mjs tests/app.test.mjs tests/reminders.test.mjs tests/finder.test.mjs tests/terms.test.mjs tests/schedule.test.mjs tests/addsummary.test.mjs tests/today.test.mjs` 와 `python -m unittest discover -s tests` — Expected: 전부 PASS.
- [ ] **Step 2: 자산·빌드·점검** — `npm run assets && python scripts/build_site.py && python scripts/check_site.py` — Expected: 아이콘 번들에 새 아이콘(`house`·`package` 등) 포함, 실패 0.
- [ ] **Step 3: 최종 브라우저 점검** — 로컬 서버에서 `today.html?app=1`·`my.html`·`recommend.html`·`help.html` 을 모바일 뷰포트로 훑고 콘솔 에러 0 확인, 데스크톱 복귀, `?app=0`.
- [ ] **Step 4: 문서 갱신** — 위 파일들.
- [ ] **Step 5: 커밋·푸시** — `git add -A && git commit -m "docs: 앱 홈·제품 추가·내 정보 맞춤 추천·사용 설명 반영 — 구조 요약·현황·출시 문서" && git pull --rebase && git push` → `git show --stat HEAD`. 충돌이 생성 파일(sw.js·meta·색인)이면 upstream 을 받고 재빌드.
