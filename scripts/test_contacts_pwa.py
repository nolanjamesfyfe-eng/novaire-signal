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
    assert '<meta name="contacts-release" content="2026-10-25-v16">' in html
    assert 'width:clamp(205px,29svh,265px)' in html
    assert '.social-card[data-position="prev"]' in html
    assert '.social-card[data-position="next"]' in html
for slug in ("instagram", "whatsapp", "telegram", "linkedin"):
    assert (OUT / f"{slug}.png").is_file()
    assert f'"/{slug}.png"' in (OUT / "sw.js").read_text()
worker = (OUT / "sw.js").read_text()
assert '"/contacts/"' in worker
assert "novaire-contacts-origin-v16" in worker
assert "event.waitUntil(self.cleanup())" in worker
assert "includeUncontrolled:true" in worker
assert "clients.forEach" in worker
assert "client.navigate(client.url)" in worker
print("contacts revolving card rack regression: PASS")
