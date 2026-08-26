#!/usr/bin/env python3
"""
Novaire Signal — Signal Feed fetcher.
Runs with the daily 07:00 Asia/Bangkok site refresh. Outputs feed.json.

Feed spec (up to 12 tweets per run):
  Four consecutive pages of 3 posts, ranked by engagement across the scanner accounts.
  The Economist is intentionally excluded: too broad for this compact section.

Nitter RSS is dead (HTTP 410). Timelines come from authenticated xurl search.
Final output is sorted by engagement score, then recency.
"""

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ENGAGEMENT_ACCOUNTS = [
    "zerohedge",
    "KobeissiLetter",
    "BambroughKevin",
    "hkuppy",
    "quakes99",
    "WatcherGuru",
    "nntaleb",
    "tferriss",
    "JohnPolomny",
    "SantiagoAuFund",
    "BarbarianCap",
    "JoshYoung",
    "wmiddelkoop",
    "White_Rabbit_OG",
    "colonelhomsi",
    "HydroGraphInc",
]

ALL_ACCOUNTS = ENGAGEMENT_ACCOUNTS  # TheEconomist intentionally excluded
REPO_ROOT = Path(__file__).parent.parent
ENGAGEMENT_MAX_AGE_MS = 24 * 60 * 60 * 1000
SIGNAL_POOL_SIZE = 12
MIN_PUBLISHABLE_POSTS = 3
XURL_BIN = "xurl"


def parse_iso_ms(value: str) -> tuple[str, int]:
    raw = str(value or "").strip()
    if not raw:
        now = datetime.now(timezone.utc)
        return now.isoformat(), int(now.timestamp() * 1000)
    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        now = datetime.now(timezone.utc)
        return now.isoformat(), int(now.timestamp() * 1000)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.isoformat(), int(dt.timestamp() * 1000)


def tweets_from_xurl_payload(payload, username: str) -> list:
    """Normalize an xurl search payload into Signal Feed posts."""
    if isinstance(payload, dict):
        rows = payload.get("data") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []

    tweets = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text or len(text) < 5:
            continue
        if re.match(r"^RT @", text):
            continue
        tweet_id = str(row.get("id") or "").strip()
        if not tweet_id:
            continue
        created_at, created_ms = parse_iso_ms(row.get("created_at") or "")
        metrics = row.get("public_metrics") or {}
        tweets.append({
            "id": tweet_id,
            "text": text,
            "author": username,
            "handle": username,
            "createdAt": created_at,
            "createdAtMs": created_ms,
            "likes": int(metrics.get("like_count") or 0),
            "retweets": int(metrics.get("retweet_count") or 0),
            "url": f"https://x.com/{username}/status/{tweet_id}",
            "avatar": None,
        })
    return tweets


def fetch_user_timeline(username: str) -> list:
    """Fetch recent original posts for one handle via xurl search."""
    try:
        result = subprocess.run(
            [XURL_BIN, "search", f"from:{username}", "-n", "10"],
            capture_output=True,
            text=True,
            timeout=25,
        )
    except FileNotFoundError:
        print(f"  @{username}: xurl is not installed")
        return []
    except subprocess.TimeoutExpired:
        print(f"  @{username}: timeout")
        return []
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "xurl failed").strip().splitlines()
        print(f"  @{username}: xurl error — {err[-1] if err else 'non-zero exit'}")
        return []
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        print(f"  @{username}: invalid xurl JSON")
        return []
    tweets = tweets_from_xurl_payload(payload, username)
    print(f"  @{username}: {len(tweets)} tweets via xurl")
    return tweets


def is_publishable_feed(feed: list) -> bool:
    """Return whether a refresh is large enough to replace the live feed."""
    return len(feed) >= MIN_PUBLISHABLE_POSTS


def top_engagement(tweet_lists: list[list], exclude_ids: set, window_ms: int, n: int) -> list:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    pool = [
        t
        for tweets in tweet_lists
        for t in tweets
        if t["id"] not in exclude_ids and (now_ms - t["createdAtMs"]) <= window_ms
    ]
    pool.sort(key=lambda t: (t["likes"] + t["retweets"], t["createdAtMs"]), reverse=True)
    picked = []
    seen_handles = set()
    for tweet in pool:
        handle = tweet.get("handle")
        if handle in seen_handles:
            continue
        picked.append(tweet)
        seen_handles.add(handle)
        if len(picked) >= n:
            break
    return picked


def main():
    print(f"Signal Feed — fetching {len(ALL_ACCOUNTS)} accounts via xurl...\n")
    all_data: dict[str, list] = {}
    errors: list[str] = []

    print("── Engagement scanner accounts ──")
    for i, username in enumerate(ENGAGEMENT_ACCOUNTS):
        all_data[username] = fetch_user_timeline(username)
        if not all_data[username]:
            errors.append(username)
        if i < len(ENGAGEMENT_ACCOUNTS) - 1:
            time.sleep(0.4)

    print(f"\n── Selecting top {SIGNAL_POOL_SIZE} by engagement (last 24h) ──")
    feed: list[dict] = []
    top12 = top_engagement(
        [all_data.get(u, []) for u in ENGAGEMENT_ACCOUNTS],
        set(),
        ENGAGEMENT_MAX_AGE_MS,
        n=SIGNAL_POOL_SIZE,
    )
    if not top12:
        print("  ⚠️  No engagement tweets in last 24h — keeping existing feed.json")

    for i, t in enumerate(top12):
        score = t["likes"] + t["retweets"]
        t["slot"] = "engagement"
        t["slot_order"] = i + 1
        t["engagementScore"] = score
        feed.append(t)
        print(
            f'  ✓ @{t["handle"]} [#{i+1}]: score={score} '
            f'(♥{t["likes"]} ↺{t["retweets"]}) — '
            f'"{t["text"][:50].strip()}…"'
        )

    feed.sort(key=lambda t: t.get("slot_order", 99))
    print(f"\n📊 Final feed: {len(feed)} tweets — top engagement only")

    if not is_publishable_feed(feed):
        print(f"\n⚠️ Only {len(feed)} post(s) fetched; minimum is {MIN_PUBLISHABLE_POSTS} — keeping existing feed.json")
        if errors:
            print(f'Failed accounts: {", ".join(errors)}')
        return

    out_path = REPO_ROOT / "feed.json"
    output = {
        "ok": True,
        "count": len(feed),
        "accountsWithPosts": len({t["handle"] for t in feed}),
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "windowHours": 24,
        "curation": "top12_engagement_no_economist",
        "errors": errors,
        "posts": feed,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved {len(feed)} posts to {out_path}")
    if errors:
        print(f'⚠️  Partial failures: {", ".join(errors)}')


if __name__ == "__main__":
    main()
