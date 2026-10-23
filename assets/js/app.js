/* 앱 모드 브리지 — Capacitor 네이티브(안드로이드·iOS 앱) 안에서 열렸는지 감지하고, 앱일 때만 Capacitor 런타임·플러그인 복사본
   (assets/js/vendor/capacitor/*.js, npm 에서 `npm run vendor:cap` 으로 복사)을 동적으로 싣는다. 웹 방문자에게는 이 파일 하나만 더해진다.
   로컬 확인: localhost 에서 주소에 ?app=1 을 붙이면 localStorage appDev=1 로 앱을 흉내 낸다(dev 모드, 런타임은 싣지 않음), ?app=0 으로 끈다. 운영 도메인에서는 무시.
   다른 스크립트는 window.AppBridge.isNative() 로 앱 모드를 묻고, 플러그인은 AppBridge.ready() 뒤 AppBridge.plugin("LocalNotifications") 로 얻는다.
   앱을 열 때 하던 일(웹뷰 저장소가 비면 Preferences 복제본에서 복원, 알림창의 우리 알림 정리, 알림 버튼 종류 등록, 알림이 켜져 있으면 한 번 동기화)은
   여기(ready → startup)서 모든 앱 화면에서 한다 — 시작 주소가 /today 라 내 영양제 페이지를 거치지 않아도 되게. 복원은 ready() 안에서 끝나므로
   페이지 스크립트는 AppBridge.ready() 뒤에 Store.load() 하면 복원된 상태를 읽는다. */
(function () {
  "use strict";
  var VENDOR = ["capacitor.js", "local-notifications.js", "preferences.js"];
  var VENDOR_VERSION = "8.5.3";   // app/package.json 의 @capacitor/core 버전 — `npm run vendor:cap` 이 함께 갱신. ?v= 로 실어 1년 캐시(_headers)·서비스워커를 무효화한다
  var state = { mode: null, ready: null, domReady: null };

  function isLocalHost(h) { return h === "localhost" || h === "127.0.0.1"; }

  /* "native" | "dev" | null — 순수 함수(tests/app.test.mjs) */
  function detect(win) {
    try {
      var cap = win.Capacitor;
      if (cap && typeof cap.isNativePlatform === "function" && cap.isNativePlatform()) return "native";
      var host = win.location && win.location.hostname;
      if (isLocalHost(host) && win.localStorage && win.localStorage.getItem("appDev") === "1") return "dev";
    } catch (e) { /* 저장소 차단 등 */ }
    return null;
  }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src; s.onload = resolve; s.onerror = function () { reject(new Error("load failed: " + src)); };
      document.head.appendChild(s);
    });
  }

  function init() {
    if (typeof window === "undefined" || typeof document === "undefined") return;
    try {
      var q = new URLSearchParams(window.location.search).get("app");
      if ((q === "1" || q === "0") && isLocalHost(window.location.hostname)) window.localStorage.setItem("appDev", q);
    } catch (e) { /* 무시 */ }
    state.mode = detect(window);
    state.domReady = waitForScripts(document);   // defer 스크립트 실행 중이라 DOMContentLoaded 가 아직 안 났다 — 여기서 만들어 둬야 놓치지 않는다
    if (!state.mode) { state.ready = Promise.resolve(); return; }
    document.documentElement.classList.add("is-app");
    var root0 = document.documentElement.getAttribute("data-root") || "./";
    if (coldStart(root0)) { state.ready = new Promise(function () {}); return; }   // 홈으로 이동 중 — 이 페이지의 스크립트는 더 진행하지 않는다
    if (!(window.SITE && window.SITE.appShopping)) document.documentElement.classList.add("app-noshop");   // 쇼핑 버튼·안내·고지 숨김(.app-hide), config.js 의 appShopping 으로 켬
    document.addEventListener("DOMContentLoaded", function () { document.body.classList.add("is-app"); });
    var root = document.documentElement.getAttribute("data-root") || "./";
    if (state.mode !== "native") { state.ready = Promise.resolve().then(function () { return restoreLocal(); }); return; }   // dev 모드도 같은 흐름(가짜 Preferences)
    state.ready = VENDOR.reduce(function (p, f) {
      return p.then(function () { return loadScript(root + "assets/js/vendor/capacitor/" + f + "?v=" + VENDOR_VERSION); });
    }, Promise.resolve()).catch(function (e) { if (window.console) console.warn("[app] 런타임 로드 실패:", e.message); })
      .then(function () { return restoreLocal(); });   // 복원까지 끝나야 ready
    state.ready.then(function () { listenNotifications(root); });
  }

  /* 웹뷰 저장소(localStorage)가 비어 있으면(재설치·백업 복원) 앱 저장소 복제본을 써 넣는다 — 순수 로직은 restoreIfEmpty(tests/app.test.mjs) */
  function restoreIfEmpty(env) {
    return Promise.resolve().then(function () {
      if (env.hasLocal()) return false;
      return Promise.resolve(env.restore()).then(function (json) { if (!json) return false; env.write(json); return true; });
    }).catch(function () { return false; });
  }
  /* defer 스크립트(store.js 등)가 모두 실행된 뒤(DOMContentLoaded)를 기다린다 — 순수(tests/app.test.mjs). defer 스크립트가 실행되는 동안
     readyState 는 이미 "interactive" 이므로 "loading" 검사로는 기다릴 수 없고, "complete" 가 아니면 DOMContentLoaded 를 기다려야 한다.
     init() 이 app.js 실행 시점(DOMContentLoaded 전)에 호출해 약속을 보관한다 */
  function waitForScripts(doc) {
    return new Promise(function (resolve) {
      if (doc.readyState === "complete") resolve();
      else doc.addEventListener("DOMContentLoaded", function () { resolve(); });
    });
  }
  function whenScripts() { return state.domReady || Promise.resolve(); }
  function restoreLocal() {
    return whenScripts().then(function () {
      if (!AppBridge.isNative()) return false;
      if (!window.Store) { if (window.console) console.warn("[app] store.js 가 없어 복원을 건너뜁니다"); return false; }
      var key = window.Store.KEY;
      return restoreIfEmpty({
        hasLocal: function () { return !!window.localStorage.getItem(key); },
        restore: function () { return AppBridge.restore(); },
        write: function (json) { window.localStorage.setItem(key, json); }
      });
    });
  }

  /* 앱 화면이 열릴 때마다: 채널 보장·알림 버튼 등록·알림창 정리(열 때와 돌아올 때)·알림이 켜져 있으면 한 번 동기화. 같은 페이지에서 한 번만 */
  var started = false;
  function startup() {
    if (started || !AppBridge.isNative()) return Promise.resolve();
    started = true;
    return AppBridge.ready().then(function () {
      var LN = AppBridge.plugin("LocalNotifications"), R = window.Reminders;
      if (!LN || !R) { started = false; return; }   // 플러그인이 아직 없으면(dev 모드에서 가짜를 나중에 넣는 경우) 다시 부를 수 있게
      R.ensureChannel(LN);
      if (LN.registerActionTypes) Promise.resolve(LN.registerActionTypes(R.actionTypes())).catch(function () { /* 무시 */ });
      var clear = function () { R.clearDelivered(LN).catch(function () { /* 무시 */ }); };
      clear();
      document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") clear(); });
      var st = window.Store ? window.Store.load() : null;
      if (st && st.settings && st.settings.remindersOn && window.Schedule && window.Data) return requestSync();
    }).catch(function (e) { if (window.console) console.warn("[app] 시작 처리 실패:", e && e.message); });
  }
  if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded", function () { startup(); });

  /* 앱 첫 실행(세션당 한 번): 옛 빌드는 시작 주소가 /my 라 내 영양제로 열리므로 홈(today.html)으로 보낸다 — 순수(tests/app.test.mjs).
     env = { native, page(data-page), started(sessionStorage yj.started), hash(location.hash+search) }. 가져오기 링크(#import=)는 그대로 둔다 */
  function coldStartTarget(env) {
    if (!env || !env.native || env.started) return null;
    if (/[?&#]import=/.test(env.hash || "")) return null;
    return env.page === "my" ? "today.html" : null;
  }
  function coldStart(root) {
    try {
      var ss = window.sessionStorage, started = !!ss.getItem("yj.started");
      var target = coldStartTarget({ native: true, page: document.body ? document.body.getAttribute("data-page") : "", started: started, hash: window.location.hash + window.location.search });
      if (!started) ss.setItem("yj.started", "1");
      if (target) { window.location.replace(root + target); return true; }
    } catch (e) { /* 저장소 차단 등 — 그대로 진행 */ }
    return false;
  }

  /* 알림 동작을 어디로 보낼지 — 순수 함수(tests/app.test.mjs). env.dispatch(detail) 가 true(내 영양제 페이지의 리스너가 받음)면 끝.
     아니면 env.store(detail) 로 보관하고(리스너가 아직 안 붙은 콜드 스타트도 여기), 내 영양제 페이지가 아니면 env.navigate() */
  function routeAction(detail, env) {
    if (env.dispatch(detail)) return;
    env.store(detail);
    if (env.page !== "my") env.navigate();
  }

  /* 알림 버튼·본문을 누른 이벤트는 어느 페이지에 있든 받는다(앱이 꺼져 있다가 열린 경우도 Capacitor 가 이벤트를 보존해 전달).
     내 영양제 페이지의 리스너(my.js)가 preventDefault 로 받았다고 알리면 끝, 아니면 sessionStorage 에 담아 둔다(my.js 가 열릴 때 처리) */
  function listenNotifications(root) {
    var LN = AppBridge.plugin("LocalNotifications");
    if (!LN || typeof LN.addListener !== "function") return;
    try {
      LN.addListener("localNotificationActionPerformed", function (ev) {
        var detail = { actionId: ev && ev.actionId, notification: ev && ev.notification, at: Date.now() };
        routeAction(detail, {
          page: document.body && document.body.getAttribute("data-page"),
          dispatch: function (d) { var e = new CustomEvent("yj:notification-action", { detail: d, cancelable: true }); window.dispatchEvent(e); return e.defaultPrevented; },
          store: function (d) { try { sessionStorage.setItem("yj.pendingAction", JSON.stringify(d)); } catch (e) { /* 무시 */ } },
          navigate: function () { window.location.href = root + "my.html"; }
        });
      });
    } catch (e) { /* 무시 */ }
  }

  /* 내 영양제 페이지 밖(성분 상세·가이드·궁합 체크)에서 목록이 바뀌었을 때 알림을 다시 예약하고 복제본을 갱신한다. 앱 모드가 아니면 아무것도 안 함 */
  function requestSync() {
    if (!AppBridge.isNative() || !window.Store || !window.Data) return Promise.resolve();
    var root = document.documentElement.getAttribute("data-root") || "./";
    var need = [];
    if (!window.Schedule) need.push("assets/js/schedule.js");
    if (!window.Reminders) need.push("assets/js/reminders.js");
    return AppBridge.ready().then(function () {
      return need.reduce(function (p, f) { return p.then(function () { return loadScript(root + f); }); }, Promise.resolve());
    }).then(function () {
      var st = window.Store.load();
      AppBridge.mirror(JSON.stringify(st));
      var LN = AppBridge.plugin("LocalNotifications");
      if (!LN || !st.settings.remindersOn || !window.Reminders || !window.Schedule) return;
      return window.Data.core().then(function (core) {
        var sched = window.Schedule.build(window.Store.entries(st), core, window.Store.overrides(st));
        return window.Reminders.sync(LN, st, sched, { shortName: window.Data.shortName });
      });
    }).catch(function (e) { if (window.console) console.warn("[app] 알림 재예약 실패:", e && e.message); });
  }

  var AppBridge = {
    detect: detect, routeAction: routeAction, coldStartTarget: coldStartTarget, requestSync: requestSync, restoreIfEmpty: restoreIfEmpty, waitForScripts: waitForScripts, startup: startup, VENDOR_VERSION: VENDOR_VERSION,
    mode: function () { return state.mode; },
    isNative: function () { return state.mode === "native" || state.mode === "dev"; },
    isReal: function () { return state.mode === "native"; },
    /* 앱 안에서 쇼핑 버튼·제휴 고지를 숨기는가 (config.js 의 SITE.appShopping 이 true 면 보임) */
    hideShopping: function () { return AppBridge.isNative() && !(window.SITE && window.SITE.appShopping); },
    ready: function () { return state.ready || Promise.resolve(); },
    /* dev 모드에서는 브라우저 검증용 가짜(window.__devPlugins)를, 아니면 Capacitor 플러그인 프록시 */
    plugin: function (name) {
      try {
        if (state.mode === "dev" && window.__devPlugins && window.__devPlugins[name]) return window.__devPlugins[name];
        if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins[name]) return window.Capacitor.Plugins[name];
      } catch (e) { /* 무시 */ }
      return null;
    },
    /* 내 영양제 상태를 앱 저장소(Preferences)에 복제 — 휴대폰 백업(Google·iCloud)에 실리고, 웹뷰 저장소가 비면 restore 로 되살린다 */
    mirror: function (json) {
      var P = AppBridge.plugin("Preferences");
      if (!P && state.mode === "dev") { try { window.localStorage.setItem("appDevBackup", json); } catch (e) { /* 무시 */ } return Promise.resolve(); }   // dev 모드: 가짜 앱 저장소(복원 확인용)
      if (!P || typeof P.set !== "function") return Promise.resolve();
      return Promise.resolve(P.set({ key: "yj.my.v1", value: json })).catch(function () { /* 무시 */ });
    },
    restore: function () {
      var P = AppBridge.plugin("Preferences");
      if (!P && state.mode === "dev") { try { return Promise.resolve(window.localStorage.getItem("appDevBackup") || null); } catch (e) { return Promise.resolve(null); } }
      if (!P || typeof P.get !== "function") return Promise.resolve(null);
      return Promise.resolve(P.get({ key: "yj.my.v1" })).then(function (r) { return r && r.value ? r.value : null; }).catch(function () { return null; });
    }
  };
  init();
  if (typeof window !== "undefined") window.AppBridge = AppBridge;
  if (typeof module !== "undefined") module.exports = AppBridge;
})();
