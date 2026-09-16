import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "map"


def test_catalog_is_exactly_195_unique_sorted_countries():
    countries = json.loads((MAP / "countries.json").read_text())
    assert len(countries) == 195
    assert len({c["iso2"] for c in countries}) == 195
    assert countries == sorted(countries, key=lambda c: c["name"])
    assert all(len(c["iso2"]) == 2 and c["iso2"].isupper() for c in countries)
    assert {"PS", "VA"} <= {c["iso2"] for c in countries}


def test_every_catalog_country_has_real_geometry():
    countries = json.loads((MAP / "countries.json").read_text())
    world = json.loads((MAP / "world.geojson").read_text())
    assert world["type"] == "FeatureCollection"
    assert len(world["features"]) == 195
    assert {f["properties"]["iso2"] for f in world["features"]} == {c["iso2"] for c in countries}
    assert all(f["geometry"]["type"] in {"Polygon", "MultiPolygon"} for f in world["features"])


def test_public_answers_start_empty_and_page_is_read_only():
    visited = json.loads((MAP / "visited.json").read_text())
    assert visited == {"answers": {}}
    html = (MAP / "index.html").read_text()
    assert "fetch(`./visited.json?t=${Date.now()}`" in html
    assert "cache:'no-store'" in html
    assert "setInterval(loadAnswers,60000)" in html
    assert "fetch(" in html
    assert "method:'POST'" not in html and 'method: "POST"' not in html
    assert "TOTAL=195" in html
