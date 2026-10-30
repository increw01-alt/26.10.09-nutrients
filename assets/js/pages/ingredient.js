/* 성분 상세 페이지 (정적 생성 페이지 i/*.html 과 ingredient.html?id= 공용) */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var id = window.__INGREDIENT_ID || D.qs("id");

  var TL = null;   // 용어 자동 링크(assets/js/terms.js) — 용어 색인을 받으면 만들어지고, 없으면 esc 만 한다
  function tlink(text, state) { var s = esc(text); return TL ? TL.link(s, D.url(""), state) : s; }
  function section(title, icon, bodyHtml, extraClass, id) {
    return '<section' + (id ? ' id="' + id + '"' : "") + ' class="scroll-mt-36 rounded-2xl border border-ink-100 bg-white p-6 shadow-card ' + (extraClass || "") + '"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="' + icon + '" class="h-5 w-5 text-brand-600"></i>' + esc(title) + '</h2><div class="mt-4">' + bodyHtml + '</div></section>';
  }
  function list(arr, cls, fn) { return arr && arr.length ? '<ul class="' + cls + ' text-[15px] text-ink-700">' + arr.map(function (x) { return "<li>" + (fn ? fn(x) : esc(x)) + "</li>"; }).join("") + "</ul>" : '<p class="text-sm text-ink-400">해당 없음</p>'; }

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

  function materialCard(g) {
    return '<div class="rounded-xl border border-ink-100 bg-white p-4"><div class="flex flex-wrap items-center gap-2"><span class="rounded-full px-2 py-0.5 text-[11px] font-bold ' + (g.type === "고시형" ? "bg-sky-50 text-sky-700" : "bg-violet-50 text-violet-700") + '">' + esc(g.type) + '</span><p class="font-bold text-ink-900">' + esc(g.name) + '</p></div>' +
      (g.function ? '<p class="mt-2 text-sm leading-relaxed text-ink-700">' + esc(g.function) + '</p>' : "") +
      '<dl class="mt-3 grid gap-x-4 gap-y-1 text-xs text-ink-600 sm:grid-cols-2">' +
      (g.intake ? '<div><dt class="inline font-bold text-ink-500">1일 섭취량</dt> <dd class="inline">' + esc(g.intake) + '</dd></div>' : "") +
      (g.recognitionNo ? '<div><dt class="inline font-bold text-ink-500">인정번호</dt> <dd class="inline">' + esc(g.recognitionNo) + (g.recognizedAt ? ' (' + esc(D.fmtDate(g.recognizedAt)) + ')' : "") + '</dd></div>' : "") +
      (g.companyCount ? '<div><dt class="inline font-bold text-ink-500">인정 업체</dt> <dd class="inline">' + esc((g.companies || []).slice(0, 2).join(", ")) + (g.companyCount > 2 ? ' 외 ' + (g.companyCount - 2) + '곳' : "") + '</dd></div>' : "") +
      '</dl>' +
      (g.caution ? '<details class="mt-2 text-xs"><summary class="cursor-pointer font-semibold text-amber-700">섭취 시 주의사항</summary><p class="mt-1 whitespace-pre-line text-ink-600">' + esc(g.caution) + '</p></details>' : "") +
      '</div>';
  }

  function renderMaterials(it) {
    var el = document.getElementById("ingredient-materials"); if (!el) return;
    // meta.json 에 원료 파일이 있는 성분 목록이 있으므로, 없는 성분은 요청 자체를 하지 않음
    D.meta().catch(function () { return {}; }).then(function (m) {
      var has = m && m.materials && m.materials.ingredients;
      if (has && has.indexOf(it.id) < 0) return [];
      return D.materialsFor(it.id);
    }).then(function (items) {
      if (!items.length) { el.remove(); return; }
      var shown = items.slice(0, 6);
      el.innerHTML = '<h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="badge-check" class="h-5 w-5 text-brand-600"></i>식약처 인정 원료 데이터 <span class="text-sm font-semibold text-ink-400">' + items.length + '건</span></h2>' +
        '<p class="mt-2 text-sm text-ink-500">식품의약품안전처가 인정한 ' + esc(it.name) + ' 관련 기능성 원료의 공식 기능성 내용·1일 섭취량·주의사항입니다. 제품 라벨의 원료명과 비교해 보세요.</p>' +
        '<div class="mt-4 grid gap-3">' + shown.map(materialCard).join("") + '</div>' +
        (items.length > shown.length ? '<a href="' + D.url("materials.html?ingredient=" + encodeURIComponent(it.id)) + '" class="mt-4 inline-flex items-center gap-1 text-sm font-bold text-brand-700 hover:underline">관련 원료 ' + items.length + '건 전체 보기 <i data-lucide="arrow-right" class="h-4 w-4"></i></a>' : "") +
        '<p class="mt-3 text-[11px] text-ink-400">출처: 식품안전나라 건강기능식품 기능성 원료인정현황·개별인정형 정보. 원료의 인정 내용은 해당 원료를 사용한 제품에만 적용됩니다.</p>';
      D.icons(el);
    }).catch(function () { el.remove(); });
  }

  function renderProducts(it, items, sample) {
    var el = document.getElementById("ingredient-products"); if (!el) return;
    items = (items || []).slice(0, 6);
    var html = (sample ? '<p class="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">아래 제품은 <strong>샘플 데이터</strong>입니다. 식약처 API 키를 설정하고 수집 스크립트를 실행하면 실제 신고 제품으로 교체됩니다.</p>' : "");
    if (!items.length) html += '<p class="text-sm text-ink-400">이 성분이 포함된 신고 제품이 아직 수집되지 않았습니다.</p>';
    else html += '<p class="mb-3 text-xs text-ink-500">식약처에 신고된 ' + esc(it.name) + ' 함유 제품 중 제품명에 성분이 드러나는 단일 목적 제품을 우선 보여드립니다.</p><div class="grid gap-3 sm:grid-cols-2">' + items.map(function (p) {
      return '<div class="rounded-xl border border-ink-100 p-4"><p class="font-bold text-ink-900">' + esc(p.name) + '</p><p class="mt-0.5 text-xs text-ink-500">' + esc(p.company) + (p.registeredAt ? ' · ' + esc(D.fmtDate(p.registeredAt)) + ' 신고' : "") + (p.shape ? ' · ' + esc(p.shape) : "") + '</p><p class="mt-2 line-clamp-2 whitespace-pre-line text-xs text-ink-600">' + esc(p.function || p.f || "") + '</p><div class="mt-3">' + window.Affiliate.buttonsHtml(p.shopQuery || p.name.replace(/^\[샘플\]\s*/, ""), { size: "sm", short: true }) + '</div></div>';
    }).join("") + "</div>";
    html += '<a href="' + D.productsUrl(it.id) + '" class="mt-4 inline-flex items-center gap-1 text-sm font-bold text-brand-700 hover:underline">' + esc(it.name) + ' 함유 제품 전체 보기 <i data-lucide="arrow-right" class="h-4 w-4"></i></a>';
    el.innerHTML = html; D.icons(el);
  }

  function render(core, it) {
    var st = { used: {}, count: 0, exclude: {} };   // 용어 자동 링크 상태 (페이지당 첫 등장만, 권장량 메모 → 시간 메모 → 주의 → FAQ 순)
    var cat = core.categories[it.category] || {};
    document.title = it.name + " 효능·권장량·궁합·먹는 시간 | " + (window.SITE && window.SITE.name);   // 빌드가 넣는 정적 <title> 과 같은 틀 (scripts/build_site.py render_page)
    var md = document.querySelector('meta[name="description"]'); if (md) md.content = it.summary;
    var ogt = document.querySelector('meta[property="og:title"]'); if (ogt) ogt.content = document.title;
    var ogd = document.querySelector('meta[property="og:description"]'); if (ogd) ogd.content = it.summary;

    var I = window.Illus;
    // 상단 사진: 빌드가 #ingredient-hero 에 넣은 data-photo(파일명?v=해시)·data-photo-claim(금색 한 줄)·data-photo-scope 를 읽는다 (scripts/build_site.py hero_photo_attrs).
    // 속성이 없는 옛 빌드면 해시 없는 주소로 사진만.
    var hero = document.getElementById("ingredient-hero"), ds = hero.dataset || {};
    var photoSrc = ds.photo ? D.url("assets/images/ingredients/" + ds.photo) : (I ? I.ingPhotoUrl(it.id) : "");
    var claimHtml = ds.photoClaim ? '<p class="ing-hero-claim">' + esc(ds.photoClaim) + '<small>' + (ds.photoScope === "individual" ? "개별인정 원료 기준 식약처 인정 기능성" : "식약처 인정 기능성") + ' · 대표 급원 사진</small></p>' : "";
    var cut = it.summary.indexOf("다. ");
    var tagline = (cut > 0 ? it.summary.slice(0, cut + 2) : it.summary).slice(0, 70);
    hero.innerHTML =
      '<div class="mx-auto max-w-7xl px-4 pb-10 pt-8 sm:px-6 sm:pt-10">' +
      '<nav class="text-xs text-ink-500" aria-label="경로"><a class="hover:text-brand-700" href="' + D.url("index.html") + '">홈</a> › <a class="hover:text-brand-700" href="' + D.url("ingredients.html") + '">성분 사전</a> › <a class="hover:text-brand-700" href="' + D.url("ingredients.html?category=" + it.category) + '">' + esc(cat.label || "") + '</a> › <span class="text-ink-800">' + esc(it.name) + '</span></nav>' +
      '<div class="mt-5 grid gap-8 lg:grid-cols-12 lg:items-start">' +
        '<div class="lg:col-span-5"><div class="ing-hero-photo"><img src="' + photoSrc + '" alt="" width="640" height="640" fetchpriority="high" decoding="async">' + claimHtml + '</div>' +
          '<div class="mt-3 flex gap-2"><div class="thumb thumb-photo">' + (I ? I.ingThumb(it, "h-full w-full object-cover") : "") + '</div><div class="thumb">' + (I ? I.forCategory(it.category) : "") + '</div><div class="thumb"><i data-lucide="' + esc(it.icon || cat.icon || "pill") + '" class="h-7 w-7 text-brand-700"></i></div></div></div>' +
        '<div class="lg:col-span-7">' +
          '<p class="eyebrow-kicker"><i data-lucide="leaf"></i> 성분 사전 <span class="text-ink-300">·</span> <span class="rounded-full px-2.5 py-0.5 text-[11px] font-bold ring-1 ' + D.catClass(cat.color) + '">' + esc(cat.label || "") + '</span></p>' +
          '<h1 class="page-title mt-3">' + esc(it.name) + '</h1>' +
          '<p class="mt-1.5 text-sm font-medium text-ink-400">' + esc(it.en) + '</p>' +
          '<p class="page-lead mt-3">' + esc(tagline) + '</p>' +
          '<dl class="kv-table mt-5 rounded-2xl border border-ink-100 bg-white px-5 py-1 shadow-card">' +
            '<dt>주요 기능성</dt><dd>' + esc((it.mfdsFunction || "고시형 기능성 원료 아님").split(" · ").slice(0, 2).join(" · ")) + '</dd>' +
            '<dt>하루 권장</dt><dd>' + esc(it.dosage.daily) + '</dd>' +
            '<dt>상한 섭취량</dt><dd>' + esc(it.dosage.upper) + '</dd>' +
            '<dt>섭취 시간</dt><dd>' + esc(it.timing.label) + (it.timing.note ? '<span class="block text-xs text-ink-500">' + esc(it.timing.note) + '</span>' : "") + '</dd>' +
            '<dt>용해성</dt><dd>' + (it.fatSoluble ? "지용성 — 지방이 포함된 식사와 함께" : "수용성") + '</dd>' +
            (it.whoFor && it.whoFor.length ? '<dt>이런 분께</dt><dd>' + esc(it.whoFor.slice(0, 2).join(" · ")) + '</dd>' : "") +
          '</dl>' +
          '<div class="mt-5 flex flex-wrap gap-3">' +
            '<a href="#shop" class="btn-primary app-hide"><i data-lucide="shopping-bag"></i>제품 찾아보기 <i data-lucide="arrow-right"></i></a>' +
            '<a href="' + D.compatUrl([it.id]) + '" class="btn-outline"><i data-lucide="heart-handshake" class="text-brand-600"></i>다른 영양제와 궁합 보기</a>' +
            (window.Store ? (function () {   // '내 영양제에 추가' (기기 내 저장, 클릭은 layout.js 의 [data-my-add] 공통 처리)
              var inMy = window.Store.load().items.some(function (i) { return i.id === it.id; });
              return inMy ? '<a class="btn-outline is-added" href="' + D.url("my.html") + '" data-my-added="' + esc(it.id) + '"><i data-lucide="check"></i>내 영양제에 있어요 · 보기</a>'   // 버튼 안 링크 대신 링크 자체
                : '<button type="button" class="btn-outline" data-my-add="' + esc(it.id) + '"><i data-lucide="plus"></i>내 영양제에 추가</button>';
            })() : "") +
          '</div>' +
          '<div class="mt-4 flex flex-wrap gap-1.5">' + (it.tags || []).map(function (t) { return '<a href="' + D.url("ingredients.html?tag=" + encodeURIComponent(t)) + '" class="rounded-full bg-white/80 px-2.5 py-1 text-xs font-semibold text-ink-600 ring-1 ring-[#e3ebdc] hover:bg-white hover:text-brand-700">#' + esc(t) + '</a>'; }).join("") + '</div>' +
        '</div>' +
      '</div></div>';

    // 탭 (섹션 앵커)
    var quick = document.getElementById("ingredient-quick");
    quick.className = "detail-tabs mt-2 scroll-x -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0";
    var TABS = [["sec-info", "성분 정보"], ["sec-intake", "섭취 가이드"], ["sec-compat", "궁합"], ["ingredient-materials", "인정 원료"], ["shop", "제품 찾기"], ["sec-faq", "FAQ"]];
    quick.innerHTML = '<div class="flex">' + TABS.map(function (t, i) { return '<a href="#' + t[0] + '" data-tab="' + t[0] + '" class="' + (i === 0 ? "active" : "") + '">' + t[1] + '</a>'; }).join("") + '</div>';
    quick.addEventListener("click", function (e) { var a = e.target.closest("a[data-tab]"); if (!a) return; quick.querySelectorAll("a").forEach(function (x) { x.classList.toggle("active", x === a); }); });

    var main = document.getElementById("ingredient-main");
    main.innerHTML =
      section("식약처 인정 기능성", "badge-check", '<p class="rounded-xl bg-brand-50 p-4 text-[15px] font-semibold leading-relaxed text-brand-900">' + esc(it.mfdsFunction || "고시형 기능성 원료 아님") + '</p><p class="mt-2 text-xs text-ink-400">식품의약품안전처 건강기능식품 기능성 원료 고시·개별인정 내용을 요약한 것입니다. 제품별 인정 내용은 라벨을 확인하세요.</p><div id="ingredient-functions" class="mt-3 flex flex-wrap items-center gap-2"></div><div id="ingredient-compares" class="mt-2 flex flex-wrap items-center gap-2"></div><div id="ingredient-drugs" class="mt-2 flex flex-wrap items-center gap-2"></div>', "", "sec-info") +
      '<section id="ingredient-materials" class="scroll-mt-36 rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><div class="skeleton h-16"></div></section>' +
      section("이런 효과를 기대할 수 있어요", "sparkles", list(it.benefits, "list-check")) +
      section("권장 섭취량과 복용법", "flask-conical",
        '<dl class="grid gap-3 sm:grid-cols-2"><div class="rounded-xl bg-ink-50 p-4"><dt class="text-xs font-bold text-ink-400">하루 권장</dt><dd class="mt-1 font-bold text-ink-900">' + esc(it.dosage.daily) + '</dd></div><div class="rounded-xl bg-ink-50 p-4"><dt class="text-xs font-bold text-ink-400">상한 섭취량</dt><dd class="mt-1 font-bold text-ink-900">' + esc(it.dosage.upper) + '</dd></div></dl>' +
        (it.dosage.note ? '<p class="mt-3 flex items-start gap-2 text-sm text-ink-600"><i data-lucide="lightbulb" class="mt-0.5 h-4 w-4 shrink-0 text-amber-500"></i>' + tlink(it.dosage.note, st) + '</p>' : "") +
        '<div class="mt-4 flex items-start gap-3 rounded-xl border border-brand-100 bg-brand-50/60 p-4"><i data-lucide="clock" class="mt-0.5 h-5 w-5 shrink-0 text-brand-600"></i><div><p class="font-bold text-brand-900">' + esc(it.timing.label) + '</p><p class="mt-0.5 text-sm text-brand-900/80">' + tlink(it.timing.note || "", st) + '</p></div></div>' +
        '<p class="mt-3 text-xs"><a class="font-bold text-brand-700 hover:underline" href="' + D.url("timing-chart.html") + '#' + encodeURIComponent(it.id) + '">영양제 복용 시간표에서 다른 성분과 비교 <i data-lucide="arrow-right" class="inline h-3.5 w-3.5"></i></a></p>', "", "sec-intake") +
      section("이런 분께 추천해요", "user", list(it.whoFor, "list-dot")) +
      section("섭취 시 주의사항", "triangle-alert", list(it.cautions, "list-warn", function (x) { return tlink(x, st); }) + (it.drugCautions && it.drugCautions.length ? '<h3 class="mt-5 text-sm font-bold text-rose-700">약과 함께 먹을 때</h3>' + list(it.drugCautions, "list-warn", function (x) { return tlink(x, st); }) : "") + '<p class="mt-4 text-xs text-ink-400">질환이 있거나 약을 복용 중이라면 섭취 전 의사·약사와 상담하세요.</p>', "ring-1 ring-amber-100") +
      section(it.name + " 궁합 한눈에", "heart-handshake", compatBlock(core, it) + '<p class="mt-4 text-xs"><a class="font-bold text-brand-700 hover:underline" href="' + D.url("compatibility-chart.html") + '#' + encodeURIComponent(it.id) + '">전체 영양제 궁합표에서 ' + esc(it.name) + ' 보기 <i data-lucide="arrow-right" class="inline h-3.5 w-3.5"></i></a></p>', "", "sec-compat") +
      '<section id="shop" class="app-hide scroll-mt-36 rounded-2xl border border-ink-100 bg-white p-6 shadow-card"><h2 class="flex items-center gap-2 text-lg font-extrabold text-ink-900"><i data-lucide="shopping-cart" class="h-5 w-5 text-brand-600"></i>' + esc(it.name) + ' 제품 찾기</h2><p class="mt-2 text-sm text-ink-500">쇼핑몰에서 "' + esc(it.shopQuery) + '" 검색 결과로 바로 이동합니다. 함량·형태·보장균수 등은 제품 라벨을 꼭 확인하세요.</p><div class="mt-4">' + window.Affiliate.buttonsHtml(it.shopQuery) + '</div><div id="ingredient-products" class="mt-6"><div class="skeleton h-24"></div></div><p class="mt-4 text-[11px] text-ink-400">' + esc(window.Affiliate.disclosure()) + '</p></section>' +
      (it.faq && it.faq.length ? section("자주 묻는 질문", "circle-help", it.faq.map(function (f) { return '<details class="group border-b border-ink-100 py-3 last:border-0"><summary class="flex cursor-pointer list-none items-center justify-between gap-3 font-bold text-ink-900"><span>Q. ' + esc(f.q) + '</span><i data-lucide="chevron-down" class="h-4 w-4 shrink-0 text-ink-400 transition group-open:rotate-180"></i></summary><p class="mt-2 text-sm leading-relaxed text-ink-600">' + tlink(f.a, st) + '</p></details>'; }).join(""), "", "sec-faq") : "");

    // 이 성분이 들어간 기능성별 허브 페이지 칩 (data/functions-index.json, 빌드 생성)
    D.functions().then(function (fx) {
      var box = document.getElementById("ingredient-functions"); if (!box) return;
      var mine = ((fx && fx.items) || []).filter(function (f) { return (f.ingredients || []).indexOf(it.id) >= 0; });
      if (!mine.length) { box.remove(); return; }
      box.innerHTML = '<span class="text-xs font-bold text-ink-500">기능성별 페이지:</span>' + mine.map(function (f) { return '<a class="chart-chip" href="' + D.url("function/" + encodeURIComponent(f.id) + ".html") + '"><i data-lucide="' + esc(f.icon) + '" class="h-3.5 w-3.5"></i>' + esc(f.label) + '</a>'; }).join("");
      D.icons(box);
    }).catch(function () {});

    // 이 성분이 들어간 성분 비교 글 칩 (data/compares-index.json, 빌드 생성)
    D.compares().then(function (cx) {
      var box = document.getElementById("ingredient-compares"); if (!box) return;
      var mine = ((cx && cx.items) || []).filter(function (c) { return (c.ids || []).indexOf(it.id) >= 0; });
      if (!mine.length) { box.remove(); return; }
      box.innerHTML = '<span class="text-xs font-bold text-ink-500">비교 글:</span>' + mine.map(function (c) { return '<a class="chart-chip" href="' + D.url("compare/" + encodeURIComponent(c.slug) + ".html") + '"><i data-lucide="scale" class="h-3.5 w-3.5"></i>' + esc(c.title) + '</a>'; }).join("");
      D.icons(box);
    }).catch(function () { var box = document.getElementById("ingredient-compares"); if (box) box.remove(); });

    // 이 성분이 '함께 챙기면 좋은/주의할' 성분으로 등장하는 약별 영양제 가이드 칩 (data/drug-guides-index.json, 빌드 생성)
    D.drugGuides().then(function (dx) {
      var box = document.getElementById("ingredient-drugs"); if (!box) return;
      var mine = ((dx && dx.items) || []).map(function (g) { var kind = (g.caution || []).indexOf(it.id) >= 0 ? "caution" : (g.good || []).indexOf(it.id) >= 0 ? "synergy" : ""; return kind ? { g: g, kind: kind } : null; }).filter(Boolean);
      if (!mine.length) { box.remove(); return; }
      box.innerHTML = '<span class="text-xs font-bold text-ink-500">약과 함께:</span>' + mine.map(function (m) { return '<a class="chart-chip chart-chip-' + m.kind + '" href="' + D.url("drug-guide/" + encodeURIComponent(m.g.id) + ".html") + '"><i data-lucide="pill" class="h-3.5 w-3.5"></i>' + esc(m.g.short) + '</a>'; }).join("");
      D.icons(box);
    }).catch(function () { var box = document.getElementById("ingredient-drugs"); if (box) box.remove(); });

    // 탭 활성화: 섹션이 화면 상단에 오면 해당 탭 표시
    try {
      var tabs = document.getElementById("ingredient-quick");
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) { if (en.isIntersecting) tabs.querySelectorAll("a").forEach(function (x) { x.classList.toggle("active", x.getAttribute("data-tab") === en.target.id); }); });
      }, { rootMargin: "-140px 0px -70% 0px" });
      ["sec-info", "sec-intake", "sec-compat", "ingredient-materials", "shop", "sec-faq"].forEach(function (id) { var el = document.getElementById(id); if (el) io.observe(el); });
    } catch (e) { /* 구형 브라우저 무시 */ }

    var side = document.getElementById("ingredient-side");
    var sameCat = core.items.filter(function (x) { return x.category === it.category && x.id !== it.id; }).slice(0, 6);
    D.guides().then(function (gd) {
      var rel = (gd.items || []).filter(function (g) { return (g.ingredients || []).some(function (x) { return x.id === it.id; }); }).slice(0, 6);
      var box = document.getElementById("ingredient-guides"); if (!box || !rel.length) return;
      var types = (gd._meta && gd._meta.types) || {};
      box.innerHTML = '<h2 class="text-sm font-bold text-ink-900">이 성분이 등장하는 가이드</h2><ul class="mt-3 space-y-1">' + rel.map(function (g) { return '<li><a class="flex items-start gap-2 rounded-lg px-2 py-2 text-sm hover:bg-brand-50" href="' + D.guideUrl(g.slug) + '"><i data-lucide="' + esc(g.icon || "book-open") + '" class="mt-0.5 h-4 w-4 shrink-0 text-brand-600"></i><span><span class="block font-semibold text-ink-800">' + esc(g.h1) + '</span><span class="text-[11px] text-ink-400">' + esc((types[g.type] || {}).short || "") + '</span></span></a></li>'; }).join("") + '</ul><a class="mt-2 inline-flex items-center gap-1 px-2 text-xs font-bold text-brand-700 hover:underline" href="' + D.url("guides.html") + '">전체 가이드 보기 <i data-lucide="arrow-right" class="h-3.5 w-3.5"></i></a>';
      box.classList.remove("hidden"); D.icons(box);
    }).catch(function () {});
    side.innerHTML = '<div id="ingredient-guides" class="mb-4 hidden rounded-2xl border border-brand-100 bg-brand-50/40 p-5"></div>' +
      '<div class="rounded-2xl border border-ink-100 bg-white p-5 shadow-card"><h2 class="text-sm font-bold text-ink-900">같은 분류의 성분</h2><ul class="mt-3 space-y-1">' + sameCat.map(function (x) { return '<li><a class="flex items-center gap-2 rounded-lg px-2 py-2 text-sm font-semibold text-ink-700 hover:bg-brand-50 hover:text-brand-700" href="' + D.ingredientUrl(x.id) + '"><i data-lucide="' + esc(x.icon || "pill") + '" class="h-4 w-4 text-ink-400"></i>' + esc(x.name) + '</a></li>'; }).join("") + '</ul></div>' +
      '<div class="mt-4 rounded-2xl bg-brand-700 p-5 text-white shadow-lift"><h2 class="text-base font-extrabold">복용 시간표가 필요하세요?</h2><p class="mt-1 text-sm text-white/85">먹고 있는 영양제를 모두 선택하면 간격을 고려한 하루 시간표를 만들어 드립니다.</p><a href="' + D.compatUrl([it.id]) + '" class="mt-3 inline-flex items-center gap-1 rounded-lg bg-white px-3 py-2 text-sm font-bold text-brand-700">궁합 체크 열기 <i data-lucide="arrow-right" class="h-4 w-4"></i></a></div>';

    // JSON-LD (정적 페이지에 이미 있으면 생략)
    if (!document.getElementById("ld-ingredient")) {
      try {
        var ld = { "@context": "https://schema.org", "@graph": [
          { "@type": "BreadcrumbList", "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "홈", "item": (window.SITE.url || "") + "/" },
            { "@type": "ListItem", "position": 2, "name": "성분 사전", "item": (window.SITE.url || "") + "/ingredients.html" },
            { "@type": "ListItem", "position": 3, "name": it.name }] },
          { "@type": "Article", "headline": it.name + " 효능·권장량·궁합·먹는 시간", "description": it.summary, "author": { "@type": "Organization", "name": window.SITE.name } }
        ] };
        if (it.faq && it.faq.length) ld["@graph"].push({ "@type": "FAQPage", "mainEntity": it.faq.map(function (f) { return { "@type": "Question", "name": f.q, "acceptedAnswer": { "@type": "Answer", "text": f.a } }; }) });
        var s = document.createElement("script"); s.type = "application/ld+json"; s.id = "ld-ingredient"; s.textContent = JSON.stringify(ld); document.head.appendChild(s);
      } catch (e) {}
    }
    var ssr = document.getElementById("ssr"); if (ssr) ssr.remove();
    document.getElementById("ingredient-app").classList.remove("hidden");
    D.icons();
    renderMaterials(it);
    window.Affiliate.ready().then(function () {
      // 목록 파일(수 MB) 대신 meta.json 으로 샘플 여부만 확인하고, 성분별 상위 파일만 불러옵니다
      D.meta().catch(function () { return {}; }).then(function (m) {
        var sample = !!(m && m.products && m.products.source === "sample");
        return D.productsTop(it.id).then(function (items) { renderProducts(it, items, sample); });
      }).catch(function () { var el = document.getElementById("ingredient-products"); if (el) el.innerHTML = ""; });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Promise.all([D.core(), D.glossary().catch(function () { return null; })]).then(function (r) {   // 용어 색인은 없어도 페이지는 그려진다
      var core = r[0];
      TL = (window.Terms && r[1] && r[1].items) ? window.Terms.build(r[1].items) : null;
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
