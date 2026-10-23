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

// ---- 최종 검토 반영: 알림 동작 라우팅(순수)·런타임 버전 고정 ----
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
const here = dirname(fileURLToPath(import.meta.url));

function env(page, consumed) { const log = []; return { log, env: { page, dispatch: () => { log.push("dispatch"); return consumed; }, store: (d) => log.push("store:" + d.actionId), navigate: () => log.push("navigate") } }; }
test("routeAction: 내 영양제 페이지에서 리스너가 받으면 저장·이동 없음", () => {
  const { log, env: e } = env("my", true); A.routeAction({ actionId: "done" }, e); assert.deepEqual(log, ["dispatch"]);
});
test("routeAction: 내 영양제 페이지인데 리스너가 아직 없으면(콜드 스타트) 저장만 한다", () => {
  const { log, env: e } = env("my", false); A.routeAction({ actionId: "done" }, e); assert.deepEqual(log, ["dispatch", "store:done"]);
});
test("routeAction: 다른 페이지면 저장하고 내 영양제로 이동", () => {
  const { log, env: e } = env("ingredients", false); A.routeAction({ actionId: "snooze" }, e); assert.deepEqual(log, ["dispatch", "store:snooze", "navigate"]);
});
test("VENDOR_VERSION 은 app/package.json 의 @capacitor/core 버전과 같다(런타임 캐시 무효화 키)", () => {
  const pkg = JSON.parse(readFileSync(join(here, "..", "app", "package.json"), "utf8"));
  assert.equal(A.VENDOR_VERSION, pkg.dependencies["@capacitor/core"]);
});

// ---- 앱 시작: 웹뷰 저장소가 비면 앱 저장소 복제본에서 복원 (10-23) ----
test("restoreIfEmpty: 로컬에 있으면 복원하지 않는다", async () => {
  let wrote = null; const ok = await A.restoreIfEmpty({ hasLocal: () => true, restore: async () => "{}", write: (j) => { wrote = j; } });
  assert.equal(ok, false); assert.equal(wrote, null);
});
test("restoreIfEmpty: 비어 있고 복제본이 있으면 써 넣고 true", async () => {
  let wrote = null; const ok = await A.restoreIfEmpty({ hasLocal: () => false, restore: async () => '{"v":2}', write: (j) => { wrote = j; } });
  assert.equal(ok, true); assert.equal(wrote, '{"v":2}');
});
test("restoreIfEmpty: 복제본이 없거나 restore 가 실패해도 false 로 끝난다", async () => {
  assert.equal(await A.restoreIfEmpty({ hasLocal: () => false, restore: async () => null, write: () => {} }), false);
  assert.equal(await A.restoreIfEmpty({ hasLocal: () => { throw new Error("x"); }, restore: async () => { throw new Error("y"); }, write: () => {} }), false);
});

// ---- 최종 검토 반영: 복원은 defer 스크립트(store.js)가 모두 실행된 뒤(DOMContentLoaded)에 — defer 실행 중 readyState 는 이미 "interactive" ----
test("waitForScripts: interactive(파싱 끝, defer 실행 중)면 DOMContentLoaded 까지 기다린다", async () => {
  let fired = null; let done = false;
  A.waitForScripts({ readyState: "interactive", addEventListener: (ev, fn) => { if (ev === "DOMContentLoaded") fired = fn; } }).then(() => { done = true; });
  await Promise.resolve(); assert.equal(done, false); assert.equal(typeof fired, "function");
  fired(); await Promise.resolve(); await Promise.resolve(); assert.equal(done, true);
});
test("waitForScripts: complete 면 바로 resolve", async () => {
  let called = false; await A.waitForScripts({ readyState: "complete", addEventListener: () => { called = true; } }); assert.equal(called, false);
});

// ---- 앱 첫 실행: 옛 빌드(시작 주소 /my)도 홈(today)으로 — 세션당 한 번, 가져오기 링크는 제외 (10-23) ----
test("coldStartTarget: 앱에서 처음 연 페이지가 내 영양제면 today.html, 이미 시작했으면 null", () => {
  assert.equal(A.coldStartTarget({ native: true, page: "my", started: false, hash: "" }), "today.html");
  assert.equal(A.coldStartTarget({ native: true, page: "my", started: true, hash: "" }), null);
});
test("coldStartTarget: 웹·다른 페이지·가져오기 링크(#import=)는 보내지 않는다", () => {
  assert.equal(A.coldStartTarget({ native: false, page: "my", started: false, hash: "" }), null);
  assert.equal(A.coldStartTarget({ native: true, page: "today", started: false, hash: "" }), null);
  assert.equal(A.coldStartTarget({ native: true, page: "my", started: false, hash: "#import=YJ1-abc" }), null);
});
