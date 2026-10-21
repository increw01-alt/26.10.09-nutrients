/* 용어 사전 허브(glossary.html, 빌드 생성) — 검색 상자와 초성/알파벳 버튼으로 카드를 거른다. 카드의 data-search(공백·구분자를 뺀 소문자)·data-initial 은 빌드가 넣는다. */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    var input = document.getElementById("term-filter");
    if (!input) return;
    var cards = Array.prototype.slice.call(document.querySelectorAll("[data-term-card]"));
    var chips = Array.prototype.slice.call(document.querySelectorAll("[data-initial-chip]"));
    var sections = Array.prototype.slice.call(document.querySelectorAll("[data-term-section]"));
    var empty = document.getElementById("term-empty"), count = document.getElementById("term-count");
    var active = "";
    function norm(s) { return String(s || "").toLowerCase().replace(/[\s·\-()（）.,/]+/g, ""); }
    function apply() {
      var q = norm(input.value), n = 0;
      cards.forEach(function (c) {
        var ok = (!q || (c.getAttribute("data-search") || "").indexOf(q) >= 0) && (!active || c.getAttribute("data-initial") === active);
        c.classList.toggle("hidden", !ok);
        if (ok) n++;
      });
      sections.forEach(function (s) { s.classList.toggle("hidden", !s.querySelector("[data-term-card]:not(.hidden)")); });
      if (empty) empty.classList.toggle("hidden", n > 0);
      if (count) count.textContent = String(n);
    }
    input.addEventListener("input", apply);
    chips.forEach(function (ch) {
      ch.addEventListener("click", function () {
        var v = ch.getAttribute("data-initial-chip");
        active = active === v ? "" : v;
        chips.forEach(function (x) { var on = x.getAttribute("data-initial-chip") === active; x.classList.toggle("is-on", on); x.setAttribute("aria-pressed", on ? "true" : "false"); });
        apply();
      });
    });
    try {
      var q0 = new URLSearchParams(location.search).get("q");
      if (q0) { input.value = q0; apply(); }
    } catch (e) { /* 주소 해석 실패는 무시 */ }
  });
})();
