/* deck-stage-presenter v6 — press P to spawn a child window with speaker
   notes + two iframe-based thumbnails (current + next), built on the
   deck-stage v2 _snthumb URL contract.

   Each thumbnail is an <iframe> loading the deck with `?_snthumb=1#<N>`:
     - `?_snthumb=...` is detected by deck-stage v2 (line ~566) and sets
       the `no-rail` attribute, so the iframe shows a clean stage with no
       editor rail and no scale offset.
     - `#<N>` (1-indexed) is parsed by `_restoreIndex` so the iframe lands
       on the requested slide.
   Iframes are loaded once at popup mount; subsequent slide changes call
   `deckStage.goTo(N)` cross-frame (same-origin happy path), with an
   `iframe.src = ...` reload fallback for browsers that block file:// →
   file:// frame access (notably Chrome's null-origin file:// policy). */
(() => {
  let p = null, notes = [], labels = [];
  const stage = () => document.querySelector('deck-stage');

  function labelForSlide(s) {
    const explicit = s.getAttribute('data-label');
    if (explicit) return explicit;
    const screen = s.getAttribute('data-screen-label');
    if (screen) return screen.replace(/^\s*\d+\s*/, '').trim();
    const h = s.querySelector('h1, h2, h3, [data-title]');
    return h ? (h.textContent || '').trim().slice(0, 80) : '';
  }

  function load() {
    try { notes = JSON.parse(document.getElementById('speaker-notes').textContent) || []; } catch (e) { notes = []; }
    labels = Array.from(document.querySelectorAll('deck-stage > section')).map(labelForSlide);
  }

  function presenterDoc(deckUrl) {
    return `<!doctype html><html lang="zh-Hant"><head>
<meta charset="utf-8"><title>Presenter — Speaker Notes</title>
<style>
:root{--paper:oklch(0.985 0.004 85);--paper-2:oklch(0.965 0.006 85);--ink:oklch(0.18 0.012 265);--ink-2:oklch(0.34 0.012 265);--ink-3:oklch(0.55 0.010 265);--rule:oklch(0.84 0.008 85);--accent:oklch(0.50 0.15 25);--serif:"Noto Serif TC","Source Han Serif TC",serif;--sans:"Noto Sans TC",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,monospace;}
html,body{margin:0;padding:0;height:100%;background:var(--paper);color:var(--ink);font-family:var(--sans);}
body{display:flex;flex-direction:column;padding:14px 20px 18px;box-sizing:border-box;gap:14px;}
.thumbs{display:flex;gap:8px;border-bottom:1px solid var(--rule);padding-bottom:10px;}
.thumb{flex:1 1 0;min-width:0;aspect-ratio:16/9;position:relative;cursor:pointer;border:1px solid var(--rule);border-radius:3px;background:#000;overflow:hidden;transition:border-color 120ms ease,box-shadow 120ms ease;}
.thumb:hover{border-color:var(--ink-3);}
.thumb[data-active]{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent);}
.thumb.empty{display:flex;align-items:center;justify-content:center;background:var(--paper-2);cursor:default;color:var(--ink-3);font-family:var(--mono);font-size:11px;letter-spacing:0.08em;border-color:var(--rule);}
.thumb iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:#000;pointer-events:none;}
.thumb .meta{position:absolute;left:6px;top:5px;display:flex;align-items:center;gap:6px;z-index:2;background:rgba(255,255,255,0.85);padding:2px 7px;border-radius:3px;max-width:calc(100% - 12px);}
.thumb .meta .k{font-family:var(--mono);font-size:9px;letter-spacing:0.10em;text-transform:uppercase;color:var(--accent);}
.thumb[data-kind="next"] .meta .k{color:var(--ink-3);}
.thumb .meta .num{font-family:var(--mono);font-size:10px;color:var(--ink-2);font-variant-numeric:tabular-nums;}
.thumb .meta .lbl{font-family:var(--sans);font-size:10px;color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
header{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--rule);padding-bottom:12px;}
.label{font-family:var(--mono);font-size:12px;letter-spacing:0.10em;color:var(--accent);text-transform:uppercase;}
.pn{font-family:var(--mono);font-size:13px;color:var(--ink-3);font-variant-numeric:tabular-nums;}
h1{font-family:var(--serif);font-size:22px;font-weight:600;margin:0;color:var(--ink);line-height:1.3;}
.note{font-family:var(--serif);font-size:17px;line-height:1.6;color:var(--ink-2);white-space:pre-wrap;flex:1;overflow-y:auto;min-height:0;}
.empty-note{color:var(--ink-3);font-style:italic;font-size:15px;}
.footer{border-top:1px solid var(--rule);padding-top:10px;font-family:var(--mono);font-size:11px;color:var(--ink-3);line-height:1.6;letter-spacing:0.02em;}
.kbd{display:inline-block;padding:1px 6px;background:var(--paper-2);border:1px solid var(--rule);border-radius:3px;font-size:10px;color:var(--ink-2);margin:0 2px;}
</style></head><body>
<div class="thumbs" id="thumbs"></div>
<header><span class="label">Speaker Notes</span><span class="pn"><span id="cur">—</span> / <span id="tot">?</span></span></header>
<h1 id="title">—</h1>
<div class="note" id="note"><span class="empty-note">（無備註）</span></div>
<div class="footer"><span class="kbd">←</span><span class="kbd">→</span> 切換 ｜ <span class="kbd">Space</span> 下一頁 ｜ <span class="kbd">R</span> 重置 ｜ 點縮圖跳頁 ｜ <span class="kbd">Esc</span> 關閉視窗</div>
<script>
const DECK_URL = ${JSON.stringify(deckUrl)};
let nN=[],lL=[],totalSlides=0,frames={current:null,next:null};

function snthumbUrl(i){
  const u=new URL(DECK_URL);
  u.searchParams.set('_snthumb','1');
  u.hash=String(i+1);
  return u.toString();
}
function gotoInIframe(iframe,i){
  // Same-origin happy path: reach into the iframe's deck-stage and call
  // goTo. If access is blocked (Chrome file:// is null-origin and rejects
  // even sibling-file iframe.contentDocument), fall back to a src reload —
  // slower but always works.
  try{
    const w=iframe.contentWindow;
    const ds=w && w.document && w.document.querySelector('deck-stage');
    if(ds && typeof ds.goTo==='function'){ ds.goTo(i); return; }
  }catch(e){}
  // Fallback: setting src to a URL that differs only in #fragment is a
  // hash-nav, not a reload — deck-stage v2 reads the hash once on
  // connectedCallback so the iframe would stay on the previous slide.
  // Add a per-call _nav nonce so the URL differs by query param too,
  // which forces the browser to actually reload the iframe document.
  const u=new URL(snthumbUrl(i));
  u.searchParams.set('_nav',String(Date.now()));
  iframe.src=u.toString();
}
function buildThumb(i,kind,activeIdx){
  const isCurrent=kind==='current';
  if(i<0||i>=totalSlides){
    const e=document.createElement('div');
    e.className='thumb empty';
    e.dataset.kind=kind;
    e.textContent=(isCurrent?'目前':'下一張')+' ─';
    return {wrapper:e,iframe:null,index:-1};
  }
  const tb=document.createElement('div');
  tb.className='thumb';
  tb.dataset.kind=kind;
  tb.dataset.i=String(i);
  if(i===activeIdx) tb.setAttribute('data-active','');
  tb.title=lL[i]||('Slide '+(i+1));
  const meta=document.createElement('div'); meta.className='meta';
  const k=document.createElement('span'); k.className='k'; k.textContent=(isCurrent?'目前':'下一張');
  const num=document.createElement('span'); num.className='num'; num.textContent=String(i+1).padStart(2,'0');
  const lbl=document.createElement('span'); lbl.className='lbl'; lbl.textContent=lL[i]||'';
  meta.append(k,num,lbl);
  const ifr=document.createElement('iframe');
  ifr.src=snthumbUrl(i);
  ifr.setAttribute('aria-hidden','true');
  ifr.setAttribute('tabindex','-1');
  ifr.dataset.i=String(i);
  tb.append(ifr,meta);
  tb.addEventListener('click',()=>{ if(window.opener && !window.opener.closed){ window.opener.postMessage({presenterGoto:i},'*'); } });
  return {wrapper:tb,iframe:ifr,index:i};
}
function updateSlot(slot,kind,idx,activeIdx){
  const cur=frames[slot];
  const inRange=idx>=0 && idx<totalSlides;
  const wasIframe=!!(cur && cur.iframe);
  // Empty<->populated transition: rebuild this slot.
  if(!cur || inRange!==wasIframe){
    const fresh=buildThumb(idx,kind,activeIdx);
    if(cur) cur.wrapper.replaceWith(fresh.wrapper);
    else document.getElementById('thumbs').appendChild(fresh.wrapper);
    frames[slot]=fresh;
    return;
  }
  if(!inRange) return; // both empty, nothing to do
  // Stays-iframe: update meta, retarget if slide index changed, refresh
  // active highlight + click handler.
  cur.wrapper.dataset.i=String(idx);
  cur.wrapper.title=lL[idx]||('Slide '+(idx+1));
  if(idx===activeIdx) cur.wrapper.setAttribute('data-active','');
  else cur.wrapper.removeAttribute('data-active');
  const num=cur.wrapper.querySelector('.meta .num');
  const lbl=cur.wrapper.querySelector('.meta .lbl');
  if(num) num.textContent=String(idx+1).padStart(2,'0');
  if(lbl) lbl.textContent=lL[idx]||'';
  if(parseInt(cur.iframe.dataset.i,10)!==idx){
    cur.iframe.dataset.i=String(idx);
    gotoInIframe(cur.iframe,idx);
  }
  cur.index=idx;
  cur.wrapper.onclick=()=>{ if(window.opener && !window.opener.closed){ window.opener.postMessage({presenterGoto:idx},'*'); } };
}
function renderThumbs(i){
  if(!frames.current && !frames.next){
    // First mount — clear and add both slots.
    const strip=document.getElementById('thumbs');
    strip.replaceChildren();
    updateSlot('current','current',i,i);
    updateSlot('next','next',i+1,i);
    return;
  }
  updateSlot('current','current',i,i);
  updateSlot('next','next',i+1,i);
}
window.addEventListener('message',(e)=>{
  const d=e.data;if(!d)return;
  if(d.init){
    nN=d.notes||[];
    lL=d.labels||[];
    totalSlides=lL.length;
    document.getElementById('tot').textContent=totalSlides;
    render(d.current||0);
  }
  else if(typeof d.slideIndexChanged==='number'){render(d.slideIndexChanged);}
});
function render(i){
  if(i<0||i>=lL.length)return;
  document.getElementById('cur').textContent=i+1;
  document.getElementById('title').textContent=lL[i]||('Slide '+(i+1));
  const n=nN[i],el=document.getElementById('note');
  if(n&&String(n).trim()){el.textContent=n;}else{el.innerHTML='<span class="empty-note">（這張無備註）</span>';}
  renderThumbs(i);
}
window.addEventListener('keydown',(e)=>{if(e.key==='Escape'){window.close();return;}const k=e.key;if(['ArrowLeft','ArrowRight','PageDown','PageUp',' ','r','R','Home','End'].includes(k)){if(window.opener&&!window.opener.closed){window.opener.postMessage({presenterKey:k},'*');}e.preventDefault();}});
<\/script></body></html>`;
  }

  function openPresenter() {
    if (p && !p.closed) { p.focus(); return; }
    p = window.open('', 'deck-presenter', 'width=960,height=1000');
    if (!p) { alert('Presenter window blocked — please allow popups for this page and press P again.'); return; }
    p.document.open();
    p.document.write(presenterDoc(document.URL));
    p.document.close();
    setTimeout(() => {
      const s = stage();
      if (p && !p.closed) p.postMessage({ init: true, notes, labels, current: s ? s.index : 0 }, '*');
    }, 80);
  }

  function init() {
    load();
    const s = stage();
    if (s) {
      s.addEventListener('slidechange', (e) => {
        if (p && !p.closed) p.postMessage({ slideIndexChanged: e.detail.index }, '*');
      });
    }
  }

  window.addEventListener('message', (e) => {
    if (!e.data) return;
    const s = stage();
    if (!s) return;
    if (typeof e.data.presenterGoto === 'number') { s.goTo(e.data.presenterGoto); return; }
    if (!e.data.presenterKey) return;
    const k = e.data.presenterKey;
    if (k === 'ArrowRight' || k === ' ' || k === 'PageDown') s.next();
    else if (k === 'ArrowLeft' || k === 'PageUp') s.prev();
    else if (k === 'Home') s.goTo(0);
    else if (k === 'End') s.goTo(s.length - 1);
    else if (k === 'r' || k === 'R') s.reset();
  });

  window.addEventListener('keydown', (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (e.key === 'p' || e.key === 'P') { e.preventDefault(); openPresenter(); }
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
