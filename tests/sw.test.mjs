// 서비스워커 템플릿(scripts/sw_template.js)의 라우팅 판단 테스트. 실행: node --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const { strategyFor, VERSION } = createRequire(import.meta.url)("../scripts/sw_template.js");
const O = "https://xn--og5b1hx9c.kr";

test("같은 origin 페이지 이동은 page", () => assert.equal(strategyFor(O + "/i/zinc", "GET", "navigate", O), "page"));
test("해시 자산은 asset", () => assert.equal(strategyFor(O + "/assets/js/data.js?v=abc12345", "GET", "no-cors", O), "asset"));
test("데이터 JSON 은 data", () => assert.equal(strategyFor(O + "/data/ingredients.json", "GET", "cors", O), "data"));
test("폰트 CDN 은 font", () => assert.equal(strategyFor("https://fonts.gstatic.com/s/x.woff2", "GET", "cors", O), "font"));
test("POST 는 bypass", () => assert.equal(strategyFor(O + "/data/x.json", "POST", "cors", O), "bypass"));
test("분석 스크립트는 bypass", () => assert.equal(strategyFor("https://www.googletagmanager.com/gtag/js?id=G-X", "GET", "no-cors", O), "bypass"));
test("제휴 링크는 bypass", () => assert.equal(strategyFor("https://link.coupang.com/a/x", "GET", "navigate", O), "bypass"));
test("템플릿의 버전 자리표시자", () => assert.equal(VERSION, "__VERSION__"));
