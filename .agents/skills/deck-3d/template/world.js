'use strict';
/* ============================================================
 * world.js — DECK → 世界佈局、主線、講者備註，最後 boot()
 *
 * DECK 是 ./fw deck-3d 從 storyboard.md 產生的場景清單（封面、島、每島的場景），
 * 寫在 index.html 裡、排在本檔之前。哪一列變成哪幾個場景由產生端決定；本檔只管
 * 兩件與版面有關的事：
 *   1. 一景排不下時怎麼辦（縮小強調字 → 依句讀分成數景），因為排不排得下要用
 *      引擎的 measure()／frameK() 才算得出來；
 *   2. 場景擺在球面的哪裡、主線怎麼走。
 * 本檔與 engine.js 都不含任何一場簡報的內容，由 ./fw deck-3d 原樣複製。
 * ============================================================ */

/* ---------- 試排：一景是否排得下、抵站後是否讀得到 ----------
   在不入世界的 svg 上建一次，用引擎取景的同一套算式（contentBox → frameK）求抵站放大率：
   每行字的實效字級要 ≥ MIN_EFF，且不超出 1280×720 構圖框的下緣（#debug 的 overflow 自檢
   量的是同一條線）。 */
function legible(build) {
  const svg = document.createElementNS(SVGNS, 'svg');
  build(svg);
  const k = frameK(contentBox(svg));
  for (const t of svg.querySelectorAll('text')) {
    const F = +t.getAttribute('font-size'), y = +t.getAttribute('y');
    if (F * k < MIN_EFF || y + F * .35 > VIEW_H) return false;
  }
  return true;
}
const probe = def => Object.assign({ id: 'probe' }, def);
const fitsScene = def => legible(svg => buildScene(probe(def), svg, C.orange));
const fitsDuo = def => legible(svg => buildDuoScene(probe(def), svg, C.orange));

// 眉標只有一行、引擎不斷行：過長就截到版心寬
function clip(str, maxW, F) {
  if (!str || measure(str, F) <= maxW) return str || '';
  const chars = Array.from(str);
  while (chars.length && measure(chars.join('') + '…', F) > maxW) chars.pop();
  return chars.join('') + '…';
}

// 一段文字自己就超過一景：依句讀拆開；只有一句就拆不了
function sentences(block) {
  const parts = block.t.match(/[^。！？；]+[。！？；]?/g) || [];
  return parts.length > 1 ? parts.map(t => Object.assign({}, block, { t })) : null;
}

/* ---------- 一個標準場景 → 一到數景 ----------
   先原樣試排；不行就把 48px 的強調段降成 30px；再不行才分景：各景重複眉標與標題，
   巨字只在第一景，引註只在最後一景，眉標加（i/n）。每一景都帶同一份講者備註，
   因為它們講的是分鏡的同一列。 */
function paginate(def) {
  if (fitsScene(def)) return [def];
  const body = (def.body || []).map(b => b.lg ? { t: b.t, em: 1 } : b);
  if (fitsScene(Object.assign({}, def, { body }))) return [Object.assign({}, def, { body })];

  const MARK = '（9/9）';
  const trial = (blocks, first) => ({
    kicker: clip((def.kicker || '') + MARK, INNER, 26), title: def.title,
    big: first ? def.big : '', body: blocks, cite: def.cite,   // 每景都留引註的高度，最後一景才放得下
  });
  const queue = body.slice(), parts = [];
  let cur = [];
  while (queue.length) {
    const b = queue.shift();
    if (fitsScene(trial(cur.concat([b]), !parts.length))) { cur.push(b); continue; }
    if (cur.length) { parts.push(cur); cur = []; queue.unshift(b); continue; }
    const split = sentences(b);
    if (split) queue.unshift(...split);
    else parts.push([b]);        // 一句就超過一景：照放，由 #debug 報出來，回分鏡改短
  }
  if (cur.length || !parts.length) parts.push(cur);
  const n = parts.length;
  return parts.map((blocks, i) => Object.assign({}, def, {
    kicker: n > 1 ? (def.kicker || '') + `（${i + 1}/${n}）` : def.kicker,
    label: n > 1 ? def.label + `（${i + 1}/${n}）` : def.label,
    big: i ? '' : def.big, body: blocks, cite: i === n - 1 ? def.cite : '',
  }));
}

// 對照場景排不下（兩方的字太多）時，改成標準場景再走分景
function expand(def) {
  if (!def.duo) return paginate(def);
  if (fitsDuo(def)) return [def];
  const side = s => ({ t: [s.h, s.t].filter(Boolean).join('：') });
  return paginate({
    label: def.label, note: def.note, kicker: def.kicker, title: def.title, cite: def.cite,
    body: [def.lead && { t: def.lead }, side(def.left), side(def.right),
           def.foot && { t: def.foot, em: 1 }].filter(b => b && b.t),
  });
}

/* ---------- 島 ---------- */
const WORLD = DECK.islands.map(isl => Object.assign({}, isl, {
  scenes: isl.scenes.flatMap(expand).map(s => Object.assign({}, s, { kicker: clip(s.kicker, INNER, 26) })),
}));
// 浮水印用島名的第一個字（「七、建議」→「七」）：與島名永遠一致，不另編號
const ISLANDS = WORLD.map((isl, i) => ({ n: String(i + 1), name: isl.name, icon: Array.from(isl.name.trim())[0] || '' }));
const BASE_ACCENTS = C.islands.slice();
while (C.islands.length < WORLD.length) C.islands.push(BASE_ACCENTS[C.islands.length % BASE_ACCENTS.length]);

/* ---------- 世界佈局 ----------
   以「弧長」排版，再換算成角度：每島的場景排成數欄，欄距 COL_ARC、列距 ROW_ARC，
   島題封面在島的正中（俯仰 0），場景在它的上下各 rows/2 列。弧長固定、半徑可變，
   所以場景再多，鄰景之間的距離也不變：先試 2、4、6 列，取半徑最小的排法；
   全長超過 MAX_SPAN 度就加大半徑，而不是把場景擠在一起。最外一列的俯仰不超過
   MAX_PITCH 度，欄距以最外一列的緯圈計算，外列才不會相疊。 */
const COL_ARC = 1240, GAP_ARC = 520, ROW_ARC = [845, 1705, 2565], MAX_SPAN = 300, MAX_PITCH = 34;
function plan(rows) {
  const top = ROW_ARC[rows / 2 - 1];
  const cols = WORLD.map(isl => Math.max(1, Math.ceil(isl.scenes.length / rows)));
  let rw = Math.max(R, top / (MAX_PITCH * RAD));
  for (;;) {
    const step = COL_ARC / (rw * Math.cos(top / rw)) / RAD, gap = GAP_ARC / rw / RAD;
    const span = cols.reduce((a, c) => a + c * step, 0) + (cols.length - 1) * gap;
    if (span <= MAX_SPAN) return { rows, rw, step, gap, cols, span };
    rw *= 1.04;
  }
}
const LAYOUT = [2, 4, 6].map(plan).reduce((a, b) => b.rw < a.rw - 1 ? b : a);
const RW = LAYOUT.rw, ZOOM = RW / R;
// 由上而下的各列俯仰（度）：rows=4 → [+1705, +845, −845, −1705] 的弧長換成角度
const PITCHES = (() => {
  const half = ROW_ARC.slice(0, LAYOUT.rows / 2).map(a => a / RW / RAD);
  return half.slice().reverse().concat(half.map(p => -p));
})();

/* ---------- 全景站的平面地圖 ----------
   從球外看球面，正面的島遠、兩側的島近而且斜，超過約 ±120° 的島背對鏡頭、根本看不到；
   字又跟著距離縮到幾個像素。所以全景站不看球，而是把面板攤平成一張地圖（引擎的
   panelTf／updatePanels）：最上面是簡報標題，各島由左到右，島名在上、場景在下排成格。
   鏡頭正對地圖，退到整張地圖剛好填滿畫面為止。
   地圖有自己的欄列，不跟球面：球面為了讓鏡頭飛得短，把場景排成又寬又矮的一帶、
   在島內逐欄蛇行；地圖是拿來讀的，所以島內的格照閱讀順序由左到右、由上到下，
   列數取「整張地圖在 16:9 畫面上放得最大」的那一個（planFlat）。
   欄距比場景寬（1280）多留 80：球面上相鄰的場景靠前後錯開分辨，平面上要靠間隔。 */
const FLAT_COL = 1360, FLAT_ROW = 860, FLAT_GAP = 700, HEAD_GAP = 260, ISL_BAND = 560;
// head＝標題區原本的寬高。回傳列數 rows、各島欄數 cols、地圖寬高 w/h、鏡頭放大率 k、
// 標題區的倍率與高度 headS/headH、島名那一帶的高度 band
function planFlat(head) {
  const band = WORLD.some(isl => isl.name) ? ISL_BAND : 0;
  let best = null;
  for (let rows = 1; rows <= 16; rows++) {
    const cols = WORLD.map(isl => Math.max(1, Math.ceil(isl.scenes.length / rows)));
    const w = cols.reduce((a, c) => a + c * FLAT_COL, 0) + (cols.length - 1) * FLAT_GAP - (FLAT_COL - VIEW_W);
    // 標題放大到與島名相稱，但不超過地圖的七成寬
    const headS = Math.min(4.4, w * .7 / head.w), headH = head.h * headS;
    const h = headH + HEAD_GAP + band + rows * FLAT_ROW - (FLAT_ROW - VIEW_H);
    const k = Math.min(1920 * FILL_W / w, 1080 * FILL_H / h);
    if (!best || k > best.k * 1.001) best = { rows, cols, w, h, k, headS, headH, band };
  }
  return best;
}
let FLAT = null;   // 標題景量出標題區的大小後才定案
// 面板在地圖上的位置：x 由地圖中線算起、y 由地圖上緣算起；z 是深度，島名略前、
// 浮水印略後，同平面的面板才不會互相穿插
const flatAt = (id, x, y, dz) => { PANELS[id].flat = { x, y: y - FLAT.h / 2, z: RW + (dz || 0) }; };

const NOTES = {};
const ROUTE = ['s0'];

/* ---------- 標題景：近、偏上，飛離後落在鏡頭後方 ----------
   標題字級由 100px 往下試到兩行內排得下為止；副題、署名依序往下排，面板高度跟著內容。 */
(function cover() {
  const c = DECK.cover, W = 1500, CX = W / 2, MAXW = 1340;
  let F = 100, lines = wrap(c.title, MAXW, F);
  while (lines.length > 2 && F > 56) { F -= 4; lines = wrap(c.title, MAXW, F); }
  const subs = c.sub ? wrap(c.sub, MAXW, 38) : [], metas = c.meta ? wrap(c.meta, MAXW, 26) : [];
  const y0 = 150 + F * .88;
  const H = Math.max(600, y0 + (lines.length - 1) * F * 1.18 + 40 + subs.length * 54 + 20 + metas.length * 40 + 110);
  const svg = panel('s0', W, H, 0, 26, R * .35);
  const g = sceneGroup({ id: 's0' }, svg, W, H);
  let y = y0;
  lines.forEach((ln, i) => { txt(g, ln, CX, y, F, C.ink, 'middle'); if (i < lines.length - 1) y += F * 1.18; });
  y += 40; el('rect', { x: CX - 190, y, width: 380, height: 5, fill: C.orange }, g);
  y += 26;
  for (const ln of subs) { y += 54; txt(g, ln, CX, y, 38, C.orange, 'middle'); }
  y += 20;
  for (const ln of metas) { y += 40; txt(g, ln, CX, y, 26, C.dim, 'middle'); }
  txt(g, '點擊任意處前進 ▸', CX, y + 76, 26, 'rgba(232,230,224,.4)', 'middle');
  // 地圖的標題區：標題、副題、署名。量出它的大小，地圖的欄列才能定案
  const head = [
    ...lines.map((t, i) => ({ t, F, fill: C.ink, gap: i ? F * .18 : 0 })),
    { rule: [380, 5], fill: C.orange, gap: 40 },
    ...subs.map((t, i) => ({ t, F: 38, fill: C.orange, gap: i ? 16 : 30 })),
    ...metas.map((t, i) => ({ t, F: 26, fill: C.dim, gap: i ? 14 : 24 })),
  ];
  FLAT = planFlat(labelBox(head));
  buildLabel('s0', head, FLAT.headS);
  PANELS.s0.div.style.setProperty('--accent', C.orange);
  flatAt('s0', 0, FLAT.headH / 2);
  frameWp('s0', c.title);
  NOTES.s0 = c.note || '';
})();

/* ---------- 各島：浮水印、島題封面、場景；主線在島內逐欄蛇行 ---------- */
let yawAt = -LAYOUT.span / 2, xAt = -(FLAT.w + FLAT_COL - VIEW_W) / 2;
const GRID_Y = FLAT.headH + HEAD_GAP + FLAT.band;   // 地圖上第一列格子的上緣
WORLD.forEach((isl, i) => {
  const n = String(i + 1), accent = C.islands[i], cols = LAYOUT.cols[i], rows = LAYOUT.rows;
  const fcols = FLAT.cols[i];
  const Y = yawAt + cols * LAYOUT.step / 2, X = xAt + fcols * FLAT_COL / 2;
  const stops = [];

  if (ISLANDS[i].icon) {
    const wm = panel('wm' + n, 1200, 1200, Y, 0, RW * 1.45, { island: n });
    txt(wm, ISLANDS[i].icon, 600, 900, 900, '#223052', 'middle').setAttribute('opacity', .05);
    flatAt('wm' + n, X, (GRID_Y + FLAT.h) / 2, 60);
  }

  if (isl.name) {   // 沒有島名＝第一個章節頁之前的開場場景，不設封面站
    const id = 'isl' + n, W = 1280;
    const names = wrap(isl.name, W - 160, 86), subs = isl.sub ? wrap(isl.sub, W - 160, 34) : [];
    const nameEnd = 430 + (names.length - 1) * 86 * 1.28;
    const H = Math.max(560, nameEnd + (subs.length ? 30 + subs.length * 50 : 0) + 110);
    const g = buildCover(i, panel(id, W, H, Y, 0, RW, { island: n, cover: 1 }), W, H);
    subs.forEach((ln, j) => txt(g, ln, W / 2, nameEnd + 80 + j * 50, 34, C.body, 'middle').classList.add('fx'));
    PANELS[id].div.classList.add('cover');
    PANELS[id].div.style.setProperty('--accent', accent);
    // 地圖上的島名：在這一島的格子上方，放大到島的寬度或那一帶的高度（先到者為準）
    const tag = [
      { rule: [110, 8], fill: accent },
      ...names.map((t, j) => ({ t, F: 86, fill: C.ink, gap: j ? 24 : 44 })),
      ...subs.map((t, j) => ({ t, F: 34, fill: C.body, gap: j ? 16 : 40 })),
    ], box = labelBox(tag);
    buildLabel(id, tag, Math.min((fcols * FLAT_COL - 200) / box.w, (FLAT.band - 130) / box.h));
    flatAt(id, X, GRID_Y - FLAT.band / 2 - 20, -30);
    frameWp(id, isl.label || isl.name);
    NOTES[id] = isl.note || '';
    stops.push(id);
  }

  isl.scenes.forEach((def, j) => {
    const col = Math.floor(j / rows), at = j % rows, row = col % 2 ? rows - 1 - at : at;
    const id = 's' + n + '-' + (j + 1);
    const svg = panel(id, VIEW_W, VIEW_H, yawAt + (col + .5) * LAYOUT.step, PITCHES[row],
                      RW * ((col + row) % 2 ? 1.08 : 1), { island: n });
    (def.duo ? buildDuoScene : buildScene)(Object.assign({}, def, { id }), svg, accent);
    // 地圖格：站名「編號・標題」拆成編號與標題（沒有「・」就整個當標題）
    const cut = def.label.indexOf('・');
    buildTile(id, cut < 0 ? '' : def.label.slice(0, cut), def.label.slice(cut + 1), accent);
    flatAt(id, xAt + (j % fcols + .5) * FLAT_COL, GRID_Y + VIEW_H / 2 + Math.floor(j / fcols) * FLAT_ROW);
    frameWp(id, def.label);
    NOTES[id] = def.note || '';
    stops.push(id);
  });

  if (i > 0 && stops.length) WP[stops[0]].visit = i - 1;   // 進下一島＝上一島標為已訪（調暗）
  ROUTE.push(...stops);
  yawAt += cols * LAYOUT.step + LAYOUT.gap;
  xAt += fcols * FLAT_COL + FLAT_GAP;
});

/* ---------- 全景：Esc 隨時回來；主線最後一站也是它 ----------
   flat＝面板攤平成地圖。鏡頭正對地圖，退到整張地圖（含標題區）剛好填到畫面的
   FILL_W × FILL_H 為止（planFlat 的 k）：地圖多大就退多遠，不是固定距離。 */
const HUB_TZ = tzFor(RW, FLAT.k);
wp('hub', '全景', { yaw: 0, pitch: 0, tz: HUB_TZ, flat: 1 });
wp('end', '全景', { yaw: 0, pitch: 0, tz: HUB_TZ, flat: 1, visit: WORLD.length - 1 });
ROUTE.push('end');

boot();
