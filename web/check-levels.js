// 关卡可解性检查（无头）：node web/check-levels.js
// 用固定 DOM 桩 require app.js，对每一关暴力扫 角度×力度 网格，
// 统计解出率——0% 的关卡不允许存在（设计文档 §15 的第一块基石）。
"use strict";
const els = {};
function makeEl() {
  return { textContent: "", innerHTML: "", onclick: null, style: {},
    dataset: {},
    classList: { add() {}, remove() {}, toggle() {} },
    querySelectorAll: () => [], appendChild() {}, remove() {} };
}
const ctxStub = new Proxy({}, {
  get: (t, k) => k === "createLinearGradient" ? () => ({ addColorStop() {} }) : (typeof t[k] !== "undefined" ? t[k] : () => {}),
  set: () => true,
});
const gameStub = {
  width: 1280, height: 720,
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 1280, height: 720 }),
  setPointerCapture() {}, addEventListener() {},
  getContext: () => ctxStub,
};
global.document = {
  getElementById: id => id === "game" ? gameStub : (els[id] || (els[id] = makeEl())),
  addEventListener() {},
};
let nowMs = 0;
global.performance = { now: () => nowMs };
global.requestAnimationFrame = () => {};

const game = require("./app.js");

function tryShot(angleRad, power) {
  const before = Number(els.made.textContent);
  game.reset();
  game.shoot(angleRad, power);
  let t = nowMs;
  for (let guard = 0; guard < 600 && els.result.textContent === "出手！"; guard++) {
    t += 16; nowMs = t; game.tick(t);
  }
  return Number(els.made.textContent) > before;
}

function checkLevel(L) {
  while (Number(els.level.textContent) - 1 !== L) game.next();
  let solved = 0, total = 0, easiest = null;
  for (let power = 0.2; power <= 1.001; power += 0.04) {
    for (let deg = 20; deg <= 80; deg += 2) {
      total++;
      if (tryShot(deg * Math.PI / 180, Number(power.toFixed(2)))) {
        solved++;
        if (!easiest) easiest = { deg, power: Number(power.toFixed(2)) };
      }
    }
  }
  return { name: game.current().name, solved, total, easiest };
}

const rows = [];
for (let L = 0; L < game.levels.length; L++) rows.push(checkLevel(L));

console.log("关卡可解性检查（角度 20-80° 步进2° × 力度 0.2-1.0 步进0.04）");
rows.forEach((r, i) => {
  const pct = (r.solved / r.total * 100).toFixed(1);
  const flag = r.solved === 0 ? "  <- 无解，禁止上线" : "";
  console.log(`  L${i + 1} ${r.name.padEnd(3)} 解出率 ${pct.padStart(6)}%  (${r.solved}/${r.total})`
    + (r.easiest ? `  最省力解: ${r.easiest.deg}deg @ ${Math.round(r.easiest.power * 100)}%` : "")
    + flag);
});
