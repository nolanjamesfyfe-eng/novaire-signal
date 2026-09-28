from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from signal_brand import signal_brand_css, signal_brand_markup
SUITE_PAGES = (
    "index.html",
    "portfolio-lock.html",
    "portfolio/index.html",
    "portfolio/daily/index.html",
    "portfolio/evolutionfund/index.html",
    "portfolio/evolutionfund/philosophy.html",
    "portfolio/finances/index.html",
    "health/index.html",
    "map/index.html",
)


def test_canonical_brand_tightens_only_bolt_to_health_spacing():
    css = signal_brand_css()
    assert ".signal-health{" in css
    assert "margin-left:calc(-.505em - 1.2px)" in css
    assert ".signal-bolt-icon{width:.738em" in css
    assert ".signal-map,.signal-brand-row .signal-bolt" in css
    assert "width:1.243em" in css


def test_canonical_brand_defaults_to_complete_four_link_layout():
    markup = signal_brand_markup()
    assert markup.index('class="signal-map"') < markup.index('class="signal-wordmark"')
    assert markup.index('class="signal-wordmark"') < markup.index('class="signal-bolt"')
    assert markup.index('class="signal-bolt"') < markup.index('class="signal-health"')


def test_every_signal_suite_page_has_complete_header_and_footer_brand_rows():
    for relative in SUITE_PAGES:
        html = (ROOT / relative).read_text(encoding="utf-8")
        assert html.count('class="signal-wordmark"') == 2, relative
        assert html.count('class="signal-map"') == 2, relative
        assert html.count('class="signal-bolt"') == 2, relative
        assert html.count('class="signal-health"') == 2, relative
        assert "margin-left:calc(-.505em - 1.2px)" in html, relative
