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
    assert "fetch('/map/world.geojson')" in html
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
        assert fact["population"]["sourceUrl"].startswith("https://"), code


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
    assert "compactPopulation(pop.value)" in html
    assert "pop.year" in html
    assert "refreshedAt" not in html
    assert ".toFixed(1)+'B'" in html
    assert "Math.round(value/1e6)+'M'" in html
