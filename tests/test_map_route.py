import json
import importlib.util
import re
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "map"


def load_refresh_module():
    spec = importlib.util.spec_from_file_location("refresh_country_facts", MAP / "refresh_country_facts.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_is_exactly_199_unique_sorted_countries():
    countries = json.loads((MAP / "countries.json").read_text())
    assert len(countries) == 199
    assert len({c["iso2"] for c in countries}) == 199
    assert countries == sorted(countries, key=lambda c: c["name"])
    assert all(len(c["iso2"]) == 2 and c["iso2"].isupper() for c in countries)
    assert {"PS", "VA"} <= {c["iso2"] for c in countries}


def test_every_catalog_country_has_real_geometry():
    countries = json.loads((MAP / "countries.json").read_text())
    world = json.loads((MAP / "world.geojson").read_text())
    assert world["type"] == "FeatureCollection"
    assert len(world["features"]) == 199
    assert {f["properties"]["iso2"] for f in world["features"]} == {c["iso2"] for c in countries}
    assert all(f["geometry"]["type"] in {"Polygon", "MultiPolygon"} for f in world["features"])


def test_public_answers_are_valid_and_page_is_read_only():
    visited = json.loads((MAP / "visited.json").read_text())
    codes = {c['iso2'] for c in json.loads((MAP / 'countries.json').read_text())}
    assert set(visited['answers']) <= codes
    assert all(type(v) is bool for v in visited['answers'].values())
    html = (MAP / "index.html").read_text()
    assert 'src="/map/d3.min.js"' in html
    assert "fetch('/map/countries.json')" in html
    assert "fetch('/map/world-globe.geojson')" in html
    assert "fetch(`/map/visited.json?t=${Date.now()}`" in html
    assert "cache:'no-store'" in html
    assert "setInterval(loadAnswers,60000)" in html
    assert "fetch(" in html
    assert "method:'POST'" not in html and 'method: "POST"' not in html
    assert "TOTAL=199" in html


def test_every_map_feature_has_sourced_capital_and_population():
    countries = json.loads((MAP / "countries.json").read_text())
    world = json.loads((MAP / "world.geojson").read_text())
    facts = json.loads((MAP / "country_facts.json").read_text())
    catalog_codes = {c["iso2"] for c in countries}
    feature_codes = {f["properties"]["iso2"] for f in world["features"]}
    assert feature_codes == catalog_codes == set(facts["countries"])
    assert facts["coverage"]["mapped"] == 199
    assert facts["coverage"]["capitalFilled"] == 199
    assert facts["coverage"]["populationFilled"] == 199
    for code, fact in facts["countries"].items():
        display = fact["capital"]["display"]
        assert display and display != "Unavailable", code
        assert not re.search(r"(?<![A-Za-z0-9])Q\d+(?![A-Za-z0-9])", display), code
        assert not display.startswith(("http://", "https://")), code
        assert fact["capital"]["sourceUrl"].startswith("https://"), code
        assert fact["population"]["value"] > 0, code
        assert 1950 <= fact["population"]["year"] <= 2100, code
        assert fact["population"]["rank"] > 0, code
        assert fact["population"]["sourceUrl"].startswith("https://"), code
        gdp = fact["gdp"]
        if gdp["value"] is None:
            assert gdp["rank"] is None, code
        else:
            assert gdp["value"] > 0 and gdp["year"] == 2025 and gdp["rank"] > 0, code
            assert gdp["indicator"] == "NGDPD"
            assert gdp["unit"] == "billions current U.S. dollars"

    assert facts["coverage"]["populationRankUniverse"] == 219
    assert facts["coverage"]["gdpFilled"] == 191
    assert facts["coverage"]["gdpUnavailable"] == ["CU", "ER", "KP", "LK", "MC", "PS", "SY", "VA"]
    assert facts["countries"]["IN"]["population"]["rank"] == 1
    assert facts["countries"]["CN"]["population"]["rank"] == 2
    assert facts["countries"]["US"]["gdp"]["rank"] == 1
    assert facts["countries"]["CN"]["gdp"]["rank"] == 2
    assert facts["countries"]["IN"]["gdp"]["rank"] == 6
    assert facts["countries"]["CA"]["gdp"]["rank"] == 10
    assert facts["sources"]["gdpNominal"]["vintage"] == "World Economic Outlook (April 2026)"
    assert facts["sources"]["gdpNominal"]["unit"] == "Billions of U.S. dollars"
    assert facts["sources"]["gdpNominal"]["rankUniverse"] == 193


def test_refresh_validator_rejects_unresolved_wikidata_capital_ids():
    refresh = load_refresh_module()
    payload = json.loads((MAP / "country_facts.json").read_text())
    broken = deepcopy(payload)
    broken["countries"]["AG"]["capital"]["display"] = "Q36262"
    with pytest.raises(AssertionError, match="AG: invalid capital display"):
        refresh.validate(broken, set(payload["countries"]))


def test_map_tooltip_loads_facts_and_uses_reference_year():
    html = (MAP / "index.html").read_text()
    assert "fetch('/map/country_facts.json')" in html
    assert '<b>Capital:</b>' in html
    assert '<b>Population:</b>' in html
    assert '<b>GDP:</b>' in html
    assert "compactPopulation(pop.value)" in html
    assert "compactGDP(gdp.value)" in html
    assert "pop.rank" in html and "gdp.rank" in html
    assert "pop.year" in html
    assert "refreshedAt" not in html
    assert "nominal current USD · 2025 estimates" in html


def test_competition_rank_ties_and_old_year_regression_contract():
    refresh = load_refresh_module()
    assert refresh.ranked({"A": 10, "B": 10, "C": 8}) == {"A": 1, "B": 1, "C": 3}
    facts = json.loads((MAP / "country_facts.json").read_text())
    assert facts["countries"]["TW"]["population"]["year"] == 2024
    assert facts["countries"]["VA"]["population"]["year"] == 2024
    assert all(fact["population"]["year"] == 2025 for code, fact in facts["countries"].items() if code not in {"TW", "VA"})
