/* 쇼핑몰 링크 생성 (제휴 설정이 있으면 자동으로 딥링크로 감쌈) */
(function () {
  "use strict";
  var deeplinkCache = null;

  function wrap(shop, targetUrl, query) {
    var A = window.AFFILIATE || {};
    try {
      if (shop.network === "linkprice" && A.linkprice && A.linkprice.enabled && A.linkprice.merchants[shop.key]) {
        return A.linkprice.buildUrl(A.linkprice.merchants[shop.key], targetUrl);
      }
      if (shop.network === "coupang" && deeplinkCache && deeplinkCache.coupang && deeplinkCache.coupang[query]) {
        return deeplinkCache.coupang[query];
      }
    } catch (e) { console.warn("[affiliate] 링크 생성 실패, 일반 링크 사용:", e); }
    return targetUrl;
  }

  var Affiliate = {
    /* 딥링크 데이터 선로드 (선택) */
    ready: function () {
      if (deeplinkCache) return Promise.resolve(deeplinkCache);
      return window.Data.deeplinks().then(function (d) { deeplinkCache = d || { coupang: {} }; return deeplinkCache; })
        .catch(function () { deeplinkCache = { coupang: {} }; return deeplinkCache; });
    },
    links: function (query) {
      var A = window.AFFILIATE || { shops: [] };
      return (A.shops || []).map(function (shop) {
        var target = shop.searchUrl(query);
        var url = wrap(shop, target, query);
        return { key: shop.key, label: shop.label, short: shop.short, color: shop.color, url: url, affiliated: url !== target };
      });
    },
    /* 버튼 묶음 HTML */
    buttonsHtml: function (query, opts) {
      if (window.AppBridge && window.AppBridge.hideShopping()) return "";   // 앱 1차 출시는 쇼핑 버튼을 숨김(config.js 의 SITE.appShopping 으로 켬)
      opts = opts || {};
      var esc = window.Data.esc;
      var size = opts.size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3.5 py-2 text-sm";
      return '<div class="flex flex-wrap gap-2 shop-buttons" data-query="' + esc(query) + '">' +
        Affiliate.links(query).map(function (l) {
          return '<a href="' + esc(l.url) + '" target="_blank" rel="nofollow sponsored noopener" ' +
            'class="shop-btn inline-flex items-center gap-1.5 rounded-lg font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:shadow ' + size + '" ' +
            'style="background:' + esc(l.color) + '" aria-label="' + esc(l.label) + '에서 ' + esc(query) + ' 검색">' +
            '<i data-lucide="shopping-cart" class="h-3.5 w-3.5"></i>' + esc(opts.short ? l.short : l.label) + '</a>';
        }).join("") +
        '</div>';
    },
    disclosure: function () { return (window.AppBridge && window.AppBridge.hideShopping()) ? "" : ((window.AFFILIATE && window.AFFILIATE.disclosure) || ""); }
  };
  window.Affiliate = Affiliate;
})();
