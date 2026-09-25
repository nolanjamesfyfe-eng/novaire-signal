"""Regression checks for the isolated Contacts installation identity."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contacts-app"
manifest = json.loads((OUT / "manifest.webmanifest").read_text())

assert manifest["id"] == "https://contacts.novairesignal.com/contacts-app"
assert manifest["start_url"] == "https://contacts.novairesignal.com/contacts/"
assert manifest["scope"] == "https://contacts.novairesignal.com/"
assert manifest["name"] == manifest["short_name"] == "Contacts"
assert manifest["display"] == "standalone"
for page in (OUT / "index.html", OUT / "contacts" / "index.html"):
    html = page.read_text()
    assert 'rel="manifest" href="https://contacts.novairesignal.com/manifest.webmanifest?v=2"' in html
    assert "https://novairesignal.com/" not in html
assert '"/contacts/"' in (OUT / "sw.js").read_text()
print("contacts PWA identity regression: PASS")