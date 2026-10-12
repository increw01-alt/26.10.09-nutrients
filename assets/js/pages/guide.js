/* 가이드 페이지: 정적으로 생성된 본문에 쇼핑 버튼만 채웁니다 */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    if (!window.Affiliate) return;
    window.Affiliate.ready().then(function () {
      document.querySelectorAll(".js-shop[data-query]").forEach(function (el) {
        el.innerHTML = window.Affiliate.buttonsHtml(el.getAttribute("data-query"), { size: "sm", short: true });
      });
      if (window.Data) window.Data.icons();
    });
  });
})();
