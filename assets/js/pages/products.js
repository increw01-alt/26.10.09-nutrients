/* 제품 찾기 페이지 (식약처 신고 제품 DB + 쇼핑 링크) */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var PAGE = 24;
  var state = { q: D.qs("q") || "", ingredient: D.qs("ingredient") || "", shape: "", page: 1 };
  var core, products;

  function detailHtml(p) {
    return (p.reportNo ? '<div><dt class="inline font-bold">신고번호</dt> <dd class="inline">' + esc(p.reportNo) + '</dd></div>' : "") +
      (p.registeredAt ? '<div><dt class="inline font-bold">신고일</dt> <dd class="inline">' + esc(D.fmtDate(p.registeredAt)) + '</dd></div>' : "") +
      (p.lastUpdated ? '<div><dt class="inline font-bold">식약처 정보 갱신</dt> <dd class="inline">' + esc(D.fmtDate(p.lastUpdated)) + '</dd></div>' : "") +
      (p.function ? '<div><dt class="inline font-bold">기능성</dt> <dd class="inline">' + esc(p.function) + '</dd></div>' : "") +
      (p.intake ? '<div><dt class="inline font-bold">섭취방법</dt> <dd class="inline">' + esc(p.intake) + '</dd></div>' : "") +
      (p.caution ? '<div><dt class="inline font-bold">주의사항</dt> <dd class="inline">' + esc(p.caution) + '</dd></div>' : "") +
      (p.rawMaterials ? '<div><dt class="inline font-bold">원재료</dt> <dd class="inline">' + esc(p.rawMaterials) + '</dd></div>' : "") +
      (p.shelfLife ? '<div><dt class="inline font-bold">유통기한</dt> <dd class="inline">' + esc(p.shelfLife) + '</dd></div>' : "");
  }

  function card(p) {
    var ings = (p.ingredients || []).map(function (id) { return core.byId[id]; }).filter(Boolean);
    var q = p.shopQuery || p.name.replace(/^\[샘플\]\s*/, "");
    var hasDetail = !!(p.rawMaterials || p.intake || p.caution);
    return '<article class="flex flex-col rounded-2xl border border-ink-100 bg-white p-5 shadow-card fade-up" data-id="' + esc(p.id) + '">' +
      '<div class="flex items-start justify-between gap-2"><div class="min-w-0"><h2 class="font-extrabold leading-snug text-ink-900"><a class="hover:text-brand-700" href="' + D.productUrl(p.id) + '">' + esc(p.name) + '</a></h2><p class="mt-1 text-xs text-ink-500">' + esc(p.company || "") + (p.shape ? ' · ' + esc(p.shape) : "") + (p.registeredAt ? ' · ' + esc(D.fmtDate(p.registeredAt)) + ' 신고' : "") + '</p></div>' + (p.isNew ? '<span class="shrink-0 rounded-full bg-brand-600 px-2 py-0.5 text-[10px] font-bold text-white">NEW</span>' : "") + "</div>" +
      '<p class="mt-3 line-clamp-3 whitespace-pre-line text-sm leading-relaxed text-ink-600">' + esc(p.f || p.function || "") + '</p>' +
      (ings.length ? '<div class="mt-3 flex flex-wrap gap-1.5">' + ings.slice(0, 5).map(function (i) { return '<a href="' + D.ingredientUrl(i.id) + '" class="rounded-md bg-brand-50 px-2 py-0.5 text-[11px] font-bold text-brand-700 hover:bg-brand-100">' + esc(i.name) + '</a>'; }).join("") + (ings.length > 5 ? '<span class="text-[11px] text-ink-400">+' + (ings.length - 5) + '</span>' : "") + "</div>" : "") +
      '<details class="mt-3 text-xs text-ink-500" data-detail="' + (hasDetail ? "inline" : "lazy") + '"><summary class="cursor-pointer font-semibold text-ink-600 hover:text-brand-700">신고 정보 더보기</summary><dl class="mt-2 space-y-1.5 whitespace-pre-line rounded-lg bg-ink-50 p-3">' + (hasDetail ? detailHtml(p) : '<div class="text-ink-400">불러오는 중…</div>') + '</dl></details>' +
      '<div class="mt-auto pt-4">' + window.Affiliate.buttonsHtml(q, { size: "sm", short: true }) + '</div></article>';
  }

  /* '더보기'를 펼칠 때 상세 조각 파일에서 전체 신고 정보를 가져옴 */
  function lazyDetail(details) {
    if (details.getAttribute("data-detail") !== "lazy") return;
    details.setAttribute("data-detail", "loading");
    var id = details.closest("article").getAttribute("data-id"), dl = details.querySelector("dl");
    D.productDetail(id).then(function (full) {
      dl.innerHTML = full ? detailHtml(full) : '<div class="text-ink-400">상세 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</div>';
      details.setAttribute("data-detail", full ? "inline" : "lazy");
    });
  }

  var names = null, nameMatch = null;   // 전체 제품 검색 색인 (목록 파일은 성분별 상한이 있어 검색은 색인으로 보완)
  function filtered() {
    var items = products.items.slice();
    if (state.ingredient) items = items.filter(function (p) { return (p.ingredients || []).indexOf(state.ingredient) >= 0; });
    if (state.shape) items = items.filter(function (p) { return (p.shape || "") === state.shape; });
    var q = state.q.trim().toLowerCase();
    if (q) {
      items = items.filter(function (p) { return [p.name, p.company, p.f || p.function || "", p.rawMaterials || ""].join(" ").toLowerCase().indexOf(q) >= 0 || D.has(p.name + " " + (p.company || ""), q); });
      if (nameMatch && !state.shape) {   // 목록에 없는 제품도 색인에서 찾아 덧붙임 (상세는 펼칠 때 조각 파일에서)
        var have = {}; items.forEach(function (p) { have[p.id] = true; });
        nameMatch(q, 400).idx.forEach(function (i) {
          var pp = names.p[i]; if (have[pp[0]]) return;
          var ids = pp[2].map(function (k) { return names.i[k]; });
          if (state.ingredient && ids.indexOf(state.ingredient) < 0) return;
          have[pp[0]] = true;
          items.push({ id: pp[0], name: pp[1], company: (names.c || [])[pp[3]] || "", ingredients: ids, registeredAt: "", shape: "", f: "", fromIndex: true });
        });
      }
    }
    items.sort(function (a, b) { return String(b.registeredAt || "").localeCompare(String(a.registeredAt || "")); });
    return items;
  }

  function render() {
    var items = filtered();
    var total = items.length, pages = Math.max(1, Math.ceil(total / PAGE));
    if (state.page > pages) state.page = pages;
    var slice = items.slice((state.page - 1) * PAGE, state.page * PAGE);
    document.getElementById("product-list").innerHTML = slice.map(card).join("");
    document.getElementById("product-count").textContent = total.toLocaleString() + "개 제품";
    document.getElementById("product-empty").classList.toggle("hidden", total > 0);
    var pg = document.getElementById("pagination");
    if (pages <= 1) pg.innerHTML = "";
    else {
      var btns = [];
      for (var i = 1; i <= pages; i++) { if (pages > 9 && Math.abs(i - state.page) > 3 && i !== 1 && i !== pages) { if (btns[btns.length - 1] !== "…") btns.push("…"); continue; } btns.push(i); }
      pg.innerHTML = btns.map(function (b) { return b === "…" ? '<span class="px-2 text-ink-400">…</span>' : '<button type="button" data-page="' + b + '" class="h-9 min-w-9 rounded-lg px-3 text-sm font-bold ' + (b === state.page ? "bg-brand-700 text-white" : "bg-white text-ink-700 ring-1 ring-ink-200 hover:ring-brand-300") + '">' + b + "</button>"; }).join("");
    }
    try {
      var u = new URL(location.href); u.search = "";
      if (state.ingredient) u.searchParams.set("ingredient", state.ingredient); if (state.q) u.searchParams.set("q", state.q);
      history.replaceState(null, "", u.toString());
    } catch (e) {}
    D.icons(document.getElementById("product-list"));
  }

  function renderMeta() {
    var m = products._meta || {}, cl = products.changelog || {};
    var box = document.getElementById("data-status");
    var sample = m.source === "sample";
    box.innerHTML = '<div class="flex flex-col gap-3 rounded-2xl border ' + (sample ? "border-amber-200 bg-amber-50" : "border-brand-100 bg-brand-50") + ' p-4 sm:flex-row sm:items-center sm:justify-between">' +
      '<div class="flex items-start gap-3"><i data-lucide="' + (sample ? "triangle-alert" : "database") + '" class="mt-0.5 h-5 w-5 shrink-0 ' + (sample ? "text-amber-600" : "text-brand-600") + '"></i><div><p class="text-sm font-bold ' + (sample ? "text-amber-900" : "text-brand-900") + '">' + (sample ? "샘플 데이터 표시 중" : "식약처 건강기능식품 품목제조신고 데이터") + '</p><p class="mt-0.5 text-xs ' + (sample ? "text-amber-800" : "text-brand-800") + '">' + (sample ? esc(m.note || "") : "최종 수집: " + esc(D.fmtDate(m.updatedAt)) + " · 총 " + Number(m.total || products.items.length).toLocaleString() + "건") + '</p></div></div>' +
      (!sample && cl.updatedAt ? '<div class="flex shrink-0 gap-2 text-xs font-bold"><span class="rounded-full bg-white px-2.5 py-1 text-brand-700 ring-1 ring-brand-200">신규 ' + (cl.added || 0) + '</span><span class="rounded-full bg-white px-2.5 py-1 text-ink-600 ring-1 ring-ink-200">변경 ' + (cl.changed || 0) + '</span><span class="rounded-full bg-white px-2.5 py-1 text-rose-600 ring-1 ring-rose-200">삭제 ' + (cl.removed || 0) + '</span></div>' : "") + "</div>";
    var clEl = document.getElementById("changelog");
    if (cl.items && cl.items.length) {
      clEl.classList.remove("hidden");
      clEl.innerHTML = '<h2 class="text-sm font-bold text-ink-900">최근 변경 이력 <span class="font-medium text-ink-400">' + esc(D.fmtDate(cl.updatedAt)) + '</span></h2><ul class="mt-2 max-h-48 space-y-1 overflow-y-auto text-xs text-ink-600">' + cl.items.slice(0, 50).map(function (c) { var tag = { added: ["신규", "text-brand-700"], removed: ["삭제", "text-rose-600"], changed: ["변경", "text-amber-700"] }[c.type] || ["", ""]; return '<li><span class="font-bold ' + tag[1] + '">' + tag[0] + '</span> ' + esc(c.name) + ' <span class="text-ink-400">' + esc(c.company || "") + (c.field ? " · " + esc(c.field) : "") + '</span></li>'; }).join("") + "</ul>";
    }
    D.icons(box);
  }

  document.addEventListener("DOMContentLoaded", function () {
    D.productNames().then(function (n) {
      names = n && n.p ? n : null; if (!names) return;
      var apply = function () { nameMatch = D.productMatcher(names); if (state.q && products && core) render(); };
      apply(); if (names.more) names.more.then(apply);   // 과거 제품 색인이 합쳐지면 한 번 더
    }).catch(function () {});
    Promise.all([D.core(), D.products(), window.Affiliate.ready()]).then(function (r) {
      core = r[0]; products = r[1];
      var sel = document.getElementById("filter-ingredient");
      sel.innerHTML = '<option value="">전체 성분</option>' + core.items.slice().sort(function (a, b) { return a.name.localeCompare(b.name, "ko"); }).map(function (i) { return '<option value="' + esc(i.id) + '">' + esc(i.name) + "</option>"; }).join("");
      sel.value = state.ingredient; sel.addEventListener("change", function () { state.ingredient = sel.value; state.page = 1; render(); });
      var shapes = {}; products.items.forEach(function (p) { if (p.shape) shapes[p.shape] = 1; });
      var ssel = document.getElementById("filter-shape");
      ssel.innerHTML = '<option value="">모든 형태</option>' + Object.keys(shapes).sort().map(function (s) { return '<option value="' + esc(s) + '">' + esc(s) + "</option>"; }).join("");
      ssel.addEventListener("change", function () { state.shape = ssel.value; state.page = 1; render(); });
      var input = document.getElementById("product-search"); input.value = state.q;
      input.addEventListener("input", function () { state.q = input.value; state.page = 1; render(); });
      document.getElementById("product-list").addEventListener("click", function (e) { var sm = e.target.closest("summary"); if (sm) lazyDetail(sm.parentElement); });
      document.getElementById("pagination").addEventListener("click", function (e) { var b = e.target.closest("[data-page]"); if (!b) return; state.page = Number(b.getAttribute("data-page")); render(); document.getElementById("product-list").scrollIntoView({ behavior: "smooth", block: "start" }); });
      var quick = document.getElementById("quick-ingredients");
      if (quick) quick.innerHTML = ["vitamin-d", "omega-3", "probiotics", "lutein", "magnesium", "milk-thistle", "red-ginseng", "calcium"].map(function (id) { var it = core.byId[id]; return it ? '<button type="button" class="chip" data-quick="' + id + '">' + esc(it.name) + "</button>" : ""; }).join("");
      if (quick) quick.addEventListener("click", function (e) { var b = e.target.closest("[data-quick]"); if (!b) return; state.ingredient = b.getAttribute("data-quick"); sel.value = state.ingredient; state.page = 1; render(); });
      renderMeta(); render(); D.icons();
    }).catch(function (e) { console.error(e); document.getElementById("product-list").innerHTML = '<p class="text-sm text-rose-600">제품 데이터를 불러오지 못했습니다.</p>'; });
  });
})();
