/* 뉴스·자료 페이지 */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;
  var state = { cat: D.qs("cat") || "all", q: "" };
  var news;
  var CATS = { all: "전체", news: "뉴스", mfds: "식약처·공공", research: "연구·논문" };

  function item(n) {
    var cat = CATS[n.category] || "뉴스";
    var catCls = { mfds: "bg-sky-50 text-sky-700", research: "bg-violet-50 text-violet-700", news: "bg-brand-50 text-brand-700" }[n.category] || "bg-brand-50 text-brand-700";
    return '<a href="' + esc(n.link) + '" target="_blank" rel="noopener" class="card-hover flex flex-col gap-2 rounded-2xl border border-ink-100 bg-white p-5 shadow-card fade-up sm:flex-row sm:items-start sm:gap-5">' +
      '<div class="flex shrink-0 items-center gap-2 text-xs sm:w-40 sm:flex-col sm:items-start"><span class="rounded-full px-2 py-0.5 font-bold ' + catCls + '">' + esc(cat) + '</span><span class="text-ink-400">' + esc(D.fmtDate(n.publishedAt)) + '</span></div>' +
      '<div class="min-w-0 flex-1"><h2 class="font-bold leading-snug text-ink-900">' + esc(n.title) + '</h2>' + (n.summary ? '<p class="mt-1.5 line-clamp-2 text-sm text-ink-500">' + esc(n.summary) + '</p>' : "") + '<p class="mt-2 flex items-center gap-1 text-xs font-semibold text-ink-400"><i data-lucide="external-link" class="h-3.5 w-3.5"></i>' + esc(n.source || "출처 미상") + '</p></div></a>';
  }

  function render() {
    var items = (news.items || []).slice().sort(function (a, b) { return new Date(b.publishedAt) - new Date(a.publishedAt); });
    if (state.cat !== "all") items = items.filter(function (n) { return n.category === state.cat; });
    var q = state.q.trim().toLowerCase();
    if (q) items = items.filter(function (n) { return (n.title + " " + (n.summary || "") + " " + (n.source || "")).toLowerCase().indexOf(q) >= 0; });
    document.getElementById("news-list").innerHTML = items.map(item).join("");
    document.getElementById("news-count").textContent = items.length + "건";
    document.getElementById("news-empty").classList.toggle("hidden", items.length > 0);
    document.querySelectorAll("[data-cat]").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-cat") === state.cat); });
    D.icons(document.getElementById("news-list"));
  }

  document.addEventListener("DOMContentLoaded", function () {
    D.news().then(function (n) {
      news = n;
      var m = n._meta || {};
      var status = document.getElementById("news-status");
      status.innerHTML = m.source === "sample"
        ? '<div class="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4"><i data-lucide="triangle-alert" class="mt-0.5 h-5 w-5 shrink-0 text-amber-600"></i><div><p class="text-sm font-bold text-amber-900">샘플 데이터 표시 중</p><p class="mt-0.5 text-xs text-amber-800">' + esc(m.note || "") + '</p></div></div>'
        : '<div class="flex items-center gap-2 text-xs text-ink-500"><i data-lucide="refresh-cw" class="h-3.5 w-3.5"></i>최근 수집: ' + esc(D.fmtDate(m.updatedAt)) + ' · 검색어: ' + esc((m.queries || []).join(", ")) + '</div>';
      var tabs = document.getElementById("news-tabs");
      tabs.innerHTML = Object.keys(CATS).map(function (k) { return '<button type="button" class="chip" data-cat="' + k + '">' + esc(CATS[k]) + "</button>"; }).join("");
      tabs.addEventListener("click", function (e) { var b = e.target.closest("[data-cat]"); if (!b) return; state.cat = b.getAttribute("data-cat"); render(); });
      var input = document.getElementById("news-search"); input.addEventListener("input", function () { state.q = input.value; render(); });
      render(); D.icons();
    }).catch(function () { document.getElementById("news-list").innerHTML = '<p class="text-sm text-rose-600">뉴스 데이터를 불러오지 못했습니다.</p>'; });
  });
})();
