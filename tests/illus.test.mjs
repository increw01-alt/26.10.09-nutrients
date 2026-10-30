// 성분 실사 사진 헬퍼(assets/js/illus.js) — 목록 띠(ingBand)·썸네일(ingThumb)·주소(ingPhotoUrl). 빌드 쪽 같은 역할은 scripts/build_site.py 의 ing_thumb_img·photo_src.
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Illus = require("../assets/js/illus.js");

const IT = { id: "garcinia", name: "가르시니아 (HCA)", en: "Garcinia Cambogia (HCA)", category: "herbal" };

test("ingPhotoUrl: 크기 접미사 없음·m·s (Node 에선 루트 없이)", () => {
  assert.equal(Illus.ingPhotoUrl("garcinia"), "assets/images/ingredients/garcinia.webp");
  assert.equal(Illus.ingPhotoUrl("garcinia", "m"), "assets/images/ingredients/garcinia-m.webp");
  assert.equal(Illus.ingPhotoUrl("garcinia", "s"), "assets/images/ingredients/garcinia-s.webp");
});

test("ingThumb: 160px 썸네일, lazy, 클래스 전달, id 이스케이프, 없는 사진은 onerror 로 _default-s", () => {
  const fb = ' onerror="this.onerror=null;this.src=\'assets/images/ingredients/_default-s.webp\'"';
  assert.equal(Illus.ingThumb(IT, "h-full w-full object-cover"),
    '<img src="assets/images/ingredients/garcinia-s.webp" alt="" width="160" height="160" loading="lazy" decoding="async"' + fb + ' class="h-full w-full object-cover">');
  assert.equal(Illus.ingThumb({ id: "zinc" }), '<img src="assets/images/ingredients/zinc-s.webp" alt="" width="160" height="160" loading="lazy" decoding="async"' + fb + '>');
  assert.ok(!Illus.ingThumb({ id: 'a"b' }).includes('a"b'));
});

test("ingPhotoFallback: 사진 파일이 없는 새 성분은 404 대신 _default 로 (띠는 srcset 까지)", () => {
  assert.equal(Illus.ingPhotoFallback("s"), ' onerror="this.onerror=null;this.src=\'assets/images/ingredients/_default-s.webp\'"');
  assert.equal(Illus.ingPhotoFallback("m", true), ' onerror="this.onerror=null;this.srcset=\'assets/images/ingredients/_default-m.webp\';this.src=\'assets/images/ingredients/_default-m.webp\'"');
  assert.equal(Illus.ingPhotoFallback(), ' onerror="this.onerror=null;this.src=\'assets/images/ingredients/_default.webp\'"');
  assert.ok(Illus.ingBand(IT).includes(Illus.ingPhotoFallback("m", true)));
});

test("ingBand: 360 src + 640 srcset, 배지, 제목(h2 기본)·영문명", () => {
  const html = Illus.ingBand(IT, { badge: '<span class="badge">식물성·허브</span>' });
  assert.ok(html.startsWith('<div class="ing-band"><img class="ing-band-img" src="assets/images/ingredients/garcinia-m.webp" srcset="assets/images/ingredients/garcinia-m.webp 360w, assets/images/ingredients/garcinia.webp 640w" sizes="(min-width: 768px) 360px, 100vw" alt="" width="360" height="360" loading="lazy" decoding="async"' + Illus.ingPhotoFallback("m", true) + '>'));
  assert.ok(html.includes('<span class="ing-band-badge"><span class="badge">식물성·허브</span></span>'));
  assert.ok(html.endsWith('<div class="ing-band-title"><h2 class="ing-band-name">가르시니아 (HCA)</h2><p class="ing-band-en">Garcinia Cambogia (HCA)</p></div></div>'));
});

test("ingBand: tag h3 + href 면 제목이 링크, 배지 없으면 생략, 이름 이스케이프", () => {
  const html = Illus.ingBand({ id: "x", name: "A<B", en: "" }, { tag: "h3", href: "i/x.html" });
  assert.ok(html.includes('<h3 class="ing-band-name"><a href="i/x.html">A&lt;B</a></h3>'));
  assert.ok(!html.includes("ing-band-badge"));
  assert.ok(!html.includes("ing-band-en"));   // 영문명이 비면 줄을 만들지 않는다
});
