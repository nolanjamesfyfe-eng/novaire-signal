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
