/* 서비스워커 템플릿 — scripts/build_site.py 가 버전 자리표시자와 PRECACHE 목록을 채워 루트 sw.js 로 만든다 (sw.js 는 생성 파일, 직접 고치지 않음).
 * 전략: 페이지·데이터는 네트워크 우선(실패 시 캐시, 페이지는 마지막에 offline.html), 해시가 붙은 자산은 캐시 우선,
 *       폰트 CDN 은 캐시 먼저 주고 뒤에서 갱신. 비-GET·분석·제휴 등 그 밖의 타 origin 요청은 손대지 않는다. */
var VERSION = "__VERSION__";
var PRECACHE = /*__PRECACHE__*/[];
var CACHE_STATIC = "static-" + VERSION, CACHE_PAGES = "pages-" + VERSION, CACHE_DATA = "data-" + VERSION, CACHE_FONTS = "fonts-v1";
var FONT_HOSTS = ["cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com"];
var OFFLINE_URL = "/offline.html";

/* 요청을 어떤 전략으로 다룰지 — "bypass" | "page" | "asset" | "data" | "font" (순수 함수, tests/sw.test.mjs 가 검증) */
function strategyFor(url, method, mode, origin) {
  if (method !== "GET") return "bypass";
  var u;
  try { u = new URL(url); } catch (e) { return "bypass"; }
  var same = u.origin === origin;
  if (mode === "navigate") return same ? "page" : "bypass";
  if (same) {
    if (u.pathname.indexOf("/assets/") === 0) return "asset";
    if (u.pathname.indexOf("/data/") === 0) return "data";
    return "bypass";
  }
  if (FONT_HOSTS.indexOf(u.hostname) >= 0) return "font";
  return "bypass";
}

function putIn(cacheName, request, response) {
  if (!response || !(response.ok || response.type === "opaque")) return response;
  var copy = response.clone();
  caches.open(cacheName).then(function (c) { c.put(request, copy); }).catch(function () {});
  return response;
}

function networkFirst(cacheName, request, fallback) {
  return fetch(request).then(function (res) { return putIn(cacheName, request, res); }).catch(function () {
    return caches.match(request).then(function (hit) { return hit || (fallback ? fallback() : Promise.reject(new Error("offline"))); });
  });
}

function cacheFirst(cacheName, request) {
  return caches.match(request).then(function (hit) {
    return hit || fetch(request).then(function (res) { return putIn(cacheName, request, res); });
  });
}

function staleWhileRevalidate(cacheName, request) {
  return caches.match(request).then(function (hit) {
    var refresh = fetch(request).then(function (res) { return putIn(cacheName, request, res); }).catch(function () { return hit; });
    return hit || refresh;
  });
}

if (typeof self !== "undefined" && self.addEventListener) {
  self.addEventListener("install", function (e) {
    e.waitUntil(caches.open(CACHE_STATIC).then(function (c) { return c.addAll(PRECACHE); }).then(function () { return self.skipWaiting(); }));
  });
  self.addEventListener("activate", function (e) {
    e.waitUntil(caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) {
        return /^(static|pages|data)-/.test(k) && k !== CACHE_STATIC && k !== CACHE_PAGES && k !== CACHE_DATA;
      }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); }));
  });
  self.addEventListener("fetch", function (e) {
    var req = e.request;
    var how = strategyFor(req.url, req.method, req.mode, self.location.origin);
    if (how === "bypass") return;
    if (how === "page") e.respondWith(networkFirst(CACHE_PAGES, req, function () { return caches.match(OFFLINE_URL); }));
    else if (how === "asset") e.respondWith(cacheFirst(CACHE_STATIC, req));
    else if (how === "data") e.respondWith(networkFirst(CACHE_DATA, req));
    else e.respondWith(staleWhileRevalidate(CACHE_FONTS, req));
  });
}

if (typeof module !== "undefined") module.exports = { strategyFor: strategyFor, VERSION: VERSION };
