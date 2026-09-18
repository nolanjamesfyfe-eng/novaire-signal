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
    assert html.count('href="/" class="signal-wordmark" aria-label="Novaire Signal home"') == 2
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


def test_mobile_uses_full_width_canvas_globe_with_real_gestures():
    html = (ROOT / 'map/index.html').read_text()
    assert "matchMedia('(max-width:760px)')" in html
    assert 'd3.geoOrthographic().clipAngle(90)' in html
    assert 'mobile?Math.max(1,Math.min((width-16)/2,(height-106)/2))' in html
    assert '.map-frame{width:calc(100% + 28px);margin-left:-14px' in html
    assert '.map-canvas{height:clamp(430px,123vw,480px);min-height:430px}' in html
    assert '<canvas id="globe-canvas"' in html
    assert 'canvas.onpointerdown=' in html
    assert "kind:'pinch'" in html
    assert 'globe.zoom=Math.max(1,Math.min(3' in html
    assert 'projection.rotate(globe.rotation).scale(globe.baseScale*globe.zoom)' in html
    assert 'requestAnimationFrame' in html
    assert 'scheduleDraw()' in html
    assert "fetch('/map/world-globe.geojson')" in html
    assert 'id="reset-view" aria-label="Reset globe view"' in html


def test_globe_hit_testing_cancel_and_metrics_are_preserved():
    html = (ROOT / 'map/index.html').read_text()
    assert 'globe.rotation=[-coords[0],-coords[1],0]' in html
    assert "code in MICRO?MICRO[code]:f&&d3.geoCentroid(f)" in html
    assert "d3.geoDistance([-globe.rotation[0],-globe.rotation[1]],coords)>Math.PI/2" in html
    assert 'd3.geoContains(feature,coords)' in html
    assert "!cancelled&&!globe.moved&&ended" in html
    assert "canvas.onpointercancel=e=>end(e,true)" in html
    assert '<b>Capital:</b>' in html
    assert '<b>Population:</b>' in html
    assert '<b>GDP:</b>' in html


def test_desktop_orthographic_rotation_and_wheel_zoom_are_available():
    html = (ROOT / 'map/index.html').read_text()
    assert ":Math.max(1,Math.min((width-48)/2,(height-73)/2))" in html
    assert "canvas.onwheel=" in html
    assert "if(!insideGlobe(e))return;e.preventDefault()" in html
    assert "globe.rotation=[globe.gesture.rotation[0]+dx*.28/globe.zoom" in html
    assert "mobile?1.35:1.5" in html


def test_canonical_signal_branding_and_copy_removal():
    html = (ROOT / 'map/index.html').read_text()
    assert html.count('class="signal-map-icon" viewBox=".85 .85 22.3 22.3"') == 2
    assert html.count('class="signal-bolt-icon" viewBox="45 38 200 264"') == 2
    assert html.count('href="/portfolio/" class="signal-bolt"') == 2
    assert html.count('href="/flaneur" class="signal-map"') == 2
    assert 'gap:12px' in html
    assert 'A living record · 195 countries + 4 destinations' not in html
    assert 'touch-action:pan-y' in html


def test_interaction_geometry_keeps_all_features_inside_budget():
    world = json.loads((ROOT / 'map/world-globe.geojson').read_text())
    points = sum(
        len(ring)
        for feature in world['features']
        for polygon in ([feature['geometry']['coordinates']]
                        if feature['geometry']['type'] == 'Polygon'
                        else feature['geometry']['coordinates'])
        for ring in polygon
    )
    assert len(world['features']) == 199
    assert points <= 5000


def test_pointer_capture_only_begins_after_drag_threshold():
    html = (ROOT / 'map/index.html').read_text()
    gestures = html.split('function bindGestures()')[1].split('function renderMap()')[0]
    assert 'setPointerCapture' not in gestures.split('canvas.onpointerdown=')[1].split('canvas.onpointermove=')[0]
    assert 'canvas.setPointerCapture(e.pointerId)' in gestures.split('canvas.onpointermove=')[1]
    assert 'if(!globe.pointers.size)globe.moved=false' in gestures
    assert 'if(pts.length>1)globe.moved=true' in gestures
