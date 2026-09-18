"""Render Novaire Signal's concise portfolio Daily snapshot."""
from __future__ import annotations
from datetime import date, datetime
from html import escape
from pathlib import Path

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


def _for_market_date(data, market_date):
    """Reject stale completed bars instead of relabeling them as the report date."""
    if data and data.get("completed_market_date") not in (None, market_date):
        return {}
    return data or {}


def _completed_account_delta(account_history, market_date, *, value_key="cad", multiplier=1.0):
    """Return the latest whole-account close delta only when it matches the Daily date."""
    points = [
        point for point in (account_history or {}).get("series", [])
        if point.get("market_date") and isinstance(point.get(value_key), (int, float))
    ]
    if len(points) < 2 or points[-1]["market_date"] != market_date:
        return None
    return (float(points[-1][value_key]) - float(points[-2][value_key])) * multiplier


def _intraday_account_swing(points):
    """Range of synchronized whole-account valuations; never sum position ranges."""
    values = [float(point["cad"]) for point in points or [] if isinstance(point.get("cad"), (int, float))]
    return max(values) - min(values) if len(values) >= 2 else None


def _account_card(account, net_worth_previous_cad):
    daily = account.get("change_pct")
    impact_cad = account.get("impact_cad")
    account_previous = (account.get("value_cad") or 0) - (impact_cad or 0)
    portfolio_impact = impact_cad / account_previous * 100 if impact_cad is not None and account_previous else None
    net_impact = impact_cad / net_worth_previous_cad * 100 if impact_cad is not None and net_worth_previous_cad else None
    cls = "up" if (impact_cad or 0) >= 0 else "down"
    daily_cls = "up" if (daily or 0) >= 0 else "down"
    high = _price(account.get("high"), account.get("price_currency", "C$"))
    low = _price(account.get("low"), account.get("price_currency", "C$"))
    range_money = _money(account.get("range_cad"), "C$", 0)
    effect_note = account.get("effect_note") or "Whole-account close to close"
    swing_note = account.get("swing_note") or "Full-account synchronized series unavailable"
    mtd_ytd = ""
    if account.get("mtd") is not None or account.get("ytd") is not None:
        mtd_ytd = f'<div class="periods"><span>MTD <b>{_pct(account.get("mtd"))}</b></span><span>YTD <b>{_pct(account.get("ytd"))}</b></span></div>'
    return f'''<details class="account" style="--accent:{account["accent"]}">
      <summary><span class="account-kicker">{escape(account["label"])}</span><strong class="account-value">{escape(account["value_label"])}</strong><span class="chevron" aria-hidden="true"></span></summary>
      <div class="account-detail"><div class="source">{escape(account.get("source", ""))}</div>
      <div class="position"><div class="position-name"><small>LARGEST POSITION</small><div class="symbol">{escape(account["symbol"])}</div><div class="lead">{account.get("weight_pct", 0):.1f}% of portfolio</div></div><div class="position-move"><small>DAILY POSITION MOVE</small><div class="daily {daily_cls}">{_pct(daily)}</div></div></div>
      <div class="quote-grid"><div><small>DAY HIGH</small><b>{high}</b></div><div><small>DAY LOW</small><b>{low}</b></div></div>
      <div class="impact-grid"><div><small>PORTFOLIO DAILY EFFECT</small><b class="{cls}">{_money(impact_cad, "C$", 0)}</b><span class="metric-sub">{escape(effect_note)}</span><span class="metric-sub {cls}">{_pct(portfolio_impact, 2)} of portfolio</span></div><div><small>INTRADAY SWING</small><b>{range_money}</b><span class="metric-sub">{escape(swing_note)}</span></div><div><small>NET WORTH EFFECT</small><b class="{cls}">{_pct(net_impact, 2)}</b><span class="metric-sub">of tracked net worth</span></div></div>{mtd_ytd}
      </div>
    </details>'''


def render_daily_html(*, portfolio_data, holdings, tracker_model, kraken_meta, crypto, rrsp_meta, rrsp_quotes, alpaca, gs_meta=None, fx=None, zh_news=None, catalysts=None, generated_at=None, account_intraday=None):
    generated_at = generated_at or datetime.now().astimezone()
    fx = fx or {"usdcad": 1.365}
    usdcad = float(fx.get("usdcad") or 1.365)
    accounts_history = tracker_model.get("accounts", {}) if tracker_model else {}
    daily_accounts = tracker_model.get("daily_accounts", accounts_history) if tracker_model else {}
    market_date = tracker_model.get("market_date") or generated_at.strftime("%Y-%m-%d")
    account_intraday = account_intraday or {}

    by_value = sorted(holdings or [], key=lambda h: portfolio_data.get(h["ticker"], {}).get("value") or 0, reverse=True)
    ws = by_value[0] if by_value else {"ticker": "—", "display": "—", "shares": 0, "currency": "CAD"}
    ws_raw = portfolio_data.get(ws.get("ticker"), {})
    ws_data = _for_market_date(ws_raw, market_date)
    ws_total_cad = float((gs_meta or {}).get("total_cad") or accounts_history.get("tfsa_ws", {}).get("current_cad") or 0)
    ws_value_cad = float(ws_raw.get("value") or 0) * usdcad
    ws_impact = _completed_account_delta(daily_accounts.get("tfsa_ws"), market_date)
    ws_multiplier = usdcad if ws.get("currency") == "USD" else (usdcad * float(fx.get("audusd") or .63) if ws.get("currency") == "AUD" else 1.0)

    weight_rows = kraken_meta.get("position_weights_pct", []) if isinstance(kraken_meta, dict) else []
    weights = {str(symbol): float(weight) for symbol, weight in weight_rows}
    kr_symbol = max(weights.items(), key=lambda item: item[1])[0] if weights else "—"
    kr_data = crypto.get(kr_symbol, {}) if isinstance(crypto, dict) else {}
    kr_total_usd = float(kraken_meta.get("total_usd") or accounts_history.get("kraken", {}).get("current_usd") or 0)
    kr_position_usd = kr_total_usd * weights.get(kr_symbol, 0) / 100
    kr_impact_usd = _completed_account_delta(daily_accounts.get("kraken"), market_date, value_key="usd")
    kr_units = kr_position_usd / kr_data["price"] if kr_data.get("price") else 0

    rrsp_positions = rrsp_meta.get("positions", []) if isinstance(rrsp_meta, dict) else []
    rrsp = rrsp_positions[0] if rrsp_positions else {"symbol": "—", "weight_pct": 0, "value_cad": 0, "shares": 0, "currency": "CAD"}
    rr_quote = _for_market_date(rrsp_quotes.get(rrsp.get("symbol"), {}) if isinstance(rrsp_quotes, dict) else {}, market_date)
    rr_impact = None
    rr_multiplier = usdcad if rrsp.get("currency") == "USD" else 1.0

    alp_positions = (alpaca.get("tier1_positions", []) + alpaca.get("tier2_positions", [])) if alpaca else []
    bot = max(alp_positions, key=lambda p: p.get("market_value", 0)) if alp_positions else {"symbol": "Cash", "market_value": 0, "day_change": None}
    bot_total_usd = float((alpaca or {}).get("equity") or (alpaca or {}).get("cash") or 0)
    bot_last_equity = (alpaca or {}).get("last_equity")
    bot_impact_usd = bot_total_usd - float(bot_last_equity) if isinstance(bot_last_equity, (int, float)) else None

    models = [
        {"label": "WS TFSA", "accent": "#ffd21f", "symbol": ws.get("display") or ws.get("ticker", "—").split(".")[0], "value_cad": ws_total_cad, "value_label": f"C${ws_total_cad:,.0f}", "weight_pct": ws_value_cad / ws_total_cad * 100 if ws_total_cad else 0, "change_pct": ws_data.get("close_change"), "impact_cad": ws_impact, "high": ws_data.get("day_high"), "low": ws_data.get("day_low"), "price_currency": "US$" if ws.get("currency") == "USD" else ("A$" if ws.get("currency") == "AUD" else "C$"), "range_cad": _intraday_account_swing(account_intraday.get("tfsa_ws")), "effect_note": "Whole account close to close · cash flows unavailable", "swing_note": "Synchronized full-account valuations" if account_intraday.get("tfsa_ws") else None, "mtd": _period(accounts_history.get("tfsa_ws", {}).get("series"), "mtd"), "ytd": _period(accounts_history.get("tfsa_ws", {}).get("series"), "ytd"), "source": "Google Sheet · TFSA/WS"},
        {"label": "Kraken", "accent": "#42d8ff", "symbol": kr_symbol, "value_cad": kr_total_usd * usdcad, "value_label": f"US${kr_total_usd:,.0f} · C${kr_total_usd * usdcad:,.0f}", "weight_pct": weights.get(kr_symbol, 0), "change_pct": kr_data.get("change"), "impact_cad": kr_impact_usd * usdcad if kr_impact_usd is not None else None, "high": kr_data.get("day_high"), "low": kr_data.get("day_low"), "price_currency": "US$", "range_cad": _intraday_account_swing(account_intraday.get("kraken")), "effect_note": "Whole account close to close · cash flows unavailable", "swing_note": "Synchronized full-account valuations" if account_intraday.get("kraken") else None, "mtd": _period(accounts_history.get("kraken", {}).get("series"), "mtd"), "ytd": _period(accounts_history.get("kraken", {}).get("series"), "ytd"), "source": "Google Sheet · Kraken"},
        {"label": "RRSP", "accent": "#b59662", "symbol": rrsp.get("symbol", "—"), "value_cad": float(rrsp_meta.get("total_cad") or 0), "value_label": f"C${float(rrsp_meta.get('total_cad') or 0):,.0f}", "weight_pct": float(rrsp.get("weight_pct") or 0), "change_pct": rr_quote.get("close_change"), "impact_cad": rr_impact, "high": rr_quote.get("day_high"), "low": rr_quote.get("day_low"), "price_currency": "US$" if rrsp.get("currency") == "USD" else "C$", "range_cad": _intraday_account_swing(account_intraday.get("rrsp")), "effect_note": "Whole-account close history unavailable", "swing_note": "Synchronized full-account valuations" if account_intraday.get("rrsp") else None, "source": "Google Sheet · RRSP"},
        {"label": "Novairecito", "accent": "#9c7cff", "symbol": bot.get("symbol", "Cash"), "value_cad": bot_total_usd * usdcad, "value_label": f"US${bot_total_usd:,.0f} · C${bot_total_usd * usdcad:,.0f}", "weight_pct": float(bot.get("portfolio_weight") or (100 if bot.get("symbol") == "Cash" and bot_total_usd else 0)), "change_pct": bot.get("day_change"), "impact_cad": bot_impact_usd * usdcad if bot_impact_usd is not None else None, "high": bot.get("day_high"), "low": bot.get("day_low"), "price_currency": "US$", "range_cad": _intraday_account_swing(account_intraday.get("novairecito")), "effect_note": "Broker whole-account close to close · cash flows unavailable", "swing_note": "Synchronized full-account valuations" if account_intraday.get("novairecito") else None, "source": "Alpaca · live book"},
    ]
    net_worth_cad = sum(model["value_cad"] for model in models)
    net_worth_previous_cad = net_worth_cad - sum(model.get("impact_cad") or 0 for model in models)
    cards = "".join(_account_card(model, net_worth_previous_cad) for model in models)

    geopolitical = _pick(zh_news, GEO_TERMS)
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
    asof = market_date
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Daily · Novaire Signal</title>
<link rel="icon" type="image/svg+xml" href="/portfolio/favicon.svg?v=2"><link rel="apple-touch-icon" href="/portfolio/apple-touch-icon.png?v=2">
<style>:root{{--bg:#09090d;--panel:#101016;--line:#24242e;--text:#eeeaf2;--dim:#8c879c;--gold:#d8b66c;--brand-gold:#b59662;--green:#38d6ad;--red:#ff6072}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 50% -20%,#22202b 0,#09090d 43%);color:var(--text);font-family:Inter,system-ui,sans-serif}}main{{width:min(1180px,calc(100% - 28px));margin:auto;padding:18px 0 72px}}nav{{display:flex;gap:8px;margin-bottom:18px}}nav a{{padding:7px 12px;border:1px solid var(--line);border-radius:999px;color:var(--dim);text-decoration:none;font-size:.66rem;text-transform:uppercase;letter-spacing:.12em}}nav a.active{{color:#09090d;background:var(--gold);border-color:var(--gold)}}.daily-header{{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:10px}}h1{{font:500 clamp(1.25rem,2.2vw,1.65rem)/1 Georgia,serif;margin:0;color:#f5e8cd;letter-spacing:-.015em}}.signal-brand-row{{display:inline-flex;align-items:center;justify-content:center;gap:12px;white-space:nowrap;font:500 1.05rem/1 Georgia,serif}}.signal-wordmark{{color:var(--text);font-style:normal;letter-spacing:.18em;margin-right:-.18em;text-decoration:none}}.signal-wordmark span{{color:var(--brand-gold);font-style:italic}}.signal-map,.signal-bolt{{display:inline-flex;align-items:center;width:1.243em;height:1.155em;color:var(--brand-gold);text-decoration:none;line-height:1}}.signal-map{{justify-content:flex-end}}.signal-bolt{{justify-content:flex-start}}.signal-map-icon{{width:1.243em;height:1.155em;display:block}}.signal-map-ocean{{fill:#0a0a0c}}.signal-map-land{{fill:#b59662}}.signal-map-rim{{fill:none;stroke:#b59662;stroke-width:.8}}.signal-bolt-icon{{width:.738em;height:.945em;display:block;fill:currentColor;transform:translateY(.088em)}}.signal-map:focus-visible,.signal-bolt:focus-visible,.signal-wordmark:focus-visible{{outline:1px solid var(--brand-gold);outline-offset:3px;border-radius:2px}}.sub{{color:var(--dim);margin:7px 0 16px;font-size:.7rem}}.accounts{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-items:start}}.account,.story,.mover{{min-width:0;background:linear-gradient(155deg,rgba(255,255,255,.045),rgba(255,255,255,.012));border:1px solid var(--line);border-radius:12px;box-shadow:inset 0 1px rgba(255,255,255,.03)}}.account{{border-top:2px solid var(--accent);overflow:hidden}}summary{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,auto) 14px;align-items:center;gap:12px;min-height:45px;padding:13px 15px;cursor:pointer;list-style:none}}summary::-webkit-details-marker{{display:none}}summary:focus-visible{{outline:1px solid var(--accent);outline-offset:-2px;border-radius:10px}}.account-kicker{{min-width:0;font-size:.61rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}}.account-value{{min-width:0;max-width:100%;font:500 clamp(.78rem,1.3vw,1rem)/1.15 Georgia,serif;color:var(--text);white-space:normal;text-align:right;overflow-wrap:anywhere}}.chevron{{width:7px;height:7px;border-right:1px solid var(--dim);border-bottom:1px solid var(--dim);transform:rotate(45deg) translateY(-2px);transition:transform .18s ease}}details[open] .chevron{{transform:rotate(225deg) translate(-2px,-1px)}}.account-detail{{border-top:1px solid var(--line);padding:13px 15px 15px}}.source{{padding-bottom:11px;color:var(--dim);font-size:.56rem;letter-spacing:.06em;text-align:right;overflow-wrap:anywhere}}.position{{display:grid;grid-template-columns:minmax(0,1fr) minmax(105px,.55fr);align-items:end;gap:16px}}.position-name,.position-move{{min-width:0}}.position-move{{padding-left:14px;border-left:1px solid var(--line);text-align:right}}.source,.lead,.quiet,.metric-sub{{color:var(--dim)}}.lead{{font-size:.61rem}}.symbol{{font:500 1.75rem/1 Georgia,serif;margin-top:4px}}.daily{{font-size:1rem;font-weight:750;margin-top:7px;overflow-wrap:anywhere}}.quote-grid,.impact-grid{{display:grid;gap:7px;margin-top:11px}}.quote-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.impact-grid{{grid-template-columns:repeat(3,minmax(0,1fr))}}.quote-grid>div,.impact-grid>div{{min-width:0;background:rgba(0,0,0,.18);border:1px solid var(--line);border-radius:10px;padding:10px}}small{{display:block;color:var(--dim);font-size:.51rem;line-height:1.25;letter-spacing:.08em;margin-bottom:5px}}.quote-grid b,.impact-grid b{{display:block;font-size:clamp(.66rem,1vw,.78rem);line-height:1.25;overflow-wrap:anywhere}}.metric-sub{{display:block;margin-top:4px;font-size:.53rem;line-height:1.25}}.periods{{display:flex;gap:16px;margin-top:11px;color:var(--dim);font-size:.58rem}}.periods b{{color:var(--text);margin-left:4px}}.up{{color:var(--green)!important}}.down{{color:var(--red)!important}}.grid{{display:grid;grid-template-columns:1fr;gap:10px;margin-top:12px}}.story{{padding:12px 14px}}.story label,.section-label{{display:block;color:var(--gold);font-size:.57rem;letter-spacing:.16em;text-transform:uppercase;margin-bottom:9px}}.story a{{color:var(--text);font:500 1.2rem/1.2 Georgia,serif;text-decoration:none}}.movers{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}}.section-label{{grid-column:1/-1;margin:0 0 1px}}.mover{{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:11px 12px;color:var(--text);text-decoration:none}}.mover span{{min-width:0}}.mover strong{{flex:0 0 auto}}.mover small{{margin-top:3px;letter-spacing:0;overflow-wrap:anywhere}}.quiet{{grid-column:1/-1;padding:8px 0}}@media(max-width:760px){{.accounts,.movers{{grid-template-columns:1fr}}.daily-header{{align-items:flex-start;gap:10px}}h1{{font-size:1.15rem;margin-top:2px}}.signal-brand-row{{font-size:.78rem;gap:8px}}}}@media(max-width:430px){{main{{width:min(100% - 20px,1180px)}}summary{{gap:8px;padding:12px}}.account-detail{{padding:12px}}.position{{grid-template-columns:minmax(0,1fr) minmax(92px,.52fr);gap:10px}}.position-move{{padding-left:10px}}.impact-grid{{grid-template-columns:1fr}}.quote-grid{{gap:6px}}}}</style></head><body><main>
<header class="daily-header"><h1>The Daily.</h1><div class="signal-brand-row" aria-label="Novaire Signal navigation"><a href="/flaneur" class="signal-map" title="Flâneur happenings" aria-label="Flâneur happenings"><svg class="signal-map-icon" viewBox=".85 .85 22.3 22.3" aria-hidden="true" focusable="false"><circle class="signal-map-ocean" cx="12" cy="12" r="10.25"/><g class="signal-map-land"><path d="M3.08 8.67 4.2 6.43l1.7-1.67 2.29-1.34 2.03-.68 1.02.42-.43.88-1.61.44-.56.9-1.02.18-.42 1.18-1.12.16-.35 1.2.7 1.14 1.47.49.63.9-.16 1.14-1.02.66-.34 1.14-1.1-.04-.55-1.02-1.28-.5-.7-1.45-1.05-.81-.49-1.07Z"/><path d="m9.12 13.04 1.05-.52 1.39.33.91 1.06-.17 1.36-.78 1.15-.22 1.6-.83 1.13-.31 1.7-.67.69-.73-1.43-.54-1.78-.1-1.47-.67-1.18.58-1.08.2-.86Z"/><path d="m12.45 2.06 1.29-.23 1.06.38-.24.73-1.23.41-.88-.38Z"/><path d="m13.42 5.04 1.08-.83 2.25-.47 2.03.75 1.39 1.23.65 1.17-.63.74-1.46-.27-.83.48-1.18-.53-.93.5-1.05-.31-.86-.98-.98-.17-.43-.65Z"/><path d="m14.26 8.23 1.18-.39 1.24.44.82 1.08-.13 1.56-.72 1.14-.36 1.88-.98 1.77-.9.65-.7-1.03-.23-1.66-.78-1.22.25-1.54-.37-1.2.41-1.04Z"/><path d="m17.57 16.51 1.24-.55 1.28.28.76.82-.24 1.12-1.12.64-1.3-.17-.75-.83Z"/></g><circle class="signal-map-rim" cx="12" cy="12" r="10.25"/></svg></a><a href="/" class="signal-wordmark" aria-label="Novaire Signal home">Novaire <span>Signal</span></a><a href="/portfolio/" class="signal-bolt" title="Portfolio" aria-label="Portfolio"><svg class="signal-bolt-icon" viewBox="45 38 200 264" aria-hidden="true" focusable="false"><path fill="currentColor" d="M219 44Q217 43 215 44L51 180Q49 183 51 185Q53 187 56 187L130 186Q132 186 132 188L72 289Q70 293 73 295Q76 297 83 291L239 155Q241 153 239 149Q238 147 236 147L166 148Q162 148 160 146L219 51Q222 46 219 44Z"/></svg></a></div></header><nav aria-label="Daily section"><a href="/portfolio/">Portfolio</a><a class="active" href="/portfolio/daily/" aria-current="page">Daily</a></nav><div class="sub">Close-to-close · {escape(asof)} · C${net_worth_cad:,.0f} tracked net worth · refreshed {generated_at.strftime('%H:%M')}</div>
<section class="accounts">{cards}</section><section class="grid"><article class="story"><label>Geopolitical pressure</label><a href="{escape(geopolitical.get('url','#'))}">{escape(geopolitical.get('title',''))}</a></article></section>
<section class="movers"><div class="section-label">Portfolio moves · ±5%</div>{movers_html}</section></main></body></html>'''


def write_daily(path, **kwargs):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(render_daily_html(**kwargs), encoding="utf-8")
