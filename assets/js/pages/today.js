/* 오늘 홈(today.html) — 앱의 첫 화면. 저장한 영양제가 없으면 시작 안내, 있으면 인사·다음 복용·오늘 시간표·오늘의 한 줄·바로가기.
   로직은 today.js(순수), 상태는 store.js. '먹었어요'는 my.html 의 체크와 같은 기록(markDue + toggleDone). 알림 버튼 동작은 app.js 가 my.html 로 보낸다. */
(function () {
  "use strict";
  var D = window.Data, S = window.Store, T = window.Today, esc = D.esc;
  var core = null, state = null, tips = [], ltRules = null, splashList = [];

  /* 앱을 처음 열 때(세션당 한 번) 로고와 건강 한 마디를 잠깐 보여 준 뒤 홈을 드러낸다. 탭하면 바로 닫힌다. 로컬 확인은 ?splash=1 */
  function wantSplash() {
    try {
      if (/[?&]splash=1/.test(location.search)) return true;
      if (!isApp() || sessionStorage.getItem("yj.splashShown")) return false;
      sessionStorage.setItem("yj.splashShown", "1"); return true;
    } catch (e) { return false; }
  }
  function showSplash() {
    var el = document.getElementById("today-splash"); if (!el) return null;
    var root = document.documentElement.getAttribute("data-root") || "./";
    el.innerHTML = '<div class="splash-inner"><img class="splash-mark" src="' + root + 'assets/images/favicon.svg?v=2" alt="" width="72" height="72"><p class="splash-brand">영양제<span>.kr</span></p><p class="splash-line" id="splash-line"></p></div>';
    el.hidden = false; el.classList.add("is-on"); document.body.classList.add("has-splash");
    var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var closed = false, timer = setTimeout(close, reduced ? 1200 : 2600);
    function close() {
      if (closed) return; closed = true; clearTimeout(timer);
      el.classList.add("is-off");
      setTimeout(function () { el.hidden = true; el.classList.remove("is-on", "is-off"); document.body.classList.remove("has-splash"); }, reduced ? 50 : 450);
    }
    el.addEventListener("click", close);
    return { setLine: function (text) { var p = document.getElementById("splash-line"); if (p && text) { p.textContent = text; p.classList.add("is-in"); } } };
  }

  function isApp() { return !!(window.AppBridge && window.AppBridge.isNative()); }
  var splash = wantSplash() ? showSplash() : null;   // defer 스크립트 실행 시점(DOMContentLoaded 전)에 바로 띄운다 — 홈이 먼저 보이는 시간을 줄임
  function today() { return S.dateKey(new Date()); }
  function schedule() { return state.items.length ? window.Schedule.build(S.entries(state), core, S.overrides(state)) : { slots: [], notes: [] }; }
  function persist() { S.save(state); if (isApp()) { window.AppBridge.mirror(JSON.stringify(state)); window.AppBridge.requestSync(); } }
  function timeLabel(hhmm) {   // "08:00" → "오전 8:00"
    var m = /^(\d\d):(\d\d)$/.exec(hhmm || ""); if (!m) return hhmm || "";
    var h = +m[1]; return (h < 12 ? "오전 " : "오후 ") + (h % 12 === 0 ? 12 : h % 12) + ":" + m[2];
  }
  function names(list) { return list.length <= 2 ? list.join(" · ") : list[0] + " 외 " + (list.length - 1); }
  function chip(n) { return '<span class="today-chip">' + esc(n) + "</span>"; }
  function tipCard(tip) {
    if (!tip || !tip.text) return "";
    return '<section class="today-card today-tip"><p class="k">오늘의 한 줄</p><p class="t">' + esc(tip.text) + '</p><small>' + esc(tip.source) + "</small></section>";
  }
  function shortcuts(list) {
    return '<nav class="today-grid" aria-label="바로가기">' + list.map(function (s) {
      return '<a href="' + esc(s.href) + '"><i data-lucide="' + s.icon + '"></i><span>' + esc(s.label) + "</span>" + (s.sub ? "<small>" + esc(s.sub) + "</small>" : "") + "</a>";
    }).join("") + "</nav>";
  }

  /* 저장한 영양제가 없을 때: 시작 안내 3단계 */
  function renderStart(now) {
    var tip = T.tip([], core, now, tips, {});
    return '<section class="today-start"><div class="art" aria-hidden="true"><i data-lucide="pill"></i><i data-lucide="leaf"></i></div>' +
      '<h1>먹는 영양제를 저장해 보세요</h1><p>복용 시간표와 알림이 자동으로 만들어지고,<br>궁합과 맞춤 추천까지 이어집니다.</p>' +
      '<ol class="today-steps">' +
        '<li><a href="my.html"><span class="num">1</span><div><b>내 영양제 추가</b><small>성분·제품명으로 검색해서 담기</small></div></a></li>' +
        '<li><a href="recommend.html"><span class="num">2</span><div><b>내 정보 입력</b><small>연령대·성별·고민 — 맞춤 추천에 쓰여요</small></div></a></li>' +
        '<li><a href="my.html#my-reminders"><span class="num">3</span><div><b>알림 켜기</b><small>시간대별 알림, \'먹었어요\'로 기록</small></div></a></li>' +
      "</ol>" +
      '<a class="btn-primary today-cta" href="my.html"><i data-lucide="plus"></i>내 영양제 추가하기</a></section>' +
      tipCard(tip) +
      shortcuts([{ href: "ingredients.html", icon: "search", label: "검색" }, { href: "compatibility.html", icon: "heart-handshake", label: "궁합 체크" }, { href: "finder.html", icon: "clipboard-check", label: "셀프체크" }, { href: "help.html", icon: "book-open", label: "사용 설명" }]);
  }

  /* 저장한 영양제가 있을 때 */
  function renderHome(now) {
    var sched = schedule(), nd = T.nextDose(state, sched, now), tl = T.timeline(state, sched, now);
    var tip = T.tip(S.entries(state), core, now, tips, { resolvePair: D.resolvePair });
    var logOn = state.settings.logEnabled === true;
    var card;
    if (nd.status === "all-done") {
      card = '<section class="today-next is-done"><p class="k">오늘 복용</p><b>오늘 다 챙겼어요 🎉</b><small>' + tl.length + "개 시간대를 모두 체크했어요. 내일 또 봐요.</small></section>";
    } else if (nd.status === "none") {
      card = "";
    } else {
      card = '<section class="today-next' + (nd.status === "missed" ? " is-missed" : "") + '"><p class="k">' + (nd.status === "missed" ? "지나간 복용 · " : "다음 복용 · ") + esc(S.SLOT_LABEL[nd.slot]) + "</p>" +
        "<b>" + esc(timeLabel(nd.time)) + "</b>" + (nd.status === "missed" ? '<small>시간이 지났어요. 챙겼다면 체크해 주세요.</small>' : "") +
        '<div class="today-chips">' + nd.names.map(chip).join("") + "</div>" +
        (logOn ? '<button type="button" class="today-done" data-done="' + esc(nd.slot) + '"><i data-lucide="check"></i>먹었어요</button>'
               : '<a class="today-done is-link" href="my.html#my-log"><i data-lucide="circle-check"></i>기록을 켜면 여기서 바로 체크해요 · 켜기</a>') +
        "</section>";
    }
    var doneCount = tl.filter(function (r) { return r.done; }).length;
    var rows = tl.map(function (r) {
      var tag = r.done ? '<span class="tag is-done">✓ 먹음</span>' : (r.isNext ? '<span class="tag">' + (nd.status === "missed" ? "지남" : "다음") + "</span>" : "");
      return '<li class="today-tl' + (r.done ? " is-done" : "") + (r.isNext ? " is-next" : "") + '"><span class="dot"></span><div><b>' + esc(r.time) + " " + esc(r.label) + "</b><small>" + esc(names(r.names)) + "</small></div>" +
        (r.reminderOff ? '<i data-lucide="bell-off" class="off" aria-label="알림 꺼짐"></i>' : "") + tag + "</li>";
    }).join("");
    var due = (ltRules && window.LongTerm) ? window.LongTerm.check(state, ltRules, core, now) : [];
    var ltCard = due.length ? '<a class="today-card today-lt" href="my.html#my-longterm"><p class="k">장기 복용 점검</p><b>' + esc(due[0].name) + (due.length > 1 ? " 외 " + (due.length - 1) + "개" : "") + " — 점검해 볼 때예요</b><small>내 영양제에서 쉬어 갈지, 계속 먹을지 골라 보세요 ›</small></a>" : "";
    var ids = S.ingredientIds(state);
    var compat = { href: "compatibility.html?items=" + ids.slice(0, 8).map(encodeURIComponent).join(","), icon: "heart-handshake", label: "궁합 체크", sub: ids.length > 8 ? "앞 8개" : "" };
    return '<p class="today-date">' + esc(T.dateLabel(now)) + '</p><h1 class="today-hello">' + esc(T.greeting(now)) + ' 👋</h1>' + card +
      '<section class="today-card"><p class="k">오늘 시간표 · ' + doneCount + " / " + tl.length + ' 완료</p><ul class="today-timeline">' + rows + "</ul></section>" +
      ltCard + tipCard(tip) +
      shortcuts([{ href: "my.html", icon: "pill", label: "내 영양제" }, compat, { href: "recommend.html", icon: "sparkles", label: "맞춤 추천" }, { href: "help.html", icon: "book-open", label: "사용 설명" }]);
  }

  function render() {
    var app = document.getElementById("today-app"), now = new Date();
    app.innerHTML = state.items.length ? renderHome(now) : renderStart(now);
    D.icons(app);
  }
  function markDone(slot) {
    var tk = today(), sched = schedule();
    var fresh = S.markDue(state, tk, sched.slots.map(function (s) { return s.key; }));
    state = S.toggleDone(fresh, tk, slot, true); persist(); render();
  }
  var midnightTimer = null;
  function scheduleMidnight() {
    clearTimeout(midnightTimer);
    var now = new Date(), next = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 2);
    midnightTimer = setTimeout(function () { render(); scheduleMidnight(); }, Math.max(1000, next - now));
  }

  document.addEventListener("DOMContentLoaded", function () {
    var app = document.getElementById("today-app");
    if (!app || !S || !T) return;
    Promise.all([D.core(), D.tips().catch(function () { return { items: [] }; }), D.longterm().catch(function () { return null; })]).then(function (res) {
      return (window.AppBridge ? window.AppBridge.ready() : Promise.resolve()).then(function () { return res; });   // 앱이면 런타임 로드·복원을 기다린다
    }).then(function (res) {
      core = res[0]; tips = (res[1] && res[1].items) || []; splashList = (res[1] && res[1].splash) || []; ltRules = res[2];
      if (splash) splash.setLine(T.splashLine(splashList, new Date()));
      state = S.load();
      var pr = S.pruneUnknown(state, core.byId);
      if (pr.removed.length) { state = pr.state; persist(); }
      app.addEventListener("click", function (e) { var t = e.target.closest("[data-done]"); if (t) markDone(t.getAttribute("data-done")); });
      document.addEventListener("visibilitychange", function () { if (!document.hidden) { state = S.load(); render(); } });   // 돌아오면 다른 화면에서 바뀐 상태·날짜 반영
      window.addEventListener("storage", function (e) { if (!e.key || e.key === S.KEY) { state = S.load(); render(); } });
      render();
      scheduleMidnight();
    }).catch(function () { app.innerHTML = '<p class="text-sm text-ink-500">데이터를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.</p>'; });
  });
})();
