/* 셀프체크(finder.html) 로직 — 답변을 규칙(data/finder.json)으로 가이드에 잇고, 가이드의 핵심 성분을 가중 합산해 추천 성분을 고른다.
 * 순수 함수만 두어 Node 에서 테스트한다(tests/finder.test.mjs). 화면은 assets/js/pages/finder.js.
 *   parse(search, data)            주소 쿼리("?age=30s&concern=fatigue,sleep") → 답변 {질문id: [옵션id…]} (모르는 값·초과 선택 제거)
 *   serialize(answers, data)       답변 → 쿼리 문자열 (질문 순서대로)
 *   matches(cond, answers)         규칙 조건: 질문마다 하나라도 일치, 질문끼리는 AND
 *   score(answers, data, guides, core) → { guides:[{slug,score}], ingredients:[{id,score,from}], recommended:[id…], have:[id…], flags:[…], restricted,
 *                                          avoided:[id…](규칙 avoid 로 추천에서 뺀 성분, 점수순), avoidedHave:[id…](이미 먹는 성분 중 제외 대상) }
 *   summary(answers, data)         고른 옵션 라벨 목록 (결과 머리글용)
 *   reasons(answers, data, slugs)  맞춤 추천의 '왜' 칩 — slugs 가이드를 고른 규칙 조건 중 내가 답한 라벨 */
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

  /* 맞춤 추천의 '왜' 칩: slugs(추천 성분에 점수를 준 가이드)를 고른 규칙들의 조건 가운데 내가 답한 옵션의 라벨 — 질문 순서 → 옵션 순서, 중복 없이, exclusive 옵션 제외 */
  function reasons(answers, data, slugs) {
    var want = {};
    (data.rules || []).forEach(function (r) {
      if (!matches(r["if"], answers)) return;
      if (!(r.guides || []).some(function (s) { return (slugs || []).indexOf(s) >= 0; })) return;
      Object.keys(r["if"] || {}).forEach(function (q) { (want[q] = want[q] || []).push.apply(want[q], r["if"][q]); });
    });
    var out = [];
    (data.questions || []).forEach(function (q) {
      var got = (answers && answers[q.id]) || [], cond = want[q.id] || [];
      (q.options || []).forEach(function (o) {
        if (o.exclusive || got.indexOf(o.id) < 0 || cond.indexOf(o.id) < 0 || out.indexOf(o.label) >= 0) return;
        out.push(o.label);
      });
    });
    return out;
  }

  /* 결과의 주의 상자 문구(flags) — 셀프체크(pages/finder.js)와 맞춤 추천(pages/recommend.js)이 공유. link 는 가이드 slug */
  var FLAG_TEXT = {
    kids: { title: "어린이 기준으로 추천했어요", body: "어린이 가이드의 성분 범위 안에서만 골랐습니다. 제품 라벨의 연령 표시와 섭취량을 꼭 확인하고, 보호자가 판단해 주세요.", link: "kids-by-age" },
    teens: { title: "청소년 기준으로 추천했어요", body: "청소년·수험생 가이드의 성분 범위 안에서만 골랐습니다. 성장기에는 식사가 우선이며 제품 라벨의 연령 표시를 확인하세요.", link: "teens" },
    pregnancy: { title: "임신·수유·출산 후에는 더 신중하게", body: "해당 가이드의 성분 범위 안에서만 추천했습니다. 새 영양제를 시작하기 전에 반드시 산부인과·약사와 상의하세요.", link: "pregnancy" },
    meds: { title: "약을 복용 중이라면", body: "약과 영양제의 상호작용이 있을 수 있어 약 복용자 가이드를 함께 보여드립니다. 복용 간격과 주의 성분을 확인하고 의사·약사와 상의하세요.", link: "with-medication" },
    cancer: { title: "항암 치료 중에는 담당 의료진과 먼저", body: "치료 중 영양제는 치료 반응에 영향을 줄 수 있어 담당 의료진의 확인이 먼저입니다. 가이드는 참고용입니다.", link: "cancer-treatment" },
    kidney: { title: "신장질환·투석 중에는 제한이 많아요", body: "칼륨·마그네슘·비타민 등 일부 성분은 제한될 수 있습니다. 담당 의료진과 영양사의 안내를 우선하세요.", link: "kidney" },
    surgery: { title: "수술 전에는 중단할 성분이 있어요", body: "출혈 경향이 있는 성분(오메가3·은행잎·마늘·비타민E·홍삼·커큐민·나토키나제 등)은 추천에서 뺐습니다. 수술 일정을 의료진에게 알리고 복용 중인 영양제의 중단·재개 시점을 상의하세요.", link: "surgery" },
    bleeding: { title: "항응고제·항혈소판제를 드신다면 출혈 경향 성분은 뺐어요", body: "혈소판·응고에 작용하는 성분(은행잎·나토키나제·오메가3·비타민E·홍삼·마늘·커큐민 등)과 와파린 효과를 바꾸는 성분(비타민K·코엔자임Q10·클로렐라)은 추천에서 제외했습니다. 새 영양제는 반드시 의사·약사와 상의하고 임의로 시작·중단하지 마세요.", link: "with-medication" }
  };

  var Finder = { parse: parse, serialize: serialize, matches: matches, score: score, summary: summary, reasons: reasons, FLAG_TEXT: FLAG_TEXT };
  if (typeof window !== "undefined") window.Finder = Finder;
  if (typeof module !== "undefined") module.exports = Finder;
})();
