/* 가이드 허브(guides.html): 제목·키워드·설명으로 카드 필터, 빈 분류는 숨김, ?q= 유지 */
(function () {
  "use strict";
  var D = window.Data;
  var input = document.getElementById("guide-search"), count = document.getElementById("guide-count"), empty = document.getElementById("guide-empty");
  if (!input) return;
  function norm(s) { return String(s || "").normalize("NFKC").toLowerCase().replace(/[\s·\-]+/g, ""); }   // build_site.py 의 search_text 와 같은 규칙
  var cards = Array.prototype.slice.call(document.querySelectorAll("[data-search]"));
  var sections = Array.prototype.slice.call(document.querySelectorAll("main section[id]"));
  var total = cards.length;
  function apply() {
    var q = norm(input.value), n = 0;
    cards.forEach(function (c) { var hit = !q || c.getAttribute("data-search").indexOf(q) >= 0; c.classList.toggle("hidden", !hit); if (hit) n++; });
    sections.forEach(function (s) { s.classList.toggle("hidden", !!q && !s.querySelector("[data-search]:not(.hidden)")); });
    if (count) count.textContent = q ? "가이드 " + n + "편 일치 (전체 " + total + "편)" : "가이드 " + total + "편";
    if (empty) empty.classList.toggle("hidden", n > 0);
    try { var u = new URL(location.href); if (input.value.trim()) u.searchParams.set("q", input.value.trim()); else u.searchParams.delete("q"); history.replaceState(null, "", u); } catch (e) { /* ignore */ }
  }
  input.value = (D && D.qs ? D.qs("q") : new URLSearchParams(location.search).get("q")) || "";
  input.addEventListener("input", apply);
  apply();
})();
