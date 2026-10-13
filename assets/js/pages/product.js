/* 제품 상세 페이지 — 식약처 신고 제품의 성분, 함께 먹으면 좋은 성분, 주의할 조합, 신고 정보 */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var id = D.qs("id");

  function show(which) {
    ["product-app", "product-loading", "product-missing"].forEach(function (k) { var el = document.getElementById(k); if (el) el.classList.toggle("hidden", k !== which); });
  }

  /* 제품에 든 성분들을 기준으로 궁합 데이터에서 '함께 먹으면 좋은 성분'과 '주의할 조합'을 뽑는다 */
  function partners(core, ids) {
    var inSet = {}; ids.forEach(function (x) { inSet[x] = true; });
    var good = {}, warn = {}, internal = [];
    core.pairs.forEach(function (p) {
      var a = p.pair[0], b = p.pair[1], aIn = inSet[a], bIn = inSet[b];
      if (aIn && bIn) { if (p.type === "caution" || p.type === "avoid") internal.push(p); return; }
      if (!aIn && !bIn) return;
      var mine = aIn ? a : b, other = aIn ? b : a;
      if (!core.byId[other]) return;
      var bucket = p.type === "synergy" ? good : (p.type === "caution" || p.type === "avoid") ? warn : null;
      if (!bucket) return;
      var e = bucket[other] || (bucket[other] = { id: other, score: 0, reasons: [] });
      e.score += (p.level || 1) + (p.type === "avoid" ? 10 : 0);
      e.reasons.push({ with: mine, title: p.title, type: p.type, hours: p.separateHours, tip: p.tip });
    });
    var sortFn = function (x, y) { return y.score - x.score; };
    return { good: Object.keys(good).map(function (k) { return good[k]; }).sort(sortFn).slice(0, 6), warn: Object.keys(warn).map(function (k) { return warn[k]; }).sort(sortFn).slice(0, 6), internal: internal };
  }

  function ingCard(core, it, reasonHtml, linkIds) {
    var I = window.Illus, cat = core.categories[it.category] || {};
    return '<div class="ing-card">' +
      '<div class="flex items-start justify-between gap-2"><div class="ing-photo left">' + (I ? I.photoImg(it.category) : "") + '</div><span class="rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-bold ring-1 ' + D.catClass(cat.color) + '">' + esc(cat.label || "") + '</span></div>' +
      '<h3 class="mt-2 text-[17px] font-extrabold tracking-tight text-ink-900"><a class="hover:text-brand-700" href="' + D.ingredientUrl(it.id) + '">' + esc(it.name) + '</a></h3>' +
      (reasonHtml || '<p class="mt-1.5 line-clamp-2 text-sm leading-relaxed text-ink-600">' + esc(it.summary || "") + '</p>') +
      '<div class="mt-auto flex items-center justify-between border-t border-[#ece9df] pt-3 text-xs text-ink-500"><span class="inline-flex items-center gap-1"><i data-lucide="clock" class="h-3.5 w-3.5"></i>' + esc(it.timing.label) + '</span>' +
      (linkIds ? '<a class="inline-flex items-center gap-1 font-bold text-brand-700 hover:underline" href="' + D.compatUrl(linkIds) + '">궁합 보기 <i data-lucide="arrow-right" class="h-3.5 w-3.5"></i></a>' : '<a class="inline-flex items-center gap-1 font-bold text-brand-700 hover:underline" href="' + D.ingredientUrl(it.id) + '">성분 정보 <i data-lucide="arrow-right" class="h-3.5 w-3.5"></i></a>') + '</div></div>';
  }
  function section(id, title, icon, body, extra) {
    return '<section id="' + id + '" class="scroll-mt-36 rounded-2xl border border-ink-100 bg-white p-6 shadow-card ' + (extra || "") + '"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="' + icon + '" class="h-5 w-5 text-brand-600"></i>' + title + '</h2>' + body + '</section>';
  }
  function kv(label, value) { return value ? '<dt>' + label + '</dt><dd class="whitespace-pre-line">' + esc(value) + '</dd>' : ""; }

  function render(core, p) {
    var S = window.SITE || {};
    var ids = (p.ingredients || []).filter(function (x) { return !!core.byId[x]; });
    var ings = ids.map(function (x) { return core.byId[x]; });
    var query = p.shopQuery || String(p.name || "").replace(/^\[샘플\]\s*/, "");
    document.title = p.name + " 성분·궁합 | " + (S.name || "영양제.kr");
    var md = document.querySelector('meta[name="description"]'); if (md) md.content = p.name + " — " + (ings.length ? "함유 성분: " + ings.map(function (i) { return i.name; }).join(", ") + ". " : "") + "함께 먹으면 좋은 성분과 주의할 조합, 식약처 신고 정보를 확인하세요.";
    var ogt = document.querySelector('meta[property="og:title"]'); if (ogt) ogt.content = document.title;

    var pr = partners(core, ids);
    var compatHref = ids.length ? D.compatUrl(ids) : D.url("compatibility.html");

    document.getElementById("product-hero").innerHTML =
      '<div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">' +
      '<nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="' + D.url("index.html") + '">홈</a> › <a class="hover:text-brand-700" href="' + D.url("products.html") + '">제품 찾기</a> › <span class="text-ink-800">' + esc(p.name) + '</span></nav>' +
      '<p class="eyebrow-kicker mt-4"><i data-lucide="package"></i> 식약처 신고 건강기능식품</p>' +
      '<h1 class="page-title mt-3">' + esc(p.name) + '</h1>' +
      '<p class="page-lead mt-3">' + esc([p.company, p.shape, p.registeredAt ? D.fmtDate(p.registeredAt) + " 신고" : ""].filter(Boolean).join(" · ")) + '</p>' +
      (ings.length ? '<div class="mt-4 flex flex-wrap items-center gap-2"><span class="text-xs font-bold text-ink-400">함유 성분</span>' + ings.map(function (i) { return '<a class="chip" href="' + D.ingredientUrl(i.id) + '">' + esc(i.name) + '</a>'; }).join("") + '</div>'
        : '<p class="mt-4 text-sm text-ink-500">성분 사전과 연결된 성분이 없는 제품입니다. 아래 원재료명을 참고하세요.</p>') +
      '<div class="mt-6 flex flex-wrap items-center gap-3">' + (ids.length ? '<a href="' + compatHref + '" class="btn-primary"><i data-lucide="heart-handshake"></i>이 제품 성분으로 궁합·시간표 보기 <i data-lucide="arrow-right"></i></a>' : "") +
      '<a href="#sec-shop" class="btn-outline"><i data-lucide="shopping-cart" class="text-brand-600"></i>구매처 보기</a></div>' +
      '</div>';

    var main = document.getElementById("product-main");
    var goodHtml = pr.good.length
      ? '<p class="mt-2 text-sm text-ink-500">이 제품의 성분과 함께 먹었을 때 흡수나 작용을 서로 돕는 것으로 알려진 성분입니다.</p><div class="mt-4 grid gap-4 sm:grid-cols-2">' + pr.good.map(function (e) {
          var it = core.byId[e.id]; var r = e.reasons[0];
          return ingCard(core, it, '<p class="mt-1.5 text-sm leading-relaxed text-ink-700"><strong class="text-brand-700">' + esc(core.byId[r.with].name) + '</strong>와 함께: ' + esc(r.title) + '</p>' + (r.tip ? '<p class="mt-1 text-xs text-ink-500">' + esc(r.tip) + '</p>' : ""), [r.with, e.id]);
        }).join("") + '</div>'
      : '<p class="mt-2 text-sm text-ink-500">' + (ids.length ? "이 제품 성분과 특별히 시너지로 알려진 조합이 아직 등록되지 않았습니다." : "성분 사전과 연결된 성분이 없어 궁합 정보를 제공할 수 없습니다.") + '</p>';
    var warnHtml = (pr.warn.length || pr.internal.length)
      ? (pr.internal.length ? '<div class="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4"><p class="text-sm font-bold text-amber-900">이 제품 안의 성분끼리 주의할 점</p><ul class="list-warn mt-1 text-sm text-amber-900">' + pr.internal.map(function (q) { return '<li><strong>' + esc(core.byId[q.pair[0]].name) + ' + ' + esc(core.byId[q.pair[1]].name) + '</strong> — ' + esc(q.title) + (q.separateHours ? ' (' + q.separateHours + '시간 이상 간격)' : "") + '</li>'; }).join("") + '</ul></div>' : "") +
        (pr.warn.length ? '<p class="mt-3 text-sm text-ink-500">다른 영양제와 같이 먹을 때 시간을 띄우거나 용량을 확인해야 하는 조합입니다.</p><ul class="mt-3 space-y-2">' + pr.warn.map(function (e) {
          var it = core.byId[e.id]; var r = e.reasons[0]; var t = core.types[r.type] || {};
          return '<li class="flex flex-wrap items-start gap-2 rounded-xl border p-3 card-' + r.type + '"><span class="badge ' + D.typeClass(r.type) + '">' + esc(t.short || "") + '</span><span class="min-w-0 flex-1 text-sm text-ink-700">' + (core.byId[r.with] ? '<span class="font-semibold text-ink-500">' + esc(core.byId[r.with].name) + ' + </span>' : "") + '<a class="font-bold text-ink-900 hover:text-brand-700" href="' + D.ingredientUrl(it.id) + '">' + esc(it.name) + '</a> — ' + esc(r.title) + (r.hours ? ' <span class="text-xs font-bold text-amber-700">(' + r.hours + '시간 이상 간격)</span>' : "") + '</span><a class="text-xs font-bold text-brand-700 hover:underline" href="' + D.compatUrl([r.with, e.id]) + '">자세히</a></li>';
        }).join("") + '</ul>' : "")
      : '<p class="mt-2 text-sm text-ink-500">등록된 주의 조합이 없습니다. 각 성분의 상한 섭취량과 섭취 시간은 지켜 주세요.</p>';
    main.innerHTML =
      section("sec-ingredients", "이 제품에 들어 있는 성분", "badge-check",
        (ings.length ? '<p class="mt-2 text-sm text-ink-500">식약처 신고 정보의 기능성·원재료를 성분 사전과 연결한 결과입니다. 함량은 제품 라벨을 확인하세요.</p><div class="mt-4 grid gap-4 sm:grid-cols-2">' + ings.map(function (i) { return ingCard(core, i); }).join("") + '</div>'
          : '<p class="mt-2 text-sm text-ink-500">성분 사전에 아직 없는 원료로 만든 제품입니다.</p>' + (p.rawMaterials ? '<p class="mt-3 whitespace-pre-line rounded-xl bg-ink-50 p-4 text-sm text-ink-700">' + esc(p.rawMaterials) + '</p>' : ""))) +
      section("sec-good", "함께 먹으면 더 좋은 성분", "heart-handshake", goodHtml) +
      section("sec-warn", "시간을 띄우거나 주의할 조합", "clock-alert", warnHtml) +
      section("sec-info", "식약처 신고 정보", "database",
        '<dl class="kv-table mt-3">' + kv("기능성", p.function || p.f) + kv("섭취방법", p.intake) + kv("주의사항", p.caution) + kv("원재료", p.rawMaterials) + kv("신고번호", p.reportNo) + kv("신고일", p.registeredAt ? D.fmtDate(p.registeredAt) : "") + kv("유통기한", p.shelfLife) + kv("정보 갱신", p.lastUpdated ? D.fmtDate(p.lastUpdated) : "") + '</dl>' +
        '<p class="mt-3 text-xs text-ink-400">출처: 식품의약품안전처 식품안전나라 건강기능식품 품목제조신고. 신고 내용은 변경될 수 있으며 실제 제품 라벨이 우선합니다.</p>') +
      section("sec-shop", esc(p.name) + " 구매처 찾기", "shopping-cart",
        '<p class="mt-2 text-sm text-ink-500">쇼핑몰에서 "' + esc(query) + '" 검색 결과로 이동합니다. 함량·형태·가격은 각 쇼핑몰에서 확인하세요.</p><div class="mt-4">' + window.Affiliate.buttonsHtml(query, {}) + '</div><p class="mt-3 text-[11px] text-ink-400">' + esc(window.Affiliate.disclosure()) + '</p>') +
      '<p class="text-xs text-ink-400">이 정보는 일반적인 건강 정보이며 의학적 진단·처방을 대신하지 않습니다. 약을 복용 중이거나 질환이 있다면 의사·약사와 상담하세요.</p>';

    var side = document.getElementById("product-side");
    side.innerHTML =
      (ids.length ? '<div class="rounded-2xl bg-brand-800 p-6 text-white shadow-lift"><p class="text-sm font-bold text-white/80">궁합 체크</p><p class="mt-1 text-lg font-extrabold leading-snug">이 제품의 성분 ' + ids.length + '개를 넣고<br>궁합과 하루 시간표를 만들어 보세요</p><a href="' + compatHref + '" class="btn-primary mt-4 w-full">궁합·시간표 만들기 <i data-lucide="arrow-right"></i></a></div>' : "") +
      '<div id="product-related" class="rounded-2xl border border-ink-100 bg-white p-5 shadow-card"><h2 class="text-sm font-bold text-ink-900">같은 성분의 다른 제품</h2><div class="skeleton mt-3 h-24"></div></div>';
    show("product-app"); D.icons();

    if (ids.length) {
      D.productsTop(ids[0]).then(function (items) {
        var others = items.filter(function (x) { return x.id !== p.id; }).slice(0, 5);
        var box = document.getElementById("product-related"); if (!box) return;
        box.innerHTML = '<h2 class="text-sm font-bold text-ink-900">' + esc(core.byId[ids[0]].name) + ' 함유 다른 제품</h2>' +
          (others.length ? '<ul class="mt-3 divide-y divide-ink-100">' + others.map(function (x) { return '<li class="py-2.5"><a class="block text-sm font-bold text-ink-800 hover:text-brand-700" href="' + D.productUrl(x.id) + '">' + esc(x.name) + '</a><span class="block text-xs text-ink-500">' + esc(x.company || "") + '</span></li>'; }).join("") + '</ul>' : '<p class="mt-3 text-sm text-ink-400">다른 제품이 아직 없습니다.</p>') +
          '<a class="mt-3 inline-flex items-center gap-1 text-sm font-bold text-brand-700 hover:underline" href="' + D.productsUrl(ids[0]) + '">전체 보기 <i data-lucide="arrow-right" class="h-4 w-4"></i></a>';
        D.icons(box);
      }).catch(function () {});
    } else { var box = document.getElementById("product-related"); if (box) box.remove(); }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!id) { show("product-missing"); D.icons(); return; }
    Promise.all([D.core(), D.productDetail(id), window.Affiliate.ready()]).then(function (r) {
      var core = r[0], p = r[1];
      if (p) { render(core, p); return; }
      // 상세 조각에 없으면 경량 색인에서 최소 정보로라도 표시
      return D.productNames().then(function (n) {
        var hit = (n.p || []).filter(function (x) { return x[0] === id; })[0];
        if (!hit) { show("product-missing"); D.icons(); return; }
        render(core, { id: hit[0], name: hit[1], ingredients: hit[2].map(function (i) { return n.i[i]; }) });
      });
    }).catch(function (e) { if (window.console) console.warn(e); show("product-missing"); D.icons(); });
  });
})();
