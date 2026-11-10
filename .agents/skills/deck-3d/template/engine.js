'use strict';
/* ============================================================
 * engine.js — 無頁式 3D 心智圖簡報引擎（可重用）
 *
 * 這支檔案是「引擎」：運鏡、佈局基元、導演台、講者視窗遙控、可讀性自檢。
 * 它「不含任何一場簡報的內容」——內容（島名、場景資料、世界佈局、主線、講者備註）
 * 由排在本檔之後的內容腳本（world.js）以全域變數提供，最後呼叫 boot() 啟動。
 *
 * 內容端必須在 boot() 之前定義這些全域：
 *   ISLANDS（島）、世界佈局（呼叫 panel()/buildScene()… 填 PANELS）、
 *   frameWp()/wp() 呼叫（填 WP）、ROUTE（主線）、NOTES（講者備註）。
 * 引擎函式只在執行期（boot 之後）讀取這些全域，故跨 <script> 標籤的後綁定成立。
 *
 * 世界＝3D 心智圖球面：鏡頭在球心，場景是球面內側的節點面板
 * （每面板一張 inline SVG，文字仍由 SVG 繪製）；
 * 運鏡＝偏航/俯仰旋轉＋推軌變焦（CSS 3D perspective）。
 * 引擎規則：運鏡與焦點淡入皆「合成器驅動」（Web Animations／CSS opacity），
 * 只在飛行頭尾各寫一次樣式；不要重新引入逐幀 rAF 改樣式（原始 zoom jank 來源）。
 * ============================================================ */

/* ---------- 講者視窗角色（presenter.html 用） ----------
   ?role=preview＝講者視窗的預覽窗：瞬移、不互動、隱藏 HUD；其餘＝正式簡報窗（動畫運鏡）。
   REMOTE＝遙控端：開啟本窗者（window.opener，簡報窗）或外層（window.parent，預覽 iframe）。 */
const ROLE = new URLSearchParams(location.search).get('role') || 'show';
const REMOTE = window.opener || (window.parent !== window ? window.parent : null);
if (ROLE === 'preview') document.body.classList.add('preview');
/* ?debug：把運鏡／抵站／收訊軌跡印到主控台（講者視窗會把旗標傳播到簡報窗與預覽窗），
   出問題時開 DevTools Console 即可看清誰在連環觸發。預設關閉、零負擔。 */
const DBG = new URLSearchParams(location.search).has('debug');
function dlog() { if (DBG) try { console.log('[deck:' + ROLE + ']', Array.prototype.join.call(arguments, ' ')); } catch (_) {} }

/* ---------- 調色盤（內容端可於 boot 前覆寫 C.xxx） ---------- */
const C = {
  bg:'#0B1020', ink:'#E8E6E0', body:'#C9CDD8', dim:'#7d879c',
  orange:'#F7931A',  // 全域強調色
  islands:['#26A17B','#F7931A','#8B7CF6','#C9A227','#3FA7D6','#EAE2B7'],
};

const R = 2600;          // 球面基準半徑（px）
const PERSP = 1100;      // 視錐 perspective
const MIN_EFF = 30;      // 教室投影可讀下限：抵站實效字級（authored × k）≥ 30px @1080p

/* ============================================================
 * 文字度量與換行：CJK 每字 1em、拉丁串約 0.55em/字、空白 0.28em。
 * 行首不收「，。、…」等收尾標點；行尾不留「（「『」等起始標點。
 * ============================================================ */
const CJK_RE = /[　-〿぀-ヿ㐀-䶿一-鿿豈-﫿＀-￯—‘’“”…·─]/;
const CLOSE_P = '，。、；：？！）」』］〉》…';
const OPEN_P  = '（「『［〈《';

function tokenize(str) {
  const toks = [];
  let i = 0;
  while (i < str.length) {
    const ch = str[i];
    if (ch === ' ') { toks.push({ s:' ', w:.28 }); i++; }
    else if (CJK_RE.test(ch)) { toks.push({ s:ch, w:1 }); i++; }
    else {
      let j = i;
      while (j < str.length && str[j] !== ' ' && !CJK_RE.test(str[j])) j++;
      toks.push({ s:str.slice(i,j), w:.55*(j-i) });
      i = j;
    }
  }
  return toks;
}
function measure(str, F) { return tokenize(str).reduce((a,t)=>a+t.w, 0) * F; }
function wrap(str, maxW, F) {
  const maxU = maxW / F;
  const lines = [];
  let cur = '', curW = 0;
  for (const t of tokenize(str)) {
    if (curW + t.w > maxU && cur) {
      if (t.s.length === 1 && CLOSE_P.includes(t.s)) { cur += t.s; continue; }  // 收尾標點黏行尾
      const last = cur[cur.length-1];
      if (OPEN_P.includes(last)) { cur = cur.slice(0,-1); lines.push(cur); cur = last; curW = 1; }  // 起始標點帶到下行
      else { lines.push(cur); cur = ''; curW = 0; }
      if (t.s === ' ') continue;  // 行首不留空白
    }
    cur += t.s; curW += t.w;
  }
  if (cur) lines.push(cur);
  return lines;
}

/* ---------- SVG 建構小工具 ---------- */
const SVGNS = 'http://www.w3.org/2000/svg';
function el(name, attrs, parent) {
  const n = document.createElementNS(SVGNS, name);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
function txt(parent, str, x, y, F, fill, anchor) {
  const t = el('text', { x, y, 'font-size':F, fill, 'text-anchor':anchor||'start' }, parent);
  t.textContent = str;
  return t;
}

/* ============================================================
 * 面板＝球面節點：一面板一張 inline SVG。
 * yaw/pitch（度）＋ radius 決定球面位置；roll 為面內微旋。
 * ============================================================ */
const space = document.getElementById('space');
const dolly = document.getElementById('dolly');
const PANELS = {};   // id → {div, yaw, pitch, r, w, h, flat, isFlat}

/* 面板有兩種擺法：球面（yaw/pitch/r）與全景站的平面地圖（flat＝{x, y, z}，由內容端指定）。
   兩種擺法寫成同一串變形函式，瀏覽器才會逐項內插——面板從球面「攤平」到地圖上，
   而不是走矩陣分解的怪路徑。沒有 flat 的面板在全景站留在球面原位。 */
function panelTf(p, flat) {
  const f = flat && p.flat;
  return `translate3d(${f ? f.x : 0}px,${f ? f.y : 0}px,0px) rotateY(${f ? 0 : -p.yaw}deg) ` +
         `rotateX(${f ? 0 : -p.pitch}deg) translateZ(${f ? -f.z : -p.r}px)` +
         (p.roll ? ` rotate(${p.roll}deg)` : '') + ' translate(-50%,-50%)';
}
let flatNow = false;   // 目前（或飛行目的地）是否為平面地圖；各面板實際擺在哪一種是 p.isFlat
function setLayout(p, flat) { p.isFlat = flat; p.div.style.transform = panelTf(p, flat); }
// 不經飛行直接換擺法（瞬移、抵站校正）；飛行中的換位在 updatePanels
function layoutPanels(flat) {
  flatNow = flat;
  for (const id in PANELS) if (PANELS[id].isFlat !== flat) setLayout(PANELS[id], flat);
}
// 抵站：飛行中留在原擺法的面板（見 updatePanels）此時歸位。強制重排讓歸位不帶過場
function settlePanels() {
  let moved = false;
  for (const id in PANELS) {
    const p = PANELS[id];
    if (p.isFlat !== flatNow) { p.div.style.transition = 'none'; setLayout(p, flatNow); moved = true; }
  }
  if (moved) void space.offsetWidth;
}

function panel(id, w, h, yaw, pitch, r, opts) {
  opts = opts || {};
  const d = document.createElement('div');
  d.className = 'panel' + (opts.cls ? ' ' + opts.cls : '');
  if (id) d.id = 'p-' + id;
  if (opts.island) d.dataset.island = opts.island;
  d.style.width = w + 'px';
  d.style.height = h + 'px';
  const p = { div:d, yaw, pitch, r, w, h, roll:opts.roll || 0, flat:null, isFlat:false };
  d.style.transform = panelTf(p, false);
  space.appendChild(d);
  const svg = document.createElementNS(SVGNS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  d.appendChild(svg);
  const baseOp = opts.opacity != null ? +opts.opacity : 1;
  d.style.opacity = baseOp;
  PANELS[id] = Object.assign(p, { svg, baseOp, visited:false, cover:!!opts.cover });
  return svg;
}

/* ============================================================
 * 場景建構：16:9 構圖框（1280×720，佈局上限），無框無底；
 * 內容靠左對齊，引註緊接正文（鏡頭取景以內容外框為準，見 frameWp）。
 * ============================================================ */
const VIEW_W = 1280, VIEW_H = 720, LX = 90, INNER = 1100;

function sceneGroup(def, parent, w, h) {
  const g = el('g', { id:def.id, class:'scene' }, parent);
  g.dataset.w = w; g.dataset.h = h;
  return g;
}
function fxer() {
  let n = 0;
  return node => { node.classList.add('fx'); node.style.transitionDelay = (n++ * .09) + 's'; return node; };
}

/* ---------- 通用 renderer：標準場景（標題＋巨數字＋條列＋引註） ---------- */
function buildScene(def, parent, accent, opt) {
  opt = opt || {};
  const small = !!opt.small;
  const w = opt.w || VIEW_W, h = opt.h || VIEW_H;
  const lx = small ? 50 : LX, innerW = small ? w - 100 : INNER;
  const g = sceneGroup(def, parent, w, h);
  // 支線小景的細輪廓＝「可點擊」語義框
  if (opt.side) el('rect', { x:0, y:0, width:w, height:h, rx:18, fill:'none', stroke:accent,
                             'stroke-opacity':.3, 'stroke-width':1.5, 'pointer-events':'all' }, g);
  const fx = fxer();
  let cy = small ? 80 : 120;

  fx(el('rect', { x:lx, y:cy-36, width:64, height:5, fill:accent }, g));
  if (def.kicker) { fx(txt(g, def.kicker, lx, cy, 26, accent)); cy += 60; }
  const titleF = small ? 32 : 46;
  for (const ln of wrap(def.title, innerW, titleF)) { fx(txt(g, ln, lx, cy, titleF, C.ink)); cy += titleF*1.4; }
  cy += small ? 8 : 16;
  if (def.big) {
    const bf = Math.min(110, innerW / (measure(def.big,1) || 1));
    cy += bf*.92;
    fx(txt(g, def.big, lx, cy, bf, '#F5F2EA'));
    cy += bf*.42;
  }
  for (const p of (def.body||[])) {
    const F = p.lg ? 48 : (small ? 24 : 30);
    const fill = (p.em || p.lg) ? C.orange : C.body;
    for (const ln of wrap(p.t, innerW, F)) { cy += F*1.45; fx(txt(g, ln, lx, cy, F, fill)); }
    cy += 10;
  }
  if (def.cite) fx(txt(g, def.cite, lx, cy + (small ? 34 : 48), small ? 16 : 20, C.dim));
  return g;
}

/* ---------- 通用 renderer：左右雙欄對照（一分割線＋兩段） ----------
   title 置中、可斷行；lead（爭點）在標題下、foot（提問或結論）在兩欄下，皆選填。
   各段位置由上一段的結尾推得，所以長標題或長欄文只會把下面往下推，不會疊字。 */
function buildDuoScene(def, parent, accent) {
  const w = VIEW_W, h = VIEW_H;
  const g = sceneGroup(def, parent, w, h);
  const fx = fxer();
  let cy = 150;
  for (const ln of wrap(def.title, INNER, 48)) { fx(txt(g, ln, w/2, cy, 48, C.ink, 'middle')); cy += 48*1.4; }
  if (def.lead) { for (const ln of wrap(def.lead, INNER, 30)) { fx(txt(g, ln, w/2, cy, 30, C.body, 'middle')); cy += 30*1.45; } cy += 8; }
  const top = cy + 12, panW = 480;
  // 分割構圖：細分隔線＝語義（兩張臉）；長度等兩欄排完才知道，先放、後補 y2
  const rule = fx(el('line', { x1:w/2, y1:top, x2:w/2, y2:top, stroke:accent, 'stroke-opacity':.35, 'stroke-width':2 }, g));
  let bottom = top + 60;
  [[def.left, LX], [def.right, w/2 + 70]].forEach(([side, px]) => {
    fx(txt(g, side.h, px, top + 60, 34, accent));
    let yy = top + 100;
    for (const ln of wrap(side.t, panW, 30)) { yy += 30*1.45; fx(txt(g, ln, px, yy, 30, C.body)); }
    bottom = Math.max(bottom, yy);
  });
  rule.setAttribute('y2', bottom + 20);
  cy = bottom + 30;
  if (def.foot) for (const ln of wrap(def.foot, INNER, 30)) { cy += 30*1.45; fx(txt(g, ln, w/2, cy, 30, C.orange, 'middle')); }
  if (def.cite) fx(txt(g, def.cite, w/2, cy + 48, 20, C.dim, 'middle'));
  return g;
}

/* ---------- 通用 renderer：島題封面（章節分隔，巨大置中主題名） ----------
   每島第一主線站。是 .scene，受內容取景與抵站置中校正，與內容場景一視同仁。
   讀內容全域 ISLANDS[i].name 與 C.islands[i]（皆由載入端提供）。 */
function buildCover(i, parent, w, h) {
  const accent = C.islands[i], cx = w/2;
  const g = sceneGroup({ id:'isl' + (i+1) }, parent, w, h);
  const fx = fxer();
  // 章節分隔：只呈現「主題名」（內容），不顯示島號——「島」是內部視覺組織概念、與內容無關。
  // 內容置中＝版心 → 鏡頭正面取景、無傾斜。
  fx(el('rect', { x:cx-55, y:300, width:110, height:8, fill:accent }, g));
  let ny = 430;
  for (const ln of wrap(ISLANDS[i].name, w - 160, 86)) { fx(txt(g, ln, cx, ny, 86, C.ink, 'middle')); ny += 86*1.28; }
  return g;
}

/* ---------- 通用 renderer：地圖格與地圖標籤（全景站用） ----------
   全景站的鏡頭離得遠，場景本身的字（30–46px）縮到只剩幾個像素。所以面板另帶一張
   全景站專用的 svg（.map）：全景站顯示它、隱藏面板原本的內容（樣式在 host）。
   它是面板裡的第二張 svg：取景（contentBox）、抵站校正、列印（slideMarkup）與自檢
   都只讀第一張，所以地圖怎麼畫都不影響抵站的畫面。 */
function mapSvg(id, cls) {
  const p = PANELS[id], svg = document.createElementNS(SVGNS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${p.w} ${p.h}`);
  svg.setAttribute('class', 'map ' + cls);
  p.div.appendChild(svg);
  p.div.classList.add('mapped');
  return svg;
}
// 地圖格：一個場景＝一格，編號＋標題，字級取排得下的最大者
function buildTile(id, tag, title, accent) {
  const p = PANELS[id], w = p.w, h = p.h, lx = 70, maxW = w - 2*lx;
  const svg = mapSvg(id, 'tile');
  el('rect', { class:'plate', x:16, y:16, width:w-32, height:h-32, rx:44, fill:accent, 'fill-opacity':.1,
               stroke:accent, 'stroke-opacity':.55, 'stroke-width':6 }, svg);
  if (tag) txt(svg, tag, lx, 132, 84, accent);
  const top = tag ? 172 : 60, room = h - top - 56;
  let F = 0, lines = [];
  for (F of [176, 150, 128, 110, 96]) { lines = wrap(title, maxW, F); if (lines.length * F*1.25 <= room) break; }
  const max = Math.max(1, Math.floor(room / (F*1.25)));
  if (lines.length > max) {   // 最小字級仍排不下：截到排得下的行數
    const tail = Array.from(lines[max-1]);
    while (tail.length && measure(tail.join('') + '…', F) > maxW) tail.pop();
    lines = lines.slice(0, max-1).concat(tail.join('') + '…');
  }
  const wide = Math.max(...lines.map(ln => measure(ln, F)));
  if (wide > maxW) F *= maxW / wide;   // 斷不開的長字（英文識別字）比格子寬：這一格縮字
  let y = top + (room - lines.length * F*1.25)/2 + F*.95;
  for (const ln of lines) { txt(svg, ln, lx, y, F, C.ink); y += F*1.25; }
}
/* 地圖標籤：島名、簡報標題這類置中的幾行。items 由上而下，每項是一行字 {t, F, fill, gap}
   或一條短線 {rule:[寬, 高], fill, gap}（gap＝與上一項的間距）。labelBox 量出整疊原本的
   寬高；buildLabel 把整疊以面板正中為中心放大 s 倍畫出來，畫出去可以超過面板。 */
function labelBox(items) {
  let w = 1, h = 0;
  for (const it of items) {
    h += it.gap || 0;
    it.top = h;
    h += it.rule ? it.rule[1] : it.F;
    w = Math.max(w, it.rule ? it.rule[0] : measure(it.t, it.F));
  }
  return { w, h };
}
function buildLabel(id, items, s) {
  const p = PANELS[id], h = labelBox(items).h;
  const g = el('g', { transform:`translate(${p.w/2},${p.h/2}) scale(${s.toFixed(3)}) translate(0,${(-h/2).toFixed(1)})` },
               mapSvg(id, 'label'));
  for (const it of items) {
    if (it.rule) el('rect', { x:-it.rule[0]/2, y:it.top, width:it.rule[0], height:it.rule[1], fill:it.fill }, g);
    else txt(g, it.t, 0, it.top + it.F*.88, it.F, it.fill, 'middle');
  }
}

/* ============================================================
 * Waypoints：{yaw, pitch, tz}＝旋轉對準＋推軌
 * tz 由「目標面板半徑＋期望放大率 k」推得：tz = r + PERSP·(1 − 1/k)
 * ============================================================ */
function tzFor(r, k) { return r + PERSP * (1 - 1/k); }
const WP = {};
function wp(id, label, opts) { WP[id] = Object.assign({ id, label }, opts); }
function sceneWp(id, label, k, opts) {
  const p = PANELS[id];
  wp(id, label, Object.assign({ yaw:p.yaw, pitch:p.pitch, tz:tzFor(p.r, k), card:1 }, opts||{}));
}

/* 內容取景：放大率與對準點由內容實際外框決定，
 * 不取 1280×720 構圖框——疏景自然拉近（字變大）、密景自然後退。
 * 外框用版面同一套 measure() 推算（與斷行一致，且不受字型載入時序影響）。 */
const FILL_W = .92, FILL_H = .86, K_MAX = 2.2;   // K_MAX：支線小景的 24px 正文 ×2.2 ≈ 主線實效字級
function contentBox(svg) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  const add = (a, b, c, d) => { x0 = Math.min(x0, a); y0 = Math.min(y0, b); x1 = Math.max(x1, c); y1 = Math.max(y1, d); };
  svg.querySelectorAll('text,rect,line').forEach(n => {
    if (n.tagName === 'text') {
      const F = +n.getAttribute('font-size'), x = +n.getAttribute('x'), y = +n.getAttribute('y');
      const w = measure(n.textContent, F);
      const lx = n.getAttribute('text-anchor') === 'middle' ? x - w/2 : x;
      add(lx, y - F*.88, lx + w, y + F*.12);   // CJK 字面約在基線上 0.88em、下 0.12em
    } else if (n.tagName === 'rect') {
      add(+n.getAttribute('x'), +n.getAttribute('y'),
          +n.getAttribute('x') + +n.getAttribute('width'), +n.getAttribute('y') + +n.getAttribute('height'));
    } else {
      add(Math.min(+n.getAttribute('x1'), +n.getAttribute('x2')), Math.min(+n.getAttribute('y1'), +n.getAttribute('y2')),
          Math.max(+n.getAttribute('x1'), +n.getAttribute('x2')), Math.max(+n.getAttribute('y1'), +n.getAttribute('y2')));
    }
  });
  return { cx:(x0 + x1)/2, cy:(y0 + y1)/2, w:x1 - x0, h:y1 - y0 };
}
// 抵站放大率：內容外框填到畫面的 FILL_W × FILL_H 為止。內容腳本在擺面板前也用它
// 預先試排（world.js 的 legible()），所以「排得下」與「抵站後讀得到」是同一個算式。
function frameK(b) { return Math.min(1920*FILL_W/b.w, 1080*FILL_H/b.h, K_MAX); }
function frameWp(id, label) {
  const p = PANELS[id], b = contentBox(p.svg), DEG = 180/Math.PI;
  const k = frameK(b);
  // 垂直置中改由 calibrateFraming() 於載入時「實測校正」：CSS 3D 對離軸面板的投影置中
  // 無法可靠解析預測（同 k 下偏移隨偏航/俯仰在 26–41% 間飄、不是常數），實測抵站位置最準。
  // 此處只負責偏航對準與變焦；俯仰直接對準面板中心（再交給校正微調 y）。
  wp(id, label, { yaw: p.yaw + Math.atan2(b.cx - p.w/2, p.r)*DEG, pitch: p.pitch,
                  tz: tzFor(p.r, k), card:1, k });
}

/* ============================================================
 * 相機：球心旋轉＋推軌補間；大角度旋轉途中自動後撤（拉遠弧線）
 * ============================================================ */
let cam = { yaw:0, pitch:0, tz:0 };   // 邏輯相機＝目前（或飛行目的地）的姿態
let flight = null;                    // {from, to, t0, dur, dip, anims[]}
const RAD = Math.PI / 180;
function dirOf(yaw, pitch) {
  const cp = Math.cos(pitch*RAD);
  return [cp*Math.sin(yaw*RAD), Math.sin(pitch*RAD), cp*Math.cos(yaw*RAD)];
}
const easeIO = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3)/2;
function spaceTf(c) { return `translateZ(${c.tz}px) rotateX(${c.pitch}deg) rotateY(${c.yaw}deg)`; }

// 飛行中被打斷時，用解析式估算當下姿態（與合成器的 bezier 足夠接近）
function currentCam(now) {
  if (!flight) return cam;
  const t = Math.min(1, (now - flight.t0) / flight.dur);
  const e = easeIO(t), f = flight.from, g = flight.to;
  return { yaw:   f.yaw   + (g.yaw   - f.yaw)   * e,
           pitch: f.pitch + (g.pitch - f.pitch) * e,
           tz:    f.tz    + (g.tz    - f.tz)    * e - flight.dip * Math.sin(Math.PI * e) };
}
function behindAt(p, c, pd) {
  const cd = dirOf(c.yaw, c.pitch);
  const cosD = cd[0]*pd[0] + cd[1]*pd[1] + cd[2]*pd[2];
  // 轉到鏡頭後方的面板（z 超過視點）→ CSS perspective 會炸出巨大殘影
  return c.tz - p.r * cosD > PERSP - 80;
}
function fadeAt(p, c, pd) {
  const cd = dirOf(c.yaw, c.pitch);
  const cosD = cd[0]*pd[0] + cd[1]*pd[1] + cd[2]*pd[2];
  if (c.tz <= 0) return 1;   // 球外全景不衰減
  // 球內視角＝聚焦衰減，且窗寬隨推軌深度變化：抵站（深推軌）時收窄，鄰景更快淡出、
  // 減少糾纏；島景（淺推軌／後撤）時放寬，保住「世界」感。
  const dDeg = Math.acos(Math.max(-1, Math.min(1, cosD))) / RAD;
  const zin = Math.max(0, Math.min(1, (c.tz - 1500) / 1100));   // 0＝島景以外，1＝貼站
  const inner = 45 - zin*22, outer = 62 - zin*20;               // 45→23、62→42
  return dDeg >= outer ? 0 : dDeg <= inner ? 1 : (outer - dDeg) / (outer - inner);
}
// 面板可見性與透明度：只在每段飛行頭尾各算一次（不逐幀），淡出交給 CSS transition；
// 全隱形（opacity≈0）的面板直接 visibility:hidden，省下合成成本。
// 進出全景站的飛行還要換擺法（球面 ↔ 地圖）。飛行頭尾都在鏡頭前方的面板，位置跟著飛行
// 一起變；球面那一端在鏡頭後方的面板不能跟著飛（途中穿過視點，perspective 會炸出殘影），
// 只在地圖那一端露面：進地圖時先就位、飛行後段才淡入；出地圖時在前段淡出、抵站才歸位。
function updatePanels(states, dur) {
  const end = states[states.length - 1];
  const late = [];   // 進地圖時後段才淡入的面板：[style, opacity]
  for (const id in PANELS) {
    const p = PANELS[id], st = p.div.style;
    const pd = dirOf(p.yaw, p.pitch);
    // 對準中的場景不受「已訪」調暗；球外全景是地圖，整張都要讀得到，也不調暗
    const dim = (p.visited && id !== focusId && end.tz > 0) ? .45 : 1;
    // 島封面大字不該在內容場景背景搶亮——非對準時壓暗；全景站的島名要讀得到，不壓
    const cdim = (p.cover && id !== focusId && end.tz > 0) ? .28 : 1;
    const op = p.baseOp * dim * cdim * fadeAt(p, end, pd);
    const behind = states.some(s => behindAt(p, s, pd));
    const move = dur && p.isFlat !== flatNow;
    if (move && behind && flatNow) {
      st.transition = 'none'; st.opacity = 0; setLayout(p, true);
      late.push([st, op]);
    } else if (move && behind) {
      st.transition = `opacity ${dur*.4}ms ease, visibility 0s linear ${dur*.4}ms`;
      st.visibility = 'hidden'; st.opacity = 0;
    } else {
      st.transition = dur ? `opacity ${dur}ms ease, transform ${dur}ms cubic-bezier(.65,0,.35,1)` : '';
      st.visibility = (op < .01 || behind) ? 'hidden' : '';
      st.opacity = op.toFixed(3);
      if (move) setLayout(p, flatNow);
    }
  }
  if (late.length) {
    void space.offsetWidth;   // 強制重排：「先就位、透明」生效後才開始淡入
    for (const [st, op] of late) {
      st.transition = `opacity ${dur*.4}ms ease ${dur*.6}ms, visibility 0s linear ${dur*.6}ms`;
      st.visibility = ''; st.opacity = op.toFixed(3);
    }
  }
}
function flyTo(target, onArrive, instant) {
  const now = performance.now();
  const from = currentCam(now);
  if (flight) { flight.anims.forEach(a => { try { a.cancel(); } catch (_) {} }); flight = null; }
  cam = { yaw:target.yaw, pitch:target.pitch, tz:target.tz };
  if (instant) {
    space.style.transform = spaceTf(cam);
    dolly.style.transform = 'translateZ(0px)';
    updatePanels([cam], 0);
    layoutPanels(!!target.flat);
    if (onArrive) onArrive();
    return;
  }
  const dA = Math.max(Math.abs(cam.yaw - from.yaw), Math.abs(cam.pitch - from.pitch));
  const dT = Math.abs(cam.tz - from.tz);
  const dur = Math.max(700, Math.min(1600, 600 + dA*9 + dT*.12));
  const dip = Math.min(dA, 110) * 16;   // 大轉角→途中後撤（px）
  const mid = { yaw:(from.yaw+cam.yaw)/2, pitch:(from.pitch+cam.pitch)/2, tz:Math.min(from.tz, cam.tz) - dip };
  flatNow = !!target.flat;
  updatePanels([from, mid, cam], dur);
  // 整段飛行交給合成器（Web Animations）：主執行緒在抵達前不再碰樣式
  const anims = [];
  anims.push(space.animate(
    [{ transform: spaceTf(from) }, { transform: spaceTf(cam) }],
    { duration: dur, easing: 'cubic-bezier(.65,0,.35,1)', fill: 'forwards' }));
  if (dip > 1) anims.push(dolly.animate(
    [{ transform: 'translateZ(0px)' }, { transform: `translateZ(${-dip}px)`, offset: .5 }, { transform: 'translateZ(0px)' }],
    { duration: dur, easing: 'cubic-bezier(.45,0,.55,1)', fill: 'forwards' }));
  flight = { from, to: cam, t0: now, dur, dip, anims };
  anims[0].onfinish = () => {
    space.style.transform = spaceTf(cam);
    dolly.style.transform = 'translateZ(0px)';
    anims.forEach(a => { try { a.cancel(); } catch (_) {} });
    flight = null;
    settlePanels();
    updatePanels([cam], 400);
    if (onArrive) onArrive();
  };
}

/* ============================================================
 * 導演台：主線推進（主要操作）；支線／跳島／Esc 屬次要選配
 * ============================================================ */
const hud = document.getElementById('hud');
let idx = 0;
let detourFrom = -1;   // ≥0 表示目前在支線／繞路，值為要返回的主線 idx
let userActed = false;
let activeScene = null;
let focusId = null;   // 目前對準的場景 id（免受已訪調暗）
let curId = '';       // 目前所在站 id（回報給講者視窗）；空字串＝尚未抵站，故啟動首跳不被冪等略過
let pendingId = '';   // 飛行中的目的站 id（冪等判斷用）

// HUD 以文字節點寫入：站名來自簡報內容，可能含 < 或 &，不能當 HTML 解析
function showHud(label, flash) {
  hud.textContent = label;
  if (flash) {
    hud.appendChild(document.createElement('br'));
    const f = document.createElement('span');
    f.className = 'flash'; f.textContent = flash;
    hud.appendChild(f);
  }
}
function deactivate() {
  if (activeScene) {
    // 瞬間退回魂影、不播離站動畫——否則離站場景若仍在鄰景，會看見它在背景退場
    const fxs = activeScene.querySelectorAll('.fx');
    fxs.forEach(n => n.style.transition = 'none');
    activeScene.classList.remove('active');
    void activeScene.getBoundingClientRect();   // 強制重排，讓 transition:none 立即生效
    fxs.forEach(n => n.style.transition = '');   // 還原，下次入場照常重播
    activeScene = null;
  }
}
function arrive(w) {
  if (!w.flat) {   // 離開全景站：飛行途中仍是地圖的樣子，抵站才換回場景
    document.body.classList.remove('overview');
    for (const k in PANELS) PANELS[k].div.classList.remove('here');
  }
  if (w.card) {
    const n = document.getElementById(w.id);
    if (n) { n.classList.add('active'); activeScene = n; }
  }
  document.body.dataset.active = activeScene ? activeScene.id : 'none';   // headless-readable 目前作用場景
  if ('visit' in w) {
    for (const id in PANELS) if (PANELS[id].div.dataset.island === String(w.visit+1)) PANELS[id].visited = true;
    updatePanels([cam], 400);
  }
  showHud(w.label, w.flash);
  history.replaceState(null, '', '#' + w.id);
  curId = w.id;
  dlog('arrive', w.id, '-> postState');
  postState();   // 抵站即回報給講者視窗（若有遙控端）
}
function goto_(id, instant) {
  // 冪等：已停在該站（且非飛行中）或正飛往該站 → 忽略，破除「同站被反覆下令」造成的重複運鏡／回授
  if ((flight && id === pendingId) || (!flight && id === curId)) { dlog('goto_SKIP', id, 'cur=' + curId, 'fly=' + !!flight); return; }
  dlog('goto_', id, 'from', curId, 'inst=' + !!instant);
  pendingId = id;
  const w = WP[id];
  focusId = w.card ? id : null;   // 對準的場景＝焦點，免受已訪調暗
  // 全景站是地圖：起飛時就換成地圖的樣子（樣式在 host），並標出繞路前所在的那一站；
  // 離開時相反，地圖的樣子留到抵站（arrive）——反白的那一格一路放大成要去的場景
  if (w.flat) {
    const here = detourFrom >= 0 ? ROUTE[detourFrom] : '';
    for (const k in PANELS) PANELS[k].div.classList.toggle('here', k === here);
    document.body.classList.add('overview');
  }
  deactivate();                   // 離站退魂影 → 再訪重播入場
  flyTo(w, () => arrive(w), instant);
}

function advance() {
  userActed = true;
  if (detourFrom >= 0) { idx = detourFrom; detourFrom = -1; goto_(ROUTE[idx]); return; }  // 支線返回原站
  if (idx < ROUTE.length - 1) { idx++; goto_(ROUTE[idx]); }
  else showHud(WP[ROUTE[idx]].label, '（已是終點）');
}
function back() {
  userActed = true;
  if (detourFrom >= 0) { idx = detourFrom; detourFrom = -1; goto_(ROUTE[idx]); return; }
  if (idx > 0) { idx--; goto_(ROUTE[idx]); }
}
function detour(id) {
  userActed = true;
  if (detourFrom < 0) detourFrom = idx;
  goto_(id);
}

/* ---------- 舞台縮放：1920×1080 等比貼合視窗 ---------- */
const fitEl = document.getElementById('fit');
function refit() {
  const f = Math.min(innerWidth/1920, innerHeight/1080);
  fitEl.style.transform = `translate(-50%,-50%) scale(${f})`;
}

/* ---------- 抵站垂直置中校正（實測） ----------
   CSS 3D perspective 對離軸面板的投影，內容垂直中心不會落在畫面中心（實測抵站偏上＝頭重，
   且偏移量隨偏航/俯仰非線性變化、無法可靠解析預測）。故載入時逐一把鏡頭對到每個取景場景，
   量測其實際螢幕中心，對該場景群組施加 y 平移校正到畫面正中。一次性樣式寫入、非逐幀，
   且只在載入與字型就緒後各跑一次；視窗縮放是等比，置中比例不變，無需重算。 */
function calibrateFraming() {
  const sTf = space.style.transform, dTf = dolly.style.transform, vh = innerHeight;
  const wasFlat = flatNow, wasOverview = document.body.classList.contains('overview');
  dolly.style.transform = 'translateZ(0px)';
  // 量測只需幾何（不透明度不影響 getBoundingClientRect），故**不碰不透明度**——否則強制 opacity:1
  // 再移除會讓每個場景 1→.12 跑一次轉場＝背景全體「亮起又淡下」的動畫。這裡只去掉 12px 入場位移
  // 並關轉場以量到「就位」位置；場景全程維持預設魂影（.12）。
  const rest = document.createElement('style');
  const FROZEN = '.panel,.panel svg{transition:none!important}';   // 面板與封面的變形也不准跑轉場
  rest.textContent = '.scene .fx{transform:none!important;transition:none!important}' + FROZEN;
  document.head.appendChild(rest);
  // 取景是球面上的事：停在全景站時（例如以 #hub 開啟）先暫時捲回球面、卸下地圖樣式再量
  document.body.classList.remove('overview');
  layoutPanels(false);
  for (const id in WP) {
    const w = WP[id]; if (!w.card) continue;
    const p = PANELS[id], g = p.svg.querySelector('.scene'); if (!g) continue;
    for (let pass = 0; pass < 3; pass++) {           // 迭代收斂（放大率為估值）
      space.style.transform = spaceTf(w);
      const r = g.getBoundingClientRect(); if (!r.height) break;
      const mag = (p.div.getBoundingClientRect().height / p.h) || 1;
      const delta = (vh/2 - (r.top + r.bottom)/2) / mag;
      if (Math.abs(delta) < 1.5) break;
      const m = /translate\(0,(-?[\d.]+)\)/.exec(g.getAttribute('transform') || '');
      g.setAttribute('transform', `translate(0,${((m ? +m[1] : 0) + delta).toFixed(1)})`);
    }
  }
  // 卸下 transform 覆寫但仍關轉場 → 強制重排讓入場位移瞬間回到自然狀態（無動畫）→ 再還原轉場
  layoutPanels(wasFlat);
  document.body.classList.toggle('overview', wasOverview);
  rest.textContent = '.scene .fx{transition:none!important}' + FROZEN;
  void document.body.getBoundingClientRect();
  rest.remove();
  space.style.transform = sTf; dolly.style.transform = dTf;
}

/* ============================================================
 * 講者視窗遙控（presenter.html ↔ 本檔，全程 postMessage——file:// 下跨視窗最穩）
 * 簡報窗（window.open）與兩個預覽 iframe 都是本檔實例：
 *   預覽窗 ?role=preview＝瞬移、不互動；正式簡報窗＝動畫運鏡。
 * 任一抵站（arrive）都把當前站回報給遙控端；接收 next／prev／goto 指令。
 * ============================================================ */
function manifestRoute() {
  return ROUTE.map(id => ({ id, label:(WP[id] && WP[id].label) || id, note:NOTES[id] || '' }));
}
/* 列印用：把一站的場景 SVG 轉成「平面、置中、全亮」的投影片標記。
   依內容外框（contentBox）重設 viewBox＝列印出抵站取景的放大樣子；去掉抵站垂直校正位移；
   .fx 在 presenter 列印頁無 deck 的 .12 規則 → 自然全亮。浮水印在另一面板（wm*），不入此 SVG。 */
function slideMarkup(id) {
  const p = PANELS[id];
  if (!p || !p.svg) return null;
  const b = contentBox(p.svg), pad = 44;
  const x = Math.round(b.cx - b.w/2 - pad), y = Math.round(b.cy - b.h/2 - pad);
  const w = Math.round(b.w + pad*2), h = Math.round(b.h + pad*2);
  const clone = p.svg.cloneNode(true);
  const sc = clone.querySelector('.scene'); if (sc) sc.removeAttribute('transform');
  clone.setAttribute('xmlns', SVGNS);
  clone.setAttribute('viewBox', x + ' ' + y + ' ' + w + ' ' + h);
  clone.removeAttribute('style');
  return { id, label:(WP[id] && WP[id].label) || id, w, h, svg:clone.outerHTML };
}
function curStateMsg() {
  return { deck:'state', role:ROLE, id:curId, idx, total:ROUTE.length,
           label:(WP[curId] && WP[curId].label) || curId, note:NOTES[curId] || '' };
}
function postState(target) {
  const t = target || REMOTE;
  if (t) t.postMessage(curStateMsg(), '*');
}
function gotoId(id, instant) {
  if (!WP[id]) return;
  const ri = ROUTE.indexOf(id);
  if (ri >= 0) { detourFrom = -1; idx = ri; goto_(id, instant); }   // 主線站：同步游標
  else { if (detourFrom < 0) detourFrom = idx; goto_(id, instant); } // 非主線（島佔位等）：當繞路
}

/* ============================================================
 * boot()：所有副作用集中於此，由內容腳本在「內容＋世界佈局＋ROUTE/NOTES
 * 全部就緒後」呼叫。在此之前 engine.js 只做純定義（與抓取 DOM 參考）。
 * ============================================================ */
function boot() {
  /* ---------- 舞台縮放 ---------- */
  refit();
  addEventListener('resize', refit);

  /* ---------- 輸入：點擊＝下一站；點支線小景＝進支線 ---------- */
  document.addEventListener('click', e => {
    if (ROLE === 'preview') return;   // 預覽窗不互動（推進由講者視窗遙控）
    const side = e.target.closest && e.target.closest('.panel.sidecard');
    if (side) { detour(side.id.replace(/^p-/, '')); return; }
    advance();
  });
  addEventListener('keydown', e => {
    if (ROLE === 'preview') return;   // 預覽窗不吃鍵盤
    if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); advance(); }
    else if (e.key === 'ArrowLeft') back();
    else if (e.key === 'ArrowDown') {   // 進入目前島的支線小景（若有）——由世界推得，不寫死站 id
      const m = (ROUTE[idx] || '').match(/^s(\d)/);
      const sc = m && document.querySelector('.panel.sidecard[data-island="' + m[1] + '"]');
      if (sc) detour(sc.id.replace(/^p-/, ''));
    }
    else if (e.key === 'Escape') detour('hub');
    else if (e.key >= '1' && e.key <= '9' && WP['isl' + e.key]) detour('isl' + e.key);   // 跳島：島數由 WP 決定
    else if (e.key === 'f' || e.key === 'F') {   // 全螢幕（雙螢幕投影用）
      if (document.fullscreenElement) document.exitFullscreen();
      else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
    }
  });

  /* ---------- 講者視窗遙控收訊 ---------- */
  addEventListener('message', e => {
    const d = e.data; if (!d || d.deck == null) return;
    const src = e.source || REMOTE;
    dlog('recv', JSON.stringify(d).slice(0, 80));
    if (d.deck === 'cmd') {
      if (d.cmd === 'next') advance();
      else if (d.cmd === 'prev') back();
      else if (d.cmd === 'goto' && d.id) gotoId(d.id, !!d.instant || ROLE === 'preview');   // 預覽窗／初次對齊瞬移；其餘動畫運鏡
    } else if (d.deck === 'hello') {
      postState(src);
    } else if (d.deck === 'manifest?') {
      if (src) src.postMessage({ deck:'manifest', route:manifestRoute() }, '*');
    } else if (d.deck === 'slides?') {
      if (src) src.postMessage({ deck:'slides', slides:ROUTE.map(slideMarkup).filter(Boolean) }, '*');
    }
  });

  /* ---------- 抵站垂直置中校正：載入即跑一次，字型就緒後再跑一次 ---------- */
  calibrateFraming();
  document.fonts.ready.then(() => { calibrateFraming(); if (activeScene) { space.style.transform = spaceTf(cam); } });

  /* ---------- 啟動：定格 S0；無自動運鏡，一切由點擊觸發 ----------
     arrive() 會以 replaceState 改寫 hash，故啟動前先記住啟動時的 #debug 旗標 */
  const LAUNCH_DEBUG = location.hash === '#debug';
  const startId = location.hash.slice(1);
  if (startId && WP[startId]) {
    const ri = ROUTE.indexOf(startId);
    if (ri >= 0) idx = ri; else detourFrom = 0;
    goto_(startId, true);
  } else {
    goto_('s0', true);
  }

  /* ---------- #debug：抵站可讀性＋版面溢出自檢（headless 驗證用）----------
     min-font 與 active 為純資料（字級×k、目前作用場景），同步寫入 dataset——
     inline script 在 load 前已跑完，故 headless `--dump-dom` 必能讀到（不必等字型）。
     overflow 需真實字形度量（getBBox），保留在 fonts.ready 後（互動式 #debug 用）。 */
  if (LAUNCH_DEBUG) {
    const tiny = [];
    document.querySelectorAll('.scene').forEach(sc => {
      const k = WP[sc.id] && WP[sc.id].k;
      if (!k) return;
      sc.querySelectorAll('text').forEach(t => {
        const eff = +t.getAttribute('font-size') * k;
        if (eff < MIN_EFF) tiny.push(sc.id + ':' + Math.round(eff) + 'px:' + t.textContent.slice(0, 8));
      });
    });
    document.body.dataset.minfont = tiny.length ? tiny.join('|') : 'ok';
    document.fonts.ready.then(() => {
      const bad = [];
      document.querySelectorAll('.scene').forEach(sc => {
        const w = +sc.dataset.w, h = +sc.dataset.h;
        sc.querySelectorAll('text').forEach(t => {
          const b = t.getBBox();
          if (b.x + b.width > w + 30 || b.y + b.height > h + 6) bad.push(sc.id + ':' + t.textContent.slice(0, 12));
        });
      });
      document.body.dataset.overflow = bad.length ? bad.join('|') : 'none';
      console.log('overflow:', bad.length ? bad : 'clean', '| minfont:', tiny.length ? tiny : 'clean');
    });
  }
}
