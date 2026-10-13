/* 의약품 상세 페이지 — 식약처 e약은요·허가정보: 주성분, 성분 사전과 연결된 영양 성분, 함께 먹으면 좋은 성분·주의할 조합, 효능·사용법·상호작용·주의사항 */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var id = D.qs("id");

  function show(which) {
    ["drug-app", "drug-loading", "drug-missing"].forEach(function (k) { var el = document.getElementById(k); if (el) el.classList.toggle("hidden", k !== which); });
  }

  /* 약에 든 영양 성분들을 기준으로 궁합 데이터에서 '함께 먹으면 좋은 성분'과 '주의할 조합'을 뽑는다 (제품 페이지와 같은 계산) */
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
  function para(text, empty) {
    return text ? '<div class="mt-3 whitespace-pre-line text-sm leading-relaxed text-ink-700">' + esc(text) + '</div>'
      : '<p class="mt-2 text-sm text-ink-400">' + (empty || "식약처 e약은요에 등록된 내용이 없습니다.") + '</p>';
  }

  function render(core, p) {
    var S = window.SITE || {};
    var ids = (p.ingredients || []).filter(function (x) { return !!core.byId[x]; });
    var ings = ids.map(function (x) { return core.byId[x]; });
    var ingr = p.ingr || [];
    var otc = p.otc || "의약품";
    document.title = p.name + " 성분·상호작용 | " + (S.name || "영양제.kr");
    var md = document.querySelector('meta[name="description"]'); if (md) md.content = p.name + " — " + (ingr.length ? "주성분: " + ingr.slice(0, 4).join(", ") + ". " : "") + "효능·사용법·상호작용·주의사항(식약처 e약은요)과 함께 먹으면 좋은 영양 성분·주의할 조합을 확인하세요.";
    var ogt = document.querySelector('meta[property="og:title"]'); if (ogt) ogt.content = document.title;

    var pr = partners(core, ids);
    var compatHref = ids.length ? D.compatUrl(ids) : D.url("compatibility.html");

    document.getElementById("drug-hero").innerHTML =
      '<div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10 md:flex md:items-start md:justify-between md:gap-8"><div class="min-w-0">' +
      '<nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="' + D.url("index.html") + '">홈</a> › <span>의약품</span> › <span class="text-ink-800">' + esc(p.name) + '</span></nav>' +
      '<p class="eyebrow-kicker mt-4"><i data-lucide="pill-bottle"></i> 식약처 허가 의약품 · ' + esc(otc) + (p.cancel ? ' · 허가 ' + esc(p.cancel) : "") + '</p>' +
      '<h1 class="page-title mt-3">' + esc(p.name) + '</h1>' +
      '<p class="page-lead mt-3">' + esc([p.company, p.cls, p.permitDate ? D.fmtDate(p.permitDate) + " 허가" : ""].filter(Boolean).join(" · ")) + '</p>' +
      (ingr.length ? '<div class="mt-4 flex flex-wrap items-center gap-2"><span class="text-xs font-bold text-ink-400">주성분</span>' + ingr.map(function (t) { return '<span class="chip cursor-default">' + esc(t) + '</span>'; }).join("") + '</div>'
        : '<p class="mt-4 text-sm text-ink-500">주성분 정보는 허가정보와 연결되는 대로 표시됩니다. 아래 식약처 설명을 참고하세요.</p>') +
      (ings.length ? '<div class="mt-2 flex flex-wrap items-center gap-2"><span class="text-xs font-bold text-ink-400">영양 성분</span>' + ings.map(function (i) { return '<a class="chip active" href="' + D.ingredientUrl(i.id) + '">' + esc(i.name) + '</a>'; }).join("") + '</div>' : "") +
      '<div class="mt-6 flex flex-wrap items-center gap-3">' + (ids.length ? '<a href="' + compatHref + '" class="btn-primary"><i data-lucide="heart-handshake"></i>이 약의 영양 성분으로 궁합·시간표 보기 <i data-lucide="arrow-right"></i></a>' : "") +
      '<a href="#sec-interaction" class="btn-outline"><i data-lucide="triangle-alert" class="text-amber-600"></i>상호작용·주의사항 보기</a></div>' +
      '</div>' +
      (p.image ? '<div id="drug-img" class="mt-6 shrink-0 md:mt-0"><div class="rounded-2xl border border-ink-100 bg-white p-3 shadow-card"><img src="' + esc(p.image) + '" alt="' + esc(p.name) + ' 제품 이미지" class="mx-auto h-40 w-auto max-w-[260px] object-contain" loading="lazy" decoding="async" referrerpolicy="no-referrer"></div><p class="mt-1 text-center text-[11px] text-ink-400">이미지: 식약처 의약품안전나라</p></div>' : "") +
      '</div>';

    var main = document.getElementById("drug-main");
    var nutrientsHtml = ings.length
      ? '<p class="mt-2 text-sm text-ink-500">이 약의 주성분 가운데 성분 사전(영양소)에 있는 것입니다. 함량은 의약품 설명서를 확인하세요.</p><div class="mt-4 grid gap-4 sm:grid-cols-2">' + ings.map(function (i) { return ingCard(core, i); }).join("") + '</div>'
      : '<p class="mt-2 text-sm leading-relaxed text-ink-600">' + (ingr.length ? '주성분(' + esc(ingr.join(", ")) + ')은 성분 사전의 영양소와 겹치지 않습니다. 이 약은 영양제가 아닌 의약품이므로, 함께 먹을 영양제는 아래 <a class="font-bold text-brand-700 hover:underline" href="#sec-interaction">상호작용</a> 항목을 읽고 약사·의사와 확인하세요.' : '주성분 정보가 아직 연결되지 않았습니다. 식약처 허가정보는 매일 새벽 갱신됩니다.') + '</p>';
    var goodHtml = pr.good.length
      ? '<p class="mt-2 text-sm text-ink-500">이 약의 영양 성분과 함께 먹었을 때 흡수나 작용을 서로 돕는 것으로 알려진 성분입니다. 의약품을 복용 중이라면 영양제 추가 전에 약사와 상의하세요.</p><div class="mt-4 grid gap-4 sm:grid-cols-2">' + pr.good.map(function (e) {
          var it = core.byId[e.id]; var r = e.reasons[0];
          return ingCard(core, it, '<p class="mt-1.5 text-sm leading-relaxed text-ink-700"><strong class="text-brand-700">' + esc(core.byId[r.with].name) + '</strong>와 함께: ' + esc(r.title) + '</p>' + (r.tip ? '<p class="mt-1 text-xs text-ink-500">' + esc(r.tip) + '</p>' : ""), [r.with, e.id]);
        }).join("") + '</div>'
      : '<p class="mt-2 text-sm text-ink-500">이 약의 영양 성분과 특별히 시너지로 알려진 조합이 아직 등록되지 않았습니다.</p>';
    var warnHtml = (pr.warn.length || pr.internal.length)
      ? (pr.internal.length ? '<div class="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4"><p class="text-sm font-bold text-amber-900">이 약 안의 영양 성분끼리 주의할 점</p><ul class="list-warn mt-1 text-sm text-amber-900">' + pr.internal.map(function (q) { return '<li><strong>' + esc(core.byId[q.pair[0]].name) + ' + ' + esc(core.byId[q.pair[1]].name) + '</strong> — ' + esc(q.title) + (q.separateHours ? ' (' + q.separateHours + '시간 이상 간격)' : "") + '</li>'; }).join("") + '</ul></div>' : "") +
        (pr.warn.length ? '<p class="mt-3 text-sm text-ink-500">다른 영양제와 같이 먹을 때 시간을 띄우거나 용량을 확인해야 하는 조합입니다.</p><ul class="mt-3 space-y-2">' + pr.warn.map(function (e) {
          var it = core.byId[e.id]; var r = e.reasons[0]; var t = core.types[r.type] || {};
          return '<li class="flex flex-wrap items-start gap-2 rounded-xl border p-3 card-' + r.type + '"><span class="badge ' + D.typeClass(r.type) + '">' + esc(t.short || "") + '</span><span class="min-w-0 flex-1 text-sm text-ink-700">' + (core.byId[r.with] ? '<span class="font-semibold text-ink-500">' + esc(core.byId[r.with].name) + ' + </span>' : "") + '<a class="font-bold text-ink-900 hover:text-brand-700" href="' + D.ingredientUrl(it.id) + '">' + esc(it.name) + '</a> — ' + esc(r.title) + (r.hours ? ' <span class="text-xs font-bold text-amber-700">(' + r.hours + '시간 이상 간격)</span>' : "") + '</span><a class="text-xs font-bold text-brand-700 hover:underline" href="' + D.compatUrl([r.with, e.id]) + '">자세히</a></li>';
        }).join("") + '</ul>' : "")
      : '<p class="mt-2 text-sm text-ink-500">등록된 주의 조합이 없습니다. 각 성분의 상한 섭취량과 섭취 시간은 지켜 주세요.</p>';

    main.innerHTML =
      section("sec-nutrients", "이 약에 들어 있는 영양 성분", "badge-check", nutrientsHtml) +
      (ids.length ? section("sec-good", "함께 먹으면 더 좋은 성분", "heart-handshake", goodHtml) + section("sec-warn", "시간을 띄우거나 주의할 조합", "clock-alert", warnHtml) : "") +
      section("sec-efficacy", "효능·효과", "heart-pulse", para(p.efficacy)) +
      section("sec-usage", "사용법", "clock", para(p.usage)) +
      section("sec-interaction", "상호작용 — 함께 먹으면 안 되는 약·음식", "triangle-alert",
        '<div class="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950">' + (p.interaction ? '<div class="whitespace-pre-line">' + esc(p.interaction) + '</div>' : '<p>식약처 e약은요에 등록된 상호작용 내용이 없습니다.</p>') + '</div>' +
        '<p class="mt-3 text-xs text-ink-500">영양제·건강기능식품과의 상호작용은 여기에 모두 적혀 있지 않습니다. 복용 중인 제품을 약사·의사에게 알리고 확인하세요.</p>') +
      section("sec-caution", "주의사항", "octagon-alert",
        (p.warn ? '<div class="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm leading-relaxed text-rose-900"><p class="font-bold">경고</p><div class="mt-1 whitespace-pre-line">' + esc(p.warn) + '</div></div>' : "") + para(p.caution)) +
      section("sec-side", "부작용", "stethoscope", para(p.sideEffects) + '<p class="mt-3 text-xs text-ink-500">이상반응이 나타나면 복용을 중단하고 의사·약사와 상의하세요.</p>') +
      section("sec-storage", "보관법", "shield", para(p.storage)) +
      section("sec-info", "허가·공개 정보", "database",
        '<dl class="kv-table mt-3">' + kv("업체", p.company) + kv("구분", p.otc) + kv("분류", p.cls) + kv("주성분", ingr.join(", ")) + kv("품목기준코드", p.id) + kv("허가일", p.permitDate ? D.fmtDate(p.permitDate) : "") + kv("정보 공개일", p.openDe ? D.fmtDate(p.openDe) : "") + kv("정보 수정일", p.updateDe ? D.fmtDate(p.updateDe) : "") + '</dl>' +
        '<p class="mt-3 text-xs text-ink-400">출처: 식품의약품안전처 의약품개요정보(e약은요)·의약품 제품 허가정보(공공데이터포털). 허가 사항은 변경될 수 있으며 실제 제품 설명서가 우선합니다.</p>') +
      '<p class="text-xs text-ink-400">이 정보는 식약처 공개 자료를 옮긴 일반 정보이며 진단·처방·복약지도를 대신하지 않습니다. 의약품은 약사·의사의 안내에 따라 복용하세요.</p>';

    var side = document.getElementById("drug-side");
    side.innerHTML =
      (ids.length ? '<div class="rounded-2xl bg-brand-800 p-6 text-white shadow-lift"><p class="text-sm font-bold text-white/80">궁합 체크</p><p class="mt-1 text-lg font-extrabold leading-snug">이 약의 영양 성분 ' + ids.length + '개를 넣고<br>궁합과 하루 시간표를 만들어 보세요</p><a href="' + compatHref + '" class="btn-primary mt-4 w-full">궁합·시간표 만들기 <i data-lucide="arrow-right"></i></a></div>' : "") +
      '<div class="rounded-2xl border border-ink-100 bg-white p-5 shadow-card"><h2 class="flex items-center gap-2 text-sm font-bold text-ink-900"><i data-lucide="pill-bottle" class="h-4 w-4 text-brand-600"></i>약국 구입·복약 안내</h2>' +
      '<p class="mt-2 text-sm leading-relaxed text-ink-600">의약품은 온라인으로 판매되지 않으며 약국에서 구입합니다' + (otc === "전문의약품" ? " (전문의약품은 의사 처방 필요)" : "") + '. 복용 중인 영양제가 있다면 약사에게 알려 상호작용을 확인하세요.</p>' +
      '<a class="mt-3 inline-flex items-center gap-1 text-sm font-bold text-brand-700 hover:underline" href="' + D.url("compatibility.html") + '">내 영양제끼리 궁합 체크 <i data-lucide="arrow-right" class="h-4 w-4"></i></a></div>' +
      (ids.length ? '<div id="drug-related" class="rounded-2xl border border-ink-100 bg-white p-5 shadow-card"><h2 class="text-sm font-bold text-ink-900">같은 영양 성분이 든 건강기능식품</h2><div class="skeleton mt-3 h-24"></div></div>' : "");
    show("drug-app"); D.icons();

    var img = document.querySelector("#drug-img img");
    if (img) img.addEventListener("error", function () { var w = document.getElementById("drug-img"); if (w) w.remove(); });

    if (ids.length) {
      D.productsTop(ids[0]).then(function (items) {
        var others = items.slice(0, 5);
        var box = document.getElementById("drug-related"); if (!box) return;
        box.innerHTML = '<h2 class="text-sm font-bold text-ink-900">' + esc(core.byId[ids[0]].name) + ' 함유 건강기능식품</h2>' +
          (others.length ? '<ul class="mt-3 divide-y divide-ink-100">' + others.map(function (x) { return '<li class="py-2.5"><a class="block text-sm font-bold text-ink-800 hover:text-brand-700" href="' + D.productUrl(x.id) + '">' + esc(x.name) + '</a><span class="block text-xs text-ink-500">' + esc(x.company || "") + '</span></li>'; }).join("") + '</ul>' : '<p class="mt-3 text-sm text-ink-400">연결된 제품이 아직 없습니다.</p>') +
          '<a class="mt-3 inline-flex items-center gap-1 text-sm font-bold text-brand-700 hover:underline" href="' + D.productsUrl(ids[0]) + '">전체 보기 <i data-lucide="arrow-right" class="h-4 w-4"></i></a>';
        D.icons(box);
      }).catch(function () {});
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!id) { show("drug-missing"); D.icons(); return; }
    Promise.all([D.core(), D.drugDetail(id)]).then(function (r) {
      var core = r[0], p = r[1];
      if (p) { render(core, p); return; }
      // 상세 조각에 없으면 검색 색인의 최소 정보로라도 표시
      return D.drugNames().then(function (n) {
        var hit = (n.p || []).filter(function (x) { return x[0] === id; })[0];
        if (!hit) { show("drug-missing"); D.icons(); return; }
        render(core, { id: hit[0], name: hit[1], ingredients: hit[2].map(function (i) { return n.i[i]; }), ingr: hit[3] ? hit[3].split(" · ") : [], otc: hit[4] === 2 ? "전문의약품" : hit[4] === 1 ? "일반의약품" : "", company: (n.c || [])[hit[5]] || "" });
      });
    }).catch(function (e) { if (window.console) console.warn(e); show("drug-missing"); D.icons(); });
  });
})();
