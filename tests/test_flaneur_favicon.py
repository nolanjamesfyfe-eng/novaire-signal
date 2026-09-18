import ast
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

def test_flaneur_has_its_own_gold_globe_favicon():
    html = (ROOT / 'map/index.html').read_text()
    assert '<link rel="icon" type="image/svg+xml" href="/map/favicon-globe.svg?v=1">' in html
    icon = ET.fromstring((ROOT / 'map/favicon-globe.svg').read_text())
    assert icon.attrib['viewBox'] == '.85 .85 22.3 22.3'
    assert icon.find('{*}g').attrib['fill'] == '#b59662'
    source = ast.parse((ROOT / 'generate.py').read_text())
    original = next(ast.literal_eval(n.value) for n in source.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SIGNAL_MAP_SVG' for t in n.targets))
    assert [p.attrib['d'] for p in icon.findall('.//{*}path')] == [p.attrib['d'] for p in ET.fromstring(original).findall('.//path')]
