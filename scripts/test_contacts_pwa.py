"""Regression checks for the isolated Contacts installation and carousel."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contacts-app"
manifest = json.loads((OUT / "manifest.webmanifest").read_text())

assert manifest["id"] == "https://contacts.novairesignal.com/contacts-app"
assert manifest["start_url"] == "https://contacts.novairesignal.com/contacts/"
assert manifest["scope"] == "https://contacts.novairesignal.com/"
assert manifest["name"] == manifest["short_name"] == "Contacts"
assert manifest["display"] == "standalone"
expected = [
    ("Instagram", "https://www.instagram.com/j.novaire/"),
    ("WhatsApp", "https://wa.me/qr/FFFDDLXIDIN2I1"),
    ("Telegram", "https://t.me/JNovaire"),
    ("LinkedIn", "https://www.linkedin.com/in/nolanjamesfyfe/"),
]
for page in (OUT / "index.html", OUT / "contacts" / "index.html"):
    html = page.read_text()
    assert 'rel="manifest" href="https://contacts.novairesignal.com/manifest.webmanifest?v=2"' in html
    assert "https://novairesignal.com/" not in html
    assert re.findall(r'<h2>(.*?)</h2>', html) == [label for label, _ in expected]
    assert re.findall(r'data-url="([^"]+)"', html) == [url for _, url in expected]
    assert len(re.findall(r'class="social-card"', html)) == 4
    assert len(re.findall(r'class="platform-tab"', html)) == 4
    assert 'aria-roledescription="carousel"' in html
    assert 'data-position="active"' in html
    assert "rotateY(var(--r))" in html
    assert "stage.addEventListener('pointerdown'" in html
    assert "Math.abs(dx)>48" in html
    assert "event.key==='ArrowLeft'" in html and "event.key==='ArrowRight'" in html
    assert "navigator.share" in html and "navigator.clipboard.writeText" in html
    assert '@media(prefers-reduced-motion:reduce)' in html
    assert '<meta name="contacts-release" content="2026-10-26-v20">' in html
    assert 'width:min(360px,38svh)' in html
    assert 'width:min(900px,calc(100vw - 180px))' in html
    assert 'height:min(720px,calc(100svh - 190px))' in html
    assert 'width:calc(100vw - 8px)' in html
    assert 'height:calc(100% - 4px)' in html
    assert '@media(max-height:800px) and (min-width:651px)' in html
    assert '.social-card{height:calc(100% - 20px);min-height:0}' in html
    assert 'Digital Card' not in html
    assert '.qr-frame{width:min(calc(100vw - 28px),calc(100svh - 330px));padding:8px}' in html
    assert '.social-card h2{font-size:50px}' in html
    assert '.handle{margin:5px 0 8px;font-size:19px}' in html
    assert '.social-card[data-position="prev"]' in html
    assert '.social-card[data-position="next"]' in html
for slug in ("instagram", "whatsapp", "telegram", "linkedin"):
    assert (OUT / f"{slug}.png").is_file()
    assert f'"/{slug}.png"' in (OUT / "sw.js").read_text()
worker = (OUT / "sw.js").read_text()
assert '"/contacts/"' in worker
assert "novaire-contacts-origin-v20" in worker
assert "event.waitUntil(self.cleanup())" in worker
assert "includeUncontrolled:true" in worker
assert "clients.forEach" in worker
assert "client.navigate(client.url)" in worker
print("contacts revolving card rack regression: PASS")
