"""Google-Sheet-backed portfolio net-worth history and rendering."""

from __future__ import annotations

import csv
import io
import json
import math
from datetime import date, datetime, time as dt_time, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any

import requests

try:
    from zoneinfo import ZoneInfo
    NEW_YORK = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - Python always has zoneinfo in production
    NEW_YORK = timezone(timedelta(hours=-5))

SHEET_ID = "1rqRNI6z3rqXGCMlPbsbVEJUw82DCskU9qf9sKEXMnak"
TFSA_GID = "527699504"
KRAKEN_GID = "338118850"
RRSP_GID = "164741412"
HISTORY_PATH = Path(__file__).with_name("portfolio_history.json")
PERIODS = (("1D", 1), ("1W", 7), ("1M", 30), ("3M", 90), ("6M", 180), ("YTD", "ytd"), ("1Y", 365), ("ALL", "all"))


def parse_money(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text or text in {"—", "#N/A", "N/A"}:
        return None
    negative = text.startswith("-")
    text = text.lstrip("+-")
    try:
        amount = float(text)
    except (TypeError, ValueError):
        return None
    return -amount if negative else amount


def parse_kraken_rows(rows: list[list[str]]) -> dict[str, Any]:
    """Read Kraken equity from the row whose status is explicitly `Live`."""
    inception_usd = None
    inception_label = None
    position_weights = []
    for raw in rows:
        row = list(raw) + [""] * max(0, 15 - len(raw))
        symbol = row[3].strip().upper()
        weight_text = row[11].strip()
        try:
            weight = float(weight_text.replace("%", "").replace(",", ""))
        except (TypeError, ValueError):
            continue
        if symbol and weight > 0:
            position_weights.append((symbol, weight))
    for raw in rows:
        row = list(raw) + [""] * max(0, 15 - len(raw))
        if row[11].strip().casefold() == "inception":
            inception_usd = parse_money(row[10])
            inception_label = row[9].strip() or None
            break
    for raw in rows:
        row = list(raw) + [""] * max(0, 15 - len(raw))
        if row[11].strip().casefold() != "live":
            continue
        total_usd = parse_money(row[10])
        usdcad = parse_money(row[14])
        if total_usd is None or usdcad is None or usdcad <= 0:
            continue
        return {
            "account": "kraken",
            "label": "Kraken",
            "total_usd": total_usd,
            "total_cad": total_usd * usdcad,
            "usdcad": usdcad,
            "sheet_gid": KRAKEN_GID,
            "sheet_name": "What's Kraken 2025",
            "source": "Google Sheet · Live value of fund",
            "inception_usd": inception_usd,
            "inception_label": inception_label,
            "position_weights_pct": sorted(position_weights, key=lambda item: item[1], reverse=True),
            "position_weight_total_pct": round(sum(weight for _, weight in position_weights), 2),
        }
    return {}


def fetch_kraken_totals(timeout: int = 20) -> dict[str, Any]:
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={KRAKEN_GID}&_={int(datetime.now().timestamp())}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        rows = list(csv.reader(io.StringIO(response.text)))
        return parse_kraken_rows(rows)
    except Exception as exc:
        print(f"    ⚠️  Kraken Sheet total unavailable: {exc}")
        return {}


def parse_rrsp_rows(rows: list[list[str]], usdcad: float = 1.365) -> dict[str, Any]:
    """Parse the dedicated RRSP tab; never substitute Evolution Fund data."""
    positions = []
    for raw in rows:
        row = list(raw) + [""] * max(0, 15 - len(raw))
        currency = row[1].strip().upper()
        symbol = row[3].strip().upper()
        price = parse_money(row[5])
        shares = parse_money(row[8])
        if currency not in {"CAD", "USD"} or not symbol or not price or not shares:
            continue
        value_native = price * shares
        value_cad = value_native * (usdcad if currency == "USD" else 1.0)
        positions.append({
            "symbol": symbol.split(":")[-1],
            "sheet_symbol": symbol,
            "name": row[2].strip() or symbol,
            "currency": currency,
            "shares": float(shares),
            "sheet_price": float(price),
            "value_native": value_native,
            "value_cad": value_cad,
        })
    total_cad = sum(position["value_cad"] for position in positions)
    for position in positions:
        position["weight_pct"] = position["value_cad"] / total_cad * 100 if total_cad else 0.0
    positions.sort(key=lambda position: position["value_cad"], reverse=True)
    return {
        "account": "rrsp",
        "label": "RRSP",
        "sheet_gid": RRSP_GID,
        "sheet_name": "RRSP",
        "source": "Google Sheet · RRSP",
        "total_cad": total_cad,
        "positions": positions,
    }


def _fetch_sheet_rows(gid: str, tab_name: str, timeout: int = 20) -> list[list[str]]:
    """Read a Sheet tab via CSV, then authenticated Sheets API when needed."""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}&_={int(datetime.now().timestamp())}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        rows = list(csv.reader(io.StringIO(response.text)))
        if any(any(cell.strip() for cell in row) for row in rows):
            return rows
    except Exception:
        pass
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        token_path = Path.home() / ".hermes" / "google_token.json"
        credentials = Credentials.from_authorized_user_file(str(token_path))
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        quoted = tab_name.replace("'", "''")
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=f"'{quoted}'!A1:Z200",
            valueRenderOption="FORMATTED_VALUE",
        ).execute()
        return result.get("values", [])
    except Exception as exc:
        print(f"    ⚠️  {tab_name} Sheet unavailable: {exc}")
        return []


def fetch_rrsp_totals(usdcad: float = 1.365, timeout: int = 20) -> dict[str, Any]:
    rows = _fetch_sheet_rows(RRSP_GID, "RRSP", timeout=timeout)
    return parse_rrsp_rows(rows, usdcad=usdcad) if rows else {}


def _previous_weekday(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def latest_completed_market_date(now: datetime | None = None) -> str:
    """Return the latest completed New York weekday close date.

    The scheduled refresh runs after the North American close. Before 16:00 ET,
    use the prior weekday; weekends roll back to Friday.
    """
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(NEW_YORK)
    day = local.date()
    if day.weekday() >= 5:
        day = _previous_weekday(day)
    elif local.time() < dt_time(16, 0):
        day = _previous_weekday(day - timedelta(days=1))
    return day.isoformat()


def load_history(path: Path | str = HISTORY_PATH) -> dict[str, Any]:
    history_path = Path(path)
    if not history_path.exists():
        return {"schema_version": 1, "snapshots": []}
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "snapshots": []}
    if not isinstance(data, dict) or not isinstance(data.get("snapshots"), list):
        return {"schema_version": 1, "snapshots": []}
    data.setdefault("schema_version", 1)
    return data


def save_history(history: dict[str, Any], path: Path | str = HISTORY_PATH) -> None:
    history_path = Path(path)
    history_path.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def upsert_daily_snapshot(
    history: dict[str, Any],
    tfsa_meta: dict[str, Any] | None,
    kraken_meta: dict[str, Any] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Upsert one close per market date; later refreshes replace intraday marks."""
    accounts: dict[str, dict[str, float]] = {}
    tfsa_meta = tfsa_meta or {}
    kraken_meta = kraken_meta or {}

    tfsa_cad = tfsa_meta.get("total_cad")
    if isinstance(tfsa_cad, (int, float)) and tfsa_cad > 0:
        account = {"cad": round(float(tfsa_cad), 2)}
        if isinstance(tfsa_meta.get("total_usd"), (int, float)):
            account["usd"] = round(float(tfsa_meta["total_usd"]), 2)
        accounts["tfsa_ws"] = account

    kraken_cad = kraken_meta.get("total_cad")
    if isinstance(kraken_cad, (int, float)) and kraken_cad >= 0:
        account = {"cad": round(float(kraken_cad), 2)}
        if isinstance(kraken_meta.get("total_usd"), (int, float)):
            account["usd"] = round(float(kraken_meta["total_usd"]), 2)
        accounts["kraken"] = account

    if not accounts:
        return history

    now = now or datetime.now(timezone.utc)
    market_date = latest_completed_market_date(now)
    existing_same_date = next(
        (
            item for item in history.get("snapshots", [])
            if isinstance(item, dict) and item.get("market_date") == market_date
        ),
        None,
    )
    merged_accounts = dict((existing_same_date or {}).get("accounts") or {})
    merged_accounts.update(accounts)
    snapshot = {
        "market_date": market_date,
        "captured_at_utc": now.astimezone(timezone.utc).isoformat(),
        "accounts": merged_accounts,
        "source": "Google Sheet daily close",
    }
    snapshot["net_worth_cad"] = round(sum(item["cad"] for item in merged_accounts.values()), 2)

    snapshots = [
        item for item in history.get("snapshots", [])
        if isinstance(item, dict) and item.get("market_date") != market_date
    ]
    snapshots.append(snapshot)
    snapshots.sort(key=lambda item: item.get("market_date", ""))
    history["schema_version"] = 1
    history["source"] = "Google Sheet daily closes · TFSA/WS + Kraken"
    if isinstance(kraken_meta.get("inception_usd"), (int, float)):
        history["kraken_reference"] = {
            "date": "2025-10-01",
            "label": kraken_meta.get("inception_label") or "Oct 2025",
            "usd": round(float(kraken_meta["inception_usd"]), 2),
            "note": "Spreadsheet inception capital · cash-flow unadjusted",
        }
    history["snapshots"] = snapshots[-730:]
    return history


def _account_value(snapshot: dict[str, Any], account_key: str) -> float | None:
    value = (snapshot.get("accounts") or {}).get(account_key, {}).get("cad")
    return float(value) if isinstance(value, (int, float)) else None


def _period_change(
    snapshots: list[dict[str, Any]],
    current: dict[str, Any],
    account_keys: tuple[str, ...],
    days: int | str,
) -> dict[str, Any] | None:
    current_date = date.fromisoformat(current["market_date"])
    if days == "ytd":
        target = date(current_date.year, 1, 1) - timedelta(days=1)
    elif days == "all":
        target = date.min
    else:
        target = current_date - timedelta(days=int(days))
    current_values = [_account_value(current, key) for key in account_keys]
    if any(value is None for value in current_values):
        return None

    prior = None
    for snapshot in snapshots:
        try:
            snapshot_date = date.fromisoformat(snapshot["market_date"])
        except (KeyError, TypeError, ValueError):
            continue
        if days == "all" and all(_account_value(snapshot, key) is not None for key in account_keys):
            prior = snapshot
            break
        if snapshot_date <= target and all(_account_value(snapshot, key) is not None for key in account_keys):
            prior = snapshot
        if snapshot_date > target:
            break
    if prior is None:
        return None
    if prior is current:
        return None

    current_total = sum(value for value in current_values if value is not None)
    prior_total = sum(_account_value(prior, key) or 0.0 for key in account_keys)
    if prior_total == 0:
        return None
    amount = current_total - prior_total
    return {
        "amount": amount,
        "percent": amount / prior_total * 100,
        "baseline_date": prior["market_date"],
        "baseline_cad": prior_total,
    }


def build_tracker_model(history: dict[str, Any]) -> dict[str, Any]:
    snapshots = [
        item for item in history.get("snapshots", [])
        if isinstance(item, dict) and item.get("market_date") and isinstance(item.get("accounts"), dict)
    ]
    snapshots.sort(key=lambda item: item["market_date"])
    if not snapshots:
        return {"available": False, "periods": [label for label, _ in PERIODS]}

    current = snapshots[-1]
    account_defs = {
        "tfsa_ws": {"label": "Wealthsimple TFSA", "currency": "CAD"},
        "kraken": {"label": "Kraken", "currency": "USD"},
    }
    accounts = {}
    active_keys = []
    kraken_reference = history.get("kraken_reference") if isinstance(history.get("kraken_reference"), dict) else None
    for key, definition in account_defs.items():
        account_data = (current.get("accounts") or {}).get(key)
        if not isinstance(account_data, dict) or not isinstance(account_data.get("cad"), (int, float)):
            continue
        active_keys.append(key)
        series = [
            {"market_date": item["market_date"], "cad": _account_value(item, key),
             "usd": ((item.get("accounts") or {}).get(key) or {}).get("usd")}
            for item in snapshots if _account_value(item, key) is not None
        ]
        if key == "kraken" and kraken_reference and isinstance(kraken_reference.get("usd"), (int, float)):
            series.insert(0, {"market_date": kraken_reference.get("date", "2025-10-01"), "usd": float(kraken_reference["usd"]), "cad": None, "reference": True})
        periods = {
            label: _period_change(snapshots, current, (key,), days)
            for label, days in PERIODS
        }
        # If Jan 1 history predates the tracker, show a YTD proxy from the
        # first verified close captured in the current calendar year.
        if periods.get("YTD") is None and key != "kraken":
            current_year = date.fromisoformat(current["market_date"]).year
            first_ytd = next((
                item for item in snapshots
                if date.fromisoformat(item["market_date"]).year == current_year
                and _account_value(item, key) is not None
            ), None)
            if first_ytd and first_ytd is not current:
                baseline = _account_value(first_ytd, key) or 0.0
                if baseline > 0:
                    amount = float(account_data["cad"]) - baseline
                    periods["YTD"] = {
                        "amount": amount,
                        "percent": amount / baseline * 100,
                        "baseline_date": first_ytd["market_date"],
                        "baseline_cad": baseline,
                        "estimated": True,
                    }
        # Kraken's spreadsheet contains its Oct-2025 starting capital. Use that
        # as the honest cash-flow-unadjusted YTD proxy until daily 2025 closes exist.
        if key == "kraken" and periods.get("YTD") is None and kraken_reference and account_data.get("usd") is not None:
            baseline = float(kraken_reference.get("usd") or 0)
            if baseline > 0:
                amount_usd = float(account_data["usd"]) - baseline
                periods["YTD"] = {"amount": amount_usd, "percent": amount_usd / baseline * 100,
                                  "baseline_date": kraken_reference.get("date", "2025-10-01"),
                                  "baseline_cad": None, "currency": "USD", "estimated": True}
        accounts[key] = {
            **definition,
            "current_cad": float(account_data["cad"]),
            "current_usd": float(account_data["usd"]) if isinstance(account_data.get("usd"), (int, float)) else None,
            "periods": periods,
            "series": series,
        }

    combined_periods = {
        label: _period_change(snapshots, current, tuple(active_keys), days)
        for label, days in PERIODS
    } if active_keys else {label: None for label, _ in PERIODS}

    current_total = sum(account["current_cad"] for account in accounts.values())
    total_series = []
    for item in snapshots:
        values = [value for key in active_keys if (value := _account_value(item, key)) is not None]
        if values:
            total_series.append({
                "market_date": item["market_date"],
                "cad": round(sum(values), 2),
                "complete": len(values) == len(active_keys),
            })
    return {
        "available": True,
        "market_date": current["market_date"],
        "captured_at_utc": current.get("captured_at_utc"),
        "current_total_cad": current_total,
        "accounts": accounts,
        "combined_periods": combined_periods,
        "total_series": total_series,
        "periods": [label for label, _ in PERIODS],
        "snapshot_count": len(snapshots),
    }


def _account_chart_svg(key: str, account: dict[str, Any]) -> str:
    """Render one account's value path in its natural currency."""
    colors = {"tfsa_ws": "#ffd21f", "kraken": "#42d8ff"}
    value_key = "usd" if key == "kraken" else "cad"
    currency = "US$" if key == "kraken" else "C$"
    series = [point for point in account.get("series", []) if isinstance(point.get(value_key), (int, float))]
    if len(series) < 2:
        return '<div class="tracker-chart-empty">History started · the close chart will build automatically.</div>'
    values = [float(point[value_key]) for point in series]
    low, high = min(values), max(values)
    spread = high - low or 1.0
    width, height, xpad, ypad = 640.0, 145.0, 18.0, 18.0
    points = []
    for index, value in enumerate(values):
        x = xpad + (width - 2 * xpad) * (index / max(len(values) - 1, 1))
        y = ypad + (height - 2 * ypad) * (1 - (value - low) / spread)
        points.append(f"{x:.1f},{y:.1f}")
    color = colors.get(key, "#b59662")
    start_date = date.fromisoformat(series[0]["market_date"]).strftime("%b %Y")
    end_date = date.fromisoformat(series[-1]["market_date"]).strftime("%b %Y")
    start = values[0]
    current = values[-1]
    change = (current / start - 1) * 100 if start else 0
    change_sign = "+" if change >= 0 else "−"
    return (
        f'<div class="tracker-chart tracker-chart--{key}"><div class="tracker-chart-head">'
        f'<div><strong>{escape(account["label"])}</strong><span>{start_date} → {end_date}</span></div>'
        f'<b class="{"positive" if change >= 0 else "negative"}">{change_sign}{abs(change):.1f}%</b></div>'
        f'<svg viewBox="0 0 640 145" role="img" aria-label="{escape(account["label"])} account value history">'
        '<defs><linearGradient id="tracker-grid" x1="0" x2="1"><stop stop-color="#ffd21f" stop-opacity=".16"/><stop offset="1" stop-color="#42d8ff" stop-opacity=".08"/></linearGradient></defs>'
        '<rect x="0" y="0" width="640" height="145" rx="14" fill="url(#tracker-grid)"/>'
        '<path d="M18 36 H622 M18 72 H622 M18 108 H622" stroke="rgba(255,255,255,.06)" stroke-width="1"/>'
        f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3" vector-effect="non-scaling-stroke"/>'
        f'<circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" r="5" fill="{color}"/>'
        '</svg>'
        f'<div class="tracker-chart-axis"><span>{currency}{start:,.0f}</span><span>Current {currency}{current:,.0f}</span></div></div>'
    )


def _charts_html(accounts: dict[str, Any]) -> str:
    return '<div class="tracker-charts">' + ''.join(
        _account_chart_svg(key, accounts[key]) for key in ("tfsa_ws", "kraken") if key in accounts
    ) + '</div>'


def _format_period_cell(change: dict[str, Any]) -> str:
    positive = change["amount"] >= 0
    sign = "+" if positive else "−"
    cls = "positive" if positive else "negative"
    return (
        f'<div class="tracker-period {cls}">'
        f'<strong>{sign}{abs(change["percent"]):.1f}%</strong>'
        f'<small>{"≈" if change.get("estimated") else ""}{sign}{"US$" if change.get("currency") == "USD" else "C$"}{abs(change["amount"]):,.0f}</small>'
        '</div>'
    )


def _interactive_chart_html(model: dict[str, Any]) -> str:
    """Render a Wealthsimple-style dependency-free interactive net-worth chart."""
    series = model.get("total_series") or []
    if len(series) < 2:
        return '<div class="tracker-chart-empty">History started · the chart will build automatically.</div>'
    payload = escape(json.dumps(series, separators=(",", ":")), quote=True)
    tabs = "".join(
        f'<button type="button" data-range="{label}" class="tracker-range{" is-active" if label == "YTD" else ""}">{label}</button>'
        for label, _ in PERIODS
    )
    return f'''<div class="tracker-hero" data-series="{payload}">
      <div class="tracker-hero-metric"><div class="tracker-hero-value">C${model["current_total_cad"]:,.2f}</div><div class="tracker-hero-change" aria-live="polite"></div><div class="tracker-hero-note"></div></div>
      <svg class="tracker-hero-svg" viewBox="0 0 920 330" preserveAspectRatio="none" role="img" aria-label="Interactive total net worth history">
        <defs><linearGradient id="netWorthFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#56f2b1" stop-opacity=".24"/><stop offset="1" stop-color="#56f2b1" stop-opacity="0"/></linearGradient></defs>
        <path class="tracker-hero-area" fill="url(#netWorthFill)"/><path class="tracker-hero-line" fill="none" stroke="#56f2b1" stroke-width="3.5" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round"/><line class="tracker-crosshair" y1="16" y2="308"/><circle class="tracker-dot" r="6"/>
      </svg><div class="tracker-ranges" aria-label="Chart range">{tabs}</div>
    </div>
    <script>(function(){{
      const root=document.currentScript.previousElementSibling;if(!root||root.dataset.ready)return;root.dataset.ready='1';
      const all=JSON.parse(root.dataset.series),svg=root.querySelector('svg'),line=root.querySelector('.tracker-hero-line'),area=root.querySelector('.tracker-hero-area'),dot=root.querySelector('.tracker-dot'),cross=root.querySelector('.tracker-crosshair'),change=root.querySelector('.tracker-hero-change'),note=root.querySelector('.tracker-hero-note');
      const W=920,H=330,P=18,cut={{'1D':1,'1W':7,'1M':30,'3M':90,'6M':180,'YTD':'ytd','1Y':365,'ALL':'all'}};let shown=[];
      const money=n=>'C$'+Math.abs(n).toLocaleString('en-CA',{{maximumFractionDigits:0}});
      function draw(range){{const end=new Date(all.at(-1).market_date+'T00:00:00Z');let start;if(cut[range]==='all')start=new Date('1900-01-01');else if(cut[range]==='ytd')start=new Date(Date.UTC(end.getUTCFullYear(),0,1));else start=new Date(end-cut[range]*86400000);shown=all.filter(p=>new Date(p.market_date+'T00:00:00Z')>=start);if(shown.length<2)shown=all.slice(-2);const vals=shown.map(p=>p.cad),lo=Math.min(...vals),hi=Math.max(...vals),pad=Math.max((hi-lo)*.13,1),min=lo-pad,max=hi+pad,pts=shown.map((p,i)=>[P+(W-2*P)*(i/Math.max(shown.length-1,1)),P+(H-2*P)*(1-(p.cad-min)/(max-min))]),d=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');line.setAttribute('d',d);area.setAttribute('d',d+' L '+pts.at(-1)[0]+' '+(H-P)+' L '+pts[0][0]+' '+(H-P)+' Z');const first=shown[0],last=shown.at(-1),delta=last.cad-first.cad,pct=first.cad?delta/first.cad*100:0,pos=delta>=0,sign=pos?'+':'−';change.className='tracker-hero-change '+(pos?'positive':'negative');change.textContent=sign+' '+money(delta)+' ('+sign+Math.abs(pct).toFixed(2)+'%) · '+range;note.textContent=(shown.length===all.length&&range!=='ALL'?'Available history begins ':'Close history from ')+new Date(first.market_date+'T00:00:00Z').toLocaleDateString('en-CA',{{month:'short',day:'numeric',year:'numeric'}})+(shown.some(p=>!p.complete)?' · earlier points exclude accounts not yet tracked':'');dot.style.opacity=cross.style.opacity=0;}}
      root.querySelectorAll('.tracker-range').forEach(b=>b.addEventListener('click',()=>{{root.querySelectorAll('.tracker-range').forEach(x=>x.classList.remove('is-active'));b.classList.add('is-active');draw(b.dataset.range)}}));
      svg.addEventListener('pointermove',e=>{{const r=svg.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*W,i=Math.max(0,Math.min(shown.length-1,Math.round((x-P)/(W-2*P)*(shown.length-1)))),p=shown[i],vals=shown.map(q=>q.cad),lo=Math.min(...vals),hi=Math.max(...vals),pad=Math.max((hi-lo)*.13,1),cx=P+(W-2*P)*(i/Math.max(shown.length-1,1)),cy=P+(H-2*P)*(1-(p.cad-(lo-pad))/((hi+pad)-(lo-pad)));dot.setAttribute('cx',cx);dot.setAttribute('cy',cy);cross.setAttribute('x1',cx);cross.setAttribute('x2',cx);dot.style.opacity=cross.style.opacity=1;root.querySelector('.tracker-hero-value').textContent='C$'+p.cad.toLocaleString('en-CA',{{minimumFractionDigits:2,maximumFractionDigits:2}});note.textContent=new Date(p.market_date+'T00:00:00Z').toLocaleDateString('en-CA',{{month:'long',day:'numeric',year:'numeric'}})}});svg.addEventListener('pointerleave',()=>{{root.querySelector('.tracker-hero-value').textContent='C$'+all.at(-1).cad.toLocaleString('en-CA',{{minimumFractionDigits:2,maximumFractionDigits:2}});draw(root.querySelector('.tracker-range.is-active').dataset.range)}});draw('YTD');
    }})();</script>'''


def render_tracker_html(model: dict[str, Any]) -> str:
    if not model.get("available"):
        return (
            '<section class="card net-worth-tracker" id="net-worth-tracker">'
            '<div class="card-title">⚡ Net Worth Tracker</div>'
            '<div class="tracker-chart-empty">Awaiting Google Sheet close data.</div>'
            '</section>'
        )

    market_date = date.fromisoformat(model["market_date"])
    date_label = market_date.strftime("%b %-d, %Y")
    account_cards = []
    performance_rows = []
    for key in ("tfsa_ws", "kraken"):
        account = model["accounts"].get(key)
        if not account:
            continue
        if key == "kraken" and account.get("current_usd") is not None:
            value = f'US${account["current_usd"]:,.0f}'
            secondary = f'C${account["current_cad"]:,.0f}'
        else:
            value = f'C${account["current_cad"]:,.0f}'
            secondary = f'US${account["current_usd"]:,.0f}' if account.get("current_usd") is not None else "CAD account"
        account_cards.append(
            f'<div class="tracker-account tracker-account--{key}">'
            f'<div class="tracker-account-name"><span></span>{escape(account["label"])}</div>'
            f'<div class="tracker-account-value">{value}</div>'
            f'<div class="tracker-account-secondary">{secondary}</div>'
            '</div>'
        )
        available_periods = [
            (label, account["periods"].get(label))
            for label in model["periods"]
            if account["periods"].get(label) is not None
        ]
        if available_periods:
            cells = "".join(
                f'<div><em>{label}</em>{_format_period_cell(change)}</div>'
                for label, change in available_periods
            )
            performance_rows.append(
                f'<div class="tracker-performance-row"><div class="tracker-performance-name">{escape(account["label"])}</div>'
                f'<div class="tracker-performance-grid{" tracker-performance-grid--single" if len(available_periods) == 1 else ""}" '
                f'style="--period-count:{len(available_periods)}">{cells}</div></div>'
            )

    available_combined_periods = [
        (label, model["combined_periods"].get(label))
        for label in model["periods"]
        if model["combined_periods"].get(label) is not None
    ]
    if available_combined_periods:
        combined_cells = "".join(
            f'<div><em>{label}</em>{_format_period_cell(change)}</div>'
            for label, change in available_combined_periods
        )
        performance_rows.insert(
            0,
            '<div class="tracker-performance-row tracker-performance-row--total">'
            '<div class="tracker-performance-name">Total Net Worth</div>'
            f'<div class="tracker-performance-grid{" tracker-performance-grid--single" if len(available_combined_periods) == 1 else ""}" '
            f'style="--period-count:{len(available_combined_periods)}">{combined_cells}</div></div>',
        )

    performance_html = ""
    if performance_rows:
        performance_html = (
            '<div class="tracker-performance-title">Close-to-close performance</div>'
            '<div class="tracker-performance">' + "".join(performance_rows) + '</div>'
        )

    return (
        '<section class="card net-worth-tracker" id="net-worth-tracker">'
        '<div class="tracker-head">'
        '<div><div class="card-title">⚡ Net Worth Tracker</div>'
        '<div class="tracker-subtitle">Google Sheet daily closes · TFSA/WS + Kraken</div></div>'
        f'<div class="tracker-asof"><span></span>{date_label} close</div></div>'
        '<div class="tracker-total-label">Combined Net Worth</div>'
        f'<div class="tracker-total">C${model["current_total_cad"]:,.0f}</div>'
        + _interactive_chart_html(model)
        + '<div class="tracker-accounts">' + "".join(account_cards) + '</div>'
        + performance_html
        + '<div class="tracker-foot"><strong>Account-value return, not pure investment return.</strong> Deposits, withdrawals and Kraken leverage affect these percentages. Kraken YTD is an approximate capital-path reference from the spreadsheet’s Oct 2025 US$7,000 inception balance; future closes will sharpen it automatically.</div>'
        '</section>'
    )
