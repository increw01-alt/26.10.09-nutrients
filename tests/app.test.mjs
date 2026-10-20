// 앱 모드 감지 모듈(assets/js/app.js) 테스트. 실행: node --test tests/app.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const A = createRequire(import.meta.url)("../assets/js/app.js");
const win = (o) => Object.assign({ location: { hostname: "xn--og5b1hx9c.kr", search: "" }, localStorage: { getItem: () => null } }, o);

test("detect: Capacitor 네이티브면 native", () => assert.equal(A.detect(win({ Capacitor: { isNativePlatform: () => true } })), "native"));
test("detect: Capacitor 객체가 있어도 웹이면 null", () => assert.equal(A.detect(win({ Capacitor: { isNativePlatform: () => false } })), null));
test("detect: localhost + appDev=1 이면 dev", () => assert.equal(A.detect(win({ location: { hostname: "localhost" }, localStorage: { getItem: (k) => (k === "appDev" ? "1" : null) } })), "dev"));
test("detect: 운영 도메인에서는 appDev 를 무시", () => assert.equal(A.detect(win({ localStorage: { getItem: () => "1" } })), null));
test("detect: 저장소가 throw 해도 null", () => assert.equal(A.detect(win({ location: { hostname: "localhost" }, localStorage: { getItem() { throw new Error("x"); } } })), null));
