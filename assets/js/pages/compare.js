/* 성분 비교 페이지(compare/<slug>.html, 빌드 생성) — 성분별 쇼핑 버튼(제휴 링크)과 제휴 고지를 채운다.
 * 버튼 자리는 <div data-query="쇼핑 검색어">, 고지는 #compare-disclosure. 앱 모드(쇼핑 숨김)에서는 둘 다 .app-hide 로 숨겨진다(app.js·style.css). */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    var A = window.Affiliate, D = window.Data;
    if (!A) return;
    (A.ready ? A.ready() : Promise.resolve()).then(function () {
      document.querySelectorAll("[data-query]").forEach(function (el) { el.innerHTML = A.buttonsHtml(el.getAttribute("data-query"), { size: "sm", short: true }); });
      var d = document.getElementById("compare-disclosure");
      if (d) { var t = A.disclosure(); if (t) d.textContent = t; else d.remove(); }
      if (D && D.icons) D.icons(document.body);
    }).catch(function (err) { console.warn("[compare] 쇼핑 버튼 생성 실패:", err && err.message); });
  });
})();
