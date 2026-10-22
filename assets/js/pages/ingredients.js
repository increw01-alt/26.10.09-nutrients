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

  /* 검색창 아래 제안 목록 — 모바일은 키보드가 결과 카드를 가리므로 입력란 바로 아래(흐름 안, 히어로가 overflow:hidden 이라 절대 위치는 잘림)에
   * 성분(최대 6)·가이드(최대 2)를 띄우고, 성분이 하나도 없으면 비슷한 이름을, 끝에는 통합 검색 링크를 둔다. 카드 목록 필터는 그대로 함께 동작 */
  function initSuggest(core, input) {
    var box = document.getElementById("list-suggest"), list = document.getElementById("list-suggest-list"), status = document.getElementById("list-suggest-status");
    if (!box || !list) return;
    var matches = [], active = -1, guides = null, guidesLoading = null;
    var names = core.items.map(function (it) { return it.name; });
    function loadGuides() {
      if (guides || guidesLoading) return guidesLoading;
      guidesLoading = D.guides().then(function (g) { guides = (g && g.items) || []; }).catch(function () { guides = []; });
      return guidesLoading;
    }
    function entries(q) {
      if (!q) return [];
      var out = D.search(core.items, q, 6).map(function (it) {
        var cat = core.categories[it.category] || {};
        return { html: D.markMatch(it.name, q), sub: (cat.label || cat.name || "") + (it.en ? " · " + it.en : ""), type: "성분", href: D.ingredientUrl(it.id) };
      });
      if (!out.length) D.similarNames(names, q, 4).forEach(function (i) {
        var it = core.items[i], cat = core.categories[it.category] || {};
        out.push({ html: esc(it.name), sub: (cat.label || cat.name || "") + (it.en ? " · " + it.en : ""), type: "비슷한 이름", href: D.ingredientUrl(it.id) });
      });
      (guides || []).filter(function (g) { return D.has([g.title, g.h1, (g.keywords || []).join(" ")].join(" "), q); }).slice(0, 2).forEach(function (g) {
        out.push({ html: esc(String(g.h1 || g.title || "").split(" — ")[0]), sub: "영양제 추천 가이드", type: "가이드", href: D.guideUrl(g.slug) });
      });
      out.push({ html: "‘" + esc(q) + "’ 전체 검색 결과 보기", sub: "제품·의약품·용어까지", type: "검색", href: D.searchUrl(q), all: true });
      return out;
    }
    function close() { box.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); active = -1; }
    function setActive(i) {
      active = i;
      var opts = list.querySelectorAll('[role="option"]');
      Array.prototype.forEach.call(opts, function (o, k) { o.setAttribute("aria-selected", k === i ? "true" : "false"); });
      if (opts[i]) { input.setAttribute("aria-activedescendant", opts[i].id); if (opts[i].scrollIntoView) opts[i].scrollIntoView({ block: "nearest" }); }
      else input.removeAttribute("aria-activedescendant");
    }
    function render() {
      var q = input.value.trim();
      matches = entries(q); active = -1; input.removeAttribute("aria-activedescendant");
      if (!matches.length) { close(); if (status) status.textContent = ""; return; }
      list.innerHTML = matches.map(function (m, i) {
        return '<li class="suggest-option' + (m.all ? " all" : "") + '" id="list-suggest-' + i + '" role="option" aria-selected="false" data-href="' + esc(m.href) + '">' +
          '<span><b>' + m.html + '</b>' + (m.sub && !m.all ? "<small>" + esc(m.sub) + "</small>" : "") + "</span>" + (m.all ? "" : '<span class="option-type">' + esc(m.type) + "</span>") + "</li>";
      }).join("");
      box.hidden = false; input.setAttribute("aria-expanded", "true");
      if (status) status.textContent = "제안 " + matches.length + "개가 있습니다. 화살표 키로 고르고 Enter 로 여세요.";
    }
    function update() { render(); var p = loadGuides(); if (p && !guides) p.then(function () { if (!box.hidden) render(); }); }
    list.addEventListener("pointerdown", function (e) { e.preventDefault(); });   // 누르는 동안 입력란 포커스(키보드)가 사라지지 않게
    list.addEventListener("click", function (e) { var li = e.target.closest("[data-href]"); if (li) location.href = li.getAttribute("data-href"); });
    input.addEventListener("input", update);
    input.addEventListener("focus", function () { if (input.value.trim()) update(); });
    input.addEventListener("keydown", function (e) {
      if (e.isComposing || e.keyCode === 229) return;
      if (e.key === "Escape") { e.preventDefault(); close(); return; }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (box.hidden) render();
        if (!matches.length) return;
        setActive((active + (e.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length);
        return;
      }
      if (e.key === "Enter") {   // 고른 항목이 있으면 열고, 없으면 제안을 닫고 키보드를 내려 아래 결과 카드가 보이게
        e.preventDefault();
        if (active >= 0 && matches[active]) { location.href = matches[active].href; return; }
        close(); input.blur();
      }
    });
    document.addEventListener("click", function (e) { if (!input.form || !input.form.contains(e.target)) close(); });
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
      initSuggest(core, input);
      var tagEl = document.getElementById("active-tag");
      if (state.tag && tagEl) { tagEl.innerHTML = '태그: <strong>#' + esc(state.tag) + '</strong> <button type="button" id="clear-tag" class="ml-1 underline">해제</button>'; tagEl.classList.remove("hidden"); document.getElementById("clear-tag").addEventListener("click", function () { state.tag = ""; tagEl.classList.add("hidden"); render(core); }); }
      render(core); D.icons();
    }).catch(function () { document.getElementById("ingredient-list").innerHTML = '<p class="text-sm text-rose-600">데이터를 불러오지 못했습니다.</p>'; });
  });
})();
