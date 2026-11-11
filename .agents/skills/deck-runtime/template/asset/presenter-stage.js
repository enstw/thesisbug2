/* deck-stage-presenter v9 — press P to spawn a child window: the current
   slide top left, the previous and next slides below it, and the speaker
   notes in the right half (a two-column console after the Slides one in the
   Claude app), with an elapsed-time clock, a 編輯 switch for the notes and a
   「下一張：」 line, plus a grid of all slides (O) to jump to a far one. Built
   on the deck-stage v2 _snthumb URL contract. On an extended desktop, P
   opens the console on the laptop and the next P sends the deck fullscreen
   to the projector.

   Each slide picture is an <iframe> loading the deck with `?_snthumb=1#<N>`:
     - `?_snthumb=...` is detected by deck-stage v2 (line ~566) and sets
       the `no-rail` attribute, so the iframe shows a clean stage with no
       editor rail and no scale offset.
     - `#<N>` (1-indexed) is parsed by `_restoreIndex` so the iframe lands
       on the requested slide.
   Iframes are loaded once and then retargeted: slide changes call
   `deckStage.goTo(N)` cross-frame (same-origin happy path), with an
   `iframe.src = ...` reload fallback for browsers that block file:// →
   file:// frame access (notably Chrome's null-origin file:// policy).

   The 編輯 switch edits a copy of the notes kept in this browser's
   localStorage only. The notes' source is the unit's speaker-notes.md,
   whose citations ./fw deck-notes checks, so the console never writes the
   deck; an edit is shown only while the deck's own note for that slide is
   unchanged, so a rebuilt deck is never covered by a stale edit. */
(() => {
  let p = null, notes = [], labels = [];
  let lastBeat = [0, 0]; // from deck-motion's deckbeat events; 0 beats = plain slide
  let clock = null; // the console's timer, kept here so a reopened console keeps counting
  let projector = null; // the screen the next P sends the deck to, once the console sits on the laptop
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
body{display:flex;flex-direction:column;}
button{font:inherit;}
.place{flex:none;margin:10px 16px 0;padding:10px 14px;border:1px solid var(--accent);border-radius:4px;background:var(--paper-2);font-size:15px;color:var(--ink);}
.sn-main{flex:1 1 0;min-height:0;display:flex;flex-direction:column;}
.sn-left{flex:none;min-width:0;min-height:0;display:flex;flex-direction:column;gap:12px;padding:12px 16px;box-sizing:border-box;}
.sn-right{flex:1 1 0;min-width:0;min-height:0;display:flex;flex-direction:column;}
/* Wide window: slides on the left 58%, notes on the right. Narrow: notes only. */
@media (min-width:640px){.sn-main{flex-direction:row;}.sn-left{flex:0 0 58%;padding:12px 16px 16px;overflow-y:auto;border-right:1px solid var(--rule);}}
.sn-bar{flex:none;display:flex;align-items:center;flex-wrap:wrap;gap:12px;font-size:13px;color:var(--ink-3);}
.sn-clock{font-family:var(--mono);font-size:28px;line-height:1;color:var(--ink);font-variant-numeric:tabular-nums;margin-right:4px;}
.sn-clock.paused{color:var(--ink-3);}
.sn-group{display:inline-flex;align-items:center;gap:8px;}
.sn-pos{margin-left:auto;}
.pn{font-family:var(--mono);font-size:13px;color:var(--ink-3);font-variant-numeric:tabular-nums;}
.pill{font-family:var(--mono);font-size:11px;letter-spacing:0.04em;padding:3px 8px;border:1px solid var(--rule);border-radius:3px;background:var(--paper);color:var(--ink-2);cursor:pointer;}
.pill:hover{border-color:var(--ink-3);}
.navbtn{width:28px;height:28px;padding:0;border:1px solid var(--rule);border-radius:3px;background:var(--paper);color:var(--ink-2);font-size:16px;line-height:1;cursor:pointer;}
.navbtn:hover{border-color:var(--ink-3);}
.navbtn:disabled{opacity:0.35;cursor:default;border-color:var(--rule);}
.slot{position:relative;overflow:hidden;aspect-ratio:16/9;border:1px solid var(--rule);border-radius:4px;background:#000;}
.slot iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:#000;pointer-events:none;}
/* The current slide never pushes the previous/next row out of the window. */
.sn-cur{flex:none;width:100%;max-width:calc((100vh - 120px) * 16 / 9);border-color:var(--accent);box-shadow:0 0 0 1px var(--accent);}
.sn-navrow{flex:none;display:flex;gap:12px;}
.sn-navcol{flex:1 1 0;min-width:0;display:flex;flex-direction:column;gap:4px;}
/* An empty end keeps its place, so the row does not jump on the first and last slide. */
.sn-navcol.empty{visibility:hidden;}
.lbl{font-size:11px;letter-spacing:0.02em;color:var(--ink-3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.lbl .num{font-family:var(--mono);font-variant-numeric:tabular-nums;}
.thumb{cursor:pointer;border-radius:4px;}
.thumb:hover .slot{border-color:var(--ink-3);}
/* After the rules it overrides, so it wins at equal specificity. */
@media (max-width:639.98px){.sn-cur,.sn-navrow{display:none;}}
.sn-head{flex:none;height:48px;padding:0 8px 0 16px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--rule);}
.label{font-family:var(--mono);font-size:12px;letter-spacing:0.10em;color:var(--accent);text-transform:uppercase;white-space:nowrap;}
.sn-title{flex:1 1 0;min-width:0;font-size:13px;color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.switch{display:inline-flex;align-items:center;gap:8px;height:36px;padding:0 8px;border:0;border-radius:6px;background:transparent;color:var(--ink-3);font-size:13px;cursor:pointer;white-space:nowrap;}
.switch:hover{color:var(--ink);}
.switch>i{position:relative;width:30px;height:17px;border-radius:999px;background:var(--rule);transition:background 120ms;}
.switch>i::after{content:'';position:absolute;top:2px;left:2px;width:13px;height:13px;border-radius:50%;background:var(--paper);transition:transform 120ms;}
.switch[aria-checked="true"]{color:var(--ink);}
.switch[aria-checked="true"]>i{background:var(--accent);}
.switch[aria-checked="true"]>i::after{transform:translateX(13px);}
.sn-notes{flex:1 1 0;min-height:0;overflow-y:auto;padding:12px 16px;font-family:var(--serif);font-size:clamp(16px,1.6vw,22px);line-height:1.6;color:var(--ink-2);white-space:pre-wrap;}
.sn-notes:focus{outline:none;}
textarea.sn-notes{display:block;width:100%;box-sizing:border-box;margin:0;border:0;resize:none;background:var(--paper-2);color:var(--ink);caret-color:var(--accent);}
.sn-notes[hidden]{display:none;}
.sn-next{flex:none;border-top:1px solid var(--rule);padding:8px 16px;font-size:clamp(12px,1.5vw,16px);color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.dim{color:var(--ink-3);}
.footer{flex:none;border-top:1px solid var(--rule);padding:6px 16px;font-family:var(--mono);font-size:11px;color:var(--ink-3);line-height:1.6;letter-spacing:0.02em;}
.kbd{display:inline-block;padding:1px 6px;background:var(--paper-2);border:1px solid var(--rule);border-radius:3px;font-size:10px;color:var(--ink-2);margin:0 2px;}
#grid{position:fixed;inset:0;z-index:10;background:var(--paper);display:flex;flex-direction:column;gap:12px;padding:14px 20px 18px;box-sizing:border-box;}
#grid[hidden]{display:none;}
.ghead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;border-bottom:1px solid var(--rule);padding-bottom:10px;}
#gridList{flex:1;min-height:0;overflow-y:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px 14px;align-content:start;padding:6px;}
.tile{cursor:pointer;display:flex;flex-direction:column;gap:5px;min-width:0;}
.tile .frame{position:relative;aspect-ratio:16/9;border:1px solid var(--rule);border-radius:3px;background:#000;overflow:hidden;}
.tile iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:#000;pointer-events:none;}
.tile:hover .frame{border-color:var(--ink-3);}
.tile[data-current] .frame{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent);}
.tile[data-sel] .frame{outline:3px solid var(--ink);outline-offset:3px;}
.tile .cap{display:flex;gap:8px;align-items:baseline;min-width:0;}
.tile .num{font-family:var(--mono);font-size:12px;color:var(--ink-3);font-variant-numeric:tabular-nums;}
.tile[data-current] .num{color:var(--accent);}
.tile .lbl{font-size:13px;color:var(--ink-2);}
</style></head><body>
<div class="place" id="place" hidden>下一步：按 <span class="kbd">P</span>，投影片會全螢幕到投影幕。若投影片先跳到前面，再按一次 <span class="kbd">P</span>。</div>
<div class="sn-main">
<div class="sn-left">
<div class="sn-bar">
<span class="sn-clock" id="clock" title="經過時間">0:00</span>
<span class="sn-group"><button class="pill" id="pause" type="button">暫停</button><button class="pill" id="reset" type="button">重置</button></span>
<button class="pill" id="gridBtn" type="button">全部投影片 O</button>
<span class="sn-group sn-pos"><span class="pn"><span id="cur">—</span> / <span id="tot">?</span><span id="beat"></span></span><button class="navbtn" id="prevBtn" type="button" aria-label="上一張" title="上一張">‹</button><button class="navbtn" id="nextBtn" type="button" aria-label="下一張" title="下一張">›</button></span>
</div>
<div class="slot sn-cur" id="curSlot"></div>
<div class="sn-navrow">
<div class="sn-navcol empty" id="prevCol"><span class="lbl" id="prevLbl"></span><div class="thumb" id="prevThumb" title="跳到上一張"><div class="slot" id="prevSlot"></div></div></div>
<div class="sn-navcol empty" id="nextCol"><span class="lbl" id="nextLbl"></span><div class="thumb" id="nextThumb" title="跳到下一張"><div class="slot" id="nextSlot"></div></div></div>
</div>
</div>
<div class="sn-right">
<div class="sn-head"><span class="label">Speaker Notes</span><span class="sn-title" id="title">—</span><button class="pill" id="revert" type="button" hidden title="丟掉這張在這台瀏覽器的修改，回到簡報的備註">已修改 · 還原</button><button class="switch" id="edit" type="button" role="switch" aria-checked="false" title="在這裡改備註（只存在這台瀏覽器，不會改 speaker-notes.md）">編輯<i aria-hidden="true"></i></button></div>
<div class="sn-notes" id="note" tabindex="0" role="region" aria-label="講者備註"></div>
<textarea class="sn-notes" id="noteEdit" hidden aria-label="編輯講者備註" placeholder="講者備註，不會出現在投影片上。"></textarea>
<div class="sn-next" id="next"></div>
</div>
</div>
<div class="footer"><span class="kbd">←</span><span class="kbd">→</span> 切換 ｜ <span class="kbd">Space</span> 下一頁 ｜ <span class="kbd">+</span><span class="kbd">−</span> 調整投影片字級 ｜ <span class="kbd">C</span> 換主題 <span class="kbd">G</span> 隨機配色（Shift 反向）｜ <span class="kbd">M</span> 活潑模式 ｜ <span class="kbd">R</span> 重置 ｜ 點縮圖跳頁 ｜ <span class="kbd">O</span> 全部投影片 ｜ <span class="kbd">Esc</span> 關閉視窗（編輯中：結束編輯）</div>
<div id="grid" hidden><div class="ghead"><span class="label">全部投影片</span><span class="pn">點一張跳過去 ｜ <span class="kbd">←</span><span class="kbd">→</span><span class="kbd">↑</span><span class="kbd">↓</span> 選 ｜ <span class="kbd">Enter</span> 跳頁 ｜ <span class="kbd">Esc</span> 返回</span></div><div id="gridList"></div></div>
<script>
const DECK_URL = ${JSON.stringify(deckUrl)};
let nN=[],lL=[],totalSlides=0,curIdx=0,beat=[0,0];
let grid=null,gridSel=0,gridCur=0;
const $=(id)=>document.getElementById(id);

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
function toDeck(m){ if(window.opener && !window.opener.closed){ window.opener.postMessage(m,'*'); } }
function title(i){ return lL[i]||('Slide '+(i+1)); }
function num(i){ return String(i+1).padStart(2,'0'); }

// Slide pictures: each slot gets one iframe on first use and is retargeted
// after, so changing slide does not reload three decks.
function showIn(slot,i){
  let f=slot.querySelector('iframe');
  if(!f){
    f=document.createElement('iframe');
    f.src=snthumbUrl(i);
    f.setAttribute('aria-hidden','true');
    f.setAttribute('tabindex','-1');
    f.dataset.i=String(i);
    slot.appendChild(f);
    return;
  }
  if(parseInt(f.dataset.i,10)!==i){ f.dataset.i=String(i); gotoInIframe(f,i); }
}
function navCol(kind,i){
  const ok=i>=0 && i<totalSlides;
  $(kind+'Col').classList.toggle('empty',!ok);
  const l=$(kind+'Lbl');
  l.replaceChildren();
  if(!ok) return;
  const n=document.createElement('span'); n.className='num'; n.textContent=num(i);
  const t=document.createElement('span'); t.className='dim'; t.textContent=' · '+(lL[i]||'');
  l.append((kind==='prev'?'上一張 ':'下一張 '),n,t);
  $(kind+'Thumb').title=(kind==='prev'?'跳到上一張：':'跳到下一張：')+title(i);
  showIn($(kind+'Slot'),i);
}
$('prevThumb').addEventListener('click',()=>{ if(curIdx>0) toDeck({presenterGoto:curIdx-1}); });
$('nextThumb').addEventListener('click',()=>{ if(curIdx<totalSlides-1) toDeck({presenterGoto:curIdx+1}); });
// The bar's arrows step like the keys, so the deck's beats still play one at a time.
$('prevBtn').addEventListener('click',()=>toDeck({presenterKey:'ArrowLeft'}));
$('nextBtn').addEventListener('click',()=>toDeck({presenterKey:'ArrowRight'}));
// A clicked button must not keep focus, or the next Space would press it again.
document.addEventListener('mousedown',(e)=>{ if(e.target.closest && e.target.closest('button')) e.preventDefault(); });

// Elapsed-time clock. The deck window keeps its state, so closing and
// reopening the console does not restart the count.
let clock={running:true,start:Date.now(),accum:0};
function elapsed(){ return clock.accum+(clock.running?Date.now()-clock.start:0); }
function fmt(ms){ const t=Math.max(0,Math.floor(ms/1000)),m=Math.floor(t/60); return m+':'+String(t%60).padStart(2,'0'); }
function tick(){
  const c=$('clock');
  c.textContent=fmt(elapsed());
  c.classList.toggle('paused',!clock.running);
  c.title=clock.running?'經過時間':'經過時間（暫停中）';
  $('pause').textContent=clock.running?'暫停':'繼續';
}
function setClock(c){ clock=c; tick(); toDeck({presenterClock:clock}); }
$('pause').addEventListener('click',()=>{
  const now=Date.now();
  setClock(clock.running?{running:false,start:clock.start,accum:clock.accum+(now-clock.start)}:{running:true,start:now,accum:clock.accum});
});
$('reset').addEventListener('click',()=>setClock({running:clock.running,start:Date.now(),accum:0}));
setInterval(tick,500);
tick();

// Notes and the 編輯 switch. An edit is stored with the note it replaced and
// shown only while the deck still carries that note.
const STORE='deck-presenter-notes:'+DECK_URL.split(/[?#]/)[0];
let edits={},editing=false;
try{ edits=JSON.parse(localStorage.getItem(STORE)||'{}')||{}; }catch(e){ edits={}; }
function saveEdits(){
  let ok=true;
  try{ localStorage.setItem(STORE,JSON.stringify(edits)); }catch(e){ ok=false; }
  $('edit').title=ok?'在這裡改備註（只存在這台瀏覽器，不會改 speaker-notes.md）':'這個瀏覽器不讓存：修改只留到關掉這個視窗';
}
function original(i){ return String(nN[i]==null?'':nN[i]); }
function edited(i){ const e=edits[i]; return e && e.orig===original(i) ? e.text : null; }
function noteText(i){ const t=edited(i); return t===null?original(i):t; }
function renderNote(){
  const el=$('note'),t=noteText(curIdx);
  if(t.trim()) el.textContent=t;
  else el.innerHTML='<span class="dim">（這張無備註）</span>';
  el.scrollTop=0;
  $('revert').hidden=edited(curIdx)===null;
}
function setEditing(on){
  editing=on;
  $('edit').setAttribute('aria-checked',String(on));
  $('note').hidden=on;
  $('noteEdit').hidden=!on;
  if(on){
    const ta=$('noteEdit');
    ta.value=noteText(curIdx);
    ta.focus();
    ta.setSelectionRange(ta.value.length,ta.value.length);
  }else{
    $('noteEdit').blur();
    renderNote();
  }
}
$('edit').addEventListener('click',()=>setEditing(!editing));
$('noteEdit').addEventListener('input',(e)=>{
  const v=e.target.value;
  if(v===original(curIdx)) delete edits[curIdx];
  else edits[curIdx]={orig:original(curIdx),text:v};
  saveEdits();
  $('revert').hidden=edited(curIdx)===null;
});
$('revert').addEventListener('click',()=>{
  delete edits[curIdx];
  saveEdits();
  if(editing) $('noteEdit').value=original(curIdx);
  renderNote();
});

function renderNext(){
  const el=$('next'),b=beat[0],n=beat[1],more=n>0 && b<n,last=curIdx>=totalSlides-1;
  $('nextBtn').disabled=last && !more;
  el.replaceChildren();
  const d=document.createElement('span'); d.className='dim';
  if(more){ d.textContent='下一步：'; el.append(d,'第 '+(b+1)+' / '+n+' 拍'); }
  else if(last){ d.textContent='最後一張'; el.append(d); }
  else { d.textContent='下一張：'; el.append(d,title(curIdx+1)); }
}

// Slide grid (O): every slide as a thumbnail, so a far slide is one click
// away instead of a page at a time. Built on first open and kept; the
// iframes load lazily, so a long deck only loads the rows in view.
function tiles(){ return document.querySelectorAll('#gridList .tile'); }
function buildGrid(){
  grid=$('grid');
  const list=$('gridList');
  for(let i=0;i<totalSlides;i++){
    const t=document.createElement('div');
    t.className='tile';
    t.title=title(i);
    const f=document.createElement('div'); f.className='frame';
    const ifr=document.createElement('iframe');
    ifr.loading='lazy';
    ifr.src=snthumbUrl(i);
    ifr.setAttribute('aria-hidden','true');
    ifr.setAttribute('tabindex','-1');
    f.appendChild(ifr);
    const cap=document.createElement('div'); cap.className='cap';
    const n=document.createElement('span'); n.className='num'; n.textContent=num(i);
    const lbl=document.createElement('span'); lbl.className='lbl'; lbl.textContent=lL[i]||'';
    cap.append(n,lbl);
    t.append(f,cap);
    t.addEventListener('click',()=>jumpTo(i));
    list.appendChild(t);
  }
}
function markGrid(){ tiles().forEach((t,i)=>{ t.toggleAttribute('data-current',i===gridCur); t.toggleAttribute('data-sel',i===gridSel); }); }
function gridOpen(){ return !!grid && !grid.hidden; }
function openGrid(){
  if(!totalSlides) return;
  if(editing) setEditing(false);
  if(!grid) buildGrid();
  grid.hidden=false;
  gridSel=gridCur;
  markGrid();
  tiles()[gridSel].scrollIntoView({block:'center'});
}
function closeGrid(){ if(grid) grid.hidden=true; }
function jumpTo(i){ toDeck({presenterGoto:i}); closeGrid(); }
function gridKey(k){
  const cols=getComputedStyle($('gridList')).gridTemplateColumns.split(' ').length;
  let n=gridSel;
  if(k==='Escape'||k==='o'||k==='O'){ closeGrid(); return; }
  if(k==='Enter'||k===' '){ jumpTo(gridSel); return; }
  if(k==='ArrowRight') n++;
  else if(k==='ArrowLeft') n--;
  else if(k==='ArrowDown') n+=cols;
  else if(k==='ArrowUp') n-=cols;
  else if(k==='Home') n=0;
  else if(k==='End') n=totalSlides-1;
  else return;
  gridSel=Math.max(0,Math.min(totalSlides-1,n));
  markGrid();
  tiles()[gridSel].scrollIntoView({block:'nearest'});
}
$('gridBtn').addEventListener('click',()=>{ gridOpen()?closeGrid():openGrid(); });

window.addEventListener('message',(e)=>{
  const d=e.data;if(!d)return;
  if(d.init){
    nN=d.notes||[];
    lL=d.labels||[];
    totalSlides=lL.length;
    $('tot').textContent=totalSlides;
    if(d.clock) clock=d.clock; else toDeck({presenterClock:clock});
    tick();
    if(Array.isArray(d.deckBeat)) beat=d.deckBeat;
    render(d.current||0);
  }
  else if(typeof d.slideIndexChanged==='number'){render(d.slideIndexChanged);}
  if(Array.isArray(d.deckBeat)){beat=d.deckBeat;$('beat').textContent=beat[1]?' · 第 '+beat[0]+' / '+beat[1]+' 拍':'';renderNext();}
  if(typeof d.placeHint==='boolean'){$('place').hidden=!d.placeHint;}
});
function render(i){
  if(i<0||i>=totalSlides)return;
  curIdx=i;
  gridCur=i;
  if(grid) markGrid();
  $('cur').textContent=i+1;
  $('title').textContent=num(i)+'  '+title(i);
  $('prevBtn').disabled=i<=0;
  if(editing) $('noteEdit').value=noteText(i);
  renderNote();
  showIn($('curSlot'),i);
  navCol('prev',i-1);
  navCol('next',i+1);
  renderNext();
  document.title='講者備註 · '+(i+1)+' / '+totalSlides;
}
window.addEventListener('keydown',(e)=>{if(e.metaKey||e.ctrlKey||e.altKey)return;if(editing){if(e.key==='Escape'&&!e.isComposing){setEditing(false);e.preventDefault();}return;}if(gridOpen()){gridKey(e.key);e.preventDefault();return;}if(e.key==='o'||e.key==='O'){openGrid();e.preventDefault();return;}if(e.key==='Escape'){window.close();return;}const k=e.key;if(k==='p'||k==='P'){if(!document.getElementById('place').hidden&&window.opener&&!window.opener.closed){window.opener.focus();window.opener.postMessage({presenterPlace:true},'*');}e.preventDefault();return;}const direction=(k==='+'||k==='=')?1:k==='-'?-1:0;if(direction){if(window.opener&&!window.opener.closed){window.opener.postMessage({deckFontDirection:direction},'*');}e.preventDefault();return;}if(k==='m'||k==='M'){if(window.opener&&!window.opener.closed){window.opener.postMessage({deckMotionKey:true},'*');}e.preventDefault();return;}if(k==='a'||k==='A'){if(window.opener&&!window.opener.closed){window.opener.postMessage({deckAutoKey:true},'*');}e.preventDefault();return;}if(!e.ctrlKey&&!e.metaKey&&!e.altKey&&/^[cg]$/i.test(k)){if(window.opener&&!window.opener.closed){window.opener.postMessage({deckThemeKey:e.shiftKey?k.toUpperCase():k.toLowerCase()},'*');}e.preventDefault();return;}if(['ArrowLeft','ArrowRight','PageDown','PageUp',' ','r','R','Home','End'].includes(k)){if(window.opener&&!window.opener.closed){window.opener.postMessage({presenterKey:k},'*');}e.preventDefault();}});
<\/script></body></html>`;
  }

  /* Two screens: the deck goes fullscreen on the external screen (the
     projector) and the console opens on the built-in one, so nothing is
     dragged across by hand. Uses the Window Management API (Chromium only).
     A desktop without a built-in
     screen keeps the console on the screen the deck was on.

     One key press grants one activation, and requestFullscreen and
     window.open each spend it: on a real two-screen Mac (Chrome, EPSON
     projector, permission granted) either order left the second step
     refused. So two screens take two presses, each doing one thing: the
     first opens the console on the laptop, the second, with the console
     open, sends the deck to the projector. A live test on 2026-10-08 showed
     Brave refuses or misplaces that second step (see docs/DESIGN.md), so
     this is a stopgap until window placement moves to an extension. The
     second press must land on the deck, since a key press in the console
     cannot make the deck fullscreen (Chrome refuses it, checked headless).
     If the console took focus, its P brings the deck forward and the deck
     asks for P once more.

     Chrome never stores the permission for a file:// page: the query says
     "prompt" and every getScreenDetails() call asks again. So the deck asks
     once per page load and keeps the live ScreenDetails it gets. If Allow is
     clicked while the key press still counts as user activation, that same
     press goes on to open the console; otherwise the next P does. */
  let details = null, asked = false;

  async function screens() {
    if (!window.getScreenDetails || !window.screen.isExtended) return null;
    if (!details && !asked) {
      asked = true;
      try { details = await window.getScreenDetails(); }
      catch (e) { console.warn('[presenter] two-screen placement skipped:', e); }
    }
    if (!details) return null;
    const consoleScreen = details.screens.find((s) => s.isInternal) || details.currentScreen;
    const projector = details.screens.find((s) => s !== consoleScreen);
    return projector ? { consoleScreen, projector } : null;
  }

  function fullscreenOn(projector) {
    return document.documentElement.requestFullscreen({ screen: projector })
      .then(() => true, (e) => { console.warn('[presenter] projector fullscreen failed:', e); return false; });
  }

  // An alert would take the deck out of fullscreen, so this says it on the slide.
  function notice(text) {
    const n = document.createElement('div');
    n.textContent = text;
    n.style.cssText = 'position:fixed;left:50%;bottom:6%;transform:translateX(-50%);z-index:2147483647;' +
      'padding:12px 20px;border-radius:6px;background:rgba(0,0,0,0.82);color:#fff;font:16px/1.4 system-ui,sans-serif;';
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 4000);
  }

  const placeHint = () => !!projector && !document.fullscreenElement;

  async function openPresenter() {
    if (p && !p.closed) {
      if (placeHint()) {
        if (!await fullscreenOn(projector)) notice('投影片沒能全螢幕到投影幕，請再按一次 P。');
        return;
      }
      p.focus();
      return;
    }
    const place = await screens();
    if (navigator.userActivation && !navigator.userActivation.isActive) {
      // The permission prompt outlasted this press; the next P opens the console.
      notice(place ? '已允許。再按一次 P，講者視窗會開在筆電螢幕。' : '再按一次 P，開講者視窗。');
      return;
    }
    projector = place && place.projector;
    const c = place && place.consoleScreen;
    // Landscape by default: the console lays the slides and the notes side by side.
    const features = c
      ? `left=${c.availLeft},top=${c.availTop},width=${c.availWidth},height=${c.availHeight}`
      : 'width=1280,height=800';
    p = window.open('', 'deck-presenter', features);
    if (!p) {
      projector = null;
      if (document.fullscreenElement) notice('講者視窗被擋：請允許此頁的彈出式視窗，再按一次 P。');
      else alert('Presenter window blocked — please allow popups for this page and press P again.');
      return;
    }
    p.document.open();
    p.document.write(presenterDoc(document.URL));
    p.document.close();
    setTimeout(() => {
      const s = stage();
      if (p && !p.closed) p.postMessage({ init: true, notes, labels, current: s ? s.index : 0, placeHint: placeHint(), deckBeat: lastBeat, clock }, '*');
    }, 80);
    // Keep the next P on the deck if the browser lets it; the console's P covers it if not.
    if (projector) window.focus();
  }

  function init() {
    load();
    const s = stage();
    if (s) {
      s.addEventListener('slidechange', (e) => {
        if (p && !p.closed) p.postMessage({ slideIndexChanged: e.detail.index }, '*');
      });
      // deck-motion.js (optional) reports the reveal step; the console shows 第 n/m 拍.
      document.addEventListener('deckbeat', (e) => {
        lastBeat = [e.detail.beat, e.detail.beats];
        if (p && !p.closed) p.postMessage({ deckBeat: lastBeat }, '*');
      });
    }
  }

  // The console's banner tracks whether the deck still has to go to the projector.
  document.addEventListener('fullscreenchange', () => {
    if (p && !p.closed) p.postMessage({ placeHint: placeHint() }, '*');
  });

  window.addEventListener('message', (e) => {
    if (!e.data) return;
    if (e.data.presenterClock && typeof e.data.presenterClock === 'object') { clock = e.data.presenterClock; return; }
    const s = stage();
    if (!s) return;
    if (e.data.presenterPlace) { if (placeHint()) notice('再按一次 P，投影片會全螢幕到投影幕。'); return; }
    if (typeof e.data.presenterGoto === 'number') { s.goTo(e.data.presenterGoto); return; }
    if (e.data.deckFontDirection === 1 || e.data.deckFontDirection === -1) return;
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
