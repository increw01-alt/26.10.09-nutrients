/* 장기 복용 점검 — data/longterm.json 의 근거 표(성분별 kind·weeks·note·source)로, 오래 먹고 있는 항목 가운데 점검 시점이 지난 것을 고른다.
 * 순수 함수라 Node 에서 테스트한다(tests/longterm.test.mjs). 화면은 pages/my.js(점검 카드·쉬는 중)와 pages/today.js(안내 한 줄).
 *   weeksBetween(iso, now)                시작일부터 지난 주 수(내림)
 *   check(state, rules, core, now)        → [{ key, id, name, viaProduct, kind, weeks, elapsedWeeks, note, sourceId, sourceTitle, sourceUrl }]
 * 시작일 = '계속 먹기'를 누른 날(ltCheckedAt)이 있으면 그 날, 없으면 추가한 날(addedAt). 쉬는 항목(pausedAt)은 건너뛴다.
 * 제품은 안의 성분을 각각 검사하되, 같은 성분을 따로도 먹고 있으면 따로 먹는 쪽만 한 번 알린다.
 * kind: limit(연속 섭취 기간 권고) · review(효과 판단 시점) · upper(고용량 장기 주의 → 주기적으로 상한 확인). 문구는 '점검'이지 '중단'이 아니다. */
(function () {
  "use strict";
  var S = (typeof window !== "undefined" && window.Store) || (typeof require === "function" ? require("./store.js") : null);
  var WEEK = 7 * 86400000;

  function weeksBetween(iso, now) {
    var ms = (now || new Date()) - new Date(iso);
    return ms > 0 ? Math.floor(ms / WEEK) : 0;
  }

  function check(state, rules, core, now) {
    now = now || new Date();
    var byId = {}, sources = {}, out = [], seen = {}, standalone = {};
    (((rules || {}).items) || []).forEach(function (r) { byId[r.id] = r; });
    ((((rules || {})._meta) || {}).sources || []).forEach(function (s) { sources[s.id] = s; });
    (state.items || []).forEach(function (it) { if (!S.isProduct(it.id) && !S.isPaused(it)) standalone[it.id] = true; });
    (state.items || []).forEach(function (it) {
      if (S.isPaused(it)) return;
      var start = it.ltCheckedAt || it.addedAt;
      if (!start) return;
      var elapsed = weeksBetween(start, now);
      var ids = S.isProduct(it.id) ? (it.ings || []).filter(function (id) { return !standalone[id]; }) : [it.id];
      ids.forEach(function (id) {
        var r = byId[id], k = it.id + "/" + id;
        if (!r || !core.byId[id] || elapsed < r.weeks || seen[k]) return;
        seen[k] = true;
        var src = sources[r.source] || {};
        out.push({ key: it.id, id: id, name: core.byId[id].name, viaProduct: S.isProduct(it.id) ? it.name : null, kind: r.kind, weeks: r.weeks, elapsedWeeks: elapsed,
          note: r.note, sourceId: r.source, sourceTitle: src.title || "", sourceUrl: src.url || "" });
      });
    });
    return out;
  }

  var LongTerm = { weeksBetween: weeksBetween, check: check };
  if (typeof window !== "undefined") window.LongTerm = LongTerm;
  if (typeof module !== "undefined") module.exports = LongTerm;
})();
