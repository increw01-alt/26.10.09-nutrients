/* 홈 페이지 — 실사형 메인: 성분·가이드 검색, 빠른 궁합 체크, 가이드 탭, 최신 뉴스 */
(function () {
  "use strict";
  var D = window.Data, esc = D.esc;

  /* 고민·대상·복용법 가이드 (slug 는 data/guides.json 과 일치해야 함) */
  var PALETTE = [["#fbf1db", "#b48a3d"], ["#eaf1e3", "#789664"], ["#f8e9e0", "#bc9479"], ["#ececf7", "#9393b3"], ["#e9f1f5", "#7c9dad"], ["#f2ede2", "#a79876"]];
  var GUIDE_GROUPS = {   // guides.json 의 모든 가이드. 순서·짧은 제목은 scripts/build_site.py 가 아니라 여기서 관리 (데스크톱 6열 그리드)
    concerns: { label: "고민별 가이드", items: [
      { slug: "fatigue", title: "피로회복", icon: "zap" }, { slug: "eye-health", title: "눈 건강", icon: "eye" }, { slug: "gut-health", title: "장 건강", icon: "microscope" },
      { slug: "sleep", title: "수면", icon: "moon" }, { slug: "immunity", title: "면역력", icon: "shield-check" }, { slug: "joint-health", title: "관절", icon: "activity" },
      { slug: "stress", title: "스트레스", icon: "activity" }, { slug: "cholesterol", title: "콜레스테롤", icon: "heart-pulse" }, { slug: "blood-sugar", title: "혈당 관리", icon: "activity" },
      { slug: "skin-health", title: "피부", icon: "sparkles" }, { slug: "hair-health", title: "탈모·모발", icon: "sparkles" }, { slug: "diet", title: "다이어트", icon: "scale" },
      { slug: "eye-twitch", title: "눈 떨림", icon: "eye" }, { slug: "anemia", title: "빈혈·철분", icon: "droplets" }, { slug: "gastritis", title: "위염·역류", icon: "stethoscope" },
      { slug: "liver-health", title: "간 건강", icon: "leaf" }, { slug: "menopause", title: "갱년기", icon: "heart" }, { slug: "blood-circulation", title: "혈행", icon: "heart-pulse" },
      { slug: "acne", title: "여드름", icon: "sparkles" }, { slug: "exercise", title: "운동·헬스", icon: "dumbbell" }, { slug: "mouth-ulcer", title: "입병·구내염", icon: "circle-dot" },
      { slug: "gout", title: "통풍·요산", icon: "triangle-alert" }, { slug: "migraine", title: "편두통", icon: "brain" }, { slug: "dental", title: "치과·구강 건강", icon: "shield-check" },
      { slug: "numbness", title: "손발 저림", icon: "zap" }, { slug: "dryness", title: "안구·구강 건조", icon: "droplets" }, { slug: "prostate", title: "야간 빈뇨·전립선", icon: "circle-dot" },
      { slug: "pms", title: "생리통·PMS", icon: "calendar-days" }, { slug: "tinnitus-dizziness", title: "이명·어지럼", icon: "compass" }, { slug: "pcos", title: "다낭성난소증후군", icon: "activity" } ] },
    people: { label: "대상별 가이드", items: [
      { slug: "20s", title: "20대", icon: "user" }, { slug: "30s-men", title: "30대 남자", icon: "dumbbell" }, { slug: "40s-women", title: "40대 여성", icon: "heart" },
      { slug: "50s-plus", title: "50대 이상", icon: "users" }, { slug: "seniors-70", title: "70대 이상", icon: "users" }, { slug: "sarcopenia", title: "노인 근감소증", icon: "users" },
      { slug: "teens", title: "청소년·성장기", icon: "book-open" }, { slug: "kids", title: "어린이", icon: "baby" }, { slug: "kids-by-age", title: "어린이 연령별", icon: "baby" },
      { slug: "atopy-kids", title: "소아 아토피·알레르기", icon: "shield" }, { slug: "pregnancy", title: "임산부·임신 준비", icon: "baby" }, { slug: "pregnancy-symptoms", title: "입덧·임신 변비", icon: "heart" },
      { slug: "breastfeeding", title: "수유부", icon: "heart" }, { slug: "postpartum", title: "산후 회복", icon: "heart-handshake" }, { slug: "students", title: "수험생", icon: "book-open" },
      { slug: "office-workers", title: "직장인", icon: "briefcase" }, { slug: "shift-workers", title: "교대 근무", icon: "sunset" }, { slug: "parents-gift", title: "부모님 선물", icon: "gift" },
      { slug: "vegan", title: "채식·비건", icon: "leaf" }, { slug: "smokers", title: "흡연자", icon: "flame" }, { slug: "hypertension", title: "혈압약 복용자", icon: "heart-pulse" },
      { slug: "diabetes-meds", title: "당뇨약 복용자", icon: "activity" }, { slug: "nsaid-users", title: "관절염 약 복용자", icon: "bone" }, { slug: "thyroid", title: "갑상선 질환자", icon: "stethoscope" },
      { slug: "kidney", title: "신장 질환자", icon: "droplets" }, { slug: "liver-disease", title: "간 질환자", icon: "stethoscope" }, { slug: "osteoporosis-meds", title: "골다공증 약 복용자", icon: "bone" },
      { slug: "antidepressant-users", title: "우울·불안 약 복용자", icon: "brain" }, { slug: "contraceptive-users", title: "피임약·호르몬 치료", icon: "pill" }, { slug: "hair-loss-meds", title: "탈모약 복용자", icon: "user" },
      { slug: "antibiotics", title: "항생제 복용 중", icon: "pill-bottle" }, { slug: "antihistamine-users", title: "비염약 복용자", icon: "shield" }, { slug: "ppi-users", title: "위산억제제 복용자", icon: "flask-conical" },
      { slug: "gout-meds", title: "통풍약 복용자", icon: "octagon-alert" }, { slug: "dialysis", title: "투석 환자", icon: "droplets" }, { slug: "athletes", title: "운동선수·도핑", icon: "dumbbell" },
      { slug: "weight-loss-drugs", title: "다이어트 약 복용자", icon: "scale" }, { slug: "cancer-treatment", title: "항암 치료 중", icon: "stethoscope" }, { slug: "surgery", title: "수술 전후", icon: "calendar-check" },
      { slug: "bariatric", title: "위 절제·비만수술 후", icon: "utensils" }, { slug: "travel-jetlag", title: "장거리 여행·시차", icon: "sunrise" } ] },
    safety: { label: "복용법·안전 가이드", items: [
      { slug: "when-to-take", title: "먹는 시간", icon: "clock" }, { slug: "how-to-combine", title: "조합 원칙", icon: "list-checks" }, { slug: "do-not-take-together", title: "같이 먹으면 안되는 영양제", icon: "octagon-alert" },
      { slug: "empty-stomach", title: "공복 영양제", icon: "sunrise" }, { slug: "daily-limit", title: "권장량·과다복용", icon: "flask-conical" }, { slug: "with-medication", title: "약과 영양제", icon: "stethoscope" },
      { slug: "storage-expiry", title: "유통기한·보관", icon: "package" }, { slug: "multivitamin-guide", title: "종합비타민 고르기", icon: "pill" }, { slug: "omega3-guide", title: "오메가3 고르기", icon: "fish" },
      { slug: "magnesium-guide", title: "마그네슘 종류", icon: "moon" }, { slug: "vitamin-d-guide", title: "비타민D 고르기", icon: "sun" }, { slug: "zinc-guide", title: "아연 고르기", icon: "shield" },
      { slug: "calcium-guide", title: "칼슘 고르기", icon: "bone" }, { slug: "vitamin-c-guide", title: "비타민C 고르기", icon: "citrus" }, { slug: "collagen-guide", title: "콜라겐 고르기", icon: "sparkles" },
      { slug: "probiotics-guide", title: "유산균 균주", icon: "microscope" } ] }
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
      grid.classList.add("is-collapsed");
      updateMore();
    }
    /* 카드가 많은 탭은 처음에 일부만 보이고(CSS nth-child), 버튼으로 나머지를 펼친다 */
    var more = document.getElementById("category-more"), moreBtn = more && more.querySelector("button"), moreLabel = document.getElementById("category-more-label");
    function updateMore() {
      if (!more) return;
      var collapsed = grid.classList.contains("is-collapsed");
      var cards = Array.prototype.slice.call(grid.querySelectorAll(".category-card"));
      var hidden = collapsed ? cards.filter(function (c) { return c.offsetParent === null; }).length : 0;
      if (collapsed && hidden === 0) { more.hidden = true; return; }
      more.hidden = false;
      moreBtn.setAttribute("aria-expanded", collapsed ? "false" : "true");
      if (moreLabel) moreLabel.textContent = collapsed ? "나머지 " + hidden + "개 가이드 더 보기" : "가이드 접기";
    }
    if (moreBtn) {
      moreBtn.addEventListener("click", function () {
        var open = grid.classList.toggle("is-collapsed");   // true = 접힘
        updateMore();
        if (status) status.textContent = open ? "가이드 목록을 접었습니다." : "가이드 목록을 모두 펼쳤습니다.";
        if (open) grid.scrollIntoView({ block: "nearest" });
      });
      var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(updateMore, 120); });
      updateMore();
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
  var POPULAR = ["vitamin-d", "omega-3", "magnesium", "probiotics"];
  var EXAMPLES = ["마그네슘", "비타민D", "락토핏", "센트룸", "눈 건강"];   // 빈 검색창 안내 행의 예시 (누르면 검색어로 들어감)
  /* 가이드·제품·의약품 색인은 검색창과 빠른 궁합 체크가 함께 쓰므로 처음 필요할 때 한 번만 불러온다 */
  var extra = { guides: null, products: null, drugs: null, prodMatch: null, drugMatch: null, pairings: null, loading: null, onMore: [] };
  function loadExtra() {
    if (extra.loading) return extra.loading;
    extra.loading = Promise.all([
      D.guides().then(function (g) { extra.guides = (g && g.items) || []; }).catch(function () { extra.guides = []; }),
      D.drugPairings().then(function (r) { extra.pairings = r; }).catch(function () { extra.pairings = { rules: [] }; }),   // 의약품별 함께 챙기면 좋은/주의할 영양 성분 규칙
      D.productNames().then(function (n) { extra.products = n && n.p ? n : { i: [], p: [] }; }).catch(function () { extra.products = { i: [], p: [] }; }).then(function () {
        extra.prodMatch = D.productMatcher(extra.products);
        if (extra.products.more) extra.products.more.then(function () { extra.prodMatch = D.productMatcher(extra.products); extra.onMore.forEach(function (f) { f(); }); });   // 과거 제품이 합쳐지면 다시 그리기
      }),
      D.drugNames().then(function (n) { extra.drugs = n && n.p ? n : { i: [], p: [] }; }).catch(function () { extra.drugs = { i: [], p: [] }; }).then(function () { extra.drugMatch = D.drugMatcher(extra.drugs); })   // 의약품 수집 전이면 빈 색인
    ]);
    return extra.loading;
  }
  function initSearch(core) {
    var input = document.getElementById("ingredient-search"), form = document.getElementById("search-form"), box = document.getElementById("search-results");
    var list = document.getElementById("search-list"), status = document.getElementById("search-status"), area = document.getElementById("search-area");
    if (!input || !form || !box || !list) return;
    var matches = [], active = -1;
    function entries(q) {
      var nq = norm(q);
      if (!nq) return [{ hint: true }].concat(POPULAR.map(function (id) { return core.byId[id]; }).filter(Boolean).map(function (it) { return { title: it.name, type: "성분", icon: "pill", href: D.ingredientUrl(it.id) }; }));
      var ings = D.search(core.items, q, 4).map(function (it) { return { title: it.name, html: D.markMatch(it.name, q), type: "성분", icon: "pill", href: D.ingredientUrl(it.id) }; });
      // 제품·의약품은 자모 단위로 비교 → 일부만 입력해도('락ㅌ', 'ㄹㅌㅍ') 관련 제품이 나온다
      var ph = extra.prodMatch ? extra.prodMatch(q, 8) : { idx: [], total: 0 };
      var prods = ph.idx.map(function (i) {
        var pp = extra.products.p[i]; var names = pp[2].map(function (k) { var it = core.byId[extra.products.i[k]]; return it ? it.name : null; }).filter(Boolean);
        var maker = (extra.products.c || [])[pp[3]] || "";
        return { title: pp[1], html: D.markMatch(pp[1], q), type: "제품", icon: "package", href: D.productUrl(pp[0]), subHtml: (maker ? '<span class="maker">' + esc(maker) + '</span> · ' : "") + esc(names.length ? "성분: " + names.slice(0, 3).join(" · ") : "성분 사전과 연결된 성분 없음") };
      });
      var dh = extra.drugMatch ? extra.drugMatch(q, 3) : { idx: [], total: 0 };
      var meds = dh.idx.map(function (i) {
        var pp = extra.drugs.p[i]; var names = pp[2].map(function (k) { var it = core.byId[extra.drugs.i[k]]; return it ? it.name : null; }).filter(Boolean);
        var sub = (pp[3] ? "주성분: " + pp[3] : "") + (names.length ? (pp[3] ? " · " : "") + "영양 성분: " + names.slice(0, 2).join(", ") : "") + (pp[4] === 2 ? " · 전문의약품" : "");
        var maker = (extra.drugs.c || [])[pp[5]] || "";
        return { title: pp[1], html: D.markMatch(pp[1], q), type: "의약품", icon: "pill-bottle", href: D.drugUrl(pp[0]), subHtml: (maker ? '<span class="maker">' + esc(maker) + '</span> · ' : "") + esc(sub || "식약처 허가 의약품") };
      });
      var gs = (extra.guides || []).filter(function (g) { return D.has([g.title, g.h1, (g.keywords || []).join(" ")].join(" "), q); }).slice(0, 2)
        .map(function (g) { return { title: String(g.h1 || g.title || "").split(" — ")[0], type: "가이드", icon: "book-open", href: D.guideUrl(g.slug) }; });
      // 성분 4 · 제품 3 · 가이드 2 · 의약품 2 까지 먼저 채우고, 자리가 남으면 제품·의약품 예시를 더 보여준다 (최대 11)
      var list = ings.concat(prods.slice(0, 3), gs, meds.slice(0, 2));
      if (list.length < 11) list = list.concat(prods.slice(3, 3 + 11 - list.length));
      if (list.length < 11) list = list.concat(meds.slice(2, 2 + 11 - list.length));
      list = list.slice(0, 11);
      var total = ph.total + dh.total;
      if (list.length) list.push({ title: "‘" + q + "’ 전체 검색 결과 보기" + (total > prods.length + meds.length ? " (제품·의약품 " + total.toLocaleString() + "건)" : ""), type: "검색", icon: "search", href: D.searchUrl(q), all: true });
      return list;
    }
    function close() { box.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); active = -1; }
    function selectable() { return matches.filter(function (m) { return !m.hint; }); }
    function setActive(i) {
      active = i;
      var opts = list.querySelectorAll('[role="option"]');
      Array.prototype.forEach.call(opts, function (o, k) { o.setAttribute("aria-selected", k === i ? "true" : "false"); });
      if (opts[i]) input.setAttribute("aria-activedescendant", opts[i].id); else input.removeAttribute("aria-activedescendant");
    }
    function render() {
      matches = entries(input.value.trim()); active = -1; input.removeAttribute("aria-activedescendant");
      var hasHint = matches.length && matches[0].hint;
      list.innerHTML = matches.length
        ? matches.map(function (m, i) {
            if (m.hint) return '<li class="search-hint" role="presentation"><strong>성분명</strong>이나 <strong>제품명</strong>으로 검색해 보세요. 제품명은 일부만 입력해도 됩니다.<div class="examples">' + EXAMPLES.map(function (x) { return '<button type="button" class="ex" data-example="' + esc(x) + '">' + esc(x) + '</button>'; }).join("") + '</div></li>';
            return '<li class="search-option' + (m.all ? " all" : "") + '" id="search-option-' + i + '" role="option" aria-selected="false" data-href="' + esc(m.href) + '"><i data-lucide="' + m.icon + '" class="icon"></i><span class="min-w-0">' + (m.html || esc(m.title)) + (m.subHtml ? '<small>' + m.subHtml + '</small>' : m.sub ? '<small>' + esc(m.sub) + '</small>' : '') + '</span><span class="option-type">' + m.type + '</span></li>';
          }).join("")
        : '<li class="search-empty" role="presentation">성분·제품·의약품·가이드에서 찾지 못했어요. 제품명 일부나 성분명으로 다시 입력해 보세요. <a href="' + esc(D.searchUrl(input.value.trim())) + '">비슷한 이름 찾아보기 →</a></li>';
      D.icons(list);
      box.hidden = false; input.setAttribute("aria-expanded", "true");
      if (hasHint) matches = selectable();   // 안내 행은 선택 대상이 아님 (option id 는 렌더 순서 기준이므로 다시 매김)
      if (hasHint) Array.prototype.forEach.call(list.querySelectorAll('[role="option"]'), function (o, k) { o.id = "search-option-" + k; });
      if (status) status.textContent = matches.length ? "검색 결과 " + matches.length + "개가 있습니다. 화살표 키로 선택하세요." : "검색 결과가 없습니다.";
    }
    function renderWithGuides() { var p = loadExtra(); render(); if (p) p.then(function () { if (!box.hidden) render(); }); }
    extra.onMore.push(function () { if (!box.hidden) render(); });
    list.addEventListener("pointerdown", function (e) { e.preventDefault(); });
    list.addEventListener("click", function (e) {
      var ex = e.target.closest("[data-example]");
      if (ex) { input.value = ex.getAttribute("data-example"); input.focus(); renderWithGuides(); return; }   // 예시를 누르면 검색어로 넣고 바로 결과 표시
      var li = e.target.closest("[data-href]"); if (li) location.href = li.getAttribute("data-href");
    });
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
      if (active >= 0 && matches[active]) { location.href = matches[active].href; return; }   // 화살표로 고른 항목
      if (q) { location.href = D.searchUrl(q); return; }                                      // 그 외에는 통합 검색 결과 페이지로
      render(); input.focus();
    });
    document.addEventListener("click", function (e) { if (area && !area.contains(e.target)) close(); });
    Array.prototype.forEach.call(document.querySelectorAll("[data-focus-search]"), function (a) {
      a.addEventListener("click", function (e) { e.preventDefault(); input.scrollIntoView({ block: "center", behavior: "smooth" }); input.focus({ preventScroll: true }); });
    });
  }

  /* 빠른 궁합 체크 — 성분·제품·의약품 이름으로 두 가지를 고르면 즉시 요약을 보여주고, 자세한 결과는 궁합 페이지로.
   * 제품·의약품은 성분 사전과 연결된 영양 성분들로 계산한다 (연결된 성분이 없으면 해당 페이지로 안내). */
  function initChecker(core) {
    var form = document.getElementById("compatibility-form"), fb = document.getElementById("pair-feedback");
    if (!form || !fb) return;
    var slots = ["first", "second"].map(function (k) {
      return { key: k, wrap: document.querySelector('.pick-wrap[data-pick="' + k + '"]'), input: document.getElementById(k + "-ingredient"), list: document.getElementById(k + "-ingredient-list"), sub: document.getElementById(k + "-ingredient-sub"), sel: null, matches: [], active: -1 };
    });
    if (slots.some(function (s) { return !s.wrap || !s.input || !s.list; })) return;
    slots.forEach(function (s) { s.clear = s.wrap.querySelector(".pick-clear"); });
    var order = { avoid: 0, caution: 1, synergy: 2, neutral: 3 };
    function namesOf(ids) { return ids.map(function (k) { return core.byId[k] ? core.byId[k].name : null; }).filter(Boolean); }
    function candidates(q) {
      var nq = norm(q), out = [];
      if (!nq) return POPULAR.map(function (id) { return core.byId[id]; }).filter(Boolean).map(function (it) { return { kind: "ing", id: it.id, name: it.name, ids: [it.id], type: "성분", icon: "pill" }; });
      D.search(core.items, q, 5).forEach(function (it) { out.push({ kind: "ing", id: it.id, name: it.name, html: D.markMatch(it.name, q), ids: [it.id], type: "성분", icon: "pill" }); });
      if (extra.prodMatch) extra.prodMatch(q, 4).idx.forEach(function (i) {
        var pp = extra.products.p[i], ids = pp[2].map(function (k) { return extra.products.i[k]; }).filter(function (k) { return !!core.byId[k]; });
        out.push({ kind: "prod", id: pp[0], name: pp[1], html: D.markMatch(pp[1], q), ids: ids, type: "제품", icon: "package", maker: (extra.products.c || [])[pp[3]] || "", sub: ids.length ? "성분: " + namesOf(ids).slice(0, 3).join(" · ") : "연결된 영양 성분 없음" });
      });
      if (extra.drugMatch) extra.drugMatch(q, 3).idx.forEach(function (i) {
        var pp = extra.drugs.p[i], ids = pp[2].map(function (k) { return extra.drugs.i[k]; }).filter(function (k) { return !!core.byId[k]; });
        out.push({ kind: "drug", id: pp[0], name: pp[1], html: D.markMatch(pp[1], q), ids: ids, type: "의약품", icon: "pill-bottle", maker: (extra.drugs.c || [])[pp[5]] || "", sub: (pp[3] ? "주성분: " + pp[3] : "") + (ids.length ? (pp[3] ? " · " : "") + "영양 성분: " + namesOf(ids).slice(0, 2).join(", ") : "") });
      });
      return out.slice(0, 9);
    }
    function close(s) { s.list.hidden = true; s.input.setAttribute("aria-expanded", "false"); s.input.removeAttribute("aria-activedescendant"); s.active = -1; }
    function setActive(s, i) {
      s.active = i;
      Array.prototype.forEach.call(s.list.querySelectorAll('[role="option"]'), function (o, k) { o.setAttribute("aria-selected", k === i ? "true" : "false"); if (k === i) { s.input.setAttribute("aria-activedescendant", o.id); o.scrollIntoView({ block: "nearest" }); } });
    }
    function open(s) {
      var q = s.input.value.trim();
      s.matches = candidates(q); s.active = -1; s.input.removeAttribute("aria-activedescendant");
      var hint = !q ? '<li class="pick-hint" role="presentation">많이 찾는 성분이에요. 성분명이나 제품명(락토핏, 우루사 …)을 입력해 보세요.</li>' : "";
      s.list.innerHTML = hint + (s.matches.length
        ? s.matches.map(function (m, i) { return '<li class="pick-option" id="' + s.key + '-ingredient-opt-' + i + '" role="option" aria-selected="false" data-i="' + i + '"><i data-lucide="' + m.icon + '" class="icon"></i><span>' + (m.html || esc(m.name)) + ((m.sub || m.maker) ? '<small>' + (m.maker ? '<span class="maker">' + esc(m.maker) + '</span>' + (m.sub ? " · " : "") : "") + esc(m.sub || "") + '</small>' : "") + '</span><span class="option-type">' + m.type + '</span></li>'; }).join("")
        : '<li class="pick-empty" role="presentation">찾지 못했어요. 성분명이나 제품명 일부로 다시 입력해 보세요.</li>');
      D.icons(s.list);
      s.list.hidden = false; s.input.setAttribute("aria-expanded", "true");
    }
    function openWithExtra(s) { var p = loadExtra(); open(s); if (p) p.then(function () { if (!s.list.hidden && document.activeElement === s.input) open(s); }); }
    function select(s, m) {
      s.sel = m; s.input.value = m.name; s.input.classList.add("has-value"); s.input.removeAttribute("aria-invalid");
      if (m.kind === "drug" && !m.loaded) {   // 규칙 판정에 필요한 주성분(영문)·분류는 상세 조각에 있다
        D.drugDetail(m.id).then(function (d) { m.detail = d || null; }).catch(function () { m.detail = null; }).then(function () { m.loaded = true; if (s.sel === m) update(); });
      }
      if (s.clear) s.clear.hidden = false;
      if (s.sub) {
        if (m.kind === "ing") { s.sub.hidden = true; s.sub.textContent = ""; }
        else { s.sub.hidden = false; s.sub.innerHTML = (m.maker ? '<span class="maker">' + esc(m.maker) + '</span> · ' : "") + (m.ids.length ? "영양 성분: " + esc(namesOf(m.ids).join(", ")) : "성분 사전과 연결된 영양 성분이 없어 궁합 계산은 어려워요"); }
      }
      close(s); update();
    }
    function clearSlot(s) { s.sel = null; s.input.value = ""; s.input.classList.remove("has-value"); if (s.clear) s.clear.hidden = true; if (s.sub) { s.sub.hidden = true; s.sub.textContent = ""; } close(s); update(); }
    function err(msg, s) { fb.textContent = msg; fb.className = "form-feedback error"; if (s) s.input.setAttribute("aria-invalid", "true"); }
    function pageOf(m) { return m.kind === "prod" ? D.productUrl(m.id) : m.kind === "drug" ? D.drugUrl(m.id) : D.ingredientUrl(m.id); }
    function unionIds(a, b) { var seen = {}, out = []; a.concat(b).forEach(function (k) { if (!seen[k]) { seen[k] = true; out.push(k); } }); return out; }
    function short(name) { var t = String(name || "").replace(/\s*\([^)]*\)\s*$/, "").trim(); return t.length > 18 ? t.slice(0, 17) + "…" : t; }
    function nameOf(id) { return core.byId[id] ? core.byId[id].name : id; }
    function ruleHits(drugSel, otherIds) {   // 의약품 규칙(data/drug-pairings.json)과 상대 성분의 교집합
      if (drugSel.kind !== "drug" || !extra.pairings) return null;
      var d = drugSel.detail || { name: drugSel.name, ingr: [], cls: "", ingredients: drugSel.ids };
      var pr = D.drugPairingFor(extra.pairings, d, core);
      return { good: pr.good.filter(function (g) { return otherIds.indexOf(g.id) >= 0; }), caution: pr.caution.filter(function (c) { return otherIds.indexOf(c.id) >= 0; }),
        suggest: pr.good.filter(function (g) { return otherIds.indexOf(g.id) < 0; }).slice(0, 3), any: !!(pr.good.length || pr.caution.length || pr.notes.length) };
    }
    function drugLink(drugSel, otherIds) { return D.drugUrl(drugSel.id) + "&with=" + otherIds.map(encodeURIComponent).join(",") + "#sec-pairing"; }
    function update() {
      slots.forEach(function (s) { s.input.removeAttribute("aria-invalid"); });
      fb.className = "form-feedback";
      var A = slots[0].sel, B = slots[1].sel;
      if (!A || !B) { fb.textContent = "성분은 물론 락토핏·우루사 같은 제품명으로도 고를 수 있어요. 자세한 결과는 궁합 페이지에서 확인합니다."; return; }
      if (A.kind === B.kind && A.id === B.id) { err("서로 다른 두 가지를 골라 주세요.", slots[1]); return; }
      if (!A.ids.length || !B.ids.length) {
        var drug = (!A.ids.length && A.kind === "drug") ? A : (!B.ids.length && B.kind === "drug") ? B : null;
        var other = drug === A ? B : A;
        if (!drug) {   // 영양 성분이 연결되지 않은 건강기능식품
          var who = !A.ids.length ? A : B;
          fb.innerHTML = '<strong>' + esc(short(who.name)) + '</strong>은(는) 성분 사전과 연결된 영양 성분이 없어 궁합을 계산할 수 없어요. <a href="' + esc(pageOf(who)) + '">제품 정보 보기 →</a>';
          fb.classList.add("ready"); return;
        }
        if (!other.ids.length) {   // 둘 다 영양 성분 없음 (의약품 + 의약품 등)
          fb.innerHTML = '두 가지 모두 영양 성분이 연결되지 않아 영양제 궁합으로는 계산할 수 없어요. 각 페이지의 상호작용 항목과 약사 상담을 참고하세요. <a href="' + esc(pageOf(A)) + '">' + esc(short(A.name)) + ' →</a> · <a href="' + esc(pageOf(B)) + '">' + esc(short(B.name)) + ' →</a>';
          fb.classList.add("ready"); return;
        }
        if (!drug.loaded) { fb.textContent = "의약품 정보를 확인하는 중…"; return; }
        var h = ruleHits(drug, other.ids);
        var link = ' <a href="' + esc(drugLink(drug, other.ids)) + '">자세히 보기 →</a>';
        if (h && h.caution.length) {
          var c = h.caution[0];
          fb.innerHTML = '<strong>주의</strong> · ' + esc(short(drug.name)) + ' + ' + esc(nameOf(c.id)) + ' — ' + esc(c.why) + (c.hours ? ' (' + c.hours + '시간 이상 간격)' : "") + link;
        } else if (h && h.good.length) {
          var g = h.good[0];
          fb.innerHTML = '<strong>함께 챙기면 좋아요</strong> · ' + esc(short(drug.name)) + ' + ' + esc(nameOf(g.id)) + ' — ' + esc(g.why) + link;
        } else {
          fb.innerHTML = '<strong>알려진 특별한 상호작용 없음</strong> · ' + esc(short(drug.name)) + ' 복용 중 ' + esc(namesOf(other.ids).join(", ")) + '을(를) 함께 먹는 것에 대해 기록된 주의사항은 없어요. 약의 상호작용 항목과 약사 상담을 참고하세요.' +
            (h && h.suggest.length ? ' <span class="muted">함께 챙기면 좋은 영양제: ' + esc(h.suggest.map(function (g) { return nameOf(g.id); }).join(", ")) + '</span>' : "") + link;
        }
        fb.classList.add("ready"); return;
      }
      var shared = A.ids.filter(function (k) { return B.ids.indexOf(k) >= 0; });
      var pairs = [];
      A.ids.forEach(function (a) { B.ids.forEach(function (b) { if (a === b) return; pairs.push({ a: a, b: b, p: D.findPair(core, a, b) }); }); });
      var notes = [];   // 의약품 쪽 규칙(제산제+철분 등)은 성분 조합과 별도로 덧붙인다
      [A, B].forEach(function (x, i) {
        if (x.kind !== "drug" || !x.loaded) return;
        var h = ruleHits(x, (i === 0 ? B : A).ids); if (!h) return;
        h.caution.forEach(function (c) { notes.push('<strong>주의</strong> · ' + esc(short(x.name)) + ' + ' + esc(nameOf(c.id)) + ' — ' + esc(c.why) + (c.hours ? ' (' + c.hours + '시간 이상 간격)' : "")); });
        h.good.forEach(function (g) { notes.push('<strong>함께 챙기면 좋아요</strong> · ' + esc(short(x.name)) + ' + ' + esc(nameOf(g.id)) + ' — ' + esc(g.why)); });
      });
      if (A.ids.length === 1 && B.ids.length === 1 && !notes.length) {
        var p1 = pairs[0] && pairs[0].p, t1 = p1 && core.types[p1.type];
        fb.textContent = t1 ? t1.short + " · " + p1.title : "알려진 특별한 상호작용이 없는 조합이에요. 자세한 내용은 궁합 페이지에서 확인하세요.";
        fb.classList.add("ready"); return;
      }
      var known = pairs.filter(function (x) { return x.p; }).sort(function (x, y) { return (order[x.p.type] === undefined ? 9 : order[x.p.type]) - (order[y.p.type] === undefined ? 9 : order[y.p.type]); });
      var counts = {}; known.forEach(function (x) { counts[x.p.type] = (counts[x.p.type] || 0) + 1; });
      var parts = [];
      if (counts.avoid) parts.push("피해야 할 조합 " + counts.avoid);
      if (counts.caution) parts.push("주의 " + counts.caution);
      if (counts.synergy) parts.push("좋은 궁합 " + counts.synergy);
      var notable = known.filter(function (x) { return x.p.type !== "neutral"; });
      var head = notable.length ? '<strong>' + esc((core.types[notable[0].p.type] || {}).short || "") + '</strong> · ' + esc(core.byId[notable[0].a].name) + " + " + esc(core.byId[notable[0].b].name) + " — " + esc(notable[0].p.title) : "알려진 특별한 상호작용이 없는 조합이에요.";
      fb.innerHTML = head + ' <span class="muted">(' + pairs.length + '개 조합' + (parts.length ? ' 중 ' + esc(parts.join(" · ")) : " 확인") + ')</span>' + (shared.length ? ' · 겹치는 성분: ' + esc(namesOf(shared).join(", ")) + ' (중복 섭취 주의)' : "") + (notes.length ? '<br>' + notes.slice(0, 2).join("<br>") : "");
      fb.classList.add("ready");
    }
    slots.forEach(function (s) {
      s.input.addEventListener("input", function () {
        if (s.sel) { s.sel = null; s.input.classList.remove("has-value"); if (s.sub) s.sub.hidden = true; update(); }
        if (s.clear) s.clear.hidden = !s.input.value;
        openWithExtra(s);
      });
      s.input.addEventListener("focus", function () { openWithExtra(s); });
      s.input.addEventListener("keydown", function (e) {
        if (e.isComposing || e.keyCode === 229) return;
        if (e.key === "Escape") { e.preventDefault(); close(s); return; }
        if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (s.list.hidden) open(s); if (!s.matches.length) return; setActive(s, (s.active + (e.key === "ArrowDown" ? 1 : -1) + s.matches.length) % s.matches.length); return; }
        if (e.key === "Enter" && !s.list.hidden) { e.preventDefault(); var m = s.matches[s.active >= 0 ? s.active : 0]; if (m) select(s, m); }
      });
      s.list.addEventListener("pointerdown", function (e) { e.preventDefault(); });
      s.list.addEventListener("click", function (e) { var li = e.target.closest("[data-i]"); if (li) select(s, s.matches[+li.getAttribute("data-i")]); });
      if (s.clear) s.clear.addEventListener("click", function () { clearSlot(s); s.input.focus(); });
    });
    document.addEventListener("click", function (e) { slots.forEach(function (s) { if (!s.wrap.contains(e.target)) close(s); }); });
    extra.onMore.push(function () { slots.forEach(function (s) { if (!s.list.hidden) open(s); }); });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var A = slots[0].sel, B = slots[1].sel;
      if (!A) { err("첫 번째 영양제를 고르세요. 성분명이나 제품명을 입력하면 목록이 나옵니다.", slots[0]); slots[0].input.focus(); return; }
      if (!B) { err("두 번째 영양제를 고르세요.", slots[1]); slots[1].input.focus(); return; }
      if (A.kind === B.kind && A.id === B.id) { err("서로 다른 두 가지를 골라 주세요.", slots[1]); slots[1].input.focus(); return; }
      if (!A.ids.length || !B.ids.length) {
        var drug = (!A.ids.length && A.kind === "drug") ? A : (!B.ids.length && B.kind === "drug") ? B : null, other = drug === A ? B : A;
        location.href = (drug && other.ids.length) ? drugLink(drug, other.ids) : pageOf(!A.ids.length ? A : B); return;
      }
      location.href = D.compatUrl(unionIds(A.ids, B.ids));
    });
    update();
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
