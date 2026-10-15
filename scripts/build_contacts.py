"""Build the isolated Contacts PWA bundle for its own web origin."""
from pathlib import Path
import json
import shutil
import qrcode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contacts-app"
OUT.mkdir(exist_ok=True)
PROFILES = [
    ("instagram", "Instagram", "@j.novaire", "https://www.instagram.com/j.novaire/"),
    ("linkedin", "LinkedIn", "Nolan James", "https://www.linkedin.com/in/nolanjamesfyfe/"),
    ("whatsapp", "WhatsApp", "Message me", "https://wa.me/qr/FFFDDLXIDIN2I1"),
]

cards = []
for slug, label, subtitle, url in PROFILES:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(OUT / f"{slug}.png")
    cards.append(f'''<article class="card" aria-label="{label} QR code">
<h2>{label}</h2><div class="qr-aura"><img src="/{slug}.png" alt="Scan to open my {label}" width="370" height="370"></div></article>''')

html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#090909"><title>Contacts · Nolan James</title><link rel="icon" href="/icon-192.png"><link rel="manifest" href="https://contacts.novairesignal.com/manifest.webmanifest?v=2"><link rel="apple-touch-icon" href="/icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Contacts"><meta name="apple-mobile-web-app-status-bar-style" content="black"><script>if('serviceWorker' in navigator){{window.addEventListener('load',()=>navigator.serviceWorker.register('/sw.js',{{scope:'/'}}).catch(console.error))}}</script><style>
:root{{color-scheme:dark;--gold:#b59662}}*{{box-sizing:border-box}}body{{margin:0;background:#090909;color:#eeeae2;font-family:Arial,Helvetica,sans-serif;min-height:100svh}}main{{max-width:1060px;margin:auto;padding:48px 24px 28px}}header{{text-align:center;margin-bottom:32px}}.eyebrow{{color:var(--gold);font-size:11px;letter-spacing:3px;text-transform:uppercase;margin:0 0 16px}}h1{{font-family:Georgia,serif;font-size:clamp(30px,6vw,44px);font-weight:400;margin:0 0 12px}}.intro{{font-size:14px;color:#aaa69f;line-height:1.6;margin:0}}#install{{margin:20px 0 0;border:1px solid var(--gold);border-radius:999px;background:var(--gold);color:#090909;padding:11px 18px;font:600 13px Arial;cursor:pointer}}.cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}}.card{{display:block;background:#111110;border:1px solid #302a21;border-radius:16px;padding:24px;text-align:center;text-decoration:none;color:inherit;transition:border-color .15s}}.card:hover{{border-color:var(--gold)}}.card:focus-visible,#install:focus-visible{{outline:3px solid var(--gold);outline-offset:5px}}h2{{font-size:19px;font-weight:500;margin:0 0 8px}}.handle{{font-size:13px;color:#aaa69f;margin:0 0 22px}}.card img{{width:100%;height:auto;display:block;background:white;border-radius:5px;image-rendering:pixelated}}.open{{display:block;color:var(--gold);font-size:13px;margin-top:22px;padding:4px}}footer{{text-align:center;margin-top:30px;font-size:11px;letter-spacing:2px}}footer a{{color:var(--gold);text-decoration:none}}@media(max-width:700px){{main{{max-width:410px;padding:32px 24px}}.cards{{grid-template-columns:1fr;gap:18px}}header{{margin-bottom:24px}}.card{{padding:22px 32px}}.card img{{max-width:250px;margin:auto}}.handle{{margin-bottom:16px}}.open{{margin-top:16px}}}}
/* Signal-inspired luminous business cards. Keep QR modules untouched. */
body{{background:radial-gradient(ellipse at 50% 0%,#28201666,transparent 65%),#090909}}header::before{{content:'';display:block;width:38px;height:1px;background:var(--gold);box-shadow:0 0 18px #d5b477;margin:0 auto 24px}}h1{{letter-spacing:-1px}}.cards{{gap:26px}}.card{{position:relative;isolation:isolate;background:linear-gradient(145deg,#211c15,#10100f 48%,#16130f);border:1px solid #76603c80;border-radius:22px;padding:28px 24px;box-shadow:inset 0 1px 0 #e8d5a719,0 16px 40px #0008;transition:transform .3s,border-color .3s,box-shadow .3s}}.card:hover{{transform:translateY(-5px);border-color:#d6b475;box-shadow:0 20px 50px #0009,0 0 30px #b5966220}}h2{{letter-spacing:.5px;color:#f4e6cc}}.qr-aura{{position:relative;padding:5px;border-radius:12px;background:linear-gradient(135deg,#f5dc9d,#8f6934 45%,#f3d99c);box-shadow:0 0 12px #ebc57860,0 0 35px #b5966240,0 0 65px #b5966220;animation:signal-glow 4s ease-in-out infinite}}.qr-aura::before{{content:'';position:absolute;inset:-14px;border:1px solid #b596622c;border-radius:23px;pointer-events:none}}.card img{{position:relative;border-radius:7px;max-width:none}}.handle{{margin-bottom:30px}}.open{{margin-top:30px;letter-spacing:1.2px;font-size:11px;text-transform:uppercase;color:#dfc38e}}.card:nth-child(2) .qr-aura{{animation-delay:-1.3s}}.card:nth-child(3) .qr-aura{{animation-delay:-2.6s}}@keyframes signal-glow{{0%,100%{{box-shadow:0 0 12px #ebc57860,0 0 35px #b5966240,0 0 65px #b5966220}}50%{{box-shadow:0 0 20px #ebc57890,0 0 48px #b5966260,0 0 85px #b5966233}}}}@media(max-width:700px){{main{{padding:30px 24px 40px}}.cards{{gap:26px}}.card{{padding:25px 32px}}.qr-aura{{max-width:260px;margin:auto}}.card img{{max-width:none}}}}@media(prefers-reduced-motion:reduce){{.qr-aura{{animation:none}}.card{{transition:none}}.card:hover{{transform:none}}}}
h1.wordmark{{font-family:'Cormorant Garamond',Georgia,serif;font-size:28.8px;font-weight:300;line-height:1;text-transform:uppercase;letter-spacing:.18em;color:#f0eef8;margin:0 0 14px;padding-left:.18em}}.identity{{font-size:13px;letter-spacing:2px;color:#aaa69f;margin:0}}h2{{margin-bottom:30px}}.card{{padding-bottom:34px}}.card:hover{{transform:none}}@media(min-width:761px){{h1.wordmark{{font-size:31.68px}}}}
</style><link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300&display=swap" rel="stylesheet"></head><body><main><header><h1 class="wordmark">Novaire</h1><p class="identity">Nolan James</p></header><section class="cards" aria-label="Social profiles">{''.join(cards)}</section></main></body></html>'''
(OUT / "index.html").write_text(html)
(OUT / "contacts").mkdir(exist_ok=True)
(OUT / "contacts" / "index.html").write_text(html)

manifest = {
    "id": "https://contacts.novairesignal.com/contacts-app",
    "name": "Contacts",
    "short_name": "Contacts",
    "description": "LinkedIn, Instagram and WhatsApp QR codes for Nolan James",
    "start_url": "https://contacts.novairesignal.com/contacts/",
    "scope": "https://contacts.novairesignal.com/",
    "display": "standalone",
    "background_color": "#090909",
    "theme_color": "#090909",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    ],
}
(OUT / "manifest.webmanifest").write_text(json.dumps(manifest, indent=2) + "\n")
assets = ["/", "/index.html", "/contacts/", "/contacts/index.html", "/linkedin.png", "/instagram.png", "/whatsapp.png", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"]
(OUT / "sw.js").write_text(f"""const CACHE='novaire-contacts-origin-v4';
const ASSETS={json.dumps(assets, separators=(',', ':'))};
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('novaire-contacts-origin-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{{const url=new URL(event.request.url);if(event.request.method!=='GET'||url.origin!==self.location.origin||!ASSETS.includes(url.pathname))return;event.respondWith(fetch(event.request).then(response=>{{if(response.ok){{const copy=response.clone();event.waitUntil(caches.open(CACHE).then(cache=>cache.put(event.request,copy)));}}return response;}}).catch(()=>caches.match(event.request).then(cached=>cached||Response.error())));}});
""")
for icon in ("icon-192.png", "icon-512.png"):
    shutil.copy2(ROOT / icon, OUT / icon)
print("Built isolated contacts-app PWA bundle")
