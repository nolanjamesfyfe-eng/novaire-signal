from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
IDS = ('latest-novaire-card', 'weekly-asymmetric-ideas', 'catalysts-card',
       'fed-signal-card', 'polymarket-card', 'darvas-card', 'thailand-news-card',
       'economies-card', 'google-daily-tasks-card')


def test_shared_closed_css_is_embedded_by_generator_and_output():
    source = (ROOT / 'generate.py').read_text()
    css = (ROOT / 'compact-closed.css').read_text().strip()
    output = (ROOT / 'index.html').read_text()
    assert "Path(__file__).with_name('compact-closed.css').read_text()" in source
    assert css in output
    assert 'height:38px;min-height:38px;padding:10px 16px' in css
    assert '@container(max-width:30rem)' in css
    assert '@container(max-width:12rem)' in css
    assert 'overflow:hidden' not in css
    assert 'text-overflow' not in css
    for card_id in IDS:
        assert '#' + card_id in css


def test_nine_outer_summaries_have_separate_aligned_icon_and_label():
    document = BeautifulSoup((ROOT / 'index.html').read_text(), 'html.parser')
    for card_id in IDS:
        card = document.find(id=card_id)
        # Economies remains intentionally absent outside its edition.
        if card_id == 'economies-card' and card is None:
            continue
        assert card is not None
        summary = card.find('summary', recursive=False)
        assert summary.select_one('.compact-peer-icon') is not None
        assert summary.select_one('.compact-peer-label').get_text(strip=True)
        assert not card.select('.signal-accordion-body .compact-peer-icon')
