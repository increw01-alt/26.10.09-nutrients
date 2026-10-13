/* 통합 검색 결과 페이지 — 성분·건강기능식품·의약품·가이드를 한 번에 보여주고, 결과가 없으면 비슷한 이름과 검색 요령을 안내한다.
 * 제품명은 자모 단위로 비교하므로 일부만 입력해도('락ㅌ', 'ㄹㅌㅍ') 관련 제품이 나온다 (assets/js/data.js 의 nameMatcher). */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var POPULAR = ["vitamin-d", "omega-3", "magnesium", "probiotics", "vitamin-c", "lutein"];
  var EXAMPLES = ["락토핏", "센트룸", "프로메가", "마그네슘", "비타민D", "우루사"];   // 검색 예시 (데이터 수집 상태에 따라 결과 수는 달라질 수 있음)

  function $(id) { return document.getElementById(id); }
  function section(id, title, icon, count, body) {
    return '<section id="' + id + '" class="rounded-2xl border border-ink-100 bg-white p-5 shadow-card sm:p-6"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="' + icon + '" class="h-5 w-5 text-brand-600"></i>' + title + (count != null ? ' <span class="text-sm font-bold text-ink-400">' + esc(String(count)) + '</span>' : "") + '</h2>' + body + '</section>';
  }
  function ingChips(core, ids, max) {
    return ids.slice(0, max || 5).map(function (k) { return '<a class="rounded-full bg-cream-200 px-2 py-0.5 text-[11px] font-bold text-brand-800 hover:bg-brand-600 hover:text-white" href="' + D.ingredientUrl(k) + '">' + esc(core.byId[k].name) + '</a>'; }).join("");
  }
  function tipsBox(meta) {
    var drugsReady = !!(meta && meta.drugs && meta.drugs.total > 0);
    return '<section id="sec-tips" class="rounded-2xl border border-dashed border-brand-600/25 bg-cream-200/40 p-5 sm:p-6"><h2 class="flex items-center gap-2 text-base font-extrabold text-ink-900"><i data-lucide="lightbulb" class="h-5 w-5 text-brand-600"></i>검색 요령</h2>' +
      '<ul class="mt-3 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-ink-600">' +
      '<li><strong class="text-ink-800">제품명은 일부만 입력해도</strong> 관련 제품이 나옵니다. 라벨에 적힌 정식 이름(예: ‘락토핏 골드’)까지 입력하면 더 정확해요. 초성(ㄹㅌㅍ)만 쳐도 됩니다.</li>' +
      '<li><strong class="text-ink-800">성분명</strong>(마그네슘, 비타민D, 오메가3 …)으로 검색하면 성분 설명과 함유 제품, 궁합을 함께 볼 수 있어요.</li>' +
      '<li>건강기능식품은 <strong class="text-ink-800">식약처 품목신고 제품</strong>, 의약품은 <strong class="text-ink-800">식약처 e약은요(일반의약품 중심)</strong>에 등록된 제품만 검색됩니다. 해외 직구 제품이나 일반 식품은 나오지 않을 수 있어요.' + (drugsReady ? "" : ' <span class="text-ink-500">(의약품 검색은 데이터 준비 중입니다.)</span>') + '</li>' +
      '</ul><div class="mt-4 flex flex-wrap gap-2"><a class="btn-outline btn-sm" href="' + D.url("ingredients.html") + '">성분 사전</a><a class="btn-outline btn-sm" href="' + D.url("products.html") + '">제품 찾기</a><a class="btn-outline btn-sm" href="' + D.url("compatibility.html") + '">궁합 체크</a></div></section>';
  }
  function show() { $("search-loading").classList.add("hidden"); $("search-results").classList.remove("hidden"); D.icons(); }

  function render(q, core, guides, products, drugs, meta) {
    var input = $("search-q"); if (input) input.value = q;
    var site = (window.SITE || {}).name || "영양제.kr";
    document.title = (q ? "‘" + q + "’ 검색 결과" : "통합 검색") + " | " + site;
    var title = $("search-title"), summary = $("search-summary"), out = $("search-results");
    var I = window.Illus;

    if (!q) {
      title.textContent = "성분·제품·의약품 통합 검색";
      summary.textContent = "성분명, 건강기능식품·의약품 제품명, 고민 키워드로 찾아보세요. 제품명은 일부만 입력해도 됩니다.";
      out.innerHTML = section("sec-start", "이렇게 검색해 보세요", "search", null,
        '<p class="mt-2 text-sm text-ink-500">많이 찾는 성분</p><div class="mt-2 flex flex-wrap gap-2">' + POPULAR.map(function (id) { return core.byId[id]; }).filter(Boolean).map(function (it) { return '<a class="chip" href="' + D.ingredientUrl(it.id) + '">' + esc(it.name) + '</a>'; }).join("") + '</div>' +
        '<p class="mt-4 text-sm text-ink-500">검색 예시</p><div class="mt-2 flex flex-wrap gap-2">' + EXAMPLES.map(function (x) { return '<a class="chip" href="' + D.searchUrl(x) + '">' + esc(x) + '</a>'; }).join("") + '</div>') + tipsBox(meta);
      show(); return;
    }

    title.textContent = "‘" + q + "’ 검색 결과";
    var ings = D.search(core.items, q, 8);
    var pm = D.nameMatcher(products.p.map(function (p) { return p[1]; })), ph = pm(q, 30);
    var dm = D.nameMatcher(drugs.p.map(function (p) { return p[1]; })), dh = dm(q, 20);
    var gs = (guides || []).filter(function (g) { return D.has([g.title, g.h1, (g.keywords || []).join(" ")].join(" "), q); }).slice(0, 8);
    var counts = [ings.length ? "성분 " + ings.length : "", ph.total ? "건강기능식품 " + ph.total.toLocaleString() : "", dh.total ? "의약품 " + dh.total.toLocaleString() : "", gs.length ? "가이드 " + gs.length : ""].filter(Boolean);
    summary.textContent = counts.length ? counts.join(" · ") + "건을 찾았어요. 제품명은 일부만 맞아도 나오며, 이름 앞부분이 맞는 제품부터 보여줍니다." : "일치하는 결과가 없어요. 아래 비슷한 이름과 검색 요령을 확인해 보세요.";

    var html = "";
    if (ings.length) html += section("sec-ingredients", "성분", "pill", ings.length + "건",
      '<ul class="mt-3 divide-y divide-ink-100">' + ings.map(function (it) {
        var cat = core.categories[it.category] || {};
        return '<li class="flex items-center gap-3 py-3"><div class="h-11 w-11 shrink-0 overflow-hidden rounded-xl bg-cream-200">' + (I ? I.photoImg(it.category, "h-full w-full object-cover") : "") + '</div>' +
          '<div class="min-w-0 flex-1"><a class="text-[15px] font-bold text-ink-900 hover:text-brand-700" href="' + D.ingredientUrl(it.id) + '">' + D.markMatch(it.name, q) + '</a><span class="ml-2 rounded-full px-2 py-0.5 text-[11px] font-bold ring-1 ' + D.catClass(cat.color) + '">' + esc(cat.label || "") + '</span><p class="mt-0.5 line-clamp-1 text-xs text-ink-500">' + esc(it.summary || "") + '</p></div>' +
          '<a class="shrink-0 text-xs font-bold text-brand-700 hover:underline" href="' + D.productsUrl(it.id) + '">함유 제품</a></li>';
      }).join("") + '</ul>');
    if (ph.total) html += section("sec-products", "건강기능식품", "package", ph.total.toLocaleString() + "건",
      '<p class="mt-1 text-xs text-ink-400">식약처 품목신고 제품 · 이름 앞부분이 맞는 순</p><ul class="mt-3 divide-y divide-ink-100">' + ph.idx.map(function (i) {
        var pp = products.p[i]; var ids = pp[2].map(function (k) { return products.i[k]; }).filter(function (k) { return !!core.byId[k]; });
        var maker = (products.c || [])[pp[3]] || "";
        return '<li class="py-3"><div class="flex flex-wrap items-center gap-x-3 gap-y-1"><a class="min-w-0 text-[15px] font-bold text-ink-900 hover:text-brand-700" href="' + D.productUrl(pp[0]) + '">' + D.markMatch(pp[1], q) + '</a>' + (maker ? '<span class="text-xs font-semibold text-ink-500">' + esc(maker) + '</span>' : "") + (ids.length ? '<a class="text-xs font-bold text-brand-700 hover:underline" href="' + D.compatUrl(ids) + '">궁합 보기</a>' : "") + '</div>' +
          (ids.length ? '<div class="mt-1.5 flex flex-wrap gap-1">' + ingChips(core, ids) + '</div>' : '<p class="mt-1 text-xs text-ink-400">성분 사전과 연결된 성분 없음</p>') + '</li>';
      }).join("") + '</ul>' + (ph.total > ph.idx.length ? '<p class="mt-3 text-xs text-ink-500">상위 ' + ph.idx.length + '건만 표시했어요. 제품명을 더 정확히 입력하면 좁혀집니다.</p>' : ""));
    if (dh.total) html += section("sec-drugs", "의약품", "pill-bottle", dh.total.toLocaleString() + "건",
      '<p class="mt-1 text-xs text-ink-400">식약처 e약은요 등록 의약품 · 약국에서 구입</p><ul class="mt-3 divide-y divide-ink-100">' + dh.idx.map(function (i) {
        var pp = drugs.p[i]; var ids = pp[2].map(function (k) { return drugs.i[k]; }).filter(function (k) { return !!core.byId[k]; });
        var dmaker = (drugs.c || [])[pp[5]] || "";
        return '<li class="py-3"><div class="flex flex-wrap items-center gap-x-3 gap-y-1"><a class="min-w-0 text-[15px] font-bold text-ink-900 hover:text-brand-700" href="' + D.drugUrl(pp[0]) + '">' + D.markMatch(pp[1], q) + '</a>' + (dmaker ? '<span class="text-xs font-semibold text-ink-500">' + esc(dmaker) + '</span>' : "") + (pp[4] === 2 ? '<span class="badge badge-neutral">전문의약품</span>' : pp[4] === 1 ? '<span class="badge badge-neutral">일반의약품</span>' : "") + '</div>' +
          '<p class="mt-1 text-xs text-ink-500">' + (pp[3] ? "주성분: " + esc(pp[3]) : "") + (ids.length ? (pp[3] ? " · " : "") + "영양 성분: " + ids.map(function (k) { return core.byId[k].name; }).join(", ") : "") + '</p></li>';
      }).join("") + '</ul>');
    if (gs.length) html += section("sec-guides", "가이드", "book-open", gs.length + "건",
      '<ul class="mt-3 divide-y divide-ink-100">' + gs.map(function (g) { return '<li class="py-3"><a class="text-[15px] font-bold text-ink-900 hover:text-brand-700" href="' + D.guideUrl(g.slug) + '">' + esc(String(g.h1 || g.title || "").split(" — ")[0]) + '</a><p class="mt-0.5 line-clamp-2 text-xs text-ink-500">' + esc(g.description || g.intro || "") + '</p></li>'; }).join("") + '</ul>');

    if (!html) {
      var pool = products.p.map(function (p) { return ["p", p]; }).concat(drugs.p.map(function (p) { return ["d", p]; }));
      var sim = D.similarNames(pool.map(function (x) { return x[1][1]; }), q, 6);
      html = section("sec-empty", "‘" + esc(q) + "’에 맞는 결과가 없어요", "search-x", null,
        (sim.length ? '<p class="mt-2 text-sm font-bold text-ink-800">혹시 이 제품을 찾으셨나요?</p><ul class="mt-2 divide-y divide-ink-100">' + sim.map(function (i) {
          var x = pool[i], pp = x[1];
          return '<li class="py-2.5"><a class="text-[15px] font-bold text-ink-900 hover:text-brand-700" href="' + (x[0] === "p" ? D.productUrl(pp[0]) : D.drugUrl(pp[0])) + '">' + esc(pp[1]) + '</a><span class="ml-2 text-xs text-ink-400">' + (x[0] === "p" ? "건강기능식품" : "의약품") + '</span></li>';
        }).join("") + '</ul>' : '<p class="mt-2 text-sm text-ink-500">비슷한 이름의 제품도 찾지 못했어요. 철자를 확인하거나 성분명으로 검색해 보세요.</p>'));
    }
    out.innerHTML = html + tipsBox(meta);
    show();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var q = (D.qs("q") || "").trim();
    Promise.all([
      D.core(),
      D.guides().then(function (g) { return (g && g.items) || []; }).catch(function () { return []; }),
      D.productNames().then(function (n) { return n && n.p ? n : { i: [], p: [] }; }).catch(function () { return { i: [], p: [] }; }),
      D.drugNames().then(function (n) { return n && n.p ? n : { i: [], p: [] }; }).catch(function () { return { i: [], p: [] }; }),
      D.meta().catch(function () { return {}; })
    ]).then(function (r) { render(q, r[0], r[1], r[2], r[3], r[4]); }).catch(function (e) {
      if (window.console) console.warn(e);
      $("search-loading").innerHTML = '<p class="text-sm text-rose-600">데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>';
    });
  });
})();
