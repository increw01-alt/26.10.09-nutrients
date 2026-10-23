// 장기 복용 점검(assets/js/longterm.js) 테스트. 실행: node --test tests/longterm.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const req = createRequire(import.meta.url);
const S = req("../assets/js/store.js"), L = req("../assets/js/longterm.js");
const core = { byId: { zinc: { id: "zinc", name: "아연" }, "vitamin-b6": { id: "vitamin-b6", name: "비타민 B6" }, omega: { id: "omega", name: "오메가3" } } };
const rules = { _meta: { sources: [{ id: "nih-zinc", title: "NIH 아연" }, { id: "efsa-b6", title: "EFSA B6" }] },
  items: [{ id: "zinc", kind: "upper", weeks: 12, note: "아연 안내", source: "nih-zinc" }, { id: "vitamin-b6", kind: "upper", weeks: 12, note: "B6 안내", source: "efsa-b6" }] };
const iso = (d) => new Date(2026, 9, d).toISOString();
function state(items) { const s = S.empty(); s.items = items; return s; }

test("weeksBetween", () => assert.equal(L.weeksBetween(iso(1), new Date(2026, 9, 22)), 3));
test("check: 시작일로부터 weeks 가 지난 성분만, 규칙 없는 성분·지나지 않은 성분은 제외", () => {
  const s = state([{ id: "zinc", addedAt: new Date(2026, 6, 1).toISOString() }, { id: "omega", addedAt: new Date(2026, 0, 1).toISOString() }, { id: "vitamin-b6", addedAt: iso(20) }]);
  const r = L.check(s, rules, core, new Date(2026, 9, 23));
  assert.deepEqual(r.map(x => x.key), ["zinc"]); assert.equal(r[0].name, "아연"); assert.equal(r[0].kind, "upper"); assert.equal(r[0].weeks, 12); assert.ok(r[0].elapsedWeeks >= 16);
  assert.equal(r[0].note, "아연 안내"); assert.equal(r[0].sourceTitle, "NIH 아연"); assert.equal(r[0].viaProduct, null);
});
test("check: 제품 안 성분도 점검하되 제품명을 함께, 같은 성분이 따로도 있으면 한 번만", () => {
  const s = state([{ id: "p:1", name: "센트룸", ings: ["zinc", "vitamin-b6"], addedAt: new Date(2026, 6, 1).toISOString() }, { id: "zinc", addedAt: new Date(2026, 6, 1).toISOString() }]);
  const r = L.check(s, rules, core, new Date(2026, 9, 23));
  assert.deepEqual(r.map(x => x.key + "/" + x.id), ["p:1/vitamin-b6", "zinc/zinc"]); assert.equal(r[0].viaProduct, "센트룸");
});
test("check: 쉬는 항목은 제외, '계속 먹기'(ltCheckedAt)·'다시 먹기'(addedAt 갱신) 뒤에는 weeks 가 다시 지나야 뜬다", () => {
  let s = state([{ id: "zinc", addedAt: new Date(2026, 6, 1).toISOString() }]);
  assert.equal(L.check(S.pauseItem(s, "zinc", iso(1)), rules, core, new Date(2026, 9, 23)).length, 0);
  const checked = S.markChecked(s, "zinc", iso(1));
  assert.equal(L.check(checked, rules, core, new Date(2026, 9, 23)).length, 0);
  assert.equal(L.check(checked, rules, core, new Date(2027, 0, 1)).length, 1);
  assert.equal(L.check(S.resumeItem(S.pauseItem(s, "zinc", iso(1)), "zinc", iso(20)), rules, core, new Date(2026, 9, 23)).length, 0);
});
