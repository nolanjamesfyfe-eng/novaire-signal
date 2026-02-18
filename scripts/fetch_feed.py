#!/usr/bin/env python3
"""
Novaire Signal — Signal Feed fetcher.
Runs in GitHub Actions every 4 hours. Outputs feed.json to repo root.

Feed spec (exactly 5 tweets per run):
  Guaranteed slots (3):
    1. Most recent tweet from @TheEconomist
    2. Most recent tweet from @zerohedge
    3. Most recent tweet from @KobeissiLetter

  Engagement slots (2):
    Top 2 tweets by (likes + retweets) from the 14 remaining accounts,
    within the last 4 hours (falls back to 8h if the window is empty).

Final output is sorted newest-first for display.
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

GUARANTEED_ACCOUNTS = [
    'TheEconomist',
    'zerohedge',
    'KobeissiLetter',
]

ENGAGEMENT_ACCOUNTS = [
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

ALL_ACCOUNTS = GUARANTEED_ACCOUNTS + ENGAGEMENT_ACCOUNTS  # 17 total

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

# ── Tweet fetcher ─────────────────────────────────────────────────────────────

def fetch_user_timeline(username: str, session: requests.Session) -> list:
    """Return a list of tweet dicts for the given username (up to 20)."""
    url = (
        f'https://syndication.twitter.com/srv/timeline-profile/'
        f'screen-name/{username}?lang=en'
    )
    try:
        resp = session.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 429:
            print(f'  @{username}: rate limited (429) — skipping')
            return []
        if not resp.ok:
            print(f'  @{username}: HTTP {resp.status_code}')
            return []

        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">([\s\S]*?)</script>',
            resp.text,
        )
        if not match:
            print(f'  @{username}: __NEXT_DATA__ not found')
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
                created_ms  = int(created_at.timestamp() * 1000)
            except (ValueError, TypeError):
                created_iso = datetime.now(timezone.utc).isoformat()
                created_ms  = 0

            tweets.append({
                'id':         t['id_str'],
                'text':       text,
                'author':     user.get('name') or username,
                'handle':     user.get('screen_name') or username,
                'createdAt':  created_iso,
                'createdAtMs': created_ms,
                'likes':      t.get('favorite_count', 0),
                'retweets':   t.get('retweet_count', 0),
                'url': (
                    f"https://x.com/{user.get('screen_name', username)}"
                    f"/status/{t['id_str']}"
                ),
                'avatar': user.get('profile_image_url_https'),
            })

        print(f'  @{username}: {len(tweets)} tweets')
        return tweets

    except requests.exceptions.Timeout:
        print(f'  @{username}: timeout')
        return []
    except Exception as exc:
        print(f'  @{username}: error — {exc}')
        return []

# ── Selection helpers ─────────────────────────────────────────────────────────

def most_recent(tweets: list) -> dict | None:
    """Return the tweet with the largest createdAtMs, or None."""
    return max(tweets, key=lambda t: t['createdAtMs']) if tweets else None


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

    # Fetch all timelines (guaranteed first, then engagement)
    all_data: dict[str, list] = {}
    errors: list[str] = []

    with requests.Session() as session:
        print('── Guaranteed accounts ──')
        for i, username in enumerate(GUARANTEED_ACCOUNTS):
            all_data[username] = fetch_user_timeline(username, session)
            if not all_data[username]:
                errors.append(username)
            if i < len(GUARANTEED_ACCOUNTS) - 1:
                time.sleep(0.5)

        print('\n── Engagement accounts ──')
        for i, username in enumerate(ENGAGEMENT_ACCOUNTS):
            all_data[username] = fetch_user_timeline(username, session)
            if not all_data[username]:
                errors.append(username)
            if i < len(ENGAGEMENT_ACCOUNTS) - 1:
                time.sleep(0.5)

    # ── Slot 1-3: guaranteed (most recent per account) ────────────────────────
    print('\n── Selecting guaranteed slots ──')
    feed: list[dict] = []
    seen_ids: set[str] = set()

    for username in GUARANTEED_ACCOUNTS:
        tweet = most_recent(all_data.get(username, []))
        if tweet and tweet['id'] not in seen_ids:
            tweet['slot'] = 'guaranteed'
            feed.append(tweet)
            seen_ids.add(tweet['id'])
            print(
                f'  ✓ @{username}: '
                f'"{tweet["text"][:60].strip()}…" '
                f'({tweet["createdAt"][:19]} UTC)'
            )
        else:
            print(f'  ✗ @{username}: no tweet available — slot skipped')

    # ── Slots 4-5: top 2 engagement from remaining 14 accounts ───────────────
    print('\n── Selecting engagement slots (last 4h) ──')
    FOUR_H_MS  = 4 * 60 * 60 * 1000
    EIGHT_H_MS = 8 * 60 * 60 * 1000

    eng_lists = [all_data.get(u, []) for u in ENGAGEMENT_ACCOUNTS]
    top2 = top_engagement(eng_lists, seen_ids, FOUR_H_MS, n=2)

    if not top2:
        print('  ⚠️  No tweets in last 4h — widening window to 8h')
        top2 = top_engagement(eng_lists, seen_ids, EIGHT_H_MS, n=2)

    for t in top2:
        score = t['likes'] + t['retweets']
        t['slot'] = 'engagement'
        feed.append(t)
        seen_ids.add(t['id'])
        print(
            f'  ✓ @{t["handle"]}: score={score} '
            f'(♥{t["likes"]} ↺{t["retweets"]}) — '
            f'"{t["text"][:50].strip()}…"'
        )

    if len(top2) < 2:
        print(f'  ⚠️  Only {len(top2)}/2 engagement slots filled')

    # ── Sort final feed newest-first ──────────────────────────────────────────
    feed.sort(key=lambda t: t['createdAtMs'], reverse=True)

    n_g = sum(1 for t in feed if t.get('slot') == 'guaranteed')
    n_e = sum(1 for t in feed if t.get('slot') == 'engagement')
    print(f'\n📊 Final feed: {len(feed)} tweets — {n_g} guaranteed, {n_e} engagement')

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
        'windowHours':     4,
        'curation':        'guaranteed3_engagement2',
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
