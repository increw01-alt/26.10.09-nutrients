// 서비스워커 템플릿(scripts/sw_template.js)의 라우팅 판단 테스트. 실행: node --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const { strategyFor, VERSION, cacheKeyCandidates, stripRedirect, cacheNames, keysToTrim, CACHE_LIMIT } = createRequire(import.meta.url)("../scripts/sw_template.js");
const O = "https://xn--og5b1hx9c.kr";

// 검토 보완: Cloudflare 는 /foo.html → /foo 로 리다이렉트하므로 캐시 키 후보와 redirected 응답 처리가 필요하다
test("해시 없는 같은 origin 자산(이미지 등)은 revalidate", () => assert.equal(strategyFor(O + "/assets/images/home/leaf.webp", "GET", "no-cors", O), "revalidate"));
test(".html 주소의 캐시 키 후보에 확장자 없는 주소가 따라온다", () => assert.deepEqual(cacheKeyCandidates(O + "/i/zinc.html"), [O + "/i/zinc.html", O + "/i/zinc"]));
test("index.html 의 캐시 키 후보는 루트", () => assert.deepEqual(cacheKeyCandidates(O + "/index.html?source=pwa"), [O + "/index.html?source=pwa", O + "/?source=pwa"]));
test("확장자 없는 주소는 .html 키도 후보 — 한 번도 안 연 /my 를 오프라인에서 precache(/my.html)로 연다", () => assert.deepEqual(cacheKeyCandidates(O + "/my"), [O + "/my", O + "/my.html"]));
test("루트는 /index.html 도 후보", () => assert.deepEqual(cacheKeyCandidates(O + "/?source=pwa"), [O + "/?source=pwa", O + "/index.html?source=pwa"]));
test("확장자가 있는 파일 주소는 후보가 하나", () => assert.deepEqual(cacheKeyCandidates(O + "/data/meta.json"), [O + "/data/meta.json"]));
test("캐시 이름은 버전을 품고 fonts 만 고정", () => assert.deepEqual(cacheNames("abc12345"), { static: "static-abc12345", pages: "pages-abc12345", data: "data-abc12345", fonts: "fonts-v1" }));
test("캐시 상한을 넘기면 먼저 넣은 키부터 지운다", () => {
  assert.deepEqual(keysToTrim(["a", "b", "c", "d"], 2), ["a", "b"]);
  assert.deepEqual(keysToTrim(["a", "b"], 2), []);
  assert.deepEqual(keysToTrim(["a"], 0), []);
  assert.ok(CACHE_LIMIT.pages > 0 && CACHE_LIMIT.data > 0 && CACHE_LIMIT.fonts > 0);
});
test("redirected 응답은 새 Response 로 감싸 redirected=false 가 된다", async () => {
  const out = stripRedirect({ redirected: true, status: 200, statusText: "OK", headers: new Headers({ "content-type": "text/html" }), body: "<p>hi</p>" });
  assert.equal(out.redirected, false);
  assert.equal(out.status, 200);
  assert.equal(await out.text(), "<p>hi</p>");
});
test("redirected 가 아니면 같은 객체를 돌려준다", () => { const r = new Response("x"); assert.equal(stripRedirect(r), r); });

test("같은 origin 페이지 이동은 page", () => assert.equal(strategyFor(O + "/i/zinc", "GET", "navigate", O), "page"));
test("해시 자산은 asset", () => assert.equal(strategyFor(O + "/assets/js/data.js?v=abc12345", "GET", "no-cors", O), "asset"));
test("데이터 JSON 은 data", () => assert.equal(strategyFor(O + "/data/ingredients.json", "GET", "cors", O), "data"));
test("폰트 CDN 은 font", () => assert.equal(strategyFor("https://fonts.gstatic.com/s/x.woff2", "GET", "cors", O), "font"));
test("POST 는 bypass", () => assert.equal(strategyFor(O + "/data/x.json", "POST", "cors", O), "bypass"));
test("분석 스크립트는 bypass", () => assert.equal(strategyFor("https://www.googletagmanager.com/gtag/js?id=G-X", "GET", "no-cors", O), "bypass"));
test("제휴 링크는 bypass", () => assert.equal(strategyFor("https://link.coupang.com/a/x", "GET", "navigate", O), "bypass"));
test("템플릿의 버전 자리표시자", () => assert.equal(VERSION, "__VERSION__"));
