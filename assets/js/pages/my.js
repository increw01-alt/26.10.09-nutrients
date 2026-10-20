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
  /* ---- 앱(Capacitor) 연동: 알림 예약은 앱에서만. 웹에서는 AppBridge 가 없거나 isNative() 가 false ---- */
  function isApp() { return !!(window.AppBridge && window.AppBridge.isNative()); }
  function LN() { return isApp() ? window.AppBridge.plugin("LocalNotifications") : null; }
  var syncTimer = null;
  function scheduleSync() {   // 설정·목록이 바뀔 때마다 300ms 뒤 한 번만 재예약 (끄면 취소만)
    var ln = LN(); if (!ln || !window.Reminders) return;
    clearTimeout(syncTimer);
    syncTimer = setTimeout(function () {
      window.Reminders.sync(ln, state, schedule(), { shortName: D.shortName }).catch(function (e) { if (window.console) console.warn("[reminders] 동기화 실패:", e && e.message); });
    }, 300);
  }
  function commit(next) {
    state = next; S.save(state); render();
    if (isApp()) { window.AppBridge.mirror(JSON.stringify(state)); scheduleSync(); }
  }
  /* 토글을 켤 때: 권한을 먼저 받고, 거부면 토글을 되돌리며 안내 */
  function enableReminders(input) {
    var ln = LN();
    if (!ln) { input.checked = false; ui.notice = "휴대폰 알림은 앱에서만 받을 수 있어요."; render(); return; }
    Promise.resolve(ln.requestPermissions()).then(function (r) {
      if (r && r.display === "granted") { ui.notice = ""; commit(S.setSetting(state, "remindersOn", true)); }
      else { ui.notice = "알림 권한이 꺼져 있어요. 휴대폰 설정 → 앱 → 영양제.kr → 알림에서 켜 주세요."; commit(S.setSetting(state, "remindersOn", false)); }
    }).catch(function () { ui.notice = "알림을 켜지 못했어요. 잠시 뒤 다시 시도해 주세요."; commit(S.setSetting(state, "remindersOn", false)); });
  }
  /* 알림의 버튼(먹었어요·30분 뒤 다시)이나 본체를 눌렀을 때. app.js 가 모든 페이지에서 받아 이 페이지면 DOM 이벤트로, 다른 페이지면
     sessionStorage 에 담아 넘어온다. 날짜는 누른 시각(at) 기준이라 자정을 넘겨 처리돼도 그날 기록으로 남는다 */
  function onNotificationAction(ev) {
    var when = ev && ev.at ? S.dateKey(new Date(ev.at)) : today();
    var r = window.Reminders.applyAction(state, ev, dueSlots(schedule()), when);
    if (r.snooze) {
      var slot = r.snooze, s = schedule().slots.filter(function (x) { return x.key === slot; })[0];
      var body = s ? s.items.map(function (it) { return D.shortName(it); }).join(" · ") : "";
      var ln = LN();
      if (ln) Promise.resolve(ln.schedule({ notifications: [window.Reminders.snoozeNotification(slot, Date.now(), { shortName: D.shortName }, body, state.settings.logEnabled === true)] })).catch(function () { /* 무시 */ });
    }
    if (r.state !== state) commit(r.state); else render();
    if (r.open) window.scrollTo(0, 0);
  }
  function initAppReminders() {
    if (!isApp() || !window.Reminders) return;
    window.addEventListener("yj:notification-action", function (e) { onNotificationAction(e.detail); });
    var pending = null;
    try { pending = JSON.parse(sessionStorage.getItem("yj.pendingAction") || "null"); sessionStorage.removeItem("yj.pendingAction"); } catch (e) { /* 무시 */ }
    if (pending) onNotificationAction(pending);
    var ln = LN(); if (!ln) return;
    if (ln.registerActionTypes) Promise.resolve(ln.registerActionTypes(window.Reminders.actionTypes())).catch(function () { /* 무시 */ });
    if (state.settings.remindersOn) scheduleSync();   // 시간표가 바뀌어 있을 수 있으니 열 때 한 번 맞춘다
  }
  function toast(msg) {
    var t = document.createElement("div");
    t.className = "fixed bottom-36 left-1/2 z-50 -translate-x-1/2 rounded-full bg-ink-900 px-4 py-2 text-sm font-semibold text-white shadow-lg md:bottom-20";
    t.textContent = msg; document.body.appendChild(t); setTimeout(function () { t.remove(); }, 2200);
  }
  function schedule() {
    return state.items.length ? window.Schedule.build(ids(), core, S.overrides(state)) : { slots: [], notes: [] };
  }

  /* ---- 목록 + 검색 추가 ---- */
  function sectionList(sched) {
    var rows = state.items.map(function (row) {
      var it = byId(row.id), d = defaultSlot(it), actual = (sched.assign && sched.assign[row.id]) || d;
      /* 값 "" = 자동(권장 시간대 + 간격 규칙으로 배정, 현재 배정을 함께 표시). 사용자가 고른 시간대는 기본값과 같아도 그대로 저장해 자동 이동하지 않게 한다 */
      var opts = '<option value=""' + (row.slot ? "" : " selected") + '>자동 · ' + esc(label(actual)) + "</option>" + S.SLOT_ORDER.map(function (k) {
        return '<option value="' + k + '"' + (row.slot === k ? " selected" : "") + ">" + esc(label(k)) + (k === d ? " (권장)" : "") + "</option>";
      }).join("");
      return '<div class="my-item">' + thumb(it) +
        '<div class="my-item-main"><a href="' + D.ingredientUrl(it.id) + '">' + esc(it.name) + '</a><small>' + esc((it.timing && it.timing.label) || label(d)) + '</small></div>' +
        '<select class="my-slot" data-id="' + esc(it.id) + '" aria-label="' + esc(it.name) + ' 복용 시간대">' + opts + '</select>' +
        '<button type="button" class="my-icon-btn" data-remove="' + esc(it.id) + '" aria-label="' + esc(it.name) + ' 삭제"><i data-lucide="x"></i></button></div>';
    }).join("");
    var empty = '<div class="my-empty">아직 저장한 영양제가 없어요.<br>아래 검색창에서 성분을 추가하거나, <a class="font-semibold text-brand-700" href="compatibility.html">궁합 체크</a>에서 고른 성분을 한 번에 저장할 수 있어요.</div>';
    return '<section class="my-section" id="my-list"><h2><i data-lucide="pill"></i>먹고 있는 영양제 <span class="my-count">' + state.items.length + '개</span></h2>' +
      '<p class="my-sub">시간대는 성분의 권장 시간과 궁합 간격 규칙으로 자동 배정돼요. 직접 고르면 그 시간대로 고정됩니다.</p>' +
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
      return '<div class="my-sched-slot"><div class="t"><span>' + esc(label(s.key)) + '</span><time data-slot="' + s.key + '">' + esc(state.settings.times[s.key] || "") + '</time></div><ul>' +
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
      (isApp()
        ? '<div class="my-row"><div class="my-row-main"><b>휴대폰 알림 받기</b><small>알림은 이 휴대폰에서 울려요. 시각을 바꾸면 바로 다시 예약돼요.</small></div>' + toggle("data-setting", "remindersOn", state.settings.remindersOn, false, "휴대폰 알림 받기") + "</div>"
        : '<div class="my-row"><div class="my-row-main"><b>휴대폰 알림 받기</b><small>휴대폰 알림은 앱에서 받을 수 있어요 (앱 출시 준비 중). 시각을 미리 정해 두면 앱에서 그대로 쓰여요.</small></div>' + toggle("data-setting", "remindersOn", false, true, "휴대폰 알림 받기") + "</div>") +
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
      return '<button type="button" class="my-check' + (done ? " is-done" : "") + '" data-check="' + s.key + '" aria-pressed="' + (done ? "true" : "false") + '"><span class="tick"><i data-lucide="check"></i></span><span><b>' + esc(label(s.key)) + ' <span class="my-muted" data-time-slot="' + s.key + '">' + esc(state.settings.times[s.key]) + '</span></b><small>' + esc(s.items.map(function (it) { return D.shortName(it); }).join(" · ")) + '</small></span></button>';
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
  /* ---- 다른 기기로 옮기기: 링크·QR·텍스트 코드 내보내기, 가져오기(합치기/바꾸기). 기록은 포함하지 않는다 ---- */
  function baseUrl() { return location.origin + location.pathname.replace(/[^/]*$/, ""); }
  function qrSvg(text) {
    try { var q = window.qrcode(0, "M"); q.addData(text); q.make(); return q.createSvgTag({ cellSize: 4, margin: 2, scalable: true }); } catch (e) { return ""; }
  }
  function previewCard(payload, source) {
    var known = payload.items.filter(function (it) { return byId(it.id); }), unknown = payload.items.length - known.length;
    return '<section class="my-card" id="' + (source === "url" ? "my-import" : "my-import-preview") + '"><h3>' + (source === "url" ? "링크로 받은 내 영양제 목록" : "가져올 목록") + '</h3>' +
      '<p>' + (known.length ? esc(known.map(function (it) { return byId(it.id).name; }).join(", ")) + " (" + known.length + "개)" : "가져올 수 있는 성분이 없어요") + (unknown ? ' · 모르는 항목 ' + unknown + '개는 건너뜁니다' : "") + "</p>" +
      '<p class="my-muted">합치기는 지금 목록을 유지하고 새 성분만 더하고, 바꾸기는 가져온 목록으로 교체해요. 복용 기록은 그대로 둡니다.</p>' +
      '<div class="my-actions"><button type="button" class="btn-primary btn-sm" data-import-apply="merge" data-import-source="' + source + '"' + (known.length ? "" : " disabled") + '>합치기</button><button type="button" class="btn-outline btn-sm" data-import-apply="replace" data-import-source="' + source + '"' + (known.length ? "" : " disabled") + '>바꾸기</button><button type="button" class="btn-outline btn-sm" data-import-cancel="' + source + '">취소</button></div></section>';
  }
  function sectionImport() { return ui.importPayload ? previewCard(ui.importPayload, "url") : ""; }
  function sectionTransfer() {
    var exportPanel = "";
    if (ui.exportOpen && state.items.length) {
      var code = S.exportCode(state), url = S.exportUrl(code, baseUrl());
      exportPanel = '<div class="my-field"><label for="my-export-url">링크 (열면 바로 가져오기)</label><div class="my-copy"><input id="my-export-url" type="text" readonly value="' + esc(url) + '"><button type="button" class="btn-outline btn-sm" data-copy="my-export-url">복사</button></div></div>' +
        '<div class="my-qr" aria-label="가져오기 링크 QR 코드">' + qrSvg(url) + "</div>" +
        '<div class="my-field"><label for="my-export-code">텍스트 코드 (앱의 가져오기 칸에 붙여넣기)</label><div class="my-copy"><textarea id="my-export-code" readonly>' + esc(code) + '</textarea><button type="button" class="btn-outline btn-sm" data-copy="my-export-code">복사</button></div></div>';
    }
    return '<section class="my-section" id="my-transfer"><h2><i data-lucide="arrow-right"></i>다른 기기로 옮기기</h2>' +
      '<p class="my-sub">내 영양제 목록과 알림 설정을 링크·QR·텍스트 코드로 옮길 수 있어요. 복용 기록은 포함되지 않습니다.</p>' +
      '<div class="my-actions"><button type="button" class="btn-primary btn-sm" data-export-open' + (state.items.length ? "" : " disabled") + '>' + (ui.exportOpen ? "내보내기 닫기" : "내보내기") + "</button></div>" + exportPanel +
      '<div class="my-field"><label for="my-import-text">가져오기 — 링크나 텍스트 코드를 붙여넣기</label><div class="my-copy"><textarea id="my-import-text" placeholder="YJ1-… 또는 my.html?import=… 링크">' + esc(ui.importText) + '</textarea><button type="button" class="btn-outline btn-sm" data-import-parse>불러오기</button></div>' +
      (ui.importError ? '<p class="my-error">' + esc(ui.importError) + "</p>" : "") + "</div>" +
      (ui.importPreview ? previewCard(ui.importPreview, "text") : "") + "</section>";
  }
  function applyImport(payload, mode, source) {
    var r = S.merge(state, payload, mode, core.byId);
    if (source === "url") ui.importPayload = null;
    else { ui.importPreview = null; ui.importText = ""; }
    commit(r.state);
    toast((mode === "replace" ? "목록을 바꿨어요" : r.added.length + "개 추가했어요") + (r.skipped.length ? " · " + r.skipped.length + "개 건너뜀" : ""));
  }
  function copyFrom(id) {
    var el = document.getElementById(id); if (!el) return;
    var text = el.value;
    var done = function () { toast("복사했어요"); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done).catch(function () { el.select(); toast("길게 눌러 복사하세요"); });
    else { el.select(); try { document.execCommand("copy"); done(); } catch (e) { toast("길게 눌러 복사하세요"); } }
  }

  /* 다시 그린 뒤에도 키보드 포커스를 잃지 않도록, 포커스된 요소를 id 또는 data-* 조합으로 기억했다가 되찾는다 */
  var FOCUS_ATTRS = ["data-id", "data-slot", "data-slot-on", "data-setting", "data-check", "data-day", "data-remove", "data-add", "data-log-enable", "data-import-apply", "data-copy"];
  function focusKey(el) {
    if (!el || el === document.body) return null;
    if (el.id) return "#" + el.id;
    for (var i = 0; i < FOCUS_ATTRS.length; i++) if (el.hasAttribute(FOCUS_ATTRS[i])) return "[" + FOCUS_ATTRS[i] + '="' + el.getAttribute(FOCUS_ATTRS[i]) + '"]';
    return null;
  }
  function dueSlots(sched) { return sched.slots.map(function (s) { return s.key; }); }
  function render() {
    var app = document.getElementById("my-app");
    var sched = schedule();
    var tk = today();
    if (state.settings.logEnabled === true) {   // 오늘 챙겨야 할 시간대를 기록해 두어야 체크·통계가 시간표를 따라간다
      var marked = S.markDue(state, tk, dueSlots(sched));
      if (JSON.stringify(marked.log) !== JSON.stringify(state.log)) { state = marked; S.save(state); }
    }
    var keep = focusKey(document.activeElement);
    app.innerHTML = (ui.notice ? '<div class="my-notice">' + esc(ui.notice) + "</div>" : "") +
      sectionImport() + sectionAskLog() + sectionList(sched) + sectionSchedule(sched) + sectionLog(sched) + sectionReminders(sched) + sectionTransfer();
    ui.renderedDay = tk;
    D.icons(app);
    renderSearchList();
    if (ui.focusSearch) { var inp = document.getElementById("my-search"); if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); } ui.focusSearch = false; }
    else if (keep) { var again = app.querySelector(keep); if (again) again.focus(); }
  }

  function bind(app) {
    app.addEventListener("click", function (e) {
      var t = e.target.closest("[data-add],[data-remove],[data-log-enable],[data-check],[data-day],[data-log-clear],[data-export-open],[data-copy],[data-import-parse],[data-import-apply],[data-import-cancel]");
      if (!t) return;
      if (t.hasAttribute("data-export-open")) { ui.exportOpen = !ui.exportOpen; render(); return; }
      if (t.hasAttribute("data-copy")) { copyFrom(t.getAttribute("data-copy")); return; }
      if (t.hasAttribute("data-import-parse")) {
        var ta = document.getElementById("my-import-text"); ui.importText = ta ? ta.value : "";
        var p = S.importCode(ui.importText);
        ui.importError = p ? "" : "코드를 읽을 수 없어요. 링크 전체나 YJ1- 로 시작하는 코드를 붙여넣어 주세요."; ui.importPreview = p; render(); return;
      }
      if (t.hasAttribute("data-import-apply")) { var src = t.getAttribute("data-import-source"); applyImport(src === "url" ? ui.importPayload : ui.importPreview, t.getAttribute("data-import-apply"), src); return; }
      if (t.hasAttribute("data-import-cancel")) {
        if (t.getAttribute("data-import-cancel") === "url") ui.importPayload = null;
        else { ui.importPreview = null; ui.importError = ""; }
        render(); return;
      }
      if (t.hasAttribute("data-add")) add(t.getAttribute("data-add"));
      else if (t.hasAttribute("data-remove")) { var id = t.getAttribute("data-remove"); commit(S.removeItem(state, id)); toast("삭제했어요"); }
      else if (t.hasAttribute("data-log-enable")) commit(S.setSetting(state, "logEnabled", t.getAttribute("data-log-enable") === "true"));
      else if (t.hasAttribute("data-check")) {   // 자정을 넘긴 채 열려 있던 화면에서도 체크가 사라지지 않게, 오늘 due 를 먼저 기록한다
        var k = t.getAttribute("data-check"), tk = today();
        var fresh = S.markDue(state, tk, dueSlots(schedule()));
        commit(S.toggleDone(fresh, tk, k, !(fresh.log[tk] && fresh.log[tk].done[k])));
      }
      else if (t.hasAttribute("data-day")) { var d = t.getAttribute("data-day"); ui.selectedDay = ui.selectedDay === d ? null : d; render(); }
      else if (t.hasAttribute("data-log-clear")) { if (window.confirm("복용 기록을 모두 지울까요?")) { ui.selectedDay = null; commit(S.clearLog(state)); toast("기록을 지웠어요"); } }
    });
    app.addEventListener("change", function (e) {
      var t = e.target;
      if (t.matches("select.my-slot")) commit(S.setSlot(state, t.getAttribute("data-id"), t.value || null));   // "" = 자동
      else if (t.matches("input.my-time")) {   // 시각은 입력 중 끊기지 않도록 다시 그리지 않고 저장만 하고, 시간표의 시각 표시만 바꾼다
        var slot = t.getAttribute("data-slot"), next = S.setTime(state, slot, t.value);
        if (next === state) { t.value = state.settings.times[slot]; return; }
        state = next; S.save(state);
        document.querySelectorAll('#my-schedule time[data-slot="' + slot + '"], #my-log [data-time-slot="' + slot + '"]').forEach(function (el) { el.textContent = t.value; });
        if (isApp()) { window.AppBridge.mirror(JSON.stringify(state)); scheduleSync(); }   // 시각이 바뀌면 알림도 다시 예약
      }
      else if (t.matches("input[data-slot-on]")) commit(S.setSlotOn(state, t.getAttribute("data-slot-on"), t.checked));
      else if (t.matches('input[data-setting="remindersOn"]')) { if (t.checked) enableReminders(t); else { ui.notice = ""; commit(S.setSetting(state, "remindersOn", false)); } }
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
      return (window.AppBridge ? window.AppBridge.ready() : Promise.resolve()).then(function () { return c; });   // 앱이면 런타임 로드를 기다린다
    }).then(function (c) {
      core = c;
      state = S.load();
      var hasLocal = false;
      try { hasLocal = !!localStorage.getItem(S.KEY); } catch (e) { /* 무시 */ }
      if (isApp() && !hasLocal) {   // 웹뷰 저장소가 비어 있으면(재설치·백업 복원) 앱 저장소 복제본에서 되살린다
        return window.AppBridge.restore().then(function (json) { if (json) { state = S.load({ getItem: function () { return json; } }); S.save(state); } return c; });
      }
      return c;
    }).then(function (c) {
      var pr = S.pruneUnknown(state, core.byId);
      if (pr.removed.length) { state = pr.state; S.save(state); ui.notice = "성분 사전에서 사라진 항목 " + pr.removed.length + "개를 목록에서 뺐어요."; }
      /* 가져오기 링크(#import=, 옛 ?import=)는 읽자마자 주소에서 지운다 — 목록이 주소에 남아 공유·기록되지 않게.
         이미 열린 페이지에서 조각만 바뀌는 이동(hashchange)도 같은 길로 처리한다 */
      function readImportFromUrl() {
        if (!/[?&#]import=/.test(location.hash + location.search)) return false;
        var imp = null;
        try { imp = S.importCode(location.href); } catch (e) { /* 무시 */ }
        try { history.replaceState(null, "", location.pathname); } catch (e) { /* 무시 */ }
        if (imp) ui.importPayload = imp; else ui.notice = "가져오기 링크의 코드를 읽을 수 없어요.";
        return true;
      }
      readImportFromUrl();
      window.addEventListener("hashchange", function () { if (readImportFromUrl()) { state = S.load(); render(); } });
      app.addEventListener("input", function (e) { if (e.target.id === "my-import-text") ui.importText = e.target.value; });
      document.addEventListener("visibilitychange", function () { if (!document.hidden && ui.renderedDay && ui.renderedDay !== today()) render(); });   // 자정을 넘겨 다시 열면 오늘 기준으로
      bind(app);
      render();
      initAppReminders();
    }).catch(function () { app.innerHTML = '<p class="text-sm text-ink-500">데이터를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.</p>'; });
  });
})();
