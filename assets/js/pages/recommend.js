/* 맞춤 추천(recommend.html) — 내 정보(연령대·성별·고민·생활 상황·복용 중인 약, 셀프체크 질문 그대로)를 기기 안(store.js profile)에 저장하고,
   셀프체크 엔진(finder.js score)으로 추천 성분을 근거 칩('왜' = 내가 답한 라벨, '식약처 인정 기능성' = 성분 사전 mfdsFunction)과 함께 보여 준다.
   답은 주소 쿼리·분석 이벤트에 담지 않는다. 구매 버튼은 앱에서 쇼핑이 꺼져 있으면 '제품 찾기'(사이트 안 제품 목록). */
(function () {
  "use strict";
  var D = window.Data, S = window.Store, F = window.Finder, esc = D.esc;
  var core = null, data = null, guides = null, state = null, ui = { editing: false };
  var FLAG_TEXT = {
    kids: { title: "어린이 기준으로 추천했어요", body: "어린이 가이드의 성분 범위 안에서만 골랐습니다. 제품 라벨의 연령 표시와 섭취량을 꼭 확인하고, 보호자가 판단해 주세요.", link: "kids-by-age" },
    teens: { title: "청소년 기준으로 추천했어요", body: "청소년·수험생 가이드의 성분 범위 안에서만 골랐습니다. 성장기에는 식사가 우선이며 제품 라벨의 연령 표시를 확인하세요.", link: "teens" },
    pregnancy: { title: "임신·수유·출산 후에는 더 신중하게", body: "해당 가이드의 성분 범위 안에서만 추천했습니다. 새 영양제를 시작하기 전에 반드시 산부인과·약사와 상의하세요.", link: "pregnancy" },
    meds: { title: "약을 복용 중이라면", body: "약과 영양제의 상호작용이 있을 수 있어 약 복용자 가이드를 함께 보여드립니다. 복용 간격과 주의 성분을 확인하고 의사·약사와 상의하세요.", link: "with-medication" },
    cancer: { title: "항암 치료 중에는 담당 의료진과 먼저", body: "치료 중 영양제는 치료 반응에 영향을 줄 수 있어 담당 의료진의 확인이 먼저입니다. 가이드는 참고용입니다.", link: "cancer-treatment" },
    kidney: { title: "신장질환·투석 중에는 제한이 많아요", body: "칼륨·마그네슘·비타민 등 일부 성분은 제한될 수 있습니다. 담당 의료진과 영양사의 안내를 우선하세요.", link: "kidney" },
    surgery: { title: "수술 전에는 중단할 성분이 있어요", body: "출혈 경향이 있는 성분(오메가3·은행잎·마늘·비타민E·홍삼·커큐민·나토키나제 등)은 추천에서 뺐습니다. 수술 일정을 의료진에게 알리고 복용 중인 영양제의 중단·재개 시점을 상의하세요.", link: "surgery" },
    bleeding: { title: "항응고제·항혈소판제를 드신다면 출혈 경향 성분은 뺐어요", body: "혈소판·응고에 작용하는 성분(은행잎·나토키나제·오메가3·비타민E·홍삼·마늘·커큐민 등)과 와파린 효과를 바꾸는 성분(비타민K·코엔자임Q10·클로렐라)은 추천에서 제외했습니다. 새 영양제는 반드시 의사·약사와 상의하고 임의로 시작·중단하지 마세요.", link: "with-medication" }
  };

  function isApp() { return !!(window.AppBridge && window.AppBridge.isNative()); }
  function hideShop() { return !!(window.AppBridge && window.AppBridge.hideShopping()); }
  function questions() { return (data.questions || []).filter(function (q) { return q.type !== "ingredients"; }); }
  function profile() { return S.profile(state); }
  /* 저장한 내 정보 + 지금 먹는 성분(제품 안 성분 포함) → 셀프체크 엔진의 답 꼴 */
  function answers() {
    var p = profile() || {}, a = {};
    Object.keys(p).forEach(function (k) { if (k !== "updatedAt") a[k] = p[k]; });
    a.have = S.ingredientIds(state);
    return a;
  }
  function guideOf(slug) { return (guides || []).filter(function (g) { return g.slug === slug; })[0]; }
  function persist() { S.save(state); if (isApp()) window.AppBridge.mirror(JSON.stringify(state)); }
  function firstSentence(s) { var m = /^(.+?[.!?])(\s|$)/.exec(String(s || "").trim()); return m ? m[1] : String(s || ""); }

  /* ---- 내 정보 폼 (셀프체크 질문·옵션 그대로, 저장은 기기 안) ---- */
  function renderForm() {
    var cur = profile() || {};
    var qs = questions().map(function (q, i) {
      var type = q.type === "single" ? "radio" : "checkbox";
      var opts = (q.options || []).map(function (o) {
        var on = (cur[q.id] || []).indexOf(o.id) >= 0;
        return '<label class="finder-opt"><input type="' + type + '" name="' + esc(q.id) + '" value="' + esc(o.id) + '"' + (on ? " checked" : "") + '><span>' + esc(o.label) + "</span></label>";
      }).join("");
      return '<fieldset class="finder-q" data-q="' + esc(q.id) + '"' + (q.max ? ' data-max="' + q.max + '"' : "") + '><legend><span class="finder-num">' + (i + 1) + "</span>" + esc(q.title) + "</legend>" +
        (q.hint ? '<p class="finder-hint">' + esc(q.hint) + "</p>" : "") + '<div class="finder-opts">' + opts + "</div></fieldset>";
    }).join("");
    return '<form id="rec-form" class="finder-form" novalidate><h2 class="rec-h2"><i data-lucide="user-round"></i>내 정보</h2>' + qs +
      '<p class="rec-privacy"><i data-lucide="lock"></i>내 정보는 이 기기에만 저장되고 서버로 보내지 않아요. 다른 기기로 옮기기 코드에는 함께 담겨요.</p>' +
      '<div class="finder-actions"><button type="submit" class="btn-primary"><i data-lucide="sparkles"></i>저장하고 추천 보기</button>' +
      (profile() ? '<button type="button" class="btn-outline" data-rec-cancel>취소</button>' : "") + "</div></form>";
  }
  function renderSummary() {
    var labels = F.summary(answers(), data);
    return '<section class="rec-summary"><div><p class="k">내 정보</p><div class="rec-chips">' + labels.map(function (l) { return '<span class="rec-chip">' + esc(l) + "</span>"; }).join("") + "</div></div>" +
      '<button type="button" class="btn-outline btn-sm" data-rec-edit><i data-lucide="pencil"></i>수정</button></section>';
  }

  /* ---- 추천 결과 ---- */
  function mfdsOf(it) { var m = it.mfdsFunction; if (Array.isArray(m)) m = m[0]; return m ? String(m) : ""; }
  function buyHtml(it) {
    if (hideShop()) return '<a class="btn-outline btn-sm" href="' + D.productsUrl(it.id) + '"><i data-lucide="search"></i>제품 찾기</a>';
    return window.Affiliate ? window.Affiliate.buttonsHtml(it.shopQuery || it.name, { size: "sm", short: true }) : "";
  }
  function addHtml(id, have) {
    if (have) return '<a class="btn-outline btn-sm is-added" href="my.html"><i data-lucide="check"></i>이미 먹고 있어요</a>';
    return '<button type="button" class="btn-primary btn-sm" data-my-add="' + esc(id) + '"><i data-lucide="plus"></i>내 영양제에 추가</button>';
  }
  function card(id, r, ans, have) {
    var it = core.byId[id], info = r.ingredients.filter(function (x) { return x.id === id; })[0] || { from: [] };
    var cat = core.categories[it.category] || {};
    var why = F.reasons(ans, data, info.from).slice(0, 3), mfds = mfdsOf(it);
    return '<article class="rec-card' + (have ? " is-have" : "") + '"><h3><a href="' + D.ingredientUrl(id) + '">' + esc(it.name) + '</a><small>' + esc(cat.label || "") + "</small></h3>" +
      '<div class="rec-chips">' + why.map(function (w) { return '<span class="rec-chip why">' + esc(w) + "</span>"; }).join("") + (mfds ? '<span class="rec-chip mfds">인정 기능성 · ' + esc(mfds) + "</span>" : "") + "</div>" +
      (it.summary ? '<p class="rec-line">' + esc(firstSentence(it.summary)) + "</p>" : "") +
      (it.whoFor && it.whoFor.length ? '<p class="rec-who">이런 분: ' + esc(it.whoFor.slice(0, 2).join(" · ")) + "</p>" : "") +
      '<div class="rec-actions">' + addHtml(id, have) + buyHtml(it) + "</div></article>";
  }
  function renderResult() {
    if (!profile()) return '<section class="rec-empty"><i data-lucide="sparkles"></i><p>내 정보를 저장하면 추천이 나와요.</p></section>';
    var ans = answers(), r = F.score(ans, data, guides, core);
    var rec = r.recommended.slice(0, 8);
    var haveScored = r.have.filter(function (id) { return r.ingredients.some(function (x) { return x.id === id; }); }).slice(0, 2);
    var flags = r.flags.map(function (f) {
      var t = FLAG_TEXT[f]; if (!t) return "";
      var g = guideOf(t.link);
      return '<div class="finder-flag"><i data-lucide="triangle-alert" class="h-5 w-5 shrink-0 text-amber-600"></i><div><p class="font-bold text-amber-900">' + esc(t.title) + '</p><p class="mt-1 text-sm text-amber-900/90">' + esc(t.body) + "</p>" +
        (g ? '<a class="mt-1 inline-block text-sm font-bold text-brand-700 underline" href="' + D.guideUrl(g.slug) + '">' + esc(g.h1 || g.title) + " 가이드 보기</a>" : "") + "</div></div>";
    }).join("");
    var avoided = (r.avoided || []).map(function (id) { return core.byId[id] ? core.byId[id].name : id; });
    var avoidedHave = (r.avoidedHave || []).map(function (id) { return core.byId[id] ? core.byId[id].name : id; });
    var html = '<section class="rec-result"><h2 class="rec-h2"><i data-lucide="sparkles"></i>추천 성분 <span class="rec-count">' + rec.length + "가지</span></h2>" +
      '<p class="my-sub">내 정보에 맞는 가이드가 식약처 인정 기능성 기준으로 꼽은 핵심 성분 가운데 점수가 높은 순입니다. 주황 칩은 "왜 골랐는지", 초록 칩은 식약처 인정 기능성 문구예요.</p>' +
      (flags ? '<div class="mt-4 space-y-3">' + flags + "</div>" : "");
    if (!rec.length && !haveScored.length) html += '<div class="rec-empty"><p>답변과 연결되는 가이드가 아직 없어요. 고민이나 생활 상황을 하나 이상 골라 보세요.</p></div>';
    html += '<div class="rec-grid">' + rec.map(function (id) { return card(id, r, ans, false); }).join("") + haveScored.map(function (id) { return card(id, r, ans, true); }).join("") + "</div>";
    if (avoided.length) html += '<p class="rec-note"><b>복용 중인 약·수술 때문에 추천에서 뺀 성분:</b> ' + esc(avoided.join(", ")) + "</p>";
    if (avoidedHave.length) html += '<p class="rec-note is-warn"><b>이미 드시는 성분 가운데 ' + esc(avoidedHave.join(", ")) + "</b> — 복용 중인 약·수술과 관련해 의사·약사와 상의하세요.</p>";
    if (r.recommended.length > rec.length) html += '<p class="rec-note">그다음으로 점수가 높은 성분: ' + esc(r.recommended.slice(8, 13).map(function (id) { return core.byId[id].name; }).join(", ")) + "</p>";
    return html + "</section>";
  }

  function render() {
    var app = document.getElementById("rec-app");
    var top = (profile() && !ui.editing) ? renderSummary() : renderForm();
    app.innerHTML = top + renderResult();
    var disc = document.getElementById("rec-disclosure");
    if (disc) { var text = (!hideShop() && profile() && window.Affiliate) ? window.Affiliate.disclosure() : ""; disc.textContent = text; disc.hidden = !text; }
    D.icons(app);
  }
  function readForm(form) {
    var out = {};
    questions().forEach(function (q) {
      var vals = Array.prototype.map.call(form.querySelectorAll('input[name="' + q.id + '"]:checked'), function (i) { return i.value; });
      if (vals.length) out[q.id] = vals;
    });
    return out;
  }
  function bind(app) {
    app.addEventListener("submit", function (e) {
      if (e.target.id !== "rec-form") return;
      e.preventDefault();
      state = S.setProfile(state, readForm(e.target), data); persist();
      ui.editing = false; render();
      var res = app.querySelector(".rec-result"); if (res) res.scrollIntoView({ block: "start", behavior: "smooth" });
    });
    app.addEventListener("change", function (e) {   // 다중 선택 상한(max): 넘으면 방금 누른 것을 되돌린다
      var t = e.target; if (!(t instanceof HTMLInputElement) || t.type !== "checkbox") return;
      var fs = t.closest("fieldset[data-max]"); if (!fs) return;
      var max = +fs.getAttribute("data-max"), on = fs.querySelectorAll("input:checked").length;
      if (max && on > max) { t.checked = false; fs.classList.add("is-over"); setTimeout(function () { fs.classList.remove("is-over"); }, 600); }
    });
    app.addEventListener("click", function (e) {
      var t = e.target.closest("[data-rec-edit],[data-rec-cancel]"); if (!t) return;
      ui.editing = t.hasAttribute("data-rec-edit"); render();
    });
    window.addEventListener("yj:change", function () { state = S.load(); render(); });   // '내 영양제에 추가'(layout.js 공통 처리) 뒤 '이미 먹고 있어요' 반영
    window.addEventListener("storage", function (e) { if (!e.key || e.key === S.KEY) { state = S.load(); render(); } });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var app = document.getElementById("rec-app");
    if (!app || !S || !F) return;
    Promise.all([D.core(), D.finder(), D.guides()]).then(function (res) {
      return (window.AppBridge ? window.AppBridge.ready() : Promise.resolve()).then(function () { return res; });
    }).then(function (res) {
      core = res[0]; data = res[1]; guides = (res[2] && res[2].items) || [];
      state = S.load();
      bind(app); render();
    }).catch(function () { app.innerHTML = '<p class="text-sm text-ink-500">데이터를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.</p>'; });
  });
})();
