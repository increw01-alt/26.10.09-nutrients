/* 내 영양제에 성분·제품을 추가한 직후 보여 주는 요약 — 배정된 시간대와 이유, 다른 항목과의 궁합을 네 가지로 분류한다.
 * 순수 함수라 Node 에서 테스트한다(tests/addsummary.test.mjs — resolvePair·josa 를 주입). 화면은 pages/my.js 의 바텀 시트.
 *   build(core, entries, key, sched, opts) → { title, subtitle, slotKey, slotLabel, time, reason, pairs: [{ key, name, kind, title, detail }], okNames, unknownNames }
 *   entries: Store.entries(state) 꼴(성분 id 또는 { id:"p:…", name, ings }), key: 방금 추가한 항목, sched: Schedule.build 결과(assign·notes),
 *   opts: { resolvePair?, josa?, times: {시간대: "HH:MM"}, slotLabel: {시간대: 라벨} }
 * 분류(우선순위): dup 겹쳐요(같은 성분이 제품과 따로, 또는 두 제품에) > care 간격 두기·주의(caution/avoid) > good 함께 먹으면 좋아요(synergy) > ok 무난. ok 는 okNames 로만 모은다.
 * 어느 쪽이든 성분 정보가 없으면(성분 연결 안 된 제품) 판단 근거가 없으므로 '무난'이 아니라 unknownNames 로 따로 돌려준다("성분 정보가 없어 궁합을 볼 수 없어요"). */
(function () {
  "use strict";
  var ORDER = { dup: 0, care: 1, good: 2 };

  function norm(e, core) {
    if (typeof e === "string") { var it = core.byId[e]; return it ? { key: e, name: it.name, kind: "ingredient", ings: [e] } : null; }
    if (!e || typeof e.id !== "string" || !e.id) return null;
    return { key: e.id, name: e.name || e.id, kind: "product", ings: (e.ings || []).filter(function (id) { return !!core.byId[id]; }) };
  }
  function nameOf(core, id) { return core.byId[id] ? core.byId[id].name : id; }
  function withJosa(opts, name, kind) {
    if (opts.josa) return opts.josa(name, kind);
    if (typeof window !== "undefined" && window.Data && window.Data.josa) return window.Data.josa(name, kind);
    return name + (kind === "을를" ? "을(를)" : kind === "은는" ? "은(는)" : "과(와)");
  }

  /* 새 항목(me)과 다른 항목(other)의 관계 한 줄 */
  function classify(core, me, other, resolvePair) {
    if (!me.ings.length || !other.ings.length) return { kind: "unknown", title: other.name + " — 성분 정보 없음", detail: "" };
    var shared = me.ings.filter(function (id) { return other.ings.indexOf(id) >= 0; });
    if (shared.length) {
      var first = core.byId[shared[0]], upper = first && first.dosage && first.dosage.upper;
      return { kind: "dup", title: other.name + " — 같은 성분이 겹쳐요",
        detail: shared.map(function (id) { return nameOf(core, id); }).join("·") + "이(가) 둘 다 들어 있어요" + (upper ? " · 합쳐서 상한(" + upper + ") 안이면 괜찮아요" : "") };
    }
    var best = null;   // 성분 쌍 가운데 가장 강한 관계: 주의(1) > 시너지(2) > 무난(3), 주의끼리는 간격이 긴 것
    me.ings.forEach(function (a) {
      other.ings.forEach(function (b) {
        var p = resolvePair ? resolvePair(core, a, b) : null;
        if (!p) return;
        var rank = (p.type === "caution" || p.type === "avoid") ? 1 : (p.type === "synergy" ? 2 : 3);
        if (!best || rank < best.rank || (rank === best.rank && (p.separateHours || 0) > (best.p.separateHours || 0))) best = { rank: rank, p: p, a: a, b: b };
      });
    });
    if (!best || best.rank === 3) return { kind: "ok", title: other.name + " — 무난해요", detail: "" };
    var who = (me.kind === "product" || other.kind === "product") ? " (" + nameOf(core, best.a) + "·" + nameOf(core, best.b) + ")" : "";
    var text = best.p.title || best.p.tip || "";
    if (best.rank === 1) {
      var h = best.p.separateHours || 0;
      return { kind: "care", title: other.name + " — " + (h ? h + "시간 간격" : "주의"), detail: text + who };
    }
    return { kind: "good", title: other.name + " — 함께 먹으면 좋아요", detail: text + who };
  }

  function build(core, entries, key, sched, opts) {
    opts = opts || {};
    var resolvePair = opts.resolvePair || (typeof window !== "undefined" && window.Data ? window.Data.resolvePair : null);
    var items = (entries || []).map(function (e) { return norm(e, core); }).filter(Boolean);
    var me = items.filter(function (x) { return x.key === key; })[0];
    if (!me) return null;
    var slotKey = (sched && sched.assign && sched.assign[key]) || "morning_after";
    var slotLabel = (opts.slotLabel && opts.slotLabel[slotKey]) || slotKey;
    var time = (opts.times && opts.times[slotKey]) || "";

    var subtitle = me.kind === "product" ? (me.ings.length ? "제품 · 한 알에 " + me.ings.length + "가지" : "제품 · 성분 정보 없음") : "";
    var note = ((sched && sched.notes) || []).filter(function (n) { return n.indexOf(me.name) >= 0; })[0];
    var reason;
    if (note) reason = note;
    else if (me.kind === "ingredient") { var t = core.byId[key].timing || {}; reason = t.note || ((t.label || slotLabel) + " 권장"); }
    else reason = "한 알에 든 성분은 나누지 않고 제품째로 배정해요." + (me.ings.length ? " " + slotLabel + " 권장이 가장 많아요." : "");

    var pairs = [], okNames = [], unknownNames = [];
    items.forEach(function (other) {
      if (other.key === key) return;
      var c = classify(core, me, other, resolvePair);
      if (c.kind === "ok") okNames.push(other.name);
      else if (c.kind === "unknown") unknownNames.push(other.name);
      else pairs.push({ key: other.key, name: other.name, kind: c.kind, title: c.title, detail: c.detail });
    });
    pairs.sort(function (a, b) { return ORDER[a.kind] - ORDER[b.kind]; });

    return { title: withJosa(opts, me.name, "을를") + " 추가했어요", subtitle: subtitle, slotKey: slotKey, slotLabel: slotLabel, time: time, reason: reason, pairs: pairs, okNames: okNames, unknownNames: unknownNames };
  }

  var AddSummary = { build: build, classify: classify };
  if (typeof window !== "undefined") window.AddSummary = AddSummary;
  if (typeof module !== "undefined") module.exports = AddSummary;
})();
