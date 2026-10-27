"""Exercise the actual emitted chart JavaScript, not only HTML markers."""
import json
import re
import shutil
import subprocess
import unittest
from portfolio_tracker import _interactive_chart_html


@unittest.skipUnless(shutil.which('node'), 'Node required for chart JS regression')
class TrackerRegimeJavascriptTests(unittest.TestCase):
    def test_generated_script_and_twenty_percent_reversals(self):
        values = [100, 80, 90, 96, 110, 100, 88, 90, 105.6]
        series = [{'market_date': f'2026-10-{i+1:02d}', 'cad': v, 'complete': True}
                  for i, v in enumerate(values)]
        html = _interactive_chart_html({'total_series': series, 'scope_label': 'test',
                                       'market_date': '2026-10-09', 'current_total_cad': values[-1]})
        script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
        checked = subprocess.run(['node', '--check'], input=script, text=True, capture_output=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        engine = next(line for line in script.splitlines() if 'const TH=' in line)
        result = subprocess.run(['node', '-e', 'const all=' + json.dumps(series) + ';' + engine +
                                 ';console.log(JSON.stringify(regime));'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        # Confirmed legs start at their turning point; small counter-moves keep the regime.
        self.assertEqual(json.loads(result.stdout),
                         ['bear', 'bull', 'bull', 'bull', 'bear', 'bear', 'bull', 'bull', 'bull'])
        self.assertIn("bull?' is-live-bull':' is-live-bear'", script)
