"""Render the Contacts-only noir/gold address-book app identity."""
from pathlib import Path
from PIL import Image
import cairosvg

OUT = Path(__file__).resolve().parents[1] / 'contacts-app'
SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
<defs>
 <radialGradient id="bg" cx="40%" cy="20%" r="90%"><stop stop-color="#30271b"/><stop offset=".6" stop-color="#111110"/><stop offset="1" stop-color="#090909"/></radialGradient>
 <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#f0d8a0"/><stop offset=".35" stop-color="#b59662"/><stop offset=".65" stop-color="#8c6c3f"/><stop offset="1" stop-color="#d8b97e"/></linearGradient>
 <linearGradient id="cover"><stop stop-color="#282219"/><stop offset=".25" stop-color="#171612"/><stop offset="1" stop-color="#10100f"/></linearGradient>
</defs>
<rect width="512" height="512" fill="url(#bg)"/>
<rect x="45" y="45" width="422" height="422" rx="92" fill="none" stroke="#b59662" stroke-opacity=".22" stroke-width="2"/>
<!-- Gilt page block and three address index tabs. -->
<rect x="145" y="107" width="226" height="314" rx="23" fill="#080808" opacity=".6"/>
<rect x="139" y="97" width="226" height="314" rx="22" fill="url(#gold)"/>
<path d="M165 392H345M165 399H345" stroke="#493a24" stroke-width="2"/>
<rect x="351" y="151" width="28" height="43" rx="8" fill="url(#gold)"/>
<rect x="351" y="211" width="28" height="43" rx="8" fill="url(#gold)"/>
<rect x="351" y="271" width="28" height="43" rx="8" fill="url(#gold)"/>
<!-- Leather cover, gold tooling, spine. -->
<rect x="126" y="91" width="232" height="304" rx="20" fill="url(#cover)" stroke="url(#gold)" stroke-width="7"/>
<path d="M163 96V389" stroke="#b59662" stroke-width="3"/>
<rect x="178" y="112" width="158" height="260" rx="8" fill="none" stroke="#b59662" stroke-opacity=".42" stroke-width="2"/>
<path d="M116 150H140M116 212H140M116 274H140M116 336H140" stroke="#090909" stroke-width="15" stroke-linecap="round"/>
<path d="M116 147H140M116 209H140M116 271H140M116 333H140" stroke="url(#gold)" stroke-width="9" stroke-linecap="round"/>
<!-- Gold embossed contact silhouette, recognizable at launcher size. -->
<circle cx="257" cy="205" r="29" fill="url(#gold)"/>
<path d="M207 284C207 251 229 242 257 242S307 251 307 284V292H207Z" fill="url(#gold)"/>
<path d="M230 326H284" stroke="#b59662" stroke-width="3"/>
</svg>'''

def build_icons():
    OUT.mkdir(exist_ok=True)
    (OUT / 'contacts-icon.svg').write_text(SVG)
    for size in (192, 512):
        cairosvg.svg2png(bytestring=SVG.encode(), write_to=str(OUT / f'contacts-gold-{size}.png'), output_width=size, output_height=size)
    # Keep the entire book comfortably within Android's circular safe zone.
    image = Image.open(OUT / 'contacts-gold-512.png').convert('RGB')
    maskable = Image.new('RGB', (512, 512), '#090909')
    maskable.paste(image.resize((440, 440), Image.Resampling.LANCZOS), (36, 36))
    maskable.save(OUT / 'contacts-gold-maskable-512.png')
    image.resize((48, 48), Image.Resampling.LANCZOS).save(OUT / 'favicon.ico', sizes=[(48, 48), (32, 32), (16, 16)])

if __name__ == '__main__':
    build_icons()
