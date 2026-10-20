/* 서비스워커 템플릿 — scripts/build_site.py 가 버전 자리표시자와 PRECACHE 목록을 채워 루트 sw.js 로 만든다 (sw.js 는 생성 파일, 직접 고치지 않음).
 * 전략: 페이지·데이터는 네트워크 우선(실패 시 캐시, 페이지는 마지막에 offline.html), 해시가 붙은 자산은 캐시 우선,
 *       폰트 CDN 은 캐시 먼저 주고 뒤에서 갱신. 비-GET·분석·제휴 등 그 밖의 타 origin 요청은 손대지 않는다. */
var VERSION = "272bec53";
var PRECACHE = ["/assets/css/home.css?v=0fcbd58a", "/assets/css/style.css?v=e756c681", "/assets/css/tailwind.css?v=954102c6", "/assets/images/app/icon-192.png", "/assets/images/app/icon-512.png", "/assets/images/favicon.svg", "/assets/images/home/leaf.webp", "/assets/js/affiliate.js?v=c6a7ac59", "/assets/js/app.js?v=8ad18574", "/assets/js/config.js?v=ff071ff5", "/assets/js/data.js?v=126a3dae", "/assets/js/icons.js?v=216455ae", "/assets/js/illus.js?v=5c359cba", "/assets/js/layout.js?v=24a2bdc7", "/assets/js/pages/compat.js?v=71e67bcb", "/assets/js/pages/drug.js?v=4c33ab7c", "/assets/js/pages/guide.js?v=b73ccdc5", "/assets/js/pages/guides.js?v=d54796b6", "/assets/js/pages/home.js?v=17f7cdec", "/assets/js/pages/ingredient.js?v=df072a4a", "/assets/js/pages/ingredients.js?v=f46d23fd", "/assets/js/pages/materials.js?v=43386ab4", "/assets/js/pages/my.js?v=beb0f2e1", "/assets/js/pages/news.js?v=f44f5d89", "/assets/js/pages/product.js?v=24051298", "/assets/js/pages/products.js?v=fa77f681", "/assets/js/pages/search.js?v=56c7e406", "/assets/js/reminders.js?v=3514dc30", "/assets/js/schedule.js?v=3ed03c55", "/assets/js/store.js?v=e62cfa7a", "/assets/js/vendor/qrcode.js?v=4c79be16", "/my.html", "/offline.html"];
var CACHE_STATIC = "static-" + VERSION, CACHE_PAGES = "pages-" + VERSION, CACHE_DATA = "data-" + VERSION, CACHE_FONTS = "fonts-v1";
var FONT_HOSTS = ["cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com"];
var OFFLINE_URL = "/offline.html";

/* 요청을 어떤 전략으로 다룰지 — "bypass" | "page" | "asset"(?v= 해시 자산, 캐시 우선) | "revalidate"(해시 없는 자산, 캐시 먼저 주고 갱신) | "data" | "font"
   (순수 함수, tests/sw.test.mjs 가 검증). 매니페스트·sw.js 자체·분석·제휴 등 그 밖은 bypass */
function strategyFor(url, method, mode, origin) {
  if (method !== "GET") return "bypass";
  var u;
  try { u = new URL(url); } catch (e) { return "bypass"; }
  var same = u.origin === origin;
  if (mode === "navigate") return same ? "page" : "bypass";
  if (same) {
    if (u.pathname.indexOf("/assets/") === 0) return /(^|[?&])v=/.test(u.search) ? "asset" : "revalidate";
    if (u.pathname.indexOf("/data/") === 0) return "data";
    return "bypass";
  }
  if (FONT_HOSTS.indexOf(u.hostname) >= 0) return "font";
  return "bypass";
}

/* 캐시에서 찾아볼 주소 후보 — Cloudflare Pages 는 /foo.html 을 /foo 로(/index.html 은 /) 리다이렉트해 최종 페이지가 확장자 없는 키로 저장되므로,
   내부 링크(.html)로 다시 올 때 확장자 없는 키도 찾는다 (순수 함수) */
function cacheKeyCandidates(url) {
  var out = [url], u;
  try { u = new URL(url); } catch (e) { return out; }
  if (/\.html$/.test(u.pathname)) {
    var p = /\/index\.html$/.test(u.pathname) ? u.pathname.replace(/index\.html$/, "") : u.pathname.replace(/\.html$/, "");
    out.push(u.origin + p + u.search);
  }
  return out;
}

/* 리다이렉트를 거쳐 받은 응답(redirected=true)은 페이지 이동 요청에 그대로 돌려줄 수 없어 새 Response 로 감싼다 (순수 함수) */
function stripRedirect(res) {
  if (!res || !res.redirected) return res;
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: res.headers });
}

function matchAny(request) {
  var keys = cacheKeyCandidates(typeof request === "string" ? request : request.url);
  return keys.reduce(function (p, k) { return p.then(function (hit) { return hit || caches.match(k); }); }, Promise.resolve(null));
}

function putIn(cacheName, request, response) {
  if (!response || !(response.ok || response.type === "opaque")) return response;
  var copy = response.clone();
  caches.open(cacheName).then(function (c) { c.put(request, copy); }).catch(function () {});
  return response;
}

function networkFirst(cacheName, request, fallback) {
  return fetch(request).then(function (res) { return putIn(cacheName, request, res); }).catch(function () {
    return matchAny(request).then(function (hit) {
      if (hit) return stripRedirect(hit);
      return fallback ? fallback() : Response.error();
    });
  });
}

function cacheFirst(cacheName, request) {
  return caches.match(request).then(function (hit) {
    return hit || fetch(request).then(function (res) { return putIn(cacheName, request, res); });
  });
}

function staleWhileRevalidate(cacheName, request) {
  return caches.match(request).then(function (hit) {
    var refresh = fetch(request).then(function (res) { return putIn(cacheName, request, res); }).catch(function () { return hit || Response.error(); });
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
    if (how === "page") e.respondWith(networkFirst(CACHE_PAGES, req, function () { return caches.match(OFFLINE_URL).then(function (hit) { return hit ? stripRedirect(hit) : Response.error(); }); }));
    else if (how === "asset") e.respondWith(cacheFirst(CACHE_STATIC, req));
    else if (how === "revalidate") e.respondWith(staleWhileRevalidate(CACHE_STATIC, req));
    else if (how === "data") e.respondWith(networkFirst(CACHE_DATA, req));
    else e.respondWith(staleWhileRevalidate(CACHE_FONTS, req));
  });
}

if (typeof module !== "undefined") module.exports = { strategyFor: strategyFor, cacheKeyCandidates: cacheKeyCandidates, stripRedirect: stripRedirect, VERSION: VERSION };
