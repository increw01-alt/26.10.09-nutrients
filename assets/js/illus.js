/* 간단한 SVG 일러스트 (사진 대신 사용) — 병·캡슐·소프트젤·정제·잎·분말 */
(function () {
  "use strict";
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  var leaf = function (x, y, s, rot, c) {
    return '<g transform="translate(' + x + ' ' + y + ') rotate(' + rot + ') scale(' + s + ')"><path d="M0 0 C 18 -30, 54 -34, 70 -10 C 52 10, 18 18, 0 0 Z" fill="' + c + '"/><path d="M4 -2 C 24 -12, 44 -16, 62 -10" stroke="rgba(255,255,255,.55)" stroke-width="2" fill="none" stroke-linecap="round"/></g>';
  };
  var Illus = {
    /* 라벨이 붙은 영양제 병 (카드용) */
    bottle: function (label, color, opts) {
      opts = opts || {};
      var body = opts.body || "#fbfaf6", cap = opts.cap || "#2f6538", lab = color || "#3a7d44";
      var sub = opts.sub || "";
      return '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="' + esc(label) + '">' +
        '<ellipse cx="100" cy="176" rx="58" ry="9" fill="rgba(28,27,24,.08)"/>' +
        leaf(18, 150, 0.9, -20, "#9cc6a4") + leaf(150, 165, 0.8, 200, "#6ea87a") +
        '<rect x="80" y="28" width="40" height="18" rx="4" fill="' + cap + '"/>' +
        '<rect x="84" y="44" width="32" height="8" fill="' + body + '" opacity=".9"/>' +
        '<rect x="62" y="50" width="76" height="118" rx="18" fill="' + body + '" stroke="rgba(28,27,24,.08)"/>' +
        '<rect x="62" y="82" width="76" height="54" fill="' + lab + '"/>' +
        '<rect x="62" y="82" width="76" height="54" fill="url(#g' + (opts.id || "") + ')" opacity=".15"/>' +
        '<text x="100" y="105" text-anchor="middle" font-family="Pretendard, sans-serif" font-size="11" font-weight="800" fill="#fff" letter-spacing=".06em">' + esc(label).toUpperCase() + '</text>' +
        '<text x="100" y="122" text-anchor="middle" font-family="Pretendard, sans-serif" font-size="8" font-weight="600" fill="rgba(255,255,255,.85)">' + esc(sub) + '</text>' +
        '<rect x="70" y="58" width="6" height="100" rx="3" fill="rgba(255,255,255,.55)"/>' +
        '</svg>';
    },
    capsule: function (c1, c2) {
      return '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><g transform="rotate(-35 32 32)"><rect x="12" y="22" width="40" height="20" rx="10" fill="' + c1 + '"/><path d="M32 22h10a10 10 0 0 1 0 20H32z" fill="' + c2 + '"/><rect x="16" y="26" width="12" height="4" rx="2" fill="rgba(255,255,255,.6)"/></g><ellipse cx="32" cy="52" rx="16" ry="3" fill="rgba(28,27,24,.08)"/></svg>';
    },
    softgel: function (c) {
      return '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><ellipse cx="32" cy="52" rx="16" ry="3" fill="rgba(28,27,24,.08)"/><g transform="rotate(-25 32 32)"><ellipse cx="32" cy="32" rx="20" ry="12" fill="' + c + '"/><ellipse cx="25" cy="27" rx="7" ry="3.5" fill="rgba(255,255,255,.55)"/></g></svg>';
    },
    tablet: function (c) {
      return '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><ellipse cx="32" cy="52" rx="16" ry="3" fill="rgba(28,27,24,.08)"/><circle cx="32" cy="31" r="17" fill="' + c + '"/><path d="M18 31h28" stroke="rgba(28,27,24,.18)" stroke-width="2" stroke-linecap="round"/><ellipse cx="25" cy="23" rx="6" ry="3" fill="rgba(255,255,255,.5)"/></svg>';
    },
    leaf: function (c) {
      return '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><ellipse cx="32" cy="54" rx="16" ry="3" fill="rgba(28,27,24,.08)"/>' + leaf(10, 40, 0.62, -30, c) + '<path d="M14 40 C 24 30, 34 24, 46 18" stroke="rgba(255,255,255,.7)" stroke-width="2" fill="none" stroke-linecap="round"/></svg>';
    },
    powder: function (c) {
      return '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><ellipse cx="32" cy="52" rx="18" ry="3" fill="rgba(28,27,24,.08)"/><path d="M12 48 C 16 30, 26 20, 32 18 C 38 20, 48 30, 52 48 Z" fill="' + c + '"/><path d="M22 44 C 26 34, 30 30, 32 28" stroke="rgba(255,255,255,.6)" stroke-width="2" fill="none" stroke-linecap="round"/></svg>';
    },
    bone: function (c) {
      return '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><ellipse cx="32" cy="52" rx="16" ry="3" fill="rgba(28,27,24,.08)"/><g transform="rotate(-35 32 32)"><rect x="18" y="27" width="28" height="10" rx="5" fill="' + c + '"/><circle cx="18" cy="26" r="6" fill="' + c + '"/><circle cx="18" cy="38" r="6" fill="' + c + '"/><circle cx="46" cy="26" r="6" fill="' + c + '"/><circle cx="46" cy="38" r="6" fill="' + c + '"/></g></svg>';
    },
    sparkle: function (c) {
      return '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><ellipse cx="32" cy="52" rx="16" ry="3" fill="rgba(28,27,24,.08)"/><path d="M32 10 C 34 24, 40 30, 54 32 C 40 34, 34 40, 32 54 C 30 40, 24 34, 10 32 C 24 30, 30 24, 32 10 Z" fill="' + c + '"/><circle cx="48" cy="16" r="4" fill="' + c + '" opacity=".7"/></svg>';
    },
    /* 성분 객체 → 병 라벨용 짧은 영문명 */
    labelFor: function (it) {
      var en = String((it && (it.en || it.name)) || "").split("(")[0].replace(/[^A-Za-z0-9 \-·]/g, "").trim();
      return (en || (it && it.name) || "").slice(0, 14);
    },
    /* 성분 분류(category) → 아이콘 */
    forCategory: function (key) {
      switch (key) {
        case "vitamin": return Illus.capsule("#f3b23e", "#f6d27a");
        case "mineral": return Illus.tablet("#c9c3b6");
        case "fatty-acid": return Illus.softgel("#f6c43d");
        case "probiotic": return Illus.capsule("#2f6fb3", "#ffffff");
        case "herbal": return Illus.leaf("#4b8c59");
        case "amino": return Illus.capsule("#8b6fc7", "#d9ccf2");
        case "joint": return Illus.bone("#e9a66b");
        case "beauty": return Illus.sparkle("#f0a3b5");
        default: return Illus.tablet("#c9c3b6");
      }
    },
    /* 성분 분류 → 병 라벨 색 */
    colorFor: function (key) {
      return { vitamin: "#e09a2e", mineral: "#5f7f9c", "fatty-acid": "#d9a21b", probiotic: "#2f6fb3", herbal: "#3a7d44", amino: "#7d62b8", joint: "#d08a4a", beauty: "#d97b93" }[key] || "#3a7d44";
    }
  };
  window.Illus = Illus;
})();
