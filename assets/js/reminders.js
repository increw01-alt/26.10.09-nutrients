/* 복용 알림 — 내 영양제의 알림 설정(시간대별 시각·켜기·이름 표시·주말)과 오늘 시간표로 휴대폰 로컬 알림을 계획하고 동기화한다.
 * 계획(plan)·동작 처리(applyAction)는 순수 함수라 Node 에서 테스트한다(tests/reminders.test.mjs). 실제 예약은 앱(Capacitor Local Notifications)에서만.
 * 알림 id 규칙: 시간대 순서 i(0~5) 기준 매일 반복 1000+i*10, 평일만(주말 끄기) 1000+i*10+weekday(2~6, 일요일=1), 30분 뒤 다시 9000+i.
 * 우리 범위(1000~1059, 9000~9005)만 취소·재예약하므로 다른 알림은 건드리지 않는다. 정확 알람 권한은 쓰지 않는다(isExactNotification: false). */
(function () {
  "use strict";
  var S = (typeof window !== "undefined" && window.Store) || (typeof require === "function" ? require("./store.js") : null);
  var ID_BASE = 1000, ID_SNOOZE = 9000, ACTION_TYPE = "DOSE", ACTION_TYPE_SNOOZE = "DOSE_SNOOZE";   // DOSE: 먹었어요+30분 뒤(기록 켬) / DOSE_SNOOZE: 30분 뒤만(기록 끔)
  /* iOS 플러그인은 sound 가 없으면 소리 없이 표시한다. 번들에 없는 이름이면 iOS 는 기본 알림음을 내고, 안드로이드는 해당 리소스가 없어 기본 채널(기본음)을 쓴다 */
  var SOUND = "default";
  var WEEKDAYS = [2, 3, 4, 5, 6];   // 월~금 (Capacitor Weekday: 일요일=1)
  function logOn(state) { return !!(state && state.settings && state.settings.logEnabled === true); }
  function actionTypeFor(state) { return logOn(state) ? ACTION_TYPE : ACTION_TYPE_SNOOZE; }

  function slotIndex(slot) { return S.SLOT_ORDER.indexOf(slot); }
  function names(items, opts) { return items.map(function (it) { return opts && opts.shortName ? opts.shortName(it) : it.name; }).join(" · "); }
  function parseTime(hhmm) { var m = /^(\d\d):(\d\d)$/.exec(String(hhmm || "")); return m ? { hour: +m[1], minute: +m[2] } : null; }

  /* 상태 + 오늘 시간표 → 예약할 알림 목록 (id 오름차순). remindersOn 이 꺼져 있으면 빈 배열 */
  function plan(state, sched, opts) {
    var st = state.settings;
    if (!st.remindersOn) return [];
    var out = [];
    (sched.slots || []).forEach(function (s) {
      var i = slotIndex(s.key);
      if (i < 0 || !st.slotOn[s.key] || !s.items.length) return;
      var t = parseTime(st.times[s.key]) || parseTime(S.DEFAULT_TIMES[s.key]);
      var title = S.SLOT_LABEL[s.key] + " 영양제 시간이에요";
      var body = st.showNames ? names(s.items, opts) : "지금 챙겨 드세요";
      var make = function (id, on) {
        return { id: id, title: title, body: body, schedule: { on: on, allowWhileIdle: true }, actionTypeId: actionTypeFor(state), extra: { slot: s.key }, isExactNotification: false, sound: SOUND };
      };
      if (st.weekends) out.push(make(ID_BASE + i * 10, { hour: t.hour, minute: t.minute }));
      else WEEKDAYS.forEach(function (wd) { out.push(make(ID_BASE + i * 10 + wd, { weekday: wd, hour: t.hour, minute: t.minute })); });
    });
    return out.sort(function (a, b) { return a.id - b.id; });
  }

  function isPlanId(id) { return id >= ID_BASE && id < ID_BASE + 60; }
  function isSnoozeId(id) { return id >= ID_SNOOZE && id < ID_SNOOZE + 6; }
  function ourIds(pending) {
    return (pending || []).map(function (n) { return n.id; }).filter(function (id) { return isPlanId(id) || isSnoozeId(id); });
  }
  /* 동기화 때 취소할 id — 반복 예약은 늘, '30분 뒤' 예약은 알림을 껐을 때만 (켜진 상태에서 재예약해도 30분 뒤 알림이 살아 있게) */
  function cancelIds(pending, remindersOn) {
    return ourIds(pending).filter(function (id) { return isPlanId(id) || !remindersOn; });
  }

  /* '30분 뒤 다시' — 그 시간대의 1회성 알림. logOn 이면 '먹었어요' 버튼도 붙는다 */
  function snoozeNotification(slot, nowMs, opts, bodyText, logEnabled) {
    return { id: ID_SNOOZE + slotIndex(slot), title: S.SLOT_LABEL[slot] + " 영양제, 30분 뒤예요", body: bodyText || "지금 챙겨 드세요",
      schedule: { at: new Date(nowMs + 30 * 60000), allowWhileIdle: true }, actionTypeId: logEnabled ? ACTION_TYPE : ACTION_TYPE_SNOOZE, extra: { slot: slot }, isExactNotification: false, sound: SOUND };
  }

  /* 알림 동작 → 새 상태. done: (기록이 켜진 경우만) 그날 due 를 먼저 기록하고 체크 / snooze: 시간대만 알려줌 / tap: 열기 */
  function applyAction(state, action, dueSlots, todayKey) {
    var slot = action && action.notification && action.notification.extra && action.notification.extra.slot;
    var id = action && action.actionId;
    if (id === "done" && slot) {
      if (!logOn(state)) return { state: state, snooze: null, open: false };
      var fresh = S.markDue(state, todayKey, dueSlots);
      return { state: S.toggleDone(fresh, todayKey, slot, true), snooze: null, open: false };
    }
    if (id === "snooze" && slot) return { state: state, snooze: slot, open: false };
    if (id === "tap") return { state: state, snooze: null, open: true };
    return { state: state, snooze: null, open: false };
  }

  /* foreground: iOS 는 이 옵션이 없는 버튼을 앱을 띄우지 않고 백그라운드로 전달해, 종료 상태면 이벤트가 다음 실행 때 소비되어 '30분 뒤'·'먹었어요' 시각이 밀린다.
     안드로이드는 버튼이 늘 앱을 열므로 옵션을 무시한다 */
  function actionTypes() {
    return { types: [
      { id: ACTION_TYPE, actions: [{ id: "done", title: "먹었어요", foreground: true }, { id: "snooze", title: "30분 뒤 다시", foreground: true }] },
      { id: ACTION_TYPE_SNOOZE, actions: [{ id: "snooze", title: "30분 뒤 다시", foreground: true }] }
    ] };
  }

  /* 우리 범위의 반복 예약을 취소하고 계획대로 다시 예약한다 (설정이 바뀔 때마다 호출해도 안전). 알림을 끄면 30분 뒤 예약도 함께 취소 */
  function sync(LN, state, sched, opts) {
    return LN.getPending().then(function (res) {
      var ids = cancelIds(res && res.notifications, !!(state.settings && state.settings.remindersOn));
      var cancel = ids.length ? LN.cancel({ notifications: ids.map(function (id) { return { id: id }; }) }) : Promise.resolve();
      return cancel.then(function () {
        var list = plan(state, sched, opts);
        if (!list.length) return { cancelled: ids.length, scheduled: 0 };
        return LN.schedule({ notifications: list }).then(function () { return { cancelled: ids.length, scheduled: list.length }; });
      });
    });
  }

  var Reminders = { ID_BASE: ID_BASE, ID_SNOOZE: ID_SNOOZE, ACTION_TYPE: ACTION_TYPE, ACTION_TYPE_SNOOZE: ACTION_TYPE_SNOOZE, plan: plan, ourIds: ourIds, cancelIds: cancelIds, snoozeNotification: snoozeNotification, applyAction: applyAction, actionTypes: actionTypes, sync: sync };
  if (typeof window !== "undefined") window.Reminders = Reminders;
  if (typeof module !== "undefined") module.exports = Reminders;
})();
