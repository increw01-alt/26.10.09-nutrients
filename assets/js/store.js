/* 내 영양제 저장 모듈 — 회원가입 없이 기기 안(localStorage)에만 저장한다. 서버로 보내지 않는다.
 * 저장 키 "yj.my.v1", 스키마 v1:
 *   { v: 1,
 *     items: [{ id: 성분id, addedAt: ISO, slot?: 사용자가 바꾼 시간대 }],   // 이름·기본 시간대는 매번 ingredients.json 에서 읽는다
 *     settings: { times: {시간대: "HH:MM"}, slotOn: {시간대: bool}, showNames: bool, weekends: bool, remindersOn: bool, logEnabled: bool|null },
 *     log: { "YYYY-MM-DD": { due: [시간대…], done: {시간대: true} } } }
 * 모든 변환 함수는 입력 상태를 바꾸지 않고 새 상태를 돌려준다(순수 함수). 저장소는 인자로 바꿔 끼울 수 있어 Node 에서 테스트한다(tests/store.test.mjs).
 * 스키마를 바꾸면 v 를 올리고 load() 에 마이그레이션을 넣는다. */
(function () {
  "use strict";
  var KEY = "yj.my.v1";
  var SLOT_ORDER = ["morning_empty", "morning_after", "before_meal", "lunch_after", "evening_after", "bedtime"];
  var SLOT_LABEL = { morning_empty: "아침 공복", morning_after: "아침 식후", before_meal: "식전", lunch_after: "점심 식후", evening_after: "저녁 식후", bedtime: "취침 전" };
  var DEFAULT_TIMES = { morning_empty: "07:30", morning_after: "08:00", before_meal: "11:30", lunch_after: "12:30", evening_after: "19:00", bedtime: "22:30" };
  var SETTING_KEYS = ["showNames", "weekends", "remindersOn", "logEnabled"];
  var TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function isSlot(s) { return SLOT_ORDER.indexOf(s) >= 0; }
  function defaultStorage() { try { return typeof localStorage !== "undefined" ? localStorage : null; } catch (e) { return null; } }

  function empty() {
    var slotOn = {};
    SLOT_ORDER.forEach(function (s) { slotOn[s] = true; });
    return { v: 1, items: [], settings: { times: clone(DEFAULT_TIMES), slotOn: slotOn, showNames: true, weekends: true, remindersOn: false, logEnabled: null }, log: {} };
  }

  /* 저장소에서 읽는다. 없거나 깨졌거나 다른 버전이면 빈 상태. 빠진 설정 키는 기본값으로 채운다. */
  function load(storage) {
    var st = storage || defaultStorage();
    var base = empty();
    if (!st) return base;
    var raw;
    try { raw = st.getItem(KEY); } catch (e) { return base; }
    if (!raw) return base;
    var data;
    try { data = JSON.parse(raw); } catch (e) { return base; }
    if (!data || data.v !== 1 || !Array.isArray(data.items)) return base;
    var out = base;
    out.items = data.items.filter(function (it) { return it && typeof it.id === "string" && it.id; }).map(function (it) {
      var o = { id: it.id, addedAt: typeof it.addedAt === "string" ? it.addedAt : new Date().toISOString() };
      if (isSlot(it.slot)) o.slot = it.slot;
      return o;
    });
    var s = data.settings || {};
    SETTING_KEYS.forEach(function (k) { if (k in s) out.settings[k] = s[k]; });
    if (s.times) SLOT_ORDER.forEach(function (k) { if (TIME_RE.test(String(s.times[k] || ""))) out.settings.times[k] = s.times[k]; });
    if (s.slotOn) SLOT_ORDER.forEach(function (k) { if (typeof s.slotOn[k] === "boolean") out.settings.slotOn[k] = s.slotOn[k]; });
    if (data.log && typeof data.log === "object") out.log = clone(data.log);
    return out;
  }

  /* 저장. 실패(차단·용량 초과)는 삼키고 false. 브라우저에서는 성공 시 yj:change 이벤트 */
  function save(state, storage) {
    var st = storage || defaultStorage();
    if (!st) return false;
    try { st.setItem(KEY, JSON.stringify(state)); } catch (e) { return false; }
    try { if (typeof window !== "undefined" && window.dispatchEvent && typeof CustomEvent === "function") window.dispatchEvent(new CustomEvent("yj:change")); } catch (e) { /* 무시 */ }
    return true;
  }

  function addItems(state, ids) {
    var out = clone(state), added = [], have = {};
    out.items.forEach(function (it) { have[it.id] = true; });
    (ids || []).forEach(function (id) {
      if (typeof id !== "string" || !id || have[id]) return;
      have[id] = true; added.push(id);
      out.items.push({ id: id, addedAt: new Date().toISOString() });
    });
    return { state: out, added: added };
  }

  function removeItem(state, id) {
    var out = clone(state);
    out.items = out.items.filter(function (it) { return it.id !== id; });
    return out;
  }

  /* 사용자가 바꾼 시간대. null 이면 기본으로 되돌림. 모르는 시간대는 무시 */
  function setSlot(state, id, slot) {
    if (slot !== null && !isSlot(slot)) return state;
    var out = clone(state);
    out.items.forEach(function (it) {
      if (it.id !== id) return;
      if (slot === null) delete it.slot; else it.slot = slot;
    });
    return out;
  }

  function overrides(state) {
    var o = {};
    state.items.forEach(function (it) { if (isSlot(it.slot)) o[it.id] = it.slot; });
    return o;
  }

  function setTime(state, slot, hhmm) {
    if (!isSlot(slot) || !TIME_RE.test(String(hhmm || ""))) return state;
    var out = clone(state); out.settings.times[slot] = hhmm; return out;
  }

  function setSetting(state, key, value) {
    if (SETTING_KEYS.indexOf(key) < 0) return state;
    var out = clone(state); out.settings[key] = value; return out;
  }

  function setSlotOn(state, slot, on) {
    if (!isSlot(slot)) return state;
    var out = clone(state); out.settings.slotOn[slot] = !!on; return out;
  }

  /* 성분 사전에서 사라진 id 를 조용히 제거하고 알려 준다 */
  function pruneUnknown(state, byId) {
    var out = clone(state), removed = [];
    out.items = out.items.filter(function (it) { if (byId && byId[it.id]) return true; removed.push(it.id); return false; });
    return { state: out, removed: removed };
  }

  /* ---- 복용 기록: 날짜 키는 기기의 현지 날짜 ---- */
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function dateKey(d) { return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()); }
  function fromKey(key) { var p = key.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function addDays(key, n) { var d = fromKey(key); d.setDate(d.getDate() + n); return dateKey(d); }
  /* 오늘을 포함해 n 일, 오래된 날부터 */
  function lastDays(todayKey, n) {
    var out = [];
    for (var i = n - 1; i >= 0; i--) out.push(addDays(todayKey, -i));
    return out;
  }

  /* 그날 챙겨야 할 시간대 목록을 기록한다(시간표가 바뀌면 due 가 따라가고 done 은 남은 것만 유지). 비면 그날 기록을 지운다 */
  function markDue(state, key, slots) {
    var out = clone(state);
    var due = (slots || []).filter(isSlot);
    if (!due.length) { delete out.log[key]; return out; }
    var prev = out.log[key] || { done: {} };
    var done = {};
    due.forEach(function (s) { if (prev.done && prev.done[s]) done[s] = true; });
    out.log[key] = { due: due, done: done };
    return out;
  }

  function toggleDone(state, key, slot, done) {
    var day = state.log[key];
    if (!day || day.due.indexOf(slot) < 0) return state;
    var out = clone(state);
    if (done) out.log[key].done[slot] = true; else delete out.log[key].done[slot];
    return out;
  }

  function dayStats(state, key) {
    var day = state.log[key];
    if (!day || !day.due.length) return { due: 0, done: 0, complete: false };
    var n = day.due.filter(function (s) { return day.done[s]; }).length;
    return { due: day.due.length, done: n, complete: n === day.due.length };
  }

  /* 연속 일수: 오늘이 완료면 오늘부터, 아니면 어제부터 거슬러 완료가 이어진 날 수 */
  function streak(state, todayKey) {
    var key = dayStats(state, todayKey).complete ? todayKey : addDays(todayKey, -1), n = 0;
    while (dayStats(state, key).complete) { n++; key = addDays(key, -1); }
    return n;
  }

  function clearLog(state) { var out = clone(state); out.log = {}; return out; }

  var Store = {
    KEY: KEY, SLOT_ORDER: SLOT_ORDER, SLOT_LABEL: SLOT_LABEL, DEFAULT_TIMES: DEFAULT_TIMES,
    empty: empty, load: load, save: save,
    addItems: addItems, removeItem: removeItem, setSlot: setSlot, overrides: overrides,
    setTime: setTime, setSetting: setSetting, setSlotOn: setSlotOn, pruneUnknown: pruneUnknown,
    dateKey: dateKey, addDays: addDays, lastDays: lastDays, markDue: markDue, toggleDone: toggleDone, dayStats: dayStats, streak: streak, clearLog: clearLog
  };
  if (typeof window !== "undefined") window.Store = Store;
  if (typeof module !== "undefined") module.exports = Store;
})();
