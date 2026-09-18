#!/usr/bin/env python3
"""Authoritative Federal Reserve decision/calendar retrieval with last-good cache."""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from fractions import Fraction
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

FED_BASE = "https://www.federalreserve.gov"
CALENDAR_URL = f"{FED_BASE}/monetarypolicy/fomccalendars.htm"
CACHE_PATH = Path(__file__).with_name("fed_signal_cache.json")
USER_AGENT = "NovaireSignal/1.0 (+https://novairesignal.com/)"
REQUIRED = {
    "last_decision", "last_action", "last_action_source", "fed_funds_rate",
    "next_decision", "next_meeting_date", "calendar_source", "verified_at",
}


def _number(value: str) -> float:
    value = value.strip().replace("−", "-")
    mixed = re.fullmatch(r"(-?\d+)-(\d+)/(\d+)", value)
    if mixed:
        return float(int(mixed.group(1)) + Fraction(int(mixed.group(2)), int(mixed.group(3))))
    fraction = re.fullmatch(r"(-?\d+)/(\d+)", value)
    if fraction:
        return float(Fraction(int(fraction.group(1)), int(fraction.group(2))))
    return float(value)


def _fmt_rate(value: float) -> str:
    return f"{value:.2f}"


def validate_fed_cache(data: dict, *, today: date | None = None) -> dict:
    if not isinstance(data, dict) or REQUIRED - data.keys():
        raise ValueError(f"Fed cache missing fields: {sorted(REQUIRED - set(data or {}))}")
    if not re.fullmatch(r"https://www\.federalreserve\.gov/newsevents/pressreleases/monetary\d{8}a\.htm", data["last_action_source"]):
        raise ValueError("Fed decision source is not an official statement URL")
    if data["calendar_source"] != CALENDAR_URL:
        raise ValueError("Fed calendar source is not the official calendar")
    last = date.fromisoformat(data["last_meeting_date"])
    nxt = date.fromisoformat(data["next_meeting_date"])
    now = today or datetime.now(timezone.utc).date()
    if last > now or nxt <= last:
        raise ValueError("Fed meeting dates are inconsistent")
    if data["last_decision"] != last.strftime("%B %-d, %Y") or data["next_decision"] != nxt.strftime("%B %-d, %Y"):
        raise ValueError("Fed display dates do not match canonical dates")
    rate = re.fullmatch(r"(\d+\.\d{2})–(\d+\.\d{2})%", data["fed_funds_rate"])
    if not rate or float(rate.group(1)) >= float(rate.group(2)):
        raise ValueError("Fed target range is invalid")
    if not re.fullmatch(r"(?:Raised|Lowered) \d+(?:\.\d+)? percentage points|Held steady", data["last_action"]):
        raise ValueError("Fed action is invalid")
    datetime.fromisoformat(data["verified_at"].replace("Z", "+00:00"))
    return data


def _meeting_dates(calendar_html: str) -> list[date]:
    soup = BeautifulSoup(calendar_html, "html.parser")
    meetings = []
    months = {name: number for number, name in enumerate(
        ("", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
    )}
    for row in soup.select(".fomc-meeting"):
        panel = row.find_parent("div", class_="panel")
        heading = panel.find(["h2", "h3", "h4"]) if panel else None
        year_match = re.search(r"20\d{2}", heading.get_text(" ", strip=True) if heading else "")
        month_node = row.select_one(".fomc-meeting__month")
        date_node = row.select_one(".fomc-meeting__date")
        if not (year_match and month_node and date_node):
            continue
        month_text = month_node.get_text(" ", strip=True).replace("Apr/May", "May").replace("Jan/Feb", "February").replace("Oct/Nov", "November")
        month = next((months[name] for name in months if name and name in month_text), None)
        days = [int(x) for x in re.findall(r"\d+", date_node.get_text(" ", strip=True))]
        if month and days:
            meetings.append(date(int(year_match.group()), month, days[-1]))
    if not meetings:
        raise ValueError("No FOMC meeting dates found")
    return sorted(set(meetings))


def _statement_url(calendar_html: str, today: date) -> str:
    soup = BeautifulSoup(calendar_html, "html.parser")
    candidates = []
    for anchor in soup.find_all("a", href=True):
        match = re.fullmatch(r"/newsevents/pressreleases/monetary(\d{8})a\.htm", anchor["href"])
        if match:
            statement_date = datetime.strptime(match.group(1), "%Y%m%d").date()
            if statement_date <= today:
                candidates.append((statement_date, urljoin(FED_BASE, anchor["href"])))
    if not candidates:
        raise ValueError("No released official FOMC statement found")
    return max(candidates)[1]


def _parse_statement(statement_html: str, source_url: str) -> dict:
    source_match = re.search(r"monetary(\d{8})a\.htm$", source_url)
    if not source_match:
        raise ValueError("Unexpected FOMC statement URL")
    meeting_date = datetime.strptime(source_match.group(1), "%Y%m%d").date()
    text = " ".join(BeautifulSoup(statement_html, "html.parser").stripped_strings)
    target = re.search(
        r"decided to (raise|lower|maintain) the target range for the federal funds rate(?: by ([\d./-]+) percentage point)?(?:s)?(?: at| to) ([\d./-]+) to ([\d./-]+) percent",
        text, re.IGNORECASE,
    )
    if not target:
        raise ValueError("Official statement target-range sentence was not recognized")
    verb, amount, low, high = target.groups()
    low_value, high_value = _number(low), _number(high)
    if not (0 <= low_value < high_value <= 25):
        raise ValueError("Official statement target range is out of bounds")
    if verb.lower() == "maintain":
        action = "Held steady"
    else:
        if not amount:
            raise ValueError("Official statement rate change has no magnitude")
        magnitude = _number(amount)
        if not (0 < magnitude <= 2):
            raise ValueError("Official statement rate change is out of bounds")
        action = f"{'Raised' if verb.lower() == 'raise' else 'Lowered'} {magnitude:g} percentage points"
    return {
        "last_meeting_date": meeting_date.isoformat(),
        "last_decision": meeting_date.strftime("%B %-d, %Y"),
        "last_action": action,
        "last_action_source": source_url,
        "fed_funds_rate": f"{_fmt_rate(low_value)}–{_fmt_rate(high_value)}%",
    }


def fetch_official_fed_data(*, session=requests, today: date | None = None) -> dict:
    now = today or datetime.now(timezone.utc).date()
    headers = {"User-Agent": USER_AGENT}
    calendar_response = session.get(CALENDAR_URL, headers=headers, timeout=15)
    calendar_response.raise_for_status()
    calendar_html = calendar_response.text
    meetings = _meeting_dates(calendar_html)
    statement_url = _statement_url(calendar_html, now)
    statement_response = session.get(statement_url, headers=headers, timeout=15)
    statement_response.raise_for_status()
    data = _parse_statement(statement_response.text, statement_url)
    last_meeting = date.fromisoformat(data["last_meeting_date"])
    future = [meeting for meeting in meetings if meeting > last_meeting]
    if not future:
        raise ValueError("Official calendar has no meeting after the latest statement")
    next_meeting = min(future)
    data.update({
        "next_meeting_date": next_meeting.isoformat(),
        "next_decision": next_meeting.strftime("%B %-d, %Y"),
        "calendar_source": CALENDAR_URL,
        "verified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    return validate_fed_cache(data, today=now)


def _write_cache(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def get_fed_data(*, cache_path: Path = CACHE_PATH, session=requests, today: date | None = None) -> dict:
    """Refresh from official sources, or retain a validated last-good cache."""
    now = today or datetime.now(timezone.utc).date()
    try:
        fresh = fetch_official_fed_data(session=session, today=now)
        _write_cache(fresh, cache_path)
        return fresh
    except Exception as fetch_error:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return validate_fed_cache(cached, today=now)
        except Exception as cache_error:
            raise RuntimeError(f"Fed refresh failed and no valid last-good cache exists: fetch={fetch_error}; cache={cache_error}") from fetch_error
