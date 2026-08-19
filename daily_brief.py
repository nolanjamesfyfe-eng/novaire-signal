"""Render Novaire Signal's concise portfolio Daily snapshot."""
from __future__ import annotations
from datetime import date, datetime
from html import escape
from pathlib import Path

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
    baseline = next((p for p in valid if date.fromisoformat(p["market_date"]).year == latest_date.year and (mode == "ytd" or date.fromisoformat(p["market_date"]).month == latest_date.month)), None)
    key = "usd" if isinstance(latest.get("usd"), (int, float)) else "cad"
    if not baseline or not isinstance(baseline.get(key), (int, float)) or not baseline[key]:
        return None
    return (latest[key] / baseline[key] - 1) * 100


def _pct(value, digits=1):
    if value is None:
        return "—"
    return f"{'+' if value >= 0 else ''}{value:.{digits}f}%"


def _money(value, currency="C$", decimals=0):
    if value is None:
        return "—"
    sign = "+" if value > 0 else ("−" if value < 0 else "")
    return f"{sign}{currency}{abs(value):,.{decimals}f}"


def _price(value, currency="C$"):
    return "—" if value is None else f"{currency}{value:,.2f}"


def _daily_delta(current_value, change_pct):
    if not isinstance(current_value, (int, float)) or not isinstance(change_pct, (int, float)) or change_pct <= -100:
        return None
    return current_value - current_value / (1 + change_pct / 100)


def _range_value(high, low, units, multiplier=1.0):
    if not isinstance(high, (int, float)) or not isinstance(low, (int, float)):
        return None
    return (high - low) * float(units or 0) * multiplier


def _account_card(account, net_worth_previous_cad):
    daily = account.get("change_pct")
    impact_cad = account.get("impact_cad")
    account_previous = (account.get("value_cad") or 0) - (impact_cad or 0)
    portfolio_impact = impact_cad / account_previous * 100 if impact_cad is not None and account_previous else None
    net_impact = impact_cad / net_worth_previous_cad * 100 if impact_cad is not None and net_worth_previous_cad else None
    cls = "up" if (daily or 0) >= 0 else "down"
    high = _price(account.get("high"), account.get("price_currency", "C$"))
    low = _price(account.get("low"), account.get("price_currency", "C$"))
    range_money = _money(account.get("range_cad"), "C$", 0)
    mtd_ytd = ""
    if account.get("mtd") is not None or account.get("ytd") is not None:
        mtd_ytd = f'<div class="periods"><span>MTD <b>{_pct(account.get("mtd"))}</b></span><span>YTD <b>{_pct(account.get("ytd"))}</b></span></div>'
    return f'''<details class="account" style="--accent:{account["accent"]}">
      <summary><span class="account-kicker">{escape(account["label"])}</span><strong class="account-value">{escape(account["value_label"])}</strong><span class="chevron" aria-hidden="true"></span></summary>
      <div class="account-detail"><div class="source">{escape(account.get("source", ""))}</div>
      <div class="position"><div><div class="symbol">{escape(account["symbol"])}</div><div class="lead">Largest · {account.get("weight_pct", 0):.1f}% of portfolio</div></div><div class="daily {cls}">{_pct(daily)}</div></div>
      <div class="quote-grid"><div><small>DAY HIGH</small><b>{high}</b></div><div><small>DAY LOW</small><b>{low}</b></div></div>
      <div class="impact-grid"><div><small>DAILY IMPACT</small><b class="{cls}">{_money(impact_cad, "C$", 0)} · {_pct(portfolio_impact, 2)}</b></div><div><small>NET WORTH IMPACT</small><b class="{cls}">{_pct(net_impact, 2)}</b></div><div><small>HIGH–LOW SWING</small><b>{range_money}</b></div></div>{mtd_ytd}
      </div>
    </details>'''


def render_daily_html(*, portfolio_data, holdings, tracker_model, kraken_meta, crypto, rrsp_meta, rrsp_quotes, alpaca, gs_meta=None, fx=None, zh_news=None, catalysts=None, generated_at=None):
    generated_at = generated_at or datetime.now().astimezone()
    fx = fx or {"usdcad": 1.365}
    usdcad = float(fx.get("usdcad") or 1.365)
    accounts_history = tracker_model.get("accounts", {}) if tracker_model else {}

    by_value = sorted(holdings or [], key=lambda h: portfolio_data.get(h["ticker"], {}).get("value") or 0, reverse=True)
    ws = by_value[0] if by_value else {"ticker": "—", "display": "—", "shares": 0, "currency": "CAD"}
    ws_data = portfolio_data.get(ws.get("ticker"), {})
    ws_total_cad = float((gs_meta or {}).get("total_cad") or accounts_history.get("tfsa_ws", {}).get("current_cad") or 0)
    ws_value_cad = float(ws_data.get("value") or 0) * usdcad
    ws_impact = _daily_delta(ws_value_cad, ws_data.get("close_change"))
    ws_multiplier = usdcad if ws.get("currency") == "USD" else (usdcad * float(fx.get("audusd") or .63) if ws.get("currency") == "AUD" else 1.0)

    weight_rows = kraken_meta.get("position_weights_pct", []) if isinstance(kraken_meta, dict) else []
    weights = {str(symbol): float(weight) for symbol, weight in weight_rows}
    kr_symbol = max(weights.items(), key=lambda item: item[1])[0] if weights else "—"
    kr_data = crypto.get(kr_symbol, {}) if isinstance(crypto, dict) else {}
    kr_total_usd = float(kraken_meta.get("total_usd") or accounts_history.get("kraken", {}).get("current_usd") or 0)
    kr_position_usd = kr_total_usd * weights.get(kr_symbol, 0) / 100
    kr_impact_usd = _daily_delta(kr_position_usd, kr_data.get("change"))
    kr_units = kr_position_usd / kr_data["price"] if kr_data.get("price") else 0

    rrsp_positions = rrsp_meta.get("positions", []) if isinstance(rrsp_meta, dict) else []
    rrsp = rrsp_positions[0] if rrsp_positions else {"symbol": "—", "weight_pct": 0, "value_cad": 0, "shares": 0, "currency": "CAD"}
    rr_quote = rrsp_quotes.get(rrsp.get("symbol"), {}) if isinstance(rrsp_quotes, dict) else {}
    rr_impact = _daily_delta(rrsp.get("value_cad"), rr_quote.get("close_change"))
    rr_multiplier = usdcad if rrsp.get("currency") == "USD" else 1.0

    alp_positions = (alpaca.get("tier1_positions", []) + alpaca.get("tier2_positions", [])) if alpaca else []
    bot = max(alp_positions, key=lambda p: p.get("market_value", 0)) if alp_positions else {"symbol": "Cash", "market_value": 0, "day_change": None}
    bot_total_usd = float((alpaca or {}).get("equity") or (alpaca or {}).get("cash") or 0)
    bot_impact_usd = _daily_delta(float(bot.get("market_value") or 0), bot.get("day_change"))

    models = [
        {"label": "WS TFSA", "accent": "#ffd21f", "symbol": ws.get("display") or ws.get("ticker", "—").split(".")[0], "value_cad": ws_total_cad, "value_label": f"C${ws_total_cad:,.0f}", "weight_pct": ws_value_cad / ws_total_cad * 100 if ws_total_cad else 0, "change_pct": ws_data.get("close_change"), "impact_cad": ws_impact, "high": ws_data.get("day_high"), "low": ws_data.get("day_low"), "price_currency": "US$" if ws.get("currency") == "USD" else ("A$" if ws.get("currency") == "AUD" else "C$"), "range_cad": _range_value(ws_data.get("day_high"), ws_data.get("day_low"), ws.get("shares"), ws_multiplier), "mtd": _period(accounts_history.get("tfsa_ws", {}).get("series"), "mtd"), "ytd": _period(accounts_history.get("tfsa_ws", {}).get("series"), "ytd"), "source": "Google Sheet · TFSA/WS"},
        {"label": "Kraken", "accent": "#42d8ff", "symbol": kr_symbol, "value_cad": kr_total_usd * usdcad, "value_label": f"US${kr_total_usd:,.0f} · C${kr_total_usd * usdcad:,.0f}", "weight_pct": weights.get(kr_symbol, 0), "change_pct": kr_data.get("change"), "impact_cad": kr_impact_usd * usdcad if kr_impact_usd is not None else None, "high": kr_data.get("day_high"), "low": kr_data.get("day_low"), "price_currency": "US$", "range_cad": (kr_data.get("day_high") - kr_data.get("day_low")) * kr_units * usdcad if isinstance(kr_data.get("day_high"), (int, float)) and isinstance(kr_data.get("day_low"), (int, float)) else None, "mtd": _period(accounts_history.get("kraken", {}).get("series"), "mtd"), "ytd": _period(accounts_history.get("kraken", {}).get("series"), "ytd"), "source": "Google Sheet · Kraken"},
        {"label": "RRSP", "accent": "#b59662", "symbol": rrsp.get("symbol", "—"), "value_cad": float(rrsp_meta.get("total_cad") or 0), "value_label": f"C${float(rrsp_meta.get('total_cad') or 0):,.0f}", "weight_pct": float(rrsp.get("weight_pct") or 0), "change_pct": rr_quote.get("close_change"), "impact_cad": rr_impact, "high": rr_quote.get("day_high"), "low": rr_quote.get("day_low"), "price_currency": "US$" if rrsp.get("currency") == "USD" else "C$", "range_cad": _range_value(rr_quote.get("day_high"), rr_quote.get("day_low"), rrsp.get("shares"), rr_multiplier), "source": "Google Sheet · RRSP"},
        {"label": "Novairecito", "accent": "#9c7cff", "symbol": bot.get("symbol", "Cash"), "value_cad": bot_total_usd * usdcad, "value_label": f"US${bot_total_usd:,.0f} · C${bot_total_usd * usdcad:,.0f}", "weight_pct": float(bot.get("portfolio_weight") or (100 if bot.get("symbol") == "Cash" and bot_total_usd else 0)), "change_pct": bot.get("day_change"), "impact_cad": bot_impact_usd * usdcad if bot_impact_usd is not None else None, "high": bot.get("day_high"), "low": bot.get("day_low"), "price_currency": "US$", "range_cad": None, "source": "Alpaca · live book"},
    ]
    net_worth_cad = sum(model["value_cad"] for model in models)
    net_worth_previous_cad = net_worth_cad - sum(model.get("impact_cad") or 0 for model in models)
    cards = "".join(_account_card(model, net_worth_previous_cad) for model in models)

    market = _pick(zh_news, MARKET_TERMS)
    if not any(term in str(market.get("title", "")).lower() for term in MARKET_TERMS):
        market = {"title": "Market-close report pending the 4:15 PM ET scan", "url": "#"}
    geopolitical = _pick(zh_news, GEO_TERMS, {market.get("url")})
    movers = []
    for holding in holdings or []:
        data = portfolio_data.get(holding["ticker"], {})
        move = data.get("close_change")
        if move is None or abs(move) < 5:
            continue
        catalyst = (catalysts or {}).get(holding["ticker"])
        if isinstance(catalyst, list):
            catalyst = catalyst[0] if catalyst else None
        reason = str(catalyst.get("title") or "No verified same-day company catalyst found; sector flow or liquidity may be driving the move.") if isinstance(catalyst, dict) else "No verified same-day company catalyst found; sector flow or liquidity may be driving the move."
        link = catalyst.get("url", "#") if isinstance(catalyst, dict) else "#"
        movers.append(f'<a class="mover" href="{escape(link)}"><span><b>{escape(holding.get("display", holding["ticker"]))}</b><small>{escape(reason)}</small></span><strong class="{"up" if move >= 0 else "down"}">{_pct(move)}</strong></a>')
    movers_html = "".join(movers) or '<div class="quiet">No portfolio position moved ±5% at the latest close.</div>'
    asof = tracker_model.get("market_date") or generated_at.strftime("%Y-%m-%d")
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Daily · Novaire Signal</title>
<style>:root{{--bg:#09090d;--panel:#101016;--line:#24242e;--text:#eeeaf2;--dim:#8c879c;--gold:#d8b66c;--green:#38d6ad;--red:#ff6072}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 50% -20%,#22202b 0,#09090d 43%);color:var(--text);font-family:Inter,system-ui,sans-serif}}main{{width:min(1180px,calc(100% - 28px));margin:auto;padding:18px 0 72px}}nav{{display:flex;gap:8px;margin-bottom:18px}}nav a{{padding:7px 12px;border:1px solid var(--line);border-radius:999px;color:var(--dim);text-decoration:none;font-size:.66rem;text-transform:uppercase;letter-spacing:.12em}}nav a.active{{color:#09090d;background:var(--gold);border-color:var(--gold)}}h1{{font:500 clamp(2rem,4vw,3.7rem)/.92 Georgia,serif;margin:0;color:#f5e8cd;letter-spacing:-.025em}}.sub{{color:var(--dim);margin:7px 0 16px;font-size:.7rem}}.accounts{{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}}.account,.story,.movers{{background:linear-gradient(155deg,rgba(255,255,255,.045),rgba(255,255,255,.012));border:1px solid var(--line);border-radius:12px;box-shadow:inset 0 1px rgba(255,255,255,.03)}}.account{{border-top:2px solid var(--accent)}}summary{{display:grid;grid-template-columns:minmax(0,1fr) auto 14px;align-items:center;gap:12px;padding:13px 15px;cursor:pointer;list-style:none}}summary::-webkit-details-marker{{display:none}}summary:focus-visible{{outline:1px solid var(--accent);outline-offset:2px;border-radius:10px}}.account-kicker{{font-size:.61rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}}.account-value{{font:500 1rem/1.1 Georgia,serif;color:var(--text);white-space:nowrap}}.chevron{{width:7px;height:7px;border-right:1px solid var(--dim);border-bottom:1px solid var(--dim);transform:rotate(45deg) translateY(-2px);transition:transform .18s ease}}details[open] .chevron{{transform:rotate(225deg) translate(-2px,-1px)}}.account-detail{{position:relative;border-top:1px solid var(--line);padding:13px 15px 15px}}.position{{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}}.source{{position:absolute;top:14px;right:15px}}.source,.lead,.quiet{{color:var(--dim);font-size:.61rem}}.symbol{{font:500 1.75rem/1 Georgia,serif;margin-top:4px}}.daily{{font-size:1rem;font-weight:750;margin-top:7px}}.quote-grid,.impact-grid{{display:grid;gap:6px;margin-top:11px}}.quote-grid{{grid-template-columns:1fr 1fr}}.impact-grid{{grid-template-columns:1.25fr 1fr 1fr}}.quote-grid div,.impact-grid div{{background:rgba(0,0,0,.18);border:1px solid var(--line);border-radius:10px;padding:10px}}small{{display:block;color:var(--dim);font-size:.53rem;letter-spacing:.08em;margin-bottom:4px}}.quote-grid b,.impact-grid b{{font-size:.74rem}}.periods{{display:flex;gap:16px;margin-top:11px;color:var(--dim);font-size:.58rem}}.periods b{{color:var(--text);margin-left:4px}}.up{{color:var(--green)!important}}.down{{color:var(--red)!important}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}}.story label,.section-label{{display:block;color:var(--gold);font-size:.57rem;letter-spacing:.16em;text-transform:uppercase;margin-bottom:9px}}.story a{{color:var(--text);font:500 1.2rem/1.2 Georgia,serif;text-decoration:none}}.movers{{margin-top:10px}}.mover{{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--line);color:var(--text);text-decoration:none}}.mover:last-child{{border:0}}.mover small{{margin-top:3px;letter-spacing:0}}@media(max-width:760px){{.accounts,.grid{{grid-template-columns:1fr}}.impact-grid{{grid-template-columns:1fr 1fr}}}}</style></head><body><main>
<nav><a href="/portfolio/">Portfolio</a><a class="active" href="/portfolio/daily/">Daily</a></nav><h1>The Daily.</h1><div class="sub">Close-to-close · {escape(asof)} · C${net_worth_cad:,.0f} tracked net worth · refreshed {generated_at.strftime('%H:%M')}</div>
<section class="accounts">{cards}</section><section class="grid"><article class="story"><label>Market mover · ZeroHedge</label><a href="{escape(market.get('url','#'))}">{escape(market.get('title',''))}</a></article><article class="story"><label>Geopolitical pressure</label><a href="{escape(geopolitical.get('url','#'))}">{escape(geopolitical.get('title',''))}</a></article></section>
<section class="movers"><div class="section-label">Portfolio moves · ±5%</div>{movers_html}</section></main></body></html>'''


def write_daily(path, **kwargs):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(render_daily_html(**kwargs), encoding="utf-8")
