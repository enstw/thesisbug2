/* deck-motion.js — deck-svg 的活潑模式（選用的漸進增強）。
   沒有這支腳本、或在簡報裡按 M 關掉，deck 就是原本的靜態簡報；它只讀投影片上的幾個 data- 屬性：

   data-beat="n"          第 n 拍出現（0 = 進頁時）。→ 鍵先播拍，拍播完才換頁；← 退一拍（瞬間），退到底才回上一頁（全展開）。
   data-fx                fadeup（預設）｜pop｜draw（SVG 線條畫出）｜type（逐字，純文字元素）｜count（數字遞增，從元素文字抓數字）｜hold（瞬間出現）
   data-delay、data-dur   秒；同一拍裡用 delay 錯開。
   data-id="x"            跨頁延續：進頁時同名元素從前一頁（找不到就往更早的頁找）的位置與大小滑過來（FLIP），所以元素「不消失只改位置」。
   <section data-enter>   進頁轉場：fade（預設）｜push｜zoom；zoom 配 data-zoom-from="<data-id>"，鏡頭從前一頁那個元素推入。
   data-along="<selector>" 沿該頁某條 SVG 路徑循環移動（流動封包），data-period 秒；circle 改 cx/cy，其他元素改 transform。

   拍數隨鏡頭緩推 4%。縮圖（?_snthumb）、#debug、列印一律全展開、不轉場，所以 deck-check 與 PDF 看到的是完整的頁。
   prefers-reduced-motion 下全部瞬間完成。
   它攔 deck-stage 的 deckstep 事件（可取消）而不改換頁本身，runtime 因此不認識「拍」，這支腳本整支拔掉也不影響簡報。
   標了 data-beat 的元素會被拿掉 .rise／.dN，因為 .rise 的 CSS 動畫會蓋過行內樣式，兩者只能擇一。
   載入順序：在 deck-stage.js 之前（和 deck-check.js 一樣要在 hash 被改寫前讀到 #debug）。 */
(() => {
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const THUMB = /[?&]_snthumb=/.test(location.search);
  const DEBUG = /(^#|[#&])debug(&|$)/.test(location.hash);
  const REVEAL = THUMB || DEBUG;
  const KEY = 'deck-motion.' + location.pathname;
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const easeOut = (p) => 1 - Math.pow(1 - p, 3);
  const easeIn = (p) => p * p * p;
  const easeInOut = (p) => (p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const now = () => performance.now() / 1000;
  const FX = {
    fadeup: (it, p) => { it.el.style.opacity = p; it.el.style.transform = `translateY(${(1 - easeOut(p)) * 36}px)`; },
    pop: (it, p) => { it.el.style.opacity = p; it.el.style.transform = `scale(${.82 + .18 * easeOut(p)})`; },
    draw: (it, p) => { it.el.style.opacity = p > 0 ? 1 : 0; it.el.style.strokeDasharray = 1; it.el.style.strokeDashoffset = 1 - easeOut(p); },
    hold: (it, p) => { it.el.style.opacity = p > 0 ? 1 : 0; },
    type: (it, p) => { it.el.style.opacity = 1; it.el.textContent = it.text.slice(0, Math.round(it.text.length * p)); },
    count: (it, p) => { it.el.style.opacity = p > 0 ? 1 : 0; it.el.textContent = it.fmt(it.n * easeOut(p)); },
  };
  const TRANS = { fade: .6, push: .7, zoom: .8 };

  // ---- 每頁的拍：解析一次，存在 WeakMap ----
  const parsed = new WeakMap();
  function items(slide) {
    if (parsed.has(slide)) return parsed.get(slide);
    const list = [];
    const make = (el, beat) => {
      el.classList.remove('rise', 'd1', 'd2', 'd3', 'd4');
      const it = { el, beat, delay: parseFloat(el.dataset.delay) || 0, dur: el.dataset.dur != null ? parseFloat(el.dataset.dur) : .6, fx: FX[el.dataset.fx] ? el.dataset.fx : 'fadeup' };
      if (it.fx === 'draw') el.setAttribute('pathLength', '1');
      if (it.fx === 'type') it.text = el.textContent;
      if (it.fx === 'count') {
        const m = /^([^\d]*)(\d[\d,]*(?:\.\d+)?)(.*)$/s.exec(el.textContent.trim());
        if (m) {
          const dec = (m[2].split('.')[1] || '').length, grp = m[2].includes(',');
          it.n = parseFloat(m[2].replace(/,/g, ''));
          it.fmt = (v) => m[1] + v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec, useGrouping: grp }) + m[3];
        } else it.fx = 'fadeup';
      }
      if (el.dataset.along) it.along = { sel: el.dataset.along, period: parseFloat(el.dataset.period) || 3, path: null, len: 0 };
      list.push(it);
      return it;
    };
    slide.querySelectorAll('[data-beat]').forEach((el) => make(el, parseInt(el.dataset.beat, 10) || 0));
    slide.querySelectorAll('[data-along]:not([data-beat])').forEach((el) => { const it = make(el, 0); it.fx = 'hold'; });
    parsed.set(slide, list);
    return list;
  }
  const beatsOf = (list) => list.reduce((m, it) => Math.max(m, it.beat), 0);

  // ---- 狀態 ----
  let on = false, trans = null, stageEl = null, toastEl = null, toastTimer = 0;
  const S = { slide: null, items: [], beat: 0, beats: 0, beatStart: 0, t0: 0, cam: 0, late: [] };
  const sections = () => (stageEl ? Array.from(stageEl.children).filter((c) => c.tagName === 'SECTION') : []);
  const index = () => sections().indexOf(S.slide);

  function announce() {
    document.dispatchEvent(new CustomEvent('deckbeat', { detail: { beat: S.beat, beats: on && !REVEAL ? S.beats : 0, index: index() } }));
  }
  function setSlide(slide, beat, { animate }) {
    const t = now();
    if (S.slide && S.slide !== slide) S.slide.style.transform = '';
    S.slide = slide; S.items = items(slide); S.beats = beatsOf(S.items);
    S.beat = Math.min(beat, S.beats); S.beatStart = animate ? t : t - 1e3; S.t0 = t;
    S.cam = S.beat / Math.max(S.beats, 1); S.late = [];
    announce();
  }

  // ---- 量位置：暫時拿掉祖先的 transform 與 .rise 動畫，量的是排版位置，不是動畫中途 ----
  const rect = (e) => { const r = e.getBoundingClientRect(); return { x: (r.left + r.right) / 2, y: (r.top + r.bottom) / 2, w: r.width, h: r.height }; };
  function measure(el, slide) {
    const saved = [];
    for (let a = el; a && a !== slide; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (cs.transform !== 'none' || cs.animationName !== 'none') { saved.push([a, a.style.transform, a.style.animation]); a.style.transform = 'none'; a.style.animation = 'none'; }
    }
    const r = rect(el);
    for (const [a, tr, an] of saved) { a.style.transform = tr; a.style.animation = an; }
    return r;
  }
  function findSource(id, slide, prev) {
    const q = `[data-id="${CSS.escape(id)}"]`;
    if (prev) { const s = prev.querySelector(q); if (s) return { el: s, slide: prev, inPrev: true }; }
    const all = sections(), i = all.indexOf(slide);
    for (let k = i - 1; k >= 0; k--) { if (all[k] === prev) continue; const s = all[k].querySelector(q); if (s) return { el: s, slide: all[k], inPrev: false }; }
    return null;
  }

  // ---- 轉場：前一頁暫時留在畫面上一起動 ----
  function startTransition(prev, slide) {
    const type = TRANS[slide.dataset.enter] ? slide.dataset.enter : 'fade';
    const dur = RM ? 0 : TRANS[type];
    const k = slide.getBoundingClientRect().width / (slide.offsetWidth || 1920) || 1;   // 畫布縮放：量到的像素 ÷ 設計像素
    const flips = [], hidden = [], flipSet = new Set();
    slide.querySelectorAll('[data-id]').forEach((e) => {
      const src = findSource(e.dataset.id, slide, prev);
      if (!src) return;
      let it = S.items.find((i) => i.el === e);
      if (!it) { it = { el: e, beat: 0, delay: 0, dur: 0, fx: 'hold' }; S.items.push(it); } else it.fx = 'hold';
      const rb = measure(e, slide), ra = measure(src.el, src.slide);
      const f = { el: e, dx: (ra.x - rb.x) / k, dy: (ra.y - rb.y) / k, sx: rb.w > 1 ? ra.w / rb.w : 1, sy: rb.h > 1 ? ra.h / rb.h : 1, beat: it.beat };
      if (src.inPrev) { hidden.push([src.el, src.el.style.opacity]); src.el.style.opacity = 0; }
      if (f.beat === 0) { flips.push(f); flipSet.add(e); } else S.late.push(f);
    });
    let origin = '50% 50%';
    if (type === 'zoom' && slide.dataset.zoomFrom) {
      const tgt = prev.querySelector(`[data-id="${CSS.escape(slide.dataset.zoomFrom)}"]`);
      if (tgt) { const r = measure(tgt, prev), s = prev.getBoundingClientRect(); origin = `${(r.x - s.left) / k}px ${(r.y - s.top) / k}px`; }
    }
    Object.assign(prev.style, { visibility: 'visible', opacity: '1', zIndex: '2', pointerEvents: 'none' });
    slide.style.zIndex = '1';
    trans = { prev, slide, type, dur, start: now(), flips, flipSet, hidden, origin };
    S.beatStart = now() + .25;
    paintTransition(now());
  }
  function paintTransition(t) {
    const T = trans, p = T.dur ? clamp((t - T.start) / T.dur) : 1, e = easeInOut(p), A = T.prev.style, B = T.slide.style;
    const out = 1 - clamp(p / .5), inn = clamp((p - .3) / .7);
    if (T.type === 'fade') { A.opacity = out; A.transform = 'scale(1.04)'; B.opacity = inn; B.transform = 'scale(1)'; }
    else if (T.type === 'push') { A.opacity = out; A.transform = `translateX(${-120 * e}px) scale(1.04)`; B.opacity = inn; B.transform = `translateX(${120 * (1 - e)}px)`; }
    else { A.transformOrigin = T.origin; A.opacity = 1 - clamp(p * 1.5); A.transform = `scale(${1.04 + 1.6 * easeIn(p)})`; B.opacity = clamp((p - .25) / .75); B.transform = `scale(${.96 + .04 * e})`; }
    const fp = easeInOut(clamp((p - .05) / .8));
    for (const f of T.flips) f.el.style.transform = `translate(${f.dx * (1 - fp)}px,${f.dy * (1 - fp)}px) scale(${f.sx + (1 - f.sx) * fp},${f.sy + (1 - f.sy) * fp})`;
    if (p >= 1) finishTransition();
  }
  function finishTransition() {
    const T = trans; if (!T) return; trans = null;
    for (const f of T.flips) f.el.style.transform = '';
    for (const [el, op] of T.hidden) el.style.opacity = op;
    Object.assign(T.prev.style, { visibility: '', opacity: '', zIndex: '', pointerEvents: '', transform: '', transformOrigin: '' });
    Object.assign(T.slide.style, { zIndex: '', opacity: '' });
    const t = now(); if (S.beatStart > t) S.beatStart = t;
  }

  // ---- 每幀 ----
  function along(it, t, p, slide) {
    const a = it.along;
    if (!a.path) { a.path = slide.querySelector(a.sel); if (!a.path || !a.path.getTotalLength) { it.along = null; return; } a.len = a.path.getTotalLength(); }
    if (p <= 0) return;
    const u = ((t - S.t0) % a.period) / a.period, pt = a.path.getPointAtLength(u * a.len);
    if (it.el.tagName.toLowerCase() === 'circle') { it.el.setAttribute('cx', pt.x); it.el.setAttribute('cy', pt.y); }
    else it.el.setAttribute('transform', `translate(${pt.x} ${pt.y})`);
  }
  function paintItems(list, t, b, bs, slide) {
    const all = REVEAL || !on;
    for (const it of list) {
      let p = all ? 1 : it.beat < b ? 1 : it.beat > b ? 0 : clamp((t - bs - it.delay) / Math.max(it.dur, .001));
      if (RM && !all) p = it.beat <= b ? 1 : 0;
      if (!(trans && trans.flipSet.has(it.el))) FX[it.fx](it, p);
      if (it.along) along(it, t, p, slide);
    }
  }
  function frame() {
    const t = now();
    if (trans) paintTransition(t);
    if (S.slide) {
      paintItems(S.items, t, S.beat, S.beatStart, S.slide);
      for (const f of S.late) {
        if (S.beat < f.beat) continue;
        const fp = RM || S.beat > f.beat ? 1 : easeInOut(clamp((t - S.beatStart) / .8));
        f.el.style.transform = fp >= 1 ? '' : `translate(${f.dx * (1 - fp)}px,${f.dy * (1 - fp)}px) scale(${f.sx + (1 - f.sx) * fp},${f.sy + (1 - f.sy) * fp})`;
      }
      if (on && !REVEAL && !trans && S.beats) { S.cam += (S.beat / S.beats - S.cam) * (RM ? 1 : .06); S.slide.style.transform = `scale(${1 + .04 * S.cam})`; }
    }
    requestAnimationFrame(frame);
  }

  // ---- 與 deck-stage 的接點 ----
  document.addEventListener('deckstep', (e) => {
    if (!on || REVEAL || !S.slide) return;
    if (trans) { finishTransition(); e.preventDefault(); return; }
    const d = e.detail && e.detail.direction;
    if (d > 0 && S.beat < S.beats) { S.beat++; S.beatStart = now(); announce(); e.preventDefault(); }
    else if (d < 0 && S.beat > 0) { S.beat--; S.beatStart = now() - 1e3; announce(); e.preventDefault(); }
  });
  document.addEventListener('slidechange', (e) => {
    const d = e.detail || {}; if (!d.slide) return;
    stageEl = stageEl || document.querySelector('deck-stage');
    if (trans) finishTransition();
    const forward = d.previousSlide && d.index > d.previousIndex;
    if (on && !REVEAL && forward) { setSlide(d.slide, 0, { animate: true }); startTransition(d.previousSlide, d.slide); }
    else setSlide(d.slide, d.previousSlide && d.index < d.previousIndex ? Infinity : 0, { animate: !d.previousSlide });
  });

  function toast(text) {
    if (!toastEl) { toastEl = document.createElement('div'); toastEl.style.cssText = 'position:fixed;left:50%;bottom:6%;transform:translateX(-50%);z-index:2147483647;padding:10px 18px;border-radius:6px;background:rgba(0,0,0,.82);color:#fff;font:16px/1.4 system-ui,sans-serif;pointer-events:none;transition:opacity .3s'; document.body.appendChild(toastEl); }
    toastEl.textContent = text; toastEl.style.opacity = '1';
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { toastEl.style.opacity = '0'; }, 1500);
  }
  function setOn(v) {
    on = v; try { localStorage.setItem(KEY, v ? '1' : '0'); } catch (e) {}
    document.documentElement.toggleAttribute('data-deck-motion', v);
    if (!v) { finishTransition(); if (S.slide) S.slide.style.transform = ''; }
    announce();
  }
  window.addEventListener('keydown', (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target; if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (e.key === 'm' || e.key === 'M') { setOn(!on); toast(on ? '活潑模式：開（→ 逐拍）' : '活潑模式：關'); e.preventDefault(); }
  });
  window.addEventListener('message', (e) => { if (e.data && e.data.deckMotionKey) { setOn(!on); toast(on ? '活潑模式：開（→ 逐拍）' : '活潑模式：關'); } });

  function init() {
    stageEl = document.querySelector('deck-stage');
    let stored = null; try { stored = localStorage.getItem(KEY); } catch (e) {}
    const authored = document.documentElement.hasAttribute('data-deck-motion') || !!document.querySelector('deck-stage [data-beat]');
    on = !REVEAL && (stored == null ? authored : stored === '1');
    document.documentElement.toggleAttribute('data-deck-motion', on);
    requestAnimationFrame(frame);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
