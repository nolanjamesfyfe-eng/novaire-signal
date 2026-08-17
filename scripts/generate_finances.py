#!/usr/bin/env python3
"""Generate the standalone On The Rise Finances debt dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "portfolio" / "finances"
CURRENT_PERIOD = "2026-08-01"
STARTING_DEBT = 58_000
SHEET_ID = "1rqRNI6z3rqXGCMlPbsbVEJUw82DCskU9qf9sKEXMnak"

RAW_ROWS = [
("2026-01-01",27000,31000,58000,470,293,763,9158),("2026-02-01",25318,31000,56318,441,293,734,8807),
("2026-03-01",21818,31000,52818,380,293,673,8075),("2026-04-01",24000,31000,55000,418,293,711,8531),
("2026-05-01",20500,31000,51500,357,293,650,7800),("2026-06-01",24392,31000,55392,425,293,718,8613),
("2026-07-01",20892,31000,51892,364,293,657,7882),("2026-08-01",25000,31000,56000,435,293,728,8740),
("2026-09-01",21500,31000,52500,374,293,667,8009),("2026-10-01",19200,31000,50200,334,293,627,7528),
("2026-11-01",16900,31000,47900,294,293,587,7048),("2026-12-01",14600,31000,45600,254,293,547,6567),
("2027-01-01",12600,31000,43600,219,293,512,6149),("2027-02-01",10600,31000,41600,185,293,478,5731),
("2027-03-01",8600,31000,39600,150,293,443,5313),("2027-04-01",6600,31000,37600,115,293,408,4895),
("2027-05-01",4600,31000,35600,80,293,373,4477),("2027-06-01",2600,31000,33600,45,293,338,4059),
("2027-07-01",600,31000,31600,10,293,303,3641),("2027-08-01",-1400,31000,29600,-24,293,269,3223),
("2027-09-01",-3400,31000,27600,-59,293,234,2805),
]
FIELDS = ("date","visa","line","total_debt","visa_interest","line_interest","total_interest","annual_interest")

def build_payload(current_period: str = CURRENT_PERIOD) -> dict:
    dates = {r[0] for r in RAW_ROWS}
    if current_period not in dates:
        raise ValueError(f"current period {current_period!r} is not in seed data")
    rows = []
    for raw in RAW_ROWS:
        row: dict[str, Any] = dict(zip(FIELDS, raw))
        row["status"] = "actual" if str(row["date"]) <= current_period else "projection"
        rows.append(row)
    return {"schema_version": 1, "title": "On The Rise Finances", "currency": "CAD", "starting_debt": STARTING_DEBT,
            "baseline_period": RAW_ROWS[0][0], "current_period": current_period, "projection_rule": "Periods after current_period are projections.",
            "source": {"type": "screenshot_seed", "google_sheet_id": SHEET_ID}, "rows": rows}

def render_html(payload: dict) -> str:
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__DASHBOARD_DATA__", data)

def generate(out_dir: Path = DEFAULT_OUT, current_period: str = CURRENT_PERIOD) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(current_period)
    json_path, html_path = out_dir / "data.json", out_dir / "index.html"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_html(payload), encoding="utf-8")
    return html_path, json_path

TEMPLATE = r'''<!doctype html>
<html lang="en" data-current-period="2026-08-01"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>On The Rise Finances — Debt Dashboard</title><meta name="theme-color" content="#090909"><meta name="description" content="A focused debt payoff dashboard for On The Rise.">
<style>
:root{--bg:#090909;--panel:#11110f;--panel2:#171612;--gold:#b59662;--ivory:#eee8dc;--muted:#918b81;--line:#2b2923;--fire:#e76527;--green:#7da66a;--red:#d17865;--serif:Georgia,'Times New Roman',serif;--sans:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}*{box-sizing:border-box}html{background:var(--bg);color:var(--ivory);scroll-behavior:smooth}body{margin:0;font:14px/1.55 var(--sans);background:radial-gradient(ellipse at 50% 0,rgba(181,150,98,.1),transparent 42rem);min-height:100vh}.wrap{width:min(720px,calc(100% - 28px));margin:auto;padding:44px 0 70px}.eyebrow,.label{text-transform:uppercase;letter-spacing:.18em;font-size:10px;font-weight:700;color:var(--gold)}h1,h2,.big{font-family:var(--serif);font-weight:400}h1{font-size:clamp(35px,8vw,54px);line-height:1;margin:9px 0 8px;color:var(--ivory)}header p{color:var(--muted);margin:0;max-width:540px}.period{margin-top:18px;display:inline-flex;gap:8px;align-items:center;border:1px solid var(--line);padding:6px 10px;border-radius:999px;color:var(--muted);font-size:11px}.dot{width:7px;height:7px;background:var(--green);border-radius:50%;box-shadow:0 0 12px var(--green)}section{margin-top:32px}.section-head{display:flex;align-items:end;justify-content:space-between;margin-bottom:10px}.section-head h2{font-size:23px;margin:0}.section-head small{color:var(--muted)}.card{background:linear-gradient(145deg,rgba(255,255,255,.018),transparent),var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}.hero-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.metric{min-height:224px;position:relative;overflow:hidden}.big{font-size:36px;line-height:1.05;margin-top:7px}.sub{font-size:12px;color:var(--muted);margin-top:6px}.fire-stage{height:108px;display:flex;justify-content:center;align-items:flex-end;margin-top:12px}.flame{width:58px;height:calc(35px + 65px * var(--intensity));position:relative;transform-origin:50% 100%;filter:drop-shadow(0 0 13px rgba(231,101,39,.42));animation:flicker 1.35s ease-in-out infinite alternate}.flame:before,.flame:after{content:"";position:absolute;inset:0;background:linear-gradient(145deg,#ffd078 8%,var(--fire) 66%,#a93014);border-radius:70% 25% 62% 38%/70% 40% 60% 30%;transform:rotate(45deg)}.flame:after{inset:40% 27% 5%;background:#ffe7a8;opacity:.9}.battery{margin:28px auto 20px;width:130px;height:66px;border:3px solid var(--muted);border-radius:8px;padding:5px;position:relative}.battery:after{content:"";position:absolute;right:-10px;top:20px;width:7px;height:22px;background:var(--muted);border-radius:0 3px 3px 0}.charge{height:100%;width:var(--charge);max-width:100%;background:linear-gradient(90deg,#52774a,var(--green));border-radius:3px;box-shadow:0 0 16px rgba(125,166,106,.28);transition:width .6s}.tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.tab{appearance:none;background:var(--panel);border:1px solid var(--line);color:var(--muted);padding:13px 5px;border-radius:10px;font:700 11px var(--sans);letter-spacing:.08em;cursor:pointer}.tab[aria-selected=true]{color:var(--ivory);border-color:var(--gold);background:#1b1812}.progress-detail{margin-top:10px;display:grid;grid-template-columns:1fr auto;align-items:center}.progress-detail .big{font-size:31px}.positive{color:var(--green)}.negative{color:var(--red)}.chart-card{padding:14px 10px 8px}canvas{width:100%;height:245px;display:block}.legend{display:flex;gap:14px;padding:4px 8px 8px;color:var(--muted);font-size:11px}.key{display:inline-block;width:15px;border-top:2px solid var(--gold);vertical-align:middle;margin-right:5px}.key.proj{border-top-style:dashed;opacity:.65}.breakdown{display:grid;grid-template-columns:1fr 1fr;gap:12px}.split-bar{height:13px;background:#282720;border-radius:999px;overflow:hidden;margin:20px 0 14px;display:flex}.split-bar i:first-child{background:var(--fire)}.split-bar i:last-child{background:var(--gold)}.row{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid var(--line)}.row:last-child{border:0}.row span{color:var(--muted)}.milestone{position:relative;padding-left:52px}.crest{position:absolute;left:15px;top:18px;width:25px;height:31px;border:1px solid var(--gold);clip-path:polygon(50% 0,100% 19%,89% 76%,50% 100%,11% 76%,0 19%);display:grid;place-items:center;color:var(--gold)}.xp-track{height:7px;background:#282720;border-radius:9px;margin-top:13px;overflow:hidden}.xp-fill{height:100%;background:linear-gradient(90deg,var(--gold),#e5c98f)}.projection-note{border-left:2px solid var(--gold);color:var(--muted);font-size:12px}.footer{text-align:center;color:#615e57;font-size:10px;letter-spacing:.12em;margin-top:38px;text-transform:uppercase}@keyframes flicker{from{transform:rotate(-2deg) scaleX(.95)}to{transform:rotate(2deg) scaleX(1.05)}}
@media(max-width:570px){.wrap{padding-top:30px}.hero-grid,.breakdown{grid-template-columns:1fr}.metric{min-height:204px}.tabs{gap:5px}.tab{padding:12px 2px}canvas{height:220px}.section-head{align-items:start;flex-direction:column;gap:3px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
</style></head><body><main class="wrap"><header><div class="eyebrow">On The Rise · Finances</div><h1>Debt, under command.</h1><p>See the cost. Keep the pressure. Build the freedom.</p><div class="period"><i class="dot"></i><span id="periodLabel"></span></div></header>
<section class="hero-grid"><article class="card metric"><div class="label">Interest fire intensity</div><div class="big" id="firePct"></div><div class="sub" id="interestCopy"></div><div class="fire-stage" aria-hidden="true"><div class="flame" id="flame"></div></div></article><article class="card metric"><div class="label">Freedom battery</div><div class="big" id="batteryPct"></div><div class="sub">Debt paid from the $58,000 starting balance</div><div class="battery" role="img" id="battery"><div class="charge"></div></div></article></section>
<section><div class="section-head"><h2>Payoff velocity</h2><small>Choose a lookback</small></div><div class="tabs" role="tablist"><button class="tab" data-months="1" aria-selected="true">1M</button><button class="tab" data-months="3" aria-selected="false">3M</button><button class="tab" data-months="6" aria-selected="false">6M</button><button class="tab" data-months="12" aria-selected="false">1Y</button></div><div class="card progress-detail" aria-live="polite"><div><div class="label" id="velocityLabel"></div><div class="big" id="velocityValue"></div><div class="sub" id="velocityCopy"></div></div><div class="big" id="velocityIcon">↘</div></div></section>
<section><div class="section-head"><h2>Debt trajectory</h2><small>Actual + clearly marked projection</small></div><div class="card chart-card"><canvas id="chart" aria-label="Monthly total debt trend chart" role="img"></canvas><div class="legend"><span><i class="key"></i>Actual</span><span><i class="key proj"></i>Projection</span></div></div></section>
<section><div class="section-head"><h2>Debt architecture</h2><small id="breakdownDate"></small></div><div class="breakdown"><article class="card"><div class="label">Card vs. line</div><div class="split-bar"><i id="visaBar"></i><i id="lineBar"></i></div><div class="row"><span>Visa card</span><b id="visaValue"></b></div><div class="row"><span>Line of credit</span><b id="lineValue"></b></div><div class="row"><span>Total debt</span><b id="totalValue"></b></div></article><article class="card milestone"><div class="crest">✦</div><div class="label">Milestone / XP</div><div class="big" id="xpLevel"></div><div class="sub" id="xpCopy"></div><div class="xp-track"><div class="xp-fill" id="xpFill"></div></div><div class="row"><span>Next unlock</span><b id="nextUnlock"></b></div></article></div></section>
<section class="card projection-note"><b>Projection boundary:</b> figures after <span id="boundary"></span> are planning estimates, not actual balances. Negative Visa values in the source projection represent an overpayment/credit balance and are preserved.</section><div class="footer">On The Rise · Every payment earns freedom</div></main>
<script id="finance-data" type="application/json">__DASHBOARD_DATA__</script><script>
(()=>{'use strict';const DATA=JSON.parse(document.getElementById('finance-data').textContent);window.OnTheRiseFinances={data:DATA,setCurrentPeriod(date){if(!DATA.rows.some(r=>r.date===date))throw new Error('Unknown period: '+date);document.documentElement.dataset.currentPeriod=date;render(date);}};const $=id=>document.getElementById(id),money=n=>new Intl.NumberFormat('en-CA',{style:'currency',currency:DATA.currency||'CAD',currencyDisplay:'narrowSymbol',maximumFractionDigits:0}).format(n),month=d=>new Date(d+'T00:00:00').toLocaleDateString('en-CA',{month:'short',year:'numeric'});let lookback=1;
function current(date){return DATA.rows.find(r=>r.date===date)||DATA.rows.find(r=>r.date===DATA.current_period)}function render(date=document.documentElement.dataset.currentPeriod||DATA.current_period){const r=current(date),idx=DATA.rows.indexOf(r),base=DATA.rows[0],intensity=r.total_interest/base.total_interest*100,paid=Math.max(0,Math.min(DATA.starting_debt,DATA.starting_debt-r.total_debt)),charge=paid/DATA.starting_debt*100;$('periodLabel').textContent=month(r.date)+' · '+r.status;$('firePct').textContent=intensity.toFixed(1)+'%';$('interestCopy').textContent=money(r.total_interest)+' monthly interest vs. '+money(base.total_interest)+' Jan 2026 baseline';$('flame').style.setProperty('--intensity',Math.max(.05,Math.min(1,intensity/100)));$('batteryPct').textContent=charge.toFixed(1)+'% charged';$('battery').style.setProperty('--charge',charge+'%');$('battery').setAttribute('aria-label','Freedom battery '+charge.toFixed(1)+' percent charged; full only when debt reaches zero');$('breakdownDate').textContent=month(r.date);$('visaValue').textContent=money(r.visa);$('lineValue').textContent=money(r.line);$('totalValue').textContent=money(r.total_debt);const visaShare=Math.max(0,r.visa)/Math.max(1,Math.max(0,r.visa)+r.line)*100;$('visaBar').style.width=visaShare+'%';$('lineBar').style.width=(100-visaShare)+'%';const xp=Math.round(charge*10),level=Math.floor(xp/100)+1,next=Math.min(DATA.starting_debt,Math.ceil(paid/5000)*5000||5000);$('xpLevel').textContent='Level '+level;$('xpCopy').textContent=xp+' XP · 10 XP for every 1% of starting debt retired';$('xpFill').style.width=(xp%100)+'%';$('nextUnlock').textContent=money(next)+' paid';$('boundary').textContent=month(r.date);renderVelocity(idx);drawChart(idx)}
function renderVelocity(idx){const now=DATA.rows[idx],past=DATA.rows[Math.max(0,idx-lookback)],change=past.total_debt-now.total_debt,good=change>=0;$('velocityLabel').textContent=lookback+' month'+(lookback>1?'s':'')+' progress';$('velocityValue').textContent=(good?'-':'+')+money(Math.abs(change));$('velocityValue').className='big '+(good?'positive':'negative');$('velocityCopy').textContent=good?'Debt retired since '+month(past.date):'Debt increased since '+month(past.date);$('velocityIcon').textContent=good?'↘':'↗';$('velocityIcon').className='big '+(good?'positive':'negative')}
function drawChart(currentIdx){const c=$('chart'),rect=c.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);c.width=rect.width*dpr;c.height=rect.height*dpr;const x=c.getContext('2d');x.scale(dpr,dpr);const w=rect.width,h=rect.height,p={l:43,r:13,t:18,b:31},rows=DATA.rows,min=25000,max=60000,X=i=>p.l+i*(w-p.l-p.r)/(rows.length-1),Y=v=>p.t+(max-v)*(h-p.t-p.b)/(max-min);x.font='10px Inter,sans-serif';x.fillStyle='#777168';x.strokeStyle='#292720';x.lineWidth=1;[30000,40000,50000,60000].forEach(v=>{x.beginPath();x.moveTo(p.l,Y(v));x.lineTo(w-p.r,Y(v));x.stroke();x.fillText('$'+v/1000+'k',4,Y(v)+3)});function line(a,b,dash){x.beginPath();x.setLineDash(dash?[5,5]:[]);for(let i=a;i<=b;i++){const px=X(i),py=Y(rows[i].total_debt);i===a?x.moveTo(px,py):x.lineTo(px,py)}x.strokeStyle='#b59662';x.lineWidth=2;x.stroke()}line(0,currentIdx,false);if(currentIdx<rows.length-1)line(Math.max(0,currentIdx),rows.length-1,true);x.setLineDash([]);x.fillStyle='#b59662';x.beginPath();x.arc(X(currentIdx),Y(rows[currentIdx].total_debt),4,0,Math.PI*2);x.fill();[0,Math.floor((rows.length-1)/2),rows.length-1].forEach(i=>x.fillText(month(rows[i].date).replace(' ',' ‘'),X(i)-16,h-8))}
document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{lookback=+b.dataset.months;document.querySelectorAll('.tab').forEach(t=>t.setAttribute('aria-selected',t===b));render()}));addEventListener('resize',()=>render());render();})();
</script></body></html>'''

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--current-period", default=CURRENT_PERIOD)
    args = parser.parse_args()
    html, data = generate(args.out, args.current_period)
    print(f"generated {html}")
    print(f"generated {data}")

if __name__ == "__main__":
    main()
