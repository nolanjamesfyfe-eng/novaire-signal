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
    assert '<small>Visited</small>' not in tip
    assert '<a class="brand" href="/">Novaire <em>Signal</em></a>' in html
    assert 'Novaire Signal · World Atlas' not in html
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


def test_mobile_uses_full_width_orthographic_globe_with_real_gestures():
    html = (ROOT / 'map/index.html').read_text()
    assert "matchMedia('(max-width:760px)')" in html
    assert 'd3.geoOrthographic().clipAngle(90)' in html
    assert 'globe.baseScale=Math.max(1,Math.min((width-16)/2,(height-106)/2))' in html
    assert '.map-frame{width:calc(100% + 28px);margin-left:-14px' in html
    assert '.map-canvas{height:clamp(430px,123vw,480px);min-height:430px}' in html
    assert 'node.onpointerdown=' in html
    assert "kind:'pinch'" in html
    assert 'globe.zoom=Math.max(1,Math.min(3' in html
    assert 'projection.rotate(globe.rotation).scale(globe.baseScale*globe.zoom)' in html
    assert 'requestAnimationFrame' in html
    assert 'scheduleGlobeRedraw()' in html
    assert 'id="reset-view" aria-label="Reset globe view"' in html


def test_mobile_globe_focus_and_backside_marker_clipping_are_preserved():
    html = (ROOT / 'map/index.html').read_text()
    assert 'globe.rotation=[-coords[0],-coords[1],0]' in html
    assert "code in MICRO?MICRO[code]:f&&d3.geoCentroid(f)" in html
    assert "d3.geoDistance([-globe.rotation[0],-globe.rotation[1]],d[1])<=Math.PI/2" in html
    assert "if(mobile&&globe.moved)return;showTip" in html
    assert "showTip(e,d.properties.iso2);if(!mobile)focusCountry" in html
    assert '<b>Capital:</b>' in html
    assert '<b>Population:</b>' in html
    assert '<b>GDP:</b>' in html


def test_desktop_natural_earth_behavior_remains_available():
    html = (ROOT / 'map/index.html').read_text()
    assert 'd3.geoNaturalEarth1().fitExtent([[24,45],[width-24,height-28]],geo)' in html
    assert "zoom=d3.zoom().scaleExtent([1,10])" in html
    assert "svg.transition().duration(550).call(zoom.transform" in html
    assert "mobile?1.35:1.5" in html


def test_mobile_pointer_capture_does_not_steal_country_taps():
    html = (ROOT / 'map/index.html').read_text()
    gestures = html.split('function bindGlobeGestures()')[1].split('function renderMap()')[0]
    assert 'setPointerCapture' not in gestures.split('node.onpointerdown=')[1].split('node.onpointermove=')[0]
    assert 'node.setPointerCapture(e.pointerId)' in gestures.split('node.onpointermove=')[1]
    assert 'if(!globe.pointers.size)globe.moved=false' in gestures
    assert 'if(pts.length>1)globe.moved=true' in gestures
