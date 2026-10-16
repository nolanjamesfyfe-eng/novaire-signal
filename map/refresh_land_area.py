#!/usr/bin/env python3
"""Build the Flâneur land-area dataset from the World Bank/FAO indicator."""
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "countries.json"
OUTPUT = ROOT / "land_area.json"
INDICATOR = "AG.LND.TOTL.K2"
API = f"https://api.worldbank.org/v2/country/all/indicator/{INDICATOR}?format=json&per_page=20000"
COUNTRIES_API = "https://api.worldbank.org/v2/country?format=json&per_page=400"
SOURCE_URL = f"https://data.worldbank.org/indicator/{INDICATOR}"
# The World Bank does not publish this indicator for these atlas entries. These
# are explicit 2023 land-area observations from FAOSTAT's Land Use domain; they
# are never silently treated as zero.
FAOSTAT_SUPPLEMENTS = {
    "XK": {"km2": 10_887, "year": 2023},
    "TW": {"km2": 35_410, "year": 2023},
    "VA": {"km2": 0.49, "year": 2023},
}
FAOSTAT_URL = "https://www.fao.org/faostat/en/#data/RL"


def fetch_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "Novaire-Signal-Flaneur/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def build() -> dict:
    catalog = json.loads(CATALOG.read_text())
    rows = fetch_json(API)[1]
    countries = fetch_json(COUNTRIES_API)[1]
    iso3_by_iso2 = {row["iso2Code"]: row["id"] for row in countries}
    latest = {}
    for row in rows:
        iso3, value = row["countryiso3code"], row["value"]
        if iso3 and value is not None and iso3 not in latest:
            latest[iso3] = {"km2": value, "year": int(row["date"])}

    areas = {}
    missing = []
    for country in catalog:
        code = country["iso2"]
        iso3 = iso3_by_iso2.get(code)
        observation = latest.get(iso3) if iso3 else None
        if observation:
            areas[code] = {**observation, "source": "World Bank / FAO"}
        elif code in FAOSTAT_SUPPLEMENTS:
            areas[code] = {**FAOSTAT_SUPPLEMENTS[code], "source": "FAOSTAT"}
        else:
            missing.append(code)
    if missing:
        raise RuntimeError(f"Missing land area for atlas codes: {', '.join(missing)}")
    if set(areas) != {country["iso2"] for country in catalog}:
        raise RuntimeError("Land-area coverage must exactly equal the atlas catalog")

    world = latest.get("WLD")
    if not world:
        raise RuntimeError("World Bank world land-area denominator is unavailable")
    return {
        "indicator": INDICATOR,
        "unit": "sq. km",
        "scope": "World land area excluding Antarctica; numerator counts each of the 199 atlas countries and destinations once.",
        "denominatorKm2": world["km2"],
        "denominatorYear": world["year"],
        "sources": [
            {"name": "World Bank — Land area (sq. km), sourced from FAO", "url": SOURCE_URL},
            {"name": "FAOSTAT Land Use (supplements for XK, TW and VA)", "url": FAOSTAT_URL},
        ],
        "areas": dict(sorted(areas.items())),
        "refreshedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def validate(data: dict) -> None:
    codes = {country["iso2"] for country in json.loads(CATALOG.read_text())}
    if set(data.get("areas", {})) != codes:
        raise RuntimeError("land_area.json codes do not exactly match countries.json")
    values = [entry.get("km2") for entry in data["areas"].values()]
    if not all(isinstance(value, (int, float)) and value > 0 for value in values):
        raise RuntimeError("Every atlas entry must have a positive land area")
    denominator = data.get("denominatorKm2")
    if not isinstance(denominator, (int, float)) or denominator <= 0:
        raise RuntimeError("A positive world land-area denominator is required")
    if sum(values) > denominator * 1.01:
        raise RuntimeError("Atlas land-area sum unexpectedly exceeds the world denominator")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate the committed dataset without fetching")
    args = parser.parse_args()
    if args.check:
        validate(json.loads(OUTPUT.read_text()))
        return
    data = build()
    validate(data)
    OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
