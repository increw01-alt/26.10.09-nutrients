/* 선택한 성분들로 하루 복용 시간표를 만드는 로직 */
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

  function build(ids, core) {
    var assign = {};
    var notes = [];
    ids.forEach(function (id) {
      var it = core.byId[id];
      if (it) assign[id] = (it.timing && it.timing.slot) || "morning_after";
    });

    function conflicts(id) {
      return ids.filter(function (o) {
        if (o === id || assign[o] !== assign[id]) return false;
        var p = window.Data.findPair(core, id, o);
        return p && (p.separateHours || 0) >= 1;
      });
    }

    // 간격이 필요한 쌍이 같은 시간대에 있으면 대체 시간대로 이동 (최대 3회 반복)
    for (var round = 0; round < 3; round++) {
      var moved = false;
      ids.forEach(function (id) {
        var cf = conflicts(id);
        if (!cf.length) return;
        var it = core.byId[id];
        var alts = (it.timing && it.timing.altSlots) || [];
        for (var i = 0; i < alts.length; i++) {
          var prev = assign[id];
          assign[id] = alts[i];
          if (!conflicts(id).length) {
            moved = true;
            notes.push(it.name + "은(는) " + core.byId[cf[0]].name + "과(와) 간격을 두기 위해 " + SLOT_META[alts[i]].label + "(으)로 옮겼습니다.");
            return;
          }
          assign[id] = prev;
        }
      });
      if (!moved) break;
    }

    // 끝까지 해결되지 않은 충돌은 안내
    ids.forEach(function (id) {
      conflicts(id).forEach(function (o) {
        if (id < o) {
          var p = window.Data.findPair(core, id, o);
          notes.push(core.byId[id].name + "과(와) " + core.byId[o].name + "은(는) " + (p.separateHours || 2) + "시간 이상 간격을 두세요. 같은 시간대라면 하나를 다른 끼니로 옮기세요.");
        }
      });
    });

    var slots = SLOT_ORDER.map(function (s) {
      return { key: s, meta: SLOT_META[s], items: ids.filter(function (id) { return assign[id] === s; }).map(function (id) { return core.byId[id]; }) };
    }).filter(function (s) { return s.items.length; });

    return { slots: slots, notes: notes.filter(function (n, i, a) { return a.indexOf(n) === i; }) };
  }

  window.Schedule = { build: build, SLOT_META: SLOT_META, SLOT_ORDER: SLOT_ORDER };
})();
