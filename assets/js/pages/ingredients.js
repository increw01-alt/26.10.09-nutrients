/* 성분 사전 목록 페이지 */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var state = { q: D.qs("q") || "", category: D.qs("category") || "", tag: D.qs("tag") || "" };

  function card(it, cats) {
    var cat = cats[it.category] || {};
    var I = window.Illus;
    return '<a href="' + D.ingredientUrl(it.id) + '" class="ing-card group fade-up">' +
      '<div class="flex items-start justify-between gap-2"><div class="ing-photo left">' + (I ? I.photoImg(it.category) : "") + '</div><span class="rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-bold ring-1 ' + D.catClass(cat.color) + '">' + esc(cat.label || "") + '</span></div>' +
      '<h2 class="mt-2 text-[17px] font-extrabold tracking-tight text-ink-900 group-hover:text-brand-700">' + esc(it.name) + '</h2>' +
      '<p class="text-xs font-medium text-ink-400">' + esc(it.en) + '</p>' +
      '<p class="mt-2 line-clamp-2 text-sm leading-relaxed text-ink-600">' + esc(it.summary) + '</p>' +
      '<div class="mt-3 flex flex-wrap gap-1.5">' + (it.tags || []).slice(0, 3).map(function (t) { return '<span class="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-semibold text-ink-500 ring-1 ring-[#e3ebdc]">#' + esc(t) + '</span>'; }).join("") + '</div>' +
      '<div class="mt-auto flex items-center justify-between border-t border-[#ece9df] pt-3 text-xs text-ink-500"><span class="inline-flex items-center gap-1"><i data-lucide="clock" class="h-3.5 w-3.5"></i>' + esc(it.timing.label) + '</span><span class="inline-flex items-center gap-1 font-bold text-brand-700">성분 정보 보기 <i data-lucide="arrow-right" class="h-3.5 w-3.5 transition group-hover:translate-x-0.5"></i></span></div></a>';
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
