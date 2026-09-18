#!/usr/bin/env python3
"""Refresh sourced capital and population facts for every map destination.

Sources:
- Capitals: Wikidata P36 (current statements), with explicit sourced display
  overrides for special/multiple/disputed arrangements.
- Population: World Bank SP.POP.TOTL; UN WPP 2024 only where World Bank has
  no series (currently Taiwan and Vatican City).

Existing valid values are retained if a source regresses or is unavailable.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "countries.json"
OUTPUT = ROOT / "country_facts.json"
WB_API = "https://api.worldbank.org/v2"
WB_INDICATOR = "SP.POP.TOTL"
WB_SOURCE = "https://data.worldbank.org/indicator/SP.POP.TOTL"
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
UN_WPP = "https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/WPP2024_Demographic_Indicators_Medium.csv.gz"
USER_AGENT = "NovaireSignalMap/1.0 (+https://novairesignal.com/map/)"

# Display labels explain arrangements that a bare P36 list cannot represent honestly.
# Every override remains linked to the country's Wikidata entity returned by the query.
CAPITAL_OVERRIDES = {
    "BJ": "Porto-Novo (official); Cotonou (seat of government)",
    "BO": "Sucre (constitutional); La Paz (seat of government)",
    "HK": "Not applicable (special administrative region)",
    "ID": "Nusantara (designated); Jakarta (current government seat)",
    "IL": "Jerusalem (status disputed)",
    "LK": "Sri Jayawardenepura Kotte (legislative); Colombo (executive and judicial)",
    "MY": "Kuala Lumpur (official); Putrajaya (administrative center)",
    "NL": "Amsterdam (constitutional); The Hague (seat of government)",
    "MO": "Not applicable (special administrative region)",
    "PS": "East Jerusalem (claimed); Ramallah (administrative center)",
    "PK": "Islamabad",
    "SZ": "Mbabane (administrative); Lobamba (royal and legislative)",
    "VA": "Vatican City",
    "YE": "Sanaa (de jure); Aden (temporary seat)",
    "ZA": "Pretoria (executive); Cape Town (legislative); Bloemfontein (judicial)",
}


def fetch_json(url: str, timeout: int = 90):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def fetch_capitals() -> tuple[dict[str, dict], str]:
    query = """
SELECT ?country ?iso ?capitalLabel WHERE {
  ?country wdt:P297 ?iso.
  OPTIONAL {
    ?country p:P36 ?statement.
    ?statement ps:P36 ?capital.
    FILTER NOT EXISTS { ?statement pq:P582 ?end. }
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
""".strip()
    url = WIKIDATA_ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    data = fetch_json(url)
    rows: dict[str, dict] = {}
    for binding in data["results"]["bindings"]:
        code = binding["iso"]["value"].upper()
        entity = binding["country"]["value"].replace("http://www.wikidata.org/", "https://www.wikidata.org/")
        row = rows.setdefault(code, {"names": [], "url": entity})
        name = binding.get("capitalLabel", {}).get("value")
        if name and not name.startswith("http") and name not in row["names"]:
            row["names"].append(name)
    return rows, url


def fetch_world_bank(codes: set[str]) -> tuple[dict[str, tuple[int, int]], str, str]:
    years = f"{datetime.now(timezone.utc).year - 6}:{datetime.now(timezone.utc).year}"
    observations_url = f"{WB_API}/country/all/indicator/{WB_INDICATOR}?format=json&date={years}&per_page=20000"
    countries_url = f"{WB_API}/country?format=json&per_page=400"
    metadata = fetch_json(countries_url)[1]
    iso3_to_iso2 = {row["id"]: row["iso2Code"] for row in metadata}
    payload = fetch_json(observations_url)
    result: dict[str, tuple[int, int]] = {}
    for row in payload[1]:
        code = iso3_to_iso2.get(row.get("countryiso3code"))
        value = row.get("value")
        if code in codes and value is not None:
            year = int(row["date"])
            if code not in result or year > result[code][0]:
                result[code] = (year, int(round(float(value))))
    return result, observations_url, payload[0].get("lastupdated", "")


def fetch_un_fallback(codes: set[str], year: int = 2024) -> dict[str, tuple[int, int]]:
    req = urllib.request.Request(UN_WPP, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as response:
        raw = response.read()
    text = io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw)), encoding="utf-8-sig")
    result: dict[str, tuple[int, int]] = {}
    for row in csv.DictReader(text):
        code = row.get("ISO2_code", "").upper()
        if code not in codes or int(row.get("Time", 0)) != year:
            continue
        # UN WPP population columns are in thousands.
        value = row.get("TPopulation1Jan") or row.get("TPopulation")
        if value:
            result[code] = (year, int(round(float(value) * 1000)))
    return result


def validate(payload: dict, codes: set[str]) -> None:
    facts = payload.get("countries", {})
    assert set(facts) == codes, f"country coverage mismatch: missing={sorted(codes-set(facts))} extra={sorted(set(facts)-codes)}"
    for code, fact in facts.items():
        assert fact.get("capital", {}).get("display"), f"{code}: missing capital display"
        assert fact["capital"].get("sourceUrl", "").startswith("https://"), f"{code}: missing capital source"
        population = fact.get("population", {})
        assert isinstance(population.get("value"), int) and population["value"] > 0, f"{code}: invalid population"
        assert isinstance(population.get("year"), int) and 1950 <= population["year"] <= datetime.now().year, f"{code}: invalid year"
        assert population.get("sourceUrl", "").startswith("https://"), f"{code}: missing population source"


def build(previous: dict) -> tuple[dict, dict]:
    catalog = json.loads(CATALOG.read_text())
    codes = {row["iso2"] for row in catalog}
    old = previous.get("countries", {})
    errors: list[str] = []
    try:
        capitals, capital_query = fetch_capitals()
    except Exception as exc:
        capitals, capital_query = {}, WIKIDATA_ENDPOINT
        errors.append(f"Wikidata fetch failed: {exc}")
    try:
        wb, wb_query, wb_updated = fetch_world_bank(codes)
    except Exception as exc:
        wb, wb_query, wb_updated = {}, WB_SOURCE, ""
        errors.append(f"World Bank fetch failed: {exc}")
    missing_wb = codes - set(wb)
    try:
        un = fetch_un_fallback(missing_wb) if missing_wb else {}
    except Exception as exc:
        un = {}
        errors.append(f"UN WPP fetch failed: {exc}")

    facts: dict[str, dict] = {}
    retained = {"capital": [], "population": []}
    unavailable = {"capital": [], "population": []}
    for item in catalog:
        code = item["iso2"]
        cap_row = capitals.get(code, {})
        names = cap_row.get("names", [])
        display = CAPITAL_OVERRIDES.get(code) or "; ".join(names)
        if display:
            capital = {"display": display, "source": "Wikidata", "sourceUrl": cap_row.get("url", WIKIDATA_ENDPOINT)}
        elif old.get(code, {}).get("capital", {}).get("display"):
            capital = old[code]["capital"]
            retained["capital"].append(code)
        else:
            capital = {"display": "Unavailable", "source": "Unavailable", "sourceUrl": capital_query}
            unavailable["capital"].append(code)

        if code in wb:
            year, value = wb[code]
            population = {"value": value, "year": year, "source": "World Bank SP.POP.TOTL", "sourceUrl": f"{WB_API}/country/{code}/indicator/{WB_INDICATOR}?format=json"}
        elif code in un:
            year, value = un[code]
            population = {"value": value, "year": year, "source": "UN World Population Prospects 2024", "sourceUrl": UN_WPP}
        elif old.get(code, {}).get("population", {}).get("value"):
            population = old[code]["population"]
            retained["population"].append(code)
        else:
            population = {"value": None, "year": None, "source": "Unavailable", "sourceUrl": WB_SOURCE}
            unavailable["population"].append(code)
        facts[code] = {"name": item["name"], "capital": capital, "population": population}

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {
        "schemaVersion": 1,
        "refreshedAt": now,
        "refreshNote": "refreshedAt is retrieval metadata, not the population reference year",
        "sources": {
            "capitals": {"name": "Wikidata P36", "url": WIKIDATA_ENDPOINT, "queryUrl": capital_query},
            "populationPrimary": {"name": "World Bank SP.POP.TOTL", "url": WB_SOURCE, "queryUrl": wb_query, "sourceUpdated": wb_updated},
            "populationFallback": {"name": "UN World Population Prospects 2024", "url": UN_WPP},
        },
        "coverage": {
            "mapped": len(codes), "capitalFilled": len(codes)-len(unavailable["capital"]),
            "populationFilled": len(codes)-len(unavailable["population"]), "unavailable": unavailable,
            "retainedFromPreviousOnRegression": retained,
        },
        "countries": facts,
    }
    validate(payload, codes)
    return payload, {"errors": errors, "missingWorldBank": sorted(missing_wb), **payload["coverage"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="fetch and validate without writing")
    parser.add_argument("--check", action="store_true", help="validate the existing file without fetching")
    args = parser.parse_args()
    codes = {row["iso2"] for row in json.loads(CATALOG.read_text())}
    previous = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    if args.check:
        validate(previous, codes)
        print(json.dumps(previous["coverage"], sort_keys=True))
        return 0
    payload, summary = build(previous)
    if not args.dry_run:
        fd, temp_name = tempfile.mkstemp(prefix="country_facts.", suffix=".json", dir=ROOT)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temp_name, OUTPUT)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
