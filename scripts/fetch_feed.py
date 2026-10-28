#!/usr/bin/env python3
"""
Novaire Signal — Signal Feed fetcher.
Runs with the daily 06:00 Asia/Bangkok site refresh. Outputs feed.json.

Feed spec (up to 12 tweets per run):
  Four consecutive pages of 3 posts, ranked by engagement across the scanner accounts.
  The Economist is intentionally excluded: too broad for this compact section.

Nitter RSS is dead (HTTP 410). Timelines come from authenticated xurl search.
Final output is sorted by engagement score, then recency.
"""

import html as html_lib
import json
import os
from urllib.parse import urlencode

# Pin the existing authorized read identity, not the publisher's unrelated HOME.
XURL_HOME = os.environ.get('SIGNAL_XURL_HOME', '/root/.hermes/home')
XURL_APP = os.environ.get('SIGNAL_XURL_APP', 'novairecito')
EXPECTED_READ_ID = '923042958'  # @jnovaire; app label is not account identity.
SOURCE_STATUS = {}
import re
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

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
X_MEDIA_HOSTS = {"pbs.twimg.com"}
FXTWITTER_API_HOST = "api.fxtwitter.com"


def _safe_x_media_url(value: str) -> str:
    try:
        candidate = html_lib.unescape(str(value or "").replace(r"\/", "/"))
        parsed = urlsplit(candidate)
        if parsed.scheme != "https" or parsed.hostname not in X_MEDIA_HOSTS or not parsed.path.startswith("/media/"):
            return ""
        return parsed.geturl()
    except Exception:
        return ""


def parse_fx_public_metadata(payload: dict, expected_id: str) -> dict:
    """Normalize full post text/media from the fixed public metadata endpoint."""
    tweet = (payload or {}).get("tweet") or {}
    if str(tweet.get("id") or "") != expected_id:
        return {}
    metadata = {}
    text = str(tweet.get("text") or "").strip()
    if text:
        metadata["text"] = text
    media = tweet.get("media") or {}
    candidates = []
    for group in ("photos", "videos", "all"):
        rows = media.get(group) if isinstance(media, dict) else []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    candidates.extend((row.get("url"), row.get("thumbnail_url")))
    for candidate in candidates:
        media_url = _safe_x_media_url(candidate)
        if media_url:
            metadata["media_url"] = media_url
            metadata["media_alt"] = "Attached post media"
            break
    views = tweet.get("views")
    if isinstance(views, int) and views > 0:
        metadata["views"] = views
    return metadata


def parse_x_public_metadata(page_html: str) -> dict:
    """Extract only genuine attached-media URLs from X's public post HTML."""
    media_url = ""
    for match in re.findall(r"https:\\?/\\?/pbs\.twimg\.com/media/[^\\\"'<>\s]+", page_html or ""):
        media_url = _safe_x_media_url(match)
        if media_url:
            break
    if not media_url:
        return {}
    return {"media_url": media_url, "media_alt": "Attached post media"}


def fetch_x_public_metadata(post: dict) -> dict:
    """Fetch bounded public metadata for one already-selected post."""
    post_id = str(post.get("id") or "")
    if not post_id.isdigit():
        return {}
    metadata = {}
    fx_request = urllib.request.Request(
        f"https://{FXTWITTER_API_HOST}/status/{post_id}",
        headers={"User-Agent": "NovaireSignal/1.0"},
    )
    try:
        with urllib.request.urlopen(fx_request, timeout=6) as response:
            if response.status == 200:
                payload = json.loads(response.read(512_000).decode("utf-8", "replace"))
                metadata = parse_fx_public_metadata(payload, post_id)
    except Exception:
        pass

    if metadata.get("media_url"):
        return metadata
    request = urllib.request.Request(
        f"https://x.com/i/status/{post_id}",
        headers={"User-Agent": "Mozilla/5.0 (compatible; NovaireSignal/1.0)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            if response.status != 200:
                return metadata
            page = response.read(1_500_000).decode("utf-8", "replace")
        return {**metadata, **parse_x_public_metadata(page)}
    except Exception:
        return metadata


def enrich_selected_posts(posts: list[dict], metadata_fetcher=None) -> list[dict]:
    """Add media after ranking; never mutate rank inputs, IDs, order, or scores."""
    fetcher = metadata_fetcher or fetch_x_public_metadata
    if metadata_fetcher is not None:
        metadata = [fetcher(post) for post in posts]
    else:
        with ThreadPoolExecutor(max_workers=4) as executor:
            metadata = list(executor.map(fetcher, posts))
    enriched = []
    for post, extra in zip(posts, metadata):
        updated = dict(post)
        source_text = str(post.get("text") or "")
        full_text = str((extra or {}).get("text") or "").strip()
        if len(full_text) >= len(source_text):
            updated["text"] = full_text
        views = (extra or {}).get("views")
        if isinstance(views, int) and views > 0:
            updated["views"] = views
        media_url = _safe_x_media_url((extra or {}).get("media_url"))
        if media_url:
            updated["media_url"] = media_url
            updated["media_alt"] = str((extra or {}).get("media_alt") or "Attached post media")[:240]
        enriched.append(updated)
    return enriched


def enrich_cached_feed(path: Path) -> bool:
    """Improve cached media without laundering the feed's fetchedAt timestamp."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        posts = payload.get("posts") or []
        if len(posts) < MIN_PUBLISHABLE_POSTS:
            return False
        enriched = enrich_selected_posts(posts)
        if enriched == posts:
            return False
        payload["posts"] = enriched
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception as exc:
        print(f"  ⚠️ Cached media enrichment failed: {exc}")
        return False


def parse_iso_ms(value: str) -> tuple[str, int]:
    raw = str(value or "").strip()
    if not raw:
        return '', 0
    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return '', 0
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
        if re.match(r"^RT @", text) or any(r.get('type') == 'retweeted' for r in row.get('referenced_tweets', [])):
            continue
        tweet_id = str(row.get("id") or "").strip()
        if not tweet_id:
            continue
        created_at, created_ms = parse_iso_ms(row.get("created_at") or "")
        metrics = row.get("public_metrics") or {}
        if not created_ms or not all(isinstance(metrics.get(k), int) and metrics[k] >= 0 for k in ('like_count', 'retweet_count')):
            continue
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


def x_read(endpoint):
    """Explicit read-only provider; retain structured errors without credentials."""
    try:
        result = subprocess.run(
            [XURL_BIN, '--app', XURL_APP, '--auth', 'oauth2', endpoint],
            env={**os.environ, 'HOME': XURL_HOME}, capture_output=True, text=True, timeout=25)
        try:
            payload = json.loads(result.stdout or '{}')
        except json.JSONDecodeError:
            return {}, {'code': 'invalid_json', 'detail': 'X returned invalid JSON'}
        if result.returncode or payload.get('errors') or payload.get('status', 200) >= 400:
            # Never dump stderr/auth diagnostics or arbitrary request headers.
            return {}, {'code': payload.get('status', 'provider_error'),
                        'title': str(payload.get('title', 'X request failed'))[:120],
                        'detail': str(payload.get('detail', 'Provider rejected retrieval'))[:300]}
        if 'data' not in payload and 'meta' not in payload:
            return {}, {'code': 'invalid_payload', 'detail': 'No data or result metadata'}
        return payload, None
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {}, {'code': type(exc).__name__, 'detail': 'X CLI unavailable or timed out'}


def fetch_user_timeline(username: str) -> list:
    # Keep the established ten-post scan, then exclude retweets locally.
    query = urlencode({'query': f'from:{username}', 'max_results': 10,
                       'tweet.fields': 'created_at,public_metrics,referenced_tweets'})
    payload, error = x_read('/2/tweets/search/recent?' + query)
    tweets = tweets_from_xurl_payload(payload, username) if not error else []
    SOURCE_STATUS[username] = {'ok': error is None, 'posts': len(tweets),
                              'checkedAt': datetime.now(timezone.utc).isoformat(), 'error': error}
    print(f"  @{username}: {error if error else str(len(tweets)) + ' posts'}")
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
        if t["id"] not in exclude_ids and 0 <= (now_ms - t["createdAtMs"]) <= window_ms
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
    SOURCE_STATUS.clear()
    attempted_at = datetime.now(timezone.utc).isoformat()
    identity, identity_error = x_read('/2/users/me')
    if not identity_error and identity.get('data', {}).get('id') != EXPECTED_READ_ID:
        identity_error = {'code': 'identity_mismatch', 'detail': 'Unexpected authorized X read identity'}
    all_data: dict[str, list] = {}
    errors: list[str] = []

    print("── Engagement scanner accounts ──")
    for i, username in enumerate(ENGAGEMENT_ACCOUNTS):
        if identity_error:
            all_data[username] = []
            SOURCE_STATUS[username] = {'ok': False, 'posts': 0, 'checkedAt': attempted_at, 'error': identity_error}
        else:
            all_data[username] = fetch_user_timeline(username)
        if not SOURCE_STATUS[username]['ok']:
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
    diagnostics = {'attemptedAt': attempted_at, 'provider': 'X API v2 / OAuth2',
                   'identity': identity.get('data', {}).get('username'),
                   'accountsRequested': len(ALL_ACCOUNTS), 'accountsSucceeded': len(ALL_ACCOUNTS) - len(errors),
                   'sources': SOURCE_STATUS, 'errors': errors,
                   'status': 'failed' if not is_publishable_feed(feed) else ('partial' if errors else 'ok')}

    if not is_publishable_feed(feed):
        print(f"\n⚠️ Only {len(feed)} post(s) fetched; minimum is {MIN_PUBLISHABLE_POSTS} — keeping existing feed.json")
        if errors:
            print(f'Failed accounts: {", ".join(errors)}')
        out_path = REPO_ROOT / "feed.json"
        previous = json.loads(out_path.read_text()) if out_path.exists() else {'posts': [], 'fetchedAt': None}
        first_error = next((s['error'] for s in SOURCE_STATUS.values() if s['error']), None)
        reason = (f"X API {first_error['code']}: {first_error['detail']}" if first_error else 'Fewer than three verified posts in the 24h window')
        previous.update({'ok': False, 'status': diagnostics['status'], 'diagnostics': diagnostics,
                         'error': reason, 'errors': errors})
        out_path.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + '\n')
        print('FEED_HEALTH ' + json.dumps(diagnostics))
        return

    # Ranking is complete. Metadata enrichment happens afterward so the original
    # account population, 24-hour window, engagement weights, IDs, and order stay unchanged.
    feed = enrich_selected_posts(feed)
    out_path = REPO_ROOT / "feed.json"
    output = {
        "ok": True,
        "status": diagnostics['status'],
        "diagnostics": diagnostics,
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
    print('FEED_HEALTH ' + json.dumps(diagnostics))
    if errors:
        print(f'⚠️  Partial failures: {", ".join(errors)}')


if __name__ == "__main__":
    main()
