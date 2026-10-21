// 용어 자동 링크(assets/js/terms.js) — scripts/build_site.py 의 TermLinker 와 같은 사례를 검사한다 (tests/test_build_site.py GlossaryTests 와 짝)
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Terms = require("../assets/js/terms.js");

const ITEMS = [
  { slug: "heme-iron", aliases: ["헴철"], short: "동물성 철" },
  { slug: "non-heme-iron", aliases: ["비헴철"], short: "식물성 철" },
  { slug: "rtg", aliases: ["rTG", "r-TG"], short: "재에스테르화 \"TG\"" },
  { slug: "ul", aliases: ["상한섭취량", "UL"], short: "상한" },
  { slug: "cfu", aliases: ["CFU", "보장균수"], short: "균 수" },
];

test("첫 등장만 링크하고 한글 경계(비헴철 안의 헴철)와 영문 경계(xrTGx)를 지킨다", () => {
  const T = Terms.build(ITEMS);
  const out = T.link("비헴철은 헴철보다 흡수가 낮고 rTG 오메가3 는 xrTGx 가 아니다. 헴철을 다시.", "../", {});
  assert.match(out, /<a class="term-link" href="\.\.\/term\/non-heme-iron\.html" title="식물성 철">비헴철<\/a>은/);
  assert.match(out, /href="\.\.\/term\/heme-iron\.html"[^>]*>헴철<\/a>보다/);
  assert.match(out, /href="\.\.\/term\/rtg\.html" title="재에스테르화 &quot;TG&quot;">rTG<\/a> 오메가3/);
  assert.ok(out.includes("xrTGx 가 아니다"));
  assert.equal((out.match(/term\/heme-iron\.html/g) || []).length, 1);   // 두 번째 '헴철'은 링크하지 않음
});

test("대소문자를 무시하고 숫자 뒤의 영문 별칭(4000IU 의 IU)은 맞추지 않는다", () => {
  const T = Terms.build(ITEMS.concat([{ slug: "iu", aliases: ["IU"], short: "국제단위" }]));
  const out = T.link("100억 cfu 와 4000IU, 그리고 IU 단위", "", {});
  assert.match(out, /href="term\/cfu\.html"[^>]*>cfu<\/a>/);
  assert.ok(out.includes("4000IU,"));
  assert.match(out, /그리고 <a class="term-link" href="term\/iu\.html"[^>]*>IU<\/a> 단위/);
});

test("exclude 의 용어는 건너뛰고 state 는 호출 사이에 이어진다", () => {
  const T = Terms.build(ITEMS);
  const st = { exclude: { "heme-iron": true } };
  const a = T.link("헴철과 비헴철", "../", st);
  const b = T.link("비헴철 다시, 상한섭취량", "../", st);
  assert.ok(!a.includes("term/heme-iron.html") && a.includes("term/non-heme-iron.html"));
  assert.ok(!b.includes("term/non-heme-iron.html") && b.includes("term/ul.html"));
});

test("페이지당 최대 MAX 개만 링크한다", () => {
  const items = [];
  for (let i = 0; i < 20; i++) items.push({ slug: "t" + i, aliases: ["용어" + String.fromCharCode(0xAC00 + i)], short: "" });
  const T = Terms.build(items);
  const text = items.map((it) => it.aliases[0]).join(" ");
  const out = T.link(text, "", {});
  assert.equal((out.match(/term-link/g) || []).length, Terms.MAX);
});

test("이스케이프된 텍스트는 그대로 두고 별칭이 없으면 그대로 돌려준다", () => {
  const T = Terms.build(ITEMS);
  assert.equal(T.link("&lt;b&gt;굵게&lt;/b&gt;", "", {}), "&lt;b&gt;굵게&lt;/b&gt;");
  assert.equal(Terms.build([]).link("헴철", "", {}), "헴철");
});
