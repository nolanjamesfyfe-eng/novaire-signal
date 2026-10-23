import math
from pathlib import Path

from bs4 import BeautifulSoup

import generate


ROOT = Path(__file__).resolve().parents[1]


def test_daily_metrics_use_position_weighted_adjacent_closes_in_cad():
    holdings = [
        {"ticker": "CAD.TO", "shares": 10, "currency": "CAD"},
        {"ticker": "USD", "shares": 2, "currency": "USD"},
        {"ticker": "AUD.AX", "shares": 5, "currency": "AUD"},
    ]
    quotes = {
        "CAD.TO": {"price": 11, "previous_close": 10, "close_session_date": "2026-09-17"},
        "USD": {"price": 21, "previous_close": 20, "close_session_date": "2026-09-17"},
        "AUD.AX": {"price": 9, "previous_close": 10, "close_session_date": "2026-09-18"},
    }

    result = generate.calculate_portfolio_daily_metrics(
        quotes, holdings, {"usdcad": 1.4, "audusd": 0.5}
    )

    assert result is not None
    expected_previous = 100 + 40 * 1.4 + 50 * 0.5 * 1.4
    expected_live = 110 + 42 * 1.4 + 45 * 0.5 * 1.4
    assert math.isclose(result["previous_value_cad"], expected_previous)
    assert math.isclose(result["pnl_cad"], expected_live - expected_previous)
    assert math.isclose(result["roi_pct"], (expected_live / expected_previous - 1) * 100)
    assert result["session_dates"] == ["2026-09-17", "2026-09-18"]


def test_daily_metrics_fail_closed_when_any_holding_lacks_baseline():
    holdings = [
        {"ticker": "GOOD", "shares": 10, "currency": "CAD"},
        {"ticker": "MISSING", "shares": 1, "currency": "CAD"},
    ]
    quotes = {
        "GOOD": {"price": 11, "previous_close": 10},
        "MISSING": {"price": 5, "previous_close": None},
    }
    assert generate.calculate_portfolio_daily_metrics(
        quotes, holdings, {"usdcad": 1.4, "audusd": 0.5}
    ) is None


def test_generated_portfolio_has_exactly_seven_compact_summary_tiles():
    html = (ROOT / "portfolio/index.html").read_text()
    soup = BeautifulSoup(html, "html.parser")
    summary = soup.select_one('[data-summary-tiles="7"]')
    assert summary is not None
    assert len(summary.select(":scope > .psum-item")) == 7
    labels = [node.get_text(" ", strip=True) for node in summary.select(".psum-label")]
    assert labels == [
        "Live CAD", "Live USD", "Daily ROI", "Daily P&L CAD",
        "ATH CAD", "Off ATH (%)", "$ off ATH CAD",
    ]
    assert "Cost Basis CAD" not in summary.get_text(" ", strip=True)
    assert "YTD Return" not in summary.get_text(" ", strip=True)
    assert 'grid-template-columns:repeat(7,minmax(0,1fr))' in html
    assert 'data-daily-basis="previous-completed-session-close"' in html


def test_sheet_daily_metrics_match_sheet_total_scope_and_exclude_covered_calls():
    from generate import calculate_sheet_daily_metrics
    holdings = [
        {"ticker": "HG.CN", "shares": 100, "sheet_value_cad": 900.0, "sheet_change_pct": -10.0},
        {"ticker": "AEU.AX", "shares": 10, "sheet_value_cad": 100.0, "sheet_change_pct": 0.0},
        {"ticker": "URNJ", "shares": 5, "sheet_value_cad": 5000.0, "sheet_change_pct": -50.0, "covered_call": True},
    ]
    metrics = calculate_sheet_daily_metrics(holdings, 1000.0)
    assert round(metrics["pnl_cad"], 2) == -100.0
    assert round(metrics["roi_pct"], 4) == round(-100 / 1100 * 100, 4)


def test_sheet_daily_metrics_fail_closed_on_missing_change():
    from generate import calculate_sheet_daily_metrics
    assert calculate_sheet_daily_metrics([{"ticker": "X", "shares": 1, "sheet_value_cad": 10.0}], 10.0) is None


def test_sheet_guard_rejects_partial_rows_and_nonreconciling_total():
    import pytest
    h = {"ticker": "X", "shares": 10, "name": "Example", "currency": "CAD", "sheet_price": 10, "sheet_value_cad": 100, "sheet_change_pct": 0}
    meta = {"total_cad": 100, "total_usd": 70, "sheet_fetched_at_utc": "2026-10-23T10:00:00+00:00"}
    fx = {"usdcad": 1.4, "audusd": .7}
    with pytest.raises(ValueError, match="Incomplete Sheet row"):
        generate.render_portfolio_html({}, {}, fx, [{**h, "sheet_price": None}], meta)
    with pytest.raises(ValueError, match="reconciliation failed"):
        generate.render_portfolio_html({}, {}, fx, [h], {**meta, "total_cad": 200})


def test_sheet_rows_override_vendor_quotes_and_label_currency():
    from bs4 import BeautifulSoup
    h = {"ticker": "X", "shares": 10, "name": "Example", "currency": "USD", "sheet_price": 10, "sheet_value_cad": 140, "sheet_change_pct": -10}
    meta = {"total_cad": 140, "total_usd": 100, "sheet_fetched_at_utc": "2026-10-23T10:00:00+00:00"}
    html = generate.render_portfolio_html({"X": {"price": 99, "value": 990, "change": 50}}, {}, {"usdcad": 1.4, "audusd": .7}, [h], meta)
    soup = BeautifulSoup(html, "html.parser")
    cells = [c.get_text(strip=True) for c in soup.select('#holdings-table tbody td')]
    assert cells[2:] == ['10', 'US$10.00', '-10.00%', '$140']
    assert "Value CAD" in html
    assert "Google Sheet snapshot" in html
