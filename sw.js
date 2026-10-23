/* 서비스워커 템플릿 — scripts/build_site.py 가 버전 자리표시자와 PRECACHE 목록을 채워 루트 sw.js 로 만든다 (sw.js 는 생성 파일, 직접 고치지 않음).
 * 전략: 페이지·데이터는 네트워크 우선(실패 시 캐시, 페이지는 마지막에 offline.html), 해시가 붙은 자산은 캐시 우선,
 *       폰트 CDN 은 캐시 먼저 주고 뒤에서 갱신. 비-GET·분석·제휴 등 그 밖의 타 origin 요청은 손대지 않는다. */
var VERSION = "64743b88";
var PRECACHE = ["/assets/css/home.css?v=0fcbd58a", "/assets/css/style.css?v=f8f0b23b", "/assets/css/tailwind.css?v=dbefc331", "/assets/images/app/icon-192.png", "/assets/images/app/icon-512.png", "/assets/images/favicon.svg", "/assets/images/home/leaf.webp", "/assets/js/addsummary.js?v=c7404eef", "/assets/js/affiliate.js?v=b9120cbd", "/assets/js/app.js?v=46c46444", "/assets/js/config.js?v=b696f061", "/assets/js/data.js?v=cbda636e", "/assets/js/finder.js?v=07cd4814", "/assets/js/icons.js?v=e1a00ddb", "/assets/js/illus.js?v=5c359cba", "/assets/js/layout.js?v=5722d440", "/assets/js/pages/compare.js?v=25a9f607", "/assets/js/pages/compat.js?v=a8d86aa9", "/assets/js/pages/drug.js?v=7179d999", "/assets/js/pages/finder.js?v=51d756e9", "/assets/js/pages/glossary.js?v=2fe1b07d", "/assets/js/pages/guide.js?v=b73ccdc5", "/assets/js/pages/guides.js?v=d54796b6", "/assets/js/pages/home.js?v=5c681484", "/assets/js/pages/ingredient.js?v=57101d63", "/assets/js/pages/ingredients.js?v=66d77039", "/assets/js/pages/materials.js?v=43386ab4", "/assets/js/pages/my.js?v=5a5ea89c", "/assets/js/pages/news.js?v=f44f5d89", "/assets/js/pages/product.js?v=2cf50fd4", "/assets/js/pages/products.js?v=fa77f681", "/assets/js/pages/recommend.js?v=a4f9bc2e", "/assets/js/pages/search.js?v=6d8aec19", "/assets/js/pages/today.js?v=f028b8f0", "/assets/js/reminders.js?v=58008f0d", "/assets/js/schedule.js?v=767f20d6", "/assets/js/store.js?v=7cd03f9d", "/assets/js/terms.js?v=8cc52b9a", "/assets/js/today.js?v=886eba2f", "/assets/js/vendor/qrcode.js?v=4c79be16", "/my.html", "/offline.html", "/today.html"];
/* 캐시 이름 — 버전이 바뀌면 static·pages·data 는 새 이름이 되어 activate 에서 옛것이 지워진다. fonts 는 버전과 무관 (순수 함수, 테스트) */
function cacheNames(version) { return { static: "static-" + version, pages: "pages-" + version, data: "data-" + version, fonts: "fonts-v1" }; }
var NAMES = cacheNames(VERSION), CACHE_STATIC = NAMES.static, CACHE_PAGES = NAMES.pages, CACHE_DATA = NAMES.data, CACHE_FONTS = NAMES.fonts;
/* 캐시별 항목 상한 — 넘치면 먼저 넣은 것부터 지운다(cache.keys() 는 넣은 순서). static 은 precache 목록이 정하므로 제한하지 않는다 */
var CACHE_LIMIT = { pages: 60, data: 120, fonts: 30 };
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

/* 캐시에서 찾아볼 주소 후보 — Cloudflare Pages 는 /foo.html 을 /foo 로(/index.html 은 /) 리다이렉트해 최종 페이지가 확장자 없는 키로 저장되므로
   내부 링크(.html)로 다시 올 때 확장자 없는 키도 찾고, 반대로 확장자 없는 주소(/my — 앱의 첫 화면, 주소창 직접 입력)로 올 때는 precache·내부 링크 키인
   /my.html 도 찾는다(/ 는 /index.html). 그래서 한 번도 /my 를 연 적 없는 기기도 오프라인에서 바로 열린다 (순수 함수) */
function cacheKeyCandidates(url) {
  var out = [url], u;
  try { u = new URL(url); } catch (e) { return out; }
  var p = u.pathname;
  if (/\.html$/.test(p)) out.push(u.origin + (/\/index\.html$/.test(p) ? p.replace(/index\.html$/, "") : p.replace(/\.html$/, "")) + u.search);
  else if (/\/$/.test(p)) out.push(u.origin + p + "index.html" + u.search);
  else if (!/\.[A-Za-z0-9]+$/.test(p.split("/").pop())) out.push(u.origin + p + ".html" + u.search);
  return out;
}

/* 상한을 넘긴 캐시에서 지울 키 — 먼저 넣은 것부터 (순수 함수) */
function keysToTrim(keys, max) { return max > 0 && keys.length > max ? keys.slice(0, keys.length - max) : []; }

/* 리다이렉트를 거쳐 받은 응답(redirected=true)은 페이지 이동 요청에 그대로 돌려줄 수 없어 새 Response 로 감싼다 (순수 함수) */
function stripRedirect(res) {
  if (!res || !res.redirected) return res;
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: res.headers });
}

function matchAny(request) {
  var keys = cacheKeyCandidates(typeof request === "string" ? request : request.url);
  return keys.reduce(function (p, k) { return p.then(function (hit) { return hit || caches.match(k); }); }, Promise.resolve(null));
}

function putIn(cacheName, request, response, limit) {
  if (!response || !(response.ok || response.type === "opaque")) return response;
  var copy = response.clone();
  caches.open(cacheName).then(function (c) {
    return c.put(request, copy).then(function () {
      if (!limit) return null;
      return c.keys().then(function (keys) { return Promise.all(keysToTrim(keys, limit).map(function (k) { return c.delete(k); })); });
    });
  }).catch(function () {});
  return response;
}

function networkFirst(cacheName, request, fallback, limit) {
  return fetch(request).then(function (res) { return putIn(cacheName, request, res, limit); }).catch(function () {
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

function staleWhileRevalidate(cacheName, request, limit) {
  return caches.match(request).then(function (hit) {
    var refresh = fetch(request).then(function (res) { return putIn(cacheName, request, res, limit); }).catch(function () { return hit || Response.error(); });
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
    if (how === "page") e.respondWith(networkFirst(CACHE_PAGES, req, function () { return caches.match(OFFLINE_URL).then(function (hit) { return hit ? stripRedirect(hit) : Response.error(); }); }, CACHE_LIMIT.pages));
    else if (how === "asset") e.respondWith(cacheFirst(CACHE_STATIC, req));
    else if (how === "revalidate") e.respondWith(staleWhileRevalidate(CACHE_STATIC, req));
    else if (how === "data") e.respondWith(networkFirst(CACHE_DATA, req, null, CACHE_LIMIT.data));
    else e.respondWith(staleWhileRevalidate(CACHE_FONTS, req, CACHE_LIMIT.fonts));
  });
}

if (typeof module !== "undefined") module.exports = { strategyFor: strategyFor, cacheKeyCandidates: cacheKeyCandidates, stripRedirect: stripRedirect, cacheNames: cacheNames, keysToTrim: keysToTrim, CACHE_LIMIT: CACHE_LIMIT, VERSION: VERSION };
