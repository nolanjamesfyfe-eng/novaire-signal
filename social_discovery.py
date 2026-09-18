"""Public, fail-preserving discovery for Novaire's social cards."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

INSTAGRAM_PROFILE_URL = "https://www.instagram.com/j.novaire/"
INSTAGRAM_EMBED_URL = f"{INSTAGRAM_PROFILE_URL}embed/"
INSTAGRAM_OWNER_ID = "5776730090"
INSTAGRAM_USERNAME = "j.novaire"
CHANNELS = {
    "second_renaissance": {
        "name": "The Second Renaissance",
        "url": "https://www.youtube.com/@TheSecondRenaissancePod",
        "channel_id": "UC0-4nIbz6OCjUa08WO0-vFw",
    },
    "j_novaire": {
        "name": "J.Novaire",
        "url": "https://www.youtube.com/@j.novaire",
        "channel_id": "UC_Pc6e_VYLJcJfqJysK-H8g",
    },
}
DEFAULT_CACHE = Path(__file__).with_name("social_latest.json")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/138 Safari/537.36"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _int(value: Any) -> int | None:
    try:
        return int(str(value).replace(",", "")) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _caption_title(text: str | None) -> str:
    first = (text or "Latest Instagram post").strip().splitlines()[0].strip()
    return first or "Latest Instagram post"


def _published_timestamp(item: dict[str, Any] | None) -> float | None:
    value = str((item or {}).get("published_at") or "").strip()
    if not value:
        return None
    for fmt in (None, "%b %d, %Y"):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if fmt is None else datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except ValueError:
            continue
    return None


def _keep_newest(candidate: dict[str, Any], cached: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    """Never let a partial upstream listing replace a known newer owned video."""
    if not _valid_instagram_item(cached):
        return candidate, False
    candidate_ts = _published_timestamp(candidate)
    cached_ts = _published_timestamp(cached)
    if candidate_ts is not None and cached_ts is not None and candidate_ts < cached_ts:
        return dict(cached or {}), True
    cached_item = cached or {}
    if candidate.get("url") == cached_item.get("url"):
        candidate = dict(candidate)
        for field in ("views", "likes", "metrics_verified_at", "metrics_source"):
            if candidate.get(field) is None and cached_item.get(field) is not None:
                candidate[field] = cached_item[field]
        if candidate.get("views") is not None and candidate.get("likes") is not None:
            candidate["metrics_status"] = "public metrics available"
    return candidate, False


def _valid_instagram_item(item: dict[str, Any] | None) -> bool:
    """Accept only a video owned by the personal account as a fallback."""
    item = item or {}
    return (
        item.get("type") == "reel"
        and str(item.get("owner_id") or "") == INSTAGRAM_OWNER_ID
        and item.get("owner_username") == INSTAGRAM_USERNAME
        and str(item.get("url") or "").startswith("https://www.instagram.com/reel/")
        and bool(item.get("verified_at"))
    )


def discover_instagram(session=requests) -> dict[str, Any]:
    """Discover the newest video owned by the personal Instagram account."""
    response = session.get(
        INSTAGRAM_EMBED_URL,
        headers={"User-Agent": "facebookexternalhit/1.1", "Accept-Language": "en-US,en;q=0.9"},
        timeout=25,
    )
    response.raise_for_status()
    match = re.search(r'contextJSON":"((?:\\.|[^"\\])*)"', response.text)
    if not match:
        raise ValueError("Instagram embed omitted profile context")
    context_json = json.loads('"' + match.group(1) + '"')
    context = json.loads(context_json)["context"]
    if context.get("username") != INSTAGRAM_USERNAME or str(context.get("owner_id")) != INSTAGRAM_OWNER_ID:
        raise ValueError("Instagram profile identity mismatch")
    media = [wrapper.get("shortcode_media") or {} for wrapper in context.get("graphql_media") or []]
    media = [item for item in media if item.get("shortcode") and _int(item.get("taken_at_timestamp"))
             and item.get("is_video") is True
             and str((item.get("owner") or {}).get("id") or "") == INSTAGRAM_OWNER_ID
             and (item.get("owner") or {}).get("username") == INSTAGRAM_USERNAME]
    if not media:
        raise ValueError("Instagram embed contained no owned public video")
    latest = max(media, key=lambda item: _int(item.get("taken_at_timestamp")) or 0)
    caption_edges = (latest.get("edge_media_to_caption") or {}).get("edges") or []
    caption = ((caption_edges[0].get("node") or {}).get("text") if caption_edges else "") or ""
    ts = datetime.fromtimestamp(_int(latest["taken_at_timestamp"]) or 0, tz=timezone.utc)
    item = {
        "platform": "instagram",
        "type": "reel",
        "owner_id": INSTAGRAM_OWNER_ID,
        "owner_username": INSTAGRAM_USERNAME,
        "title": _caption_title(caption),
        "url": f"https://www.instagram.com/reel/{latest['shortcode']}/",
        "published_at": ts.isoformat(),
        "views": _int(latest.get("video_play_count") or latest.get("video_view_count")),
        "likes": _int((latest.get("edge_media_preview_like") or {}).get("count")),
        "verified_at": _now(),
        "source": "Instagram public profile embed",
    }
    missing = [label for field, label in (("views", "views/watches"), ("likes", "likes")) if item.get(field) is None]
    item["metrics_status"] = (f"Instagram does not expose public {' and '.join(missing)} here" if missing else "public metrics available")
    return item


def _extract_channel_id(page: str) -> str | None:
    for pattern in (r'"channelId":"([\w-]+)"', r'"externalId":"([\w-]+)"',
                    r'<meta itemprop="channelId" content="([\w-]+)">',
                    r'<link rel="canonical" href="https://www.youtube.com/channel/([\w-]+)">'):
        match = re.search(pattern, page)
        if match:
            return match.group(1)
    return None


def _first_video_id(page: str, shorts: bool) -> str | None:
    if shorts and "shortsLockupViewModel" not in page:
        return None
    marker = page.find("shortsLockupViewModel") if shorts else 0
    segment = page[marker:] if marker >= 0 else page
    match = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', segment)
    return match.group(1) if match else None


def fetch_youtube_video(video_id: str, session=requests) -> dict[str, Any]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    response = session.get(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}, timeout=25)
    response.raise_for_status()
    page = response.text
    def text(pattern: str) -> str | None:
        match = re.search(pattern, page, re.S)
        return json.loads('"' + match.group(1) + '"') if match else None
    title = text(r'"playerOverlayVideoDetailsRenderer":\{"title":\{"simpleText":"((?:[^"\\]|\\.)*)"')
    if not title:
        title = text(r'<meta name="title" content="((?:[^"\\]|\\.)+)"')
    published = text(r'"publishDate":\{"simpleText":"([^"]+)"') or text(r'<meta itemprop="datePublished" content="([^"]+)"')
    views_match = re.search(r'"label":\{"simpleText":"Views"\},"accessibilityText":"([0-9,]+) views"', page, re.I)
    views = _int(views_match.group(1)) if views_match else None
    if views is None:
        views = _int((re.search(r'"viewCount":"([0-9]+)"', page) or [None, None])[1])
    likes_match = re.search(r'like this video along with ([0-9,]+)', page, re.I) or re.search(r'"accessibilityText":"([0-9,]+) likes"', page, re.I)
    return {
        "title": title or f"YouTube video {video_id}", "url": url, "published_at": published,
        "views": views, "likes": _int(likes_match.group(1)) if likes_match else None,
    }


def discover_youtube_channel(key: str, session=requests) -> dict[str, Any]:
    channel = CHANNELS[key]
    result: dict[str, Any] = {"name": channel["name"], "url": channel["url"], "channel_id": channel["channel_id"]}
    for kind, tab in (("video", "videos"), ("short", "shorts")):
        response = session.get(f"{channel['url']}/{tab}", headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}, timeout=25)
        response.raise_for_status()
        found_id = _extract_channel_id(response.text)
        if found_id != channel["channel_id"]:
            raise ValueError(f"YouTube identity mismatch for {key}: {found_id}")
        video_id = _first_video_id(response.text, shorts=(kind == "short"))
        if not video_id:
            result[kind] = None
            result[f"{kind}_status"] = "No public Shorts" if kind == "short" else "No public videos"
            continue
        item = fetch_youtube_video(video_id, session=session)
        item.update({"platform": "youtube", "type": kind, "channel": channel["name"], "channel_id": channel["channel_id"]})
        if kind == "short":
            item["url"] = f"https://www.youtube.com/shorts/{video_id}"
        result[kind] = item
    result.update({"verified_at": _now(), "source": "YouTube public channel tabs and watch pages"})
    return result


def _valid_snapshot(data: dict[str, Any]) -> bool:
    instagram = data.get("instagram") or {}
    if not _valid_instagram_item(instagram):
        return False
    for key, expected in CHANNELS.items():
        channel = (data.get("youtube") or {}).get(key) or {}
        if channel.get("channel_id") != expected["channel_id"] or not channel.get("verified_at"):
            return False
        if not channel.get("video") and not channel.get("short"):
            return False
    return True


def load_cache(path: Path = DEFAULT_CACHE) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
        return data if _valid_snapshot(data) else {}
    except Exception:
        return {}


def save_cache(data: dict[str, Any], path: Path = DEFAULT_CACHE) -> None:
    if not _valid_snapshot(data):
        raise ValueError("refusing incomplete social snapshot")
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(temp, path)


def discover_all(path: Path = DEFAULT_CACHE, session=requests) -> dict[str, Any]:
    """Refresh sources independently and retain dated verified cards on failure."""
    cached = load_cache(path)
    result = {"instagram": cached.get("instagram"), "youtube": dict(cached.get("youtube") or {})}
    errors: dict[str, str] = {}
    try:
        instagram, regressed = _keep_newest(discover_instagram(session=session), cached.get("instagram"))
        result["instagram"] = instagram
        if regressed:
            errors["instagram"] = "public profile embed returned older media; retained newer verified item"
    except Exception as exc:
        errors["instagram"] = str(exc)
    for key in CHANNELS:
        try:
            result["youtube"][key] = discover_youtube_channel(key, session=session)
        except Exception as exc:
            errors[key] = str(exc)
    result["refreshed_at"] = _now()
    result["errors"] = errors
    if _valid_snapshot(result):
        save_cache(result, path)
    elif not cached:
        raise RuntimeError(f"social discovery incomplete with no verified fallback: {errors}")
    return result if _valid_snapshot(result) else cached
