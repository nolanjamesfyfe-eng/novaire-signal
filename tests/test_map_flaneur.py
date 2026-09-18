import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_flaneur_title_and_brand():
    html = (ROOT / 'map/index.html').read_text()
    assert '<h1>Flâneur <i>Happenings</i></h1>' in html
    assert '61.2px' in html
    assert '<p class="lede">' not in html
    assert 'white-space:nowrap' in html
    assert 'Travel ledger · Public edition' not in html
    assert 'so far.' not in html
    assert 'font:300 19px/1.5 "Cormorant Garamond"' in html
    assert 'letter-spacing:.18em;text-transform:uppercase' in html


def test_wishlist_is_ten_unvisited_countries_separate_from_planned():
    html = (ROOT / 'map/index.html').read_text()
    section = html.split('<section class="wishlist"')[1].split('</section>')[0]
    codes = re.findall(r'data-code="([A-Z]{2})"', section)
    data = json.loads((ROOT / 'map/visited.json').read_text())
    assert len(codes) == len(set(codes)) == 10
    assert codes[:6] == ['AR', 'CL', 'BR', 'UA', 'UY', 'BY']
    assert all(data['answers'][code] is False for code in codes)
    assert set(codes).isdisjoint(data['planned'])
    assert 'Suggested' not in section
    assert 'id="wishlist-lock"' in section
    assert 'id="wishlist-add"' in section
    assert html.index('<section class="wishlist"') < html.index('<section class="directory"')


def test_tooltip_omits_negative_status_but_preserves_facts():
    html = (ROOT / 'map/index.html').read_text()
    tip = html.split('function showTip(')[1].split('function hideTip')[0]
    assert 'Not visited' not in tip
    assert 'statusLabel(code)' not in tip
    assert '<small>Upcoming</small>' in tip
    assert '<b>Capital:</b>' in tip
    assert '<b>Population:</b>' in tip


def test_flaneur_route_and_legacy_redirect():
    config = json.loads((ROOT / 'vercel.json').read_text())
    assert {'source': '/flaneur', 'destination': '/map/index.html'} in config['rewrites']
    for path in ['/map', '/map/', '/map/index.html']:
        assert {'source': path, 'destination': '/flaneur', 'permanent': True} in config['redirects']
    for source in ['index.html', 'generate.py']:
        content = (ROOT / source).read_text()
        assert 'href="/flaneur" class="signal-map"' in content
        assert 'href="/map/" class="signal-map"' not in content
