"""Canonical Novaire Signal brand markup and styles shared by generated pages."""

SIGNAL_BOLT_SVG = (
    '<svg class="signal-bolt-icon" viewBox="45 38 200 264" aria-hidden="true" focusable="false">'
    '<path fill="currentColor" d="M219 44Q217 43 215 44L51 180Q49 183 51 185Q53 187 56 187L130 186Q132 186 132 188L72 289Q70 293 73 295Q76 297 83 291L239 155Q241 153 239 149Q238 147 236 147L166 148Q162 148 160 146L219 51Q222 46 219 44Z"/>'
    '</svg>'
)

SIGNAL_MAP_SVG = (
    '<svg class="signal-map-icon" viewBox=".85 .85 22.3 22.3" aria-hidden="true" focusable="false">'
    '<circle class="signal-map-ocean" cx="12" cy="12" r="10.25"/>'
    '<g class="signal-map-land">'
    '<path d="M3.08 8.67 4.2 6.43l1.7-1.67 2.29-1.34 2.03-.68 1.02.42-.43.88-1.61.44-.56.9-1.02.18-.42 1.18-1.12.16-.35 1.2.7 1.14 1.47.49.63.9-.16 1.14-1.02.66-.34 1.14-1.1-.04-.55-1.02-1.28-.5-.7-1.45-1.05-.81-.49-1.07Z"/>'
    '<path d="m9.12 13.04 1.05-.52 1.39.33.91 1.06-.17 1.36-.78 1.15-.22 1.6-.83 1.13-.31 1.7-.67.69-.73-1.43-.54-1.78-.1-1.47-.67-1.18.58-1.08.2-.86Z"/>'
    '<path d="m12.45 2.06 1.29-.23 1.06.38-.24.73-1.23.41-.88-.38Z"/>'
    '<path d="m13.42 5.04 1.08-.83 2.25-.47 2.03.75 1.39 1.23.65 1.17-.63.74-1.46-.27-.83.48-1.18-.53-.93.5-1.05-.31-.86-.98-.98-.17-.43-.65Z"/>'
    '<path d="m14.26 8.23 1.18-.39 1.24.44.82 1.08-.13 1.56-.72 1.14-.36 1.88-.98 1.77-.9.65-.7-1.03-.23-1.66-.78-1.22.25-1.54-.37-1.2.41-1.04Z"/>'
    '<path d="m17.57 16.51 1.24-.55 1.28.28.76.82-.24 1.12-1.12.64-1.3-.17-.75-.83Z"/>'
    '</g><circle class="signal-map-rim" cx="12" cy="12" r="10.25"/></svg>'
)


def signal_brand_markup(*, wordmark_link=True):
    wordmark = '<a href="/" class="signal-wordmark" aria-label="Novaire Signal home">Novaire <span>Signal</span></a>' if wordmark_link else '<span class="signal-wordmark">Novaire <span>Signal</span></span>'
    return f'<div class="signal-brand-row" aria-label="Novaire Signal navigation"><a href="/flaneur" class="signal-map" title="Flâneur happenings" aria-label="Flâneur happenings">{SIGNAL_MAP_SVG}</a>{wordmark}<a href="/portfolio/" class="signal-bolt" title="Portfolio" aria-label="Portfolio">{SIGNAL_BOLT_SVG}</a></div>'


def signal_brand_css():
    return """
.signal-brand-row{display:inline-flex;align-items:center;justify-content:center;gap:12px;white-space:nowrap;letter-spacing:0;font-family:'Cormorant Garamond',Georgia,serif;font-size:1.6363636rem;font-weight:300;line-height:1;text-transform:uppercase;color:var(--text)}
.signal-brand-row .signal-wordmark{display:inline-block;letter-spacing:.18em;margin-right:-.18em;color:var(--text);font-style:normal;text-decoration:none}
.signal-brand-row .signal-wordmark>span{color:#b59662;font-style:italic}
.signal-map,.signal-bolt{display:inline-flex;align-items:center;width:1.243em;height:1.155em;color:#b59662;text-decoration:none;line-height:1}
.signal-map{justify-content:flex-end}.signal-bolt{justify-content:flex-start}
.signal-map-icon{width:1.243em;height:1.155em;display:block}.signal-map-ocean{fill:#0a0a0c}.signal-map-land{fill:#b59662}.signal-map-rim{fill:none;stroke:#b59662;stroke-width:.8}
.signal-bolt-icon{width:.738em;height:.945em;display:block;fill:currentColor;transform:translateY(.088em)}
@keyframes signal-gold-shimmer{0%,100%{opacity:.94;filter:brightness(.96) saturate(.95) drop-shadow(0 0 1px rgba(181,150,98,.22))}32%{opacity:1;filter:brightness(1.18) saturate(1.08) drop-shadow(0 0 3px rgba(181,150,98,.58)) drop-shadow(0 0 7px rgba(255,224,164,.22))}46%{opacity:1;filter:brightness(1.42) saturate(.82) drop-shadow(0 0 4px rgba(255,226,169,.76)) drop-shadow(0 0 10px rgba(181,150,98,.3))}61%{opacity:.98;filter:brightness(1.1) saturate(1.04) drop-shadow(0 0 2px rgba(181,150,98,.42))}}
.signal-brand-row .signal-bolt-icon,.signal-brand-row .signal-map-icon{animation:signal-gold-shimmer 3.8s cubic-bezier(.45,0,.35,1) infinite;will-change:filter,opacity}.signal-brand-row .signal-map-icon{animation-delay:-.72s}
.signal-brand-row .signal-bolt:hover,.signal-brand-row .signal-map:hover{opacity:1;transform:none}.signal-brand-row .signal-bolt:focus-visible,.signal-brand-row .signal-map:focus-visible,.signal-brand-row .signal-wordmark:focus-visible{outline:1px solid #b59662;outline-offset:3px;border-radius:2px}
@media(prefers-reduced-motion:reduce){.signal-brand-row .signal-bolt-icon,.signal-brand-row .signal-map-icon{animation:none;filter:brightness(1.12) drop-shadow(0 0 3px rgba(181,150,98,.5));opacity:1}}
""".strip()
