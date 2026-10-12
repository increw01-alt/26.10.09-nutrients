/* 사이트에서 실제로 쓰는 Lucide 아이콘만 골라 assets/js/icons.js 를 만든다 (npm run icons).
 * unpkg 의 전체 번들(350KB) 대신 10KB 남짓의 파일 하나만 내려받게 해 첫 화면 속도를 높인다. */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(ROOT, "package.json"));
const lucidePath = process.env.LUCIDE_DIR ? path.join(process.env.LUCIDE_DIR, "dist/cjs/lucide.js") : "lucide";
const { icons } = require(lucidePath);

function listFiles(dir, exts, out = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) { if (!["node_modules", ".git", ".venv"].includes(ent.name)) listFiles(p, exts, out); }
    else if (exts.some(e => ent.name.endsWith(e))) out.push(p);
  }
  return out;
}
const sources = [...fs.readdirSync(ROOT).filter(f => f.endsWith(".html")).map(f => path.join(ROOT, f)),
  ...listFiles(path.join(ROOT, "assets/js"), [".js"]).filter(f => !f.endsWith("icons.js")),
  path.join(ROOT, "scripts/build_site.py"),
  ...["ingredients.json", "interactions.json", "guides.json"].map(f => path.join(ROOT, "data", f))];
const names = new Set(["pill", "circle-help", "arrow-right", "chevron-right", "chevron-down", "x", "check", "search", "menu", "arrow-up", "link"]);
const patterns = [/data-lucide="([a-z0-9-]+)"/g, /icon:\s*"([a-z0-9-]+)"/g, /"icon":\s*"([a-z0-9-]+)"/g, /"([a-z0-9-]+)"\s*:\s*\[/g];
for (const f of sources) {
  const s = fs.readFileSync(f, "utf8");
  for (const re of patterns) for (const m of s.matchAll(re)) if (f.endsWith(".json") || re !== patterns[3]) names.add(m[1]);
}
const toPascal = s => s.split("-").map(w => w[0].toUpperCase() + w.slice(1)).join("");
const out = {}, missing = [];
for (const n of [...names].sort()) {
  const node = icons[toPascal(n)];
  if (!node) { missing.push(n); continue; }
  out[n] = node[2];                       // ["svg", attrs, children] → children 만 저장
}
const js = `/* 사이트에서 쓰는 Lucide 아이콘 ${Object.keys(out).length}개만 모은 경량 번들 — 자동 생성(npm run icons), 직접 수정하지 않음. 출처: lucide ${require(process.env.LUCIDE_DIR ? path.join(process.env.LUCIDE_DIR, "package.json") : "lucide/package.json").version} (ISC) */
(function () {
  "use strict";
  var ICONS = ${JSON.stringify(out)};
  var NS = "http://www.w3.org/2000/svg";
  var BASE = { xmlns: NS, width: "24", height: "24", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round" };
  function replace(el) {
    var name = el.getAttribute("data-lucide"), nodes = ICONS[name];
    if (!nodes) return;
    var svg = document.createElementNS(NS, "svg");
    Object.keys(BASE).forEach(function (k) { svg.setAttribute(k, BASE[k]); });
    Array.prototype.forEach.call(el.attributes, function (a) { if (a.name !== "data-lucide" && a.name !== "class") svg.setAttribute(a.name, a.value); });
    svg.setAttribute("class", ("lucide lucide-" + name + " " + (el.getAttribute("class") || "")).trim());
    nodes.forEach(function (n) { var c = document.createElementNS(NS, n[0]); Object.keys(n[1]).forEach(function (k) { c.setAttribute(k, n[1][k]); }); svg.appendChild(c); });
    el.parentNode.replaceChild(svg, el);
  }
  window.lucide = {
    icons: ICONS,
    createIcons: function (opts) {
      var root = (opts && opts.root) || document;
      Array.prototype.slice.call(root.querySelectorAll("[data-lucide]")).forEach(replace);
    }
  };
})();
`;
fs.writeFileSync(path.join(ROOT, "assets/js/icons.js"), js);
console.log(`icons.js: ${Object.keys(out).length}개 아이콘, ${(js.length / 1024).toFixed(1)}KB` + (missing.length ? ` | 알 수 없는 이름 제외: ${missing.join(", ")}` : ""));
