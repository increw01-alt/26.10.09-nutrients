# 내 영양제·복용 시간표·복용 기록·내보내기(앱 2단계) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 회원가입 없이 기기 안에 저장되는 "내 영양제" 기능을 웹 코드로 만든다: 성분 저장·시간대 변경, 시간대별 시각이 붙은 오늘 시간표, 사용자가 켜고 끄는 복용 기록(오늘 체크·연속 일수·7일/30일 보기), 링크·QR·텍스트 코드로 내보내기와 가져오기, 그리고 궁합 체크·성분 페이지·헤더·홈의 진입점.

**Architecture:** 상태(내 영양제·설정·기록)는 새 모듈 `assets/js/store.js` 하나가 읽고 쓴다. 이 모듈은 순수 함수(상태 변환·날짜·통계·내보내기 코드)와 얇은 저장 계층(localStorage, 주입 가능)으로 나뉘어 Node 에서 테스트된다. 새 페이지 `my.html` 의 UI 는 `assets/js/pages/my.js` 가 상태를 통째로 다시 그리는 방식으로 만들고, 시간표는 기존 `schedule.js` 에 "사용자가 바꾼 시간대" 인자를 더해 그대로 쓴다. 알림 예약 자체는 3단계(앱)이며, 이 계획은 알림 시각·토글 설정의 저장과 화면만 만든다.

**Tech Stack:** 정적 HTML + Vanilla JS(IIFE + `module.exports` 겸용으로 Node 테스트), `assets/css/style.css` 일반 CSS, QR 은 npm `qrcode-generator`(MIT) 파일을 `assets/js/vendor/qrcode.js` 로 복사해 커밋(런타임 CDN 없음), 테스트는 `node --test`. 파이썬 빌드 스크립트는 한 줄 수정.

**Spec:** `docs/superpowers/specs/2026-10-20-mobile-app-reminders-design.md` 5-1(내 영양제), 5-3(복용 기록), 5-4(내보내기·가져오기), 5-5(저장), 5-2 중 설정 항목(시각·토글·성분 이름 표시·주말), 9절 2단계

## Global Constraints

- 스택·규칙은 CLAUDE.md 그대로: 프레임워크·번들러·런타임 CDN 금지, 1st-party 스크립트는 `defer`, 생성 파일은 빌드로만, JS·CSS 수정 뒤 `python scripts/build_site.py`(해시·`sw.js`), 점검 `python scripts/check_site.py` 실패 0.
- 새 Tailwind 유틸리티 클래스를 쓰지 않는다. 새 스타일은 `assets/css/style.css` 에 `.my-` 접두 일반 CSS 로. (Task 8 에서 `npm run assets` 를 한 번 돌려 CI 와 산출물을 맞춘다.)
- 저장 키 `yj.my.v1`, 스키마 버전 `v: 1`. 저장소에는 성분 id 와 사용자가 바꾼 시간대만 두고 이름·기본 시간대는 매번 `ingredients.json` 에서 읽는다.
- 시간대 키와 순서(`schedule.js` 와 동일): `morning_empty`(아침 공복) · `morning_after`(아침 식후) · `before_meal`(식전) · `lunch_after`(점심 식후) · `evening_after`(저녁 식후) · `bedtime`(취침 전). 기본 알림 시각: `07:30` · `08:00` · `11:30` · `12:30` · `19:00` · `22:30`.
- 내보내기 코드 형식 `YJ1-<base64url(JSON)>`; 링크는 `my.html?import=<코드>`. 복용 기록은 내보내기에 넣지 않는다.
- 문구: 효능·치료 표현 금지. 시간표 팁은 성분의 `timing.note`·`timing.label` 만 쓴다. `my.html` 은 `<meta name="robots" content="noindex">`.
- 응답·커밋·주석·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. 각 작업 끝에 테스트·빌드·점검 뒤 커밋, 푸시는 Task 9 에서 한 번. `.claude/launch.json` 은 커밋 전 삭제, 모바일 확인 뒤 데스크톱 복귀. 로컬 서비스워커는 켜지 않는다(`?sw=1` 불필요).

## Review Focus

1. 가져오기 코드가 손상·위조됐을 때 화면이 죽거나 기존 목록이 지워지면 안 된다. 잘못된 코드는 거부하고, 모르는 성분 id 는 건너뛰며 알려 준다. → Task 3 `importCode: 깨진 입력은 null`, `merge: 모르는 id 는 skipped 로`.
2. localStorage 를 못 쓰는 환경(사생활 보호 모드·저장소 차단)에서도 페이지가 그려지고 조용히 동작해야 한다. → Task 1 `load: 저장소가 throw 하면 빈 상태`, `save: throw 를 삼킴`.
3. 날짜 키는 기기의 현지 날짜여야 한다(UTC 로 계산하면 밤 9시 이후 체크가 내일로 기록됨). → Task 2 `dateKey 는 현지 날짜`.
4. 사용자가 직접 바꾼 시간대는 궁합 간격 규칙보다 우선해야 하고(자동으로 옮기지 않음), 대신 메모로 알린다. → Task 4 브라우저 검증.
5. 성분 사전에서 id 가 사라져도 내 영양제 페이지가 깨지면 안 된다(조용히 제외하고 한 번 알림). → Task 1 `pruneUnknown`.

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `assets/js/store.js` (신규) | 상태 스키마·변환·날짜·통계·내보내기 코드(순수 함수) + localStorage 저장 계층. `window.Store` 와 `module.exports` 둘 다 노출 |
| `assets/js/pages/my.js` (신규) | `my.html` 의 모든 UI(목록·추가 검색·시간표·기록·알림 설정·내보내기/가져오기·질문 카드) |
| `my.html` (신규) | 페이지 뼈대(noindex) |
| `assets/js/vendor/qrcode.js` (신규, 복사본) | QR 생성 라이브러리(`qrcode-generator`) |
| `assets/js/schedule.js` (수정) | `build(ids, core, overrides)` — 사용자 시간대 우선 |
| `assets/js/pages/compat.js`, `scripts/build_site.py`(성분 템플릿), `assets/js/pages/ingredient.js`, `assets/js/layout.js`, `index.html`, `compatibility.html` (수정) | 진입점: "내 영양제로 저장"·"내 영양제에 추가"·헤더 메뉴·홈 링크, `store.js` 로드 |
| `assets/css/style.css` (수정) | `.my-*` 스타일 |
| `privacy.html` (수정) | 제5조에 실제 저장 항목(키 이름) 반영 |
| `package.json` (수정) | devDependency `qrcode-generator`, 스크립트 `vendor:qr` |
| `tests/store.test.mjs` (신규) | store.js 테스트 |
| `CLAUDE.md`, `docs/PROJECT-STATUS.md` (수정) | 구조·명령·이력 |

---

### Task 1: store.js — 상태·항목·시간대·설정·정리

**Files:**
- Create: `assets/js/store.js`
- Create: `tests/store.test.mjs`

**Interfaces:**
- Produces (`window.Store` = `module.exports`):
  - `KEY = "yj.my.v1"`, `SLOT_ORDER` (위 6개 순서), `DEFAULT_TIMES` (위 6개 시각), `SLOT_LABEL`(키→한글).
  - `empty() -> State` — `{ v: 1, items: [], settings: { times: {…DEFAULT_TIMES}, slotOn: {6개 모두 true}, showNames: true, weekends: true, remindersOn: false, logEnabled: null }, log: {} }`. `logEnabled: null` 은 "아직 묻지 않음".
  - `load(storage?) -> State` — `storage`(기본 `localStorage`)에서 `KEY` 를 읽어 JSON 파싱. 없거나 파싱 실패·`v !== 1`·throw 면 `empty()`. 읽은 상태는 `empty()` 위에 얕게 합쳐 빠진 설정 키를 채운다.
  - `save(state, storage?) -> boolean` — 저장 성공 여부. throw 는 삼키고 false. 브라우저에서는 성공 시 `window.dispatchEvent(new CustomEvent("yj:change"))`.
  - `addItems(state, ids: string[]) -> { state, added: string[] }` — 중복·빈 값 제외, `items` 에 `{ id, addedAt: ISO 문자열 }` 추가(순서 유지). 입력 상태는 바꾸지 않는다(모든 변환 함수 공통: 새 객체 반환).
  - `removeItem(state, id) -> State`
  - `setSlot(state, id, slot | null) -> State` — `slot` 이 `SLOT_ORDER` 에 없으면 그대로 반환. `null` 이면 override 제거.
  - `overrides(state) -> { [id]: slot }` — `slot` 이 있는 항목만.
  - `setTime(state, slot, "HH:MM") -> State` — `^([01]\d|2[0-3]):[0-5]\d$` 아니면 그대로.
  - `setSetting(state, key, value) -> State` — `key ∈ {showNames, weekends, remindersOn, logEnabled}` 외는 그대로. `slotOn` 은 `setSlotOn(state, slot, bool)`.
  - `pruneUnknown(state, byId: object) -> { state, removed: string[] }` — `byId[id]` 가 없는 항목 제거.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/store.test.mjs`

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const S = createRequire(import.meta.url)("../assets/js/store.js");

function fakeStorage(init) { const m = new Map(Object.entries(init || {})); return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), map: m }; }
const throwing = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };

test("empty: 스키마 v1, 기본 시각 6개, logEnabled 는 null", () => {
  const s = S.empty();
  assert.equal(s.v, 1); assert.deepEqual(s.items, []);
  assert.equal(s.settings.times.morning_after, "08:00"); assert.equal(s.settings.times.bedtime, "22:30");
  assert.equal(s.settings.logEnabled, null); assert.equal(s.settings.remindersOn, false);
});
test("load: 저장소가 throw 하면 빈 상태", () => assert.deepEqual(S.load(throwing), S.empty()));
test("load: 깨진 JSON·다른 버전은 빈 상태", () => {
  assert.deepEqual(S.load(fakeStorage({ "yj.my.v1": "{nope" })), S.empty());
  assert.deepEqual(S.load(fakeStorage({ "yj.my.v1": JSON.stringify({ v: 2, items: [{ id: "zinc" }] }) })), S.empty());
});
test("load: 빠진 설정 키는 기본값으로 채운다", () => {
  const s = S.load(fakeStorage({ "yj.my.v1": JSON.stringify({ v: 1, items: [{ id: "zinc", addedAt: "2026-10-20T00:00:00Z" }], settings: { showNames: false }, log: {} }) }));
  assert.equal(s.items[0].id, "zinc"); assert.equal(s.settings.showNames, false); assert.equal(s.settings.times.bedtime, "22:30"); assert.equal(s.settings.weekends, true);
});
test("save: throw 를 삼키고 false, 성공하면 true 와 저장 내용", () => {
  assert.equal(S.save(S.empty(), throwing), false);
  const st = fakeStorage(); assert.equal(S.save(S.empty(), st), true); assert.equal(JSON.parse(st.map.get("yj.my.v1")).v, 1);
});
test("addItems: 중복·빈 값 제외, 입력 상태는 그대로", () => {
  const s0 = S.empty(); const r = S.addItems(s0, ["zinc", "zinc", "", "vitamin-d"]);
  assert.deepEqual(r.added, ["zinc", "vitamin-d"]); assert.equal(r.state.items.length, 2); assert.equal(s0.items.length, 0);
  assert.deepEqual(S.addItems(r.state, ["zinc"]).added, []);
});
test("removeItem·setSlot·overrides", () => {
  let s = S.addItems(S.empty(), ["zinc", "magnesium"]).state;
  s = S.setSlot(s, "magnesium", "morning_after"); assert.deepEqual(S.overrides(s), { magnesium: "morning_after" });
  assert.deepEqual(S.overrides(S.setSlot(s, "magnesium", "nope")), { magnesium: "morning_after" });
  assert.deepEqual(S.overrides(S.setSlot(s, "magnesium", null)), {});
  assert.equal(S.removeItem(s, "zinc").items.length, 1);
});
test("setTime·setSetting·setSlotOn 검증", () => {
  const s = S.empty();
  assert.equal(S.setTime(s, "bedtime", "23:15").settings.times.bedtime, "23:15");
  assert.equal(S.setTime(s, "bedtime", "25:00").settings.times.bedtime, "22:30");
  assert.equal(S.setSetting(s, "logEnabled", true).settings.logEnabled, true);
  assert.equal(S.setSetting(s, "hacker", true).settings.hacker, undefined);
  assert.equal(S.setSlotOn(s, "bedtime", false).settings.slotOn.bedtime, false);
});
test("pruneUnknown: 사전에 없는 id 는 제거하고 알려 준다", () => {
  const s = S.addItems(S.empty(), ["zinc", "gone"]).state;
  const r = S.pruneUnknown(s, { zinc: {} });
  assert.deepEqual(r.removed, ["gone"]); assert.deepEqual(r.state.items.map(i => i.id), ["zinc"]);
});
```

- [ ] **Step 2: 실패 확인** — Run: `node --test tests/store.test.mjs` → Expected: `Cannot find module '../assets/js/store.js'`

- [ ] **Step 3: `assets/js/store.js` 구현** — IIFE 안에서 `Store` 객체를 만들고 끝에 `if (typeof window !== "undefined") window.Store = Store; if (typeof module !== "undefined") module.exports = Store;`. 상단 주석에 스키마와 키를 적는다. 날짜·통계·내보내기 함수 자리는 Task 2·3 에서 채운다.

- [ ] **Step 4: 통과 확인** — Run: `node --test tests/store.test.mjs` → Expected: `pass 9`, `fail 0`

- [ ] **Step 5: 커밋**

```bash
git add assets/js/store.js tests/store.test.mjs
git commit -m "feat(my): 내 영양제 저장 모듈 store.js — 상태 스키마 v1, 항목·시간대·설정 변환, 저장소 주입과 오류 흡수"
```

---

### Task 2: store.js — 복용 기록·날짜·통계

**Files:**
- Modify: `assets/js/store.js`, `tests/store.test.mjs`

**Interfaces:**
- Produces:
  - `dateKey(d: Date) -> "YYYY-MM-DD"` — 현지 시각 기준(`getFullYear/getMonth/getDate`).
  - `addDays(key, n) -> key`, `lastDays(todayKey, n) -> string[]` — 오래된 날부터 `n` 개(오늘 포함).
  - `markDue(state, key, slots: string[]) -> State` — `log[key] = { due: slots(순서 유지), done: 기존 done 중 slots 에 있는 것만 }`. `slots` 가 비면 `log[key]` 를 지운다.
  - `toggleDone(state, key, slot, done: boolean) -> State` — `log[key].due` 에 없는 slot 이면 그대로.
  - `dayStats(state, key) -> { due: number, done: number, complete: boolean }` — 기록 없으면 `{0,0,false}`.
  - `streak(state, todayKey) -> number` — 오늘이 complete 면 오늘부터, 아니면 어제부터 거슬러 complete 인 날이 이어진 수.
  - `clearLog(state) -> State`.

- [ ] **Step 1: 실패하는 테스트 추가**

```js
test("dateKey 는 현지 날짜", () => assert.equal(S.dateKey(new Date(2026, 9, 20, 23, 30)), "2026-10-20"));
test("addDays·lastDays", () => {
  assert.equal(S.addDays("2026-10-20", -1), "2026-10-19"); assert.equal(S.addDays("2026-10-31", 1), "2026-11-01");
  assert.deepEqual(S.lastDays("2026-10-20", 3), ["2026-10-18", "2026-10-19", "2026-10-20"]);
});
test("markDue·toggleDone·dayStats", () => {
  let s = S.markDue(S.empty(), "2026-10-20", ["morning_after", "bedtime"]);
  s = S.toggleDone(s, "2026-10-20", "morning_after", true);
  s = S.toggleDone(s, "2026-10-20", "nope", true);
  assert.deepEqual(S.dayStats(s, "2026-10-20"), { due: 2, done: 1, complete: false });
  s = S.toggleDone(s, "2026-10-20", "bedtime", true);
  assert.equal(S.dayStats(s, "2026-10-20").complete, true);
  s = S.markDue(s, "2026-10-20", ["morning_after"]);   // 시간표가 줄면 due 가 줄고 done 도 그에 맞춤
  assert.deepEqual(S.dayStats(s, "2026-10-20"), { due: 1, done: 1, complete: true });
  assert.deepEqual(S.dayStats(S.markDue(s, "2026-10-20", []), "2026-10-20"), { due: 0, done: 0, complete: false });
});
test("streak: 오늘 미완료면 어제부터 센다", () => {
  let s = S.empty();
  for (const k of ["2026-10-17", "2026-10-18", "2026-10-19"]) { s = S.markDue(s, k, ["morning_after"]); s = S.toggleDone(s, k, "morning_after", true); }
  s = S.markDue(s, "2026-10-20", ["morning_after"]);
  assert.equal(S.streak(s, "2026-10-20"), 3);
  assert.equal(S.streak(S.toggleDone(s, "2026-10-20", "morning_after", true), "2026-10-20"), 4);
  assert.equal(S.streak(S.markDue(s, "2026-10-18", []), "2026-10-20"), 1);   // 중간이 비면 끊김
  assert.equal(S.streak(S.empty(), "2026-10-20"), 0);
});
test("clearLog", () => assert.deepEqual(S.clearLog(S.markDue(S.empty(), "2026-10-20", ["bedtime"])).log, {}));
```

- [ ] **Step 2: 실패 확인** — Run: `node --test tests/store.test.mjs` → Expected: 새 5건 `TypeError: … is not a function`, 기존 9건 pass
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인** — Expected: `pass 14`
- [ ] **Step 5: 커밋** — `git commit -m "feat(my): 복용 기록 — 현지 날짜 키, 시간대별 체크, 오늘 통계·연속 일수"`

---

### Task 3: store.js — 내보내기·가져오기 코드, QR 라이브러리 복사

**Files:**
- Modify: `assets/js/store.js`, `tests/store.test.mjs`, `package.json`
- Create: `assets/js/vendor/qrcode.js` (복사본)

**Interfaces:**
- Produces:
  - `exportCode(state) -> string` — `"YJ1-" + base64url(JSON)`; JSON 은 `{ v: 1, items: [[id, slot 또는 0], …], times: {기본값과 다른 것만}, opts: { names: showNames, weekends } }`. base64url 은 UTF-8 → base64 → `+/` 를 `-_` 로, `=` 제거.
  - `importCode(text) -> { items: [{ id, slot: string|null }], times: object, opts: object } | null` — 앞뒤 공백 제거, 전체 URL 이나 `import=…` 가 섞여 있으면 그 값만 추출, `YJ1-` 접두 없음·base64 오류·JSON 오류·`v !== 1`·`items` 가 배열 아님이면 `null`. `slot` 이 `SLOT_ORDER` 밖이면 `null` 로.
  - `merge(state, payload, mode: "merge" | "replace", byId) -> { state, added: string[], skipped: string[] }` — `byId` 에 없는 id 는 `skipped`. `merge` 는 기존 유지 + 새 항목 추가(가져온 slot 은 새 항목에만 적용), `replace` 는 가져온 목록으로 교체. `times`·`opts` 는 두 모드 모두 설정에 반영. 기록(`log`)은 건드리지 않는다.
  - `exportUrl(code, base: string) -> string` — `base + "my.html?import=" + encodeURIComponent(code)`.
- `package.json`: `"qrcode-generator": "1.4.4"` devDependency, 스크립트 `"vendor:qr": "node -e \"require('fs').copyFileSync('node_modules/qrcode-generator/qrcode.js','assets/js/vendor/qrcode.js')\""`. 복사본 머리에 라이선스(MIT, Kazuhiko Arase)가 그대로 있어야 한다.

- [ ] **Step 1: 실패하는 테스트 추가**

```js
test("exportCode ↔ importCode 왕복, 기본 시각은 생략", () => {
  let s = S.addItems(S.empty(), ["zinc", "magnesium"]).state;
  s = S.setSlot(s, "magnesium", "morning_after"); s = S.setTime(s, "bedtime", "23:00"); s = S.setSetting(s, "weekends", false);
  const code = S.exportCode(s);
  assert.match(code, /^YJ1-[A-Za-z0-9_-]+$/);
  const p = S.importCode(code);
  assert.deepEqual(p.items, [{ id: "zinc", slot: null }, { id: "magnesium", slot: "morning_after" }]);
  assert.deepEqual(p.times, { bedtime: "23:00" }); assert.deepEqual(p.opts, { names: true, weekends: false });
});
test("importCode: URL 이나 import= 가 섞여도 코드만 뽑는다", () => {
  const code = S.exportCode(S.addItems(S.empty(), ["zinc"]).state);
  assert.equal(S.importCode("https://xn--og5b1hx9c.kr/my.html?import=" + encodeURIComponent(code) + "#x").items[0].id, "zinc");
  assert.equal(S.importCode("  " + code + "\n").items[0].id, "zinc");
});
test("importCode: 깨진 입력은 null", () => {
  for (const bad of ["", "garbage", "YJ1-!!!", "YJ1-" + btoa("{nope"), "YJ1-" + btoa(JSON.stringify({ v: 2, items: [] })), "YJ1-" + btoa(JSON.stringify({ v: 1, items: "x" }))]) assert.equal(S.importCode(bad), null, bad);
});
test("merge: 모르는 id 는 skipped 로, merge 는 기존 유지, replace 는 교체", () => {
  const byId = { zinc: {}, magnesium: {}, iron: {} };
  const base = S.setSlot(S.addItems(S.empty(), ["zinc"]).state, "zinc", "bedtime");
  const payload = { items: [{ id: "magnesium", slot: "morning_after" }, { id: "zinc", slot: null }, { id: "ghost", slot: null }], times: { bedtime: "23:00" }, opts: { names: false, weekends: true } };
  const m = S.merge(base, payload, "merge", byId);
  assert.deepEqual(m.added, ["magnesium"]); assert.deepEqual(m.skipped, ["ghost"]);
  assert.deepEqual(m.state.items.map(i => i.id), ["zinc", "magnesium"]); assert.deepEqual(S.overrides(m.state), { zinc: "bedtime", magnesium: "morning_after" });
  assert.equal(m.state.settings.times.bedtime, "23:00"); assert.equal(m.state.settings.showNames, false);
  const r = S.merge(base, payload, "replace", byId);
  assert.deepEqual(r.state.items.map(i => i.id), ["magnesium", "zinc"]); assert.deepEqual(S.overrides(r.state), { magnesium: "morning_after" });
});
test("exportUrl", () => assert.equal(S.exportUrl("YJ1-abc", "./"), "./my.html?import=YJ1-abc"));
```

- [ ] **Step 2: 실패 확인** — Expected: 새 5건 실패, 기존 14건 pass
- [ ] **Step 3: 구현** — base64url 은 `btoa(unescape(encodeURIComponent(json)))`/`decodeURIComponent(escape(atob(…)))` (Node 24·브라우저 공통).
- [ ] **Step 4: 통과 확인** — Expected: `pass 19`
- [ ] **Step 5: QR 라이브러리 설치·복사** — Run: `npm install --save-dev qrcode-generator@1.4.4 && npm run vendor:qr && head -c 400 assets/js/vendor/qrcode.js && node -e "const q=require('./assets/js/vendor/qrcode.js'); const c=q(0,'M'); c.addData('YJ1-test'); c.make(); console.log(c.getModuleCount())"` → Expected: 머리에 `Copyright (c) 2009 Kazuhiko Arase` 와 MIT 표기, 모듈 수 출력(예: `21`).
- [ ] **Step 6: 커밋**

```bash
git add assets/js/store.js tests/store.test.mjs package.json package-lock.json assets/js/vendor/qrcode.js
git commit -m "feat(my): 내보내기·가져오기 코드(YJ1-base64url)와 합치기/바꾸기, QR 라이브러리(qrcode-generator) 복사본"
```

---

### Task 4: schedule.js — 사용자 시간대 우선

**Files:**
- Modify: `assets/js/schedule.js` (`build`)

**Interfaces:**
- Produces: `Schedule.build(ids, core, overrides?)` — `overrides[id]` 가 있으면 그 시간대로 시작하고 충돌 때문에 자동으로 옮기지 않는다(다른 항목만 옮김). 해결되지 않은 충돌은 지금처럼 `notes` 에 남는다. 반환 구조는 그대로 `{ slots, notes }`.

- [ ] **Step 1: RED(브라우저)** — `.claude/launch.json` + `preview_start name=static`, `compatibility.html` 을 열고 `javascript_tool`:

```js
(async () => { const core = await Data.core(); const s = Schedule.build(["psyllium", "banaba"], core, { psyllium: "before_meal" }); const slotOf = id => (s.slots.find(x => x.items.some(i => i.id === id)) || {}).key; return { psyllium: slotOf("psyllium"), banaba: slotOf("banaba"), notes: s.notes }; })()
```
Expected(RED): `psyllium: "bedtime"` (현재는 overrides 를 무시하고 자동 이동)

- [ ] **Step 2: 구현** — `assign[id] = (overrides && overrides[id]) || timing.slot`; 이동 루프에서 `overrides[id]` 가 있는 항목은 건너뜀.
- [ ] **Step 3: GREEN** — 같은 스크립트 → Expected: `psyllium: "before_meal"`, `banaba: "before_meal"` 또는 banaba 가 대체 시간대로 이동, `notes` 에 "간격" 문구 1건 이상. 이어 `Schedule.build(["psyllium","banaba"], core)` 는 이전과 같은 결과(차전자피가 취침 전으로 이동).
- [ ] **Step 4: 빌드·점검·커밋** — `python scripts/build_site.py && python scripts/check_site.py --quiet` → `실패 0`. `git add assets/js/schedule.js sw.js i guide *.html data/meta.json && git commit -m "feat(schedule): 사용자가 바꾼 시간대는 자동 이동하지 않고 메모로만 안내(overrides 인자)"`

---

### Task 5: my.html + my.js — 목록·추가·시간표·알림 설정

**Files:**
- Create: `my.html`, `assets/js/pages/my.js`
- Modify: `assets/css/style.css`, `scripts/build_site.py` (`PRECACHE_EXTRA` 에 `"my.html"`)

**Interfaces:**
- Consumes: Task 1~4 의 `Store.*`, `Schedule.build(ids, core, overrides)`, 기존 `Data.core()`, `Data.search(items, q, limit)`, `Data.shortName`, `Data.esc`, `Illus.bottle/labelFor/colorFor`(compat.js 의 `thumb` 와 같은 방식).
- Produces (`my.html`): `data-page="my"`, head 는 다른 정적 페이지와 같고 스크립트는 `icons, config, data, affiliate, layout, store, schedule, pages/my` 순(모두 `defer`). `<title>내 영양제 — 복용 시간표와 기록 | 영양제.kr</title>`, description 50자 이상, `robots noindex`, canonical `https://xn--og5b1hx9c.kr/my`. 본문: `.page-hero`(경로 홈 › 내 영양제, kicker "내 영양제", 제목 "내가 먹는 영양제를 한곳에", lead 한 문장: 기기에만 저장되고 서버로 보내지 않는다는 설명) + `<div id="my-app">` 하나. 나머지는 `my.js` 가 그린다.
- Produces (`my.js`): `render()` 가 상태로 아래 섹션을 통째로 다시 그린다(`#my-app` 안, 각 섹션은 `<section id="…">`):
  - `#my-import`(Task 7), `#my-ask-log`(Task 6) 자리.
  - `#my-list` "먹고 있는 영양제 N개": 항목마다 썸네일·이름(성분 페이지 링크)·시간대 `<select class="my-slot">`(6개 옵션, 기본 시간대 옵션 텍스트 끝에 " (기본)")·삭제 버튼. 비어 있으면 안내 + `compatibility.html` 링크. 아래에 검색창 `<input id="my-search" placeholder="성분 이름으로 추가 (예: 마그네슘)">` 과 자동완성 목록(`Data.search(core.items, q, 8)`, 클릭하면 추가).
  - `#my-schedule` "오늘 시간표": `Schedule.build(ids, core, Store.overrides(state))` 결과를 시간대 순으로, 각 시간대 제목 + 설정 시각(`settings.times[slot]`) + 항목(이름·`timing.note` 또는 `timing.label`), `notes` 는 "시간표 메모" 상자. 아래 안내문은 compat 페이지의 시간표 안내문과 같은 문장.
  - `#my-reminders` "복용 알림": 상단에 `remindersOn` 토글은 비활성 + 문구 "휴대폰 알림은 앱에서 받을 수 있어요 (앱 출시 준비 중). 시각을 미리 정해 두면 앱에서 그대로 쓰여요." 그 아래 시간표에 영양제가 있는 시간대만 행으로: 이름 · `<input type="time" class="my-time">` · 켜기 토글(`slotOn`). 그리고 "알림에 성분 이름 표시"(`showNames`)·"주말에도 알림"(`weekends`) 토글.
  - `#my-log`·`#my-transfer` 는 Task 6·7.
  - 모든 변경은 `state = Store.xxx(state, …); Store.save(state); render();` 패턴. 검색창은 재렌더 뒤에도 입력값·포커스를 유지한다(검색 상태를 모듈 변수로 보관).
  - 시작 시 `Store.pruneUnknown(state, core.byId)` 로 사라진 성분을 제거하고 `removed.length` 면 상단 알림 한 줄.
- Produces (`style.css`): `.my-item`, `.my-slot`, `.my-empty`, `.my-search-list`, `.my-sched`, `.my-toggle`(체크박스를 토글처럼), `.my-note` 등 `.my-` 접두. 모바일 375px 에서 가로 스크롤 없음.

- [ ] **Step 1: `my.html`·`my.js`·CSS 작성, `PRECACHE_EXTRA` 에 `my.html` 추가**
- [ ] **Step 2: 빌드·점검** — `python scripts/build_site.py && python scripts/check_site.py --quiet && node --check assets/js/pages/my.js` → `실패 0 · 경고 0`
- [ ] **Step 3: 브라우저 검증(빈 상태 → 추가 → 시간대 변경 → 새로고침 유지)** — 로컬 서버에서 `my.html` 열고 `javascript_tool`:

```js
(async () => { localStorage.removeItem("yj.my.v1"); location.reload(); })()
```
이어 빈 안내가 보이는지 확인한 뒤, 검색창에 "마그네슘" 입력(`computer type`) → 자동완성 클릭 → 목록 1개·시간표에 '취침 전' 확인. `select.my-slot` 값을 `morning_after` 로 바꾸고 `change` 이벤트 발생 → 시간표의 마그네슘이 아침 식후로. 새로고침 뒤에도 유지(`JSON.parse(localStorage.getItem("yj.my.v1")).items[0]` 에 `slot: "morning_after"`). 알림 섹션에 아침 식후 행과 `08:00` 이 보이고 시각을 `08:30` 으로 바꾸면 시간표 제목의 시각도 바뀜. 콘솔 오류 없음.
- [ ] **Step 4: 모바일 확인** — `resize_window mobile`, 스크린샷으로 목록·시간표가 한 열로 보이고 `scrollWidth === 375`; 뒤에 `desktop`.
- [ ] **Step 5: 커밋** — `git add my.html assets/js/pages/my.js assets/css/style.css scripts/build_site.py sw.js i guide *.html data/meta.json && git commit -m "feat(my): 내 영양제 페이지 — 목록·검색 추가·시간대 변경·오늘 시간표·알림 시각 설정(기기 내 저장)"`

---

### Task 6: 복용 기록 섹션과 "기록도 남길까요?" 질문

**Files:**
- Modify: `assets/js/pages/my.js`, `assets/css/style.css`

**Interfaces:**
- Consumes: Task 2 의 `dateKey/markDue/toggleDone/dayStats/streak/lastDays/clearLog`.
- Produces (`my.js`):
  - 렌더 때 `today = Store.dateKey(new Date())`, 오늘 시간표의 시간대 키 목록으로 `Store.markDue(state, today, slots)` 를 호출해 저장(시간표가 바뀌면 due 도 따라감). 시간대 목록이 비면 `markDue(…, [])`.
  - `#my-ask-log`: `items.length > 0 && settings.logEnabled === null` 일 때만. 문구 "복용 기록도 남길까요? 시간대마다 '먹었어요'를 체크하고 연속 일수를 볼 수 있어요. 기록은 이 기기에만 남아요." 버튼 "네, 남길게요"(기본 강조) / "아니요". 선택하면 `setSetting(logEnabled, true|false)`.
  - `#my-log`(`logEnabled === true` 일 때만): 상단 "오늘 {done}개 중 {due}개 챙겼어요 · 연속 {streak}일" (due 가 0 이면 "오늘 시간표에 영양제가 없어요"). 오늘 시간대별 체크 버튼(`.my-check`, 눌린 상태 표시, 시간대 이름 + 그 시간대 성분 이름들). "최근 7일" 가로 줄: `lastDays(today, 7)` 의 날짜마다 점(완료 `.is-complete` / 일부 `.is-partial` / 없음). "최근 30일" 7열 달력(`lastDays(today, 30)`, 요일 머리 없이 날짜 숫자 + 점). 날짜 누르면 그 날의 due·done 목록을 아래에 펼침(`.my-day-detail`). 맨 아래 "기록 끄기"(`logEnabled=false`, 기록은 남김)와 "기록 지우기"(`confirm("복용 기록을 모두 지울까요?")` 뒤 `clearLog`).
  - `logEnabled === false` 면 `#my-log` 자리에 한 줄 "복용 기록은 꺼져 있어요" + "켜기" 버튼.

- [ ] **Step 1: 구현**
- [ ] **Step 2: 빌드·점검** — `python scripts/build_site.py && python scripts/check_site.py --quiet`
- [ ] **Step 3: 브라우저 검증** — `my.html` 에서 (Task 5 상태 이어서) 질문 카드가 보이면 "네" 클릭 → 기록 섹션 등장, 오늘 체크 1개 누름 → 문구 "오늘 1개 중 1개" 와 "연속 1일" 확인; `localStorage` 의 `log[today].done` 에 반영; 새로고침 뒤 유지. `javascript_tool` 로 어제 날짜를 완료로 심어(`Store.toggleDone(Store.markDue(...))` 후 `Store.save`) 새로고침하면 "연속 2일". "기록 지우기" 는 confirm 을 자동 수락하도록 `window.confirm = () => true` 로 바꾼 뒤 눌러 기록이 비는지 확인.
- [ ] **Step 4: 커밋** — `git commit -m "feat(my): 복용 기록 — 오늘 체크·연속 일수·7일/30일 보기, 첫 저장 때 기록 여부 질문, 끄기·지우기"`

---

### Task 7: 내보내기·가져오기 섹션과 `?import=` 흐름

**Files:**
- Modify: `assets/js/pages/my.js`, `my.html`(vendor/qrcode.js 스크립트 추가), `assets/css/style.css`

**Interfaces:**
- Consumes: Task 3 의 `exportCode/importCode/merge/exportUrl`, `window.qrcode`(vendor: `qrcode(0, "M")` → `addData(text)` → `make()` → `createSvgTag({ cellSize: 4, margin: 2 })`).
- Produces (`my.js`):
  - `#my-transfer` "다른 기기로 옮기기": 설명 한 줄(기록은 포함되지 않음). "내보내기" 버튼 → 패널에 링크(`Store.exportUrl(code, location.origin + location.pathname.replace(/[^/]*$/, ""))`, 읽기 전용 input + "복사" 버튼 `navigator.clipboard.writeText`, 실패 시 선택 상태로), QR(SVG, 링크 내용), 텍스트 코드(읽기 전용 textarea + "복사"). 항목이 0개면 버튼 비활성.
  - "가져오기": textarea + "불러오기" 버튼 → `Store.importCode` 가 `null` 이면 "코드를 읽을 수 없어요" 표시, 아니면 미리보기 카드(가져올 성분 이름 N개, 모르는 id 수) + 버튼 "합치기" / "바꾸기" / "취소". 실행 후 `merge` 결과를 "N개 추가, M개 건너뜀" 으로 알리고 재렌더.
  - 페이지 로드 시 `new URLSearchParams(location.search).get("import")` 가 있으면 같은 미리보기 카드를 `#my-import` 에 먼저 띄우고, 어떤 버튼이든 누르면 `history.replaceState(null, "", location.pathname)` 로 파라미터를 지운다.

- [ ] **Step 1: 구현**
- [ ] **Step 2: 빌드·점검** — 동일
- [ ] **Step 3: 브라우저 검증** — `my.html` 에서 내보내기 → 링크가 `my.html?import=YJ1-` 로 시작, QR `<svg>` 가 그려짐. 링크 값을 읽어 `localStorage.removeItem("yj.my.v1")` 뒤 그 링크로 이동 → 미리보기 카드 → "합치기" → 목록 복원, 주소에서 `import=` 가 사라짐. 가져오기 textarea 에 "garbage" 입력 → 오류 문구. 콘솔 오류 없음.
- [ ] **Step 4: 커밋** — `git commit -m "feat(my): 내보내기(링크·QR·텍스트 코드)와 가져오기(합치기/바꾸기), my.html?import= 복원 흐름"`

---

### Task 8: 진입점·개인정보처리방침·자산 정리

**Files:**
- Modify: `assets/js/layout.js` (`NAV` 에 `{ key: "my", label: "내 영양제", href: "my.html" }` 를 "궁합 체크" 다음에), `index.html:141` 근처 `.checker-footer` 에 " · <a href="my.html">내 영양제 보기</a>", `compatibility.html`(head 에 `store.js` 스크립트, `layout.js` 뒤), `assets/js/pages/compat.js`(결과 요약 `verdict` 아래 버튼 "내 영양제로 저장" → `Store.addItems(Store.load(), selected)` → `save` → `showToast("내 영양제에 N개 저장했어요")` + `my.html` 링크 토스트/버튼), `scripts/build_site.py`(성분 템플릿 head 에 `../assets/js/store.js`, 594행 궁합 버튼 옆에 `<button type="button" class="btn-outline mt-4" data-my-add="{id}"><i data-lucide="plus"></i>내 영양제에 추가</button>`; 285행 슬라이스를 `html_src[line_start : a]` 로), `assets/js/pages/ingredient.js`(`[data-my-add]` 클릭 → 추가 → 버튼 문구 "내 영양제에 있어요 ✓"로, 이미 있으면 처음부터 그 문구), `privacy.html` 제5조(저장되는 항목을 실제 키로: 내 영양제 목록·바꾼 시간대·알림 시각과 토글·복용 기록(날짜·시간대·체크)·설치 안내 닫은 날짜·로컬 서비스워커 스위치, "제공 예정" 표현 제거), `assets/css/tailwind.css`(`npm run assets` 결과)
- 아이콘: `plus` 가 번들에 없으면 `npm run icons`(`npm run assets` 가 포함).

- [ ] **Step 1: 구현** — 위 파일들.
- [ ] **Step 2: 자산·빌드·점검** — `npm run assets && python scripts/build_site.py && python scripts/check_site.py --quiet && git diff --stat assets/css/tailwind.css assets/js/icons.js` → `실패 0`, tailwind.css 변경이 있으면 쓰레기 규칙 `line_start` 가 사라진 것(`grep -c line_start assets/css/tailwind.css` → `0`).
- [ ] **Step 3: 브라우저 검증** — `compatibility.html?items=vitamin-d,magnesium` 에서 "내 영양제로 저장" 클릭 → 토스트 → `my.html` 에 2개. `i/zinc.html` 의 "내 영양제에 추가" 클릭 → 문구 변경, `my.html` 에 3개. 헤더 메뉴(데스크톱·모바일 메뉴)에 "내 영양제", 홈 하단 체커 아래 링크 확인. 하단 탭 바는 여전히 5개.
- [ ] **Step 4: 커밋** — `git add -A`(launch.json 없음 확인) 후 `git commit -m "feat(my): 진입점 — 헤더 메뉴·홈 링크·궁합 결과 '내 영양제로 저장'·성분 페이지 '내 영양제에 추가', 개인정보처리방침 제5조 실제 항목 반영, Tailwind 산출물 정리"`

---

### Task 9: 문서·푸시·배포 확인

**Files:**
- Modify: `CLAUDE.md`(구조 요약 `assets/js/` 에 `store.js`(내 영양제 저장, `yj.my.v1`)·`pages/my.js`·`vendor/qrcode.js`, 테스트 명령에 `node --test tests/store.test.mjs`, 작업 요령에 "내 영양제 스키마를 바꾸면 `v` 올리고 `load` 에 마이그레이션"), `docs/PROJECT-STATUS.md`(작업 이력 10-20 행, 7절 A 항목을 "2단계 완료 → 다음은 계획 3" 으로, 보류 항목 중 처리한 것 삭제)

- [ ] **Step 1: 전체 테스트·빌드·점검** — `node --test tests/store.test.mjs tests/sw.test.mjs && python -m unittest discover -s tests && python scripts/build_site.py && python scripts/check_site.py --quiet && test ! -e .claude/launch.json` → 모두 통과
- [ ] **Step 2: 커밋·푸시** — `git add -A && git commit -m "docs: 내 영양제(앱 2단계) 완료 기록, 다음 단계 안내" && git push origin HEAD`
- [ ] **Step 3: 배포 확인** — 2~3분 뒤 `curl -s https://xn--og5b1hx9c.kr/my | grep -c 'id="my-app"'` → `1`; 앱 안 브라우저로 `https://xn--og5b1hx9c.kr/my` 를 열어 마그네슘 추가·새로고침 유지·내보내기 QR 확인. 푸시 뒤 CI 가 `chore(assets)` 커밋을 올리면 pull.

---

## 자가 점검 기록

- 사양 대조: 5-1 목록·추가 경로 3가지·id 만 저장·시간대 변경·진입점(헤더·홈, 탭 바 유지) → Task 1·5·8; 5-2 중 설정(시각·토글·이름 표시·주말) 저장과 화면 → Task 1·5(알림 예약은 3단계); 5-3 토글·첫 저장 질문·오늘 체크·연속 일수·7일/30일·지우기 → Task 2·6; 5-4 링크·QR·텍스트 코드·합치기/바꾸기·`?import=`·기록 제외 → Task 3·7; 5-5 저장 모듈·스키마 버전·사라진 id 처리 → Task 1·9(문서).
- 이름 일치: `Store.addItems/removeItem/setSlot/overrides/setTime/setSetting/setSlotOn/pruneUnknown/dateKey/addDays/lastDays/markDue/toggleDone/dayStats/streak/clearLog/exportCode/importCode/merge/exportUrl`, `Schedule.build(ids, core, overrides)` 가 테스트·단계에서 같은 이름.
- Review Focus 5건 모두 소유 작업에 테스트 또는 검증 단계가 있음.
