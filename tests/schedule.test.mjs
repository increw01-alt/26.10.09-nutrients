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

// ---- 최종 검토 미룬 지적 #5: 옮긴 항목을 구조화된 moves 로 돌려준다 ----
test("build: moves 에 옮긴 항목(key)·새 시간대·상대(because)가 담긴다, 안 옮기면 빈 배열", () => {
  const r = Sch.build(["zinc", { id: "p:2", name: "칼슘제", ings: ["calcium"] }], core, { zinc: "evening_after" }, { resolvePair });
  assert.deepEqual(r.moves, [{ key: "p:2", slot: r.assign["p:2"], because: "zinc" }]);
  assert.deepEqual(Sch.build(["magnesium"], core, {}, { resolvePair }).moves, []);
});
