// 셀프체크 로직(assets/js/finder.js) 테스트 — 실데이터(data/finder.json·guides-index.json·ingredients.json)로. 실행: node --test tests/finder.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const F = createRequire(import.meta.url)("../assets/js/finder.js");
const J = (p) => JSON.parse(readFileSync(new URL("../data/" + p, import.meta.url), "utf8"));
const data = J("finder.json"), guides = J("guides-index.json").items, ing = J("ingredients.json").items;
const core = { byId: Object.fromEntries(ing.map((i) => [i.id, i])) };
const bySlug = Object.fromEntries(guides.map((g) => [g.slug, g]));

test("parse: 모르는 값·초과 선택·단일 질문의 둘째 값은 버린다", () => {
  const a = F.parse("?age=30s,40s&sex=zzz&concern=fatigue,sleep,eye,gut&life=office&have=vitamin-d,<bad>,omega-3", data);
  assert.deepEqual(a.age, ["30s"]);
  assert.equal(a.sex, undefined);
  assert.deepEqual(a.concern, ["fatigue", "sleep", "eye"]);
  assert.deepEqual(a.have, ["vitamin-d", "omega-3"]);
  assert.deepEqual(F.parse("", data), {});
});

test("serialize ↔ parse 라운드트립, 질문 순서 고정", () => {
  const a = { concern: ["sleep", "fatigue"], age: ["20s"], have: ["magnesium"] };
  const s = F.serialize(a, data);
  assert.equal(s, "age=20s&concern=sleep%2Cfatigue&have=magnesium");
  assert.deepEqual(F.parse("?" + s, data), { age: ["20s"], concern: ["sleep", "fatigue"], have: ["magnesium"] });
});

test("matches: 질문끼리 AND, 질문 안은 OR", () => {
  assert.equal(F.matches({ age: ["30s"], sex: ["m"] }, { age: ["30s"], sex: ["m"] }), true);
  assert.equal(F.matches({ age: ["30s"], sex: ["m"] }, { age: ["30s"], sex: ["f"] }), false);
  assert.equal(F.matches({ concern: ["sleep", "fatigue"] }, { concern: ["fatigue"] }), true);
  assert.equal(F.matches({}, {}), true);
});

test("30대 남성 + 피로·수면 + 앉아서 근무 → 해당 가이드와 그 핵심 성분이 앞에 온다", () => {
  const r = F.score({ age: ["30s"], sex: ["m"], concern: ["fatigue", "sleep"], life: ["office"], meds: ["none"] }, data, guides, core);
  const slugs = r.guides.map((g) => g.slug);
  for (const s of ["30s-men", "fatigue", "sleep", "office-workers"]) assert.ok(slugs.includes(s), s);
  assert.ok(!slugs.includes("40s-women"));
  assert.ok(r.recommended.length >= 5);
  assert.ok(r.recommended.includes("magnesium"));          // 피로·수면·30대 남성·직장인 가이드 모두의 핵심 성분
  assert.equal(r.flags.length, 0);
  assert.equal(r.restricted, false);
  for (const id of r.recommended) assert.ok(core.byId[id], id);
});

test("이미 먹는 성분은 추천에서 빼되 목록(have)에는 남는다", () => {
  const r = F.score({ age: ["30s"], sex: ["m"], concern: ["fatigue"], have: ["magnesium", "zzz-unknown"] }, data, guides, core);
  assert.ok(!r.recommended.includes("magnesium"));
  assert.ok(r.ingredients.some((i) => i.id === "magnesium"));
  assert.deepEqual(r.have, ["magnesium"]);               // 사전에 없는 id 는 제외
});

test("어린이 + 다이어트 고민 → 어린이 가이드 성분 범위로 제한(가르시니아 없음), kids 플래그", () => {
  const r = F.score({ age: ["kids"], concern: ["diet", "eye"] }, data, guides, core);
  const allowed = new Set([...bySlug["kids"].ingredients, ...bySlug["kids-by-age"].ingredients].map((i) => i.id));
  assert.ok(r.recommended.length > 0);
  for (const id of r.recommended) assert.ok(allowed.has(id), id);
  assert.ok(!r.recommended.includes("garcinia"));
  assert.ok(r.flags.includes("kids"));
  assert.equal(r.restricted, true);
});

test("임신 중 → 임신 가이드 성분 범위로 제한(홍삼·가르시니아 없음), pregnancy 플래그", () => {
  const r = F.score({ age: ["30s"], sex: ["f"], concern: ["fatigue", "diet"], life: ["pregnant"] }, data, guides, core);
  const allowed = new Set([...bySlug["pregnancy"].ingredients, ...bySlug["pregnancy-symptoms"].ingredients].map((i) => i.id));
  for (const id of r.recommended) assert.ok(allowed.has(id), id);
  assert.ok(!r.recommended.includes("red-ginseng") && !r.recommended.includes("garcinia"));
  assert.ok(r.flags.includes("pregnancy"));
  assert.equal(r.guides[0].slug, "pregnancy");             // 가중치 4 로 가장 앞
});

test("약 복용 → meds 플래그와 약 복용자 가이드", () => {
  const r = F.score({ age: ["50s"], sex: ["m"], meds: ["thyroid", "hypertension"] }, data, guides, core);
  assert.ok(r.flags.includes("meds"));
  const slugs = r.guides.map((g) => g.slug);
  assert.ok(slugs.includes("thyroid") && slugs.includes("hypertension") && slugs.includes("50s-plus"));
});

test("규칙·질문 데이터 무결성: 가이드 slug·옵션 id·인기 성분 id 가 모두 존재", () => {
  const qs = Object.fromEntries(data.questions.map((q) => [q.id, q]));
  for (const r of data.rules) {
    for (const [q, vals] of Object.entries(r.if)) { assert.ok(qs[q], q); for (const v of vals) assert.ok(qs[q].options.some((o) => o.id === v), q + ":" + v); }
    for (const s of [...(r.guides || []), ...(r.restrictTo || [])]) assert.ok(bySlug[s], s);
  }
  for (const id of qs.have.popular) assert.ok(core.byId[id], id);
  for (const q of data.questions) if (q.options) assert.equal(new Set(q.options.map((o) => o.id)).size, q.options.length, q.id);
});

test("summary: 고른 옵션 라벨만, '없음' 류(exclusive)는 제외", () => {
  const s = F.summary({ age: ["30s"], sex: ["na"], concern: ["fatigue", "none"], meds: ["none"], have: ["vitamin-d"] }, data);
  assert.deepEqual(s, ["30대", "답하지 않음", "피로·활력"]);
});

test("항응고제 복용 → bleeding 플래그, 출혈 경향 성분은 추천에서 빠지고 avoided 에 점수순으로 남는다", () => {
  const r = F.score({ age: ["50s"], sex: ["m"], concern: ["circulation", "memory"], meds: ["anticoagulant"] }, data, guides, core);
  assert.ok(r.flags.includes("bleeding") && r.flags.includes("meds"));
  for (const id of ["ginkgo", "nattokinase", "omega-3", "red-ginseng", "vitamin-k", "coq10"]) assert.ok(!r.recommended.includes(id) && !r.ingredients.some((x) => x.id === id), id);
  assert.ok(r.avoided.includes("ginkgo") && r.avoided.includes("omega-3"));
  assert.ok(r.recommended.length >= 3);
  assert.ok(r.guides.map((g) => g.slug).includes("with-medication"));
  const plain = F.score({ age: ["50s"], sex: ["m"], concern: ["circulation", "memory"], meds: ["none"] }, data, guides, core);
  assert.ok(plain.recommended.includes("omega-3") && plain.avoided.length === 0 && plain.avoidedHave.length === 0);
});

test("수술 예정 → 출혈 경향 성분 제외, 이미 먹는 성분이 제외 대상이면 avoidedHave 에 표시", () => {
  const r = F.score({ age: ["40s"], sex: ["f"], concern: ["joint"], meds: ["surgery"], have: ["ginkgo", "vitamin-c"] }, data, guides, core);
  assert.ok(r.flags.includes("surgery"));
  assert.deepEqual(r.avoidedHave, ["ginkgo"]);
  assert.ok(r.have.includes("ginkgo") && r.have.includes("vitamin-c"));
  assert.ok(!r.recommended.includes("omega-3"));
});

test("기억력 고민 → 기억력 가이드와 핵심 성분(오메가3·포스파티딜세린)이 상위에 온다", () => {
  const r = F.score({ age: ["50s"], sex: ["f"], concern: ["memory"], meds: ["none"] }, data, guides, core);
  assert.ok(r.guides.map((g) => g.slug).includes("memory"));
  for (const id of ["omega-3", "phosphatidylserine"]) assert.ok(r.recommended.slice(0, 5).includes(id), id);
});

test("뼈 고민 → 뼈 건강 가이드와 칼슘·비타민D 상위; 혈압 고민 + 혈압약 → 코엔자임Q10 추천·칼륨 제외; 신장질환 → 칼륨·마그네슘 제외", () => {
  const b = F.score({ age: ["50s"], sex: ["f"], concern: ["bone"], meds: ["none"] }, data, guides, core);
  assert.ok(b.guides.map((g) => g.slug).includes("bone-health"));
  for (const id of ["calcium", "vitamin-d"]) assert.ok(b.recommended.slice(0, 5).includes(id), id);
  const p = F.score({ age: ["50s"], sex: ["m"], concern: ["blood-pressure"], meds: ["hypertension"] }, data, guides, core);
  const slugs = p.guides.map((g) => g.slug);
  assert.ok(slugs.includes("blood-pressure") && slugs.includes("hypertension"));
  assert.ok(p.recommended.includes("coq10") && !p.recommended.includes("potassium") && p.avoided.includes("potassium"));
  const k = F.score({ age: ["50s"], sex: ["m"], concern: ["blood-pressure", "sleep"], meds: ["kidney"] }, data, guides, core);
  for (const id of ["potassium", "magnesium"]) assert.ok(!k.recommended.includes(id) && !k.ingredients.some((x) => x.id === id), id);
  assert.ok(k.flags.includes("kidney"));
});

test("생활 '술자리가 잦아요' → 간 건강 가이드와 밀크씨슬, '햇빛을 거의 못 봐요' → 비타민D 가이드", () => {
  const d = F.score({ age: ["40s"], sex: ["m"], life: ["drinker"], meds: ["none"] }, data, guides, core);
  assert.ok(d.guides.map((g) => g.slug).includes("liver-health"));
  assert.ok(d.recommended.slice(0, 5).includes("milk-thistle"));
  const i = F.score({ age: ["30s"], sex: ["f"], life: ["indoor", "office"], meds: ["none"] }, data, guides, core);
  assert.ok(i.guides.map((g) => g.slug).includes("vitamin-d-guide"));
  assert.ok(i.recommended.slice(0, 3).includes("vitamin-d"));
});

// ---- 맞춤 추천의 근거 칩: 추천 가이드를 고른 규칙의 조건 가운데 내가 답한 라벨 (10-23) ----
test("reasons: 추천 가이드를 고른 규칙의 조건 가운데 내가 답한 라벨만, 질문 순서로 중복 없이", () => {
  const data = { questions: [{ id: "age", type: "single", options: [{ id: "40s", label: "40대" }] }, { id: "concern", type: "multi", options: [{ id: "eye", label: "눈 건강" }, { id: "sleep", label: "수면" }] }],
    rules: [{ if: { concern: ["eye"] }, guides: ["eye"] }, { if: { age: ["40s"], concern: ["eye", "sleep"] }, guides: ["eye", "aging"] }, { if: { concern: ["sleep"] }, guides: ["sleep"] }] };
  assert.deepEqual(F.reasons({ age: ["40s"], concern: ["eye"] }, data, ["eye"]), ["40대", "눈 건강"]);
  assert.deepEqual(F.reasons({ age: ["40s"], concern: ["sleep"] }, data, ["sleep"]), ["수면"]);   // 수면 가이드를 고른 규칙은 셋째뿐
});

// ---- 최종 검토 미룬 지적 #10: 주의 상자 문구를 셀프체크·맞춤 추천이 공유 ----
test("FLAG_TEXT: 규칙의 flags 가 모두 문구를 갖고, 각 문구에 title·body·link 가 있다", () => {
  const flags = new Set(); data.rules.forEach(r => (r.flags || []).forEach(f => flags.add(f)));
  for (const f of flags) { const t = F.FLAG_TEXT[f]; assert.ok(t, f); assert.ok(t.title && t.body && t.link, f); }
});
