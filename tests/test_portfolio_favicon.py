import ast
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ICON_LINK = '<link rel="icon" type="image/svg+xml" href="/portfolio/favicon.svg?v=1">'
TOUCH_LINK = '<link rel="apple-touch-icon" href="/portfolio/apple-touch-icon.png?v=1">'


def test_all_portfolio_pages_use_the_silver_dollar_favicon():
    for relative in (
        'portfolio/index.html',
        'portfolio/daily/index.html',
        'portfolio/evolutionfund/index.html',
    ):
        html = (ROOT / relative).read_text()
        assert ICON_LINK in html, relative
        assert TOUCH_LINK in html, relative
        assert '⚡</text></svg>' not in html, relative


def test_portfolio_icon_is_custom_vector_art_not_text_or_emoji():
    icon = ET.fromstring((ROOT / 'portfolio/favicon.svg').read_text())
    assert icon.attrib['viewBox'] == '0 0 100 100'
    assert not icon.findall('.//{*}text')
    paths = icon.findall('.//{*}path')
    assert len(paths) == 2
    assert all(path.attrib.get('stroke') is None for path in paths)
    background = icon.find('{*}rect')
    assert background is not None
    assert background.attrib['fill'] == '#050506'


def test_touch_icon_is_180_pixel_png():
    data = (ROOT / 'portfolio/apple-touch-icon.png').read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II', data[16:24]) == (180, 180)


def test_generator_sources_keep_portfolio_icon_route_specific():
    generator = (ROOT / 'generate.py').read_text()
    daily = (ROOT / 'daily_brief.py').read_text()
    assert generator.count(ICON_LINK) == 1
    assert generator.count(TOUCH_LINK) == 1
    assert ICON_LINK in daily and TOUCH_LINK in daily
    ast.parse(generator)
    ast.parse(daily)


def test_main_signal_and_flaneur_icons_are_unchanged():
    main = (ROOT / 'index.html').read_text()
    flaneur = (ROOT / 'map/index.html').read_text()
    assert "<text y='.9em' font-size='90'>⚡</text>" in main
    assert '/portfolio/favicon.svg' not in main
    assert '<link rel="icon" type="image/svg+xml" href="/map/favicon-globe.svg?v=1">' in flaneur
    assert '/portfolio/favicon.svg' not in flaneur
