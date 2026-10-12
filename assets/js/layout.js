/* 공통 레이아웃: 헤더·푸터·검색 오버레이·모바일 메뉴·메타 태그 보정 */
(function () {
  "use strict";
  var D = window.Data, S = window.SITE || {}, esc = D.esc;
  var page = "";
  var NAV = [
    { key: "home", label: "홈", href: "index.html", desktop: false },
    { key: "ingredients", label: "성분 사전", href: "ingredients.html" },
    { key: "compat", label: "궁합 체크", href: "compatibility.html" },
    { key: "guides", label: "가이드", href: "guides.html" },
    { key: "products", label: "제품 찾기", href: "products.html" },
    { key: "news", label: "뉴스", href: "news.html" },
    { key: "about", label: "소개", href: "about.html" }
  ];

  function brandWord() {
    var n = S.name || "";
    var m = /^(.*?)(\.[a-z]{2,4})$/i.exec(n);
    return m ? esc(m[1]) + '<small>' + esc(m[2]) + '</small>' : esc(n);
  }

  function renderHeader() {
    var el = document.getElementById("site-header");
    if (!el) return;
    el.className = "sticky top-0 z-40";   // 고정 헤더: 래퍼(#site-header) 자체를 sticky 로 (자식만 sticky 면 래퍼 높이에 갇혀 고정되지 않음)
    el.innerHTML =
      '<div class="border-b border-[#edf0e9] bg-white/95 backdrop-blur">' +
        '<div class="mx-auto flex h-[68px] max-w-7xl items-center gap-3 px-4 sm:px-6 md:h-[84px] md:gap-6">' +
          '<a href="' + D.url("index.html") + '" class="wordmark" aria-label="' + esc(S.name) + ' 홈"><img class="brand-leaf" src="' + D.url("assets/images/home/leaf.webp") + '" alt="" width="30" height="38" decoding="async"><span>' + brandWord() + '</span></a>' +
          '<span class="brand-description hidden xl:block">' + esc(S.tagline) + '</span>' +
          '<nav class="main-nav ml-auto hidden items-center gap-0.5 md:flex" aria-label="주요 메뉴">' +
            NAV.filter(function (n) { return n.desktop !== false; }).map(function (n) {
              var active = n.key === page;
              return '<a href="' + D.url(n.href) + '" class="' + (active ? "active" : "") + '"' + (active ? ' aria-current="page"' : "") + '>' + esc(n.label) + '</a>';
            }).join("") +
          '</nav>' +
          '<div class="header-actions ml-auto flex items-center gap-1 md:ml-0 md:gap-2">' +
            '<button type="button" id="open-search" class="icon-button" aria-label="성분 검색 열기" title="검색 ( / )"><i data-lucide="search"></i></button>' +
            '<a href="' + D.url("compatibility.html") + '" class="header-cta hidden sm:inline-flex">궁합 체크 <i data-lucide="arrow-right"></i></a>' +
            '<button type="button" id="open-menu" class="icon-button md:hidden" aria-label="메뉴 열기" aria-expanded="false" aria-controls="mobile-menu"><i data-lucide="menu"></i></button>' +
          '</div>' +
        '</div>' +
        '<div id="mobile-menu" class="mobile-menu md:hidden border-t border-ink-100 bg-white"><nav class="mx-auto max-w-7xl px-4 py-2" aria-label="모바일 메뉴">' +
          NAV.map(function (n) {
            var active = n.key === page;
            return '<a href="' + D.url(n.href) + '" class="flex items-center justify-between rounded-lg px-3 py-3 text-[15px] font-semibold ' + (active ? "bg-brand-50 text-brand-700" : "text-ink-700") + '">' + esc(n.label) + '<i data-lucide="chevron-right" class="h-4 w-4 text-ink-300"></i></a>';
          }).join("") +
          '<a href="' + D.url("materials.html") + '" class="flex items-center justify-between rounded-lg px-3 py-3 text-[15px] font-semibold text-ink-700">기능성 원료 인정현황<i data-lucide="chevron-right" class="h-4 w-4 text-ink-300"></i></a>' +
        '</nav></div>' +
      '</div>';
    var btn = document.getElementById("open-menu"), menu = document.getElementById("mobile-menu");
    if (btn && menu) btn.addEventListener("click", function () {
      var open = menu.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    ["open-search", "open-search-m"].forEach(function (id) { var b = document.getElementById(id); if (b) b.addEventListener("click", openSearch); });
  }

  /* 모바일 하단 탭 바 */
  function renderTabbar() {
    var TABS = [
      { key: "home", label: "홈", href: "index.html", icon: "house" },
      { key: "ingredients", label: "성분", href: "ingredients.html", icon: "book-open" },
      { key: "compat", label: "궁합", href: "compatibility.html", icon: "heart-handshake" },
      { key: "guides", label: "가이드", href: "guides.html", icon: "compass" },
      { key: "products", label: "제품", href: "products.html", icon: "shopping-bag" }
    ];
    var nav = document.createElement("nav");
    nav.className = "tabbar no-print"; nav.setAttribute("aria-label", "하단 메뉴");
    nav.innerHTML = TABS.map(function (t) { return '<a href="' + D.url(t.href) + '" class="' + (t.key === page ? "active" : "") + '"' + (t.key === page ? ' aria-current="page"' : "") + '><i data-lucide="' + t.icon + '"></i>' + esc(t.label) + '</a>'; }).join("");
    document.body.appendChild(nav); document.body.classList.add("has-tabbar");
    D.icons(nav);
  }

  function renderFooter() {
    var el = document.getElementById("site-footer");
    if (!el) return;
    var A = window.AFFILIATE || {};
    el.innerHTML =
      '<footer class="mt-20 border-t border-[#e8eee1] bg-[#f8faf5]">' +
        '<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">' +
          '<div class="grid gap-10 md:grid-cols-12">' +
            '<div class="md:col-span-5">' +
              '<a href="' + D.url("index.html") + '" class="wordmark wordmark-sm" aria-label="' + esc(S.name) + ' 홈"><img class="brand-leaf" src="' + D.url("assets/images/home/leaf.webp") + '" alt="" width="24" height="30" loading="lazy" decoding="async"><span>' + brandWord() + '</span></a>' +
              '<p class="mt-4 text-sm leading-relaxed text-ink-500">' + esc(S.description) + '</p>' +
              '<p class="mt-4 text-xs leading-relaxed text-ink-400" id="footer-updated"></p>' +
            '</div>' +
            '<div class="md:col-span-3"><h3 class="text-sm font-bold text-ink-900">바로가기</h3><ul class="mt-3 space-y-2 text-sm text-ink-600">' +
              NAV.slice(1).map(function (n) { return '<li><a class="hover:text-brand-700" href="' + D.url(n.href) + '">' + esc(n.label === "뉴스" ? "뉴스·자료" : n.label === "가이드" ? "영양제 가이드" : n.label) + '</a></li>'; }).join("") +
              '<li><a class="hover:text-brand-700" href="' + D.url("materials.html") + '">기능성 원료 인정현황</a></li>' +
            '</ul></div>' +
            '<div class="md:col-span-4"><h3 class="text-sm font-bold text-ink-900">데이터 출처</h3><ul class="mt-3 space-y-2 text-sm text-ink-600">' +
              '<li><a class="hover:text-brand-700" href="https://www.foodsafetykorea.go.kr" target="_blank" rel="noopener">식품안전나라(식품의약품안전처) 건강기능식품 정보</a></li>' +
              '<li><a class="hover:text-brand-700" href="https://www.data.go.kr" target="_blank" rel="noopener">공공데이터포털</a></li>' +
              '<li>한국인 영양소 섭취기준(2020) · 건강기능식품 기능성 원료 고시</li>' +
            '</ul>' +
            '<p class="mt-4 text-xs text-ink-500">문의: <a class="underline hover:text-brand-700" href="mailto:' + esc(S.contactEmail) + '">' + esc(S.contactEmail) + '</a></p></div>' +
          '</div>' +
          '<div class="mt-10 space-y-3 rounded-2xl bg-white p-5 text-xs leading-relaxed text-ink-500">' +
            '<p><strong class="text-ink-700">의학적 면책:</strong> 이 사이트의 정보는 일반적인 건강 정보 제공을 목적으로 하며 의학적 진단·처방을 대신하지 않습니다. 질환이 있거나 약을 복용 중이라면 영양제 섭취 전 의사·약사와 상담하세요. 건강기능식품은 질병의 예방·치료를 위한 의약품이 아닙니다.</p>' +
            '<p><strong class="text-ink-700">제휴 고지:</strong> ' + esc(A.disclosure || "") + '</p>' +
          '</div>' +
          '<div class="mt-6 flex flex-col items-start justify-between gap-2 text-xs text-ink-400 sm:flex-row sm:items-center"><p>© ' + new Date().getFullYear() + ' ' + esc(S.name) + '. All rights reserved.</p><p>제품·가격 정보는 각 쇼핑몰 기준이며 변동될 수 있습니다.</p></div>' +
        '</div>' +
      '</footer>';
    D.meta().then(function (m) {
      var t = document.getElementById("footer-updated");
      if (t && m && m.builtAt) t.textContent = "데이터 최종 갱신: " + D.fmtDate(m.builtAt) + (m.products && m.products.source === "sample" ? " · 제품/뉴스 샘플 데이터 표시 중" : "");
    }).catch(function () {});
  }

  /* ---------- 검색 오버레이 ---------- */
  var overlay = null, focusIdx = -1;
  function openSearch() {
    if (overlay) return;
    overlay = document.createElement("div");
    overlay.className = "search-overlay";
    overlay.setAttribute("role", "dialog"); overlay.setAttribute("aria-modal", "true"); overlay.setAttribute("aria-label", "성분 검색");
    overlay.innerHTML =
      '<div class="search-panel">' +
        '<div class="relative"><i data-lucide="search" class="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-400"></i>' +
        '<label for="global-search-input" class="sr-only">성분 검색</label><input id="global-search-input" type="search" placeholder="성분명·별칭·효능으로 검색 (예: 비타민D, 눈 건강)" autocomplete="off" />' +
        '<button type="button" id="close-search" class="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg px-2 py-1 text-xs font-semibold text-ink-400 hover:bg-ink-50" aria-label="닫기">ESC</button></div>' +
        '<div id="global-search-results" class="max-h-[60vh] overflow-y-auto py-2"><p class="px-5 py-6 text-sm text-ink-400">검색어를 입력하면 성분 사전에서 바로 찾아드립니다.</p></div>' +
        '<div class="flex items-center justify-between border-t border-ink-100 px-5 py-2.5 text-[11px] text-ink-400"><span>↑↓ 이동 · Enter 열기</span><a class="font-semibold text-brand-700" href="' + D.url("ingredients.html") + '">전체 성분 보기 →</a></div>' +
      '</div>';
    document.body.appendChild(overlay);
    document.body.style.overflow = "hidden";
    D.icons(overlay);
    var input = overlay.querySelector("#global-search-input"), results = overlay.querySelector("#global-search-results");
    overlay.addEventListener("click", function (e) { if (e.target === overlay) closeSearch(); });
    overlay.querySelector("#close-search").addEventListener("click", closeSearch);
    input.focus();
    D.ingredients().then(function (d) {
      input.addEventListener("input", function () {
        focusIdx = -1;
        var q = input.value;
        var hits = D.search(d.items, q, 10);
        if (!q.trim()) { results.innerHTML = '<p class="px-5 py-6 text-sm text-ink-400">검색어를 입력하면 성분 사전에서 바로 찾아드립니다.</p>'; return; }
        if (!hits.length) { results.innerHTML = '<p class="px-5 py-6 text-sm text-ink-400">"' + esc(q) + '"에 해당하는 성분이 아직 없습니다. <a class="font-semibold text-brand-700" href="' + D.url("ingredients.html") + '">전체 목록</a>에서 찾아보세요.</p>'; return; }
        results.innerHTML = hits.map(function (it) {
          var cat = d._meta.categories[it.category] || {};
          return '<a class="search-result" href="' + D.ingredientUrl(it.id) + '">' +
            '<span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg ring-1 ' + D.catClass(cat.color) + '"><i data-lucide="' + esc(it.icon || cat.icon || "pill") + '" class="h-4 w-4"></i></span>' +
            '<span class="min-w-0"><span class="block truncate text-sm font-bold text-ink-900">' + esc(it.name) + ' <span class="font-medium text-ink-400">' + esc(it.en) + '</span></span><span class="block truncate text-xs text-ink-500">' + esc((it.tags || []).join(" · ")) + '</span></span></a>';
        }).join("");
        D.icons(results);
      });
    }).catch(function () { results.innerHTML = '<p class="px-5 py-6 text-sm text-rose-600">데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>'; });
    input.addEventListener("keydown", function (e) {
      var links = results.querySelectorAll(".search-result");
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault(); if (!links.length) return;
        focusIdx = (focusIdx + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
        links.forEach(function (l, i) { l.classList.toggle("focus", i === focusIdx); });
        links[focusIdx].scrollIntoView({ block: "nearest" });
      } else if (e.key === "Enter" && links.length) {
        location.href = links[focusIdx >= 0 ? focusIdx : 0].href;
      }
    });
  }
  function closeSearch() {
    if (!overlay) return;
    overlay.remove(); overlay = null; document.body.style.overflow = "";
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeSearch();
    if (e.key === "/" && !overlay && !/input|textarea|select/i.test((e.target && e.target.tagName) || "")) { e.preventDefault(); openSearch(); }
  });

  /* ---------- 메타 태그 보정 (config의 URL 기준 canonical·OG) ---------- */
  function fixMeta() {
    try {
      var base = (S.url || "").replace(/\/+$/, "");
      if (!base || /example\.com/.test(base)) return; // 도메인 미설정 시 건너뜀
      var path = document.body.getAttribute("data-path") || location.pathname.split("/").pop() || "index.html";
      var canonical = document.querySelector('link[rel="canonical"]');
      if (canonical) canonical.href = base + "/" + path.replace(/^\/+/, "");
      var og = document.querySelector('meta[property="og:url"]'); if (og) og.content = canonical ? canonical.href : base;
      var ogi = document.querySelector('meta[property="og:image"]'); if (ogi && !/^https?:/.test(ogi.content)) ogi.content = base + "/" + (S.ogImage || "").replace(/^\/+/, "");
      // 소유 확인 메타태그는 검색엔진이 원본 HTML 에서 읽어야 하므로 JS 로 넣지 않고 build_site.py 가 index.html 에 정적으로 삽입한다.
    } catch (e) { /* 무시 */ }
  }

  /* 맨 위로 버튼 */
  function topButton() {
    var b = document.createElement("button");
    b.type = "button"; b.className = "no-print fixed bottom-20 right-4 z-30 hidden h-11 w-11 items-center justify-center rounded-full bg-ink-900/85 text-white shadow-lg transition hover:bg-brand-700 md:bottom-5 md:right-5";
    b.setAttribute("aria-label", "맨 위로"); b.innerHTML = '<i data-lucide="arrow-up" class="h-5 w-5"></i>';
    b.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    document.body.appendChild(b);
    window.addEventListener("scroll", function () { b.classList.toggle("hidden", window.scrollY < 500); b.classList.toggle("flex", window.scrollY >= 500); }, { passive: true });
    D.icons(b);
  }

  /* 임시 주소(*.pages.dev)로 접속하면 정식 도메인으로 보냅니다 (중복 색인 방지) */
  try {
    var canon = (S.url || "").replace(/\/+$/, "");
    if (canon && /\.pages\.dev$/i.test(location.hostname)) location.replace(canon + location.pathname + location.search + location.hash);
  } catch (e) { /* 무시 */ }

  document.addEventListener("DOMContentLoaded", function () {
    page = document.body.getAttribute("data-page") || "";
    renderHeader(); renderFooter(); renderTabbar(); fixMeta(); topButton(); D.icons();
  });
  window.Layout = { openSearch: openSearch, closeSearch: closeSearch };
})();
