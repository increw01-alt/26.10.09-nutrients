/* 용어 자동 링크 — HTML 이스케이프된 본문 조각에서 용어 사전 별칭의 첫 등장만 term/<slug>.html 링크로 바꾼다.
 * scripts/build_site.py 의 TermLinker 와 같은 규칙: 별칭은 긴 것부터, 영문·숫자 별칭은 앞뒤가 영문·숫자가 아닐 때, 한글 별칭은 앞이 한글이 아닐 때만,
 * 대소문자 무시, 페이지당 용어마다 한 번·최대 MAX 개, exclude 의 용어는 건너뜀. 태그가 든 문자열에는 쓰지 않는다.
 * 순수 함수라 node --test tests/terms.test.mjs 로 검증한다. 구형 브라우저(lookbehind 미지원)는 정규식 생성이 실패하므로 링크 없이 지나간다. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Terms = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  var MAX = 12;
  function escHtml(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;"); }
  function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
  function pattern(a) {
    var head = /^[A-Za-z0-9]/.test(a) ? "(?<![A-Za-z0-9])" : "(?<![가-힣])";
    var tail = /[A-Za-z0-9]$/.test(a) ? "(?![A-Za-z0-9])" : "";
    return head + escRe(a) + tail;
  }
  function build(items) {
    var byAlias = {}, aliases = [];
    (items || []).forEach(function (it) {
      (it.aliases || []).forEach(function (a) {
        var e = escHtml(a), k = e.toLowerCase();
        if (byAlias[k]) return;
        byAlias[k] = { slug: it.slug, short: it.short || "" };
        aliases.push(e);
      });
    });
    aliases.sort(function (a, b) { return b.length - a.length; });
    var re = null;
    try { re = aliases.length ? new RegExp(aliases.map(pattern).join("|"), "gi") : null; } catch (e) { re = null; }
    return {
      size: aliases.length,
      link: function (textEsc, rootPath, state) {
        state = state || {};
        state.used = state.used || {};
        state.count = state.count || 0;
        var exclude = state.exclude || {};
        if (!re || !textEsc || state.count >= MAX) return textEsc == null ? "" : String(textEsc);
        return String(textEsc).replace(re, function (m) {
          var hit = byAlias[m.toLowerCase()];
          if (!hit) return m;
          if (exclude[hit.slug] || state.used[hit.slug] || state.count >= MAX) return m;
          state.used[hit.slug] = true; state.count++;
          return '<a class="term-link" href="' + (rootPath || "") + "term/" + hit.slug + '.html" title="' + escHtml(hit.short) + '">' + m + "</a>";
        });
      }
    };
  }
  return { build: build, MAX: MAX, escHtml: escHtml };
});
