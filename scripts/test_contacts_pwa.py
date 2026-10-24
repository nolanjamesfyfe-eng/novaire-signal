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
    import re
    assert re.findall(r'<h2>(.*?)</h2>', html) == ['Instagram', 'WhatsApp', 'Telegram', 'LinkedIn']
    assert 'src="/telegram.png"' in html
    assert '@media(max-width:700px) and (orientation:portrait)' in html
    assert 'main{max-width:none;padding:24px 12px 36px}' in html
    assert 'min-height:min(78svh,680px)' in html
    assert '.qr-aura{width:100%;max-width:420px}' in html
assert (OUT / 'telegram.png').is_file()
assert '"/telegram.png"' in (OUT / 'sw.js').read_text()
assert '"/contacts/"' in (OUT / "sw.js").read_text()
worker = (OUT / "sw.js").read_text()
assert "novaire-contacts-origin-v11" in worker
assert "includeUncontrolled:true" in worker
assert "clients.forEach" in worker
assert "client.navigate(client.url)" in worker
print("contacts PWA identity regression: PASS")