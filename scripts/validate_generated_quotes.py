#!/usr/bin/env python3
"""Fail closed when a generated Signal would replace live prices with blanks."""
from pathlib import Path
from bs4 import BeautifulSoup

root = Path(__file__).resolve().parents[1]
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
portfolio = (root / 'portfolio' / 'index.html').read_text(encoding='utf-8')
portfolio_count = portfolio.count('data-chart-symbol=')
if portfolio_count < 21:
    failures.append(f'portfolio: expected 21 ticker rows; got {portfolio_count}')
if failures:
    print('REFRESH BLOCKED — generated quote coverage regressed')
    print('\n'.join(f'- {failure}' for failure in failures))
    raise SystemExit(1)
print('generated quote coverage: ok')
