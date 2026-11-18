// Novaire Signal · per-box customize drawer (ported from Wizard Signal; arrow-only trigger)
(function () {
  if (window.__nvCustomize) return; window.__nvCustomize = 1;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  
  const store = {
    get(k, d) { try { const v = JSON.parse(localStorage.getItem(k) || 'null'); return v ?? d; } catch (_) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) {} },
    del(k) { try { localStorage.removeItem(k); } catch (_) {} },
  };
  const pctHtml = ch => Number.isFinite(ch) ? `<span class="${ch >= 0 ? 'positive' : 'negative'}">${ch >= 0 ? '+' : ''}${ch.toFixed(2)}%</span>` : '<span style="color:var(--dim)">—</span>';
  const money = p => !Number.isFinite(p) ? '—' : p >= 1000 ? '$' + p.toLocaleString('en-US', {maximumFractionDigits: 2}) : p >= 1 ? '$' + p.toFixed(2) : '$' + p.toFixed(4);
  const num = p => !Number.isFinite(p) ? '—' : p.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const flagOf = cc => /^[A-Z]{2}$/i.test(cc || '') ? String.fromCodePoint(...[...cc.toUpperCase()].map(c => 0x1F1A5 + c.charCodeAt(0))) : '🏳️';
  const getJSON = (u, o) => fetch(u, o).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
  const norm = s => String(s || '').toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');

  // Section identity (cards without an id get a stable key from their title)
  const cardKey = card => card.id || (card.querySelector('.market-futures') ? 'wall-street-card' : card.querySelector('.commodities-grid') ? 'commodities-card' : card.querySelector('.crypto-grid') ? 'crypto-card' : card.querySelector('.fx-row') ? 'fx-card' : 'card-' + norm(card.querySelector('.card-title')?.textContent).slice(0, 24));
  const USED_KEY = 'nv_cz_used_v1';
  const usedSet = () => new Set(store.get(USED_KEY, []));
  const markUsed = () => {};
  const HIDE_KEY = 'nv_cz_hidden_v1';
  const hiddenSet = () => new Set(store.get(HIDE_KEY, []));
  // ── Frequency: how often each section appears (anchor = day it was set, so it shows that day) ──
  const FREQ_KEY = 'nv_cz_freq_v1', PEEK_KEY = 'nv_cz_peek_v1';
  const FREQS = [['daily', 'Daily'], ['weekly', 'Weekly'], ['biweekly', 'Biweekly'], ['monthly', 'Monthly'], ['annual', 'Annually']];
  const dayStr = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const parseDay = s => { const [y, m, d] = String(s).split('-').map(Number); return new Date(y, m - 1, d); };
  const todayStr = () => dayStr(new Date());
  const dim = (y, m) => new Date(y, m + 1, 0).getDate();
  const freqOf = key => { const v = store.get(FREQ_KEY, {})[key]; return v && v.f && v.f !== 'daily' && v.a ? v : null; };
  const isDue = (v, d) => {
    if (!v) return true;
    const a = parseDay(v.a), diff = Math.round((d - a) / 864e5);
    if (diff < 0) return false;
    if (v.f === 'weekly') return diff % 7 === 0;
    if (v.f === 'biweekly') return diff % 14 === 0;
    if (v.f === 'monthly') return d.getDate() === Math.min(a.getDate(), dim(d.getFullYear(), d.getMonth()));
    if (v.f === 'annual') return d.getMonth() === a.getMonth() && d.getDate() === Math.min(a.getDate(), dim(d.getFullYear(), d.getMonth()));
    return true;
  };
  const nextDue = v => { const d = parseDay(todayStr()); for (let i = 1; i <= 400; i++) { d.setDate(d.getDate() + 1); if (isDue(v, d)) return d; } return null; };
  const fmtDay = d => d ? d.toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: 'numeric'}) : '';
  const peeked = key => { const p = store.get(PEEK_KEY, {}); return p.d === todayStr() && (p.k || []).includes(key); };
  const scheduledOff = key => !isDue(freqOf(key), parseDay(todayStr())) && !peeked(key);
  const cardName = c => (c.querySelector('.card-title')?.textContent || c.querySelector('summary')?.textContent || 'Section').replace(/[\p{Extended_Pictographic}\uFE0F]/gu, '').replace(/\s+/g, ' ').trim();
  const freqBlock = key => {
    const cur = freqOf(key)?.f || 'daily';
    const chips = FREQS.map(([id, name]) => `<button type="button" class="cz-chip cz-freq-chip${cur === id ? ' on' : ''}" data-f="${id}" aria-pressed="${cur === id}">${name}</button>`).join('');
    return `<div class="cz-freq"><div class="cz-head">How often do you want to see this section?</div><div class="cz-chips">${chips}</div><div class="cz-msg cz-freq-msg" role="status">${freqMsg(key)}</div></div>`;
  };
  const freqMsg = key => { const v = freqOf(key); return v ? `Showing ${FREQS.find(f => f[0] === v.f)[1].toLowerCase()} · next ${fmtDay(nextDue(v))}` : ''; };
  const applyHidden = () => {
    const hidden = hiddenSet(), resting = [];
    document.querySelectorAll('.container > .card').forEach(c => {
      const k = cardKey(c), off = !hidden.has(k) && scheduledOff(k);
      c.hidden = hidden.has(k) || off;
      if (off) resting.push([k, cardName(c), nextDue(freqOf(k))]);
    });
    let rest = document.getElementById('nv-resting');
    if (!resting.length) rest?.remove();
    else {
      if (!rest) {
        rest = document.createElement('div'); rest.id = 'nv-resting'; rest.className = 'nv-restore nv-resting';
        document.querySelector('.container').appendChild(rest);
        rest.addEventListener('click', e => { const b = e.target.closest('button[data-k]'); if (!b) return; const p = store.get(PEEK_KEY, {}), t = todayStr(); store.set(PEEK_KEY, {d: t, k: [...(p.d === t ? p.k || [] : []), b.dataset.k]}); applyHidden(); });
      }
      rest.innerHTML = 'Resting today: ' + resting.map(([k, n, d]) => `<button type="button" data-k="${esc(k)}" title="Show it today">${esc(n)}</button> <span>(next ${fmtDay(d)})</span>`).join(' · ');
    }
    let bar = document.getElementById('nv-restore');
    if (!hidden.size) { bar?.remove(); return; }
    if (!bar) {
      bar = document.createElement('div'); bar.id = 'nv-restore'; bar.className = 'nv-restore';
      const anchor = document.querySelector('.container');
      anchor.appendChild(bar);
      bar.addEventListener('click', e => { if (e.target.closest('button')) { store.del(HIDE_KEY); applyHidden(); } });
    }
    bar.innerHTML = `${hidden.size} section${hidden.size === 1 ? '' : 's'} hidden · <button type="button">Restore all</button>`;
  };


  const SECTIONS = {};
  // WEATHER — Change City
  const WX_KEY = 'nv_cz_weather_v1';
  const WX_DEFAULT = [
    {name: 'Bangkok', cc: 'TH', lat: 13.75, lon: 100.5, tz: 'Asia/Bangkok', season: 'Cool Season'},
    {name: 'Edmonton', cc: 'CA', lat: 53.55, lon: -113.49, tz: 'America/Edmonton'},
    {name: 'Medellín', cc: 'CO', lat: 6.24, lon: -75.58, tz: 'America/Bogota', season: 'Eternal Spring'},
    {name: 'Montevideo', cc: 'UY', lat: -34.9, lon: -56.16, tz: 'America/Montevideo'},
  ];
  const seasonOf = c => {
    if (c.season) return c.season;
    if (Math.abs(c.lat) < 23.5) return 'Tropical';
    const m = new Date().getUTCMonth(), north = ['Winter', 'Winter', 'Spring', 'Spring', 'Spring', 'Summer', 'Summer', 'Summer', 'Autumn', 'Autumn', 'Autumn', 'Winter'][m];
    return c.lat >= 0 ? north : ({Winter: 'Summer', Summer: 'Winter', Spring: 'Autumn', Autumn: 'Spring'})[north];
  };
  const WMO = c => c === 0 ? 'Clear ☀️' : c <= 2 ? 'Partly cloudy ⛅' : c === 3 ? 'Overcast ☁️' : c <= 48 ? 'Foggy 🌫' : c <= 57 ? 'Drizzle 🌦' : c <= 67 ? 'Rain 🌧' : c <= 77 ? 'Snow 🌨' : c <= 82 ? 'Showers 🌦' : c <= 86 ? 'Snow 🌨' : 'Storm ⛈';
  const AQ = v => v <= 50 ? 'Good' : v <= 100 ? 'Moderate' : v <= 150 ? 'Sensitive' : 'Unhealthy';
  const wxCities = () => { const v = store.get(WX_KEY, null); return Array.isArray(v) && v.length === 4 ? v : WX_DEFAULT; };
  const wxOriginal = document.querySelector('#weather-card .weather-grid')?.innerHTML;
  const renderWeather = () => {
    const grid = document.querySelector('#weather-card .weather-grid'); if (!grid) return;
    if (!store.get(WX_KEY, null)) { grid.innerHTML = wxOriginal; return; }
    const cities = wxCities();
    grid.innerHTML = cities.map(c => `<div class="weather-item">
          <div class="condition live-clock" data-tz="${esc(c.tz)}" style="font-size:.7rem;margin-bottom:3px;letter-spacing:.08em;font-weight:600">${new Intl.DateTimeFormat('en-GB', {timeZone: c.tz, hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'}).format(new Date())}</div>
          <div class="city">${flagOf(c.cc)} ${esc(c.name)}</div>
          <div class="temp">—</div>
          <div class="weather-range"><span>H —</span><span>L —</span></div>
          <div class="condition">Loading…</div>
          <div class="condition" style="margin-top:2px;font-style:italic">${esc(seasonOf(c))}</div>
          <div class="condition" style="margin-top:3px;font-size:.58rem;opacity:.7">💧 —</div>
        </div>`).join('');
    grid.querySelectorAll('.weather-item').forEach((card, i) => {
      const {lat, lon} = cities[i];
      Promise.all([
        getJSON(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,weather_code&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=1`),
        getJSON(`https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat}&longitude=${lon}&current=us_aqi`).catch(() => null),
      ]).then(([w, a]) => {
        const c = w.current; if (!c) return;
        card.querySelector('.temp').textContent = Math.round(c.temperature_2m) + '°C';
        const rng = card.querySelectorAll('.weather-range span');
        rng[0].textContent = 'H ' + Math.round(w.daily.temperature_2m_max[0]) + '°';
        rng[1].textContent = 'L ' + Math.round(w.daily.temperature_2m_min[0]) + '°';
        const conds = card.querySelectorAll('.condition:not(.live-clock)');
        conds[0].textContent = WMO(c.weather_code);
        const aqi = a?.current?.us_aqi;
        conds[2].textContent = '💧 ' + c.relative_humidity_2m + '%' + (Number.isFinite(aqi) ? ' · AQI ' + Math.round(aqi) + ' (' + AQ(aqi) + ')' : '');
      }).catch(() => { card.querySelectorAll('.condition:not(.live-clock)')[0].textContent = 'Unavailable'; });
    });
  };
  SECTIONS['weather-card'] = {
    title: 'Change City', label: 'City', items: () => wxCities().map(c => c.name), key: WX_KEY,
    async resolve(q, prev) {
      if (prev && norm(prev.name) === norm(q)) return prev;
      const j = await getJSON(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(q.split(',')[0].trim())}&count=5&language=en`);
      const want = norm(q.split(',')[1] || '');
      const r = (j.results || []).find(x => !want || norm(x.country).startsWith(want) || norm(x.country_code) === want || norm(x.admin1).startsWith(want)) || (j.results || [])[0];
      if (!r) throw new Error(`Couldn't find “${q}”`);
      return {name: r.name, cc: r.country_code, lat: +r.latitude.toFixed(2), lon: +r.longitude.toFixed(2), tz: r.timezone || 'UTC'};
    },
    current: () => wxCities(), render: renderWeather,
  };

  // WALL STREET — Change Index
  const IDX_KEY = 'nv_cz_indices_v1';
  const IDX_DEFAULT = [{symbol: 'ES=F', name: 'S&P 500'}, {symbol: 'NQ=F', name: 'NASDAQ 100'}, {symbol: 'YM=F', name: 'DOW JONES'}];
  const IDX_ALIAS = {sp500: 'ES=F', spx: 'ES=F', sandp500: 'ES=F', sandp: 'ES=F', sp: 'ES=F', nasdaq: 'NQ=F', nasdaq100: 'NQ=F', ndx: 'NQ=F', dow: 'YM=F', dowjones: 'YM=F', djia: 'YM=F',
    russell: 'RTY=F', russell2000: 'RTY=F', vix: '^VIX', nikkei: '^N225', nikkei225: '^N225', ftse: '^FTSE', ftse100: '^FTSE', dax: '^GDAXI', cac: '^FCHI', cac40: '^FCHI', hangseng: '^HSI', hsi: '^HSI',
    set: '^SET.BK', setindex: '^SET.BK', tsx: '^GSPTSE', sptsx: '^GSPTSE', asx: '^AXJO', asx200: '^AXJO', kospi: '^KS11', sensex: '^BSESN', nifty: '^NSEI', nifty50: '^NSEI', shanghai: '000001.SS', stoxx50: '^STOXX50E', eurostoxx: '^STOXX50E', ibovespa: '^BVSP', dxy: 'DX-Y.NYB', dollarindex: 'DX-Y.NYB'};
  const idxList = () => { const v = store.get(IDX_KEY, null); return Array.isArray(v) && v.length === 3 ? v : IDX_DEFAULT; };
  const idxOriginal = {};
  document.querySelectorAll('[data-future-symbol]').forEach(el => { idxOriginal[el.dataset.futureSymbol] = el.cloneNode(true); });
  const renderIndices = () => {
    const box = document.querySelector('.market-futures'); if (!box) return;
    box.innerHTML = '';
    idxList().forEach(it => {
      if (idxOriginal[it.symbol]) { box.appendChild(idxOriginal[it.symbol].cloneNode(true)); return; }
      const a = document.createElement('a');
      a.className = 'market-future market-link'; a.dataset.qSymbol = it.symbol; a.target = '_blank'; a.rel = 'noopener';
      a.href = 'https://finance.yahoo.com/quote/' + encodeURIComponent(it.symbol); a.title = it.symbol + ' · Yahoo Finance';
      a.innerHTML = `<span>${esc(it.name.toUpperCase())}</span><b>—</b><em>—</em>`;
      box.appendChild(a);
    });
    refreshCustomQuotes();
  };
  const yahooResolve = kind => async (q, prev) => {
    if (prev && (norm(prev.name) === norm(q) || norm(prev.symbol) === norm(q))) return prev;
    const j = await getJSON(`/api/quotes?kind=${kind}&q=${encodeURIComponent(q)}`).catch(() => null);
    if (!j?.ok) throw new Error(`Couldn't find “${q}”`);
    return {symbol: j.match.symbol, name: q.length <= 14 && !/[=^]/.test(q) ? q : (j.match.name || j.match.symbol).slice(0, 18)};
  };
  SECTIONS['wall-street-card'] = {
    title: 'Change Index', label: 'Index', items: () => idxList().map(i => i.name), key: IDX_KEY, current: idxList, render: renderIndices,
    async resolve(q, prev) {
      const d = IDX_DEFAULT.find(x => norm(x.name) === norm(q) || norm(x.symbol) === norm(q)); if (d) return d;
      const alias = IDX_ALIAS[norm(q)]; if (alias) { const dd = IDX_DEFAULT.find(x => x.symbol === alias); return dd || {symbol: alias, name: q}; }
      return yahooResolve('index')(q, prev);
    },
  };

  // COMMODITIES — Change Commodity
  const COM_KEY = 'nv_cz_commodities_v1';
  const COM_DEFAULT = [{key: 'GOLD', name: 'Gold'}, {key: 'SILVER', name: 'Silver'}, {key: 'COPPER', name: 'Copper'}, {key: 'WTI', name: 'Crude Oil'}, {key: 'URANIUM_SPOT', name: 'Uranium'}, {key: 'DIESEL', name: 'Diesel'}];
  const COM_ALIAS = {gold: 'GOLD', silver: 'SILVER', copper: 'COPPER', oil: 'WTI', crude: 'WTI', crudeoil: 'WTI', wti: 'WTI', uranium: 'URANIUM_SPOT', diesel: 'DIESEL',
    brent: ['BZ=F', 'Brent', '/bbl'], naturalgas: ['NG=F', 'Nat Gas', '/MMBtu'], natgas: ['NG=F', 'Nat Gas', '/MMBtu'], gas: ['NG=F', 'Nat Gas', '/MMBtu'], platinum: ['PL=F', 'Platinum', '/oz'], palladium: ['PA=F', 'Palladium', '/oz'],
    wheat: ['ZW=F', 'Wheat', '¢/bu'], corn: ['ZC=F', 'Corn', '¢/bu'], soybeans: ['ZS=F', 'Soybeans', '¢/bu'], soy: ['ZS=F', 'Soybeans', '¢/bu'], oats: ['ZO=F', 'Oats', '¢/bu'], rice: ['ZR=F', 'Rice', '/cwt'],
    coffee: ['KC=F', 'Coffee', '¢/lb'], cocoa: ['CC=F', 'Cocoa', '/t'], sugar: ['SB=F', 'Sugar', '¢/lb'], cotton: ['CT=F', 'Cotton', '¢/lb'], orangejuice: ['OJ=F', 'Orange Juice', '¢/lb'], oj: ['OJ=F', 'Orange Juice', '¢/lb'],
    lumber: ['LBR=F', 'Lumber', '/mbf'], gasoline: ['RB=F', 'Gasoline', '/gal'], heatingoil: ['HO=F', 'Heating Oil', '/gal'], cattle: ['LE=F', 'Live Cattle', '¢/lb'], livecattle: ['LE=F', 'Live Cattle', '¢/lb'], hogs: ['HE=F', 'Lean Hogs', '¢/lb'], leanhogs: ['HE=F', 'Lean Hogs', '¢/lb'],
    aluminum: ['ALI=F', 'Aluminum', '/t'], aluminium: ['ALI=F', 'Aluminum', '/t']};
  const comList = () => { const v = store.get(COM_KEY, null); return Array.isArray(v) && v.length === 6 ? v : COM_DEFAULT; };
  const comOriginal = {};
  document.querySelectorAll('.commodity-item[data-commodity]').forEach(el => { comOriginal[el.dataset.commodity] = el.cloneNode(true); });
  const renderCommodities = () => {
    const grid = document.querySelector('.commodities-grid'); if (!grid) return;
    grid.dataset.custom = store.get(COM_KEY, null) ? '1' : '';
    grid.innerHTML = '';
    comList().forEach(it => {
      if (it.key && comOriginal[it.key]) { grid.appendChild(comOriginal[it.key].cloneNode(true)); return; }
      const a = document.createElement('a');
      a.className = 'commodity-item market-link'; a.dataset.commodity = 'X_' + it.symbol; a.dataset.qSymbol = it.symbol; a.target = '_blank'; a.rel = 'noopener';
      a.href = 'https://finance.yahoo.com/quote/' + encodeURIComponent(it.symbol);
      a.innerHTML = `<div class="commodity-name" style="color:#d9c08a">${esc(it.name)}</div><div class="commodity-price"><span class="commodity-price-value">—</span><span class="commodity-unit">${esc(it.unit || '')}</span></div><div class="commodity-change">—</div>`;
      grid.appendChild(a);
    });
    refreshCustomQuotes();
    window.dispatchEvent(new Event('ws:commodities-rendered'));
  };
  SECTIONS['commodities-card'] = {
    title: 'Change Commodity', label: 'Commodity', items: () => comList().map(c => c.name), key: COM_KEY, current: comList, render: renderCommodities,
    async resolve(q, prev) {
      const a = COM_ALIAS[norm(q)];
      if (typeof a === 'string') return COM_DEFAULT.find(d => d.key === a);
      if (Array.isArray(a)) return {symbol: a[0], name: a[1], unit: a[2]};
      const r = await yahooResolve('commodity')(q, prev);
      return {...r, unit: ''};
    },
  };

  // CRYPTO — Change Token
  const TOK_KEY = 'nv_cz_tokens_v1';
  const TOK_DEFAULT = ['BTC', 'ETH', 'SOL', 'ZEC', 'ADA', 'SUI', 'TON', 'NIGHT'].map(s => ({sym: s}));
  const tokList = () => { const v = store.get(TOK_KEY, null); return Array.isArray(v) && v.length === 8 ? v : TOK_DEFAULT; };
  const tokOriginal = {};
  document.querySelectorAll('.crypto-item[data-coin]').forEach(el => { tokOriginal[el.dataset.coin] = el.cloneNode(true); });
  const renderTokens = () => {
    const grid = document.querySelector('.crypto-grid'); if (!grid) return;
    grid.dataset.custom = store.get(TOK_KEY, null) ? '1' : '';
    grid.innerHTML = '';
    tokList().forEach(t => {
      if (tokOriginal[t.sym] && !t.pair && !t.cg) { grid.appendChild(tokOriginal[t.sym].cloneNode(true)); return; }
      const a = document.createElement('a');
      a.className = 'crypto-item market-link'; a.dataset.coin = t.sym; a.dataset.qToken = '1'; a.target = '_blank'; a.rel = 'noopener';
      a.href = t.cg ? 'https://www.coingecko.com/en/coins/' + encodeURIComponent(t.cg) : 'https://www.binance.com/en/trade/' + encodeURIComponent(t.sym) + '_USDT';
      if (t.pair) a.dataset.pair = t.pair; if (t.cg) a.dataset.cg = t.cg;
      a.innerHTML = `<div class="crypto-symbol" style="color:#d9c08a">${esc(t.sym)}</div><div class="crypto-price">—</div><div class="crypto-change">—</div>`;
      grid.appendChild(a);
    });
    refreshTokens();
  };
  const refreshTokens = () => {
    const tiles = [...document.querySelectorAll('.crypto-item[data-q-token]')];
    tiles.filter(t => t.dataset.pair).forEach(t => getJSON('https://api.binance.com/api/v3/ticker/24hr?symbol=' + t.dataset.pair, {cache: 'no-store'}).then(d => {
      t.querySelector('.crypto-price').textContent = money(parseFloat(d.lastPrice));
      t.querySelector('.crypto-change').innerHTML = pctHtml(parseFloat(d.priceChangePercent));
    }).catch(() => {}));
    const cg = tiles.filter(t => t.dataset.cg && !t.dataset.pair);
    if (cg.length) getJSON('https://api.coingecko.com/api/v3/simple/price?vs_currencies=usd&include_24hr_change=true&ids=' + cg.map(t => t.dataset.cg).join(',')).then(j => cg.forEach(t => {
      const r = j[t.dataset.cg]; if (!r) return;
      t.querySelector('.crypto-price').textContent = money(Number(r.usd));
      t.querySelector('.crypto-change').innerHTML = pctHtml(Number(r.usd_24h_change));
    })).catch(() => {});
  };
  SECTIONS['crypto-card'] = {
    title: 'Change Token', label: 'Token', items: () => tokList().map(t => t.sym), key: TOK_KEY, current: tokList, render: renderTokens,
    async resolve(q, prev) {
      const sym = q.toUpperCase().replace(/[^A-Z0-9]/g, '');
      if (prev && prev.sym === sym) return prev;
      if (tokOriginal[sym]) return {sym};
      const bin = await getJSON('https://api.binance.com/api/v3/ticker/price?symbol=' + sym + 'USDT').catch(() => null);
      if (bin?.price) return {sym, pair: sym + 'USDT'};
      const s = await getJSON('https://api.coingecko.com/api/v3/search?query=' + encodeURIComponent(q)).catch(() => null);
      const hit = (s?.coins || []).find(c => c.symbol?.toUpperCase() === sym) || (s?.coins || [])[0];
      if (!hit) throw new Error(`Couldn't find “${q}”`);
      return {sym: hit.symbol.toUpperCase(), cg: hit.id};
    },
  };

  // FX — Change Currency
  const FX_KEY = 'nv_cz_fx_v1';
  const FX_DEFAULT = ['THB', 'CAD', 'AUD', 'COP', 'EUR', 'RUB', 'KRW', 'JPY'].map(c => ({code: c}));
  const fxList = () => { const v = store.get(FX_KEY, null); return Array.isArray(v) && v.length === 8 ? v : FX_DEFAULT; };
  const fxOriginal = {};
  document.querySelectorAll('.fx-chip').forEach(el => { const c = el.querySelector('[data-fx-rate]')?.dataset.fxRate; if (c) fxOriginal[c] = el.cloneNode(true); });
  const fxFlag = c => c === 'EUR' ? '🇪🇺' : c === 'XAU' ? '🪙' : flagOf(c.slice(0, 2));
  const fxOriginalHtml = document.querySelector('.fx-row')?.innerHTML;
  const renderFx = () => {
    const row = document.querySelector('.fx-row'); if (!row) return;
    if (!store.get(FX_KEY, null)) { row.innerHTML = fxOriginalHtml; return; }
    row.innerHTML = '';
    const list = fxList();
    list.forEach(({code}) => {
      if (fxOriginal[code]) { row.appendChild(fxOriginal[code].cloneNode(true)); return; }
      const a = document.createElement('a');
      a.className = 'fx-chip market-link'; a.target = '_blank'; a.rel = 'noopener';
      a.href = 'https://www.investing.com/currencies/usd-' + code.toLowerCase();
      a.innerHTML = `<div class="fx-ccy"><span class="fx-flag">${fxFlag(code)}</span> ${esc(code)}</div><span class="fx-rate" data-fx-rate="${esc(code)}">—</span><span class="fx-change" data-fx-chg="${esc(code)}"></span>`;
      row.appendChild(a);
    });
    if (store.get(FX_KEY, null)) getJSON('/api/fx-rates?c=' + list.map(x => x.code).join(',') + '&_=' + Date.now(), {cache: 'no-store'}).then(d => {
      Object.keys(d.rates || {}).forEach(c => {
        const el = row.querySelector(`[data-fx-rate="${c}"]`), ce = row.querySelector(`[data-fx-chg="${c}"]`), r = Number(d.rates[c]), ch = Number((d.changes || {})[c]);
        if (el && Number.isFinite(r)) el.textContent = r >= 1000 ? Math.round(r).toLocaleString('en-US') : r >= 10 ? r.toFixed(2) : r.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
        if (ce && Number.isFinite(ch)) ce.innerHTML = pctHtml(ch);
      });
    }).catch(() => {});
  };
  SECTIONS['fx-card'] = {
    title: 'Change Currency', label: 'Currency', items: () => fxList().map(x => x.code), key: FX_KEY, current: fxList, render: renderFx,
    async resolve(q) {
      const code = q.toUpperCase().replace(/[^A-Z]/g, '');
      if (!/^[A-Z]{3}$/.test(code) || code === 'USD') throw new Error(`Use a 3-letter code like GEL, not “${q}”`);
      if (fxOriginal[code]) return {code};
      const d = await getJSON('/api/fx-rates?c=' + code).catch(() => null);
      if (!d?.rates?.[code]) throw new Error(`No rate for ${code}`);
      return {code};
    },
  };


  // FLÂNEUR — Change Destination (4 countdowns)
  const DEST_KEY = 'nv_cz_dest_v1';
  const destItems = () => [...document.querySelectorAll('#world-tour-card .countdown-item')];
  const DEST_DEFAULT = destItems().map(el => ({name: el.querySelector('.countdown-label').textContent.trim(), date: el.dataset.date || '', label: el.querySelector('.countdown-date').textContent.trim(), days: el.querySelector('.countdown-days').textContent.trim(), url: el.getAttribute('href') || ''}));
  const loadDest = () => { const v = store.get(DEST_KEY, null); return Array.isArray(v) && v.length === DEST_DEFAULT.length ? v : DEST_DEFAULT; };
  const bkkToday = () => { const p = new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Bangkok'}).format(new Date()); return Date.parse(p + 'T00:00:00Z'); };
  const fmtDest = iso => { const dt = new Date(iso + 'T00:00:00Z'); const far = dt - Date.now() > 300 * 864e5; return new Intl.DateTimeFormat('en-US', far ? {month: 'short', year: 'numeric', timeZone: 'UTC'} : {month: 'short', day: 'numeric', timeZone: 'UTC'}).format(dt); };
  const renderDest = () => loadDest().forEach((d, i) => {
    const el = destItems()[i]; if (!el) return;
    el.querySelector('.countdown-label').textContent = d.name;
    if (d.date && d.date !== (DEST_DEFAULT[i] || {}).date) {
      const n = Math.round((Date.parse(d.date + 'T00:00:00Z') - bkkToday()) / 864e5);
      el.querySelector('.countdown-days').textContent = n > 1 ? n + ' days' : n === 1 ? '1 day' : n === 0 ? 'Today' : Math.abs(n) + ' days since';
      el.querySelector('.countdown-date').textContent = fmtDest(d.date);
    } else { el.querySelector('.countdown-days').textContent = d.days; el.querySelector('.countdown-date').textContent = d.label; }
    el.href = d.url || ('https://www.google.com/search?q=' + encodeURIComponent(d.name.replace(/[^\p{L}\p{N} ]/gu, '').trim()));
  });
  // Shared live quotes for custom index + commodity tiles
  function refreshCustomQuotes() {
    const tiles = [...document.querySelectorAll('[data-q-symbol]')];
    if (!tiles.length) return;
    const syms = [...new Set(tiles.map(t => t.dataset.qSymbol))];
    getJSON('/api/quotes?s=' + encodeURIComponent(syms.join(',')) + '&_=' + Date.now(), {cache: 'no-store'}).then(j => {
      (j.quotes || []).forEach(q => document.querySelectorAll(`[data-q-symbol="${CSS.escape(q.symbol)}"]`).forEach(t => {
        const price = Number(q.price), ch = q.change == null ? NaN : Number(q.change);
        if (t.classList.contains('market-future')) {
          t.querySelector('b').textContent = num(price);
          const em = t.querySelector('em'); em.textContent = Number.isFinite(ch) ? (ch >= 0 ? '+' : '') + ch.toFixed(2) + '%' : '—'; em.className = Number.isFinite(ch) ? (ch >= 0 ? 'positive' : 'negative') : '';
        } else {
          t.querySelector('.commodity-price-value').textContent = q.currency === 'USX' ? num(price) : q.currency && q.currency !== 'USD' ? num(price) + ' ' + q.currency : money(price);
          t.querySelector('.commodity-change').innerHTML = pctHtml(ch);
        }
      }));
    }).catch(() => {});
  }
  setInterval(() => { refreshCustomQuotes(); refreshTokens(); }, 60000);


  // Initial render of saved customisations
  if (store.get(WX_KEY, null)) renderWeather();
  if (store.get(IDX_KEY, null)) renderIndices();
  if (store.get(COM_KEY, null)) renderCommodities();
  if (store.get(TOK_KEY, null)) renderTokens();
  if (store.get(FX_KEY, null)) renderFx();
  if (store.get(DEST_KEY, null)) renderDest();
  applyHidden();

  // ── Panel UI ──
  const deleteBtn = '<button type="button" class="cz-delete">Delete Section</button>';
  const actions = extra => `<div class="cz-actions">${deleteBtn}<span class="cz-spacer"></span>${extra || ''}</div>`;
  const customizePanel = card => {
    const key = cardKey(card);
    if (card.id === 'world-tour-card') {
      const rows = loadDest().map((d, i) => `<div class="cz-row"><input data-k="name" data-i="${i}" maxlength="28" value="${esc(d.name)}" aria-label="Destination ${i + 1}"><input type="date" data-k="date" data-i="${i}" value="${esc(d.date)}" aria-label="Date ${i + 1}"></div>`).join('');
      return `<form class="cz-form" data-mode="dest"><div class="cz-head">Change Destination</div>${rows}${actions('<button type="button" class="cz-reset">Reset</button><button type="submit">Apply</button>')}</form>`;
    }
    const sec = SECTIONS[key];
    if (sec) {
      const rows = sec.items().map((v, i) => `<label class="cz-box"><span>Box ${i + 1}</span><input data-i="${i}" maxlength="32" value="${esc(v)}" placeholder="${esc(v)}" aria-label="${sec.label} box ${i + 1}" autocomplete="off" spellcheck="false"></label>`).join('');
      return `<form class="cz-form" data-mode="list"><div class="cz-head">${sec.title}</div><div class="cz-grid">${rows}</div><div class="cz-msg" role="status"></div>${actions('<button type="button" class="cz-reset">Reset</button><button type="submit">Apply</button>')}</form>`;
    }
    return `<form class="cz-form" data-mode="none">${actions()}</form>`;
  };
  const CHEVRON = '<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  document.querySelectorAll('.container > .card').forEach(card => {
    if (card.classList.contains('anki-quick-row')) return;
    const host = card.querySelector(':scope > .signal-accordion-body') || card;
    const wrap = document.createElement('div');
    wrap.className = 'cz';
    wrap.innerHTML = `<button type="button" class="cz-btn" aria-expanded="false" aria-label="Customize ${esc(cardName(card))}" title="Customize">${CHEVRON}</button><div class="cz-panel" hidden></div>`;
    host.appendChild(wrap);
    const btn = wrap.querySelector('.cz-btn'), panel = wrap.querySelector('.cz-panel');
    const close = () => { panel.hidden = true; btn.setAttribute('aria-expanded', 'false'); wrap.classList.remove('is-open'); };
    const open = () => { panel.innerHTML = customizePanel(card); { const f = panel.querySelector('.cz-form'), a = f && f.querySelector(':scope > .cz-actions'); if (f) a ? a.insertAdjacentHTML('beforebegin', freqBlock(cardKey(card))) : f.insertAdjacentHTML('beforeend', freqBlock(cardKey(card))); wireFreq(); } panel.hidden = false; btn.setAttribute('aria-expanded', 'true'); wrap.classList.add('is-open'); wire(); };
    ['click', 'keydown', 'keyup'].forEach(t => wrap.addEventListener(t, ev => ev.stopPropagation()));
    btn.addEventListener('click', e => { e.preventDefault(); panel.hidden ? open() : close(); });
    function wireFreq() {
      const box = panel.querySelector('.cz-freq'); if (!box) return;
      box.querySelectorAll('.cz-freq-chip').forEach(ch => ch.addEventListener('click', () => {
        const k = cardKey(card), all = store.get(FREQ_KEY, {});
        if (ch.dataset.f === 'daily') delete all[k]; else all[k] = {f: ch.dataset.f, a: todayStr()};
        store.set(FREQ_KEY, all);
        box.querySelectorAll('.cz-freq-chip').forEach(o => { o.classList.toggle('on', o === ch); o.setAttribute('aria-pressed', String(o === ch)); });
        box.querySelector('.cz-freq-msg').textContent = freqMsg(k);
        applyHidden();
      }));
    }
    function wire() {
      const form = panel.querySelector('.cz-form'); if (!form) return;
      const del = form.querySelector('.cz-delete');
      del.addEventListener('click', () => {
        if (!del.classList.contains('armed')) { del.classList.add('armed'); del.textContent = 'Tap again to delete'; setTimeout(() => { del.classList.remove('armed'); del.textContent = 'Delete Section'; }, 3500); return; }
        const h = hiddenSet(); h.add(cardKey(card)); store.set(HIDE_KEY, [...h]); close(); applyHidden();
      });
      form.addEventListener('submit', ev => ev.preventDefault());
      const reset = form.querySelector('.cz-reset');
      if (form.dataset.mode === 'dest') {
        form.addEventListener('submit', () => {
          const cur = loadDest(), next = cur.map(d => ({...d}));
          form.querySelectorAll('input').forEach(inp => { const i = +inp.dataset.i, k = inp.dataset.k, v = inp.value.trim(); if (v && v !== cur[i][k]) { next[i][k] = v; if (k === 'name') next[i].url = ''; } });
          if (JSON.stringify(next) !== JSON.stringify(DEST_DEFAULT)) store.set(DEST_KEY, next); else store.del(DEST_KEY);
          renderDest(); close();
        });
        reset.addEventListener('click', () => { store.del(DEST_KEY); renderDest(); open(); });
        return;
      }
      if (form.dataset.mode !== 'list') return;
      const sec = SECTIONS[cardKey(card)], msg = form.querySelector('.cz-msg'), apply = form.querySelector('button[type=submit]');
      reset.addEventListener('click', () => { store.del(sec.key); sec.render(); open(); });
      form.addEventListener('submit', async () => {
        const prev = sec.current(), labels = sec.items();
        apply.disabled = true; apply.textContent = 'Applying…'; msg.textContent = ''; msg.classList.remove('err');
        try {
          const next = await Promise.all([...form.querySelectorAll('input')].map(inp => {
            const i = +inp.dataset.i, v = inp.value.trim();
            if (!v || v === labels[i]) return prev[i];
            return sec.resolve(v, prev[i]).catch(err => { inp.classList.add('bad'); throw err; });
          }));
          store.set(sec.key, next); sec.render(); close();
        } catch (err) {
          msg.textContent = err.message || 'Lookup failed'; msg.classList.add('err');
          apply.disabled = false; apply.textContent = 'Apply';
        }
      });
      form.querySelectorAll('input').forEach(inp => inp.addEventListener('input', () => inp.classList.remove('bad')));
    }
  });
})();
