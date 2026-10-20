/* 앱 모드 브리지 — Capacitor 네이티브(안드로이드 앱) 안에서 열렸는지 감지하고, 앱일 때만 Capacitor 런타임·플러그인 복사본
   (assets/js/vendor/capacitor/*.js, npm 에서 `npm run vendor:cap` 으로 복사)을 동적으로 싣는다. 웹 방문자에게는 이 파일 하나만 더해진다.
   로컬 확인: localhost 에서 주소에 ?app=1 을 붙이면 localStorage appDev=1 로 앱을 흉내 낸다(dev 모드, 런타임은 싣지 않음), ?app=0 으로 끈다. 운영 도메인에서는 무시.
   다른 스크립트는 window.AppBridge.isNative() 로 앱 모드를 묻고, 플러그인은 AppBridge.ready() 뒤 AppBridge.plugin("LocalNotifications") 로 얻는다. */
(function () {
  "use strict";
  var VENDOR = ["capacitor.js", "local-notifications.js", "preferences.js"];
  var state = { mode: null, ready: null };

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
    if (!state.mode) { state.ready = Promise.resolve(); return; }
    document.documentElement.classList.add("is-app");
    if (!(window.SITE && window.SITE.appShopping)) document.documentElement.classList.add("app-noshop");   // 쇼핑 버튼·안내·고지 숨김(.app-hide), config.js 의 appShopping 으로 켬
    document.addEventListener("DOMContentLoaded", function () { document.body.classList.add("is-app"); });
    var root = document.documentElement.getAttribute("data-root") || "./";
    if (state.mode !== "native") { state.ready = Promise.resolve(); return; }
    state.ready = VENDOR.reduce(function (p, f) {
      return p.then(function () { return loadScript(root + "assets/js/vendor/capacitor/" + f); });
    }, Promise.resolve()).catch(function (e) { if (window.console) console.warn("[app] 런타임 로드 실패:", e.message); });
    state.ready.then(function () { listenNotifications(root); });
  }

  /* 알림 버튼·본문을 누른 이벤트는 어느 페이지에 있든 받아서, 내 영양제 페이지면 DOM 이벤트(yj:notification-action)로 넘기고
     다른 페이지면 sessionStorage 에 담아 내 영양제 페이지로 이동한다(앱이 꺼져 있다가 열린 경우도 Capacitor 가 이벤트를 보존해 전달). */
  function listenNotifications(root) {
    var LN = AppBridge.plugin("LocalNotifications");
    if (!LN || typeof LN.addListener !== "function") return;
    try {
      LN.addListener("localNotificationActionPerformed", function (ev) {
        var detail = { actionId: ev && ev.actionId, notification: ev && ev.notification, at: Date.now() };
        var page = document.body && document.body.getAttribute("data-page");
        if (page === "my") { window.dispatchEvent(new CustomEvent("yj:notification-action", { detail: detail })); return; }
        try { sessionStorage.setItem("yj.pendingAction", JSON.stringify(detail)); } catch (e) { /* 무시 */ }
        window.location.href = root + "my.html";
      });
    } catch (e) { /* 무시 */ }
  }

  var AppBridge = {
    detect: detect,
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
      if (!P || typeof P.set !== "function") return Promise.resolve();
      return Promise.resolve(P.set({ key: "yj.my.v1", value: json })).catch(function () { /* 무시 */ });
    },
    restore: function () {
      var P = AppBridge.plugin("Preferences");
      if (!P || typeof P.get !== "function") return Promise.resolve(null);
      return Promise.resolve(P.get({ key: "yj.my.v1" })).then(function (r) { return r && r.value ? r.value : null; }).catch(function () { return null; });
    }
  };
  init();
  if (typeof window !== "undefined") window.AppBridge = AppBridge;
  if (typeof module !== "undefined") module.exports = AppBridge;
})();
