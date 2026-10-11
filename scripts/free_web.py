#!/usr/bin/env python3
"""Shared free search + extract ladder for polls when Firecrawl is dead.

Search: Brave (if key) → DuckDuckGo HTML (no key).
Extract: Firecrawl (skip 402) → direct fetch → Jina (if key) → Wayback.
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SECRETS = Path("/root/clawd/.secrets")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.S)
STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
DDG_HREF_RE = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"', re.I)
DDG_TITLE_RE = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]*>(.*?)</a>', re.I | re.S)
DDG_SNIP_RE = re.compile(r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', re.I | re.S)


def secret(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    if SECRETS.exists():
        for raw in SECRETS.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key == name:
                return value.strip().strip('"').strip("'")
    return ""


def _fetch(url: str, headers: dict[str, str] | None = None, timeout: int = 25) -> tuple[int, bytes, str]:
    base = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8"}
    base.update(headers or {})
    req = urllib.request.Request(url, headers=base)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), resp.geturl()
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read() if exc.fp else b""), getattr(exc, "url", url) or url
    except Exception:
        return 0, b"", url


def _clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def search(query: str, limit: int = 8, freshness: str | None = None) -> list[dict[str, Any]]:
    """Return [{title, url, description}] via Brave, then DuckDuckGo HTML."""
    # Keyless DDGS first; Brave is only a fallback for existing accounts.
    try:
        from ddgs import DDGS
        hits = DDGS(timeout=15).text(query, max_results=limit)
        results = [{"title": h.get("title", ""), "url": h.get("href", ""),
                    "description": h.get("body", "")} for h in hits if h.get("href")]
        if results:
            return results
    except Exception:
        pass
    results = _ddg_search(query, limit)
    if results:
        return results
    return _brave_search(query, limit, freshness)


def _brave_search(query: str, limit: int, freshness: str | None) -> list[dict[str, Any]]:
    key = secret("BRAVE_SEARCH_API_KEY") or secret("BRAVE_API_KEY")
    if not key:
        return []
    params = {"q": query, "count": max(1, min(int(limit), 20)), "search_lang": "en", "safesearch": "off"}
    if freshness:
        params["freshness"] = freshness
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(params)
    status, raw, _ = _fetch(url, {"X-Subscription-Token": key, "Accept": "application/json"})
    if status != 200 or not raw:
        return []
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return []
    out = []
    for item in (payload.get("web") or {}).get("results") or []:
        href = (item.get("url") or "").strip()
        if not href:
            continue
        out.append(
            {
                "title": _clean_html(item.get("title") or ""),
                "url": href,
                "description": _clean_html(item.get("description") or ""),
            }
        )
        if len(out) >= limit:
            break
    return out


def _ddg_search(query: str, limit: int) -> list[dict[str, Any]]:
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    status, raw, _ = _fetch(url)
    if status != 200 or not raw:
        return []
    body = raw.decode("utf-8", "replace")
    hrefs = DDG_HREF_RE.findall(body)
    titles = DDG_TITLE_RE.findall(body)
    snips = DDG_SNIP_RE.findall(body)
    out: list[dict[str, Any]] = []
    for i, href in enumerate(hrefs):
        resolved = _unwrap_ddg(href)
        if not resolved or resolved.startswith("https://duckduckgo.com"):
            continue
        out.append(
            {
                "title": _clean_html(titles[i] if i < len(titles) else resolved),
                "url": resolved,
                "description": _clean_html(snips[i] if i < len(snips) else ""),
            }
        )
        if len(out) >= limit:
            break
    return out


def _unwrap_ddg(href: str) -> str:
    href = html.unescape(href)
    parsed = urllib.parse.urlparse(href)
    qs = urllib.parse.parse_qs(parsed.query)
    if "uddg" in qs:
        return qs["uddg"][0]
    return href


def extract(url: str, *, allow_wayback: bool = True, timeout: int = 25) -> dict[str, Any]:
    """Return {url, title, content, route} or {url, error}.

    ``allow_wayback=False`` is required for live quotes: archives are not current
    market data. ``timeout`` is the socket-operation timeout for each live
    attempt; it is not an absolute wall-clock deadline.
    """
    # Firecrawl is deliberately excluded, including self-hosted endpoints.
    direct = _direct(url, timeout=timeout)
    if direct:
        return direct
    jina = _jina(url, timeout=timeout)
    if jina:
        return jina
    if allow_wayback:
        wayback = _wayback(url)
        if wayback:
            return wayback
    return {"url": url, "error": "free extract exhausted (direct/jina/wayback)"}


def _firecrawl_scrape_urls() -> list[str]:
    urls: list[str] = []
    local = secret("FIRECRAWL_API_URL").rstrip("/")
    if local:
        urls.append(local + "/v2/scrape")
    urls.append("https://api.firecrawl.dev/v2/scrape")
    return urls


def _firecrawl(url: str) -> dict[str, Any] | None:
    key = secret("FIRECRAWL_API_KEY")
    payload = json.dumps({"url": url, "formats": ["markdown"], "onlyMainContent": True}).encode()
    last_error = None
    for endpoint in _firecrawl_scrape_urls():
        headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        elif "api.firecrawl.dev" in endpoint:
            continue
        req = urllib.request.Request(endpoint, data=payload, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            last_error = exc.code
            if exc.code in {401, 402, 403, 429}:
                continue
            continue
        except Exception:
            continue
        data = body.get("data") or {}
        content = (data.get("markdown") or data.get("content") or "").strip()
        if len(content) < 80:
            continue
        title = str((data.get("metadata") or {}).get("title") or "")
        route = "firecrawl-local" if "127.0.0.1" in endpoint or "localhost" in endpoint else "firecrawl"
        return {"url": url, "title": title, "content": content, "route": route}
    return None


def _html_to_text(raw: bytes) -> tuple[str, str]:
    decoded = raw.decode("utf-8", "replace")
    title_m = TITLE_RE.search(decoded[:65536])
    title = html.unescape(re.sub(r"\s+", " ", title_m.group(1))).strip() if title_m else ""
    body = SCRIPT_RE.sub("\n", decoded)
    body = STYLE_RE.sub("\n", body)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"</p>", "\n\n", body, flags=re.I)
    body = re.sub(r"</h[1-6]>", "\n\n", body, flags=re.I)
    body = re.sub(r"</(div|li|tr)>", "\n", body, flags=re.I)
    body = TAG_RE.sub(" ", body)
    body = html.unescape(body)
    body = re.sub(r"[ \t]+\n", "\n", body)
    body = re.sub(r"[ \t]{2,}", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return title, body


def _direct(url: str, *, timeout: int = 25) -> dict[str, Any] | None:
    status, raw, _ = _fetch(url, timeout=timeout)
    if status != 200 or not raw:
        return None
    title, text = _html_to_text(raw)
    if len(text) < 120:
        return None
    return {"url": url, "title": title, "content": text, "route": "direct"}


def _jina(url: str, *, timeout: int = 25) -> dict[str, Any] | None:
    key = secret("JINA_API_KEY")
    if not key:
        return None
    status, raw, _ = _fetch("https://r.jina.ai/" + url, {"Authorization": f"Bearer {key}"}, timeout=timeout)
    if status != 200 or not raw:
        return None
    text = raw.decode("utf-8", "replace")
    if len(text.strip()) < 80:
        return None
    title = ""
    for line in text.splitlines()[:12]:
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            break
    return {"url": url, "title": title, "content": text, "route": "jina"}


def _wayback(url: str) -> dict[str, Any] | None:
    discovery = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    status, raw, _ = _fetch(discovery, timeout=20)
    if status != 200 or not raw:
        return None
    try:
        closest = json.loads(raw.decode("utf-8", "replace")).get("archived_snapshots", {}).get("closest", {})
    except Exception:
        return None
    snap = closest.get("url")
    if not snap:
        return None
    status, body, _ = _fetch(snap, timeout=25)
    if status != 200 or not body:
        return None
    title, text = _html_to_text(body)
    if len(text) < 120:
        return None
    ts = closest.get("timestamp") or "unknown"
    return {
        "url": url,
        "title": title,
        "content": text + f"\n\n[provenance: Wayback snapshot {ts} — not live]",
        "route": "wayback",
        "snapshot": snap,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("search", "extract"))
    parser.add_argument("value")
    parser.add_argument("--live-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=25)
    args = parser.parse_args()
    if args.command == "search":
        result = search(args.value)
    else:
        result = extract(
            args.value,
            allow_wayback=not args.live_only,
            timeout=args.timeout,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
