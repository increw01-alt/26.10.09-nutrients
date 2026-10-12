/* 홈 페이지 — 실사형 메인: 성분·가이드 검색, 빠른 궁합 체크, 가이드 탭, 최신 뉴스 */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;

  /* 고민·대상·복용법 가이드 (slug 는 data/guides.json 과 일치해야 함) */
  var PALETTE = [["#fbf1db", "#b48a3d"], ["#eaf1e3", "#789664"], ["#f8e9e0", "#bc9479"], ["#ececf7", "#9393b3"], ["#e9f1f5", "#7c9dad"], ["#f2ede2", "#a79876"]];
  var GUIDE_GROUPS = {
    concerns: { label: "고민별 가이드", items: [
      { slug: "fatigue", title: "피로회복", icon: "zap" }, { slug: "eye-health", title: "눈 건강", icon: "eye" }, { slug: "gut-health", title: "장 건강", icon: "microscope" },
      { slug: "sleep", title: "수면", icon: "moon" }, { slug: "immunity", title: "면역력", icon: "shield-check" }, { slug: "joint-health", title: "관절", icon: "bone" } ] },
    people: { label: "대상별 가이드", items: [
      { slug: "20s", title: "20대", icon: "sun" }, { slug: "30s-men", title: "30대 남자", icon: "dumbbell" }, { slug: "40s-women", title: "40대 여성", icon: "heart" },
      { slug: "50s-plus", title: "50대 이상", icon: "users" }, { slug: "pregnancy", title: "임산부·임신 준비", icon: "baby" }, { slug: "office-workers", title: "직장인", icon: "briefcase" } ] },
    safety: { label: "복용법·안전 가이드", items: [
      { slug: "when-to-take", title: "먹는 시간", icon: "clock" }, { slug: "how-to-combine", title: "조합 원칙", icon: "list-checks" }, { slug: "do-not-take-together", title: "같이 먹으면 안되는 영양제", icon: "octagon-alert" },
      { slug: "empty-stomach", title: "공복 영양제", icon: "sunrise" }, { slug: "daily-limit", title: "권장량·과다복용", icon: "flask-conical" }, { slug: "with-medication", title: "약과 영양제", icon: "stethoscope" } ] }
  };

  function categoryCard(g, i) {
    var pal = PALETTE[i % PALETTE.length];
    return '<a class="category-card" href="' + D.guideUrl(g.slug) + '" aria-label="' + esc(g.title) + ' 가이드 읽기"><span class="category-icon" style="--cat-bg:' + pal[0] + ';--cat-color:' + pal[1] + '"><i data-lucide="' + esc(g.icon) + '" class="icon"></i></span><h3>' + esc(g.title) + '</h3><span class="category-subtitle">가이드 살펴보기</span></a>';
  }

  function initGuideTabs() {
    var tabs = Array.prototype.slice.call(document.querySelectorAll('.guide-tabs [role="tab"]'));
    var grid = document.getElementById("category-grid"), status = document.getElementById("guide-status");
    if (!tabs.length || !grid) return;
    function setGroup(name, focus) {
      var g = GUIDE_GROUPS[name]; if (!g) return;
      tabs.forEach(function (t) {
        var on = t.getAttribute("data-group") === name;
        t.setAttribute("aria-selected", on ? "true" : "false"); t.tabIndex = on ? 0 : -1;
        if (on && focus) t.focus();
      });
      grid.innerHTML = g.items.map(categoryCard).join("");
      grid.setAttribute("aria-labelledby", "tab-" + name);
      if (status) status.textContent = g.label + " 항목을 표시했습니다.";
      D.icons(grid);
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { setGroup(t.getAttribute("data-group")); });
      t.addEventListener("keydown", function (e) {
        var n = i;
        if (e.key === "ArrowRight") n = (i + 1) % tabs.length;
        else if (e.key === "ArrowLeft") n = (i + tabs.length - 1) % tabs.length;
        else if (e.key === "Home") n = 0;
        else if (e.key === "End") n = tabs.length - 1;
        else return;
        e.preventDefault(); setGroup(tabs[n].getAttribute("data-group"), true);
      });
    });
  }

  /* 성분·가이드 검색 (가이드 목록은 처음 입력할 때 한 번만 불러옴) */
  function norm(s) { return String(s || "").normalize("NFKC").toLowerCase().replace(/[\s·\-]+/g, ""); }
  function initSearch(core) {
    var input = document.getElementById("ingredient-search"), form = document.getElementById("search-form"), box = document.getElementById("search-results");
    var list = document.getElementById("search-list"), status = document.getElementById("search-status"), area = document.getElementById("search-area");
    if (!input || !form || !box || !list) return;
    var POPULAR = ["vitamin-d", "omega-3", "magnesium", "probiotics"];
    var guides = null, guidesLoading = null, matches = [], active = -1;
    function loadGuides() {
      if (guides || guidesLoading) return guidesLoading;
      guidesLoading = D.guides().then(function (g) { guides = (g && g.items) || []; }).catch(function () { guides = []; });
      return guidesLoading;
    }
    function entries(q) {
      var nq = norm(q);
      if (!nq) return POPULAR.map(function (id) { return core.byId[id]; }).filter(Boolean).map(function (it) { return { title: it.name, type: "성분", icon: "pill", href: D.ingredientUrl(it.id) }; });
      var ings = D.search(core.items, q, 5).map(function (it) { return { title: it.name, type: "성분", icon: "pill", href: D.ingredientUrl(it.id) }; });
      var gs = (guides || []).filter(function (g) { return norm([g.title, g.h1, (g.keywords || []).join(" ")].join(" ")).indexOf(nq) >= 0; }).slice(0, 3)
        .map(function (g) { return { title: String(g.h1 || g.title || "").split(" — ")[0], type: "가이드", icon: "book-open", href: D.guideUrl(g.slug) }; });
      return ings.concat(gs).slice(0, 8);
    }
    function close() { box.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); active = -1; }
    function setActive(i) {
      active = i;
      var opts = list.querySelectorAll('[role="option"]');
      Array.prototype.forEach.call(opts, function (o, k) { o.setAttribute("aria-selected", k === i ? "true" : "false"); });
      if (opts[i]) input.setAttribute("aria-activedescendant", opts[i].id); else input.removeAttribute("aria-activedescendant");
    }
    function render() {
      matches = entries(input.value.trim()); active = -1; input.removeAttribute("aria-activedescendant");
      list.innerHTML = matches.length
        ? matches.map(function (m, i) { return '<li class="search-option" id="search-option-' + i + '" role="option" aria-selected="false" data-href="' + esc(m.href) + '"><i data-lucide="' + m.icon + '" class="icon"></i><span>' + esc(m.title) + '</span><span class="option-type">' + m.type + '</span></li>'; }).join("")
        : '<li class="search-empty" role="presentation">검색 결과가 없어요. 전체 성분 사전에서 확인해 주세요.</li>';
      D.icons(list);
      box.hidden = false; input.setAttribute("aria-expanded", "true");
      if (status) status.textContent = matches.length ? "검색 결과 " + matches.length + "개가 있습니다. 화살표 키로 선택하세요." : "검색 결과가 없습니다.";
    }
    function renderWithGuides() { var p = loadGuides(); render(); if (p) p.then(function () { if (!box.hidden) render(); }); }
    list.addEventListener("pointerdown", function (e) { e.preventDefault(); });
    list.addEventListener("click", function (e) { var li = e.target.closest("[data-href]"); if (li) location.href = li.getAttribute("data-href"); });
    input.addEventListener("input", renderWithGuides);
    input.addEventListener("focus", renderWithGuides);
    input.addEventListener("keydown", function (e) {
      if (e.isComposing || e.keyCode === 229) return;
      if (e.key === "Escape") { e.preventDefault(); close(); return; }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (box.hidden) render();
        if (!matches.length) return;
        setActive((active + (e.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length);
      }
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = input.value.trim();
      var pick = active >= 0 ? matches[active] : (q ? matches[0] : null);
      if (pick) { location.href = pick.href; return; }
      if (q) { location.href = D.url("ingredients.html?q=" + encodeURIComponent(q)); return; }
      render(); input.focus();
    });
    document.addEventListener("click", function (e) { if (area && !area.contains(e.target)) close(); });
    Array.prototype.forEach.call(document.querySelectorAll("[data-focus-search]"), function (a) {
      a.addEventListener("click", function (e) { e.preventDefault(); input.scrollIntoView({ block: "center", behavior: "smooth" }); input.focus({ preventScroll: true }); });
    });
  }

  /* 빠른 궁합 체크 — 두 성분을 고르면 즉시 등급·제목을 보여주고, 자세한 결과는 궁합 페이지로 */
  function initChecker(core) {
    var first = document.getElementById("first-ingredient"), second = document.getElementById("second-ingredient");
    var form = document.getElementById("compatibility-form"), fb = document.getElementById("pair-feedback");
    if (!first || !second || !form || !fb) return;
    var cats = core.categories;
    var html = '<option value="">선택하기</option>' + Object.keys(cats).map(function (k) {
      var items = core.items.filter(function (i) { return i.category === k; }).sort(function (a, b) { return a.name.localeCompare(b.name, "ko"); });
      return items.length ? '<optgroup label="' + esc(cats[k].label) + '">' + items.map(function (it) { return '<option value="' + esc(it.id) + '">' + esc(it.name) + '</option>'; }).join("") + "</optgroup>" : "";
    }).join("");
    first.innerHTML = html; second.innerHTML = html;
    function err(msg, el) { fb.textContent = msg; fb.className = "form-feedback error"; el.setAttribute("aria-invalid", "true"); }
    function update() {
      [first, second].forEach(function (s) { s.classList.toggle("has-value", !!s.value); s.removeAttribute("aria-invalid"); });
      fb.className = "form-feedback";
      if (first.value && first.value === second.value) { err("서로 다른 두 가지 성분을 선택해 주세요.", second); return; }
      if (first.value && second.value) {
        var p = D.findPair(core, first.value, second.value), t = p && core.types[p.type];
        fb.textContent = t ? t.short + " · " + p.title : "알려진 특별한 상호작용이 없는 조합이에요. 자세한 내용은 궁합 페이지에서 확인하세요.";
        fb.classList.add("ready"); return;
      }
      fb.textContent = "선택한 성분의 자세한 결과는 궁합 페이지에서 확인합니다.";
    }
    first.addEventListener("change", update); second.addEventListener("change", update);
    form.addEventListener("submit", function (e) {
      e.preventDefault(); update();
      if (!core.byId[first.value]) { err("첫 번째 영양제를 선택해 주세요.", first); first.focus(); return; }
      if (!core.byId[second.value]) { err("두 번째 영양제를 선택해 주세요.", second); second.focus(); return; }
      if (first.value === second.value) { second.focus(); return; }
      location.href = D.compatUrl([first.value, second.value]);
    });
  }

  /* 최신 뉴스 3건 */
  function renderNews(news) {
    var el = document.getElementById("home-news"); if (!el) return;
    var items = (news.items || []).slice().sort(function (a, b) { return new Date(b.publishedAt) - new Date(a.publishedAt); }).slice(0, 3);
    if (!items.length) { el.innerHTML = '<p class="search-empty">표시할 뉴스가 없습니다.</p>'; return; }
    el.innerHTML = items.map(function (n) {
      var cat = { mfds: "식약처", research: "연구", news: "뉴스" }[n.category] || "뉴스";
      return '<a class="news-card" href="' + esc(n.link) + '" target="_blank" rel="noopener"><span class="news-tag">' + esc(cat) + '</span><strong>' + esc(n.title) + '</strong><small>' + esc(n.source || "") + (n.publishedAt ? " · " + esc(D.timeAgo(n.publishedAt)) : "") + '</small></a>';
    }).join("");
  }

  document.addEventListener("DOMContentLoaded", function () {
    initGuideTabs();
    D.core().then(function (core) { initChecker(core); initSearch(core); }).catch(function () {
      var fb = document.getElementById("pair-feedback"); if (fb) { fb.textContent = "데이터를 불러오지 못했습니다. 새로고침해 주세요."; fb.className = "form-feedback error"; }
    });
    D.news().then(renderNews).catch(function () { var el = document.getElementById("home-news"); if (el) el.innerHTML = ""; });
  });
})();
