/* 내 영양제 페이지 — 목록·검색 추가·시간대 변경·오늘 시간표·복용 기록·알림 설정·다른 기기로 옮기기.
   상태는 store.js(기기 내 localStorage)가 들고, 바뀔 때마다 통째로 다시 그린다(검색어·선택 날짜 같은 화면 상태만 모듈 변수로 유지). */
(function () {
  "use strict";
  var D = window.Data, S = window.Store, esc = D.esc;
  var core = null, state = null;
  var ui = { q: "", open: false, cursor: -1, focusSearch: false, selectedDay: null, notice: "", importPayload: null, exportOpen: false, importError: "", importPreview: null, importText: "" };

  function thumb(it, cls) {
    var I = window.Illus;
    return '<span class="thumb ' + (cls || "thumb-sm") + '" aria-hidden="true">' + (I && it ? I.bottle(I.labelFor(it), I.colorFor(it.category), { sub: it.name, id: it.id }) : "") + "</span>";
  }
  function ids() { return state.items.map(function (i) { return i.id; }); }
  function byId(id) { return core.byId[id]; }
  function defaultSlot(it) { return (it.timing && it.timing.slot) || "morning_after"; }
  function label(slot) { return S.SLOT_LABEL[slot] || slot; }
  function commit(next) { state = next; S.save(state); render(); }
  function toast(msg) {
    var t = document.createElement("div");
    t.className = "fixed bottom-36 left-1/2 z-50 -translate-x-1/2 rounded-full bg-ink-900 px-4 py-2 text-sm font-semibold text-white shadow-lg md:bottom-20";
    t.textContent = msg; document.body.appendChild(t); setTimeout(function () { t.remove(); }, 2200);
  }
  function schedule() {
    return state.items.length ? window.Schedule.build(ids(), core, S.overrides(state)) : { slots: [], notes: [] };
  }

  /* ---- 목록 + 검색 추가 ---- */
  function sectionList() {
    var rows = state.items.map(function (row) {
      var it = byId(row.id), d = defaultSlot(it);
      var opts = S.SLOT_ORDER.map(function (k) {
        return '<option value="' + k + '"' + ((row.slot || d) === k ? " selected" : "") + ">" + esc(label(k)) + (k === d ? " (기본)" : "") + "</option>";
      }).join("");
      return '<div class="my-item">' + thumb(it) +
        '<div class="my-item-main"><a href="' + D.ingredientUrl(it.id) + '">' + esc(it.name) + '</a><small>' + esc((it.timing && it.timing.label) || label(d)) + '</small></div>' +
        '<select class="my-slot" data-id="' + esc(it.id) + '" aria-label="' + esc(it.name) + ' 복용 시간대">' + opts + '</select>' +
        '<button type="button" class="my-icon-btn" data-remove="' + esc(it.id) + '" aria-label="' + esc(it.name) + ' 삭제"><i data-lucide="x"></i></button></div>';
    }).join("");
    var empty = '<div class="my-empty">아직 저장한 영양제가 없어요.<br>아래 검색창에서 성분을 추가하거나, <a class="font-semibold text-brand-700" href="compatibility.html">궁합 체크</a>에서 고른 성분을 한 번에 저장할 수 있어요.</div>';
    return '<section class="my-section" id="my-list"><h2><i data-lucide="pill"></i>먹고 있는 영양제 <span class="my-count">' + state.items.length + '개</span></h2>' +
      '<p class="my-sub">시간대는 성분의 일반적인 권장 시간이 기본이고, 직접 바꿀 수 있어요.</p>' +
      (rows || empty) +
      '<div class="my-search"><i data-lucide="search"></i><input id="my-search" type="text" autocomplete="off" role="combobox" aria-expanded="' + (ui.open ? "true" : "false") + '" aria-controls="my-search-list" placeholder="성분 이름으로 추가 (예: 마그네슘)" value="' + esc(ui.q) + '"><div id="my-search-list" role="listbox" aria-label="추가할 성분"></div></div>' +
      "</section>";
  }
  function searchHits() {
    return ui.q.trim() ? D.search(core.items, ui.q, 8) : [];
  }
  function renderSearchList() {
    var box = document.getElementById("my-search-list"), input = document.getElementById("my-search");
    if (!box) return;
    var hits = searchHits();
    if (!ui.open || !hits.length) { box.innerHTML = ""; box.className = ""; if (input) input.setAttribute("aria-expanded", "false"); return; }
    var have = {}; state.items.forEach(function (i) { have[i.id] = true; });
    box.className = "my-search-list";
    box.innerHTML = hits.map(function (it, i) {
      return '<button type="button" role="option" data-add="' + esc(it.id) + '" class="' + (i === ui.cursor ? "is-active " : "") + (have[it.id] ? "is-added" : "") + '" aria-selected="' + (i === ui.cursor ? "true" : "false") + '">' + thumb(it, "thumb-xs") + '<span>' + esc(it.name) + '</span><small>' + (have[it.id] ? "이미 있음" : esc(label(defaultSlot(it)))) + '</small></button>';
    }).join("");
    if (input) input.setAttribute("aria-expanded", "true");
    D.icons(box);
  }
  function add(id) {
    var r = S.addItems(state, [id]);
    ui.q = ""; ui.open = false; ui.cursor = -1; ui.focusSearch = true;
    if (!r.added.length) { toast("이미 내 영양제에 있어요"); render(); return; }
    commit(r.state);
    toast(byId(id).name + " 을(를) 추가했어요");
  }

  /* ---- 오늘 시간표 ---- */
  function sectionSchedule(sched) {
    if (!state.items.length) return "";
    var slots = sched.slots.map(function (s) {
      return '<div class="my-sched-slot"><div class="t"><span>' + esc(label(s.key)) + '</span><time>' + esc(state.settings.times[s.key] || "") + '</time></div><ul>' +
        s.items.map(function (it) { return '<li><a class="font-bold hover:text-brand-700" href="' + D.ingredientUrl(it.id) + '">' + esc(it.name) + '</a> <small>' + esc((it.timing && (it.timing.note || it.timing.label)) || "") + '</small></li>'; }).join("") + "</ul></div>";
    }).join("");
    var notes = sched.notes.length ? '<div class="mt-3 rounded-2xl border border-amber-200 bg-amber-50 p-4"><p class="text-sm font-bold text-amber-800">시간표 메모</p><ul class="list-warn mt-1 text-sm text-amber-900">' + sched.notes.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul></div>" : "";
    return '<section class="my-section" id="my-schedule"><h2><i data-lucide="calendar-check"></i>오늘 시간표</h2>' +
      '<p class="my-sub">시각은 아래 알림 설정에서 바꿀 수 있어요.</p><div class="my-sched">' + slots + "</div>" + notes +
      '<p class="mt-3 text-xs text-ink-400">각 성분의 일반적인 권장 시간과 간격 규칙을 바탕으로 자동 생성한 참고용 시간표입니다. 제품 라벨의 섭취 방법과 전문가 안내를 우선하세요.</p></section>';
  }

  /* ---- 복용 알림 설정 (예약 자체는 앱에서) ---- */
  function toggle(attr, value, checked, disabled, ariaLabel) {
    return '<input type="checkbox" class="my-toggle" ' + attr + '="' + esc(value) + '"' + (checked ? " checked" : "") + (disabled ? " disabled" : "") + ' aria-label="' + esc(ariaLabel) + '">';
  }
  function sectionReminders(sched) {
    if (!state.items.length) return "";
    var rows = sched.slots.map(function (s) {
      return '<div class="my-row"><div class="my-row-main"><b>' + esc(label(s.key)) + '</b><small>' + esc(s.items.map(function (it) { return D.shortName(it); }).join(" · ")) + '</small></div>' +
        '<input type="time" class="my-time" data-slot="' + s.key + '" value="' + esc(state.settings.times[s.key]) + '" aria-label="' + esc(label(s.key)) + ' 알림 시각">' +
        toggle("data-slot-on", s.key, state.settings.slotOn[s.key], false, label(s.key) + " 알림") + "</div>";
    }).join("");
    return '<section class="my-section" id="my-reminders"><h2><i data-lucide="bell"></i>복용 알림</h2>' +
      '<div class="my-row"><div class="my-row-main"><b>휴대폰 알림 받기</b><small>휴대폰 알림은 앱에서 받을 수 있어요 (앱 출시 준비 중). 시각을 미리 정해 두면 앱에서 그대로 쓰여요.</small></div>' + toggle("data-setting", "remindersOn", false, true, "휴대폰 알림 받기") + "</div>" +
      '<p class="my-sub" style="margin-top:.75rem">시간대별 알림 시각</p>' + rows +
      '<div class="my-row"><div class="my-row-main"><b>알림에 성분 이름 표시</b><small>끄면 "영양제 시간이에요"만 표시</small></div>' + toggle("data-setting", "showNames", state.settings.showNames, false, "알림에 성분 이름 표시") + "</div>" +
      '<div class="my-row"><div class="my-row-main"><b>주말에도 알림</b></div>' + toggle("data-setting", "weekends", state.settings.weekends, false, "주말에도 알림") + "</div>" +
      "</section>";
  }

  /* ---- 복용 기록: 처음 저장했을 때 한 번 묻고, 켜면 오늘 체크·연속 일수·7일/30일 보기 ---- */
  function today() { return S.dateKey(new Date()); }
  function sectionAskLog() {
    if (!state.items.length || state.settings.logEnabled !== null) return "";
    return '<section class="my-card" id="my-ask-log"><h3>복용 기록도 남길까요?</h3><p>시간대마다 \'먹었어요\'를 체크하고 연속 일수를 볼 수 있어요. 기록은 이 기기에만 남아요.</p>' +
      '<div class="my-actions"><button type="button" class="btn-primary btn-sm" data-log-enable="true">네, 남길게요</button><button type="button" class="btn-outline btn-sm" data-log-enable="false">아니요</button></div></section>';
  }
  function dayClass(key, t) {
    var st = S.dayStats(state, key);
    return "my-day" + (st.complete ? " is-complete" : st.done > 0 ? " is-partial" : "") + (key === t ? " is-today" : "") + (key === ui.selectedDay ? " is-selected" : "");
  }
  function sectionLog(sched) {
    if (!state.items.length || state.settings.logEnabled === null) return "";
    if (state.settings.logEnabled === false) {
      return '<section class="my-section" id="my-log"><h2><i data-lucide="circle-check"></i>복용 기록</h2><div class="my-row"><div class="my-row-main"><b>복용 기록은 꺼져 있어요</b><small>켜면 시간대별 체크와 연속 일수를 볼 수 있어요.</small></div><button type="button" class="btn-outline btn-sm" data-log-enable="true">켜기</button></div></section>';
    }
    var t = today(), st = S.dayStats(state, t), streak = S.streak(state, t);
    var checks = sched.slots.map(function (s) {
      var done = !!(state.log[t] && state.log[t].done[s.key]);
      return '<button type="button" class="my-check' + (done ? " is-done" : "") + '" data-check="' + s.key + '" aria-pressed="' + (done ? "true" : "false") + '"><span class="tick"><i data-lucide="check"></i></span><span><b>' + esc(label(s.key)) + ' <span class="my-muted">' + esc(state.settings.times[s.key]) + '</span></b><small>' + esc(s.items.map(function (it) { return D.shortName(it); }).join(" · ")) + '</small></span></button>';
    }).join("");
    var week = S.lastDays(t, 7).map(function (k) { return '<button type="button" class="' + dayClass(k, t) + '" data-day="' + k + '" aria-label="' + k + '"><span>' + (k === t ? "오늘" : k.slice(5).replace("-", "/")) + '</span><span class="dot"></span></button>'; }).join("");
    var month = S.lastDays(t, 30).map(function (k) { return '<button type="button" class="' + dayClass(k, t) + '" data-day="' + k + '" aria-label="' + k + '"><span>' + parseInt(k.slice(8), 10) + '</span><span class="dot"></span></button>'; }).join("");
    var detail = "";
    if (ui.selectedDay) {
      var day = state.log[ui.selectedDay];
      detail = '<div class="my-day-detail"><b>' + esc(ui.selectedDay) + '</b> · ' + (day && day.due.length ? day.due.map(function (k) { return (day.done[k] ? "✓ " : "— ") + esc(label(k)); }).join(" · ") : "기록 없음") + "</div>";
    }
    return '<section class="my-section" id="my-log"><h2><i data-lucide="circle-check"></i>복용 기록</h2>' +
      '<p class="my-stat">' + (st.due ? "오늘 " + st.due + "개 중 " + st.done + "개 챙겼어요" : "오늘 시간표에 영양제가 없어요") + ' <span>· 연속 ' + streak + '일</span></p>' +
      '<div class="my-checks">' + checks + "</div>" +
      '<p class="my-sub" style="margin-top:1rem">최근 7일</p><div class="my-days">' + week + "</div>" +
      '<p class="my-sub" style="margin-top:1rem">최근 30일</p><div class="my-days">' + month + "</div>" + detail +
      '<div class="my-actions"><button type="button" class="btn-outline btn-sm" data-log-enable="false">기록 끄기</button><button type="button" class="btn-outline btn-sm" data-log-clear>기록 지우기</button></div></section>';
  }
  function sectionTransfer() { return ""; }
  function sectionImport() { return ""; }

  function render() {
    var app = document.getElementById("my-app");
    var sched = schedule();
    if (state.settings.logEnabled === true) {   // 오늘 챙겨야 할 시간대를 기록해 두어야 체크·통계가 시간표를 따라간다
      var marked = S.markDue(state, today(), sched.slots.map(function (s) { return s.key; }));
      if (JSON.stringify(marked.log) !== JSON.stringify(state.log)) { state = marked; S.save(state); }
    }
    app.innerHTML = (ui.notice ? '<div class="my-notice">' + esc(ui.notice) + "</div>" : "") +
      sectionImport() + sectionAskLog() + sectionList() + sectionSchedule(sched) + sectionLog(sched) + sectionReminders(sched) + sectionTransfer();
    D.icons(app);
    renderSearchList();
    if (ui.focusSearch) { var inp = document.getElementById("my-search"); if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); } ui.focusSearch = false; }
  }

  function bind(app) {
    app.addEventListener("click", function (e) {
      var t = e.target.closest("[data-add],[data-remove],[data-log-enable],[data-check],[data-day],[data-log-clear]");
      if (!t) return;
      if (t.hasAttribute("data-add")) add(t.getAttribute("data-add"));
      else if (t.hasAttribute("data-remove")) { var id = t.getAttribute("data-remove"); commit(S.removeItem(state, id)); toast("삭제했어요"); }
      else if (t.hasAttribute("data-log-enable")) commit(S.setSetting(state, "logEnabled", t.getAttribute("data-log-enable") === "true"));
      else if (t.hasAttribute("data-check")) { var k = t.getAttribute("data-check"), tk = today(); commit(S.toggleDone(state, tk, k, !(state.log[tk] && state.log[tk].done[k]))); }
      else if (t.hasAttribute("data-day")) { var d = t.getAttribute("data-day"); ui.selectedDay = ui.selectedDay === d ? null : d; render(); }
      else if (t.hasAttribute("data-log-clear")) { if (window.confirm("복용 기록을 모두 지울까요?")) { ui.selectedDay = null; commit(S.clearLog(state)); toast("기록을 지웠어요"); } }
    });
    app.addEventListener("change", function (e) {
      var t = e.target;
      if (t.matches("select.my-slot")) { var it = byId(t.getAttribute("data-id")); commit(S.setSlot(state, it.id, t.value === defaultSlot(it) ? null : t.value)); }
      else if (t.matches("input.my-time")) { var next = S.setTime(state, t.getAttribute("data-slot"), t.value); if (next === state) { t.value = state.settings.times[t.getAttribute("data-slot")]; return; } commit(next); }
      else if (t.matches("input[data-slot-on]")) commit(S.setSlotOn(state, t.getAttribute("data-slot-on"), t.checked));
      else if (t.matches("input[data-setting]")) commit(S.setSetting(state, t.getAttribute("data-setting"), t.checked));
    });
    app.addEventListener("input", function (e) {
      if (e.target.id !== "my-search") return;
      ui.q = e.target.value; ui.open = true; ui.cursor = -1; renderSearchList();
    });
    app.addEventListener("focusin", function (e) { if (e.target.id === "my-search" && ui.q) { ui.open = true; renderSearchList(); } });
    app.addEventListener("keydown", function (e) {
      if (e.target.id !== "my-search") return;
      var hits = searchHits();
      if (e.key === "ArrowDown") { e.preventDefault(); ui.open = true; ui.cursor = Math.min(ui.cursor + 1, hits.length - 1); renderSearchList(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); ui.cursor = Math.max(ui.cursor - 1, -1); renderSearchList(); }
      else if (e.key === "Enter") { e.preventDefault(); var pick = hits[ui.cursor >= 0 ? ui.cursor : 0]; if (pick) add(pick.id); }
      else if (e.key === "Escape") { ui.open = false; renderSearchList(); }
    });
    document.addEventListener("click", function (e) { if (!e.target.closest(".my-search") && ui.open) { ui.open = false; renderSearchList(); } });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var app = document.getElementById("my-app");
    if (!app || !S) return;
    D.core().then(function (c) {
      core = c;
      state = S.load();
      var pr = S.pruneUnknown(state, core.byId);
      if (pr.removed.length) { state = pr.state; S.save(state); ui.notice = "성분 사전에서 사라진 항목 " + pr.removed.length + "개를 목록에서 뺐어요."; }
      bind(app);
      render();
    }).catch(function () { app.innerHTML = '<p class="text-sm text-ink-500">데이터를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.</p>'; });
  });
})();
