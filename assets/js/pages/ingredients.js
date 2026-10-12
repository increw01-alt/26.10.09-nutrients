/* 성분 사전 목록 페이지 */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var state = { q: D.qs("q") || "", category: D.qs("category") || "", tag: D.qs("tag") || "" };

  function card(it, cats) {
    var cat = cats[it.category] || {};
    var I = window.Illus;
    var label = ((it.en || it.name).split("(")[0].replace(/[^A-Za-z0-9 \-·]/g, "").trim() || it.name).slice(0, 14);
    var art = I ? I.bottle(label, I.colorFor(it.category), { sub: it.name, id: it.id }) : "";
    return '<a href="' + D.ingredientUrl(it.id) + '" class="card-hover group flex flex-col rounded-2xl border border-ink-100 bg-white p-3 shadow-card fade-up">' +
      '<div class="relative"><div class="illus-box aspect-[4/3] w-full">' + art + '</div><span class="absolute left-3 top-3 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-bold ring-1 ' + D.catClass(cat.color) + '">' + esc(cat.label || "") + '</span></div>' +
      '<div class="px-2 pb-2 pt-3"><h2 class="text-lg font-extrabold text-ink-900 group-hover:text-brand-700">' + esc(it.name) + '</h2>' +
      '<p class="text-xs font-medium text-ink-400">' + esc(it.en) + '</p>' +
      '<p class="mt-2 line-clamp-2 text-sm leading-relaxed text-ink-600">' + esc(it.summary) + '</p>' +
      '<div class="mt-3 flex flex-wrap gap-1.5">' + (it.tags || []).slice(0, 3).map(function (t) { return '<span class="rounded-md bg-cream-200 px-2 py-0.5 text-[11px] font-semibold text-ink-500">#' + esc(t) + '</span>'; }).join("") + '</div>' +
      '<div class="mt-3 flex items-center justify-between border-t border-ink-100 pt-3 text-xs text-ink-500"><span class="inline-flex items-center gap-1"><i data-lucide="clock" class="h-3.5 w-3.5"></i>' + esc(it.timing.label) + '</span><span class="grid h-8 w-8 place-items-center rounded-full bg-brand-600 text-white transition group-hover:bg-brand-700"><i data-lucide="arrow-right" class="h-4 w-4"></i></span></div></div></a>';
  }

  function render(core) {
    var list = document.getElementById("ingredient-list"), count = document.getElementById("result-count"), empty = document.getElementById("empty-state");
    var items = core.items.slice();
    if (state.category) items = items.filter(function (i) { return i.category === state.category; });
    if (state.tag) items = items.filter(function (i) { return (i.tags || []).indexOf(state.tag) >= 0; });
    if (state.q.trim()) {
      var hits = D.search(items, state.q, 100); items = hits;
    } else items.sort(function (a, b) { return a.name.localeCompare(b.name, "ko"); });
    list.innerHTML = items.map(function (i) { return card(i, core.categories); }).join("");
    count.textContent = items.length + "개 성분";
    empty.classList.toggle("hidden", items.length > 0);
    document.querySelectorAll("[data-cat]").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-cat") === state.category); b.setAttribute("aria-pressed", b.getAttribute("data-cat") === state.category ? "true" : "false"); });
    try {
      var u = new URL(location.href); u.searchParams.delete("q"); u.searchParams.delete("category"); u.searchParams.delete("tag");
      if (state.q) u.searchParams.set("q", state.q); if (state.category) u.searchParams.set("category", state.category); if (state.tag) u.searchParams.set("tag", state.tag);
      history.replaceState(null, "", u.toString());
    } catch (e) {}
    D.icons(list);
  }

  document.addEventListener("DOMContentLoaded", function () {
    D.core().then(function (core) {
      var filters = document.getElementById("category-filters");
      filters.innerHTML = '<button type="button" class="chip" data-cat="">전체</button>' + Object.keys(core.categories).map(function (k) {
        var c = core.categories[k];
        return '<button type="button" class="chip" data-cat="' + esc(k) + '"><i data-lucide="' + esc(c.icon) + '" class="h-3.5 w-3.5"></i>' + esc(c.label) + '</button>';
      }).join("");
      filters.addEventListener("click", function (e) { var b = e.target.closest("[data-cat]"); if (!b) return; state.category = b.getAttribute("data-cat"); render(core); });
      var input = document.getElementById("list-search"); input.value = state.q;
      input.addEventListener("input", function () { state.q = input.value; render(core); });
      var tagEl = document.getElementById("active-tag");
      if (state.tag && tagEl) { tagEl.innerHTML = '태그: <strong>#' + esc(state.tag) + '</strong> <button type="button" id="clear-tag" class="ml-1 underline">해제</button>'; tagEl.classList.remove("hidden"); document.getElementById("clear-tag").addEventListener("click", function () { state.tag = ""; tagEl.classList.add("hidden"); render(core); }); }
      render(core); D.icons();
    }).catch(function () { document.getElementById("ingredient-list").innerHTML = '<p class="text-sm text-rose-600">데이터를 불러오지 못했습니다.</p>'; });
  });
})();
