/* 공통 레이아웃: 헤더·푸터·검색 오버레이·모바일 메뉴·메타 태그 보정 */
(function () {
  "use strict";
  var D = window.Data, S = window.SITE || {}, esc = D.esc;
  var page = "";
  var NAV = [
    { key: "home", label: "홈", href: "index.html", desktop: false },
    { key: "ingredients", label: "성분 사전", href: "ingredients.html" },
    { key: "compat", label: "영양제 궁합", href: "compatibility.html" },
    { key: "my", label: "내 영양제", href: "my.html" },
    { key: "guides", label: "영양제 추천", href: "guides.html" },
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
    var inApp = !!(window.AppBridge && window.AppBridge.isNative());
    var TABS = [
      inApp ? { key: "my", label: "내 영양제", href: "my.html", icon: "pill" } : { key: "home", label: "홈", href: "index.html", icon: "house" },   // 앱에서는 첫 탭이 내 영양제
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
              NAV.slice(1).map(function (n) { return '<li><a class="hover:text-brand-700" href="' + D.url(n.href) + '">' + esc(n.label === "뉴스" ? "뉴스·자료" : n.label === "영양제 추천" ? "영양제 추천 가이드" : n.label) + '</a></li>'; }).join("") +
              '<li><a class="hover:text-brand-700" href="' + D.url("finder.html") + '">나에게 맞는 영양제 찾기</a></li>' +
              '<li><a class="hover:text-brand-700" href="' + D.url("compatibility-chart.html") + '">영양제 궁합표</a></li>' +
              '<li><a class="hover:text-brand-700" href="' + D.url("timing-chart.html") + '">영양제 복용 시간표</a></li>' +
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
            (window.AppBridge && window.AppBridge.hideShopping() ? "" : '<p><strong class="text-ink-700">제휴 고지:</strong> ' + esc(A.disclosure || "") + '</p>') +   // 앱에서 쇼핑을 숨기면 고지도 생략

          '</div>' +
          '<div class="mt-6 flex flex-col items-start justify-between gap-3 text-xs text-ink-400 sm:flex-row sm:items-end">' +
            '<div class="space-y-1"><p>© ' + new Date().getFullYear() + ' ' + esc(S.name) + '. All rights reserved. · <a class="underline hover:text-brand-700" href="' + D.url("terms.html") + '">이용약관 · 데이터 이용 정책</a> · <a class="underline hover:text-brand-700" href="' + D.url("privacy.html") + '">개인정보처리방침</a></p>' +
            '<p>콘텐츠와 데이터베이스는 저작권법으로 보호됩니다. 무단 복제·크롤링·재배포를 금합니다.</p></div>' +
            '<p>제품·가격 정보는 각 쇼핑몰 기준이며 변동될 수 있습니다.</p>' +
          '</div>' +
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
        '<label for="global-search-input" class="sr-only">성분 검색</label><input id="global-search-input" type="search" placeholder="성분명·제품명·의약품명으로 검색 (예: 비타민D, 락토핏, 우루사)" autocomplete="off" />' +
        '<button type="button" id="close-search" class="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg px-2 py-1 text-xs font-semibold text-ink-400 hover:bg-ink-50" aria-label="닫기">ESC</button></div>' +
        '<div id="global-search-results" class="max-h-[60vh] overflow-y-auto py-2"><p class="px-5 py-6 text-sm text-ink-400">검색어를 입력하면 성분 사전과 신고 제품에서 바로 찾아드립니다.</p></div>' +
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
      var byId = {}; d.items.forEach(function (it) { byId[it.id] = it; });
      var names = null, drugs = null, prodMatch = null, drugMatch = null, namesLoading = false;
      function norm(v) { return String(v || "").toLowerCase().replace(/[\s·\-]+/g, ""); }
      function row(href, iconHtml, title, sub) {
        return '<a class="search-result" href="' + href + '">' + iconHtml + '<span class="min-w-0"><span class="block truncate text-sm font-bold text-ink-900">' + title + '</span><span class="block truncate text-xs text-ink-500">' + sub + '</span></span></a>';
      }
      function render() {
        focusIdx = -1;
        var q = input.value, nq = norm(q.trim());
        if (!q.trim()) { results.innerHTML = '<p class="px-5 py-6 text-sm text-ink-400">성분명·제품명·의약품명으로 검색해 보세요. (예: 비타민D, 락토핏, 우루사)</p>'; return; }
        var hits = D.search(d.items, q, 8);
        var ph = prodMatch ? prodMatch(q, 4) : { idx: [], total: 0 }, prods = ph.idx.map(function (i) { return names.p[i]; });   // 자모 비교: 일부만 입력해도 관련 제품
        var dh = drugMatch ? drugMatch(q, 4) : { idx: [], total: 0 }, meds = dh.idx.map(function (i) { return drugs.p[i]; });
        if (!hits.length && !prods.length && !meds.length) { results.innerHTML = '<p class="px-5 py-6 text-sm text-ink-400">"' + esc(q) + '"에 해당하는 성분·제품·의약품이 없습니다. 제품명 일부나 성분명으로 다시 입력해 보세요. <a class="font-semibold text-brand-700" href="' + esc(D.searchUrl(q.trim())) + '">비슷한 이름 찾아보기 →</a></p>'; return; }
        var html = hits.map(function (it) {
          var cat = d._meta.categories[it.category] || {};
          return row(D.ingredientUrl(it.id), '<span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg ring-1 ' + D.catClass(cat.color) + '"><i data-lucide="' + esc(it.icon || cat.icon || "pill") + '" class="h-4 w-4"></i></span>',
            D.markMatch(it.name, q) + ' <span class="font-medium text-ink-400">' + esc(it.en) + '</span>', esc((it.tags || []).slice(0, 3).join(" · ")));
        }).join("");
        if (prods.length) html += '<p class="px-5 pb-1 pt-3 text-[11px] font-bold text-ink-400">식약처 신고 제품</p>' + prods.map(function (pp) {
          var ingNames = pp[2].map(function (i) { var it = byId[names.i[i]]; return it ? it.name : null; }).filter(Boolean);
          var maker = (names.c || [])[pp[3]] || "";
          return row(D.productUrl(pp[0]), '<span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-cream-200 text-brand-700"><i data-lucide="package" class="h-4 w-4"></i></span>', D.markMatch(pp[1], q), (maker ? '<span class="font-semibold text-ink-700">' + esc(maker) + '</span> · ' : "") + (ingNames.length ? "성분: " + esc(ingNames.slice(0, 3).join(" · ")) : "성분 사전과 연결된 성분 없음"));
        }).join("");
        if (meds.length) html += '<p class="px-5 pb-1 pt-3 text-[11px] font-bold text-ink-400">식약처 허가 의약품</p>' + meds.map(function (pp) {
          var dmaker = (drugs.c || [])[pp[5]] || "";
          return row(D.drugUrl(pp[0]), '<span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-amber-50 text-amber-700 ring-1 ring-amber-200"><i data-lucide="pill-bottle" class="h-4 w-4"></i></span>', D.markMatch(pp[1], q), (dmaker ? '<span class="font-semibold text-ink-700">' + esc(dmaker) + '</span> · ' : "") + (pp[3] ? "주성분: " + esc(pp[3]) : "식약처 허가 의약품") + (pp[4] === 2 ? " · 전문의약품" : ""));
        }).join("");
        var total = ph.total + dh.total;
        html += '<a class="search-result justify-center border-t border-ink-100 text-sm font-bold text-brand-700" href="' + esc(D.searchUrl(q.trim())) + '">‘' + esc(q.trim()) + '’ 전체 검색 결과 보기' + (total > prods.length + meds.length ? ' (제품·의약품 ' + total.toLocaleString() + '건)' : '') + ' →</a>';
        results.innerHTML = html; D.icons(results);
      }
      input.addEventListener("input", function () {
        if (!names && !namesLoading && input.value.trim()) {   // 제품·의약품 색인은 처음 입력할 때 한 번만 (의약품은 수집 전이면 404 → 빈 목록)
          namesLoading = true;
          Promise.all([
            D.productNames().then(function (n) { names = n && n.p ? n : { i: [], p: [] }; }).catch(function () { names = { i: [], p: [] }; }).then(function () { prodMatch = D.productMatcher(names); if (names.more) names.more.then(function () { prodMatch = D.productMatcher(names); render(); }); }),
            D.drugNames().then(function (n) { drugs = n && n.p ? n : { i: [], p: [] }; }).catch(function () { drugs = { i: [], p: [] }; }).then(function () { drugMatch = D.drugMatcher(drugs); })
          ]).then(render);
        }
        render();
      });
    }).catch(function () { results.innerHTML = '<p class="px-5 py-6 text-sm text-rose-600">데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>'; });
    input.addEventListener("keydown", function (e) {
      var links = results.querySelectorAll(".search-result");
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault(); if (!links.length) return;
        focusIdx = (focusIdx + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
        links.forEach(function (l, i) { l.classList.toggle("focus", i === focusIdx); });
        links[focusIdx].scrollIntoView({ block: "nearest" });
      } else if (e.key === "Enter") {
        if (focusIdx >= 0 && links[focusIdx]) location.href = links[focusIdx].href;        // 화살표로 고른 항목
        else if (input.value.trim()) location.href = D.searchUrl(input.value.trim());     // 그 외에는 통합 검색 결과 페이지
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
      // Cloudflare Pages 는 /foo.html 을 /foo 로(/index.html 은 /) 리다이렉트해 확장자 없이 서비스하므로 canonical 도 그 형태로 맞춘다 (원본 HTML 의 태그와 동일해야 함)
      var path = (document.body.getAttribute("data-path") || location.pathname.replace(/^\/+/, "") || "index.html").replace(/\.html$/, "").replace(/(^|\/)index$/, "$1");
      var canonical = document.querySelector('link[rel="canonical"]');
      if (canonical) canonical.href = base + "/" + path.replace(/^\/+/, "");
      var og = document.querySelector('meta[property="og:url"]'); if (og) og.content = canonical ? canonical.href : base + "/" + path.replace(/^\/+/, "");   // canonical 이 없는 noindex 페이지도 같은 형태
      var ogi = document.querySelector('meta[property="og:image"]'); if (ogi && !/^https?:/.test(ogi.content)) ogi.content = base + "/" + (S.ogImage || "").replace(/^\/+/, "");
      // 소유 확인 메타태그는 검색엔진이 원본 HTML 에서 읽어야 하므로 JS 로 넣지 않고 build_site.py 가 index.html 에 정적으로 삽입한다.
    } catch (e) { /* 무시 */ }
  }

  /* data-contact-email 요소에 config.js 의 문의 이메일을 채움 (소개·이용약관 페이지가 주소를 하드코딩하지 않게) */
  function fillContact() {
    if (!S.contactEmail) return;
    document.querySelectorAll("[data-contact-email]").forEach(function (el) {
      el.textContent = S.contactEmail;
      if (el.tagName === "A") el.href = "mailto:" + S.contactEmail;
    });
  }

  /* 맨 위로 버튼 */
  function topButton() {
    var b = document.createElement("button");
    b.type = "button"; b.className = "no-print fixed bottom-20 right-4 z-30 hidden h-11 w-11 items-center justify-center rounded-full bg-ink-900/85 text-white shadow-lg transition hover:bg-brand-700 md:bottom-5 md:right-5";
    b.id = "top-btn"; b.setAttribute("aria-label", "맨 위로"); b.innerHTML = '<i data-lucide="arrow-up" class="h-5 w-5"></i>';
    b.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    document.body.appendChild(b);
    window.addEventListener("scroll", function () { b.classList.toggle("hidden", window.scrollY < 500); b.classList.toggle("flex", window.scrollY >= 500); }, { passive: true });
    D.icons(b);
  }

  /* 홈 화면 설치 배너 — 보여 줄지 판단하는 순수 함수. standalone(이미 설치)·궁합 체크 페이지('궁합 결과 보기' 플로팅 버튼과 겹침)·
     이번 세션에 이미 보여 줌·닫은 지 30일 안이면 안 보임. 브라우저 검증용으로 Layout 에 노출 */
  function shouldShowInstallBanner(standalone, dismissedAt, now, page, shownThisSession) {
    if (standalone) return false;
    if (page === "compat") return false;
    if (shownThisSession) return false;
    if (dismissedAt && now - dismissedAt < 30 * 86400000) return false;
    return true;
  }
  /* "Safari 공유 버튼 → 홈 화면에 추가" 안내가 맞는 환경(iOS·iPadOS 의 Safari 자체)만 true. iOS Chrome·네이버·카카오톡 같은 인앱 브라우저에서는 그 안내가 틀려 false (순수 함수) */
  function isIosSafari(ua, platform, touchPoints) {
    var ios = /iPhone|iPad|iPod/.test(ua) || (platform === "MacIntel" && touchPoints > 1);
    if (!ios) return false;
    if (/CriOS|FxiOS|EdgiOS|OPiOS|NAVER|KAKAOTALK|Instagram|FBAN|FBAV|Line\/|Whale|DaumApps|SamsungBrowser|Electron/i.test(ua)) return false;
    return /Safari\//.test(ua);
  }
  /* Chrome 계열은 beforeinstallprompt 를 받았을 때 '설치' 버튼으로, iOS Safari 는 공유 → '홈 화면에 추가' 안내로. 세션당 1회, 닫으면 30일 동안 다시 띄우지 않음 */
  function initInstallBanner() {
    if (window.AppBridge && window.AppBridge.isNative()) return;   // 앱 안에서는 설치 배너가 뜨지 않는다
    var standalone = false, dismissedAt = null, shown = false;
    try { standalone = (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) || navigator.standalone === true; } catch (e) { /* 무시 */ }
    try { dismissedAt = parseInt(localStorage.getItem("pwaBannerDismissedAt"), 10) || null; } catch (e) { /* 저장소 차단 시 무시 */ }
    try { shown = sessionStorage.getItem("pwaBannerShown") === "1"; } catch (e) { /* 무시 */ }
    if (!shouldShowInstallBanner(standalone, dismissedAt, Date.now(), page, shown)) return;
    var isIOS = isIosSafari(navigator.userAgent, navigator.platform, navigator.maxTouchPoints);
    var deferred = null, el = null;
    function dismiss() {
      try { localStorage.setItem("pwaBannerDismissedAt", String(Date.now())); } catch (e) { /* 무시 */ }
      document.body.classList.remove("has-pwa-banner");
      if (el) { el.remove(); el = null; }
    }
    function show(mode) {
      if (el) return;
      try { sessionStorage.setItem("pwaBannerShown", "1"); } catch (e) { /* 무시 */ }
      document.body.classList.add("has-pwa-banner");   // 겹치는 '맨 위로' 버튼은 배너가 떠 있는 동안 숨김(style.css)
      el = document.createElement("div");
      el.className = "pwa-banner no-print"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", "홈 화면에 설치");
      el.innerHTML = '<img src="' + D.url("assets/images/app/icon-192.png") + '" alt="" width="40" height="40">' +
        '<div class="pwa-banner-text"><strong>영양제.kr 을 홈 화면에 설치하면 앱처럼 바로 열려요</strong>' +
        (mode === "ios" ? "<span>Safari 공유 버튼 → '홈 화면에 추가'</span>" : "") + "</div>" +
        '<div class="pwa-banner-actions">' + (mode === "prompt" ? '<button type="button" class="pwa-install">설치</button>' : "") + '<button type="button" class="pwa-dismiss">닫기</button></div>';
      el.querySelector(".pwa-dismiss").addEventListener("click", dismiss);
      var ib = el.querySelector(".pwa-install");
      if (ib) ib.addEventListener("click", function () {
        if (!deferred) return;
        deferred.prompt();
        deferred.userChoice.then(function () { deferred = null; dismiss(); }).catch(dismiss);
      });
      document.body.appendChild(el);
    }
    window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); deferred = e; show("prompt"); });
    window.addEventListener("appinstalled", function () { if (window.gtag) window.gtag("event", "pwa_install"); dismiss(); });
    if (isIOS) show("ios");
  }

  /* "내 영양제에 추가" 버튼([data-my-add="성분id"] 또는 쉼표로 이은 여러 id) — store.js 가 실린 페이지(성분 상세·가이드)에서만 동작. 모두 이미 있으면 처음부터 '있어요' 표시 */
  function markMyAdded(b) { b.innerHTML = '<i data-lucide="check"></i>내 영양제에 있어요 · <a href="' + D.url("my.html") + '">보기</a>'; b.classList.add("is-added"); D.icons(b); }
  function myAddIds(b) { return b.getAttribute("data-my-add").split(",").map(function (s) { return s.trim(); }).filter(Boolean); }
  function initMyAddButtons() {
    var St = window.Store; if (!St) return;
    var have = {};
    St.load().items.forEach(function (i) { have[i.id] = true; });
    document.querySelectorAll("[data-my-add]").forEach(function (b) { if (myAddIds(b).every(function (id) { return have[id]; })) markMyAdded(b); });
    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-my-add]"); if (!b || b.classList.contains("is-added") || e.target.closest("a")) return;
      var r = St.addItems(St.load(), myAddIds(b));
      St.save(r.state); markMyAdded(b);
      if (window.AppBridge && window.AppBridge.isNative()) window.AppBridge.requestSync();   // 앱이면 알림 재예약·복제본 갱신
    });
  }

  /* 임시 주소(*.pages.dev)로 접속하면 정식 도메인으로 보냅니다 (중복 색인 방지) */
  try {
    var canon = (S.url || "").replace(/\/+$/, "");
    if (canon && /\.pages\.dev$/i.test(location.hostname)) location.replace(canon + location.pathname + location.search + location.hash);
  } catch (e) { /* 무시 */ }

  /* Google Analytics 4 — config.js 의 gaMeasurementId 가 있을 때만 로드. 페이지뷰·기본 이벤트의 집계 통계만 쓰고 개인 식별 정보는 보내지 않는다(이용약관 제9조) */
  (function () {
    var id = S.gaMeasurementId;
    if (!id || !/^G-[A-Z0-9]+$/.test(id)) return;
    var h = location.hostname;
    if (h === "localhost" || h === "127.0.0.1" || /\.pages\.dev$/i.test(h)) return;   // 로컬·미리보기 방문은 통계에서 제외
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    if (window.AppBridge && window.AppBridge.isNative()) window.gtag("set", "user_properties", { platform: "app" });   // 앱 방문 구분(GA4 사용자 속성) — 첫 page_view 에도 실리도록 config 앞에
    window.gtag("config", id, { anonymize_ip: true });
    var sc = document.createElement("script"); sc.async = true; sc.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(id);
    document.head.appendChild(sc);
  })();

  /* PWA 서비스워커 등록 — 자산 캐시·오프라인 안내 (sw.js 는 scripts/sw_template.js 에서 빌드가 생성).
     로컬 확인(localhost·127.0.0.1)에서는 빌드 없이 고친 JS·CSS 가 캐시에 가려지지 않도록 기본은 등록하지 않고 기존 등록을 해제한다.
     오프라인 동작을 로컬에서 보려면 주소에 ?sw=1 을 한 번 붙여 켜고(localStorage swDev), ?sw=0 으로 끈다 */
  function shouldRegisterSw(hostname, devFlag) {
    if (hostname === "localhost" || hostname === "127.0.0.1") return devFlag === "1";
    return true;
  }
  if ("serviceWorker" in navigator && /^https?:$/.test(location.protocol)) {
    var swDev = null;
    try {
      var swQ = new URLSearchParams(location.search).get("sw");
      if (swQ === "1" || swQ === "0") localStorage.setItem("swDev", swQ);
      swDev = localStorage.getItem("swDev");
    } catch (e) { /* 저장소 차단 시 무시 */ }
    window.addEventListener("load", function () {
      if (shouldRegisterSw(location.hostname, swDev)) navigator.serviceWorker.register(D.url("sw.js")).catch(function () { /* 미지원·차단 시 무시 */ });
      else navigator.serviceWorker.getRegistrations().then(function (rs) { rs.forEach(function (r) { r.unregister(); }); }).catch(function () { /* 무시 */ });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    page = document.body.getAttribute("data-page") || "";
    renderHeader(); renderFooter(); renderTabbar(); fixMeta(); fillContact(); topButton(); initInstallBanner(); initMyAddButtons(); D.icons();
  });
  window.Layout = { openSearch: openSearch, closeSearch: closeSearch, shouldShowInstallBanner: shouldShowInstallBanner, isIosSafari: isIosSafari, shouldRegisterSw: shouldRegisterSw };
})();
