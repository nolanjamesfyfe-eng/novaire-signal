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
HISTORY_PATH = Path(__file__).with_name("portfolio_history.json")
PERIODS = (("1D", 1), ("1W", 7), ("MoM", 30), ("QoQ", 90), ("YTD", "ytd"))


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
        if snapshot_date <= target and all(_account_value(snapshot, key) is not None for key in account_keys):
            prior = snapshot
        if snapshot_date > target:
            break
    if prior is None:
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
    return {
        "available": True,
        "market_date": current["market_date"],
        "captured_at_utc": current.get("captured_at_utc"),
        "current_total_cad": current_total,
        "accounts": accounts,
        "combined_periods": combined_periods,
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
    width, height, xpad, ypad = 640.0, 190.0, 18.0, 24.0
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
        f'<svg viewBox="0 0 640 190" role="img" aria-label="{escape(account["label"])} account value history">'
        '<defs><linearGradient id="tracker-grid" x1="0" x2="1"><stop stop-color="#ffd21f" stop-opacity=".16"/><stop offset="1" stop-color="#42d8ff" stop-opacity=".08"/></linearGradient></defs>'
        '<rect x="0" y="0" width="640" height="190" rx="14" fill="url(#tracker-grid)"/>'
        '<path d="M18 48 H622 M18 95 H622 M18 142 H622" stroke="rgba(255,255,255,.06)" stroke-width="1"/>'
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
                f'<div class="tracker-performance-grid">{cells}</div></div>'
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
            f'<div class="tracker-performance-grid">{combined_cells}</div></div>',
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
        '<div class="tracker-accounts">' + "".join(account_cards) + '</div>'
        + _charts_html(model["accounts"])
        + performance_html
        + '<div class="tracker-foot"><strong>Account-value return, not pure investment return.</strong> Deposits, withdrawals and Kraken leverage affect these percentages. Kraken YTD is an approximate capital-path reference from the spreadsheet’s Oct 2025 US$7,000 inception balance; future closes will sharpen it automatically.</div>'
        '</section>'
    )
