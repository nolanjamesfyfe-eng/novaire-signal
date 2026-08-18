#!/usr/bin/env python3
"""Weekly end-to-end health audit for every Novaire Signal quote surface.

Exits 0 only when upstream quotes, generated markup, and the deployed homepage
all pass. Intended for a weekly cron run; this script does not install cron.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import generate  # noqa: E402

CANONICAL_URL = "https://novairesignal.com"
EXPECTED_CRYPTO = {"BTC", "ETH", "SOL", "ADA", "TON", "SUI", "ZEC", "NIGHT"}
EXPECTED_FX = {"CAD", "THB", "AUD", "COP", "EUR", "RUB", "KRW", "JPY"}
FORBIDDEN = (
    "Daily " + "Updog Vote",
    "Daily product " + "senate",
    'id="' + 'updog-card"',
    "render" + "UpdogVotes",
    "UPDOG_" + "SUGGESTIONS",
    "UPDOG_" + "ACTION_STEPS",
    "handle" + "UpdogVote",
)


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


class Audit:
    def __init__(self) -> None:
        self.results: list[dict[str, str]] = []

    def record(self, ok: bool, name: str, detail: str) -> None:
        self.results.append({"status": "PASS" if ok else "FAIL", "name": name, "detail": detail})

    def warn(self, name: str, detail: str) -> None:
        self.results.append({"status": "WARN", "name": name, "detail": detail})

    @property
    def failures(self) -> list[dict[str, str]]:
        return [result for result in self.results if result["status"] == "FAIL"]


def audit_upstreams(audit: Audit) -> None:
    now = datetime.now(timezone.utc)

    crypto = generate.fetch_crypto()
    audit.record(set(crypto) == EXPECTED_CRYPTO, "crypto coverage", f"{len(crypto)}/{len(EXPECTED_CRYPTO)} assets")
    for ticker in sorted(EXPECTED_CRYPTO):
        item = crypto.get(ticker, {})
        price = item.get("price")
        quote_time = parse_time(item.get("quote_time"))
        source = item.get("source")
        age_minutes = (now - quote_time).total_seconds() / 60 if quote_time else None
        ok = bool(price and float(price) > 0 and source and age_minutes is not None and -2 <= age_minutes <= 30)
        detail = f"price={price} source={source} age_min={age_minutes:.1f}" if age_minutes is not None else f"price={price} source={source} age=missing"
        audit.record(ok, f"crypto {ticker}", detail)
    ton_pair = getattr(generate, "CRYPTO_BINANCE_PAIRS", {}).get("TON")
    audit.record(ton_pair == "GRAMUSDT", "TON successor mapping", f"TON display polls {ton_pair!r}; frozen TONUSDT is forbidden")

    markets = generate.fetch_market_futures()
    expected_markets = getattr(generate, "MARKET_FUTURES", {})
    audit.record(set(markets) == set(expected_markets), "Wall Street coverage", f"{len(markets)}/{len(expected_markets)} benchmarks")
    for symbol, meta in expected_markets.items():
        item = markets.get(symbol, {})
        price = item.get("price")
        quote_time = parse_time(item.get("quote_time"))
        age_hours = (now - quote_time).total_seconds() / 3600 if quote_time else None
        # Four calendar days covers normal weekends and exchange holidays.
        ok = bool(price and float(price) > 0 and age_hours is not None and -1 <= age_hours <= 96)
        source = str(item.get("source") or "")
        ok = ok and "CME/CBOT front month" in source and "Consensus" not in source
        detail = f"{meta.get('label')}={price} source={source} age_hours={age_hours:.1f}" if age_hours is not None else f"{meta.get('label')}={price} source={source} age=missing"
        audit.record(ok, f"market {symbol}", detail)

    cash_indices = generate.fetch_market_indices()
    expected_indices = getattr(generate, "MARKET_INDICES", {})
    audit.record(set(cash_indices) == set(expected_indices), "cash-index coverage", f"{len(cash_indices)}/{len(expected_indices)} benchmarks")
    for symbol, meta in expected_indices.items():
        item = cash_indices.get(symbol, {})
        price = item.get("price")
        quote_time = parse_time(item.get("quote_time"))
        age_hours = (now - quote_time).total_seconds() / 3600 if quote_time else None
        ok = bool(price and float(price) > 0 and age_hours is not None and -1 <= age_hours <= 96)
        detail = f"{meta.get('label')}={price} age_hours={age_hours:.1f}" if age_hours is not None else f"{meta.get('label')}={price} age=missing"
        audit.record(ok, f"cash index {symbol}", detail)

    commodities = generate.fetch_commodities()
    expected_commodities = {"GOLD", "SILVER", "COPPER", "WTI", "URANIUM_SPOT", "DIESEL"}
    audit.record(set(commodities) == expected_commodities, "commodity coverage", f"{len(commodities)}/{len(expected_commodities)} quotes")
    for symbol in sorted(expected_commodities):
        price = commodities.get(symbol, {}).get("price")
        audit.record(bool(price and float(price) > 0), f"commodity {symbol}", f"price={price}")

    fx_rates = generate.fetch_fx_rates()
    audit.record(set(fx_rates) == EXPECTED_FX, "FX coverage", f"{len(fx_rates)}/{len(EXPECTED_FX)} pairs")
    for currency in sorted(EXPECTED_FX):
        rate = fx_rates.get(currency, {}).get("rate")
        audit.record(bool(rate and float(rate) > 0), f"FX {currency}", f"1 USD={rate}")

    fx = generate.fetch_fx()
    portfolio, holdings, _ = generate.fetch_portfolio(usdcad=fx["usdcad"], audusd=fx["audusd"])
    missing = [h["ticker"] for h in holdings if not portfolio.get(h["ticker"], {}).get("price")]
    audit.record(not missing, "portfolio quote coverage", f"{len(holdings) - len(missing)}/{len(holdings)} live marks; missing={missing}")
    fallback = [ticker for ticker, item in portfolio.items() if item.get("fallback")]
    if fallback:
        audit.warn("portfolio sheet marks", f"sheet-supplied marks (not shown as live Yahoo changes): {fallback}")


def audit_html(audit: Audit, html: str, label: str) -> None:
    weather = html.find("🌤 Weather")
    wall_street = html.find("Wall Street")
    fx = html.find("💱 FX Rates")
    audit.record(min(weather, wall_street, fx) >= 0 and weather < wall_street < fx, f"{label} section order", f"Weather={weather}, WallStreet={wall_street}, FX={fx}")

    catalysts = html.find("🔍 Catalysts — Top 5 Holdings")
    fed = html.find("🏛️ Fed Signal")
    trading_books = html.find("<!-- TRADING BOOKS")
    audit.record(min(catalysts, fed, trading_books) >= 0 and catalysts < fed < trading_books, f"{label} Fed placement", f"Catalysts={catalysts}, Fed={fed}, TradingBooks={trading_books}")

    soup = BeautifulSoup(html, "html.parser")
    crypto_nodes = soup.select("[data-crypto-price]")
    commodity_nodes = soup.select("[data-comm-price]")
    market_nodes = soup.select("[data-market-price], [data-future-price]")
    for name, nodes, expected in (
        ("crypto markup", crypto_nodes, 8),
        ("commodity markup", commodity_nodes, 7),
        ("market markup", market_nodes, len(getattr(generate, "MARKET_FUTURES", {}))),
    ):
        values = [node.get_text(" ", strip=True) for node in nodes]
        audit.record(len(nodes) == expected and all(value not in {"", "—"} for value in values), f"{label} {name}", f"count={len(nodes)} values={values}")

    audit.record('"TON":"GRAMUSDT"' in html and '"TON":"TONUSDT"' not in html, f"{label} TON browser poll", "active GRAMUSDT mapping present")
    absent = [marker for marker in FORBIDDEN if marker in html]
    audit.record(not absent, f"{label} retired vote guard", f"forbidden markers={absent}")
    audit.record("data.isSet" in html and "items.every" in html, f"{label} Keystone gates", "set gate and all-action completion gate present")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-url", default=CANONICAL_URL)
    parser.add_argument("--no-live", action="store_true", help="Skip the deployed-page check")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    audit = Audit()
    try:
        audit_upstreams(audit)
    except Exception as exc:
        audit.record(False, "upstream audit execution", repr(exc))

    local_path = ROOT / "index.html"
    try:
        audit_html(audit, local_path.read_text(encoding="utf-8"), "local")
    except Exception as exc:
        audit.record(False, "local HTML", repr(exc))

    if not args.no_live:
        try:
            separator = "&" if "?" in args.live_url else "?"
            response = requests.get(f"{args.live_url}{separator}quote-audit={int(datetime.now().timestamp())}", headers={"Cache-Control": "no-cache", "User-Agent": "NovaireSignalQuoteAudit/1.0"}, timeout=30)
            audit.record(response.status_code == 200, "live HTTP", f"status={response.status_code} bytes={len(response.content)}")
            if response.status_code == 200:
                audit_html(audit, response.text, "live")

            api_url = args.live_url.rstrip("/") + "/api/market-futures"
            api_response = requests.get(api_url, headers={"Cache-Control": "no-cache", "User-Agent": "NovaireSignalQuoteAudit/1.0"}, timeout=30)
            api_payload = api_response.json()
            futures = api_payload.get("quotes") or []
            indices = api_payload.get("indices") or []
            canonical = all("CME/CBOT front month" in str(item.get("source") or "") and item.get("price") for item in futures)
            api_ok = api_response.status_code in (200, 206) and len(futures) == 3 and len(indices) == 3 and canonical
            audit.record(api_ok, "live market API", f"status={api_response.status_code} futures={len(futures)} cash_indices={len(indices)} canonical={canonical}")
        except Exception as exc:
            audit.record(False, "live HTML/API", repr(exc))

    payload = {
        "ok": not audit.failures,
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "live_url": None if args.no_live else args.live_url,
        "results": audit.results,
        "failures": len(audit.failures),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for result in audit.results:
            print(f"[{result['status']}] {result['name']}: {result['detail']}")
        print(f"\n{'PASS' if payload['ok'] else 'FAIL'}: {len(audit.results)} checks, {payload['failures']} failures")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
