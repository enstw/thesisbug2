/* deck.html#debug 自我檢查：字級下限與是否溢出投影片框。
   只在網址為 #debug 時啟用，平常開啟與上台時不做任何事。
   必須在 deck-stage.js 之前載入，因為 deck-stage 一啟動就把網址的 # 改成頁碼。

   每到一頁、等進場動畫跑完後檢查該頁，結果寫在 document.body.dataset：
     minfont      ok ＝ 已檢查各頁的可見文字都 ≥ FLOOR（1920×1080 設計像素）；否則 small
     minfontBad   不合格處，例如「3 p.lead 30px; 5 td 28px」（頁碼與網址 #N 相同）
     overflow     none ＝ 沒有東西超出投影片框或被容器裁掉；否則 found
     overflowBad  超出處，例如「4 .content +62px; 6 .card 被裁 18px」
     checked      已檢查的頁碼
   同樣的內容也會以 console.warn 輸出。調整 +／− 字級後先前結果作廢，重新檢查目前這頁。 */
(() => {
  if (location.hash !== '#debug') return;

  const FLOOR = 34;                        // 表格與標籤的下限；內文預設 40
  const EXEMPT = '.hero__hint';            // 講者用的按鍵提示，觀眾不需要讀
  const results = new Map();               // 頁碼 → { small: [], overflow: [] }

  function describe(el) {
    const cls = [...el.classList].slice(0, 2).map(c => '.' + c).join('');
    return el.tagName.toLowerCase() + cls;
  }

  function textNodes(slide) {
    const walker = document.createTreeWalker(slide, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const el = node.parentElement;
        if (!node.textContent.trim() || !el) return NodeFilter.FILTER_REJECT;
        if (el.closest('[aria-hidden="true"], script, style, ' + EXEMPT)) return NodeFilter.FILTER_REJECT;
        if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    return nodes;
  }

  function check(slide, number) {
    const frame = slide.getBoundingClientRect();
    const scale = frame.width / slide.offsetWidth || 1;   // 舞台縮放；換回設計像素用
    const small = [], overflow = [];
    const seenSmall = new Set();

    for (const node of textNodes(slide)) {
      const el = node.parentElement;
      let size = parseFloat(getComputedStyle(el).fontSize);
      const svg = el.closest('svg');
      if (svg && el instanceof SVGElement) {
        const ctm = el.getScreenCTM();
        if (ctm) size *= Math.hypot(ctm.a, ctm.b) / scale;   // viewBox 縮放後的實際大小
      }
      if (size < FLOOR - 0.5 && !seenSmall.has(el)) {
        seenSmall.add(el);
        small.push(`${number} ${describe(el)} ${Math.round(size)}px`);
      }
      const range = document.createRange();
      range.selectNodeContents(node);
      const r = range.getBoundingClientRect();
      const out = Math.max(frame.left - r.left, r.right - frame.right,
                           frame.top - r.top, r.bottom - frame.bottom) / scale;
      if (out > 1) overflow.push(`${number} ${describe(el)} 出框 ${Math.round(out)}px`);
    }

    // 內容區塞不下時會往上下溢出、壓到頁首；設了 overflow 的容器（如 .card）則會把文字裁掉。
    // 投影片本身不在此列：它的背景動畫本來就超出框，出框的文字已由上面逐字檢查。
    for (const el of slide.querySelectorAll('*')) {
      if (el.closest('[aria-hidden="true"], svg, ' + EXEMPT)) continue;
      const style = getComputedStyle(el);
      const clips = style.overflowX !== 'visible' || style.overflowY !== 'visible';
      if (!clips && !el.classList.contains('content')) continue;
      let extra = Math.max(el.scrollHeight - el.clientHeight, el.scrollWidth - el.clientWidth);
      if (!clips) {
        // .content 置中：塞不下時上下各溢出一半，scrollHeight 只看得到往下那一半，改量子元素。
        const box = el.getBoundingClientRect();
        for (const child of el.children) {
          const r = child.getBoundingClientRect();
          extra = Math.max(extra, (box.top - r.top) / scale, (r.bottom - box.bottom) / scale);
        }
      }
      if (extra > 2) overflow.push(`${number} ${describe(el)} ${clips ? '被裁' : '溢出'} ${Math.round(extra)}px`);
    }
    return { small, overflow };
  }

  function publish() {
    const small = [], overflow = [];
    for (const r of results.values()) { small.push(...r.small); overflow.push(...r.overflow); }
    const data = document.body.dataset;
    data.minfont = small.length ? 'small' : 'ok';
    data.minfontBad = small.join('; ');
    data.overflow = overflow.length ? 'found' : 'none';
    data.overflowBad = overflow.join('; ');
    data.checked = [...results.keys()].sort((a, b) => a - b).join(',');
  }

  let pending = 0;
  async function settle(slide, number) {
    const ticket = ++pending;
    await document.fonts.ready;
    await new Promise(requestAnimationFrame);
    // 只等有限長度的動畫（進場）；.flow／.pulse 這類無限迴圈不等。
    const finite = slide.getAnimations({ subtree: true })
      .filter(a => Number.isFinite(a.effect?.getComputedTiming().endTime));
    await Promise.all(finite.map(a => a.finished.catch(() => {})));
    await new Promise(requestAnimationFrame);
    if (ticket !== pending || !slide.hasAttribute('data-deck-active')) return;   // 已換頁
    const r = check(slide, number);
    results.set(number, r);
    publish();
    for (const line of [...r.small, ...r.overflow]) console.warn('[deck-check]', line);
  }

  let current = null;
  document.addEventListener('slidechange', (event) => {
    const { slide, index } = event.detail || {};
    if (!slide) return;
    current = { slide, number: index + 1 };
    results.delete(index + 1);               // 重新進場：等這次檢查完才算數
    publish();
    settle(slide, index + 1);
  });

  // +／− 改的是 <html> 上的 --deck-font-scale，舊結果作廢。
  new MutationObserver(() => {
    results.clear();
    publish();
    if (current) settle(current.slide, current.number);
  }).observe(document.documentElement, { attributes: true, attributeFilter: ['style'] });

  console.info(`[deck-check] #debug：每到一頁檢查字級 ≥ ${FLOOR}px 與溢出，結果見 document.body.dataset`);
})();
