/* 성분 상세 페이지 (정적 생성 페이지 i/*.html 과 ingredient.html?id= 공용) */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var id = window.__INGREDIENT_ID || D.qs("id");

  function section(title, icon, bodyHtml, extraClass) {
    return '<section class="rounded-2xl border border-ink-100 bg-white p-6 shadow-card ' + (extraClass || "") + '"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="' + icon + '" class="h-5 w-5 text-brand-600"></i>' + esc(title) + '</h2><div class="mt-4">' + bodyHtml + '</div></section>';
  }
  function list(arr, cls) { return arr && arr.length ? '<ul class="' + cls + ' text-[15px] text-ink-700">' + arr.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>" : '<p class="text-sm text-ink-400">해당 없음</p>'; }

  function compatBlock(core, it) {
    var rel = D.related(core, it.id);
    rel.sort(function (a, b) { return D.typeOrder[a.pair.type] - D.typeOrder[b.pair.type] || (b.pair.level || 0) - (a.pair.level || 0); });
    var groups = { synergy: [], caution: [], avoid: [], neutral: [] };
    rel.forEach(function (r) { (groups[r.pair.type] || groups.neutral).push(r); });
    function grp(type) {
      var t = core.types[type]; var arr = groups[type]; if (!arr.length) return "";
      return '<div class="mt-5 first:mt-0"><h3 class="flex items-center gap-2 text-sm font-bold"><span class="h-2.5 w-2.5 rounded-full dot-' + type + '"></span>' + esc(t.label) + ' <span class="text-ink-400">' + arr.length + '</span></h3>' +
        '<div class="mt-2 grid gap-2 sm:grid-cols-2">' + arr.map(function (r) {
          return '<a href="' + D.compatUrl([it.id, r.other.id]) + '" class="card-hover flex items-start gap-3 rounded-xl border p-3.5 card-' + type + '"><span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white ring-1 ring-ink-100"><i data-lucide="' + esc(r.other.icon || "pill") + '" class="h-4 w-4 text-ink-600"></i></span><span class="min-w-0"><span class="block font-bold text-ink-900">' + esc(r.other.name) + (r.pair.separateHours ? ' <span class="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">' + r.pair.separateHours + 'h 간격</span>' : "") + '</span><span class="mt-0.5 line-clamp-2 block text-xs text-ink-600">' + esc(r.pair.title) + '</span></span></a>';
        }).join("") + "</div></div>";
    }
    var html = grp("avoid") + grp("caution") + grp("synergy") + grp("neutral");
    if (!html) html = '<p class="text-sm text-ink-400">아직 등록된 궁합 정보가 없습니다.</p>';
    html += '<div class="mt-6 rounded-xl bg-brand-50 p-4 text-sm text-brand-900"><strong>내가 먹는 영양제와 함께 확인하고 싶다면</strong> <a class="ml-1 inline-flex items-center gap-1 font-bold text-brand-700 underline" href="' + D.compatUrl([it.id]) + '">궁합 체크에서 ' + esc(it.name) + ' 포함해 검사하기 <i data-lucide="arrow-right" class="h-4 w-4"></i></a></div>';
    return html;
  }

  function renderProducts(it, products) {
    var el = document.getElementById("ingredient-products"); if (!el) return;
    var items = (products.items || []).filter(function (p) { return (p.ingredients || []).indexOf(it.id) >= 0; }).slice(0, 6);
    var sample = products._meta && products._meta.source === "sample";
    var html = (sample ? '<p class="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">아래 제품은 <strong>샘플 데이터</strong>입니다. 식약처 API 키를 설정하고 수집 스크립트를 실행하면 실제 신고 제품으로 교체됩니다.</p>' : "");
    if (!items.length) html += '<p class="text-sm text-ink-400">이 성분이 포함된 신고 제품이 아직 수집되지 않았습니다.</p>';
    else html += '<div class="grid gap-3 sm:grid-cols-2">' + items.map(function (p) {
      return '<div class="rounded-xl border border-ink-100 p-4"><p class="font-bold text-ink-900">' + esc(p.name) + '</p><p class="mt-0.5 text-xs text-ink-500">' + esc(p.company) + (p.registeredAt ? ' · ' + esc(D.fmtDate(p.registeredAt)) + ' 신고' : "") + '</p><p class="mt-2 line-clamp-2 text-xs text-ink-600">' + esc(p.function || "") + '</p><div class="mt-3">' + window.Affiliate.buttonsHtml(p.shopQuery || p.name.replace(/^\[샘플\]\s*/, ""), { size: "sm", short: true }) + '</div></div>';
    }).join("") + "</div>";
    html += '<a href="' + D.productsUrl(it.id) + '" class="mt-4 inline-flex items-center gap-1 text-sm font-bold text-brand-700 hover:underline">' + esc(it.name) + ' 함유 제품 전체 보기 <i data-lucide="arrow-right" class="h-4 w-4"></i></a>';
    el.innerHTML = html; D.icons(el);
  }

  function render(core, it) {
    var cat = core.categories[it.category] || {};
    document.title = it.name + " 효능·권장량·궁합 | " + (window.SITE && window.SITE.name);
    var md = document.querySelector('meta[name="description"]'); if (md) md.content = it.summary;
    var ogt = document.querySelector('meta[property="og:title"]'); if (ogt) ogt.content = document.title;
    var ogd = document.querySelector('meta[property="og:description"]'); if (ogd) ogd.content = it.summary;

    var hero = document.getElementById("ingredient-hero");
    hero.innerHTML =
      '<nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="' + D.url("index.html") + '">홈</a> › <a class="hover:text-brand-700" href="' + D.url("ingredients.html") + '">성분 사전</a> › <a class="hover:text-brand-700" href="' + D.url("ingredients.html?category=" + it.category) + '">' + esc(cat.label || "") + '</a> › <span class="text-ink-800">' + esc(it.name) + '</span></nav>' +
      '<div class="mt-4 flex flex-col gap-5 md:flex-row md:items-start md:justify-between">' +
        '<div class="flex items-start gap-4"><span class="grid h-16 w-16 shrink-0 place-items-center rounded-2xl ring-1 ' + D.catClass(cat.color) + '"><i data-lucide="' + esc(it.icon || cat.icon) + '" class="h-8 w-8"></i></span>' +
        '<div><span class="rounded-full px-2.5 py-1 text-[11px] font-bold ring-1 ' + D.catClass(cat.color) + '">' + esc(cat.label || "") + '</span><h1 class="mt-2 text-3xl font-extrabold tracking-tight text-ink-900 sm:text-4xl">' + esc(it.name) + '</h1><p class="mt-1 text-sm font-medium text-ink-400">' + esc(it.en) + (it.aliases && it.aliases.length ? ' · ' + esc(it.aliases.slice(0, 4).join(", ")) : "") + '</p>' +
        '<p class="mt-4 max-w-2xl text-[15px] leading-relaxed text-ink-700">' + esc(it.summary) + '</p>' +
        '<div class="mt-4 flex flex-wrap gap-1.5">' + (it.tags || []).map(function (t) { return '<a href="' + D.url("ingredients.html?tag=" + encodeURIComponent(t)) + '" class="rounded-md bg-white px-2 py-1 text-xs font-semibold text-ink-600 ring-1 ring-ink-200 hover:ring-brand-300">#' + esc(t) + '</a>'; }).join("") + '</div></div></div>' +
        '<div class="flex shrink-0 flex-col gap-2 md:w-64"><a href="' + D.compatUrl([it.id]) + '" class="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-3 text-sm font-bold text-white shadow-lift hover:bg-brand-700"><i data-lucide="heart-handshake" class="h-4 w-4"></i>다른 영양제와 궁합 보기</a><a href="#shop" class="inline-flex items-center justify-center gap-2 rounded-xl border border-ink-200 bg-white px-4 py-3 text-sm font-bold text-ink-800 hover:border-brand-300"><i data-lucide="shopping-cart" class="h-4 w-4"></i>제품 찾아보기</a></div>' +
      '</div>';

    var quick = document.getElementById("ingredient-quick");
    quick.innerHTML = [
      { icon: "clock", k: "섭취 시간", v: it.timing.label, s: it.timing.note },
      { icon: "flask-conical", k: "하루 권장", v: it.dosage.daily, s: "" },
      { icon: "shield-alert", k: "상한 섭취량", v: it.dosage.upper, s: "" },
      { icon: it.fatSoluble ? "droplets" : "glass-water", k: "용해성", v: it.fatSoluble ? "지용성 (식사와 함께)" : "수용성", s: "" }
    ].map(function (q) {
      return '<div class="rounded-2xl border border-ink-100 bg-white p-4 shadow-card"><div class="flex items-center gap-2 text-xs font-bold text-ink-400"><i data-lucide="' + q.icon + '" class="h-4 w-4 text-brand-600"></i>' + esc(q.k) + '</div><p class="mt-2 text-sm font-extrabold leading-snug text-ink-900">' + esc(q.v) + '</p>' + (q.s ? '<p class="mt-1 text-xs text-ink-500">' + esc(q.s) + '</p>' : "") + '</div>';
    }).join("");

    var main = document.getElementById("ingredient-main");
    main.innerHTML =
      section("식약처 인정 기능성", "badge-check", '<p class="rounded-xl bg-brand-50 p-4 text-[15px] font-semibold leading-relaxed text-brand-900">' + esc(it.mfdsFunction || "고시형 기능성 원료 아님") + '</p><p class="mt-2 text-xs text-ink-400">식품의약품안전처 건강기능식품 기능성 원료 고시·개별인정 내용을 요약한 것입니다. 제품별 인정 내용은 라벨을 확인하세요.</p>') +
      section("이런 효과를 기대할 수 있어요", "sparkles", list(it.benefits, "list-check")) +
      section("권장 섭취량과 복용법", "flask-conical",
        '<dl class="grid gap-3 sm:grid-cols-2"><div class="rounded-xl bg-ink-50 p-4"><dt class="text-xs font-bold text-ink-400">하루 권장</dt><dd class="mt-1 font-bold text-ink-900">' + esc(it.dosage.daily) + '</dd></div><div class="rounded-xl bg-ink-50 p-4"><dt class="text-xs font-bold text-ink-400">상한 섭취량</dt><dd class="mt-1 font-bold text-ink-900">' + esc(it.dosage.upper) + '</dd></div></dl>' +
        (it.dosage.note ? '<p class="mt-3 flex items-start gap-2 text-sm text-ink-600"><i data-lucide="lightbulb" class="mt-0.5 h-4 w-4 shrink-0 text-amber-500"></i>' + esc(it.dosage.note) + '</p>' : "") +
        '<div class="mt-4 flex items-start gap-3 rounded-xl border border-brand-100 bg-brand-50/60 p-4"><i data-lucide="clock" class="mt-0.5 h-5 w-5 shrink-0 text-brand-600"></i><div><p class="font-bold text-brand-900">' + esc(it.timing.label) + '</p><p class="mt-0.5 text-sm text-brand-900/80">' + esc(it.timing.note || "") + '</p></div></div>') +
      section("이런 분께 추천해요", "user", list(it.whoFor, "list-dot")) +
      section("섭취 시 주의사항", "triangle-alert", list(it.cautions, "list-warn") + (it.drugCautions && it.drugCautions.length ? '<h3 class="mt-5 text-sm font-bold text-rose-700">약과 함께 먹을 때</h3>' + list(it.drugCautions, "list-warn") : "") + '<p class="mt-4 text-xs text-ink-400">질환이 있거나 약을 복용 중이라면 섭취 전 의사·약사와 상담하세요.</p>', "ring-1 ring-amber-100") +
      section(it.name + " 궁합 한눈에", "heart-handshake", compatBlock(core, it)) +
      '<section id="shop" class="rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="shopping-cart" class="h-5 w-5 text-brand-600"></i>' + esc(it.name) + ' 제품 찾기</h2><p class="mt-2 text-sm text-ink-500">쇼핑몰에서 "' + esc(it.shopQuery) + '" 검색 결과로 바로 이동합니다. 함량·형태·보장균수 등은 제품 라벨을 꼭 확인하세요.</p><div class="mt-4">' + window.Affiliate.buttonsHtml(it.shopQuery) + '</div><div id="ingredient-products" class="mt-6"><div class="skeleton h-24"></div></div><p class="mt-4 text-[11px] text-ink-400">' + esc(window.Affiliate.disclosure()) + '</p></section>' +
      (it.faq && it.faq.length ? section("자주 묻는 질문", "circle-help", it.faq.map(function (f) { return '<details class="group border-b border-ink-100 py-3 last:border-0"><summary class="flex cursor-pointer list-none items-center justify-between gap-3 font-bold text-ink-900"><span>Q. ' + esc(f.q) + '</span><i data-lucide="chevron-down" class="h-4 w-4 shrink-0 text-ink-400 transition group-open:rotate-180"></i></summary><p class="mt-2 text-sm leading-relaxed text-ink-600">' + esc(f.a) + '</p></details>'; }).join("")) : "");

    var side = document.getElementById("ingredient-side");
    var sameCat = core.items.filter(function (x) { return x.category === it.category && x.id !== it.id; }).slice(0, 6);
    side.innerHTML =
      '<div class="rounded-2xl border border-ink-100 bg-white p-5 shadow-card"><h2 class="text-sm font-bold text-ink-900">같은 분류의 성분</h2><ul class="mt-3 space-y-1">' + sameCat.map(function (x) { return '<li><a class="flex items-center gap-2 rounded-lg px-2 py-2 text-sm font-semibold text-ink-700 hover:bg-brand-50 hover:text-brand-700" href="' + D.ingredientUrl(x.id) + '"><i data-lucide="' + esc(x.icon || "pill") + '" class="h-4 w-4 text-ink-400"></i>' + esc(x.name) + '</a></li>'; }).join("") + '</ul></div>' +
      '<div class="mt-4 rounded-2xl bg-gradient-to-br from-brand-600 to-brand-800 p-5 text-white shadow-lift"><h2 class="text-base font-extrabold">복용 시간표가 필요하세요?</h2><p class="mt-1 text-sm text-white/85">먹고 있는 영양제를 모두 선택하면 간격을 고려한 하루 시간표를 만들어 드립니다.</p><a href="' + D.compatUrl([it.id]) + '" class="mt-3 inline-flex items-center gap-1 rounded-lg bg-white px-3 py-2 text-sm font-bold text-brand-700">궁합 체크 열기 <i data-lucide="arrow-right" class="h-4 w-4"></i></a></div>';

    // JSON-LD (정적 페이지에 이미 있으면 생략)
    if (!document.getElementById("ld-ingredient")) {
      try {
        var ld = { "@context": "https://schema.org", "@graph": [
          { "@type": "BreadcrumbList", "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "홈", "item": (window.SITE.url || "") + "/" },
            { "@type": "ListItem", "position": 2, "name": "성분 사전", "item": (window.SITE.url || "") + "/ingredients.html" },
            { "@type": "ListItem", "position": 3, "name": it.name }] },
          { "@type": "Article", "headline": it.name + " 효능·권장량·궁합", "description": it.summary, "author": { "@type": "Organization", "name": window.SITE.name } }
        ] };
        if (it.faq && it.faq.length) ld["@graph"].push({ "@type": "FAQPage", "mainEntity": it.faq.map(function (f) { return { "@type": "Question", "name": f.q, "acceptedAnswer": { "@type": "Answer", "text": f.a } }; }) });
        var s = document.createElement("script"); s.type = "application/ld+json"; s.id = "ld-ingredient"; s.textContent = JSON.stringify(ld); document.head.appendChild(s);
      } catch (e) {}
    }
    var ssr = document.getElementById("ssr"); if (ssr) ssr.remove();
    document.getElementById("ingredient-app").classList.remove("hidden");
    D.icons();
    window.Affiliate.ready().then(function () { D.products().then(function (p) { renderProducts(it, p); }).catch(function () { var el = document.getElementById("ingredient-products"); if (el) el.innerHTML = ""; }); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    D.core().then(function (core) {
      var it = core.byId[id];
      if (!it) {
        document.getElementById("ingredient-hero").innerHTML = '<div class="rounded-2xl border border-rose-100 bg-rose-50 p-6"><h1 class="text-xl font-extrabold text-rose-700">성분을 찾을 수 없습니다</h1><p class="mt-2 text-sm text-rose-800">주소가 잘못되었거나 아직 등록되지 않은 성분입니다.</p><a class="mt-4 inline-block font-bold text-brand-700 underline" href="' + D.url("ingredients.html") + '">성분 사전으로 이동</a></div>';
        document.getElementById("ingredient-app").classList.remove("hidden");
        var ssr = document.getElementById("ssr"); if (ssr) ssr.remove();
        return;
      }
      render(core, it);
    }).catch(function (e) { console.error(e); });
  });
})();
