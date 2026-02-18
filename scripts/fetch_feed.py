#!/usr/bin/env python3
"""
Fetch signal feed from X accounts via Twitter's syndication API.
Runs in GitHub Actions every 4 hours.

Feed logic (exactly 5 tweets per run):
  Guaranteed slots (1 each):
    - @TheEconomist  — most recent tweet
    - @zerohedge     — most recent tweet
    - @KobeissiLetter — most recent tweet
  Engagement slots (2 total):
    - From 14 remaining accounts: top 2 by engagement score (likes + retweets)
      from tweets in the last 4 hours (falls back to 8h if none found)

Each tweet is marked with a 'slot' field: "guaranteed" or "engagement".
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

# ── Slot definitions ──────────────────────────────────────────────────────────

GUARANTEED_ACCOUNTS = ['TheEconomist', 'zerohedge', 'KobeissiLetter']

ENGAGEMENT_ACCOUNTS = [
    'BambroughKevin', 'hkuppy', 'quakes99', 'WatcherGuru', 'nntaleb',
    'tferriss', 'JohnPolomny', 'SantialyAuFund', 'BarbarianCap', 'JoshYoung',
    'wmiddelkoop', 'White_Rabbit_OG', 'colonelhomsi', 'HydroGraphInc',
]

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

# ── Fetch helpers ─────────────────────────────────────────────────────────────

def fetch_user_timeline(username: str, session: requests.Session) -> list:
    """Fetch recent tweets for a user via Twitter's syndication API."""
    url = (
        f'https://syndication.twitter.com/srv/timeline-profile/'
        f'screen-name/{username}?lang=en'
    )
    try:
        resp = session.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 429:
            print(f'  @{username}: rate limited (429), skipping')
            return []
        if not resp.ok:
            print(f'  @{username}: HTTP {resp.status_code}')
            return []

        html = resp.text
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">([\s\S]*?)</script>',
            html,
        )
        if not match:
            print(f'  @{username}: no __NEXT_DATA__ found')
            return []

        data = json.loads(match.group(1))
        entries = (
            data.get('props', {})
                .get('pageProps', {})
                .get('timeline', {})
                .get('entries', [])
        )

        tweets = []
        for entry in entries[:20]:
            if entry.get('type') != 'tweet':
                continue
            t = entry.get('content', {}).get('tweet', {})
            if not t.get('id_str'):
                continue

            user = t.get('user', {})
            raw_text = t.get('full_text') or t.get('text') or ''
            text = re.sub(r'https?://t\.co/\S+', '', raw_text).strip()
            if not text:
                continue

            try:
                created_at = datetime.strptime(
                    t.get('created_at', ''), '%a %b %d %H:%M:%S +0000 %Y'
                ).replace(tzinfo=timezone.utc)
                created_iso = created_at.isoformat()
                created_ms = int(created_at.timestamp() * 1000)
            except (ValueError, TypeError):
                created_iso = datetime.now(timezone.utc).isoformat()
                created_ms = 0

            tweets.append({
                'id': t['id_str'],
                'text': text,
                'author': user.get('name') or username,
                'handle': user.get('screen_name') or username,
                'createdAt': created_iso,
                'createdAtMs': created_ms,
                'likes': t.get('favorite_count', 0),
                'retweets': t.get('retweet_count', 0),
                'url': (
                    f"https://x.com/{user.get('screen_name', username)}"
                    f"/status/{t['id_str']}"
                ),
                'avatar': user.get('profile_image_url_https'),
            })

        print(f'  @{username}: {len(tweets)} tweets fetched')
        return tweets

    except requests.exceptions.Timeout:
        print(f'  @{username}: timeout')
        return []
    except Exception as e:
        print(f'  @{username}: error — {e}')
        return []


def most_recent(tweets: list) -> dict | None:
    """Return the single most recent tweet from a list, or None."""
    if not tweets:
        return None
    return max(tweets, key=lambda t: t['createdAtMs'])


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(
        f'Fetching signal feed '
        f'({len(GUARANTEED_ACCOUNTS)} guaranteed + '
        f'{len(ENGAGEMENT_ACCOUNTS)} engagement accounts)...'
    )

    guaranteed_data: dict[str, list] = {}
    engagement_data: dict[str, list] = {}
    errors: list[str] = []

    with requests.Session() as session:
        print('\n── Guaranteed accounts ──')
        for i, username in enumerate(GUARANTEED_ACCOUNTS):
            tweets = fetch_user_timeline(username, session)
            guaranteed_data[username] = tweets
            if not tweets:
                errors.append(username)
            if i < len(GUARANTEED_ACCOUNTS) - 1:
                time.sleep(0.5)

        print('\n── Engagement accounts ──')
        for i, username in enumerate(ENGAGEMENT_ACCOUNTS):
            tweets = fetch_user_timeline(username, session)
            engagement_data[username] = tweets
            if not tweets:
                errors.append(username)
            if i < len(ENGAGEMENT_ACCOUNTS) - 1:
                time.sleep(0.5)

    # ── 1. Fill guaranteed slots ──────────────────────────────────────────────
    feed: list[dict] = []
    seen_ids: set[str] = set()

    print('\n── Selecting guaranteed slots ──')
    for username in GUARANTEED_ACCOUNTS:
        tweet = most_recent(guaranteed_data.get(username, []))
        if tweet and tweet['id'] not in seen_ids:
            tweet['slot'] = 'guaranteed'
            feed.append(tweet)
            seen_ids.add(tweet['id'])
            print(f'  ✓ @{username}: {tweet["id"]} ({tweet["createdAt"][:19]})')
        else:
            # Graceful skip — do NOT backfill with an engagement pick
            print(f'  ✗ @{username}: no data — slot left empty')

    # ── 2. Fill engagement slots (top 2 by likes+retweets, last 4h) ──────────
    print('\n── Selecting engagement slots ──')
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    four_h_ms = 4 * 60 * 60 * 1000
    eight_h_ms = 8 * 60 * 60 * 1000

    def candidate_pool(window_ms: int) -> list[dict]:
        pool = []
        for tweets in engagement_data.values():
            for t in tweets:
                if t['id'] not in seen_ids and (now_ms - t['createdAtMs']) <= window_ms:
                    pool.append(t)
        return pool

    pool = candidate_pool(four_h_ms)
    if not pool:
        print('  ⚠️  No engagement tweets in last 4h — widening to 8h')
        pool = candidate_pool(eight_h_ms)

    pool.sort(key=lambda t: t['likes'] + t['retweets'], reverse=True)

    picked = 0
    for t in pool:
        if t['id'] in seen_ids:
            continue
        if picked >= 2:
            break
        t['slot'] = 'engagement'
        feed.append(t)
        seen_ids.add(t['id'])
        score = t['likes'] + t['retweets']
        print(f'  ✓ @{t["handle"]}: {t["id"]} (score={score})')
        picked += 1

    if picked < 2:
        print(f'  ⚠️  Only {picked}/2 engagement slot(s) filled')

    # ── 3. Sort final feed newest-first ──────────────────────────────────────
    feed.sort(key=lambda t: t['createdAtMs'], reverse=True)

    n_g = sum(1 for t in feed if t.get('slot') == 'guaranteed')
    n_e = sum(1 for t in feed if t.get('slot') == 'engagement')
    print(f'\n📊 Final feed: {len(feed)} tweets ({n_g} guaranteed, {n_e} engagement)')

    # ── 4. Write output ───────────────────────────────────────────────────────
    out_path = REPO_ROOT / 'feed.json'

    if not feed:
        print('\n⚠️  No posts fetched — keeping existing feed.json')
        if errors:
            print(f'Failed accounts: {", ".join(errors)}')
        return

    output = {
        'ok': True,
        'count': len(feed),
        'fetchedAt': datetime.now(timezone.utc).isoformat(),
        'errors': errors,
        'posts': feed,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n✅ Saved {len(feed)} posts to feed.json')
    if errors:
        print(f'⚠️  Partial failures: {", ".join(errors)}')


if __name__ == '__main__':
    main()
