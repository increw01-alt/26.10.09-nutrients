// 오늘 홈 로직(assets/js/today.js) 테스트 — 인사·다음 복용·타임라인·오늘의 한 줄. 실행: node --test tests/today.test.mjs
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
  assert.deepEqual(a, b); assert.equal(a.source, "내 영양제 기준 · 영양제.kr 성분 자료"); assert.ok(a.text.length > 5);
  assert.equal(T.tip([], core, at(9, 0), general, {}).source, "영양 상식");
  assert.notEqual(T.tip([], core, new Date(2026, 9, 24), general, {}).text, T.tip([], core, new Date(2026, 9, 23), general, {}).text);
});
test("tip: 제품 항목은 안의 성분으로 푼다, 성분 정보 없으면 일반 팁", () => {
  const general = [{ text: "일반", source: "영양 상식" }];
  assert.equal(T.tip([{ id: "p:1", name: "x", ings: ["vitamin-d"] }], core, at(9, 0), general, {}).source, "내 영양제 기준 · 영양제.kr 성분 자료");
  assert.equal(T.tip([{ id: "p:1", name: "x", ings: [] }], core, at(9, 0), general, {}).text, "일반");
});

test("tip: 데이터 쌍의 시너지 팁은 조합 이름을 앞에 붙이고, 규칙으로 판정한 쌍(inferred)의 팁은 쓰지 않는다", () => {
  const c2 = { byId: { a: { id: "a", name: "A", timing: {} }, b: { id: "b", name: "B", timing: {} } } };
  const data = T.tip(["a", "b"], c2, at(9, 0), [], { resolvePair: () => ({ type: "synergy", tip: "식후에 함께" }) });
  assert.equal(data.text, "A + B: 식후에 함께");
  const inferred = T.tip(["a", "b"], c2, at(9, 0), [{ text: "일반", source: "영양 상식" }], { resolvePair: () => ({ type: "synergy", tip: "식후에 함께", inferred: true }) });
  assert.equal(inferred.text, "일반");
});
