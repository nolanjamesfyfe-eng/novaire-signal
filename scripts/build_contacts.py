"""Build the isolated Contacts PWA bundle for its own web origin."""
from pathlib import Path
import json
import shutil
import qrcode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contacts-app"
OUT.mkdir(exist_ok=True)
PROFILES = [
    ("linkedin", "LinkedIn", "Nolan James Fyfe", "https://www.linkedin.com/in/nolanjamesfyfe/"),
    ("instagram", "Instagram", "@j.novaire", "https://www.instagram.com/j.novaire/"),
    ("whatsapp", "WhatsApp", "Message me", "https://wa.me/qr/FFFDDLXIDIN2I1"),
]

cards = []
for slug, label, subtitle, url in PROFILES:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(OUT / f"{slug}.png")
    cards.append(f'''<a class="card" href="{url}" target="_blank" rel="noopener noreferrer" aria-label="Open {label}: {subtitle}">
<h2>{label}</h2><p class="handle">{subtitle}</p><img src="/{slug}.png" alt="Scan to open my {label}" width="370" height="370"><span class="open">Open {label} <span aria-hidden="true">↗</span></span></a>''')

html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#090909"><title>Contacts · Nolan James Fyfe</title><link rel="icon" href="/icon-192.png"><link rel="manifest" href="https://contacts.novairesignal.com/manifest.webmanifest?v=2"><link rel="apple-touch-icon" href="/icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Contacts"><meta name="apple-mobile-web-app-status-bar-style" content="black"><script>if('serviceWorker' in navigator){{window.addEventListener('load',()=>navigator.serviceWorker.register('/sw.js',{{scope:'/'}}).catch(console.error))}}</script><style>
:root{{color-scheme:dark;--gold:#b59662}}*{{box-sizing:border-box}}body{{margin:0;background:#090909;color:#eeeae2;font-family:Arial,Helvetica,sans-serif;min-height:100svh}}main{{max-width:1060px;margin:auto;padding:48px 24px 28px}}header{{text-align:center;margin-bottom:32px}}.eyebrow{{color:var(--gold);font-size:11px;letter-spacing:3px;text-transform:uppercase;margin:0 0 16px}}h1{{font-family:Georgia,serif;font-size:clamp(30px,6vw,44px);font-weight:400;margin:0 0 12px}}.intro{{font-size:14px;color:#aaa69f;line-height:1.6;margin:0}}#install{{margin:20px 0 0;border:1px solid var(--gold);border-radius:999px;background:var(--gold);color:#090909;padding:11px 18px;font:600 13px Arial;cursor:pointer}}.cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}}.card{{display:block;background:#111110;border:1px solid #302a21;border-radius:16px;padding:24px;text-align:center;text-decoration:none;color:inherit;transition:border-color .15s}}.card:hover{{border-color:var(--gold)}}.card:focus-visible,#install:focus-visible{{outline:3px solid var(--gold);outline-offset:5px}}h2{{font-size:19px;font-weight:500;margin:0 0 8px}}.handle{{font-size:13px;color:#aaa69f;margin:0 0 22px}}.card img{{width:100%;height:auto;display:block;background:white;border-radius:5px;image-rendering:pixelated}}.open{{display:block;color:var(--gold);font-size:13px;margin-top:22px;padding:4px}}footer{{text-align:center;margin-top:30px;font-size:11px;letter-spacing:2px}}footer a{{color:var(--gold);text-decoration:none}}@media(max-width:700px){{main{{max-width:410px;padding:32px 24px}}.cards{{grid-template-columns:1fr;gap:18px}}header{{margin-bottom:24px}}.card{{padding:22px 32px}}.card img{{max-width:250px;margin:auto}}.handle{{margin-bottom:16px}}.open{{margin-top:16px}}}}
</style></head><body><main><header><p class="eyebrow">Let's connect</p><h1>Nolan James Fyfe</h1><p class="intro">Scan a code, or tap to open.</p><button id="install" type="button" hidden>Install Contacts</button></header><section class="cards" aria-label="Social profiles">{''.join(cards)}</section></main><script>
let installPrompt;
const installButton=document.getElementById('install');
window.addEventListener('beforeinstallprompt',event=>{{event.preventDefault();installPrompt=event;installButton.hidden=false}});
installButton.addEventListener('click',async()=>{{if(!installPrompt)return;installPrompt.prompt();await installPrompt.userChoice;installPrompt=null;installButton.hidden=true}});
window.addEventListener('appinstalled',()=>{{installPrompt=null;installButton.hidden=true}});
</script></body></html>'''
(OUT / "index.html").write_text(html)
(OUT / "contacts").mkdir(exist_ok=True)
(OUT / "contacts" / "index.html").write_text(html)

manifest = {
    "id": "https://contacts.novairesignal.com/contacts-app",
    "name": "Contacts",
    "short_name": "Contacts",
    "description": "LinkedIn, Instagram and WhatsApp QR codes for Nolan James Fyfe",
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
(OUT / "sw.js").write_text(f"""const CACHE='novaire-contacts-origin-v2';
const ASSETS={json.dumps(assets, separators=(',', ':'))};
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('novaire-contacts-origin-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{{const url=new URL(event.request.url);if(event.request.method!=='GET'||url.origin!==self.location.origin||!ASSETS.includes(url.pathname))return;event.respondWith(fetch(event.request).then(response=>{{if(response.ok){{const copy=response.clone();event.waitUntil(caches.open(CACHE).then(cache=>cache.put(event.request,copy)));}}return response;}}).catch(()=>caches.match(event.request).then(cached=>cached||Response.error())));}});
""")
for icon in ("icon-192.png", "icon-512.png"):
    shutil.copy2(ROOT / icon, OUT / icon)
print("Built isolated contacts-app PWA bundle")
