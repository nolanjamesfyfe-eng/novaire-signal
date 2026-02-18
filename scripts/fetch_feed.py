#!/usr/bin/env python3
"""
Fetch recent tweets from specified X accounts via Twitter's syndication API.
Runs in GitHub Actions (different IPs than Vercel, avoids rate limiting).
Outputs feed.json to repo root.
"""

import json
import re
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests

ACCOUNTS = [
    'BambroughKevin', 'zerohedge', 'KobeissiLetter', 'hkuppy', 'quakes99',
    'WatcherGuru', 'nntaleb', 'tferriss', 'TheEconomist', 'JohnPolomny',
    'SantiagoAuFund', 'BarbarianCap', 'JoshYoung', 'wmiddelkoop',
    'White_Rabbit_OG', 'colonelhomsi', 'HydroGraphInc'
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

REPO_ROOT = Path(__file__).parent.parent


def fetch_user_timeline(username: str, session: requests.Session) -> list:
    """Fetch recent/popular tweets for a user via Twitter's syndication API."""
    url = f'https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}?lang=en'
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
            html
        )
        if not match:
            print(f'  @{username}: no __NEXT_DATA__ found')
            return []

        data = json.loads(match.group(1))
        entries = data.get('props', {}).get('pageProps', {}).get('timeline', {}).get('entries', [])

        tweets = []
        for entry in entries[:20]:
            if entry.get('type') != 'tweet':
                continue
            t = entry.get('content', {}).get('tweet', {})
            if not t.get('id_str'):
                continue

            user = t.get('user', {})
            raw_text = t.get('full_text') or t.get('text') or ''
            # Remove t.co links
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
                'url': f"https://x.com/{user.get('screen_name', username)}/status/{t['id_str']}",
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


def main():
    print(f'Fetching signal feed for {len(ACCOUNTS)} accounts...')
    all_tweets = []
    errors = []

    with requests.Session() as session:
        for i, username in enumerate(ACCOUNTS):
            tweets = fetch_user_timeline(username, session)
            all_tweets.extend(tweets)
            if not tweets:
                errors.append(username)
            # Rate limit protection: small delay between requests
            if i < len(ACCOUNTS) - 1:
                time.sleep(0.5)

    # Deduplicate by ID
    seen = set()
    unique = []
    for t in all_tweets:
        if t['id'] not in seen:
            seen.add(t['id'])
            unique.append(t)

    # Sort by recency
    unique.sort(key=lambda t: t['createdAtMs'], reverse=True)

    # Cap per-account to ensure distribution (max 5 per handle)
    per_account = {}
    balanced = []
    for t in unique:
        h = t['handle']
        if per_account.get(h, 0) < 5:
            per_account[h] = per_account.get(h, 0) + 1
            balanced.append(t)
        if len(balanced) >= 60:
            break

    # If we still have slots, add more from any account
    if len(balanced) < 60:
        in_balanced = set(t['id'] for t in balanced)
        for t in unique:
            if t['id'] not in in_balanced:
                balanced.append(t)
                in_balanced.add(t['id'])
            if len(balanced) >= 60:
                break

    # Final sort by recency
    balanced.sort(key=lambda t: t['createdAtMs'], reverse=True)
    feed = balanced[:60]

    out_path = REPO_ROOT / 'feed.json'

    # If we got no posts (all rate-limited), keep the existing feed.json
    if not feed:
        print('\n⚠️  No posts fetched — keeping existing feed.json')
        if errors:
            print(f'Failed accounts: {", ".join(errors)}')
        return

    output = {
        'ok': True,
        'count': len(feed),
        'accountsWithPosts': len(set(t['handle'] for t in feed)),
        'fetchedAt': datetime.now(timezone.utc).isoformat(),
        'errors': errors,
        'posts': feed,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n✅ Saved {len(feed)} posts from {output["accountsWithPosts"]} accounts to feed.json')
    if errors:
        print(f'⚠️  Partial failures: {", ".join(errors)}')


if __name__ == '__main__':
    main()
