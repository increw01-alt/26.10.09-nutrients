/* 간단한 SVG 일러스트 (사진 대신 사용) — 병·캡슐·소프트젤·정제·잎·분말 */
(function () {
  "use strict";
  /* 사이트 루트(하위 폴더 페이지는 ../) — data.js 가 있을 때만, Node 테스트(window 없음)에선 빈 문자열 */
  function siteRoot() { return (typeof window !== "undefined" && window.Data && window.Data.url) ? window.Data.url("") : ""; }
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
    /* 성분 분류 → 실사 알약 사진 경로 (메인 시안의 연출 이미지, assets/images/home/) */
    photoFor: function (key) {
      var file = { vitamin: "capsule-yellow", mineral: "tablet-beige", "fatty-acid": "softgel-amber", probiotic: "capsule-blue", herbal: "capsule-green", amino: "capsule-violet", joint: "capsule-orange", beauty: "capsule-pink" }[key] || "tablet-beige";
      return siteRoot() + "assets/images/home/" + file + ".webp";
    },
    photoImg: function (key, cls) {
      return '<img src="' + Illus.photoFor(key) + '" alt="" width="54" height="48" loading="lazy" decoding="async"' + (cls ? ' class="' + esc(cls) + '"' : "") + '>';
    },
    /* 성분별 실사 사진(assets/images/ingredients/<id>.webp 3종 — scripts/convert_photos.py): size "" 640(상세 상단·가이드), "m" 360(목록 띠), "s" 160(썸네일).
       JS 가 그리는 사진은 ?v= 해시 없이 쓴다(_headers 7일 캐시 + 서비스워커 재검증) — 빌드(SSR)는 build_site.py photo_src 가 해시를 붙인다 */
    ingPhotoUrl: function (id, size) {
      return siteRoot() + "assets/images/ingredients/" + encodeURIComponent(String(id)) + (size ? "-" + size : "") + ".webp";
    },
    /* 사진 파일이 아직 없는 새 성분(ingredients.json 에 넣고 사진은 나중에 채우는 경우) — JS 는 파일 유무 표가 없으므로 onerror 로 _default 로 바꿔 404 빈 칸을 막는다.
       withSrcset 이면 srcset(띠의 640 후보)도 같이 바꾼다. 빌드(SSR)는 prepare_photos 가 미리 _default 로 정한다 */
    ingPhotoFallback: function (size, withSrcset) {
      var d = Illus.ingPhotoUrl("_default", size);
      return ' onerror="this.onerror=null;' + (withSrcset ? "this.srcset='" + d + "';" : "") + "this.src='" + d + "'\"";
    },
    /* 작은 목록(검색 결과·셀프체크 결과·상세 작은 칸)의 160px 썸네일 — build_site.py ing_thumb_img 와 같은 모양 */
    ingThumb: function (it, cls) {
      return '<img src="' + Illus.ingPhotoUrl(it.id, "s") + '" alt="" width="160" height="160" loading="lazy" decoding="async"' + Illus.ingPhotoFallback("s") + (cls ? ' class="' + esc(cls) + '"' : "") + '>';
    },
    /* 성분 카드 위 사진 띠(B-1): 360px 사진(고해상도·휴대폰은 srcset 의 640) + 아래쪽 그라데이션(CSS .ing-band::after) + 분류 배지 + 성분명·영문명을 사진 위에.
       opts: tag(h2 기본|h3), href(있으면 성분명을 링크로), badge(배지 HTML). 스타일은 style.css .ing-band* */
    ingBand: function (it, opts) {
      opts = opts || {};
      var tag = opts.tag || "h2", m = Illus.ingPhotoUrl(it.id, "m"), full = Illus.ingPhotoUrl(it.id);
      var name = opts.href ? '<a href="' + esc(opts.href) + '">' + esc(it.name) + "</a>" : esc(it.name);
      return '<div class="ing-band"><img class="ing-band-img" src="' + m + '" srcset="' + m + ' 360w, ' + full + ' 640w" sizes="(min-width: 768px) 360px, 100vw" alt="" width="360" height="360" loading="lazy" decoding="async"' + Illus.ingPhotoFallback("m", true) + '>' +
        (opts.badge ? '<span class="ing-band-badge">' + opts.badge + "</span>" : "") +
        '<div class="ing-band-title"><' + tag + ' class="ing-band-name">' + name + "</" + tag + ">" + (it.en ? '<p class="ing-band-en">' + esc(it.en) + "</p>" : "") + "</div></div>";
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
  if (typeof window !== "undefined") window.Illus = Illus;
  if (typeof module !== "undefined") module.exports = Illus;   // node --test tests/illus.test.mjs
})();
