// 복용 알림 계획·동작 모듈(assets/js/reminders.js) 테스트. 실행: node --test tests/reminders.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const req = createRequire(import.meta.url);
const S = req("../assets/js/store.js"), R = req("../assets/js/reminders.js");
const sn = (it) => it.name.replace(/\s*\(.*$/, "");
const core = { byId: { magnesium: { id: "magnesium", name: "마그네슘" }, "vitamin-d": { id: "vitamin-d", name: "비타민 D" } } };
const sched = { slots: [{ key: "morning_after", items: [core.byId["vitamin-d"]] }, { key: "bedtime", items: [core.byId.magnesium] }] };
function on() { return S.setSetting(S.addItems(S.empty(), ["vitamin-d", "magnesium"]).state, "remindersOn", true); }

test("plan: 꺼져 있으면 없음", () => assert.deepEqual(R.plan(S.empty(), sched, { shortName: sn }), []));
test("plan: 매일 반복 — 시간대마다 1건, 시각·이름·id", () => {
  const p = R.plan(on(), sched, { shortName: sn });
  assert.deepEqual(p.map(n => n.id), [1010, 1050]);
  assert.deepEqual(p[0].schedule.on, { hour: 8, minute: 0 }); assert.equal(p[0].title, "아침 식후 영양제 시간이에요"); assert.equal(p[0].body, "비타민 D");
  assert.equal(p[1].schedule.on.hour, 22); assert.equal(p[1].schedule.on.minute, 30); assert.equal(p[1].actionTypeId, "DOSE"); assert.equal(p[1].extra.slot, "bedtime");
  assert.equal(p[0].isExactNotification, false); assert.equal(p[0].schedule.allowWhileIdle, true);
});
test("plan: 주말 끄면 월~금 5건씩, 토·일 없음", () => {
  const p = R.plan(S.setSetting(on(), "weekends", false), { slots: [sched.slots[0]] }, { shortName: sn });
  assert.deepEqual(p.map(n => n.schedule.on.weekday), [2, 3, 4, 5, 6]); assert.deepEqual(p.map(n => n.id), [1012, 1013, 1014, 1015, 1016]);
});
test("plan: 시간대 토글이 꺼진 시간대·이름 숨김", () => {
  let s = S.setSlotOn(on(), "bedtime", false); s = S.setSetting(s, "showNames", false);
  const p = R.plan(s, sched, { shortName: sn });
  assert.equal(p.length, 1); assert.equal(p[0].body, "지금 챙겨 드세요");
});
test("plan: 같은 입력이면 같은 결과(동기화가 멱등)", () => assert.deepEqual(R.plan(on(), sched, { shortName: sn }), R.plan(on(), sched, { shortName: sn })));
test("ourIds: 우리 범위만", () => assert.deepEqual(R.ourIds([{ id: 1 }, { id: 1010 }, { id: 1059 }, { id: 1060 }, { id: 9003 }, { id: 9006 }]), [1010, 1059, 9003]));
test("snoozeNotification: 30분 뒤 1회", () => {
  const n = R.snoozeNotification("bedtime", 0, { shortName: sn }, "마그네슘");
  assert.equal(n.id, 9005); assert.equal(n.schedule.at.getTime(), 30 * 60000); assert.equal(n.title, "취침 전 영양제, 30분 뒤예요");
});
test("applyAction: done 은 오늘 due 를 먼저 기록하고 체크", () => {
  const r = R.applyAction(on(), { actionId: "done", notification: { extra: { slot: "bedtime" } } }, ["morning_after", "bedtime"], "2026-10-20");
  assert.deepEqual(S.dayStats(r.state, "2026-10-20"), { due: 2, done: 1, complete: false }); assert.equal(r.open, false); assert.equal(r.snooze, null);
});
test("applyAction: snooze·tap·모르는 동작", () => {
  assert.equal(R.applyAction(on(), { actionId: "snooze", notification: { extra: { slot: "bedtime" } } }, [], "2026-10-20").snooze, "bedtime");
  assert.equal(R.applyAction(on(), { actionId: "tap", notification: { extra: { slot: "bedtime" } } }, [], "2026-10-20").open, true);
  const s = on(); assert.equal(R.applyAction(s, { actionId: "x", notification: {} }, [], "2026-10-20").state, s);
});
test("sync: 우리 id 만 취소하고 계획을 예약한다", async () => {
  const calls = [];
  const LN = { getPending: async () => ({ notifications: [{ id: 1010 }, { id: 42 }] }), cancel: async (o) => calls.push(["cancel", o.notifications.map(n => n.id)]), schedule: async (o) => calls.push(["schedule", o.notifications.map(n => n.id)]) };
  const r = await R.sync(LN, on(), sched, { shortName: sn });
  assert.deepEqual(calls, [["cancel", [1010]], ["schedule", [1010, 1050]]]); assert.deepEqual(r, { cancelled: 1, scheduled: 2 });
  calls.length = 0; await R.sync(LN, S.empty(), sched, { shortName: sn }); assert.deepEqual(calls, [["cancel", [1010]]]);
});
