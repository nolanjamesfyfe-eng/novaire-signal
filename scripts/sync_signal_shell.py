#!/usr/bin/env python3
"""Lock companion shells to the unchanged original Signal component.
Run after any generator and at build time. Never touch homepage output.
"""
from pathlib import Path
import re, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from signal_brand import signal_brand_css, signal_brand_font_link, signal_brand_markup
PAGES=('map/index.html','health/index.html','portfolio/index.html','portfolio/daily/index.html','portfolio/evolutionfund/index.html','portfolio/evolutionfund/philosophy.html','portfolio/finances/index.html','portfolio-lock.html')
LINK='<link rel="stylesheet" href="/signal-shell.css?v=2">'
def sync():
    css=signal_brand_css()+'''\n/* Companion-only cascade boundary. Original homepage remains immutable. */
.signal-brand-row{flex-shrink:0;font-synthesis:none}
.signal-brand-row>*{flex-shrink:0}
.signal-brand-row .signal-wordmark{font-weight:300;text-transform:uppercase}
.signal-brand-row .signal-wordmark>span{font-weight:inherit}
.signal-brand-row .signal-health{color:#b59662}
/* Health has narrow header/footer containers; center the full row, not a shrunken flex box. */
body.signal-health-page .topbar{padding-inline:0}
body.signal-health-page footer{padding-inline:0}
.signal-gate-brand,.signal-gate-footer{display:flex;justify-content:center;width:100%}
.signal-gate-brand{padding-top:32px}.signal-gate-footer{padding:24px 0 32px}
@media(min-width:761px){.signal-gate-brand{padding-top:35.2px}}
/* Match homepage's desktop raster/layout scale without zooming any canvas. */
@media(min-width:900px){body.signal-companion-unzoomed .signal-brand-row{zoom:1.1;transform:scale(.9090909);transform-origin:center top}}
'''
    (ROOT/'signal-shell.css').write_text(css)
    for rel in PAGES:
        p=ROOT/rel
        if not p.exists(): continue
        text=p.read_text()
        # Request the same actual italic face as home, not synthesized 400 italic.
        text=text.replace(signal_brand_font_link(),'')
        if rel.startswith('portfolio/evolutionfund/') and 'family=JetBrains' not in text:
            text=text.replace('</head>','<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"></head>')
        text=text.replace(LINK,'')
        text=text.replace('</head>',signal_brand_font_link()+LINK+'</head>')
        if rel=='health/index.html': text=text.replace('<body>','<body class="signal-health-page">')
        if rel != 'portfolio/index.html' and 'signal-companion-unzoomed' not in text:
            text=re.sub(r'<body(?: class="([^"]*)")?>',lambda m:'<body class="'+(m[1]+' ' if m[1] else '')+'signal-companion-unzoomed">',text,count=1)
        if rel=='portfolio-lock.html' and 'signal-gate-brand' not in text:
            text=re.sub(r'(<body[^>]*>)',lambda m:m[1]+'<header class="signal-gate-brand">'+signal_brand_markup()+'</header>',text,count=1)
            text=text.replace('</body>','<footer class="signal-gate-footer">'+signal_brand_markup()+'</footer></body>')
            text=re.sub(r'<a class="brand" href="/"[^>]*>.*?</a>','',text)
            # Existing lock uses a centered body grid; keep PIN card, not the whole page, centered.
            text=text.replace('</head>','<style>body{display:flex;flex-direction:column;min-height:100svh;padding:0}body>.lock{margin:auto;max-width:calc(100% - 32px)}</style></head>')
        text=re.sub(r'(?m)^ +$', '', text)
        p.write_text(text)
if __name__=='__main__': sync()
