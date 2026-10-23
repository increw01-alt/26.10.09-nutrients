/* 선택한 성분·제품들로 하루 복용 시간표를 만드는 로직. 순수 함수라 Node 에서 테스트한다(tests/schedule.test.mjs — resolvePair 를 주입).
 * 항목(entries)은 성분 id 문자열 또는 제품 객체 { id: "p:…", name, ings: [성분id…] }. 제품은 한 알에 든 성분을 나눌 수 없으므로
 * 한 시간대에 통째로 배정하고(기본 = 안의 성분 권장 시간대의 최빈값, 동률이면 아침 식후), 같은 제품 안 성분끼리는 충돌로 보지 않는다. */
(function () {
  "use strict";
  var SLOT_ORDER = ["morning_empty", "morning_after", "before_meal", "lunch_after", "evening_after", "bedtime"];
  var SLOT_META = {
    morning_empty: { label: "아침 공복", sub: "기상 직후, 식사 30분 전", icon: "sunrise" },
    morning_after: { label: "아침 식후", sub: "아침 식사 직후", icon: "coffee" },
    before_meal: { label: "식전", sub: "점심·저녁 식사 30분 전", icon: "timer" },
    lunch_after: { label: "점심 식후", sub: "점심 식사 직후", icon: "utensils" },
    evening_after: { label: "저녁 식후", sub: "저녁 식사 직후", icon: "sunset" },
    bedtime: { label: "취침 전", sub: "잠들기 30~60분 전", icon: "bed" }
  };
  var PRODUCT_ALTS = ["morning_after", "evening_after", "lunch_after"];   // 제품을 옮길 때의 대체 시간대 순서(기본값은 뺀다)

  /* 제품 기본 시간대: 안의 성분 권장 시간대 최빈값, 동률·빈 목록이면 아침 식후 */
  function productSlot(ings, core) {
    var count = {}, best = 0;
    (ings || []).forEach(function (id) {
      var it = core.byId[id], s = it && it.timing && it.timing.slot;
      if (!s) return;
      count[s] = (count[s] || 0) + 1;
      if (count[s] > best) best = count[s];
    });
    var tops = SLOT_ORDER.filter(function (s) { return best > 0 && count[s] === best; });
    return tops.length === 1 ? tops[0] : "morning_after";
  }

  /* entries → 내부 항목 { key, kind, ings:[성분id], it?|name } (사전에 없는 성분 id 는 건너뛴다) */
  function normalize(entries, core) {
    var out = [];
    (entries || []).forEach(function (e) {
      if (typeof e === "string") { if (core.byId[e]) out.push({ key: e, kind: "ingredient", ings: [e], it: core.byId[e] }); return; }
      if (!e || typeof e.id !== "string" || !e.id) return;
      out.push({ key: e.id, kind: "product", name: e.name || e.id, ings: (e.ings || []).filter(function (id) { return !!core.byId[id]; }) });
    });
    return out;
  }

  /* entries: 성분 id·제품 객체 목록, overrides: { key: 시간대 } — 사용자가 직접 바꾼 시간대는 그대로 두고(자동 이동 안 함) 다른 항목만 옮긴다.
     opts.resolvePair(core, a, b) 를 주면 그것을, 없으면 window.Data.resolvePair 를 쓴다. 충돌이 남으면 메모로 안내 */
  function build(entries, core, overrides, opts) {
    overrides = overrides || {}; opts = opts || {};
    var resolvePair = opts.resolvePair || (typeof window !== "undefined" && window.Data ? window.Data.resolvePair : null);
    var items = normalize(entries, core), assign = {}, notes = [];
    items.forEach(function (x) {
      assign[x.key] = overrides[x.key] || (x.kind === "product" ? productSlot(x.ings, core) : ((x.it.timing && x.it.timing.slot) || "morning_after"));
    });
    function nameOf(x) { return x.kind === "product" ? x.name : x.it.name; }
    function altsOf(x) {
      if (x.kind === "product") { var d = productSlot(x.ings, core); return PRODUCT_ALTS.filter(function (s) { return s !== d; }); }
      return (x.it.timing && x.it.timing.altSlots) || [];
    }
    /* 두 항목 사이에 필요한 간격(시간) — 성분 쌍 전부 중 가장 큰 값, 없으면 0. 데이터에 없는 쌍도 규칙(차전자피·키토산 2시간 간격)을 적용 */
    function gap(x, y) {
      var h = 0;
      if (!resolvePair) return 0;
      x.ings.forEach(function (a) { y.ings.forEach(function (b) { var p = resolvePair(core, a, b); if (p && (p.separateHours || 0) > h) h = p.separateHours; }); });
      return h;
    }
    function conflicts(x) {
      return items.filter(function (y) { return y.key !== x.key && assign[y.key] === assign[x.key] && gap(x, y) >= 1; });
    }

    // 간격이 필요한 쌍이 같은 시간대에 있으면 대체 시간대로 이동 (최대 3회 반복)
    for (var round = 0; round < 3; round++) {
      var moved = false;
      items.forEach(function (x) {
        if (overrides[x.key]) return;   // 사용자가 정한 시간대는 옮기지 않는다
        var cf = conflicts(x);
        if (!cf.length) return;
        var alts = altsOf(x);
        for (var i = 0; i < alts.length; i++) {
          var prev = assign[x.key];
          assign[x.key] = alts[i];
          if (!conflicts(x).length) {
            moved = true;
            notes.push(nameOf(x) + "은(는) " + nameOf(cf[0]) + "과(와) 간격을 두기 위해 " + SLOT_META[alts[i]].label + "(으)로 옮겼습니다.");
            return;
          }
          assign[x.key] = prev;
        }
      });
      if (!moved) break;
    }

    // 끝까지 해결되지 않은 충돌은 안내
    items.forEach(function (x) {
      conflicts(x).forEach(function (y) {
        if (x.key < y.key) notes.push(nameOf(x) + "과(와) " + nameOf(y) + "은(는) " + (gap(x, y) || 2) + "시간 이상 간격을 두세요. 같은 시간대라면 하나를 다른 끼니로 옮기세요.");
      });
    });

    var slots = SLOT_ORDER.map(function (s) {
      return { key: s, meta: SLOT_META[s], items: items.filter(function (x) { return assign[x.key] === s; }).map(function (x) {
        return x.kind === "product" ? { id: x.key, name: x.name, kind: "product", ings: x.ings.map(function (id) { return core.byId[id]; }) } : x.it;
      }) };
    }).filter(function (s) { return s.items.length; });

    return { slots: slots, assign: assign, notes: notes.filter(function (n, i, a) { return a.indexOf(n) === i; }) };   // assign: key → 실제 배정 시간대
  }

  var Schedule = { build: build, productSlot: productSlot, SLOT_META: SLOT_META, SLOT_ORDER: SLOT_ORDER };
  if (typeof window !== "undefined") window.Schedule = Schedule;
  if (typeof module !== "undefined") module.exports = Schedule;
})();
