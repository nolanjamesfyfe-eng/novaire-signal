#!/usr/bin/env python3
"""Fail closed when a generated Signal would replace live prices with blanks."""
import json
from pathlib import Path
from bs4 import BeautifulSoup

def validate(root):
    root = Path(root)
    soup = BeautifulSoup((root / 'index.html').read_text(encoding='utf-8'), 'html.parser')
    checks = {
        'crypto': (soup.select('[data-crypto-price]'), 8),
        'commodities': (soup.select('[data-comm-price]'), 6),
        'futures': (soup.select('[data-future-price]'), 3),
    }
    failures = []
    for name, (nodes, expected) in checks.items():
        values = [node.get_text(' ', strip=True) for node in nodes]
        if len(nodes) != expected or any(value in {'', '—'} for value in values):
            failures.append(f'{name}: expected {expected} complete quotes; got {len(nodes)} values={values}')

    stats = json.loads((root / 'stats.json').read_text(encoding='utf-8'))
    expected_portfolio_count = stats.get('portfolio', {}).get('holdings_count')
    if not isinstance(expected_portfolio_count, int) or isinstance(expected_portfolio_count, bool) or expected_portfolio_count < 1:
        failures.append(f'portfolio: invalid generated holdings_count={expected_portfolio_count!r}')
    else:
        portfolio = (root / 'portfolio' / 'index.html').read_text(encoding='utf-8')
        portfolio_count = portfolio.count('data-chart-symbol=')
        if portfolio_count != expected_portfolio_count:
            failures.append(
                f'portfolio: expected {expected_portfolio_count} ticker rows from generated holdings source; '
                f'got {portfolio_count}'
            )
    return failures


if __name__ == '__main__':
    failures = validate(Path(__file__).resolve().parents[1])
    if failures:
        print('REFRESH BLOCKED — generated quote coverage regressed')
        print('\n'.join(f'- {failure}' for failure in failures))
        raise SystemExit(1)
    print('generated quote coverage: ok')
