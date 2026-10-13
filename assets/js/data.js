/* 데이터 로더 + 공통 유틸 (모든 페이지에서 사용) */
(function () {
  "use strict";
  var ROOT = document.documentElement.getAttribute("data-root") || "./";
  var cache = {};

  function fetchJSON(path, timeoutMs) {
    timeoutMs = timeoutMs || 10000;
    var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, timeoutMs) : null;
    return fetch(path, { cache: "no-cache", signal: ctrl ? ctrl.signal : undefined })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status + " for " + path);
        return r.json();
      })
      .finally(function () { if (timer) clearTimeout(timer); });
  }

  function load(name) {
    if (!cache[name]) {
      cache[name] = fetchJSON(ROOT + "data/" + name + ".json").catch(function (err) {
        (/HTTP 404/.test(err.message) ? console.warn : console.error)("[data] " + name + " 로드 실패:", err.message);
        delete cache[name];
        throw err;
      });
    }
    return cache[name];
  }

  var Data = {
    root: ROOT,
    url: function (p) { return ROOT + p.replace(/^\/+/, ""); },
    ingredientUrl: function (id) { return ROOT + "i/" + encodeURIComponent(id) + ".html"; },
    compatUrl: function (ids) { return ROOT + "compatibility.html?items=" + ids.map(encodeURIComponent).join(","); },
    productsUrl: function (id) { return ROOT + "products.html" + (id ? "?ingredient=" + encodeURIComponent(id) : ""); },
    productUrl: function (id) { return ROOT + "product.html?id=" + encodeURIComponent(id); },

    ingredients: function () { return load("ingredients"); },
    interactions: function () { return load("interactions"); },
    products: function () { return load("products"); },
    productNames: function () { return load("products/names"); },   // 검색용 경량 색인 { i:[성분id], p:[[제품id, 이름, [성분번호]]] }
    news: function () { return load("news"); },
    meta: function () { return load("meta"); },
    deeplinks: function () { return load("deeplinks").catch(function () { return { coupang: {} }; }); },

    /* 제품 데이터 구조
     *  data/products.json                 — 가벼운 목록(제품 찾기 페이지)
     *  data/products/top/<성분id>.json     — 성분별 상위 제품 (성분 상세 페이지)
     *  data/products/detail/<NN>.json     — 전체 레코드 조각 (제품 '더보기' 펼칠 때)
     */
    productsTop: function (iid) {
      return load("products/top/" + iid).then(function (d) { return (d && d.items) || []; }).catch(function () {
        // 성분별 파일이 없으면(샘플 상태 등) 목록에서 걸러서 사용
        return load("products").then(function (d) { return (d.items || []).filter(function (p) { return (p.ingredients || []).indexOf(iid) >= 0; }); }).catch(function () { return []; });
      });
    },
    guides: function () { return load("guides"); },
    guideUrl: function (slug) { return ROOT + "guide/" + encodeURIComponent(slug) + ".html"; },

    /* 식약처 기능성 원료 데이터: data/materials.json(전체), data/materials/<성분id>.json(성분별) */
    materials: function () { return load("materials"); },
    materialsFor: function (iid) {
      return load("materials/" + iid).then(function (d) { return (d && d.items) || []; }).catch(function () { return []; });
    },
    productShard: function (id) {           // scripts/fetch_products.py 의 shard_of() 와 동일한 계산
      var h = 0; id = String(id || "");
      for (var i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) % 1000003;
      var n = h % 64; return (n < 10 ? "0" : "") + n;
    },
    productDetail: function (id) {
      return load("products/detail/" + Data.productShard(id)).then(function (d) {
        var hit = ((d && d.items) || []).filter(function (p) { return p.id === id; })[0];
        return hit || null;
      }).catch(function () { return null; });
    },

    /* 성분 + 궁합을 함께 로드해 인덱스까지 만들어 반환 */
    core: function () {
      if (cache.__core) return cache.__core;
      cache.__core = Promise.all([load("ingredients"), load("interactions")]).then(function (res) {
        var ing = res[0], inter = res[1];
        var byId = {};
        ing.items.forEach(function (it) { byId[it.id] = it; });
        var pairIndex = {};
        inter.pairs.forEach(function (p) { pairIndex[Data.pairKey(p.pair[0], p.pair[1])] = p; });
        return {
          items: ing.items, byId: byId, categories: ing._meta.categories, slots: ing._meta.slots,
          pairs: inter.pairs, pairIndex: pairIndex, types: inter._meta.types
        };
      });
      return cache.__core;
    },

    pairKey: function (a, b) { return a < b ? a + "|" + b : b + "|" + a; },
    findPair: function (core, a, b) { return core.pairIndex[Data.pairKey(a, b)] || null; },
    /* 특정 성분과 관계된 모든 궁합 */
    related: function (core, id) {
      return core.pairs.filter(function (p) { return p.pair.indexOf(id) >= 0; }).map(function (p) {
        var other = p.pair[0] === id ? p.pair[1] : p.pair[0];
        return { other: core.byId[other], pair: p };
      }).filter(function (r) { return !!r.other; });
    },
    typeOrder: { avoid: 0, caution: 1, synergy: 2, neutral: 3, unknown: 4 },

    /* 간단 검색 (이름·별칭·태그·영문) */
    search: function (items, q, limit) {
      q = (q || "").trim().toLowerCase();
      if (!q) return [];
      var scored = [];
      items.forEach(function (it) {
        var s = 0;
        var name = it.name.toLowerCase();
        if (name === q) s = 100;
        else if (name.indexOf(q) === 0) s = 80;
        else if (name.indexOf(q) >= 0) s = 60;
        else if ((it.aliases || []).some(function (a) { return a.toLowerCase().indexOf(q) >= 0; })) s = 50;
        else if ((it.en || "").toLowerCase().indexOf(q) >= 0) s = 40;
        else if ((it.tags || []).some(function (t) { return t.toLowerCase().indexOf(q) >= 0; })) s = 30;
        else if ((it.summary || "").toLowerCase().indexOf(q) >= 0) s = 10;
        if (s) scored.push({ s: s, it: it });
      });
      scored.sort(function (a, b) { return b.s - a.s; });
      return scored.slice(0, limit || 8).map(function (x) { return x.it; });
    },

    /* HTML 이스케이프 */
    esc: function (s) {
      return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
      });
    },
    qs: function (name) {
      try { return new URLSearchParams(location.search).get(name); } catch (e) { return null; }
    },
    fmtDate: function (iso) {
      if (!iso) return "";
      var d = new Date(iso);
      if (isNaN(d.getTime())) return String(iso).slice(0, 10);
      return d.getFullYear() + "." + String(d.getMonth() + 1).padStart(2, "0") + "." + String(d.getDate()).padStart(2, "0");
    },
    timeAgo: function (iso) {
      var d = new Date(iso); if (isNaN(d.getTime())) return "";
      var diff = (Date.now() - d.getTime()) / 1000;
      if (diff < 3600) return Math.max(1, Math.floor(diff / 60)) + "분 전";
      if (diff < 86400) return Math.floor(diff / 3600) + "시간 전";
      if (diff < 86400 * 14) return Math.floor(diff / 86400) + "일 전";
      return Data.fmtDate(iso);
    },
    icons: function (root) {
      try { if (window.lucide && window.lucide.createIcons) window.lucide.createIcons(root ? { root: root } : undefined); } catch (e) { /* 아이콘 로드 실패 시 무시 */ }
    },
    /* 카테고리 색상 클래스 (Tailwind) */
    catClass: function (color) {
      var map = {
        amber: "bg-amber-50 text-amber-700 ring-amber-200", sky: "bg-sky-50 text-sky-700 ring-sky-200",
        blue: "bg-blue-50 text-blue-700 ring-blue-200", lime: "bg-lime-50 text-lime-700 ring-lime-200",
        emerald: "bg-emerald-50 text-emerald-700 ring-emerald-200", violet: "bg-violet-50 text-violet-700 ring-violet-200",
        orange: "bg-orange-50 text-orange-700 ring-orange-200", pink: "bg-pink-50 text-pink-700 ring-pink-200",
        rose: "bg-rose-50 text-rose-700 ring-rose-200", slate: "bg-slate-100 text-slate-600 ring-slate-200"
      };
      return map[color] || map.slate;
    },
    typeClass: function (type) {
      return { synergy: "badge-synergy", caution: "badge-caution", avoid: "badge-avoid", neutral: "badge-neutral", unknown: "badge-neutral" }[type] || "badge-neutral";
    }
  };
  window.Data = Data;
})();
