"""Render Novaire Signal's close-to-close portfolio Daily."""
from __future__ import annotations
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any

MARKET_TERMS = ("stocks", "futures", "yields", "bonds", "wall street", "nasdaq", "s&p", "dow ", "fed sends", "dollar jumps", "dollar dumps")
GEO_TERMS = ("china", "russia", "ukraine", "iran", "israel", "war", "tariff", "sanction", "nato", "taiwan", "oil")


def _pick(items, terms, skip=None):
    skip = skip or set()
    for item in items or []:
        title = str(item.get("title", ""))
        if item.get("url") not in skip and any(term in title.lower() for term in terms):
            return item
    return next((item for item in (items or []) if item.get("url") not in skip), {"title": "No verified headline available", "url": "#"})


def _period(series, mode):
    valid = [p for p in series or [] if isinstance(p.get("cad"), (int, float)) or isinstance(p.get("usd"), (int, float))]
    if len(valid) < 2:
        return None
    latest = valid[-1]
    latest_date = date.fromisoformat(latest["market_date"])
    baseline = next((p for p in valid if (date.fromisoformat(p["market_date"]).year == latest_date.year and (mode == "ytd" or date.fromisoformat(p["market_date"]).month == latest_date.month))), None)
    key = "usd" if isinstance(latest.get("usd"), (int, float)) else "cad"
    if not baseline or not isinstance(baseline.get(key), (int, float)) or not baseline[key]:
        return None
    return (latest[key] / baseline[key] - 1) * 100


def _pct(value):
    if value is None:
        return "—"
    return f"{'+' if value >= 0 else ''}{value:.1f}%"


def _account_card(label, accent, biggest, value, daily, mtd=None, ytd=None, metrics_only=False):
    daily_cls = "up" if (daily or 0) >= 0 else "down"
    detail = "" if metrics_only else f'<div class="account-lead">Largest position <strong>{escape(biggest)}</strong></div>'
    return f'''<article class="account" style="--accent:{accent}">
      <div class="account-kicker">{escape(label)}</div><div class="account-symbol">{escape(biggest)}</div>{detail}
      <div class="account-value">{escape(value)}</div>
      <div class="account-metrics"><span>Daily <b class="{daily_cls}">{_pct(daily)}</b></span><span>MTD <b>{_pct(mtd)}</b></span><span>YTD <b>{_pct(ytd)}</b></span></div>
    </article>'''


def render_daily_html(*, portfolio_data, holdings, tracker_model, kraken_meta, crypto, evo_positions, alpaca, zh_news, catalysts, generated_at=None):
    generated_at = generated_at or datetime.now().astimezone()
    by_value = sorted(holdings or [], key=lambda h: portfolio_data.get(h["ticker"], {}).get("value") or 0, reverse=True)
    ws = by_value[0] if by_value else {"ticker": "—", "display": "—"}
    ws_data = portfolio_data.get(ws.get("ticker"), {})
    ws_symbol = ws.get("display") or ws.get("ticker", "—").split(".")[0]

    weight_rows = kraken_meta.get("position_weights_pct", []) if isinstance(kraken_meta, dict) else []
    weights = {str(symbol): float(weight) for symbol, weight in weight_rows}
    kr_symbol = max(weights.items(), key=lambda item: item[1])[0] if weights else "—"
    kr_data = crypto.get(kr_symbol, {}) if isinstance(crypto, dict) else {}
    kr_value = f'{weights.get(kr_symbol, 0):.1f}% weight' if kr_symbol != "—" else "Awaiting Sheet"

    evo_sorted = sorted(evo_positions or [], key=lambda p: p.get("value", 0), reverse=True)
    rrsp = evo_sorted[0] if evo_sorted else {"symbol": "—", "value": 0, "change": None}
    alp_positions = (alpaca.get("tier1_positions", []) + alpaca.get("tier2_positions", [])) if alpaca else []
    alp_sorted = sorted(alp_positions, key=lambda p: p.get("market_value", 0), reverse=True)
    bot = alp_sorted[0] if alp_sorted else {"symbol": "Cash", "market_value": alpaca.get("cash", 0) if alpaca else 0, "day_change": None}

    accounts = tracker_model.get("accounts", {}) if tracker_model else {}
    ws_hist = accounts.get("tfsa_ws", {})
    kr_hist = accounts.get("kraken", {})
    cards = "".join([
        _account_card("WS TFSA", "#ffd21f", ws_symbol, f"C${(ws_data.get('close_price') or ws_data.get('price') or 0):,.2f} close", ws_data.get("close_change"), _period(ws_hist.get("series"), "mtd"), _period(ws_hist.get("series"), "ytd")),
        _account_card("Kraken", "#42d8ff", kr_symbol, kr_value, kr_data.get("change"), _period(kr_hist.get("series"), "mtd"), _period(kr_hist.get("series"), "ytd")),
        _account_card("RRSP", "#b59662", rrsp.get("symbol", "—"), f"US${rrsp.get('value', 0):,.0f}", rrsp.get("change"), metrics_only=True),
        _account_card("Novairecito", "#9c7cff", bot.get("symbol", "Cash"), f"US${bot.get('market_value', 0):,.0f}", bot.get("day_change"), metrics_only=True),
    ])

    market = _pick(zh_news, MARKET_TERMS)
    if not any(term in str(market.get("title", "")).lower() for term in MARKET_TERMS):
        market = {"title": "Market-close report pending the 4:15 PM ET scan", "url": "#"}
    geopolitical = _pick(zh_news, GEO_TERMS, {market.get("url")})
    movers = []
    for h in holdings or []:
        data = portfolio_data.get(h["ticker"], {})
        move = data.get("close_change")
        if move is None or abs(move) < 5:
            continue
        cat = catalysts.get(h["ticker"]) if catalysts else None
        if isinstance(cat, list): cat = cat[0] if cat else None
        if not isinstance(cat, dict): cat = None
        reason = str(cat.get("title") or "No verified same-day company catalyst found; sector flow or liquidity may be driving the move.") if cat else "No verified same-day company catalyst found; sector flow or liquidity may be driving the move."
        link = cat.get("url", "#") if cat else "#"
        movers.append(f'<a class="mover" href="{escape(link)}"><span><b>{escape(h.get("display", h["ticker"]))}</b><small>{escape(reason)}</small></span><strong class="{"up" if move >= 0 else "down"}">{_pct(move)}</strong></a>')
    movers_html = "".join(movers) or '<div class="quiet">No portfolio position moved ±5% at the latest close.</div>'

    asof = tracker_model.get("market_date") or generated_at.strftime("%Y-%m-%d")
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Daily · Novaire Signal</title>
<style>:root{{--bg:#09090d;--panel:#101016;--line:#24242e;--text:#eeeaf2;--dim:#8c879c;--gold:#d8b66c;--green:#38d6ad;--red:#ff6072}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 50% -20%,#22202b 0,#09090d 43%);color:var(--text);font-family:Inter,system-ui,sans-serif}}main{{width:min(1120px,calc(100% - 28px));margin:auto;padding:24px 0 72px}}nav{{display:flex;gap:8px;margin-bottom:28px}}nav a{{padding:8px 14px;border:1px solid var(--line);border-radius:999px;color:var(--dim);text-decoration:none;font-size:.72rem;text-transform:uppercase;letter-spacing:.12em}}nav a.active{{color:#09090d;background:var(--gold);border-color:var(--gold)}}h1{{font:500 clamp(2.4rem,7vw,5.8rem)/.9 Georgia,serif;margin:0;color:#f5e8cd}}.sub{{color:var(--dim);margin:10px 0 24px;font-size:.78rem}}.accounts{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.account,.story,.movers{{background:linear-gradient(155deg,rgba(255,255,255,.045),rgba(255,255,255,.012));border:1px solid var(--line);border-radius:16px;padding:16px;box-shadow:inset 0 1px rgba(255,255,255,.03)}}.account{{border-top:2px solid var(--accent)}}.account-kicker{{font-size:.6rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}}.account-symbol{{font:500 2rem/1 Georgia,serif;margin:12px 0 4px}}.account-lead,.quiet{{color:var(--dim);font-size:.68rem}}.account-value{{margin:14px 0 8px;font-size:.9rem}}.account-metrics{{display:flex;gap:10px;flex-wrap:wrap;font-size:.58rem;color:var(--dim)}}.account-metrics b{{display:block;color:var(--text);font-size:.74rem;margin-top:2px}}.up{{color:var(--green)!important}}.down{{color:var(--red)!important}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}}.story label,.section-label{{display:block;color:var(--gold);font-size:.57rem;letter-spacing:.16em;text-transform:uppercase;margin-bottom:9px}}.story a{{color:var(--text);font:500 1.2rem/1.2 Georgia,serif;text-decoration:none}}.story a:hover,.mover:hover{{color:var(--gold)}}.movers{{margin-top:10px}}.mover{{display:flex;justify-content:space-between;gap:16px;padding:11px 0;border-top:1px solid var(--line);color:var(--text);text-decoration:none}}.mover:first-of-type{{border-top:0}}.mover small{{display:block;color:var(--dim);font-size:.66rem;margin-top:3px}}@media(max-width:780px){{.accounts{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}}}@media(max-width:440px){{.accounts{{grid-template-columns:1fr}}}}</style></head><body><main>
<nav><a href="/portfolio/">Portfolio</a><a class="active" href="/portfolio/daily/">Daily</a></nav><h1>The Daily.</h1><div class="sub">Close-to-close · {escape(asof)} · refreshed {generated_at.strftime('%H:%M')}</div>
<section class="accounts">{cards}</section><section class="grid"><article class="story"><label>Market mover · ZeroHedge</label><a href="{escape(market.get('url','#'))}">{escape(market.get('title',''))}</a></article><article class="story"><label>Geopolitical pressure</label><a href="{escape(geopolitical.get('url','#'))}">{escape(geopolitical.get('title',''))}</a></article></section>
<section class="movers"><div class="section-label">Portfolio moves · ±5%</div>{movers_html}</section></main></body></html>'''


def write_daily(path, **kwargs):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(render_daily_html(**kwargs), encoding="utf-8")
