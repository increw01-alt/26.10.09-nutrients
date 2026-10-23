// 추가 직후 요약(assets/js/addsummary.js) 테스트 — resolvePair 는 가짜로 주입. 실행: node --test tests/addsummary.test.mjs
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
  assert.deepEqual(s.pairs, []); assert.deepEqual(s.okNames, []); assert.deepEqual(s.unknownNames, ["이름만"]);   // 판단 근거가 없으면 "무난"이 아니라 "볼 수 없음"
  const s2 = A.build(core, [{ id: "p:9", name: "이름만", ings: [] }], "p:9", { assign: { "p:9": "morning_after" }, notes: [] }, opts);
  assert.equal(s2.subtitle, "제품 · 성분 정보 없음");
  const s3 = A.build(core, [{ id: "p:9", name: "이름만", ings: [] }, "magnesium", "calcium"], "p:9", { assign: { "p:9": "morning_after", magnesium: "bedtime", calcium: "morning_after" }, notes: [] }, opts);
  assert.deepEqual(s3.pairs, []); assert.deepEqual(s3.okNames, []); assert.deepEqual(s3.unknownNames, ["마그네슘", "칼슘"]);
});

// ---- 최종 검토 미룬 지적 #5: 배정 이유는 moves 로 판정 — 상대로만 언급된 메모를 고르지 않는다 ----
test("이유: sched.moves 가 있으면 그것으로만 판정하고(상대로 언급된 메모 무시), 옮긴 항목은 옮긴 이유 문장", () => {
  const sched2 = { assign: { calcium: "morning_after", magnesium: "evening_after" }, notes: ["마그네슘은(는) 칼슘과(와) 간격을 두기 위해 저녁 식후(으)로 옮겼습니다."], moves: [{ key: "magnesium", slot: "evening_after", because: "calcium" }] };
  const o = Object.assign({}, opts, { times: { morning_after: "08:00", evening_after: "19:00" }, slotLabel: { morning_after: "아침 식후", evening_after: "저녁 식후" } });
  const cal = A.build(core, ["calcium", "magnesium"], "calcium", sched2, o);
  assert.equal(cal.reason.indexOf("옮겼"), -1);   // 칼슘은 옮겨지지 않았다
  const mag = A.build(core, ["calcium", "magnesium"], "magnesium", sched2, o);
  assert.ok(mag.reason.indexOf("칼슘") >= 0 && mag.reason.indexOf("저녁 식후") >= 0 && mag.reason.indexOf("옮겼") >= 0);
});
