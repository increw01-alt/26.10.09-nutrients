/* 나에게 맞는 영양제 찾기(finder.html) — 정적 폼(빌드 생성)을 가로채 결과를 그린다.
 * 로직은 assets/js/finder.js(순수 함수), 궁합은 D.resolvePair, 시간표는 Schedule.build, 저장은 layout.js 의 [data-my-add] 공통 처리.
 * 답변은 주소 쿼리(?age=…&concern=…)에만 담겨 공유·재방문이 되고 서버로 보내지 않는다. */
(function () {
  "use strict";
  var D = window.Data, F = window.Finder, I = window.Illus, esc = D.esc;
  var core = null, guides = null, data = null, types = {};
  var form, result, bar, progressText, errorBox, haveSearch, haveList;

  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function guideOf(slug) { return guides.filter(function (g) { return g.slug === slug; })[0]; }
  function thumb(it, cls) { return '<span class="' + cls + '">' + (I ? I.photoImg(it.category, "h-full w-full object-cover") : "") + "</span>"; }

  /* ---------- 폼 ---------- */
  function collect() {
    var a = {};
    data.questions.forEach(function (q) {
      var vals = qsa('input[name="' + q.id + '"]:checked', form).map(function (i) { return i.value; });
      if (vals.length) a[q.id] = vals;
    });
    return F.parse(F.serialize(a, data), data);   // 같은 규칙으로 정리 (최대 개수 등)
  }
  function fill(answers) {
    qsa("input[type=checkbox], input[type=radio]", form).forEach(function (i) { i.checked = false; });
    data.questions.forEach(function (q) {
      (answers[q.id] || []).forEach(function (v) {
        var input = qs('input[name="' + q.id + '"][value="' + v + '"]', form);
        if (!input && q.type === "ingredients" && core.byId[v]) input = addHaveChip(v);
        if (input) input.checked = true;
      });
    });
    updateProgress();
  }
  function updateProgress() {
    var answered = data.questions.filter(function (q) { return qsa('input[name="' + q.id + '"]:checked', form).length; }).length;
    var pct = Math.round(answered / data.questions.length * 100);
    bar.style.width = pct + "%";
    progressText.textContent = "질문 " + data.questions.length + "개 중 " + answered + "개 답함";
    qsa(".finder-q", form).forEach(function (fs) {
      var q = fs.getAttribute("data-q"), max = parseInt(fs.getAttribute("data-max") || "0", 10);
      var n = qsa('input[name="' + q + '"]:checked', fs).length;
      fs.classList.toggle("is-answered", n > 0);
      if (max) qsa('input[name="' + q + '"]', fs).forEach(function (i) { i.disabled = !i.checked && n >= max; });
    });
  }
  function onChange(e) {
    var input = e.target; if (!input || !input.name) return;
    var fs = input.closest(".finder-q");
    if (input.checked && input.getAttribute("data-exclusive")) {          // '없음' 류는 같은 질문의 다른 선택을 지운다
      qsa('input[name="' + input.name + '"]', fs).forEach(function (i) { if (i !== input) i.checked = false; });
    } else if (input.checked) {
      qsa('input[name="' + input.name + '"][data-exclusive]', fs).forEach(function (i) { i.checked = false; });
    }
    updateProgress();
  }
  function addHaveChip(id) {
    var it = core.byId[id]; if (!it) return null;
    var box = qs("#have-opts", form);
    var exist = qs('input[name="have"][value="' + id + '"]', box); if (exist) return exist;
    var label = document.createElement("label"); label.className = "finder-opt";
    label.innerHTML = '<input type="checkbox" name="have" value="' + esc(id) + '"><span>' + esc(it.name) + "</span>";
    box.appendChild(label);
    return label.querySelector("input");
  }
  function initHaveSearch() {
    if (!haveSearch) return;
    function render() {
      var q = haveSearch.value.trim();
      if (!q) { haveList.hidden = true; haveList.innerHTML = ""; return; }
      var hits = D.search(core.items, q, 6);
      haveList.innerHTML = hits.length ? hits.map(function (it) { return '<li role="option"><button type="button" data-add="' + esc(it.id) + '">' + esc(it.name) + '<small>' + esc((core.categories[it.category] || {}).label || "") + "</small></button></li>"; }).join("") : '<li class="finder-search-empty">일치하는 성분이 없어요</li>';
      haveList.hidden = false;
    }
    haveSearch.addEventListener("input", render);
    haveList.addEventListener("click", function (e) {
      var b = e.target.closest("[data-add]"); if (!b) return;
      var input = addHaveChip(b.getAttribute("data-add")); if (input) input.checked = true;
      haveSearch.value = ""; haveList.hidden = true; updateProgress();
    });
    document.addEventListener("click", function (e) { if (!e.target.closest(".finder-search")) haveList.hidden = true; });
  }

  /* ---------- 결과 ---------- */
  var FLAG_TEXT = {
    kids: { title: "어린이 기준으로 추천했어요", body: "어린이 가이드의 성분 범위 안에서만 골랐습니다. 제품 라벨의 연령 표시와 섭취량을 꼭 확인하고, 보호자가 판단해 주세요.", link: "kids-by-age" },
    teens: { title: "청소년 기준으로 추천했어요", body: "청소년·수험생 가이드의 성분 범위 안에서만 골랐습니다. 성장기에는 식사가 우선이며 제품 라벨의 연령 표시를 확인하세요.", link: "teens" },
    pregnancy: { title: "임신·수유·출산 후에는 더 신중하게", body: "해당 가이드의 성분 범위 안에서만 추천했습니다. 새 영양제를 시작하기 전에 반드시 산부인과·약사와 상의하세요.", link: "pregnancy" },
    meds: { title: "약을 복용 중이라면", body: "약과 영양제의 상호작용이 있을 수 있어 약 복용자 가이드를 함께 보여드립니다. 복용 간격과 주의 성분을 확인하고 의사·약사와 상의하세요.", link: "with-medication" },
    cancer: { title: "항암 치료 중에는 담당 의료진과 먼저", body: "치료 중 영양제는 치료 반응에 영향을 줄 수 있어 담당 의료진의 확인이 먼저입니다. 가이드는 참고용입니다.", link: "cancer-treatment" },
    kidney: { title: "신장질환·투석 중에는 제한이 많아요", body: "칼륨·마그네슘·비타민 등 일부 성분은 제한될 수 있습니다. 담당 의료진과 영양사의 안내를 우선하세요.", link: "kidney" },
    surgery: { title: "수술 전에는 중단할 성분이 있어요", body: "일부 성분은 수술 전 일정 기간 중단을 권하기도 합니다. 수술 일정을 의료진에게 알리고 복용 중인 영양제를 상의하세요.", link: "surgery" }
  };

  function pairRows(ids) {
    var rows = [];
    for (var i = 0; i < ids.length; i++) for (var j = i + 1; j < ids.length; j++) {
      var p = D.resolvePair(core, ids[i], ids[j]); if (!p) continue;
      rows.push({ a: core.byId[ids[i]], b: core.byId[ids[j]], p: p });
    }
    rows.sort(function (x, y) { return D.typeOrder[x.p.type] - D.typeOrder[y.p.type] || (y.p.level || 0) - (x.p.level || 0); });
    return rows;
  }

  function render(answers) {
    var r = F.score(answers, data, guides, core);
    var top = data._meta && data._meta.top || 5;
    var rec = r.recommended.slice(0, top), have = r.have;
    var all = rec.concat(have.filter(function (id) { return rec.indexOf(id) < 0; }));
    var labels = F.summary(answers, data);
    if (!rec.length && !r.guides.length) {
      result.innerHTML = '<div class="rounded-2xl border border-dashed border-ink-200 bg-white p-6 text-sm text-ink-600">답변과 연결되는 가이드가 아직 없어요. 고민이나 생활 상황을 하나 이상 골라 보시거나 <a class="font-bold text-brand-700 underline" href="' + D.url("guides.html") + '">전체 가이드</a>에서 찾아보세요.</div>';
      result.hidden = false; return;
    }
    var html = '<div class="finder-result-head"><p class="eyebrow-kicker"><i data-lucide="sparkles"></i> 셀프체크 결과</p>' +
      '<h2 class="text-2xl font-extrabold tracking-tight text-ink-900">' + (labels.length ? esc(labels.join(" · ")) + '<span class="block text-base font-semibold text-ink-500">에 맞춰 고른 추천 성분 ' + rec.length + '가지</span>' : "추천 성분 " + rec.length + "가지") + '</h2>' +
      '<p class="mt-2 text-sm text-ink-500">아래 가이드들이 식약처 인정 기능성을 기준으로 꼽은 핵심 성분 가운데 점수가 높은 순입니다. 특정 제품·브랜드를 보증하지 않습니다.</p></div>';

    // 주의 상자
    var flagsHtml = r.flags.map(function (f) {
      var t = FLAG_TEXT[f]; if (!t) return "";
      var g = guideOf(t.link);
      return '<div class="finder-flag"><i data-lucide="triangle-alert" class="h-5 w-5 shrink-0 text-amber-600"></i><div><p class="font-bold text-amber-900">' + esc(t.title) + '</p><p class="mt-1 text-sm text-amber-900/90">' + esc(t.body) + (g ? ' <a class="font-bold underline" href="' + D.guideUrl(g.slug) + '">' + esc(g.h1) + ' →</a>' : "") + '</p></div></div>';
    }).join("");
    if (flagsHtml) html += '<div class="mt-5 space-y-3">' + flagsHtml + "</div>";

    // 추천 성분
    html += '<section class="mt-8"><h3 class="text-lg font-extrabold text-ink-900">추천 성분</h3><div class="mt-3 grid gap-3 md:grid-cols-2">' + rec.map(function (id, n) {
      var it = core.byId[id], info = r.ingredients.filter(function (x) { return x.id === id; })[0] || { from: [] };
      var reasons = info.from.map(function (s) { var g = guideOf(s); return g ? (types[g.type] ? types[g.type].short + " · " : "") + g.h1 : s; }).slice(0, 3);
      var cat = core.categories[it.category] || {};
      return '<article class="finder-card"><div class="flex items-start gap-3">' + thumb(it, "finder-thumb") + '<div class="min-w-0 flex-1"><p class="text-xs font-bold text-brand-700">' + (n + 1) + '순위 · ' + esc(cat.label || "") + '</p>' +
        '<h4 class="text-base font-extrabold text-ink-900"><a class="hover:text-brand-700" href="' + D.ingredientUrl(id) + '">' + esc(it.name) + '</a></h4>' +
        '<p class="mt-1 text-sm text-ink-600">' + esc(it.summary || "") + '</p>' +
        (reasons.length ? '<p class="mt-2 text-xs text-ink-500"><span class="font-bold text-ink-700">근거:</span> ' + esc(reasons.join(", ")) + ' 가이드의 핵심 성분</p>' : "") +
        '<p class="mt-2 text-xs text-ink-500"><i data-lucide="clock" class="inline h-3.5 w-3.5 text-brand-600"></i> ' + esc((it.timing && it.timing.label) || "") + '</p>' +
        '<div class="mt-3 flex flex-wrap gap-2"><a class="btn-outline btn-sm" href="' + D.ingredientUrl(id) + '">자세히</a><a class="btn-outline btn-sm app-hide" href="' + D.productsUrl(id) + '">제품 찾기</a></div></div></div></article>';
    }).join("") + "</div>" +
      (r.recommended.length > rec.length ? '<p class="mt-3 text-xs text-ink-500">그다음으로 점수가 높은 성분: ' + esc(r.recommended.slice(top, top + 5).map(function (id) { return core.byId[id].name; }).join(", ")) + "</p>" : "") +
      (have.length ? '<p class="mt-3 text-sm text-ink-700"><span class="font-bold">이미 드시는 성분:</span> ' + have.map(function (id) { return '<a class="chip chip-sm" href="' + D.ingredientUrl(id) + '">' + esc(core.byId[id].name) + "</a>"; }).join(" ") + ' <span class="text-xs text-ink-500">— 추천에서는 빼고 궁합·시간표에는 넣었어요</span></p>' : "") +
      '<div class="mt-4 flex flex-wrap gap-2"><button type="button" class="btn-primary" data-my-add="' + esc(all.join(",")) + '"><i data-lucide="plus"></i>추천 성분을 내 영양제에 추가</button><a class="btn-outline" href="' + D.compatUrl(all) + '"><i data-lucide="heart-handshake"></i>궁합 체크에서 자세히</a></div></section>';

    // 궁합
    var rows = pairRows(all), cautions = rows.filter(function (x) { return x.p.type === "caution" || x.p.type === "avoid"; }), syn = rows.filter(function (x) { return x.p.type === "synergy"; });
    if (rows.length) {
      html += '<section class="mt-8"><h3 class="text-lg font-extrabold text-ink-900">이 조합의 궁합</h3><p class="mt-1 text-sm text-ink-500">추천 성분' + (have.length ? "과 이미 드시는 성분" : "") + ' ' + all.length + '가지, 조합 ' + rows.length + '쌍 — 함께 먹으면 좋아요 ' + syn.length + '쌍 · 시간을 띄우거나 주의 ' + cautions.length + '쌍</p>';
      if (cautions.length) html += '<ul class="mt-3 space-y-2">' + cautions.map(function (x) { return '<li class="finder-pair finder-pair-' + esc(x.p.type) + '"><span class="badge badge-' + esc(x.p.type) + '">' + esc((core.types[x.p.type] || {}).short || x.p.type) + '</span><div><p class="font-bold text-ink-900">' + esc(D.shortName(x.a)) + ' + ' + esc(D.shortName(x.b)) + (x.p.separateHours ? ' · ' + x.p.separateHours + '시간 간격' : "") + '</p><p class="text-sm text-ink-600">' + esc(x.p.title) + (x.p.tip ? " — " + esc(x.p.tip) : "") + '</p></div></li>'; }).join("") + "</ul>";
      if (syn.length) html += '<p class="mt-3 text-sm text-ink-700"><span class="font-bold text-emerald-700">함께 먹으면 좋아요:</span> ' + esc(syn.slice(0, 6).map(function (x) { return D.shortName(x.a) + " + " + D.shortName(x.b); }).join(", ")) + (syn.length > 6 ? " 외 " + (syn.length - 6) + "쌍" : "") + "</p>";
      if (!cautions.length) html += '<p class="mt-3 text-sm text-ink-700">시간을 띄워야 하는 조합이 없어 같은 시간에 드셔도 됩니다.</p>';
      html += "</section>";
    }

    // 시간표
    if (window.Schedule && all.length) {
      var sch = window.Schedule.build(all, core);
      html += '<section class="mt-8"><h3 class="text-lg font-extrabold text-ink-900">하루 복용 시간표</h3><div class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">' + sch.slots.map(function (s) {
        return '<div class="rounded-2xl border border-ink-100 bg-white p-4 shadow-card"><div class="flex items-center gap-2.5"><span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-cream-200 text-brand-700"><i data-lucide="' + esc(s.meta.icon) + '" class="h-5 w-5"></i></span><div><p class="font-extrabold text-ink-900">' + esc(s.meta.label) + '</p><p class="text-[11px] text-ink-400">' + esc(s.meta.sub) + '</p></div></div><ul class="mt-3 space-y-2">' +
          s.items.map(function (it) { return '<li class="flex items-center gap-2.5 text-sm">' + thumb(it, "finder-thumb finder-thumb-xs") + '<span class="min-w-0"><a class="font-bold text-ink-800 hover:text-brand-700" href="' + D.ingredientUrl(it.id) + '">' + esc(it.name) + '</a><span class="block text-xs text-ink-500">' + esc((it.timing && (it.timing.note || it.timing.label)) || "") + "</span></span></li>"; }).join("") + "</ul></div>";
      }).join("") + "</div>" +
        (sch.notes.length ? '<div class="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4"><p class="text-sm font-bold text-amber-800">시간표 메모</p><ul class="list-warn mt-1 text-sm text-amber-900">' + sch.notes.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul></div>" : "") +
        '<p class="mt-3 text-xs text-ink-400">각 성분의 일반적인 권장 시간과 간격 규칙을 바탕으로 자동 생성한 참고용 시간표입니다. 내 영양제에 추가하면 시간대를 바꾸고 알림(앱)을 받을 수 있습니다.</p></section>';
    }

    // 가이드
    var gl = r.guides.slice(0, 6).map(function (x) { return guideOf(x.slug); }).filter(Boolean);
    if (gl.length) html += '<section class="mt-8"><h3 class="text-lg font-extrabold text-ink-900">읽어볼 가이드</h3><div class="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-3">' + gl.map(function (g) {
      var t = types[g.type] || {};
      return '<a class="finder-guide" href="' + D.guideUrl(g.slug) + '"><span class="badge badge-neutral">' + esc(t.short || "") + '</span><span class="mt-2 block font-bold text-ink-900">' + esc(g.h1) + '</span><span class="mt-1 line-clamp-2 block text-xs text-ink-500">' + esc(g.description || "") + "</span></a>";
    }).join("") + "</div></section>";

    // 공유·다시
    html += '<div class="mt-8 flex flex-wrap items-center gap-2 border-t border-ink-100 pt-5"><button type="button" class="btn-outline btn-sm" id="finder-share"><i data-lucide="link"></i>결과 링크 복사</button><a class="btn-outline btn-sm" href="' + D.url("timing-chart.html") + '"><i data-lucide="calendar-days"></i>영양제 복용 시간표</a><a class="btn-outline btn-sm" href="' + D.url("compatibility-chart.html") + '"><i data-lucide="heart-handshake"></i>영양제 궁합표</a><button type="button" class="btn-outline btn-sm" id="finder-again"><i data-lucide="rotate-ccw"></i>다시 하기</button><span id="finder-copied" class="text-xs font-bold text-brand-700" hidden>링크를 복사했어요</span></div>' +
      '<p class="mt-4 text-xs text-ink-400">이 결과는 일반 건강 정보이며 의학적 진단·처방을 대신하지 않습니다. 건강기능식품은 질병의 예방·치료 목적이 아닙니다.</p>';

    result.innerHTML = html; result.hidden = false; D.icons(result);
    if (window.AppBridge && window.AppBridge.hideShopping && window.AppBridge.hideShopping()) qsa(".app-hide", result).forEach(function (el) { el.hidden = true; });
    qs("#finder-share", result).addEventListener("click", copyLink);
    qs("#finder-again", result).addEventListener("click", function () { reset(); form.scrollIntoView({ behavior: "smooth", block: "start" }); });
    try {   // 이미 모두 저장돼 있으면 layout.js 와 같은 표시 (추가 클릭 자체는 layout.js 의 [data-my-add] 공통 처리가 받는다)
      if (window.Store) {
        var saved = {}; window.Store.load().items.forEach(function (i) { saved[i.id] = true; });
        var addBtn = qs("[data-my-add]", result);
        if (addBtn && all.every(function (id) { return saved[id]; })) { addBtn.innerHTML = '<i data-lucide="check"></i>내 영양제에 있어요 · <a href="' + D.url("my.html") + '">보기</a>'; addBtn.classList.add("is-added"); D.icons(addBtn); }
      }
    } catch (e3) { /* 저장소를 못 쓰는 환경 */ }
  }

  function copyLink() {
    var url = location.href, done = qs("#finder-copied", result);
    function ok() { if (done) { done.hidden = false; setTimeout(function () { done.hidden = true; }, 2500); } }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(ok, function () { window.prompt("이 링크를 복사하세요", url); });
    else window.prompt("이 링크를 복사하세요", url);
  }
  function reset() {
    form.reset(); qsa("input", form).forEach(function (i) { i.disabled = false; });
    result.hidden = true; result.innerHTML = ""; errorBox.hidden = true;
    try { history.replaceState(null, "", location.pathname); } catch (e) { /* 무시 */ }
    updateProgress();
  }
  function submit(e) {
    if (e) e.preventDefault();
    var answers = collect();
    var missing = data.questions.filter(function (q) { return q.required && !(answers[q.id] || []).length; });
    if (missing.length) { errorBox.textContent = missing.map(function (q) { return q.title; }).join(", ") + " 항목을 골라 주세요."; errorBox.hidden = false; qs('[data-q="' + missing[0].id + '"]', form).scrollIntoView({ behavior: "smooth", block: "center" }); return; }
    errorBox.hidden = true;
    try { history.replaceState(null, "", location.pathname + "?" + F.serialize(answers, data)); } catch (e2) { /* 무시 */ }
    render(answers);
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  document.addEventListener("DOMContentLoaded", function () {
    form = qs("#finder-form"); result = qs("#result"); bar = qs("#finder-bar"); progressText = qs("#finder-progress-text"); errorBox = qs("#finder-error");
    haveSearch = qs("#have-search"); haveList = qs("#have-list");
    if (!form) return;
    Promise.all([D.core(), D.guides(), D.finder()]).then(function (res) {
      core = res[0]; guides = (res[1] && res[1].items) || []; types = (res[1] && res[1]._meta && res[1]._meta.types) || {}; data = res[2];
      form.addEventListener("change", onChange);
      form.addEventListener("submit", submit);
      qs("#finder-reset").addEventListener("click", reset);
      initHaveSearch();
      updateProgress();
      var fromUrl = F.parse(location.search, data);
      if (Object.keys(fromUrl).length) { fill(fromUrl); render(fromUrl); if (location.hash !== "#form") result.scrollIntoView({ block: "start" }); }
    }).catch(function (err) {
      console.error("[finder] 데이터 로드 실패:", err && err.message);
      errorBox.textContent = "데이터를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요."; errorBox.hidden = false;
    });
  });
})();
