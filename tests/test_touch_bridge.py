"""Responsive shell and finance loss regression (no data or network writes)."""
import unittest
from pathlib import Path
from scripts.touch_bridge import BRIDGE, bridge_css, bridge_html
from scripts.generate_finances import render_html, build_payload
ROOT = Path(__file__).resolve().parents[1]

class TouchBridgeTests(unittest.TestCase):
    def test_rewrite_is_idempotent_and_preserves_non_width_conditions(self):
        css='@media(max-width:600px) and (prefers-reduced-motion:reduce){.x{display:none}}'
        result=bridge_css(css)
        self.assertIn('(prefers-reduced-motion:reduce) and '+BRIDGE,result)
        self.assertEqual(bridge_css(result),result)

    def test_brand_and_input_specific_queries_remain_untouched(self):
        for css in ('@media(max-width:600px){.signal-brand-row{font-size:28px}}', '@media (hover:none){.x{color:red}}'):
            self.assertEqual(bridge_css(css),css)

    def test_finance_generator_and_published_page_keep_canvas_constraints(self):
        generated=bridge_html(render_html(build_payload()))
        published=(ROOT/'portfolio/finances/index.html').read_text()
        for html in (generated,published):
            self.assertIn('canvas{width:100%;height:245px;display:block}',html)
            self.assertIn('.hero-grid{display:grid;',html)
            self.assertIn('.breakdown{display:grid;',html)
            self.assertIn('canvas{height:220px}',html)
        self.assertEqual(bridge_html(generated),generated)

    def test_every_companion_is_synced(self):
        from scripts.sync_signal_shell import PAGES, LINK
        for page in PAGES:
            html=(ROOT/page).read_text()
            self.assertIn(LINK,html,page)
            self.assertEqual(bridge_html(html),html,page)
        self.assertNotIn('/signal-shell.css',(ROOT/'index.html').read_text())
