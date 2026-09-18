#!/usr/bin/env python3
"""Refresh sourced capital, population, and nominal GDP facts for the map.

Sources:
- Capitals: Wikidata P36 (current statements), with explicit sourced display
  overrides for special/multiple/disputed arrangements.
- Population: World Bank SP.POP.TOTL; UN WPP 2024 only where World Bank has
  no series (currently Taiwan and Vatican City).
- GDP: IMF World Economic Outlook NGDPD, current prices in billions of U.S.
  dollars. Rankings use only IMF country/economy codes, never aggregates.

Existing valid values are retained if a source regresses or is unavailable.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import re
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
IMF_API = "https://www.imf.org/external/datamapper/api/v1"
IMF_SOURCE = "https://www.imf.org/external/datamapper/NGDPD@WEO/WEOWORLD"
IMF_INDICATOR = "NGDPD"
USER_AGENT = "NovaireSignalMap/1.0 (+https://novairesignal.com/map/)"

# Display labels explain arrangements that a bare P36 list cannot represent honestly.
# Every override remains linked to the country's Wikidata entity returned by the query.
CAPITAL_OVERRIDES = {
    "AG": "St. John's",
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
    # The truthy P36 path returns Wikidata's best-ranked statements, avoiding
    # normal-ranked historical capitals when a preferred current value exists.
    ?country wdt:P36 ?capital.
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul,en-gb". }
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
        if valid_capital_display(name) and name not in row["names"]:
            row["names"].append(name)
    return rows, url


def fetch_world_bank(codes: set[str]) -> tuple[dict[str, tuple[int, int]], dict[str, tuple[int, int]], str, str]:
    years = f"{datetime.now(timezone.utc).year - 6}:{datetime.now(timezone.utc).year}"
    observations_url = f"{WB_API}/country/all/indicator/{WB_INDICATOR}?format=json&date={years}&per_page=20000"
    countries_url = f"{WB_API}/country?format=json&per_page=400"
    metadata = fetch_json(countries_url)[1]
    iso3_to_iso2 = {row["id"]: row["iso2Code"] for row in metadata}
    economy_iso3 = {row["id"] for row in metadata if row.get("region", {}).get("id") != "NA"}
    payload = fetch_json(observations_url)
    result: dict[str, tuple[int, int]] = {}
    universe: dict[str, tuple[int, int]] = {}
    for row in payload[1]:
        code = iso3_to_iso2.get(row.get("countryiso3code"))
        value = row.get("value")
        if row.get("countryiso3code") in economy_iso3 and value is not None:
            year = int(row["date"])
            if code and (code not in universe or year > universe[code][0]):
                universe[code] = (year, int(round(float(value))))
            if code not in result or year > result[code][0]:
                if code in codes:
                    result[code] = (year, int(round(float(value))))
    return result, universe, observations_url, payload[0].get("lastupdated", "")


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


def ranked(values: dict[str, int | float]) -> dict[str, int]:
    """Return competition ranks; exact ties share a rank."""
    result: dict[str, int] = {}
    previous = None
    previous_rank = 0
    for position, (code, value) in enumerate(sorted(values.items(), key=lambda item: (-item[1], item[0])), 1):
        if value != previous:
            previous_rank, previous = position, value
        result[code] = previous_rank
    return result


def fetch_imf_gdp(codes: set[str]) -> tuple[dict[str, dict], dict]:
    indicator = fetch_json(f"{IMF_API}/indicators")["indicators"][IMF_INDICATOR]
    countries = fetch_json(f"{IMF_API}/countries")["countries"]
    series = fetch_json(f"{IMF_API}/{IMF_INDICATOR}")["values"][IMF_INDICATOR]
    assert indicator["unit"] == "Billions of U.S. dollars", indicator["unit"]
    wb_metadata = fetch_json(f"{WB_API}/country?format=json&per_page=400")[1]
    iso3_to_iso2 = {row["id"]: row["iso2Code"] for row in wb_metadata}
    iso3_to_iso2.update({"UVK": "XK", "TWN": "TW"})
    year = 2025
    # IMF's countries endpoint is the allowlist: analytical/regional aggregates
    # such as WEOWORLD appear in the series endpoint but not in this collection.
    universe = {
        imf_code: float(series[imf_code][str(year)])
        for imf_code in countries
        if series.get(imf_code, {}).get(str(year)) is not None
    }
    assert len(universe) >= 180, f"partial IMF GDP snapshot: {len(universe)} economies"
    ranks = ranked(universe)
    mapped: dict[str, dict] = {}
    for imf_code, value in universe.items():
        code = iso3_to_iso2.get(imf_code)
        if code in codes:
            mapped[code] = {
                "value": value, "year": year, "rank": ranks[imf_code],
                "unit": "billions current U.S. dollars", "indicator": IMF_INDICATOR,
                "estimate": True, "source": indicator["source"], "sourceUrl": IMF_SOURCE,
            }
    metadata = {
        "name": f"IMF {indicator['source']} {IMF_INDICATOR}", "url": IMF_SOURCE,
        "apiUrl": f"{IMF_API}/{IMF_INDICATOR}", "unit": indicator["unit"],
        "referenceYear": year, "vintage": indicator["source"],
        "sourceLastModified": indicator.get("last-modified", ""),
        "rankUniverse": len(universe),
        "rankRule": "IMF country/economy codes with a 2025 NGDPD value; IMF analytical and regional aggregates excluded",
    }
    return mapped, metadata


def valid_capital_display(value: object) -> bool:
    """Reject missing placeholders, entity IDs, and unresolved entity URLs."""
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value != "Unavailable"
        and not value.startswith(("http://", "https://"))
        and re.search(r"(?<![A-Za-z0-9])Q\d+(?![A-Za-z0-9])", value) is None
    )


def validate(payload: dict, codes: set[str]) -> None:
    facts = payload.get("countries", {})
    assert set(facts) == codes, f"country coverage mismatch: missing={sorted(codes-set(facts))} extra={sorted(set(facts)-codes)}"
    for code, fact in facts.items():
        assert valid_capital_display(fact.get("capital", {}).get("display")), f"{code}: invalid capital display"
        assert fact["capital"].get("sourceUrl", "").startswith("https://"), f"{code}: missing capital source"
        population = fact.get("population", {})
        assert isinstance(population.get("value"), int) and population["value"] > 0, f"{code}: invalid population"
        assert isinstance(population.get("year"), int) and 1950 <= population["year"] <= datetime.now().year, f"{code}: invalid year"
        assert isinstance(population.get("rank"), int) and population["rank"] > 0, f"{code}: invalid population rank"
        assert population.get("sourceUrl", "").startswith("https://"), f"{code}: missing population source"
        gdp = fact.get("gdp", {})
        if gdp.get("value") is not None:
            assert isinstance(gdp["value"], (int, float)) and gdp["value"] > 0, f"{code}: invalid GDP"
            assert gdp.get("year") == 2025 and isinstance(gdp.get("rank"), int), f"{code}: invalid GDP rank/year"
            assert gdp.get("indicator") == IMF_INDICATOR and gdp.get("unit") == "billions current U.S. dollars", f"{code}: invalid GDP units"
        else:
            assert gdp.get("rank") is None, f"{code}: unavailable GDP cannot have rank"


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
        wb, wb_universe, wb_query, wb_updated = fetch_world_bank(codes)
    except Exception as exc:
        wb, wb_universe, wb_query, wb_updated = {}, {}, WB_SOURCE, ""
        errors.append(f"World Bank fetch failed: {exc}")
    missing_wb = codes - set(wb)
    try:
        un = fetch_un_fallback(missing_wb) if missing_wb else {}
    except Exception as exc:
        un = {}
        errors.append(f"UN WPP fetch failed: {exc}")

    population_snapshot_complete = len(wb_universe) >= 200 and not (missing_wb - set(un))
    if population_snapshot_complete and old:
        incoming = {**wb, **un}
        population_snapshot_complete = all(
            code in incoming and incoming[code][0] >= old[code]["population"].get("year", 0)
            for code in codes
        )
    population_ranks: dict[str, int] = {}
    if population_snapshot_complete:
        population_universe = {code: value for code, (_, value) in wb_universe.items()}
        population_universe.update({code: value for code, (_, value) in un.items()})
        population_ranks = ranked(population_universe)
    else:
        errors.append("Population snapshot incomplete; retaining the entire prior ranked population snapshot")

    try:
        gdp_rows, gdp_metadata = fetch_imf_gdp(codes)
        previous_universe = previous.get("sources", {}).get("gdpNominal", {}).get("rankUniverse", 0)
        if previous_universe and gdp_metadata["rankUniverse"] < previous_universe:
            raise ValueError(f"IMF rank universe regressed from {previous_universe} to {gdp_metadata['rankUniverse']}")
    except Exception as exc:
        gdp_rows = {}
        gdp_metadata = previous.get("sources", {}).get("gdpNominal", {})
        errors.append(f"IMF WEO GDP fetch failed; retained prior complete GDP snapshot: {exc}")

    facts: dict[str, dict] = {}
    retained = {"capital": [], "population": [], "gdp": []}
    unavailable = {"capital": [], "population": [], "gdp": []}
    for item in catalog:
        code = item["iso2"]
        cap_row = capitals.get(code, {})
        names = cap_row.get("names", [])
        display = CAPITAL_OVERRIDES.get(code) or "; ".join(names)
        if display:
            capital = {"display": display, "source": "Wikidata", "sourceUrl": cap_row.get("url", WIKIDATA_ENDPOINT)}
        elif valid_capital_display(old.get(code, {}).get("capital", {}).get("display")):
            capital = old[code]["capital"]
            retained["capital"].append(code)
        else:
            capital = {"display": "Unavailable", "source": "Unavailable", "sourceUrl": capital_query}
            unavailable["capital"].append(code)

        candidate = None
        if population_snapshot_complete and code in wb:
            year, value = wb[code]
            candidate = {"value": value, "year": year, "rank": population_ranks[code], "source": "World Bank SP.POP.TOTL", "sourceUrl": f"{WB_API}/country/{code}/indicator/{WB_INDICATOR}?format=json"}
        elif population_snapshot_complete and code in un:
            year, value = un[code]
            candidate = {"value": value, "year": year, "rank": population_ranks[code], "source": "UN World Population Prospects 2024", "sourceUrl": UN_WPP}
        old_population = old.get(code, {}).get("population", {})
        if candidate and old_population.get("value") and old_population.get("year", 0) > candidate["year"]:
            population = old_population
            retained["population"].append(code)
        elif candidate:
            population = candidate
        elif old_population.get("value"):
            population = old_population
            retained["population"].append(code)
        else:
            population = {"value": None, "year": None, "source": "Unavailable", "sourceUrl": WB_SOURCE}
            unavailable["population"].append(code)
        if code in gdp_rows:
            gdp = gdp_rows[code]
        elif old.get(code, {}).get("gdp", {}).get("value") is not None and not gdp_rows:
            gdp = old[code]["gdp"]
            retained["gdp"].append(code)
        else:
            gdp = {"value": None, "year": 2025, "rank": None, "unit": "billions current U.S. dollars", "indicator": IMF_INDICATOR, "estimate": True, "source": gdp_metadata.get("vintage", "IMF World Economic Outlook"), "sourceUrl": IMF_SOURCE}
            unavailable["gdp"].append(code)
        facts[code] = {"name": item["name"], "capital": capital, "population": population, "gdp": gdp}

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {
        "schemaVersion": 2,
        "refreshedAt": now,
        "refreshNote": "refreshedAt is retrieval metadata, not the population reference year",
        "sources": {
            "capitals": {"name": "Wikidata P36", "url": WIKIDATA_ENDPOINT, "queryUrl": capital_query},
            "populationPrimary": {"name": "World Bank SP.POP.TOTL", "url": WB_SOURCE, "queryUrl": wb_query, "sourceUpdated": wb_updated},
            "populationFallback": {"name": "UN World Population Prospects 2024", "url": UN_WPP},
            "gdpNominal": gdp_metadata,
        },
        "coverage": {
            "mapped": len(codes), "capitalFilled": len(codes)-len(unavailable["capital"]),
            "populationFilled": len(codes)-len(unavailable["population"]),
            "populationRankUniverse": len(population_ranks) or previous.get("coverage", {}).get("populationRankUniverse"),
            "populationRankRule": "Latest available World Bank SP.POP.TOTL observation per non-aggregate economy, plus UN WPP 2024 for Taiwan and Vatican City; unrounded values; mixed reference years are stored per economy",
            "gdpFilled": len(codes)-len(unavailable["gdp"]),
            "gdpUnavailable": sorted(unavailable["gdp"]), "unavailable": unavailable,
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
