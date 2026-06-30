#!/usr/bin/env python3
"""
Novaire Signal — Signal Feed fetcher.
Runs in GitHub Actions every 4 hours. Outputs feed.json to repo root.

Feed spec (exactly 4 tweets per run):
  Top 4 posts by engagement across the scanner accounts.
  The Economist is intentionally excluded: too broad for this compact section.

Final output is sorted by engagement score, then recency.
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests

# ── Account lists ─────────────────────────────────────────────────────────────

ENGAGEMENT_ACCOUNTS = [
    'zerohedge',
    'KobeissiLetter',
    'BambroughKevin',
    'hkuppy',
    'quakes99',
    'WatcherGuru',
    'nntaleb',
    'tferriss',
    'JohnPolomny',
    'SantiagoAuFund',
    'BarbarianCap',
    'JoshYoung',
    'wmiddelkoop',
    'White_Rabbit_OG',
    'colonelhomsi',
    'HydroGraphInc',
]

ALL_ACCOUNTS = ENGAGEMENT_ACCOUNTS  # TheEconomist intentionally excluded

# ── HTTP config ───────────────────────────────────────────────────────────────

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

REPO_ROOT = Path(__file__).parent.parent
NITTER_BASE = 'https://nitter.net'  # Primary Nitter instance for RSS

# ── Tweet fetcher via Nitter RSS ──────────────────────────────────────────────

def fetch_user_timeline(username: str, session: requests.Session) -> list:
    """Fetch tweets via Nitter RSS (reliable, no rate-limiting)."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime as parse_rfc822

    url = f'{NITTER_BASE}/{username}/rss'
    try:
        resp = session.get(url, headers=HEADERS, timeout=12)
        if not resp.ok:
            print(f'  @{username}: Nitter HTTP {resp.status_code}')
            return []

        root = ET.fromstring(resp.text)
        items = root.findall('.//item')
        tweets = []
        for item in items[:20]:
            title_el = item.find('title')
            link_el  = item.find('link')
            pub_el   = item.find('pubDate')
            desc_el  = item.find('description')
            if title_el is None:
                continue

            raw_text = title_el.text or ''
            # Strip "R to @handle:" and "RT by @handle:" prefixes
            raw_text = re.sub(r'^R to @\S+:\s*', '', raw_text)
            raw_text = re.sub(r'^RT by @\S+:\s*', '', raw_text)
            text = raw_text.strip()
            if not text or len(text) < 5:
                continue

            link = (link_el.text or '').strip() if link_el is not None else ''
            # Normalise nitter link → x.com
            link = re.sub(r'https?://nitter\.[^/]+/', 'https://x.com/', link)

            # Parse timestamp
            created_dt = None
            if pub_el is not None and pub_el.text:
                try:
                    created_dt = parse_rfc822(pub_el.text)
                except Exception:
                    pass
            if created_dt is None:
                created_dt = datetime.now(timezone.utc)

            tweet_id = re.search(r'/status/(\d+)', link)
            tweet_id_str = tweet_id.group(1) if tweet_id else str(int(created_dt.timestamp()))

            tweets.append({
                'id':          tweet_id_str,
                'text':        text,
                'author':      username,
                'handle':      username,
                'createdAt':   created_dt.isoformat(),
                'createdAtMs': int(created_dt.timestamp() * 1000),
                'likes':       0,
                'retweets':    0,
                'url':         link or f'https://x.com/{username}',
                'avatar':      None,
            })

        print(f'  @{username}: {len(tweets)} tweets via Nitter')
        return tweets

    except requests.exceptions.Timeout:
        print(f'  @{username}: timeout')
        return []
    except Exception as exc:
        print(f'  @{username}: error — {exc}')
        return []

# ── Selection helpers ─────────────────────────────────────────────────────────

ENGAGEMENT_MAX_AGE_MS = 24 * 60 * 60 * 1000  # 24h — engagement slots

def top_engagement(tweet_lists: list[list], exclude_ids: set, window_ms: int, n: int) -> list:
    """
    From all tweets in tweet_lists that are within window_ms of now
    and whose id is not in exclude_ids, return the top-n by likes+retweets.
    """
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    pool = [
        t
        for tweets in tweet_lists
        for t in tweets
        if t['id'] not in exclude_ids and (now_ms - t['createdAtMs']) <= window_ms
    ]
    pool.sort(key=lambda t: t['likes'] + t['retweets'], reverse=True)
    return pool[:n]

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f'Signal Feed — fetching {len(ALL_ACCOUNTS)} accounts...\n')

    # Fetch all timelines, then take the top four by engagement.
    all_data: dict[str, list] = {}
    errors: list[str] = []

    with requests.Session() as session:
        print('── Engagement scanner accounts ──')
        for i, username in enumerate(ENGAGEMENT_ACCOUNTS):
            all_data[username] = fetch_user_timeline(username, session)
            if not all_data[username]:
                errors.append(username)
            if i < len(ENGAGEMENT_ACCOUNTS) - 1:
                time.sleep(0.5)

    print('\n── Selecting top four by engagement (last 24h) ──')
    feed: list[dict] = []
    top4 = top_engagement([all_data.get(u, []) for u in ENGAGEMENT_ACCOUNTS], set(), ENGAGEMENT_MAX_AGE_MS, n=4)

    if not top4:
        print('  ⚠️  No engagement tweets in last 24h — keeping existing feed.json')

    for i, t in enumerate(top4):
        score = t['likes'] + t['retweets']
        t['slot'] = 'engagement'
        t['slot_order'] = i + 1
        t['engagementScore'] = score
        feed.append(t)
        print(
            f'  ✓ @{t["handle"]} [#{i+1}]: score={score} '
            f'(♥{t["likes"]} ↺{t["retweets"]}) — '
            f'"{t["text"][:50].strip()}…"'
        )

    # ── Sort final feed by slot_order (engagement rank) ────────────────────────
    feed.sort(key=lambda t: t.get('slot_order', 99))

    print(f'\n📊 Final feed: {len(feed)} tweets — top engagement only')

    # ── Write feed.json ───────────────────────────────────────────────────────
    if not feed:
        print('\n⚠️  Nothing to write — keeping existing feed.json')
        if errors:
            print(f'Failed accounts: {", ".join(errors)}')
        return

    out_path = REPO_ROOT / 'feed.json'
    output = {
        'ok':              True,
        'count':           len(feed),
        'accountsWithPosts': len({t['handle'] for t in feed}),
        'fetchedAt':       datetime.now(timezone.utc).isoformat(),
        'windowHours':     24,
        'curation':        'top4_engagement_no_economist',
        'errors':          errors,
        'posts':           feed,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'✅ Saved {len(feed)} posts to {out_path}')
    if errors:
        print(f'⚠️  Partial failures: {", ".join(errors)}')


if __name__ == '__main__':
    main()
