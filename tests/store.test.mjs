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
