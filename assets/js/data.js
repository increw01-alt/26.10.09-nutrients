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
        (/HTTP 404|Failed to fetch|NetworkError|abort/i.test(err.message) ? console.warn : console.error)("[data] " + name + " 로드 실패:", err.message);   // 404·페이지 이동 중 취소는 경고로만
        delete cache[name];
        throw err;
      });
    }
    return cache[name];
  }

  var CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ", JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ";
  var JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
  function jamo(s) {   // 한글 음절 → 자모 나열, 영문·숫자는 소문자, 공백·기호 제거
    var out = ""; s = String(s == null ? "" : s).toLowerCase();
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i), ch = s.charAt(i);
      if (c >= 0xAC00 && c <= 0xD7A3) { var n = c - 0xAC00; out += CHO.charAt(Math.floor(n / 588)) + JUNG.charAt(Math.floor((n % 588) / 28)) + JONG[n % 28]; }
      else if ((c >= 0x3131 && c <= 0x318E) || /[a-z0-9]/.test(ch)) out += ch;
    }
    return out;
  }
  function chosung(s) {  // 초성만 (영문·숫자 포함)
    var out = ""; s = String(s == null ? "" : s).toLowerCase();
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i), ch = s.charAt(i);
      if (c >= 0xAC00 && c <= 0xD7A3) out += CHO.charAt(Math.floor((c - 0xAC00) / 588));
      else if ((c >= 0x3131 && c <= 0x314E) || /[a-z0-9]/.test(ch)) out += ch;
    }
    return out;
  }
  function wordStarts(s, fn) {   // fn(jamo·chosung) 으로 풀어 쓴 문자열에서 단어가 시작하는 위치 → {위치: 1} (공백·기호 뒤, 한글↔영문·숫자 경계)
    var out = {}, len = 0, start = true, prevH = null; s = String(s == null ? "" : s);
    for (var i = 0; i < s.length; i++) {
      var piece = fn(s.charAt(i));
      if (!piece) { start = true; continue; }
      var c = s.charCodeAt(i), h = (c >= 0xAC00 && c <= 0xD7A3) || (c >= 0x3131 && c <= 0x318E);
      if (start || (prevH !== null && h !== prevH)) out[len] = 1;
      start = false; prevH = h; len += piece.length;
    }
    return out;
  }

  var Data = {
    root: ROOT,
    url: function (p) { return ROOT + p.replace(/^\/+/, ""); },
    ingredientUrl: function (id) { return ROOT + "i/" + encodeURIComponent(id) + ".html"; },
    compatUrl: function (ids) { return ROOT + "compatibility.html?items=" + ids.map(encodeURIComponent).join(","); },
    productsUrl: function (id) { return ROOT + "products.html" + (id ? "?ingredient=" + encodeURIComponent(id) : ""); },
    productUrl: function (id) { return ROOT + "product.html?id=" + encodeURIComponent(id); },
    drugUrl: function (id) { return ROOT + "drug.html?id=" + encodeURIComponent(id); },

    ingredients: function () { return load("ingredients"); },
    interactions: function () { return load("interactions"); },
    products: function () { return load("products"); },          // 최신 일부(_meta.listed 건) + 변경 이력·제형 목록. 전체 목록은 productsAll()
    productsAll: function () {                                        // 제품 찾기 전체 목록 (필터·검색·뒷페이지에서 지연 로드). 파일이 없으면(구버전 데이터) 목록 파일로 대체
      return load("products/all").catch(function () { return load("products"); });
    },
    productNames: function () {   // 검색용 경량 색인 { i:[성분id], c:[제조사], p:[[제품id, 이름, [성분번호], 제조사번호]] }
      // 최근 제품(names.json)을 먼저 돌려주고, 과거 제품(names-old.json)은 n.more 가 끝나면 n.p 에 이어 붙는다 → 호출한 쪽은 n.more.then(다시 그리기)
      if (!cache.__productNames) {
        cache.__productNames = load("products/names").then(function (n) {
          n.more = (n._meta && n._meta.old) ? load("products/names-old").then(function (o) { n.p = n.p.concat((o && o.p) || []); return n; }).catch(function () { return n; }) : Promise.resolve(n);
          return n;
        });
        cache.__productNames.catch(function () { delete cache.__productNames; });
      }
      return cache.__productNames;
    },
    /* 검색 색인 {c:[제조사], p:[[id, 이름, …]]} → 매처: 이름으로 찾고 제조사명(ci 번째)으로도 찾으며, 브랜드 가중치(wi 번째, data/brand-priority.json 을 빌드가 실어 둠)를 순위에 반영 */
    indexMatcher: function (n, ci, wi) {
      var p = (n && n.p) || [], c = (n && n.c) || [];
      return Data.nameMatcher(p.map(function (pp) { return pp[1]; }), {
        extra: p.map(function (pp) { return (ci >= 0 && pp[ci] >= 0 && c[pp[ci]]) || ""; }),
        weights: p.map(function (pp) { return pp[wi] || 0; })
      });
    },
    productMatcher: function (n) { return Data.indexMatcher(n, 3, 4); },   // 제품 색인: [제품id, 이름, [성분번호], 제조사번호, (가중치)]
    drugMatcher: function (n) { return Data.indexMatcher(n, 5, 6); },      // 의약품 색인: [품목코드, 이름, [성분번호], 주성분요약, 1=일반·2=전문, 제조사번호, (가중치)]
    drugNames: function () { return load("drugs/names"); },         // 의약품 검색 색인 { i:[성분id], c:[제조사], p:[[품목코드, 이름, [성분번호], 주성분요약, 1=일반·2=전문, 제조사번호]] } (수집 전이면 빈 색인)
    news: function () { return load("news"); },
    meta: function () { return load("meta"); },
    deeplinks: function () { return load("deeplinks").catch(function () { return { coupang: {} }; }); },

    /* 제품 데이터 구조
     *  data/products.json                 — 가벼운 목록 중 최신 일부(제품 찾기 첫 화면) + 변경 이력
     *  data/products/all.json             — 가벼운 목록 전체 (필터·검색·뒷페이지에서 지연 로드)
     *  data/products/top/<성분id>.json     — 성분별 상위 제품 (성분 상세 페이지)
     *  data/products/detail/<NN>.json     — 전체 레코드 조각 (제품 '더보기' 펼칠 때)
     */
    productsTop: function (iid) {
      return load("products/top/" + iid).then(function (d) { return (d && d.items) || []; }).catch(function () {
        // 성분별 파일이 없으면(샘플 상태 등) 전체 목록에서 걸러서 사용
        return Data.productsAll().then(function (d) { return (d.items || []).filter(function (p) { return (p.ingredients || []).indexOf(iid) >= 0; }); }).catch(function () { return []; });
      });
    },
    guides: function () { return load("guides-index"); },   // 요약 색인(빌드 생성). 본문이 필요하면 guides.json 을 따로 읽는다
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
    /* 의약품 데이터 구조 (scripts/fetch_drugs.py): data/drugs/names.json(검색 색인) + data/drugs/detail/<NNN>.json(상세 조각 128개) */
    drugShard: function (id) {              // scripts/fetch_drugs.py 의 shard_of() 와 동일한 계산
      var h = 0; id = String(id || "");
      for (var i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) % 1000003;
      var n = h % 128; return (n < 10 ? "00" : n < 100 ? "0" : "") + n;
    },
    /* 의약품별 '함께 챙기면 좋은/주의할 영양 성분' 규칙 (data/drug-pairings.json, 수동 관리) */
    drugPairings: function () { return load("drug-pairings").catch(function () { return { rules: [] }; }); },
    drugPairingFor: function (rules, drug, core) {   // → { good:[{id, why, hours, label}], caution:[…], notes:[…], labels:[…] }
      var out = { good: [], caution: [], notes: [], labels: [] };
      if (!rules || !rules.rules || !drug) return out;
      var tokens = ((drug.ingrEn && drug.ingrEn.length) ? drug.ingrEn : (drug.ingr || [])).map(function (t) { return String(t).toLowerCase(); });
      var cls = String(drug.cls || ""), name = String(drug.name || "");
      var external = /연고|크림|로션|패취|패치|플라스타|카타플라스마|좌제|점안|점비|점이|외용|스프레이|가글|구강용|습포|테이프|밴드|소독|파스|샴푸|비누|세정제|관장|질정|주사|수액|겔(제|$|\(|\d)/.test(name);
      var own = {}; (drug.ingredients || []).forEach(function (i) { own[i] = true; });
      var seen = { good: {}, caution: {} };
      rules.rules.forEach(function (r) {
        if (r.oralOnly && external) return;
        var hit = (r.ingr || []).some(function (k) { k = k.toLowerCase(); return tokens.some(function (t) { return t.indexOf(k) >= 0; }); })
          || (r.cls || []).some(function (c) { return cls && (cls === c || cls.indexOf(c) >= 0); })
          || (r.names || []).some(function (n) { return name.indexOf(n) >= 0; });
        if (!hit) return;
        out.labels.push(r.label || r.id);
        (r.good || []).forEach(function (g) { if (own[g.id] || seen.good[g.id] || (core && !core.byId[g.id])) return; seen.good[g.id] = true; out.good.push({ id: g.id, why: g.why, hours: g.hours, label: r.label }); });
        (r.caution || []).forEach(function (c) { if (seen.caution[c.id] || (core && !core.byId[c.id])) return; seen.caution[c.id] = true; out.caution.push({ id: c.id, why: c.why, hours: c.hours, label: r.label }); });
        if (r.note) out.notes.push(r.note);
      });
      return out;
    },
    drugDetail: function (id) {
      return load("drugs/detail/" + Data.drugShard(id)).then(function (d) {
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
        else if (Data.has(it.name, q) || (it.aliases || []).some(function (a) { return Data.has(a, q); })) s = 20;   // '비탐'·'ㅂㅌㅁ' 같은 입력 중 글자·초성
        if (s) scored.push({ s: s, it: it });
      });
      scored.sort(function (a, b) { return b.s - a.s; });
      return scored.slice(0, limit || 8).map(function (x) { return x.it; });
    },

    /* ---------- 한글 자모 검색 ----------
     * 음절을 초성·중성·종성으로 풀어 비교하므로 '락ㅌ'·'비탐' 처럼 입력 중인 글자, 'ㄹㅌㅍ' 같은 초성만으로도 제품명을 찾는다. */
    jamo: jamo,
    chosung: chosung,
    isChosung: function (q) { return /^[ㄱ-ㅎ]+$/.test(String(q || "").replace(/\s+/g, "")); },
    has: function (text, q) {   // text 안에 q 가 (자모 기준으로) 들어 있는가
      var key = Data.isChosung(q) ? String(q).replace(/\s+/g, "") : jamo(q);
      return !!key && (Data.isChosung(q) ? chosung(text) : jamo(text)).indexOf(key) >= 0;
    },
    /* 이름 목록용 매처: 한 번 자모로 풀어 두고 (q, limit) → { idx: [색인…], total } 를 돌려준다.
     * 순위: 이름 앞부분 일치(0) → 단어 첫머리 일치(300) → 이름 중간 일치(1000) → 제조사명 일치(2000, opts.extra) 등급으로 묶고,
     * 같은 등급 안에서는 브랜드 가중치(opts.weights 0~3, 한 단계당 -200: 등급 안에서는 항상 앞이고, 가중치 2 이상이면 단어 첫머리 일치가 가중치 없는 앞부분 일치보다 앞) 가 높은 것, 그다음 일치 위치가 앞인 것, 짧은 이름 순. */
    nameMatcher: function (names, opts) {
      opts = opts || {};
      var J = names.map(jamo), C = names.map(chosung), W = opts.weights || null;
      var E = opts.extra ? opts.extra.map(jamo) : null, EC = opts.extra ? opts.extra.map(chosung) : null;
      var SJ = names.map(function (n) { return wordStarts(n, jamo); }), SC = names.map(function (n) { return wordStarts(n, chosung); });
      return function (q, limit) {
        var cho = Data.isChosung(q), key = cho ? String(q).replace(/\s+/g, "") : jamo(q);
        if (key.length < 2) return { idx: [], total: 0 };
        var hits = [], arr = cho ? C : J, ext = cho ? EC : E, starts = cho ? SC : SJ;
        for (var i = 0; i < arr.length; i++) {
          var pos = arr[i].indexOf(key), tier;
          if (pos === 0) tier = 0;
          else if (pos > 0) tier = starts[i][pos] ? 300 : 1000;
          else if (ext && ext[i].indexOf(key) >= 0) { tier = 2000; pos = 0; }
          else continue;
          hits.push([i, tier + Math.min(pos, 60) * 3 + Math.min(arr[i].length, 99) - (W ? (W[i] || 0) * 200 : 0)]);   // 위치(자모 단위, 최대 180)·길이(최대 99)는 가중치 한 단계(200)를 넘지 않는다
        }
        hits.sort(function (a, b) { return a[1] - b[1]; });
        return { idx: hits.slice(0, limit || 10).map(function (h) { return h[0]; }), total: hits.length };
      };
    },
    /* 비슷한 이름 찾기 (검색 결과가 없을 때): 자모 2글자 묶음(바이그램) 겹침 비율 */
    similarNames: function (names, q, limit) {
      var jq = jamo(q); if (jq.length < 3) return [];
      function grams(s) { var m = {}, n = 0; for (var i = 0; i + 1 < s.length; i++) { var g = s.substr(i, 2); m[g] = (m[g] || 0) + 1; n++; } return { m: m, n: n }; }
      var gq = grams(jq), out = [];
      for (var i = 0; i < names.length; i++) {
        var js = jamo(names[i]); if (!js) continue;
        var gs = grams(js), common = 0;
        for (var g in gq.m) if (gs.m[g]) common += Math.min(gq.m[g], gs.m[g]);
        var score = (2 * common) / (gq.n + gs.n || 1);
        var pre = 0; while (pre < jq.length && pre < js.length && jq.charAt(pre) === js.charAt(pre)) pre++;
        if (pre >= 3) score += 0.25;                          // 앞부분이 같으면 가산
        if (score >= 0.4) out.push([i, score]);
      }
      out.sort(function (a, b) { return b[1] - a[1]; });
      return out.slice(0, limit || 6).map(function (h) { return h[0]; });
    },
    /* 이름에서 검색어와 (자모 기준으로) 일치한 부분을 <mark> 로 감싼 HTML */
    markMatch: function (name, q) {
      name = String(name == null ? "" : name);
      var cho = Data.isChosung(q), key = cho ? String(q).replace(/\s+/g, "") : jamo(q);
      if (!key) return Data.esc(name);
      var parts = [], off = [], total = "";
      for (var i = 0; i < name.length; i++) { var piece = cho ? chosung(name.charAt(i)) : jamo(name.charAt(i)); off.push(total.length); parts.push(piece); total += piece; }
      var pos = total.indexOf(key); if (pos < 0) return Data.esc(name);
      var end = pos + key.length, a = -1, b = -1;
      for (var k = 0; k < name.length; k++) { if (!parts[k]) continue; if (a < 0 && off[k] + parts[k].length > pos) a = k; if (off[k] < end) b = k; }
      if (a < 0 || b < a) return Data.esc(name);
      return Data.esc(name.slice(0, a)) + "<mark>" + Data.esc(name.slice(a, b + 1)) + "</mark>" + Data.esc(name.slice(b + 1));
    },
    searchUrl: function (q) { return ROOT + "search.html?q=" + encodeURIComponent(q || ""); },

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
