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
function onLog() { return S.setSetting(on(), "logEnabled", true); }

test("plan: 꺼져 있으면 없음", () => assert.deepEqual(R.plan(S.empty(), sched, { shortName: sn }), []));
test("plan: 주말 포함이면 시간대마다 요일별 7건(일~토 1~7) — 같은 번호가 이틀 연속 쓰이지 않아 어제 알림이 남아 있어도 오늘 알림이 조용히 갱신되지 않는다", () => {
  const p = R.plan(on(), sched, { shortName: sn });
  assert.deepEqual(p.map(n => n.id), [1011, 1012, 1013, 1014, 1015, 1016, 1017, 1051, 1052, 1053, 1054, 1055, 1056, 1057]);
  assert.deepEqual(p[0].schedule.on, { weekday: 1, hour: 8, minute: 0 }); assert.equal(p[0].title, "아침 식후 영양제 시간이에요"); assert.equal(p[0].body, "비타민 D");
  assert.deepEqual(p[7].schedule.on, { weekday: 1, hour: 22, minute: 30 }); assert.equal(p[7].actionTypeId, "DOSE_SNOOZE"); assert.equal(p[7].extra.slot, "bedtime");   // on() 은 기록이 꺼진 상태
  assert.equal(p[0].isExactNotification, false); assert.equal(p[0].schedule.allowWhileIdle, true);
});
test("plan: 주말 끄면 월~금 5건씩, 토·일 없음", () => {
  const p = R.plan(S.setSetting(on(), "weekends", false), { slots: [sched.slots[0]] }, { shortName: sn });
  assert.deepEqual(p.map(n => n.schedule.on.weekday), [2, 3, 4, 5, 6]); assert.deepEqual(p.map(n => n.id), [1012, 1013, 1014, 1015, 1016]);
});
test("plan: 시간대 토글이 꺼진 시간대·이름 숨김", () => {
  let s = S.setSlotOn(on(), "bedtime", false); s = S.setSetting(s, "showNames", false);
  const p = R.plan(s, sched, { shortName: sn });
  assert.equal(p.length, 7); assert.equal(p[0].body, "지금 챙겨 드세요");
});
test("plan: 같은 입력이면 같은 결과(동기화가 멱등)", () => assert.deepEqual(R.plan(on(), sched, { shortName: sn }), R.plan(on(), sched, { shortName: sn })));
test("ourIds: 우리 범위만", () => assert.deepEqual(R.ourIds([{ id: 1 }, { id: 1010 }, { id: 1059 }, { id: 1060 }, { id: 9003 }, { id: 9006 }]), [1010, 1059, 9003]));
test("snoozeNotification: 30분 뒤 1회", () => {
  const n = R.snoozeNotification("bedtime", 0, { shortName: sn }, "마그네슘");
  assert.equal(n.id, 9005); assert.equal(n.schedule.at.getTime(), 30 * 60000); assert.equal(n.title, "취침 전 영양제, 30분 뒤예요");
});
test("applyAction: done 은 오늘 due 를 먼저 기록하고 체크", () => {
  const r = R.applyAction(onLog(), { actionId: "done", notification: { extra: { slot: "bedtime" } } }, ["morning_after", "bedtime"], "2026-10-20");
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
  assert.deepEqual(calls, [["cancel", [1010]], ["schedule", [1011, 1012, 1013, 1014, 1015, 1016, 1017, 1051, 1052, 1053, 1054, 1055, 1056, 1057]]]); assert.deepEqual(r, { cancelled: 1, scheduled: 14 });   // 옛 매일 반복 id(1010)도 우리 범위라 함께 취소된다
  calls.length = 0; await R.sync(LN, S.empty(), sched, { shortName: sn }); assert.deepEqual(calls, [["cancel", [1010]]]);
});

// ---- 중간 검토 반영 ----
test("plan: 기록이 켜져 있으면 DOSE(먹었어요+30분 뒤), 아니면 DOSE_SNOOZE(30분 뒤만)", () => {
  assert.equal(R.plan(on(), sched, { shortName: sn })[0].actionTypeId, "DOSE_SNOOZE");
  assert.equal(R.plan(onLog(), sched, { shortName: sn })[0].actionTypeId, "DOSE");
  assert.deepEqual(R.actionTypes().types.map(t => t.id + ":" + t.actions.map(a => a.id).join("+")), ["DOSE:done+snooze", "DOSE_SNOOZE:snooze"]);
  assert.equal(R.snoozeNotification("bedtime", 0, { shortName: sn }, "x", false).actionTypeId, "DOSE_SNOOZE");
  assert.equal(R.snoozeNotification("bedtime", 0, { shortName: sn }, "x", true).actionTypeId, "DOSE");
});
test("applyAction: 기록이 꺼져 있으면 done 은 아무것도 남기지 않는다", () => {
  const s = on();
  const r = R.applyAction(s, { actionId: "done", notification: { extra: { slot: "bedtime" } } }, ["bedtime"], "2026-10-20");
  assert.equal(r.state, s); assert.deepEqual(r.state.log, {});
});
test("sync: 30분 뒤 예약(9000대)은 알림이 켜져 있으면 남기고, 끄면 함께 취소한다", async () => {
  const calls = [];
  const LN = { getPending: async () => ({ notifications: [{ id: 1010 }, { id: 9003 }, { id: 42 }] }), cancel: async (o) => calls.push(["cancel", o.notifications.map(n => n.id)]), schedule: async (o) => calls.push(["schedule", o.notifications.map(n => n.id)]) };
  await R.sync(LN, on(), sched, { shortName: sn });
  assert.deepEqual(calls[0], ["cancel", [1010]]);
  calls.length = 0; await R.sync(LN, S.empty(), sched, { shortName: sn });
  assert.deepEqual(calls, [["cancel", [1010, 9003]]]);
});

test("알림 버튼은 iOS 에서도 앱을 띄워 처리한다(foreground) — 백그라운드 전달이면 '30분 뒤'·'먹었어요' 시각이 다음 실행 때로 밀린다", () => {
  for (const t of R.actionTypes().types) for (const a of t.actions) assert.equal(a.foreground, true, t.id + ":" + a.id);
});

test("알림마다 sound 를 지정한다 — iOS 플러그인은 sound 가 없으면 소리 없이 표시(안드로이드는 기본 채널 소리 유지)", () => {
  const p = R.plan(on(), sched, { shortName: sn });
  assert.equal(p.length, 14);
  for (const n of p) assert.equal(n.sound, "default", "plan " + n.id);
  assert.equal(R.snoozeNotification("bedtime", 0, { shortName: sn }, "x").sound, "default");
});

// ---- 안드로이드 소리·채널·알림창 정리 (10-22) ----
test("plan: 주말 끄기·켜기 모두 id 가 우리 범위(1000~1059) 안이고 겹치지 않는다", () => {
  const six = { slots: S.SLOT_ORDER.map(k => ({ key: k, items: [core.byId.magnesium] })) };
  for (const weekends of [true, false]) {
    const ids = R.plan(S.setSetting(on(), "weekends", weekends), six, { shortName: sn }).map(n => n.id);
    assert.equal(new Set(ids).size, ids.length); for (const id of ids) assert.ok(id >= 1000 && id < 1060, String(id));
    assert.equal(ids.length, weekends ? 42 : 30);
  }
});
test("channel: 안드로이드 전용 채널 — id dose, 한글 이름, 중요도 높음(4, 화면 위에 뜨고 소리)", () => {
  const c = R.channel();
  assert.equal(c.id, "dose"); assert.equal(c.name, "복용 알림"); assert.equal(c.importance, 4); assert.equal(c.vibration, true); assert.equal(c.visibility, 1);
  assert.equal(typeof c.description, "string"); assert.ok(c.description.length > 0);
});
test("plan·snoozeNotification: 모든 알림이 채널 dose 로 간다", () => {
  for (const n of R.plan(onLog(), sched, { shortName: sn })) assert.equal(n.channelId, "dose", String(n.id));
  assert.equal(R.snoozeNotification("bedtime", 0, { shortName: sn }, "x", true).channelId, "dose");
});
test("ensureChannel: createChannel 이 있으면 채널 정의로 부르고, 없거나(iOS) 실패해도 resolve", async () => {
  const calls = [];
  await R.ensureChannel({ createChannel: async (c) => calls.push(c.id) });
  assert.deepEqual(calls, ["dose"]);
  await R.ensureChannel({});
  await R.ensureChannel({ createChannel: async () => { throw new Error("not implemented"); } });
});
test("sync: 채널을 먼저 만들고 예약한다 — 채널이 없는 id 로 예약하면 안드로이드가 알림을 버린다", async () => {
  const calls = [];
  const LN = { createChannel: async (c) => calls.push("channel:" + c.id), getPending: async () => ({ notifications: [] }), cancel: async () => calls.push("cancel"), schedule: async (o) => calls.push("schedule:" + o.notifications.length) };
  await R.sync(LN, on(), sched, { shortName: sn });
  assert.deepEqual(calls, ["channel:dose", "schedule:14"]);
});
test("scheduleSnooze: 채널을 확인한 뒤 30분 뒤 알림을 예약한다", async () => {
  const calls = [];
  const LN = { createChannel: async (c) => calls.push("channel:" + c.id), schedule: async (o) => calls.push("schedule:" + o.notifications.map(n => n.id).join(",")) };
  await R.scheduleSnooze(LN, R.snoozeNotification("bedtime", 0, { shortName: sn }, "x", false));
  assert.deepEqual(calls, ["channel:dose", "schedule:9005"]);
});
test("clearDelivered: 알림창에 남은 우리 알림만 지운다 — 같은 번호가 남아 있으면 다음 알림이 소리 없이 갱신되기 때문. API 가 없으면 아무것도 안 함", async () => {
  const calls = [];
  const LN = { getDeliveredNotifications: async () => ({ notifications: [{ id: 1013 }, { id: 9001 }, { id: 42 }] }), removeDeliveredNotifications: async (o) => calls.push(o.notifications.map(n => n.id)) };
  assert.deepEqual(await R.clearDelivered(LN), { removed: 2 }); assert.deepEqual(calls, [[1013, 9001]]);
  calls.length = 0;
  assert.deepEqual(await R.clearDelivered({ getDeliveredNotifications: async () => ({ notifications: [{ id: 42 }] }), removeDeliveredNotifications: async (o) => calls.push(o) }), { removed: 0 }); assert.deepEqual(calls, []);
  assert.deepEqual(await R.clearDelivered({}), { removed: 0 });
});
