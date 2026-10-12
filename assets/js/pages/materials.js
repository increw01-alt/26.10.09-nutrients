/* 식약처 기능성 원료 인정현황 페이지 */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var state = { q: D.qs("q") || "", ingredient: D.qs("ingredient") || "", type: "" };
  var core, data;
  var PAGE = 30, page = 1;

  function card(g) {
    var ings = (g.ingredients || []).map(function (id) { return core.byId[id]; }).filter(Boolean);
    return '<article class="rounded-2xl border border-ink-100 bg-white p-5 shadow-card fade-up">' +
      '<div class="flex flex-wrap items-center gap-2"><span class="rounded-full px-2 py-0.5 text-[11px] font-bold ' + (g.type === "고시형" ? "bg-sky-50 text-sky-700" : "bg-violet-50 text-violet-700") + '">' + esc(g.type) + '</span>' + (g.recognizedAt ? '<span class="text-xs text-ink-400">' + esc(D.fmtDate(g.recognizedAt)) + ' 인정</span>' : "") + '</div>' +
      '<h2 class="mt-2 font-extrabold leading-snug text-ink-900">' + esc(g.name) + '</h2>' +
      (g.function ? '<p class="mt-2 text-sm leading-relaxed text-ink-700">' + esc(g.function) + '</p>' : "") +
      '<dl class="mt-3 space-y-1 text-xs text-ink-600">' +
      (g.intake ? '<div><dt class="inline font-bold text-ink-500">1일 섭취량</dt> <dd class="inline">' + esc(g.intake) + '</dd></div>' : "") +
      (g.recognitionNo ? '<div><dt class="inline font-bold text-ink-500">인정번호</dt> <dd class="inline">' + esc(g.recognitionNo) + '</dd></div>' : "") +
      (g.companyCount ? '<div><dt class="inline font-bold text-ink-500">인정 업체</dt> <dd class="inline">' + esc((g.companies || []).slice(0, 3).join(", ")) + (g.companyCount > 3 ? ' 외 ' + (g.companyCount - 3) + '곳' : "") + '</dd></div>' : "") +
      '</dl>' +
      (g.caution ? '<details class="mt-2 text-xs"><summary class="cursor-pointer font-semibold text-amber-700">섭취 시 주의사항</summary><p class="mt-1 whitespace-pre-line text-ink-600">' + esc(g.caution) + '</p></details>' : "") +
      (ings.length ? '<div class="mt-3 flex flex-wrap gap-1.5">' + ings.map(function (i) { return '<a href="' + D.ingredientUrl(i.id) + '" class="rounded-md bg-brand-50 px-2 py-0.5 text-[11px] font-bold text-brand-700 hover:bg-brand-100">' + esc(i.name) + ' 사전 →</a>'; }).join("") + '</div>' : "") +
      '</article>';
  }

  function filtered() {
    var items = (data.items || []).slice();
    if (state.ingredient) items = items.filter(function (g) { return (g.ingredients || []).indexOf(state.ingredient) >= 0; });
    if (state.type) items = items.filter(function (g) { return g.type === state.type; });
    var q = state.q.trim().toLowerCase();
    if (q) items = items.filter(function (g) { return [g.name, g.function, g.caution, (g.companies || []).join(" ")].join(" ").toLowerCase().indexOf(q) >= 0; });
    return items;
  }

  function render() {
    var items = filtered();
    var pages = Math.max(1, Math.ceil(items.length / PAGE)); if (page > pages) page = pages;
    document.getElementById("material-list").innerHTML = items.slice((page - 1) * PAGE, page * PAGE).map(card).join("");
    document.getElementById("material-count").textContent = items.length.toLocaleString() + "건";
    document.getElementById("material-empty").classList.toggle("hidden", items.length > 0);
    var pg = document.getElementById("material-pagination"); pg.innerHTML = "";
    if (pages > 1) { var btns = []; for (var i = 1; i <= pages; i++) { if (pages > 9 && Math.abs(i - page) > 3 && i !== 1 && i !== pages) { if (btns[btns.length - 1] !== "…") btns.push("…"); continue; } btns.push(i); }
      pg.innerHTML = btns.map(function (b) { return b === "…" ? '<span class="px-2 text-ink-400">…</span>' : '<button type="button" data-page="' + b + '" class="h-9 min-w-9 rounded-lg px-3 text-sm font-bold ' + (b === page ? "bg-brand-700 text-white" : "bg-white text-ink-700 ring-1 ring-ink-200 hover:ring-brand-300") + '">' + b + "</button>"; }).join(""); }
    document.querySelectorAll("[data-type]").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-type") === state.type); });
    try { var u = new URL(location.href); u.search = ""; if (state.ingredient) u.searchParams.set("ingredient", state.ingredient); if (state.q) u.searchParams.set("q", state.q); history.replaceState(null, "", u.toString()); } catch (e) {}
    D.icons(document.getElementById("material-list"));
  }

  document.addEventListener("DOMContentLoaded", function () {
    Promise.all([D.core(), D.materials()]).then(function (r) {
      core = r[0]; data = r[1];
      var m = data._meta || {};
      var status = document.getElementById("material-status");
      if (m.source !== "mfds") {
        status.innerHTML = '<div class="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4"><i data-lucide="triangle-alert" class="mt-0.5 h-5 w-5 shrink-0 text-amber-600"></i><div><p class="text-sm font-bold text-amber-900">아직 수집 전입니다</p><p class="mt-0.5 text-xs text-amber-800">' + esc(m.note || "다음 자동 갱신 때 식약처 기능성 원료 데이터가 채워집니다.") + '</p></div></div>';
      } else {
        var svc = Object.keys(m.services || {}).map(function (k) { return esc(m.services[k].label) + " " + Number(m.services[k].rows || 0).toLocaleString() + "행"; }).join(" · ");
        status.innerHTML = '<div class="flex items-center gap-2 text-xs text-ink-500"><i data-lucide="database" class="h-3.5 w-3.5"></i>최종 수집 ' + esc(D.fmtDate(m.updatedAt)) + ' · ' + svc + ' · 원료 ' + Number(m.total || 0).toLocaleString() + '건 (성분 사전 연결 ' + Number(m.matched || 0).toLocaleString() + '건)</div>';
      }
      var sel = document.getElementById("material-ingredient");
      sel.innerHTML = '<option value="">전체 성분</option>' + core.items.slice().sort(function (a, b) { return a.name.localeCompare(b.name, "ko"); }).map(function (i) { return '<option value="' + esc(i.id) + '">' + esc(i.name) + "</option>"; }).join("");
      sel.value = state.ingredient; sel.addEventListener("change", function () { state.ingredient = sel.value; page = 1; render(); });
      var input = document.getElementById("material-search"); input.value = state.q; input.addEventListener("input", function () { state.q = input.value; page = 1; render(); });
      document.getElementById("material-types").addEventListener("click", function (e) { var b = e.target.closest("[data-type]"); if (!b) return; state.type = b.getAttribute("data-type"); page = 1; render(); });
      document.getElementById("material-pagination").addEventListener("click", function (e) { var b = e.target.closest("[data-page]"); if (!b) return; page = Number(b.getAttribute("data-page")); render(); document.getElementById("material-list").scrollIntoView({ behavior: "smooth", block: "start" }); });
      render(); D.icons();
    }).catch(function () { document.getElementById("material-list").innerHTML = '<p class="text-sm text-rose-600">데이터를 불러오지 못했습니다.</p>'; });
  });
})();
