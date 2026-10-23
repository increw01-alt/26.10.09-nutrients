// 내 영양제 저장 모듈(assets/js/store.js) 테스트. 실행: node --test tests/store.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const S = createRequire(import.meta.url)("../assets/js/store.js");

function fakeStorage(init) { const m = new Map(Object.entries(init || {})); return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), map: m }; }
const throwing = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };

test("empty: 스키마 v2, 기본 시각 6개, logEnabled 는 null", () => {
  const s = S.empty();
  assert.equal(s.v, 2); assert.deepEqual(s.items, []);
  assert.equal(s.settings.times.morning_after, "08:00"); assert.equal(s.settings.times.bedtime, "22:30");
  assert.equal(s.settings.logEnabled, null); assert.equal(s.settings.remindersOn, false);
});
test("load: 저장소가 throw 하면 빈 상태", () => assert.deepEqual(S.load(throwing), S.empty()));
test("load: 깨진 JSON·다른 버전은 빈 상태", () => {
  assert.deepEqual(S.load(fakeStorage({ "yj.my.v1": "{nope" })), S.empty());
  assert.deepEqual(S.load(fakeStorage({ "yj.my.v1": JSON.stringify({ v: 3, items: [{ id: "zinc" }] }) })), S.empty());
});
test("load: 빠진 설정 키는 기본값으로 채운다", () => {
  const s = S.load(fakeStorage({ "yj.my.v1": JSON.stringify({ v: 1, items: [{ id: "zinc", addedAt: "2026-10-20T00:00:00Z" }], settings: { showNames: false }, log: {} }) }));
  assert.equal(s.items[0].id, "zinc"); assert.equal(s.settings.showNames, false); assert.equal(s.settings.times.bedtime, "22:30"); assert.equal(s.settings.weekends, true);
});
test("save: throw 를 삼키고 false, 성공하면 true 와 저장 내용", () => {
  assert.equal(S.save(S.empty(), throwing), false);
  const st = fakeStorage(); assert.equal(S.save(S.empty(), st), true); assert.equal(JSON.parse(st.map.get("yj.my.v1")).v, 2);
});
test("addItems: 중복·빈 값 제외, 입력 상태는 그대로", () => {
  const s0 = S.empty(); const r = S.addItems(s0, ["zinc", "zinc", "", "vitamin-d"]);
  assert.deepEqual(r.added, ["zinc", "vitamin-d"]); assert.equal(r.state.items.length, 2); assert.equal(s0.items.length, 0);
  assert.deepEqual(S.addItems(r.state, ["zinc"]).added, []);
});
test("removeItem·setSlot·overrides", () => {
  let s = S.addItems(S.empty(), ["zinc", "magnesium"]).state;
  s = S.setSlot(s, "magnesium", "morning_after"); assert.deepEqual(S.overrides(s), { magnesium: "morning_after" });
  assert.deepEqual(S.overrides(S.setSlot(s, "magnesium", "nope")), { magnesium: "morning_after" });
  assert.deepEqual(S.overrides(S.setSlot(s, "magnesium", null)), {});
  assert.equal(S.removeItem(s, "zinc").items.length, 1);
});
test("setTime·setSetting·setSlotOn 검증", () => {
  const s = S.empty();
  assert.equal(S.setTime(s, "bedtime", "23:15").settings.times.bedtime, "23:15");
  assert.equal(S.setTime(s, "bedtime", "25:00").settings.times.bedtime, "22:30");
  assert.equal(S.setSetting(s, "logEnabled", true).settings.logEnabled, true);
  assert.equal(S.setSetting(s, "hacker", true).settings.hacker, undefined);
  assert.equal(S.setSlotOn(s, "bedtime", false).settings.slotOn.bedtime, false);
});
test("pruneUnknown: 사전에 없는 id 는 제거하고 알려 준다", () => {
  const s = S.addItems(S.empty(), ["zinc", "gone"]).state;
  const r = S.pruneUnknown(s, { zinc: {} });
  assert.deepEqual(r.removed, ["gone"]); assert.deepEqual(r.state.items.map(i => i.id), ["zinc"]);
});

// ---- Task 2: 복용 기록·날짜·통계 ----
test("dateKey 는 현지 날짜", () => assert.equal(S.dateKey(new Date(2026, 9, 20, 23, 30)), "2026-10-20"));
test("addDays·lastDays", () => {
  assert.equal(S.addDays("2026-10-20", -1), "2026-10-19"); assert.equal(S.addDays("2026-10-31", 1), "2026-11-01");
  assert.deepEqual(S.lastDays("2026-10-20", 3), ["2026-10-18", "2026-10-19", "2026-10-20"]);
});
test("markDue·toggleDone·dayStats", () => {
  let s = S.markDue(S.empty(), "2026-10-20", ["morning_after", "bedtime"]);
  s = S.toggleDone(s, "2026-10-20", "morning_after", true);
  s = S.toggleDone(s, "2026-10-20", "nope", true);
  assert.deepEqual(S.dayStats(s, "2026-10-20"), { due: 2, done: 1, complete: false });
  s = S.toggleDone(s, "2026-10-20", "bedtime", true);
  assert.equal(S.dayStats(s, "2026-10-20").complete, true);
  s = S.markDue(s, "2026-10-20", ["morning_after"]);   // 시간표가 줄면 due 가 줄고 done 도 그에 맞춤
  assert.deepEqual(S.dayStats(s, "2026-10-20"), { due: 1, done: 1, complete: true });
  assert.deepEqual(S.dayStats(S.markDue(s, "2026-10-20", []), "2026-10-20"), { due: 0, done: 0, complete: false });
});
test("streak: 오늘 미완료면 어제부터 센다", () => {
  let s = S.empty();
  for (const k of ["2026-10-17", "2026-10-18", "2026-10-19"]) { s = S.markDue(s, k, ["morning_after"]); s = S.toggleDone(s, k, "morning_after", true); }
  s = S.markDue(s, "2026-10-20", ["morning_after"]);
  assert.equal(S.streak(s, "2026-10-20"), 3);
  assert.equal(S.streak(S.toggleDone(s, "2026-10-20", "morning_after", true), "2026-10-20"), 4);
  assert.equal(S.streak(S.markDue(s, "2026-10-18", []), "2026-10-20"), 1);   // 중간이 비면 끊김
  assert.equal(S.streak(S.empty(), "2026-10-20"), 0);
});
test("clearLog", () => assert.deepEqual(S.clearLog(S.markDue(S.empty(), "2026-10-20", ["bedtime"])).log, {}));

// ---- Task 3: 내보내기·가져오기 ----
test("exportCode ↔ importCode 왕복, 기본 시각은 생략", () => {
  let s = S.addItems(S.empty(), ["zinc", "magnesium"]).state;
  s = S.setSlot(s, "magnesium", "morning_after"); s = S.setTime(s, "bedtime", "23:00"); s = S.setSetting(s, "weekends", false);
  const code = S.exportCode(s);
  assert.match(code, /^YJ1-[A-Za-z0-9_-]+$/);
  const p = S.importCode(code);
  assert.deepEqual(p.items, [{ id: "zinc", slot: null }, { id: "magnesium", slot: "morning_after" }]);
  assert.deepEqual(p.times, { bedtime: "23:00" }); assert.deepEqual(p.opts, { names: true, weekends: false });
});
test("importCode: URL 이나 import= 가 섞여도 코드만 뽑는다", () => {
  const code = S.exportCode(S.addItems(S.empty(), ["zinc"]).state);
  assert.equal(S.importCode("https://xn--og5b1hx9c.kr/my.html?x=1#import=" + encodeURIComponent(code)).items[0].id, "zinc");
  assert.equal(S.importCode("  " + code + "\n").items[0].id, "zinc");
});
test("importCode: 깨진 입력은 null", () => {
  for (const bad of ["", "garbage", "YJ1-!!!", "YJ1-" + btoa("{nope"), "YJ1-" + btoa(JSON.stringify({ v: 3, items: [] })), "YJ1-" + btoa(JSON.stringify({ v: 1, items: "x" }))]) assert.equal(S.importCode(bad), null, bad);
});
test("merge: 모르는 id 는 skipped 로, merge 는 기존 유지, replace 는 교체", () => {
  const byId = { zinc: {}, magnesium: {}, iron: {} };
  const base = S.setSlot(S.addItems(S.empty(), ["zinc"]).state, "zinc", "bedtime");
  const payload = { items: [{ id: "magnesium", slot: "morning_after" }, { id: "zinc", slot: null }, { id: "ghost", slot: null }], times: { bedtime: "23:00" }, opts: { names: false, weekends: true } };
  const m = S.merge(base, payload, "merge", byId);
  assert.deepEqual(m.added, ["magnesium"]); assert.deepEqual(m.skipped, ["ghost"]);
  assert.deepEqual(m.state.items.map(i => i.id), ["zinc", "magnesium"]); assert.deepEqual(S.overrides(m.state), { zinc: "bedtime", magnesium: "morning_after" });
  assert.equal(m.state.settings.times.bedtime, "23:00"); assert.equal(m.state.settings.showNames, false);
  const r = S.merge(base, payload, "replace", byId);
  assert.deepEqual(r.state.items.map(i => i.id), ["magnesium", "zinc"]); assert.deepEqual(S.overrides(r.state), { magnesium: "morning_after" });
});
test("exportUrl 은 해시 조각(#import=)을 쓴다 — 서버·분석 도구·SW 캐시 키에 실리지 않게", () => assert.equal(S.exportUrl("YJ1-abc", "./"), "./my.html#import=YJ1-abc"));
test("importCode: #import= 링크와 옛 ?import= 링크 둘 다 읽는다", () => {
  const code = S.exportCode(S.addItems(S.empty(), ["zinc"]).state);
  assert.equal(S.importCode("https://xn--og5b1hx9c.kr/my.html#import=" + encodeURIComponent(code)).items[0].id, "zinc");
  assert.equal(S.importCode("https://xn--og5b1hx9c.kr/my.html?import=" + encodeURIComponent(code)).items[0].id, "zinc");
});
test("exportCode ↔ importCode: 시간대별 알림 토글(slotOn)도 옮긴다", () => {
  const s = S.setSlotOn(S.addItems(S.empty(), ["zinc"]).state, "bedtime", false);
  const p = S.importCode(S.exportCode(s));
  assert.deepEqual(p.slotOn, { bedtime: false });
  const m = S.merge(S.empty(), p, "merge", { zinc: {} });
  assert.equal(m.state.settings.slotOn.bedtime, false); assert.equal(m.state.settings.slotOn.morning_after, true);
});

test("load: 기록은 날짜 키 + due/done 꼴만 받고 프로토타입 키·깨진 값은 버린다", () => {
  const raw = { v: 1, items: [], settings: {}, log: { "2026-10-20": { due: ["morning_after", "nope"], done: { morning_after: true, bedtime: true } }, "__proto__": { due: ["bedtime"], done: {} }, "constructor": 1, "2026-10-21": { due: [] }, "bad": { due: ["bedtime"], done: {} } } };
  const s = S.load(fakeStorage({ "yj.my.v1": JSON.stringify(raw) }));
  assert.deepEqual(Object.keys(s.log), ["2026-10-20"]);
  assert.deepEqual(s.log["2026-10-20"], { due: ["morning_after"], done: { morning_after: true } });
  assert.deepEqual(S.dayStats(s, "constructor"), { due: 0, done: 0, complete: false });   // 상속된 키는 기록으로 보지 않는다
  assert.equal(S.toggleDone(s, "toString", "bedtime", true), s);
});
test("merge replace: 알림 시각·시간대 켜짐을 기본값으로 되돌린 뒤 가져온 값만 덮는다", () => {
  let s = S.addItems(S.empty(), ["zinc"]).state;
  s = S.setTime(s, "bedtime", "23:30"); s = S.setSlotOn(s, "lunch_after", false);
  const payload = S.importCode(S.exportCode(S.setTime(S.addItems(S.empty(), ["magnesium"]).state, "morning_after", "07:00")));
  const r = S.merge(s, payload, "replace", { magnesium: {}, zinc: {} });
  assert.deepEqual(r.state.items.map((i) => i.id), ["magnesium"]);
  assert.equal(r.state.settings.times.bedtime, "22:30"); assert.equal(r.state.settings.times.morning_after, "07:00"); assert.equal(r.state.settings.slotOn.lunch_after, true);
  const m = S.merge(s, payload, "merge", { magnesium: {}, zinc: {} });   // 합치기는 기존 설정 유지
  assert.equal(m.state.settings.times.bedtime, "23:30"); assert.equal(m.state.settings.slotOn.lunch_after, false);
});
test("exportUrl: 기본은 my.html, 확장자 없는 운영 주소 형태도 만든다", () => {
  assert.equal(S.exportUrl("YJ1-abc", "https://xn--og5b1hx9c.kr/"), "https://xn--og5b1hx9c.kr/my.html#import=YJ1-abc");
  assert.equal(S.exportUrl("YJ1-abc", "https://xn--og5b1hx9c.kr/", true), "https://xn--og5b1hx9c.kr/my#import=YJ1-abc");
});

// ---- 알림 시각 시·분 선택 (10-22) ----
test("timeChoices: 저장된 HH:MM 을 시·분 선택 값과 목록(시 0~23, 분 5분 단위)으로 푼다", () => {
  const c = S.timeChoices("07:30");
  assert.equal(c.hour, "07"); assert.equal(c.minute, "30");
  assert.equal(c.hours.length, 24); assert.equal(c.hours[0], "00"); assert.equal(c.hours[23], "23");
  assert.deepEqual(c.minutes, ["00", "05", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55"]);
});
test("timeChoices: 5분 단위가 아닌 저장값(옛 입력란)은 분 목록에 제자리로 끼워 넣어 선택이 유지된다", () => {
  const c = S.timeChoices("07:03");
  assert.equal(c.minute, "03"); assert.deepEqual(c.minutes.slice(0, 3), ["00", "03", "05"]); assert.equal(c.minutes.length, 13);
});
test("timeChoices: 깨진 값은 08:00 으로", () => { const c = S.timeChoices("x"); assert.equal(c.hour, "08"); assert.equal(c.minute, "00"); });

// ---- 스키마 v2: 제품 항목·내 정보·옮기기 코드 (10-23) ----
const FD = { questions: [{ id: "age", type: "single", options: [{ id: "40s" }, { id: "30s" }] }, { id: "concern", type: "multi", max: 3, options: [{ id: "eye" }, { id: "fatigue" }, { id: "sleep" }, { id: "skin" }] }, { id: "have", type: "ingredients" }] };
const P = { id: "p:1", name: "센트룸 맨", ings: ["vitamin-d", "zinc"] };
test("empty: v2", () => assert.equal(S.empty().v, 2));
test("addItems: 성분 id 와 제품 객체를 함께 받고 제품은 id·name·ings 로 저장", () => {
  const r = S.addItems(S.empty(), ["magnesium", P, "magnesium", { id: "x", name: "no" }]);
  assert.deepEqual(r.added, ["magnesium", "p:1"]);
  const p = r.state.items[1]; assert.equal(p.name, "센트룸 맨"); assert.deepEqual(p.ings, ["vitamin-d", "zinc"]); assert.ok(p.addedAt);
});
test("isProduct·entries·ingredientIds", () => {
  const s = S.addItems(S.empty(), ["magnesium", P, "zinc"]).state;
  assert.equal(S.isProduct("p:1"), true); assert.equal(S.isProduct("zinc"), false);
  assert.deepEqual(S.entries(s), ["magnesium", { id: "p:1", name: "센트룸 맨", ings: ["vitamin-d", "zinc"] }, "zinc"]);
  assert.deepEqual(S.ingredientIds(s), ["magnesium", "zinc", "vitamin-d"]);
});
test("load: v1 저장본을 그대로 읽고 v2 로 올린다", () => {
  const raw = JSON.stringify({ v: 1, items: [{ id: "magnesium", addedAt: "2026-10-01T00:00:00.000Z" }], settings: {}, log: {} });
  const s = S.load({ getItem: () => raw }); assert.equal(s.v, 2); assert.equal(s.items[0].id, "magnesium");
});
test("load: 제품 항목은 name·ings 가 맞을 때만, ings 는 문자열만", () => {
  const raw = JSON.stringify({ v: 2, items: [{ id: "p:1", name: "센트룸 맨", ings: ["zinc", 3] }, { id: "p:2", ings: [] }, { id: "p:3", name: "x" }], settings: {}, log: {} });
  const s = S.load({ getItem: () => raw }); assert.deepEqual(s.items.map(i => i.id), ["p:1"]); assert.deepEqual(s.items[0].ings, ["zinc"]);
});
test("setProfile: 질문·옵션 검증, single 1개, max 초과 자름, have 무시, 비면 삭제", () => {
  let s = S.setProfile(S.empty(), { age: ["40s", "30s"], concern: ["eye", "zzz", "fatigue", "sleep", "skin"], have: ["x"], bogus: ["1"] }, FD);
  assert.deepEqual(s.profile.age, ["40s"]); assert.deepEqual(s.profile.concern, ["eye", "fatigue", "sleep"]); assert.equal("have" in s.profile, false); assert.ok(s.profile.updatedAt);
  assert.deepEqual(S.profile(s).age, ["40s"]);
  s = S.setProfile(s, { age: ["zzz"] }, FD); assert.equal(S.profile(s), null); assert.equal("profile" in s, false);
});
test("load: profile 은 문자열 배열 값만 남긴다", () => {
  const raw = JSON.stringify({ v: 2, items: [], settings: {}, log: {}, profile: { age: ["40s"], concern: "eye", life: [1], updatedAt: "2026-10-23T00:00:00.000Z" } });
  assert.deepEqual(S.load({ getItem: () => raw }).profile, { age: ["40s"], updatedAt: "2026-10-23T00:00:00.000Z" });
});
test("exportCode ↔ importCode v2: 제품은 id·slot·name 만, profile 은 updatedAt 빼고", () => {
  let s = S.addItems(S.empty(), ["magnesium", P]).state; s = S.setSlot(s, "p:1", "evening_after"); s = S.setProfile(s, { age: ["40s"] }, FD);
  const code = S.exportCode(s); assert.ok(code.startsWith("YJ1-")); assert.equal(code.indexOf("zinc"), -1);
  const p = S.importCode(code);
  assert.deepEqual(p.items, [{ id: "magnesium", slot: null }, { id: "p:1", slot: "evening_after", name: "센트룸 맨" }]);
  assert.deepEqual(p.profile, { age: ["40s"] });
});
test("importCode: v1 코드도 읽는다(profile null)", () => {
  const v1 = "YJ1-" + Buffer.from(JSON.stringify({ v: 1, items: [["magnesium", 0]], times: {}, on: {}, opts: {} })).toString("base64url");
  const p = S.importCode(v1); assert.deepEqual(p.items, [{ id: "magnesium", slot: null }]); assert.equal(p.profile, null);
});
test("merge: 제품은 productIngs 로 성분을 채우고 없으면 빈 배열, 사전 검사 대상이 아니다", () => {
  const byId = { magnesium: {}, zinc: {} };
  const payload = { items: [{ id: "p:1", slot: null, name: "센트룸 맨" }, { id: "p:9", slot: "bedtime", name: "모름" }, { id: "nope", slot: null }], times: {}, slotOn: {}, opts: {}, profile: { age: ["40s"] } };
  const r = S.merge(S.empty(), payload, "merge", byId, { productIngs: { "p:1": ["zinc"] }, finderData: FD });
  assert.deepEqual(r.added, ["p:1", "p:9"]); assert.deepEqual(r.skipped, ["nope"]);
  assert.deepEqual(r.state.items[0].ings, ["zinc"]); assert.deepEqual(r.state.items[1].ings, []); assert.equal(r.state.items[1].slot, "bedtime");
  assert.deepEqual(r.state.profile.age, ["40s"]);
});
test("pruneUnknown: 제품은 남기고 안의 모르는 성분만 뺀다", () => {
  const s = S.addItems(S.empty(), [{ id: "p:1", name: "x", ings: ["zinc", "gone"] }, "gone"]).state;
  const r = S.pruneUnknown(s, { zinc: {} });
  assert.deepEqual(r.removed, ["gone"]); assert.deepEqual(r.state.items.map(i => i.id), ["p:1"]); assert.deepEqual(r.state.items[0].ings, ["zinc"]);
});
