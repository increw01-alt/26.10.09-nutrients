/* 궁합 체크 페이지 */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var MAX = 8;
  var selected = [];
  var core = null;

  function parseInitial() {
    var items = D.qs("items") || "";
    var a = D.qs("a"), b = D.qs("b");
    var ids = items.split(",").concat([a, b]).map(function (s) { return (s || "").trim(); }).filter(Boolean);
    return ids.filter(function (x, i, arr) { return arr.indexOf(x) === i; });
  }

  function syncUrl() {
    try {
      var u = new URL(location.href);
      u.search = selected.length ? "?items=" + selected.map(encodeURIComponent).join(",") : "";
      history.replaceState(null, "", u.toString());
    } catch (e) {}
  }

  function add(id) {
    if (!core.byId[id] || selected.indexOf(id) >= 0) return;
    if (selected.length >= MAX) { showToast("최대 " + MAX + "개까지 선택할 수 있어요."); return; }
    selected.push(id); update();
  }
  function remove(id) { selected = selected.filter(function (x) { return x !== id; }); update(); }

  function showToast(msg) {
    var t = document.createElement("div");
    t.className = "fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-full bg-ink-900 px-4 py-2 text-sm font-semibold text-white shadow-lg";
    t.textContent = msg; document.body.appendChild(t); setTimeout(function () { t.remove(); }, 2200);
  }

  /* 선택 UI */
  function renderPicker() {
    var chips = document.getElementById("selected-chips");
    chips.innerHTML = selected.length ? selected.map(function (id) {
      var it = core.byId[id];
      return '<span class="inline-flex items-center gap-1.5 rounded-full bg-brand-700 py-1.5 pl-3 pr-1.5 text-sm font-bold text-white"><i data-lucide="' + esc(it.icon || "pill") + '" class="h-3.5 w-3.5"></i>' + esc(it.name) + '<button type="button" class="grid h-6 w-6 place-items-center rounded-full hover:bg-white/20" data-remove="' + esc(id) + '" aria-label="' + esc(it.name) + ' 제거"><i data-lucide="x" class="h-3.5 w-3.5"></i></button></span>';
    }).join("") : '<span class="text-sm text-ink-400">아래 목록에서 성분을 선택하거나 검색하세요. (2개 이상)</span>';
    var counter = document.getElementById("selected-count"); counter.textContent = selected.length + " / " + MAX;
    document.querySelectorAll("#picker-grid [data-pick]").forEach(function (b) {
      var on = selected.indexOf(b.getAttribute("data-pick")) >= 0;
      b.classList.toggle("active", on); b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    D.icons(chips);
  }

  function buildPickerGrid() {
    var grid = document.getElementById("picker-grid");
    var cats = core.categories;
    grid.innerHTML = Object.keys(cats).map(function (k) {
      var items = core.items.filter(function (i) { return i.category === k; });
      if (!items.length) return "";
      return '<div class="picker-group" data-group="' + esc(k) + '"><h3 class="mb-2 flex items-center gap-1.5 text-xs font-bold text-ink-500"><i data-lucide="' + esc(cats[k].icon) + '" class="h-3.5 w-3.5"></i>' + esc(cats[k].label) + '</h3><div class="flex flex-wrap gap-2">' +
        items.map(function (it) { return '<button type="button" class="chip" data-pick="' + esc(it.id) + '" data-name="' + esc(it.name + " " + (it.aliases || []).join(" ")) + '">' + esc(it.name) + '</button>'; }).join("") + "</div></div>";
    }).join("");
    grid.addEventListener("click", function (e) {
      var b = e.target.closest("[data-pick]"); if (!b) return;
      var id = b.getAttribute("data-pick");
      if (selected.indexOf(id) >= 0) remove(id); else add(id);
    });
    var filter = document.getElementById("picker-filter");
    filter.addEventListener("input", function () {
      var q = filter.value.trim().toLowerCase();
      grid.querySelectorAll("[data-pick]").forEach(function (b) { b.classList.toggle("hidden", !!q && b.getAttribute("data-name").toLowerCase().indexOf(q) < 0); });
      grid.querySelectorAll(".picker-group").forEach(function (g) { g.classList.toggle("hidden", !g.querySelector("[data-pick]:not(.hidden)")); });
    });
    D.icons(grid);
  }

  /* 결과 */
  function pairResults() {
    var out = [];
    for (var i = 0; i < selected.length; i++) for (var j = i + 1; j < selected.length; j++) {
      var p = D.findPair(core, selected[i], selected[j]);
      out.push({ a: core.byId[selected[i]], b: core.byId[selected[j]], pair: p, type: p ? p.type : "unknown" });
    }
    out.sort(function (x, y) { return D.typeOrder[x.type] - D.typeOrder[y.type] || ((y.pair && y.pair.level) || 0) - ((x.pair && x.pair.level) || 0); });
    return out;
  }

  function resultCard(r) {
    var t = core.types[r.type] || { label: "알려진 상호작용 없음", short: "정보 없음", icon: "circle-help" };
    var title = r.pair ? r.pair.title : "특별히 알려진 상호작용이 없습니다";
    var detail = r.pair ? r.pair.detail : "현재 데이터베이스에 두 성분 간 주의할 상호작용이 등록되어 있지 않습니다. 일반적인 용량에서는 함께 섭취해도 무방한 경우가 많지만, 각 성분의 상한 섭취량과 섭취 시간 권장을 지켜 주세요.";
    var tip = r.pair ? r.pair.tip : "";
    return '<article class="rounded-2xl border p-5 shadow-card card-' + r.type + ' fade-up">' +
      '<div class="flex flex-wrap items-center justify-between gap-2"><span class="badge ' + D.typeClass(r.type) + '"><i data-lucide="' + esc(t.icon) + '" class="h-3.5 w-3.5"></i>' + esc(t.short) + '</span>' +
      (r.pair && r.pair.separateHours ? '<span class="inline-flex items-center gap-1 text-xs font-bold text-amber-700"><i data-lucide="clock" class="h-3.5 w-3.5"></i>' + r.pair.separateHours + '시간 이상 간격</span>' : "") + '</div>' +
      '<h3 class="mt-3 text-lg font-extrabold text-ink-900"><a class="hover:text-brand-700" href="' + D.ingredientUrl(r.a.id) + '">' + esc(r.a.name) + '</a> <span class="text-ink-300">+</span> <a class="hover:text-brand-700" href="' + D.ingredientUrl(r.b.id) + '">' + esc(r.b.name) + '</a></h3>' +
      '<p class="mt-1 font-semibold text-ink-800">' + esc(title) + '</p>' +
      '<p class="mt-2 text-sm leading-relaxed text-ink-600">' + esc(detail) + '</p>' +
      (tip ? '<p class="mt-3 flex items-start gap-2 rounded-xl bg-white/80 p-3 text-sm text-ink-700 ring-1 ring-ink-100"><i data-lucide="lightbulb" class="mt-0.5 h-4 w-4 shrink-0 text-amber-500"></i><span><strong>이렇게 드세요:</strong> ' + esc(tip) + '</span></p>' : "") +
      '</article>';
  }

  function renderMatrix() {
    var wrap = document.getElementById("matrix-wrap");
    if (selected.length < 3) { wrap.classList.add("hidden"); return; }
    wrap.classList.remove("hidden");
    var head = '<tr><th></th>' + selected.map(function (id) { return '<th scope="col"><span class="line-clamp-2">' + esc(core.byId[id].name) + '</span></th>'; }).join("") + "</tr>";
    var rows = selected.map(function (ra) {
      return '<tr><th scope="row" class="text-left"><span class="line-clamp-2">' + esc(core.byId[ra].name) + '</span></th>' + selected.map(function (cb) {
        if (ra === cb) return '<td class="cell-self"></td>';
        var p = D.findPair(core, ra, cb); var type = p ? p.type : "unknown";
        var sym = { synergy: "○", caution: "△", avoid: "✕", neutral: "–", unknown: "·" }[type];
        return '<td class="cell-' + type + '"><a href="' + D.compatUrl([ra, cb]) + '" title="' + esc(core.byId[ra].name + " + " + core.byId[cb].name + (p ? ": " + p.title : "")) + '">' + sym + "</a></td>";
      }).join("") + "</tr>";
    }).join("");
    document.getElementById("matrix").innerHTML = "<thead>" + head + "</thead><tbody>" + rows + "</tbody>";
  }

  function renderSchedule() {
    var el = document.getElementById("schedule");
    if (selected.length < 1) { el.innerHTML = ""; return; }
    var sch = window.Schedule.build(selected, core);
    el.innerHTML = '<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">' + sch.slots.map(function (s) {
      return '<div class="rounded-2xl border border-ink-100 bg-white p-4 shadow-card"><div class="flex items-center gap-2"><span class="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-700"><i data-lucide="' + esc(s.meta.icon) + '" class="h-4 w-4"></i></span><div><p class="font-extrabold text-ink-900">' + esc(s.meta.label) + '</p><p class="text-[11px] text-ink-400">' + esc(s.meta.sub) + '</p></div></div><ul class="mt-3 space-y-1.5">' +
        s.items.map(function (it) { return '<li class="flex items-start gap-2 text-sm"><i data-lucide="' + esc(it.icon || "pill") + '" class="mt-0.5 h-4 w-4 shrink-0 text-ink-400"></i><span><a class="font-bold text-ink-800 hover:text-brand-700" href="' + D.ingredientUrl(it.id) + '">' + esc(it.name) + '</a><span class="block text-xs text-ink-500">' + esc(it.timing.note || it.timing.label) + '</span></span></li>'; }).join("") + "</ul></div>";
    }).join("") + "</div>" +
      (sch.notes.length ? '<div class="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4"><p class="text-sm font-bold text-amber-800">시간표 메모</p><ul class="list-warn mt-1 text-sm text-amber-900">' + sch.notes.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul></div>" : "") +
      '<p class="mt-3 text-xs text-ink-400">각 성분의 일반적인 권장 시간과 간격 규칙을 바탕으로 자동 생성한 참고용 시간표입니다. 제품 라벨의 섭취 방법과 전문가 안내를 우선하세요.</p>';
    D.icons(el);
  }

  function renderResults() {
    var wrap = document.getElementById("results-wrap"), list = document.getElementById("results"), summary = document.getElementById("summary"), empty = document.getElementById("results-empty");
    if (selected.length < 2) {
      wrap.classList.add("hidden"); empty.classList.remove("hidden");
      empty.innerHTML = selected.length === 1 ? '<p class="text-sm text-ink-500">1개 선택됨 — <strong>' + esc(core.byId[selected[0]].name) + '</strong>과(와) 함께 먹는 영양제를 하나 더 선택하세요.</p>' : '<p class="text-sm text-ink-500">성분을 2개 이상 선택하면 결과가 표시됩니다.</p>';
      renderSchedule(); return;
    }
    empty.classList.add("hidden"); wrap.classList.remove("hidden");
    var res = pairResults();
    var cnt = { synergy: 0, caution: 0, avoid: 0, neutral: 0, unknown: 0 };
    res.forEach(function (r) { cnt[r.type]++; });
    var verdict, vcls;
    if (cnt.avoid) { verdict = "병용을 피하거나 전문가 상담이 필요한 조합이 있어요"; vcls = "from-rose-500 to-rose-600"; }
    else if (cnt.caution) { verdict = "함께 먹어도 되지만 시간을 나누면 더 좋은 조합이 있어요"; vcls = "from-amber-500 to-orange-500"; }
    else if (cnt.synergy) { verdict = "서로 도움이 되는 좋은 조합이에요"; vcls = "from-emerald-500 to-brand-600"; }
    else { verdict = "특별한 주의 사항이 없는 무난한 조합이에요"; vcls = "from-ink-600 to-ink-800"; }
    summary.innerHTML = '<div class="rounded-2xl bg-gradient-to-r ' + vcls + ' p-5 text-white shadow-lift"><p class="text-xs font-bold uppercase tracking-wide text-white/80">' + selected.length + '개 성분 · ' + res.length + '개 조합 분석</p><h2 class="mt-1 text-xl font-extrabold sm:text-2xl">' + esc(verdict) + '</h2>' +
      '<div class="mt-4 flex flex-wrap gap-2 text-xs font-bold">' + [["synergy", "좋은 궁합"], ["caution", "주의"], ["avoid", "피하기"], ["neutral", "무난"], ["unknown", "정보 없음"]].map(function (x) { return cnt[x[0]] ? '<span class="rounded-full bg-white/20 px-2.5 py-1">' + x[1] + " " + cnt[x[0]] + "</span>" : ""; }).join("") + "</div></div>";
    list.innerHTML = res.map(resultCard).join("");
    renderMatrix(); renderSchedule();
    var shopEl = document.getElementById("shop-list");
    shopEl.innerHTML = selected.map(function (id) { var it = core.byId[id]; return '<div class="flex flex-col gap-2 rounded-xl border border-ink-100 bg-white p-4 sm:flex-row sm:items-center sm:justify-between"><div><p class="font-bold text-ink-900">' + esc(it.name) + '</p><p class="text-xs text-ink-500">검색어: ' + esc(it.shopQuery) + '</p></div>' + window.Affiliate.buttonsHtml(it.shopQuery, { size: "sm", short: true }) + "</div>"; }).join("");
    D.icons();
  }

  function update() { renderPicker(); renderResults(); syncUrl(); }

  document.addEventListener("DOMContentLoaded", function () {
    D.core().then(function (c) {
      core = c; buildPickerGrid();
      selected = parseInitial().filter(function (id) { return !!core.byId[id]; }).slice(0, MAX);
      document.getElementById("selected-chips").addEventListener("click", function (e) { var b = e.target.closest("[data-remove]"); if (b) remove(b.getAttribute("data-remove")); });
      document.getElementById("clear-all").addEventListener("click", function () { selected = []; update(); });
      document.getElementById("copy-link").addEventListener("click", function () {
        var url = location.href;
        var done = function () { showToast("링크를 복사했어요. 친구에게 공유해 보세요!"); };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done).catch(function () { prompt("아래 링크를 복사하세요", url); });
        else prompt("아래 링크를 복사하세요", url);
      });
      var presets = document.getElementById("presets");
      if (presets) presets.addEventListener("click", function (e) { var b = e.target.closest("[data-preset]"); if (!b) return; selected = b.getAttribute("data-preset").split(",").filter(function (id) { return !!core.byId[id]; }); update(); document.getElementById("results-anchor").scrollIntoView({ behavior: "smooth", block: "start" }); });
      window.Affiliate.ready().then(update);
    }).catch(function () { document.getElementById("picker-grid").innerHTML = '<p class="text-sm text-rose-600">데이터를 불러오지 못했습니다. 새로고침해 주세요.</p>'; });
  });
})();
