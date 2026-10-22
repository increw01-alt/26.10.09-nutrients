/* 셀프체크(finder.html) 로직 — 답변을 규칙(data/finder.json)으로 가이드에 잇고, 가이드의 핵심 성분을 가중 합산해 추천 성분을 고른다.
 * 순수 함수만 두어 Node 에서 테스트한다(tests/finder.test.mjs). 화면은 assets/js/pages/finder.js.
 *   parse(search, data)            주소 쿼리("?age=30s&concern=fatigue,sleep") → 답변 {질문id: [옵션id…]} (모르는 값·초과 선택 제거)
 *   serialize(answers, data)       답변 → 쿼리 문자열 (질문 순서대로)
 *   matches(cond, answers)         규칙 조건: 질문마다 하나라도 일치, 질문끼리는 AND
 *   score(answers, data, guides, core) → { guides:[{slug,score}], ingredients:[{id,score,from}], recommended:[id…], have:[id…], flags:[…], restricted,
 *                                          avoided:[id…](규칙 avoid 로 추천에서 뺀 성분, 점수순), avoidedHave:[id…](이미 먹는 성분 중 제외 대상) }
 *   summary(answers, data)         고른 옵션 라벨 목록 (결과 머리글용) */
(function () {
  "use strict";

  function trim(s) { return String(s == null ? "" : s).trim(); }
  function uniq(arr) { return arr.filter(function (v, i, a) { return a.indexOf(v) === i; }); }
  function optionIds(q) { return (q.options || []).map(function (o) { return o.id; }); }

  function parse(search, data) {
    var sp = typeof search === "string" ? new URLSearchParams(search) : (search || new URLSearchParams());
    var out = {};
    (data.questions || []).forEach(function (q) {
      var raw = sp.get(q.id);
      if (!raw) return;
      var vals = uniq(raw.split(",").map(trim).filter(Boolean));
      if (q.type !== "ingredients") { var ok = optionIds(q); vals = vals.filter(function (v) { return ok.indexOf(v) >= 0; }); }
      else vals = vals.filter(function (v) { return /^[a-z0-9-]+$/.test(v); });
      if (q.type === "single") vals = vals.slice(0, 1);
      if (q.max) vals = vals.slice(0, q.max);
      if (vals.length) out[q.id] = vals;
    });
    return out;
  }

  function serialize(answers, data) {
    var sp = new URLSearchParams();
    (data.questions || []).forEach(function (q) {
      var v = answers && answers[q.id];
      if (v && v.length) sp.set(q.id, v.join(","));
    });
    return sp.toString();
  }

  function matches(cond, answers) {
    return Object.keys(cond || {}).every(function (q) {
      var want = cond[q] || [], got = (answers && answers[q]) || [];
      return want.some(function (w) { return got.indexOf(w) >= 0; });
    });
  }

  function score(answers, data, guides, core) {
    answers = answers || {};
    var bySlug = {};
    (guides || []).forEach(function (g) { bySlug[g.slug] = g; });
    var gScore = {}, flags = {}, restrict = null, avoid = {};
    (data.rules || []).forEach(function (r) {
      if (!matches(r["if"], answers)) return;
      var w = r.weight || 1;
      (r.guides || []).forEach(function (s) { if (bySlug[s]) gScore[s] = (gScore[s] || 0) + w; });
      (r.flags || []).forEach(function (f) { flags[f] = true; });
      (r.avoid || []).forEach(function (id) { avoid[id] = true; });   // 항응고제·수술 예정 등: 출혈 경향 성분을 추천에서 뺀다
      if (r.restrictTo && r.restrictTo.length) {
        restrict = restrict || {};
        r.restrictTo.forEach(function (s) { ((bySlug[s] && bySlug[s].ingredients) || []).forEach(function (i) { restrict[i.id] = true; }); });
      }
    });
    var have = (answers.have || []).filter(function (id) { return !core || !core.byId || !!core.byId[id]; });
    var iScore = {}, from = {};
    Object.keys(gScore).forEach(function (s) {
      (bySlug[s].ingredients || []).forEach(function (ing, idx) {
        if (core && core.byId && !core.byId[ing.id]) return;
        iScore[ing.id] = (iScore[ing.id] || 0) + gScore[s] / (1 + 0.3 * idx);   // 가이드 점수 × 핵심 성분 순서 가중(앞일수록 큼)
        (from[ing.id] = from[ing.id] || []).push(s);
      });
    });
    var byScore = function (a, b) { return iScore[b] - iScore[a] || a.localeCompare(b); };
    var ranked = Object.keys(iScore)
      .filter(function (id) { return (!restrict || restrict[id]) && !avoid[id]; })
      .sort(byScore);
    var avoided = Object.keys(iScore).filter(function (id) { return avoid[id] && (!restrict || restrict[id]); }).sort(byScore);
    var guidesRanked = Object.keys(gScore).sort(function (a, b) { return gScore[b] - gScore[a] || a.localeCompare(b); });
    return {
      guides: guidesRanked.map(function (s) { return { slug: s, score: gScore[s] }; }),
      ingredients: ranked.map(function (id) { return { id: id, score: iScore[id], from: uniq(from[id]) }; }),
      recommended: ranked.filter(function (id) { return have.indexOf(id) < 0; }),
      have: have,
      flags: Object.keys(flags),
      restricted: !!restrict,
      avoided: avoided,
      avoidedHave: have.filter(function (id) { return !!avoid[id]; })
    };
  }

  function summary(answers, data) {
    var out = [];
    (data.questions || []).forEach(function (q) {
      var v = (answers && answers[q.id]) || [];
      if (!v.length || q.type === "ingredients") return;
      v.forEach(function (id) {
        var o = (q.options || []).filter(function (x) { return x.id === id; })[0];
        if (o && !o.exclusive) out.push(o.label);
      });
    });
    return out;
  }

  var Finder = { parse: parse, serialize: serialize, matches: matches, score: score, summary: summary };
  if (typeof window !== "undefined") window.Finder = Finder;
  if (typeof module !== "undefined") module.exports = Finder;
})();
