/* 홈 페이지 */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;

  // 메인에 노출할 인기 궁합 (큐레이션 — 데이터에 존재하는 쌍만 표시됨)
  var FEATURED_PAIRS = [
    ["vitamin-d", "calcium"], ["vitamin-c", "iron"], ["calcium", "iron"], ["omega-3", "lutein"],
    ["zinc", "copper"], ["iron", "green-tea-extract"], ["probiotics", "psyllium"], ["vitamin-e", "ginkgo"]
  ];
  var POPULAR = ["vitamin-d", "omega-3", "probiotics", "magnesium", "vitamin-c", "lutein", "iron", "calcium", "zinc", "milk-thistle", "red-ginseng", "vitamin-b-complex"];

  function ingredientCard(it, cats) {
    var cat = cats[it.category] || {};
    return '<a href="' + D.ingredientUrl(it.id) + '" class="card-hover group flex items-start gap-3 rounded-2xl border border-ink-100 bg-white p-4 shadow-card">' +
      '<span class="grid h-11 w-11 shrink-0 place-items-center rounded-xl ring-1 ' + D.catClass(cat.color) + '"><i data-lucide="' + esc(it.icon || cat.icon) + '" class="h-5 w-5"></i></span>' +
      '<span class="min-w-0"><span class="block truncate font-bold text-ink-900 group-hover:text-brand-700">' + esc(it.name) + '</span>' +
      '<span class="mt-0.5 block truncate text-xs text-ink-500">' + esc((it.tags || []).slice(0, 3).join(" · ")) + '</span></span></a>';
  }

  function pairCard(core, p) {
    var a = core.byId[p.pair[0]], b = core.byId[p.pair[1]];
    if (!a || !b) return "";
    var t = core.types[p.type] || core.types.neutral;
    return '<a href="' + D.compatUrl(p.pair) + '" class="card-hover block rounded-2xl border p-5 shadow-card card-' + p.type + '">' +
      '<div class="flex items-center justify-between gap-3"><span class="badge ' + D.typeClass(p.type) + '"><i data-lucide="' + esc(t.icon) + '" class="h-3.5 w-3.5"></i>' + esc(t.short) + '</span>' +
      (p.separateHours ? '<span class="text-xs font-semibold text-amber-700">' + p.separateHours + '시간 간격</span>' : "") + '</div>' +
      '<h3 class="mt-3 text-lg font-extrabold text-ink-900">' + esc(a.name) + ' <span class="text-ink-300">+</span> ' + esc(b.name) + '</h3>' +
      '<p class="mt-1 text-sm font-semibold text-ink-700">' + esc(p.title) + '</p>' +
      '<p class="mt-2 line-clamp-2 text-sm leading-relaxed text-ink-500">' + esc(p.detail) + '</p></a>';
  }

  function initQuickCheck(core) {
    var a = document.getElementById("quick-a"), b = document.getElementById("quick-b"), form = document.getElementById("quick-form");
    if (!a || !b || !form) return;
    var opts = '<option value="">성분 선택</option>' + core.items.slice().sort(function (x, y) { return x.name.localeCompare(y.name, "ko"); })
      .map(function (it) { return '<option value="' + esc(it.id) + '">' + esc(it.name) + '</option>'; }).join("");
    a.innerHTML = opts; b.innerHTML = opts;
    a.value = "vitamin-d"; b.value = "calcium";
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var ids = [a.value, b.value].filter(Boolean);
      if (ids.length < 2) { alert("성분을 두 가지 선택해 주세요."); return; }
      if (ids[0] === ids[1]) { alert("서로 다른 성분을 선택해 주세요."); return; }
      location.href = D.compatUrl(ids);
    });
  }

  function initHeroSearch(items) {
    var input = document.getElementById("hero-search"), box = document.getElementById("hero-search-results");
    if (!input || !box) return;
    input.addEventListener("input", function () {
      var hits = D.search(items, input.value, 6);
      if (!input.value.trim() || !hits.length) { box.classList.add("hidden"); box.innerHTML = ""; return; }
      box.innerHTML = hits.map(function (it) {
        return '<a class="flex items-center justify-between gap-3 px-4 py-2.5 text-sm hover:bg-brand-50" href="' + D.ingredientUrl(it.id) + '"><span class="font-semibold text-ink-900">' + esc(it.name) + '</span><span class="truncate text-xs text-ink-400">' + esc((it.tags || []).slice(0, 2).join(" · ")) + '</span></a>';
      }).join("");
      box.classList.remove("hidden");
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); var first = box.querySelector("a"); if (first) location.href = first.href; else location.href = D.url("ingredients.html?q=" + encodeURIComponent(input.value)); }
      if (e.key === "Escape") box.classList.add("hidden");
    });
    document.addEventListener("click", function (e) { if (!box.contains(e.target) && e.target !== input) box.classList.add("hidden"); });
  }

  function renderNews(news) {
    var el = document.getElementById("home-news");
    if (!el) return;
    var items = (news.items || []).slice().sort(function (a, b) { return new Date(b.publishedAt) - new Date(a.publishedAt); }).slice(0, 4);
    if (!items.length) { el.innerHTML = '<p class="text-sm text-ink-400">표시할 뉴스가 없습니다.</p>'; return; }
    el.innerHTML = items.map(function (n) {
      var cat = { mfds: "식약처", research: "연구", news: "뉴스" }[n.category] || "뉴스";
      return '<a href="' + esc(n.link) + '" target="_blank" rel="noopener" class="card-hover flex flex-col rounded-2xl border border-ink-100 bg-white p-5 shadow-card">' +
        '<div class="flex items-center gap-2 text-xs"><span class="rounded-full bg-brand-50 px-2 py-0.5 font-bold text-brand-700">' + esc(cat) + '</span><span class="text-ink-400">' + esc(n.source || "") + ' · ' + esc(D.timeAgo(n.publishedAt)) + '</span></div>' +
        '<h3 class="mt-3 line-clamp-2 font-bold leading-snug text-ink-900">' + esc(n.title) + '</h3>' +
        '<p class="mt-2 line-clamp-2 text-sm text-ink-500">' + esc(n.summary || "") + '</p></a>';
    }).join("");
    var badge = document.getElementById("home-news-sample");
    if (badge && news._meta && news._meta.source === "sample") badge.classList.remove("hidden");
  }

  document.addEventListener("DOMContentLoaded", function () {
    D.core().then(function (core) {
      var popular = document.getElementById("popular-ingredients");
      if (popular) { popular.innerHTML = POPULAR.map(function (id) { return core.byId[id] ? ingredientCard(core.byId[id], core.categories) : ""; }).join(""); }
      var pairs = document.getElementById("featured-pairs");
      if (pairs) { pairs.innerHTML = FEATURED_PAIRS.map(function (pr) { var p = D.findPair(core, pr[0], pr[1]); return p ? pairCard(core, p) : ""; }).join(""); }
      var cats = document.getElementById("category-grid");
      if (cats) {
        cats.innerHTML = Object.keys(core.categories).map(function (k) {
          var c = core.categories[k]; var n = core.items.filter(function (i) { return i.category === k; }).length;
          return '<a href="' + D.url("ingredients.html?category=" + k) + '" class="card-hover flex items-center gap-3 rounded-2xl border border-ink-100 bg-white px-4 py-3.5 shadow-card"><span class="grid h-10 w-10 place-items-center rounded-xl ring-1 ' + D.catClass(c.color) + '"><i data-lucide="' + esc(c.icon) + '" class="h-5 w-5"></i></span><span><span class="block font-bold text-ink-900">' + esc(c.label) + '</span><span class="text-xs text-ink-400">' + n + '개 성분</span></span></a>';
        }).join("");
      }
      var stat = document.getElementById("stat-ingredients"); if (stat) stat.textContent = core.items.length;
      var stat2 = document.getElementById("stat-pairs"); if (stat2) stat2.textContent = core.pairs.length;
      initQuickCheck(core); initHeroSearch(core.items); D.icons();
    }).catch(function () {
      var el = document.getElementById("popular-ingredients"); if (el) el.innerHTML = '<p class="text-sm text-rose-600">데이터를 불러오지 못했습니다. 새로고침해 주세요.</p>';
    });
    D.news().then(renderNews).catch(function () {});
    D.products().then(function (p) { var s = document.getElementById("stat-products"); if (s) s.textContent = (p.items || []).length.toLocaleString(); }).catch(function () {});
  });
})();
