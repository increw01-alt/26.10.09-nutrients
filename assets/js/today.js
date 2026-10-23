/* 오늘 홈(today.html) 로직 — 인사·다음 복용·오늘 시간표 타임라인·오늘의 한 줄. 순수 함수라 Node 에서 테스트한다(tests/today.test.mjs). 화면은 pages/today.js.
 *   greeting(date)                       시간대별 인사
 *   dateLabel(date)                      "10월 23일 금요일"
 *   nextDose(state, sched, now)          { status: "none"|"upcoming"|"missed"|"all-done", slot?, time?, names? }
 *   timeline(state, sched, now)          [{ key, label, time, names, done, isNext, reminderOff }]
 *   tip(entries, core, date, general, opts) { text, source } — 내 성분(제품은 안의 성분)의 팁을 날짜별로 하나, 없으면 일반 팁(data/tips.json)
 * 모집단은 시간표의 모든 시간대다: slotOn(시간대 알림 끄기)·weekends 는 알림에만 관여하고 복용 여부와는 무관하다(설계 7절 ②). */
(function () {
  "use strict";
  var S = (typeof window !== "undefined" && window.Store) || (typeof require === "function" ? require("./store.js") : null);
  var DAYS = ["일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일"];
  var SOURCE_MINE = "내 영양제 기준 · 영양제.kr 성분 자료";   // 식약처 인정 문구는 mfdsFunction 뿐이라 '식약처 인정 기능성 자료'라고 적지 않는다

  function greeting(date) {
    var h = date.getHours();
    if (h >= 5 && h < 11) return "좋은 아침이에요";
    if (h >= 11 && h < 17) return "좋은 오후예요";
    if (h >= 17 && h < 22) return "좋은 저녁이에요";
    return "늦은 시간이에요";
  }
  function dateLabel(date) { return (date.getMonth() + 1) + "월 " + date.getDate() + "일 " + DAYS[date.getDay()]; }
  function toMin(hhmm) { var m = /^(\d\d):(\d\d)$/.exec(String(hhmm || "")); return m ? (+m[1]) * 60 + (+m[2]) : 0; }

  /* 오늘 시간표의 시간대마다 시각·이름·먹음 여부 */
  function rows(state, sched, now) {
    var key = S.dateKey(now), log = (state.log && state.log[key]) || { done: {} };
    return (sched && sched.slots ? sched.slots : []).map(function (s) {
      var time = (state.settings && state.settings.times && state.settings.times[s.key]) || S.DEFAULT_TIMES[s.key] || "";
      return { key: s.key, label: S.SLOT_LABEL[s.key] || s.key, time: time, minutes: toMin(time),
        names: (s.items || []).map(function (it) { return it.name; }), done: !!(log.done && log.done[s.key]),
        reminderOff: !!(state.settings && state.settings.slotOn && state.settings.slotOn[s.key] === false) };
    });
  }
  function nextDose(state, sched, now) {
    var all = rows(state, sched, now);
    if (!all.length) return { status: "none" };
    var pending = all.filter(function (r) { return !r.done; });
    if (!pending.length) return { status: "all-done" };
    var nowMin = now.getHours() * 60 + now.getMinutes();
    var up = pending.filter(function (r) { return r.minutes >= nowMin; }).sort(function (a, b) { return a.minutes - b.minutes; })[0];
    if (up) return { status: "upcoming", slot: up.key, time: up.time, names: up.names };
    var late = pending.sort(function (a, b) { return b.minutes - a.minutes; })[0];   // 다 지났으면 가장 늦은 것(놓친 것)
    return { status: "missed", slot: late.key, time: late.time, names: late.names };
  }
  function timeline(state, sched, now) {
    var nd = nextDose(state, sched, now);
    return rows(state, sched, now).map(function (r) {
      return { key: r.key, label: r.label, time: r.time, names: r.names, done: r.done, isNext: nd.slot === r.key, reminderOff: r.reminderOff };
    });
  }

  function dayOfYear(d) { return Math.floor((Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) - Date.UTC(d.getFullYear(), 0, 1)) / 86400000) + 1; }
  /* 후보 문장: 성분 사전의 timing.note·dosage.note·benefits[0], 내 성분끼리의 시너지 tip(opts.resolvePair 가 있을 때). 새 문장을 짓지 않는다 */
  function tip(entries, core, date, general, opts) {
    opts = opts || {};
    var ids = [];
    (entries || []).forEach(function (e) {
      var list = typeof e === "string" ? [e] : ((e && e.ings) || []);
      list.forEach(function (id) { if (core.byId[id] && ids.indexOf(id) < 0) ids.push(id); });
    });
    var cands = [];
    ids.forEach(function (id) {
      var it = core.byId[id], t = it.timing || {};
      if (t.note) cands.push(it.name + ": " + (t.label ? t.label + " — " : "") + t.note);
      if (it.dosage && it.dosage.note) cands.push(it.name + ": " + it.dosage.note);
      if (it.benefits && it.benefits[0]) cands.push(it.name + " — " + it.benefits[0]);
    });
    if (opts.resolvePair) for (var i = 0; i < ids.length; i++) for (var j = i + 1; j < ids.length; j++) {
      var p = opts.resolvePair(core, ids[i], ids[j]);
      if (p && p.type === "synergy" && p.tip && !p.inferred) cands.push(core.byId[ids[i]].name + " + " + core.byId[ids[j]].name + ": " + p.tip);   // 데이터 쌍만(규칙 판정은 일반 문장이라 뺌), 어느 조합의 팁인지 앞에 붙인다
    }
    var source = SOURCE_MINE, pool = cands;
    if (!pool.length) { pool = (general || []).map(function (g) { return g.text; }); source = null; }
    if (!pool.length) return { text: "", source: "" };
    var idx = (date.getFullYear() * 366 + dayOfYear(date)) % pool.length;
    return { text: pool[idx], source: source || (general[idx] && general[idx].source) || "영양 상식" };
  }

  var Today = { greeting: greeting, dateLabel: dateLabel, nextDose: nextDose, timeline: timeline, tip: tip, SOURCE_MINE: SOURCE_MINE };
  if (typeof window !== "undefined") window.Today = Today;
  if (typeof module !== "undefined") module.exports = Today;
})();
