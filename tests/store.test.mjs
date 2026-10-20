// 내 영양제 저장 모듈(assets/js/store.js) 테스트. 실행: node --test tests/store.test.mjs
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

// ---- Task 2: 복용 기록·날짜·통계 ----
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

// ---- Task 3: 내보내기·가져오기 ----
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
