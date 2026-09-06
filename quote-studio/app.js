(() => {
  'use strict';

  // Curated verbatim from the public quote collections in ../generate.py.
  const QUOTES = [
    { text: 'The impediment to action advances action. What stands in the way becomes the way.', author: 'Marcus Aurelius' },
    { text: 'We suffer more in imagination than in reality.', author: 'Seneca' },
    { text: 'The stock market is a device for transferring money from the impatient to the patient.', author: 'Warren Buffett' },
    { text: 'In the short run, the market is a voting machine. In the long run, it is a weighing machine.', author: 'Benjamin Graham' },
    { text: 'Price is what you pay. Value is what you get.', author: 'Warren Buffett' },
    { text: 'Know what you own, and know why you own it.', author: 'Peter Lynch' },
    { text: 'An investment in knowledge pays the best interest.', author: 'Benjamin Franklin' },
    { text: 'Markets can remain irrational longer than you can remain solvent.', author: 'John Maynard Keynes' },
    { text: 'The cave you fear to enter holds the treasure you seek.', author: 'Joseph Campbell' },
    { text: 'The curious paradox is that when I accept myself just as I am, then I can change.', author: 'Carl Rogers' },
    { text: 'Knowing yourself is the beginning of all wisdom.', author: 'Aristotle' },
    { text: 'Not all those who wander are lost.', author: 'J.R.R. Tolkien' },
    { text: 'You cannot swim for new horizons until you have courage to lose sight of the shore.', author: 'William Faulkner' },
    { text: 'Energy and persistence conquer all things.', author: 'Benjamin Franklin' }
  ];
  const SIZES = { x: [1600, 900], story: [1080, 1920] };
  const state = { style: new URLSearchParams(location.search).get('style') === 'modern' ? 'modern' : 'editorial', format: 'x', quote: 0, authenticated: false, requestId: null, postLocked: false };
  const fontsReady = document.fonts ? Promise.all([
    document.fonts.load('italic 100px "Cormorant Garamond"'),
    document.fonts.load('500 30px Inter'),
    document.fonts.load('700 100px Inter')
  ]).then(() => document.fonts.ready) : Promise.resolve();
  const $ = (id) => document.getElementById(id);
  const canvas = $('art');
  const ctx = canvas.getContext('2d', { alpha: false });
  const picker = $('quote-picker');
  const status = $('status');
  ['download', 'share', 'review'].forEach(id => { $(id).disabled = true; });

  QUOTES.forEach((q, i) => picker.add(new Option(`${q.author} — ${q.text.slice(0, 50)}${q.text.length > 50 ? '…' : ''}`, String(i))));

  function postText() { const q = QUOTES[state.quote]; return `“${q.text}”\n— ${q.author}`; }
  function setStatus(message, error = false) { status.textContent = message; status.classList.toggle('error', error); }
  function setDialogStatus(message, url = '') { const box = $('dialog-status'); box.replaceChildren(document.createTextNode(message)); if (url) { const link = document.createElement('a'); link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = ' View verified post on X.'; link.style.color = '#b59662'; box.append(link); } }
  function roundedRect(x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }
  function rule(x1, y1, x2, y2, color, width = 1) { ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke(); }
  function wrap(text, maxWidth) {
    const words = text.split(/\s+/); const lines = []; let line = '';
    for (const word of words) { const next = line ? `${line} ${word}` : word; if (ctx.measureText(next).width <= maxWidth || !line) line = next; else { lines.push(line); line = word; } }
    if (line) lines.push(line); return lines;
  }
  function fit(text, maxWidth, maxHeight, maxSize, minSize, family, weight, style, lineRatio) {
    let lo = minSize, hi = maxSize, best = minSize, lines = [];
    while (lo <= hi) { const size = Math.floor((lo + hi) / 2); ctx.font = `${style} ${weight} ${size}px ${family}`; const test = wrap(text, maxWidth); if (test.length * size * lineRatio <= maxHeight) { best = size; lines = test; lo = size + 1; } else hi = size - 1; }
    ctx.font = `${style} ${weight} ${best}px ${family}`; return { size: best, lines: wrap(text, maxWidth), lineHeight: best * lineRatio };
  }
  function fillBackground(w, h) {
    ctx.fillStyle = '#050505'; ctx.fillRect(0, 0, w, h);
    const glow = ctx.createRadialGradient(w * .22, h * .15, 0, w * .22, h * .15, Math.max(w, h) * .85);
    glow.addColorStop(0, 'rgba(181,150,98,.13)'); glow.addColorStop(.38, 'rgba(105,78,35,.035)'); glow.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = glow; ctx.fillRect(0, 0, w, h);
    const vignette = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * .08, w / 2, h / 2, Math.max(w, h) * .72); vignette.addColorStop(.45, 'rgba(0,0,0,0)'); vignette.addColorStop(1, 'rgba(0,0,0,.55)'); ctx.fillStyle = vignette; ctx.fillRect(0, 0, w, h);
  }
  function drawEditorial(q, w, h) {
    fillBackground(w, h); const story = h > w; const left = story ? 112 : 150, right = story ? 112 : 150; const safeTop = story ? 260 : 105, safeBottom = story ? 290 : 105; const contentH = h - safeTop - safeBottom;
    ctx.strokeStyle = 'rgba(181,150,98,.42)'; ctx.lineWidth = 2; ctx.strokeRect(story ? 64 : 76, story ? 150 : 58, w - (story ? 128 : 152), h - (story ? 300 : 116));
    rule(left, safeTop, left + (story ? 72 : 104), safeTop, '#b59662', 5);
    const fitted = fit(q.text, w - left - right, contentH * .67, story ? 118 : 112, story ? 55 : 48, '"Cormorant Garamond", Georgia, serif', '400', 'italic', 1.22);
    ctx.fillStyle = '#f0eef8'; ctx.textBaseline = 'top'; ctx.textAlign = 'left'; let y = safeTop + (contentH - (fitted.lines.length * fitted.lineHeight + 100)) / 2;
    for (const line of fitted.lines) { ctx.fillText(line, left, y); y += fitted.lineHeight; }
    y += story ? 58 : 38; rule(left, y + 10, left + (story ? 42 : 54), y + 10, '#b59662', 2); ctx.fillStyle = '#b59662'; ctx.font = `600 ${story ? 25 : 21}px Inter, sans-serif`; ctx.letterSpacing = `${story ? 5 : 4}px`; ctx.fillText(q.author.toUpperCase(), left + (story ? 66 : 78), y); ctx.letterSpacing = '0px';
  }
  function drawModern(q, w, h) {
    fillBackground(w, h); const story = h > w; const mx = story ? 104 : 130, top = story ? 290 : 108, bottom = story ? 310 : 108; const contentH = h - top - bottom;
    ctx.fillStyle = '#b59662'; roundedRect(mx, top, story ? 12 : 9, story ? 88 : 66, 8); ctx.fill();
    ctx.fillStyle = 'rgba(181,150,98,.08)'; roundedRect(mx + (story ? 42 : 34), top, w - mx * 2 - (story ? 42 : 34), contentH, story ? 28 : 20); ctx.fill();
    const x = mx + (story ? 88 : 82), maxW = w - x - mx - (story ? 48 : 40); const fitted = fit(q.text, maxW, contentH * .65, story ? 104 : 91, story ? 49 : 43, 'Inter, sans-serif', '700', 'normal', 1.14);
    const total = fitted.lines.length * fitted.lineHeight + (story ? 102 : 78); let y = top + (contentH - total) / 2; ctx.fillStyle = '#f0eef8'; ctx.textBaseline = 'top'; ctx.textAlign = 'left';
    fitted.lines.forEach((line, i) => { ctx.fillStyle = i === fitted.lines.length - 1 ? '#b59662' : '#f0eef8'; ctx.fillText(line, x, y); y += fitted.lineHeight; });
    y += story ? 62 : 43; ctx.fillStyle = '#a7a1aa'; ctx.font = `500 ${story ? 27 : 21}px Inter, sans-serif`; ctx.letterSpacing = `${story ? 6 : 5}px`; ctx.fillText(q.author.toUpperCase(), x, y); ctx.letterSpacing = '0px';
  }
  function render() {
    const [w, h] = SIZES[state.format]; canvas.width = w; canvas.height = h; const q = QUOTES[state.quote];
    state.style === 'editorial' ? drawEditorial(q, w, h) : drawModern(q, w, h);
    $('quote-text').textContent = `“${q.text}”`; $('quote-author').textContent = `— ${q.author}`; $('post-copy').textContent = postText();
    const count = [...postText()].length; $('char-count').textContent = `${count} / 280`; $('char-count').classList.toggle('over', count > 280); $('review').disabled = count > 280;
    $('canvas-frame').className = `canvas-frame ${state.format}`; $('safe-note').textContent = state.format === 'x' ? 'X · 1600 × 900' : 'Story · 1080 × 1920 · safe zones held';
    document.querySelectorAll('[data-style]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.style === state.style))); document.querySelectorAll('[data-format]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.format === state.format)));
  }
  function imageBlob() { return new Promise(resolve => canvas.toBlob(resolve, 'image/png')); }
  function dataUrl() { return canvas.toDataURL('image/png'); }
  function filename() { return `quote-${state.style}-${state.format === 'x' ? '1600x900' : '1080x1920'}.png`; }
  async function download() { await fontsReady; render(); const a = document.createElement('a'); a.href = dataUrl(); a.download = filename(); a.click(); setStatus(`PNG ready: ${filename()}`); }
  async function nativeShare() {
    await fontsReady; render();
    const blob = await imageBlob(); const file = new File([blob], filename(), { type: 'image/png' });
    if (!navigator.share || !navigator.canShare?.({ files: [file] })) return setStatus('Native file sharing is unavailable here. Download the PNG instead.', true);
    try { await navigator.share({ files: [file], text: postText() }); setStatus('Share sheet opened.'); } catch (e) { if (e.name !== 'AbortError') setStatus('The share sheet could not be opened.', true); }
  }
  async function copyText() { try { await navigator.clipboard.writeText(postText()); setStatus('Quote and author copied — nothing else appended.'); } catch { setStatus('Clipboard permission was denied.', true); } }
  async function checkPostAccess() {
    const auth = $('auth-panel'); auth.classList.add('hidden'); $('confirm-post').disabled = false;
    try { const r = await fetch('/api/quote-post', { credentials: 'same-origin' }); if (r.status === 401) { state.authenticated = false; auth.classList.remove('hidden'); $('confirm-post').disabled = true; return; } const info = await r.json(); if (!r.ok || info.configured === false || info.account !== 'Novairecito') { $('confirm-post').disabled = true; setDialogStatus('Posting backend is not configured for @Novairecito.'); } else if (info.authenticated !== true) { state.authenticated = false; auth.classList.remove('hidden'); $('confirm-post').disabled = true; setDialogStatus('Authenticate to enable explicit posting confirmation.'); } else { state.authenticated = true; setDialogStatus('Authenticated session detected.'); } } catch { $('confirm-post').disabled = true; setDialogStatus('Posting status unavailable. Export and copy still work.'); }
  }
  async function authenticate() {
    const pin = $('post-pin').value; if (!pin) return void setDialogStatus('Enter the portfolio PIN.'); $('authenticate').disabled = true;
    try { const r = await fetch('/api/quote-auth', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pin }) }); $('post-pin').value = ''; if (!r.ok) { state.authenticated = false; setDialogStatus('Authentication failed.'); return; } state.authenticated = true; $('auth-panel').classList.add('hidden'); $('confirm-post').disabled = false; setDialogStatus('Authenticated. Review once more, then explicitly confirm.'); } catch { setDialogStatus('Authentication service is unavailable.'); } finally { $('authenticate').disabled = false; }
  }
  async function confirmPost() {
    await fontsReady; render();
    const text = postText(); if ([...text].length > 280) return void setDialogStatus('Blocked: post text exceeds 280 characters.'); if (state.postLocked) return; if (!state.authenticated) { $('auth-panel').classList.remove('hidden'); $('confirm-post').disabled = true; setDialogStatus('Authenticate before confirming.'); return; }
    const button = $('confirm-post'); button.disabled = true; state.requestId ||= crypto.randomUUID();
    try { const r = await fetch('/api/quote-post', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, imageDataUrl: dataUrl(), confirmation: true, requestId: state.requestId }) }); const result = await r.json().catch(() => ({})); if (r.status === 401) { state.authenticated = false; $('auth-panel').classList.remove('hidden'); setDialogStatus('Session expired. Authenticate, then press confirm again. Nothing was retried automatically.'); button.disabled = true; return; } if (!r.ok) { setDialogStatus(result.error || `Posting was rejected (${r.status}).`); return; } if (result.ok !== true || !result.url) throw new Error('unverified response'); state.postLocked = true; setDialogStatus('Post verified.', result.url); setStatus('Post verified by the posting backend.'); } catch { state.postLocked = true; setDialogStatus('Could not confirm posting. Check @Novairecito before retrying. This request is locked to prevent a duplicate.'); setStatus('Posting result is ambiguous; repeat posting is locked.', true); } finally { button.disabled = state.postLocked; }
  }

  document.querySelectorAll('[data-style]').forEach(b => b.addEventListener('click', () => { state.style = b.dataset.style; history.replaceState(null, '', `?style=${state.style}`); render(); }));
  document.querySelectorAll('[data-format]').forEach(b => b.addEventListener('click', () => { state.format = b.dataset.format; render(); }));
  picker.addEventListener('change', () => { state.quote = Number(picker.value); render(); }); $('download').addEventListener('click', download); $('share').addEventListener('click', nativeShare); $('copy').addEventListener('click', copyText);
  $('review').addEventListener('click', () => { state.requestId = crypto.randomUUID(); state.postLocked = false; setDialogStatus(''); $('post-dialog').showModal(); checkPostAccess(); }); $('cancel-post').addEventListener('click', () => { $('post-pin').value = ''; $('post-dialog').close(); }); $('authenticate').addEventListener('click', authenticate); $('confirm-post').addEventListener('click', confirmPost);
  fontsReady.then(() => { render(); ['download', 'share', 'review'].forEach(id => { $(id).disabled = false; }); }).catch(() => { render(); ['download', 'share', 'review'].forEach(id => { $(id).disabled = false; }); setStatus('Local font load failed; using system fallbacks.', true); });
})();
