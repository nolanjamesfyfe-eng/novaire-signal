#!/usr/bin/env python3
"""
Novaire Signal — Daily Brief Generator
Generates index.html with premium dark + gold aesthetic + live data
"""

import requests
import json
import re
import hashlib
import math
import os
import sys
import time
import traceback
from html import escape
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from portfolio_tracker import (
    HISTORY_PATH as PORTFOLIO_HISTORY_PATH,
    SHEET_ID as PORTFOLIO_SHEET_ID,
    TFSA_GID,
    build_tracker_model,
    fetch_kraken_totals,
    load_history as load_portfolio_history,
    render_tracker_html,
    save_history as save_portfolio_history,
    upsert_daily_snapshot,
)
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

try:
    from zoneinfo import ZoneInfo
    BKK_TZ = ZoneInfo("Asia/Bangkok")
except Exception:
    BKK_TZ = timezone(timedelta(hours=7))

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
OUTPUT = "/tmp/novaire-signal/index.html"

MARKET_FUTURES = {
    "ES=F": {"label": "S&P 500", "short": "S&P FUT"},
    "NQ=F": {"label": "Nasdaq 100", "short": "NASDAQ FUT"},
    "YM=F": {"label": "Dow Jones", "short": "DOW FUT"},
}

MARKET_INDICES = {
    "^GSPC": {"label": "S&P 500", "short": "S&P CASH"},
    "^IXIC": {"label": "Nasdaq Composite", "short": "NASDAQ CASH"},
    "^DJI": {"label": "Dow Jones", "short": "DOW CASH"},
}

CRYPTO_BINANCE_PAIRS = {
    "BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "ADA": "ADAUSDT",
    "TON": "GRAMUSDT", "SUI": "SUIUSDT", "ZEC": "ZECUSDT", "NIGHT": "NIGHTUSDT",
}

# PERMANENT PRODUCT RULE — explicitly rejected by Novaire (2026-08-15):
# The five-lane daily product-voting module is retired. Never restore, rename,
# redesign, or regenerate it. Daily Action Steps come only from the Keystone.
# These split strings keep the retired UI text out of generated/searchable copy.
RETIRED_HOME_MARKERS = (
    "Daily " + "Updog Vote",
    'id="' + 'updog-card"',
    "render" + "UpdogVotes",
    "UPDOG_" + "SUGGESTIONS",
    "UPDOG_" + "ACTION_STEPS",
    "handle" + "UpdogVote",
    "Daily product " + "senate",
)

CITIES = [
    {"name": "Bangkok",    "flag": "🇹🇭", "lat": 13.7563,  "lon": 100.5018, "tz_offset": 7},
    {"name": "Medellín",   "flag": "🇨🇴", "lat": 6.2442,   "lon": -75.5812, "tz_offset": -5},
    {"name": "Edmonton",   "flag": "🇨🇦", "lat": 53.5461,  "lon": -113.4938, "tz_offset": -6},
    {"name": "Montevideo", "flag": "🇺🇾", "lat": -34.9011, "lon": -56.1645, "tz_offset": -3},
]

# Tickers: use OTC/working variants where TSX.V tickers are unavailable on Yahoo
# FVL.V → hardcoded fallback (not on Yahoo Finance); MAXX.V → hardcoded fallback; VZLA.TO = TSX CAD; MOLY.V → fallback
HOLDINGS = [
    {"ticker": "HG.CN",  "display": "HG",    "name": "Hydrograph",         "shares": 10000, "currency": "CAD", "sector": "Graphene"},
    {"ticker": "GLO.TO", "display": "GLO",   "name": "Global Atomic",       "shares": 23000, "currency": "CAD", "sector": "Uranium"},
    {"ticker": "FVL.TO",  "display": "FVL",   "name": "FreeGold Ventures",   "shares": 10000, "currency": "CAD", "sector": "Gold"},
    {"ticker": "DML.TO", "display": "DML",   "name": "Denison",             "shares": 1000,  "currency": "CAD", "sector": "Uranium"},
    {"ticker": "BNNLF",  "display": "BNNLF", "name": "Bannerman Energy",    "shares": 1300,  "currency": "USD", "sector": "Uranium"},
    {"ticker": "MAXX.CN",  "display": "MAXX",  "name": "Power Mining Corp",   "shares": 2000,  "currency": "CAD", "sector": "Silver"},
    {"ticker": "TOM.V",  "display": "TOM",   "name": "Trinity One Metals",  "shares": 5000,  "currency": "CAD", "sector": "Silver"},
    {"ticker": "LOT.AX", "display": "LOT",   "name": "Lotus Resources",     "shares": 956,   "currency": "AUD", "sector": "Uranium"},
    {"ticker": "NAM.V",  "display": "NAM",   "name": "New Age Metals",      "shares": 3772,  "currency": "CAD", "sector": "Copper"},
    {"ticker": "PNPN.V", "display": "PNPN",  "name": "Power Nickel",        "shares": 1000,  "currency": "CAD", "sector": "Copper"},
    {"ticker": "SVE.V",  "display": "SVE",   "name": "Silver One",          "shares": 2000,  "currency": "CAD", "sector": "Silver"},
    {"ticker": "PEGA.V", "display": "PEGA",  "name": "Pegasus Uranium",     "shares": 20000, "currency": "CAD", "sector": "Uranium"},
    {"ticker": "CAPT.V", "display": "CAPT",  "name": "Capitan Silver",      "shares": 500,   "currency": "CAD", "sector": "Silver"},
    {"ticker": "VZLA.TO", "display": "VZLA",  "name": "Vizsla Silver",       "shares": 200,   "currency": "CAD", "sector": "Silver"},
    {"ticker": "AEU.AX", "display": "AEU",   "name": "Atomic Eagle",        "shares": 2027,  "currency": "AUD", "sector": "Uranium"},
    {"ticker": "AAG.V",  "display": "AAG",   "name": "Aftermath Silver",    "shares": 1000,  "currency": "CAD", "sector": "Copper"},
    {"ticker": "BQSSF",  "display": "BQSSF", "name": "Boss Energy",         "shares": 500,   "currency": "USD", "sector": "Uranium"},
    {"ticker": "EU.V",   "display": "EU",    "name": "Encore Energy",       "shares": 125,   "currency": "CAD", "sector": "Uranium"},
    {"ticker": "MOLY.TO", "display": "MOLY", "name": "GreenLand Resources", "shares": 5000, "currency": "CAD", "sector": "Molybdenum"},
]

# Never substitute an old remembered quote. Off-Yahoo holdings may use the
# current Google Sheet mark (visibly labelled as a fallback); otherwise show
# unavailable. A stale number is worse than no number on a signal dashboard.
FALLBACK_PRICES = {}

WEEKLY_IDEAS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weekly_ideas.json")


def load_weekly_ideas():
    """Load the researched weekly slate; frequent builds only render it."""
    try:
        with open(WEEKLY_IDEAS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("ideas"), list):
            raise ValueError("invalid shape")
        return data
    except Exception as e:
        print(f"  ⚠ Weekly asymmetric ideas unavailable: {e}")
        return {"as_of": None, "ideas": []}

HOLDINGS_MAP = {h["ticker"]: {"shares": h["shares"], "name": h["name"], "display": h.get("display", h["ticker"].split(".")[0])} for h in HOLDINGS}
SECTORS      = {h["ticker"]: h["sector"] for h in HOLDINGS}

SECOND_RENAISSANCE = {
    "channel_url": "https://www.youtube.com/channel/UC0-4nIbz6OCjUa08WO0-vFw",
    "episode_title": "How Stress Makes You Stronger (Hormesis Explained)",
    "episode_url": "https://www.youtube.com/watch?v=TUgELHZm6ZU",
    "thumbnail_url": "https://img.youtube.com/vi/TUgELHZm6ZU/hqdefault.jpg",
    "episode_blurb": "DeFleur and Novaire explore hormesis: why controlled stress — from exercise, fasting, sauna, cold exposure, Stoicism, psychedelics, and debate — can make biological, psychological, and civic systems stronger.",
}

INSTAGRAM_PROFILE_URL = "https://www.instagram.com/j.novaire/"
INSTAGRAM_LATEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instagram_latest.json")
SECOND_RENAISSANCE_FEED = (
    "https://www.youtube.com/feeds/videos.xml?"
    "channel_id=UC0-4nIbz6OCjUa08WO0-vFw"
)


def _safe_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def load_latest_instagram():
    """Load the last publicly verified Instagram post; never invent a URL."""
    fallback = {
        "title": "Latest Instagram post",
        "url": INSTAGRAM_PROFILE_URL,
        "published_at": None,
        "views": None,
        "likes": None,
        "followers": None,
    }
    try:
        with open(INSTAGRAM_LATEST_PATH, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
        if not cached.get("url", "").startswith("https://www.instagram.com/"):
            raise ValueError("unverified Instagram URL")
        return {**fallback, **cached}
    except Exception as exc:
        print(f"  ⚠ Latest Instagram cache unavailable: {exc}")
        return fallback


def fetch_live_instagram_metrics(item):
    """Fetch public Reel plays, likes and comments from Instagram's current GraphQL endpoints."""
    match = re.search(r"/(?:p|reel|reels)/([A-Za-z0-9_-]+)", item.get("url", ""))
    if not match:
        return item
    shortcode = match.group(1)
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/138 Safari/537.36",
            "X-IG-App-ID": "936619743392459",
        })
        session.get("https://www.instagram.com/", timeout=20).raise_for_status()
        csrf = session.cookies.get("csrftoken", "")
        headers = {"X-CSRFToken": csrf, "Referer": item["url"]}
        variables = {
            "shortcode": shortcode,
            "__relay_internal__pv__PolarisAIGMMediaWebLabelEnabledrelayprovider": False,
        }
        response = session.post(
            "https://www.instagram.com/graphql/query",
            data={"doc_id": "27128499623469141", "variables": json.dumps(variables, separators=(",", ":"))},
            headers=headers, timeout=20,
        )
        response.raise_for_status()
        items = (((response.json().get("data") or {}).get("xdt_api__v1__media__shortcode__web_info") or {}).get("items") or [])
        if not items:
            return item
        media = items[0]
        current = {**item, "likes": _safe_int(media.get("like_count")), "comments": _safe_int(media.get("comment_count"))}
        current["views"] = _safe_int(media.get("play_count") or media.get("view_count"))
        if current["views"] is None and (media.get("user") or {}).get("pk"):
            clips_vars = {"data": {"include_feed_video": True, "page_size": 12, "target_user_id": str(media["user"]["pk"])}}
            clips = session.post(
                "https://www.instagram.com/graphql/query",
                data={"doc_id": "27234427476213202", "variables": json.dumps(clips_vars, separators=(",", ":"))},
                headers=headers, timeout=20,
            )
            clips.raise_for_status()
            edges = (((clips.json().get("data") or {}).get("xdt_api__v1__clips__user__connection_v2") or {}).get("edges") or [])
            for edge in edges:
                candidate = (edge.get("node") or {}).get("media") or {}
                if candidate.get("code") == shortcode:
                    current["views"] = _safe_int(candidate.get("play_count") or candidate.get("view_count"))
                    current["likes"] = _safe_int(candidate.get("like_count")) or current["likes"]
                    current["comments"] = _safe_int(candidate.get("comment_count")) or current["comments"]
                    break
        return current
    except Exception as exc:
        print(f"  ⚠ Live Instagram metrics unavailable; using verified cache: {exc}")
        return item


def fetch_latest_novaire_content():
    """Fetch current content and metrics without inventing unavailable data."""
    instagram = fetch_live_instagram_metrics(load_latest_instagram())
    instagram.update({
        "title": os.getenv("IG_LATEST_TITLE", instagram["title"]),
        "url": os.getenv("IG_LATEST_URL", instagram["url"]),
        "views": _safe_int(os.getenv("IG_LATEST_VIEWS")) if os.getenv("IG_LATEST_VIEWS") else instagram.get("views"),
        "likes": _safe_int(os.getenv("IG_LATEST_LIKES")) if os.getenv("IG_LATEST_LIKES") else instagram.get("likes"),
        "comments": _safe_int(os.getenv("IG_LATEST_COMMENTS")) if os.getenv("IG_LATEST_COMMENTS") else instagram.get("comments"),
        "followers": _safe_int(os.getenv("IG_FOLLOWERS")) if os.getenv("IG_FOLLOWERS") else instagram.get("followers"),
    })
    result = {
        "clip": None,
        "episode": {
            "title": SECOND_RENAISSANCE["episode_title"],
            "url": SECOND_RENAISSANCE["episode_url"],
            "views": None,
            "likes": None,
        },
        "instagram": instagram,
    }
    try:
        response = requests.get(
            SECOND_RENAISSANCE_FEED,
            headers={"User-Agent": "NovaireSignal/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "xml")
        entries = []
        for entry in soup.find_all("entry"):
            video_id = entry.find("yt:videoId") or entry.find("videoId")
            title = entry.find("title")
            description = entry.find("media:description") or entry.find("description")
            stats = entry.find("media:statistics") or entry.find("statistics")
            rating = entry.find("media:starRating") or entry.find("starRating")
            if not video_id or not title:
                continue
            entries.append({
                "title": title.get_text(strip=True),
                "url": f"https://www.youtube.com/watch?v={video_id.get_text(strip=True)}",
                "views": _safe_int(stats.get("views")) if stats else None,
                "likes": _safe_int(rating.get("count")) if rating else None,
                "description": description.get_text(" ", strip=True) if description else "",
            })

        if entries:
            result["clip"] = next(
                (item for item in entries if "this clip comes from" in item["description"].lower()),
                entries[0],
            )
            result["episode"] = next(
                (item for item in entries if item["url"] == SECOND_RENAISSANCE["episode_url"]),
                result["episode"],
            )
    except Exception as exc:
        print(f"  ⚠ Latest Novaire social feed unavailable: {exc}")
    return result

# Portfolio basis stats (from spreadsheet)
PORT_BASIS_CAD = 99_234.14
PORT_ATH       = 113_522
PORT_ROI_ABS   = 24_660.95

# ── Radar Moonshots — discovery subreddits (max 5 lines, refreshes every build) ──
RADAR_MOONSHOT_SUBS = [
    # Crypto moonshots & new projects
    ("CryptoMoonShots", "crypto"),
    ("altcoins",        "crypto"),
    ("defi",            "crypto"),
    # Micro cap resource plays
    ("uranium",         "resource"),
    ("SilverSqueeze",   "resource"),
    ("MiningStocks",    "resource"),
    ("pennystocks",     "resource"),
]

RADAR_CRYPTO_KEYWORDS  = {"coin","token","crypto","blockchain","gem","defi","layer","launch","project","airdrop","protocol","nft","dao","yield","swap","staking","presale","altcoin","bull","pump"}
RADAR_RESOURCE_KEYWORDS = {"stock","mining","uranium","silver","gold","exploration","drill","cap","copper","lithium","junior","ounce","resource","deposit","mineral","graphene","platinum","vanadium","zinc"}

RADAR_STATIC_FALLBACK = [
    {"title": "New AI crypto infrastructure projects launching weekly — scan r/CryptoMoonShots daily for sub-$50M cap gems.", "source": ""},
    {"title": "Uranium junior with high-grade Athabasca drill results — discovery risk priced in, asymmetric upside.", "source": ""},
    {"title": "Silver micro cap with Nevada exploration license — $500-1K starter position ahead of resource estimate.", "source": ""},
    {"title": "Critical minerals ETF rotation incoming — scout early-stage graphene and lithium plays under $200M cap.", "source": ""},
    {"title": "DeFi protocol with real yield and sub-$10M TVL — early entry before any major exchange listing.", "source": ""},
]

def fetch_fed_signal():
    """Hardcoded Fed Signal data. Update when FOMC decisions change."""
    from datetime import date as _date
    today = datetime.now(timezone.utc).date()
    fomc_date = _date(2026, 9, 16)
    days_until = (fomc_date - today).days
    return {
        "next_decision": "September 16, 2026",
        "days_until": days_until,
        "fed_funds_rate": "3.50\u20133.75%",
        "next_meeting": "September FOMC",
        "hold_pct": 55,
        "cut_25bps_pct": 0,
    }


def fetch_top5_economies():
    """Top 5 economies by GDP nominal. Hardcoded — update quarterly."""
    return [
        {"country": "USA",     "flag": "\U0001f1fa\U0001f1f8", "gdp": "$28.8T", "per_capita": "$85,370", "inflation": "2.8%", "gdp_qoq": "+0.7%", "gdp_yoy": "+2.1%"},
        {"country": "China",   "flag": "\U0001f1e8\U0001f1f3", "gdp": "$18.5T", "per_capita": "$13,140", "inflation": "0.7%", "gdp_qoq": "+1.4%", "gdp_yoy": "+4.5%"},
        {"country": "Germany", "flag": "\U0001f1e9\U0001f1ea", "gdp": "$4.6T",  "per_capita": "$54,290", "inflation": "2.3%", "gdp_qoq": "+0.3%", "gdp_yoy": "+0.2%"},
        {"country": "Japan",   "flag": "\U0001f1ef\U0001f1f5", "gdp": "$4.2T",  "per_capita": "$33,950", "inflation": "3.6%", "gdp_qoq": "+0.3%", "gdp_yoy": "+0.1%"},
        {"country": "India",   "flag": "\U0001f1ee\U0001f1f3", "gdp": "$3.9T",  "per_capita": "$2,730",  "inflation": "4.3%", "gdp_qoq": "+1.8%", "gdp_yoy": "+7.8%"},
    ]


def fetch_radar_moonshots():
    """Fetch top 5 moonshot ideas from Reddit — new crypto projects + micro cap resource plays under $1B."""
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    posts  = {"crypto": [], "resource": []}

    for sub, category in RADAR_MOONSHOT_SUBS:
        try:
            r = requests.get(
                f"https://www.reddit.com/r/{sub}/hot.json?limit=15",
                headers={"User-Agent": "NovaireSignal/1.0"},
                timeout=8,
            )
            for post in r.json().get("data", {}).get("children", []):
                d       = post.get("data", {})
                created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
                title   = (d.get("title") or "").strip()
                score   = d.get("score", 0)
                kws     = RADAR_CRYPTO_KEYWORDS if category == "crypto" else RADAR_RESOURCE_KEYWORDS
                relevant = any(kw in title.lower() for kw in kws)
                if (created >= cutoff and not d.get("stickied")
                        and len(title) > 25 and score >= 5 and relevant):
                    posts[category].append({
                        "title":  title[:130] + ("\u2026" if len(title) > 130 else ""),
                        "score":  score,
                        "source": f"r/{sub}",
                    })
        except Exception:
            pass

    # Sort each bucket by score desc, pick top 1 per category
    crypto_top   = sorted(posts["crypto"],   key=lambda x: x["score"], reverse=True)[:1]
    resource_top = sorted(posts["resource"], key=lambda x: x["score"], reverse=True)[:1]

    return {
        "crypto":   crypto_top   if crypto_top   else RADAR_STATIC_FALLBACK[:1],
        "resource": resource_top if resource_top else RADAR_STATIC_FALLBACK[3:4],
    }

WEATHER_CODES = {
    0: "Clear Sky ☀️", 1: "Mainly Clear 🌤", 2: "Partly Cloudy ⛅", 3: "Overcast ☁️",
    45: "Foggy 🌫", 48: "Icy Fog 🌫", 51: "Light Drizzle 🌦", 53: "Drizzle 🌦",
    55: "Heavy Drizzle 🌧", 61: "Slight Rain 🌧", 63: "Rain 🌧", 65: "Heavy Rain 🌧",
    71: "Slight Snow 🌨", 73: "Snow 🌨", 75: "Heavy Snow ❄️", 77: "Snow Grains 🌨",
    80: "Showers 🌦", 81: "Showers 🌦", 82: "Violent Showers ⛈", 85: "Slight Snow ❄️",
    86: "Heavy Snow ❄️", 95: "Thunderstorm ⛈", 96: "Thunderstorm ⛈", 99: "Thunderstorm ⛈",
}

ZODIAC_SIGNS = [
    {"cutoff": (1, 19),  "name": "Capricorn",   "symbol": "♑", "range": "Dec 22 – Jan 19", "desc": "Disciplined, ambitious, and patient — Capricorns build empires one brick at a time."},
    {"cutoff": (2, 18),  "name": "Aquarius",    "symbol": "♒", "range": "Jan 20 – Feb 18", "desc": "Innovative, independent, and humanitarian — forward-thinking visionaries who value freedom."},
    {"cutoff": (3, 20),  "name": "Pisces",      "symbol": "♓", "range": "Feb 19 – Mar 20", "desc": "Intuitive, compassionate, and creative — Pisces feel the currents others cannot see."},
    {"cutoff": (4, 19),  "name": "Aries",       "symbol": "♈", "range": "Mar 21 – Apr 19", "desc": "Bold, energetic, and pioneering — Aries charge headfirst into new territory."},
    {"cutoff": (5, 20),  "name": "Taurus",      "symbol": "♉", "range": "Apr 20 – May 20", "desc": "Steadfast, practical, and patient — Taurus builds lasting value through consistency."},
    {"cutoff": (6, 20),  "name": "Gemini",      "symbol": "♊", "range": "May 21 – Jun 20", "desc": "Curious, adaptable, and communicative — Gemini see every angle of the picture."},
    {"cutoff": (7, 22),  "name": "Cancer",      "symbol": "♋", "range": "Jun 21 – Jul 22", "desc": "Intuitive, nurturing, and protective — Cancer builds fortresses of loyalty."},
    {"cutoff": (8, 22),  "name": "Leo",         "symbol": "♌", "range": "Jul 23 – Aug 22", "desc": "Charismatic, bold, and generous — Leo commands the room and inspires the crowd."},
    {"cutoff": (9, 22),  "name": "Virgo",       "symbol": "♍", "range": "Aug 23 – Sep 22", "desc": "Analytical, precise, and dedicated — Virgo optimizes everything they touch."},
    {"cutoff": (10, 22), "name": "Libra",       "symbol": "♎", "range": "Sep 23 – Oct 22", "desc": "Balanced, diplomatic, and aesthetic — Libra seeks harmony in all things."},
    {"cutoff": (11, 21), "name": "Scorpio",     "symbol": "♏", "range": "Oct 23 – Nov 21", "desc": "Intense, perceptive, and transformative — Scorpio sees what others hide."},
    {"cutoff": (12, 21), "name": "Sagittarius", "symbol": "♐", "range": "Nov 22 – Dec 21", "desc": "Adventurous, optimistic, and philosophical — Sagittarians seek truth beyond the horizon."},
]

# SAT/GRE Word of the Day (rotates daily, not in Novaire's 2011 deck)
SAT_WORDS = [
    {"word": "acrimony", "def": "bitterness or ill feeling", "sentence": "The acrimony between the two factions made any compromise impossible."},
    {"word": "alacrity", "def": "brisk and cheerful readiness", "sentence": "She accepted the challenge with alacrity, eager to prove her worth."},
    {"word": "ameliorate", "def": "to make something bad better", "sentence": "The new policies were designed to ameliorate the housing crisis."},
    {"word": "anachronism", "def": "something out of its proper time", "sentence": "His formal manners seemed an anachronism in the casual startup culture."},
    {"word": "anathema", "def": "something intensely disliked or loathed", "sentence": "Passive investing was anathema to the active fund managers."},
    {"word": "antithesis", "def": "the exact opposite", "sentence": "His reckless spending was the antithesis of prudent financial planning."},
    {"word": "apocryphal", "def": "of doubtful authenticity", "sentence": "The apocryphal story of his early failures became part of corporate legend."},
    {"word": "approbation", "def": "approval or praise", "sentence": "The strategy won the approbation of even the most skeptical board members."},
    {"word": "ascetic", "def": "characterized by severe self-discipline", "sentence": "He lived an ascetic life, reinvesting every dollar into his portfolio."},
    {"word": "bellicose", "def": "demonstrating aggression and willingness to fight", "sentence": "The bellicose rhetoric from both nations rattled global markets."},
    {"word": "bombastic", "def": "high-sounding but with little meaning", "sentence": "His bombastic predictions rarely materialized into actual returns."},
    {"word": "cacophony", "def": "a harsh, discordant mixture of sounds", "sentence": "The cacophony of conflicting analyst opinions left investors confused."},
    {"word": "capricious", "def": "given to sudden changes of mood or behavior", "sentence": "The capricious nature of the market punished those without conviction."},
    {"word": "castigate", "def": "to reprimand severely", "sentence": "The CEO was castigated by shareholders for the failed acquisition."},
    {"word": "circumspect", "def": "wary and unwilling to take risks", "sentence": "A circumspect approach to leverage saved them during the crash."},
    {"word": "clandestine", "def": "kept secret or done secretively", "sentence": "The clandestine meetings between executives raised suspicions."},
    {"word": "cogent", "def": "clear, logical, and convincing", "sentence": "He presented a cogent argument for increasing exposure to uranium."},
    {"word": "commensurate", "def": "corresponding in size or degree", "sentence": "The risk must be commensurate with the potential reward."},
    {"word": "compendium", "def": "a collection of concise but detailed information", "sentence": "The annual report served as a compendium of market insights."},
    {"word": "conflagration", "def": "an extensive fire; a conflict or war", "sentence": "The conflagration in the bond market spread to equities within hours."},
    {"word": "conundrum", "def": "a confusing and difficult problem", "sentence": "The Fed faced a conundrum: raise rates and crash markets, or let inflation run."},
    {"word": "corroborate", "def": "to confirm or give support to", "sentence": "The earnings report corroborated the thesis of accelerating growth."},
    {"word": "deleterious", "def": "causing harm or damage", "sentence": "The deleterious effects of inflation eroded purchasing power silently."},
    {"word": "diatribe", "def": "a forceful and bitter verbal attack", "sentence": "His diatribe against central bank policy went viral on financial Twitter."},
    {"word": "dichotomy", "def": "a division into two contrasting things", "sentence": "The dichotomy between public optimism and private pessimism was striking."},
    {"word": "diffident", "def": "modest or shy because of lack of self-confidence", "sentence": "Despite his success, he remained diffident about his market timing abilities."},
    {"word": "ebullient", "def": "cheerful and full of energy", "sentence": "The ebullient mood on the trading floor suggested a strong close."},
    {"word": "efficacious", "def": "successful in producing a desired result", "sentence": "The stimulus proved efficacious in averting a deeper recession."},
    {"word": "egregious", "def": "outstandingly bad; shocking", "sentence": "The egregious accounting fraud destroyed decades of shareholder value."},
    {"word": "enervate", "def": "to drain of energy or vitality", "sentence": "The prolonged bear market enervated even the most bullish investors."},
    {"word": "ephemeral", "def": "lasting for a very short time", "sentence": "The rally proved ephemeral, fading by the afternoon session."},
    {"word": "equanimity", "def": "mental calmness in difficult situations", "sentence": "He faced the market crash with remarkable equanimity."},
    {"word": "esoteric", "def": "intended for only a small group with specialized knowledge", "sentence": "The esoteric derivatives strategy was understood by few on the desk."},
    {"word": "exacerbate", "def": "to make a problem worse", "sentence": "The tariffs only exacerbated the supply chain disruptions."},
    {"word": "exigent", "def": "pressing; demanding immediate attention", "sentence": "The exigent liquidity crisis required overnight intervention."},
    {"word": "fastidious", "def": "very attentive to detail", "sentence": "His fastidious record-keeping saved him during the audit."},
    {"word": "feckless", "def": "lacking initiative or strength of character", "sentence": "The feckless response to early warning signs proved costly."},
    {"word": "frenetic", "def": "fast and energetic but disorganized", "sentence": "The frenetic trading during expiration week tested everyone's nerves."},
    {"word": "garrulous", "def": "excessively talkative", "sentence": "The garrulous analyst buried the key insight in an hour of rambling."},
    {"word": "gregarious", "def": "fond of company; sociable", "sentence": "His gregarious nature made him a natural at investor conferences."},
    {"word": "harbinger", "def": "a person or thing that signals something to come", "sentence": "The inverted yield curve was a harbinger of the recession ahead."},
    {"word": "hegemony", "def": "leadership or dominance over others", "sentence": "America's economic hegemony faces new challenges from the East."},
    {"word": "hubris", "def": "excessive pride or self-confidence", "sentence": "His hubris blinded him to the risks accumulating in his portfolio."},
    {"word": "iconoclast", "def": "a person who attacks cherished beliefs", "sentence": "The iconoclast fund manager shorted every market darling."},
    {"word": "implacable", "def": "unable to be appeased or placated", "sentence": "The implacable march of inflation demanded a policy response."},
    {"word": "inchoate", "def": "just begun and not fully formed", "sentence": "The inchoate recovery showed signs of fragility."},
    {"word": "inexorable", "def": "impossible to stop or prevent", "sentence": "The inexorable rise of AI would reshape every sector."},
    {"word": "insidious", "def": "proceeding harmfully in a gradual way", "sentence": "The insidious creep of fees compounded into massive losses over time."},
    {"word": "intransigent", "def": "unwilling to change one's views", "sentence": "The intransigent stance of both parties prolonged the debt ceiling crisis."},
    {"word": "invective", "def": "insulting or abusive language", "sentence": "The earnings call devolved into invective between the CEO and analysts."},
    {"word": "laconic", "def": "using very few words", "sentence": "His laconic investment thesis fit on a single index card."},
    {"word": "lassitude", "def": "a state of physical or mental weariness", "sentence": "A strange lassitude settled over markets during the summer doldrums."},
    {"word": "magnanimous", "def": "generous or forgiving", "sentence": "The magnanimous offer to renegotiate terms surprised everyone."},
    {"word": "mendacious", "def": "not telling the truth; lying", "sentence": "The mendacious earnings projections eventually caught up with them."},
    {"word": "mercurial", "def": "subject to sudden changes of mood", "sentence": "The mercurial founder was brilliant but impossible to predict."},
    {"word": "munificent", "def": "larger or more generous than usual", "sentence": "The munificent dividend attracted income-focused investors."},
    {"word": "nascent", "def": "just beginning to develop", "sentence": "The nascent bull market showed increasing signs of strength."},
    {"word": "nebulous", "def": "unclear, vague, or ill-defined", "sentence": "The company's growth strategy remained frustratingly nebulous."},
    {"word": "nefarious", "def": "wicked or criminal", "sentence": "The nefarious scheme to manipulate prices was uncovered by regulators."},
    {"word": "obfuscate", "def": "to make obscure or unclear", "sentence": "The complex footnotes seemed designed to obfuscate the true liabilities."},
    {"word": "obstinate", "def": "stubbornly refusing to change", "sentence": "His obstinate faith in the thesis paid off after three painful years."},
    {"word": "onerous", "def": "involving heavy obligations", "sentence": "The onerous debt covenants restricted the company's flexibility."},
    {"word": "ostentatious", "def": "designed to impress or attract notice", "sentence": "The ostentatious headquarters stood in contrast to their frugal claims."},
    {"word": "panacea", "def": "a solution for all problems", "sentence": "Rate cuts were not a panacea for structural economic issues."},
    {"word": "parsimonious", "def": "excessively unwilling to spend money", "sentence": "The parsimonious allocation to growth stocks hurt returns."},
    {"word": "paucity", "def": "the presence of something in small quantities", "sentence": "The paucity of quality assets drove investors into riskier bets."},
    {"word": "perfidious", "def": "deceitful and untrustworthy", "sentence": "The perfidious partner had been skimming profits for years."},
    {"word": "perspicacious", "def": "having a ready insight into things", "sentence": "The perspicacious analyst spotted the accounting irregularities early."},
    {"word": "petulant", "def": "childishly sulky or bad-tempered", "sentence": "His petulant response to criticism damaged his credibility."},
    {"word": "platitude", "def": "a remark used too often to be interesting", "sentence": "The CEO's letter was full of platitudes about stakeholder value."},
    {"word": "plethora", "def": "an excess or overabundance", "sentence": "The plethora of new ETFs made selection increasingly difficult."},
    {"word": "portentous", "def": "of great importance; ominous", "sentence": "The portentous decline in leading indicators worried strategists."},
    {"word": "precipitous", "def": "dangerously high or steep; sudden", "sentence": "The precipitous drop in oil prices caught everyone off guard."},
    {"word": "prescient", "def": "having knowledge of events before they happen", "sentence": "Her prescient call on the housing bubble made her reputation."},
    {"word": "profligate", "def": "recklessly extravagant or wasteful", "sentence": "The profligate spending eventually bankrupted the enterprise."},
    {"word": "propitious", "def": "favorable; giving a good chance of success", "sentence": "Conditions were propitious for a sector rotation into value."},
    {"word": "prosaic", "def": "lacking imagination; dull", "sentence": "The prosaic quarterly update contained no surprises."},
    {"word": "pugnacious", "def": "eager to fight or argue", "sentence": "The pugnacious hedge fund manager relished confrontation."},
    {"word": "quagmire", "def": "a difficult or precarious situation", "sentence": "The regulatory quagmire delayed the merger by eighteen months."},
    {"word": "quixotic", "def": "extremely idealistic; unrealistic", "sentence": "His quixotic goal of beating the market every year set him up for failure."},
    {"word": "recalcitrant", "def": "having an obstinately uncooperative attitude", "sentence": "The recalcitrant board refused to consider any takeover offer."},
    {"word": "redoubtable", "def": "formidable, especially as an opponent", "sentence": "The redoubtable competitor forced them to innovate or die."},
    {"word": "refractory", "def": "resistant to a process or treatment", "sentence": "Inflation proved refractory to traditional monetary policy tools."},
    {"word": "repudiate", "def": "to refuse to accept or be associated with", "sentence": "The new management repudiated the aggressive accounting of their predecessors."},
    {"word": "sagacious", "def": "having keen mental discernment", "sentence": "The sagacious investor saw opportunity where others saw only risk."},
    {"word": "salient", "def": "most noticeable or important", "sentence": "The salient point was buried on page forty-seven of the prospectus."},
    {"word": "sardonic", "def": "grimly mocking or cynical", "sentence": "His sardonic commentary on market euphoria proved prophetic."},
    {"word": "specious", "def": "superficially plausible but actually wrong", "sentence": "The specious argument for infinite valuations collapsed with rates."},
    {"word": "spurious", "def": "not genuine; false", "sentence": "The spurious correlation led many astray in their analysis."},
    {"word": "strident", "def": "loud and harsh; presenting a point forcefully", "sentence": "The strident warnings from bears were ignored until too late."},
    {"word": "supercilious", "def": "behaving as if one is superior to others", "sentence": "The supercilious dismissal of retail investors backfired spectacularly."},
    {"word": "surreptitious", "def": "kept secret because it would be disapproved of", "sentence": "The surreptitious stock sales by insiders preceded the crash."},
    {"word": "taciturn", "def": "reserved or uncommunicative", "sentence": "The taciturn value investor let his returns speak for him."},
    {"word": "temerity", "def": "excessive confidence or boldness", "sentence": "He had the temerity to short the most crowded trade in decades."},
    {"word": "tenuous", "def": "very weak or slight", "sentence": "The tenuous connection between policy and outcomes frustrated everyone."},
    {"word": "trenchant", "def": "vigorous or incisive in expression", "sentence": "Her trenchant analysis cut through the noise to the core issue."},
    {"word": "truculent", "def": "eager to argue or fight; aggressively defiant", "sentence": "The truculent response to regulators only intensified scrutiny."},
    {"word": "ubiquitous", "def": "present everywhere", "sentence": "The ubiquitous presence of passive funds reshaped market dynamics."},
    {"word": "untenable", "def": "not able to be maintained or defended", "sentence": "The valuation became untenable once growth decelerated."},
    {"word": "vacuous", "def": "having or showing a lack of thought or intelligence", "sentence": "The vacuous commentary offered nothing actionable."},
    {"word": "venal", "def": "susceptible to bribery; corrupt", "sentence": "The venal officials were paid to look the other way."},
    {"word": "vicissitude", "def": "a change of circumstances, typically unwelcome", "sentence": "The vicissitudes of the market humbled even the most confident."},
    {"word": "vitriolic", "def": "filled with bitter criticism", "sentence": "The vitriolic short report wiped out a third of the market cap."},
    {"word": "volatile", "def": "liable to change rapidly and unpredictably", "sentence": "The volatile price action shook out weak hands."},
    {"word": "voracious", "def": "wanting great quantities of something", "sentence": "His voracious appetite for information gave him an edge."},
    {"word": "zealous", "def": "showing great energy or enthusiasm", "sentence": "The zealous pursuit of alpha drove excessive risk-taking."},
]

THAI_WORDS = [
    {"thai": "กำลอม (kam-lom)",           "meaning": "speculate — taking calculated risks for potential gains"},
    {"thai": "สบาย (sa-baai)",            "meaning": "comfortable, easy, relaxed — the Thai ideal of wellbeing"},
    {"thai": "เงิน (ngern)",              "meaning": "money / silver — the same word covers both in Thai"},
    {"thai": "ใจเย็น (jai-yen)",          "meaning": "cool heart — stay calm, don't panic"},
    {"thai": "ไม่เป็นไร (mai-pen-rai)",   "meaning": "never mind, no worries — the Thai spirit of ease"},
    {"thai": "มีโอกาส (mee-o-gard)",      "meaning": "there is an opportunity — seize the moment"},
    {"thai": "ขยัน (kha-yan)",            "meaning": "hardworking, diligent — a virtue deeply respected"},
    {"thai": "อดทน (ot-ton)",             "meaning": "patient, endure — the long-game mindset"},
    {"thai": "กล้าหาญ (gla-harn)",        "meaning": "brave, courageous — bold in the face of uncertainty"},
    {"thai": "ความสำเร็จ (kwaam-sam-ret)","meaning": "success, achievement — the destination"},
    {"thai": "ตลาด (ta-lard)",            "meaning": "market — where opportunity and risk converge"},
    {"thai": "ทอง (tong)",               "meaning": "gold — precious metal and lucky color in Thai culture"},
    {"thai": "ฝัน (fan)",               "meaning": "dream — the vision that drives you forward"},
    {"thai": "ชีวิต (chee-wit)",          "meaning": "life — make it count"},
    {"thai": "พอใจ (por-jai)",            "meaning": "satisfied, content — knowing when enough is enough"},
    {"thai": "เป้าหมาย (pao-mai)",        "meaning": "goal, target — what you're aiming at"},
    {"thai": "ความเสี่ยง (kwaam-siang)",   "meaning": "risk — the price of opportunity"},
    {"thai": "กำไร (gam-rai)",            "meaning": "profit, gain — the reward for good judgment"},
    {"thai": "สำเร็จ (sam-ret)",          "meaning": "to succeed, accomplish — to reach the summit"},
    {"thai": "นักลงทุน (nak-long-tun)",   "meaning": "investor — one who plants seeds for the future"},
    {"thai": "อนาคต (a-na-kot)",          "meaning": "future — the horizon you're always moving toward"},
    {"thai": "เวลา (way-la)",             "meaning": "time — the most precious and non-renewable resource"},
    {"thai": "ทำงาน (tham-ngan)",         "meaning": "to work — the engine of all progress"},
    {"thai": "แข็งแกร่ง (kaeng-graeng)", "meaning": "strong, resilient — built for adversity"},
    {"thai": "เรียนรู้ (rian-roo)",       "meaning": "to learn — the compounding asset of the mind"},
    {"thai": "ความจริง (kwaam-jing)",     "meaning": "truth, reality — what matters in the long run"},
    {"thai": "ปัญญา (pan-ya)",           "meaning": "wisdom — knowledge applied with discernment"},
    {"thai": "สมดุล (som-dun)",           "meaning": "balance — the key to sustainable growth"},
    {"thai": "พัฒนา (pat-ta-na)",         "meaning": "develop, progress — always moving forward"},
    {"thai": "เริ่มต้น (rerm-ton)",       "meaning": "to begin, start — the hardest and most important step"},
]

SPANISH_WORDS = [
    {"spanish": "Negocio", "pron": "neh-GO-see-oh", "meaning": "business — from the Latin 'negotium' (denial of leisure). Hustle never changes."},
    {"spanish": "Riesgo", "pron": "ree-ES-go", "meaning": "risk — no riesgo, no recompensa."},
    {"spanish": "Ganancia", "pron": "gah-NAN-see-ah", "meaning": "profit, gain — the sweet taste of a thesis playing out."},
    {"spanish": "Apalancamiento", "pron": "ah-pah-lan-kah-mee-EN-toh", "meaning": "leverage — a double-edged sword that builds empires or buries them."},
    {"spanish": "Sabiduría", "pron": "sah-bee-doo-REE-ah", "meaning": "wisdom — the ultimate compounding asset."},
    {"spanish": "Confianza", "pron": "con-fee-AN-sah", "meaning": "trust, confidence — the currency that makes everything else work."},
    {"spanish": "Oportunidad", "pron": "oh-por-too-nee-DAHD", "meaning": "opportunity — they're everywhere if you're paying attention."},
    {"spanish": "Voluntad", "pron": "vo-loon-TAHD", "meaning": "willpower — the force multiplier behind every great outcome."},
    {"spanish": "Libertad", "pron": "lee-ber-TAHD", "meaning": "freedom — what all of this is ultimately about."},
    {"spanish": "Patrimonio", "pron": "pah-tree-MO-nee-oh", "meaning": "wealth, heritage — what you build and what you leave behind."},
    {"spanish": "Emprendedor", "pron": "em-pren-deh-DOR", "meaning": "entrepreneur — one who undertakes. The doer, not the talker."},
    {"spanish": "Resiliencia", "pron": "reh-see-lee-EN-see-ah", "meaning": "resilience — antifragility's Spanish cousin."},
    {"spanish": "Audaz", "pron": "ow-DAHZ", "meaning": "bold, audacious — fortune favors the audaz."},
    {"spanish": "Abundancia", "pron": "ah-boon-DAN-see-ah", "meaning": "abundance — the mindset that creates more than it consumes."},
    {"spanish": "Disciplina", "pron": "dees-see-PLEE-nah", "meaning": "discipline — the bridge between goals and accomplishments."},
    {"spanish": "Poder", "pron": "po-DEHR", "meaning": "power — both ability and influence. Use wisely."},
    {"spanish": "Inversión", "pron": "een-ver-see-OHN", "meaning": "investment — planting seeds today for tomorrow's harvest."},
    {"spanish": "Contrario", "pron": "con-TRAH-ree-oh", "meaning": "contrarian — when everyone zigs, the contrario zags."},
    {"spanish": "Evolución", "pron": "eh-vo-loo-see-OHN", "meaning": "evolution — adapt or die. The fund knows."},
    {"spanish": "Tesón", "pron": "teh-SOHN", "meaning": "tenacity, grit — the relentless pursuit that separates dreamers from builders."},
    {"spanish": "Soberanía", "pron": "so-beh-rah-NEE-ah", "meaning": "sovereignty — self-rule. The ultimate goal for individuals and nations."},
    {"spanish": "Verdad", "pron": "ver-DAHD", "meaning": "truth — what survives when narratives collapse."},
    {"spanish": "Coraje", "pron": "co-RAH-heh", "meaning": "courage — not the absence of fear, but action despite it."},
    {"spanish": "Inflación", "pron": "een-flah-see-OHN", "meaning": "inflation — the silent thief. Your money's worst enemy."},
    {"spanish": "Rendimiento", "pron": "ren-dee-mee-EN-toh", "meaning": "yield, performance — what the portfolio delivers."},
    {"spanish": "Ventaja", "pron": "ven-TAH-hah", "meaning": "advantage, edge — the asymmetry you're always hunting for."},
    {"spanish": "Convicción", "pron": "con-vik-see-OHN", "meaning": "conviction — buy with it or don't buy at all."},
    {"spanish": "Despertar", "pron": "des-per-TAR", "meaning": "to awaken — the first step of every revolution."},
    {"spanish": "Legado", "pron": "leh-GAH-doh", "meaning": "legacy — what endures after you're gone."},
    {"spanish": "Imparable", "pron": "eem-pah-RAH-bleh", "meaning": "unstoppable — a man on the rise."},
]

MOTIVATION_QUOTES = [
    {"text": "The man who moves a mountain begins by carrying away small stones.", "author": "Confucius"},
    {"text": "Hard work beats talent when talent doesn't work hard.", "author": "Tim Notke"},
    {"text": "Success is not final, failure is not fatal: it is the courage to continue that counts.", "author": "Winston Churchill"},
    {"text": "Do one thing every day that scares you.", "author": "Eleanor Roosevelt"},
    {"text": "The only way to do great work is to love what you do.", "author": "Steve Jobs"},
    {"text": "Believe you can and you're halfway there.", "author": "Theodore Roosevelt"},
    {"text": "Don't watch the clock; do what it does. Keep going.", "author": "Sam Levenson"},
    {"text": "The future belongs to those who believe in the beauty of their dreams.", "author": "Eleanor Roosevelt"},
    {"text": "Act as if what you do makes a difference. It does.", "author": "William James"},
    {"text": "Start where you are. Use what you have. Do what you can.", "author": "Arthur Ashe"},
    {"text": "It does not matter how slowly you go as long as you do not stop.", "author": "Confucius"},
    {"text": "Everything you've ever wanted is on the other side of fear.", "author": "George Addair"},
    {"text": "You are never too old to set another goal or to dream a new dream.", "author": "C.S. Lewis"},
    {"text": "Energy and persistence conquer all things.", "author": "Benjamin Franklin"},
    {"text": "What you get by achieving your goals is not as important as what you become.", "author": "Thoreau"},
]

# Embedded JS quote arrays (30+ per category) for client-side dedup rotation
# These are baked into the HTML so no server round-trip needed
QUOTES_JS_INVESTING = """[
  {text:"The stock market is a device for transferring money from the impatient to the patient.", author:"Warren Buffett"},
  {text:"In the short run, the market is a voting machine. In the long run, it is a weighing machine.", author:"Benjamin Graham"},
  {text:"It's not whether you're right or wrong, but how much money you make when you're right and how much you lose when you're wrong.", author:"George Soros"},
  {text:"The four most dangerous words in investing are: 'this time it's different.'", author:"Sir John Templeton"},
  {text:"Price is what you pay. Value is what you get.", author:"Warren Buffett"},
  {text:"Know what you own, and know why you own it.", author:"Peter Lynch"},
  {text:"Risk comes from not knowing what you're doing.", author:"Warren Buffett"},
  {text:"An investment in knowledge pays the best interest.", author:"Benjamin Franklin"},
  {text:"The most contrarian thing of all is not to oppose the crowd but to think for yourself.", author:"Peter Thiel"},
  {text:"Compound interest is the eighth wonder of the world. He who understands it, earns it; he who doesn't, pays it.", author:"Albert Einstein"},
  {text:"The individual investor should act consistently as an investor and not as a speculator.", author:"Benjamin Graham"},
  {text:"Wide diversification is only required when investors do not understand what they are doing.", author:"Warren Buffett"},
  {text:"Our favourite holding period is forever.", author:"Warren Buffett"},
  {text:"It takes 20 years to build a reputation and five minutes to ruin it.", author:"Warren Buffett"},
  {text:"The time of maximum pessimism is the best time to buy.", author:"Sir John Templeton"},
  {text:"Markets can remain irrational longer than you can remain solvent.", author:"John Maynard Keynes"},
  {text:"Be fearful when others are greedy, and greedy when others are fearful.", author:"Warren Buffett"},
  {text:"The biggest risk is not taking any risk.", author:"Mark Zuckerberg"},
  {text:"Invest in yourself. Your career is the engine of your wealth.", author:"Paul Clitheroe"},
  {text:"The goal of a successful trader is to make the best trades. Money is secondary.", author:"Alexander Elder"},
  {text:"Do not save what is left after spending; instead spend what is left after saving.", author:"Warren Buffett"},
  {text:"Financial freedom is available to those who learn about it and work for it.", author:"Robert Kiyosaki"},
  {text:"Bottoms in the investment world don't end with four-year lows; they end with ten- or fifteen-year lows.", author:"Jim Rogers"},
  {text:"The secret to investing is to figure out the value of something and then pay a lot less.", author:"Joel Greenblatt"},
  {text:"The stock market is filled with individuals who know the price of everything, but the value of nothing.", author:"Philip Fisher"},
  {text:"If you have trouble imagining a 20% loss in the stock market, you shouldn't be in stocks.", author:"John Bogle"},
  {text:"The key to making money in stocks is not to get scared out of them.", author:"Peter Lynch"},
  {text:"The intelligent investor is a realist who sells to optimists and buys from pessimists.", author:"Benjamin Graham"},
  {text:"In investing, what is comfortable is rarely profitable.", author:"Robert Arnott"},
  {text:"Successful investing is about managing risk, not avoiding it.", author:"Benjamin Graham"},
  {text:"I will tell you how to become rich. Be fearful when others are greedy. Be greedy when others are fearful.", author:"Warren Buffett"},
  {text:"The way to get started is to quit talking and begin doing.", author:"Walt Disney"},
]"""

QUOTES_JS_PSYCHOLOGY = """[
  {text:"The cave you fear to enter holds the treasure you seek.", author:"Joseph Campbell"},
  {text:"Until you make the unconscious conscious, it will direct your life and you will call it fate.", author:"Carl Jung"},
  {text:"Between stimulus and response there is a space. In that space is our power to choose our response.", author:"Viktor Frankl"},
  {text:"The curious paradox is that when I accept myself just as I am, then I can change.", author:"Carl Rogers"},
  {text:"What we resist persists.", author:"Carl Jung"},
  {text:"The first step toward change is awareness. The second step is acceptance.", author:"Nathaniel Branden"},
  {text:"Comparison is the thief of joy.", author:"Theodore Roosevelt"},
  {text:"The greatest discovery of any generation is that a human being can alter their life by altering their attitudes.", author:"William James"},
  {text:"Inaction breeds doubt and fear. Action breeds confidence and courage.", author:"Dale Carnegie"},
  {text:"Your task is not to seek for love, but merely to seek and find all the barriers within yourself that you have built against it.", author:"Rumi"},
  {text:"The measure of intelligence is the ability to change.", author:"Albert Einstein"},
  {text:"We cannot solve our problems with the same thinking we used when we created them.", author:"Albert Einstein"},
  {text:"The mind is everything. What you think you become.", author:"Buddha"},
  {text:"Knowing yourself is the beginning of all wisdom.", author:"Aristotle"},
  {text:"You cannot swim for new horizons until you have courage to lose sight of the shore.", author:"William Faulkner"},
  {text:"It is not death that a man should fear, but he should fear never beginning to live.", author:"Marcus Aurelius"},
  {text:"Absorb what is useful, discard what is not, add what is uniquely your own.", author:"Bruce Lee"},
  {text:"The only journey is the one within.", author:"Rainer Maria Rilke"},
  {text:"He who knows others is wise; he who knows himself is enlightened.", author:"Lao Tzu"},
  {text:"You are not a drop in the ocean. You are the entire ocean in a drop.", author:"Rumi"},
  {text:"Everything can be taken from a man but one thing: the last of the human freedoms — to choose one's attitude.", author:"Viktor Frankl"},
  {text:"The snake which cannot cast its skin has to die.", author:"Friedrich Nietzsche"},
  {text:"The impediment to action advances action. What stands in the way becomes the way.", author:"Marcus Aurelius"},
  {text:"We suffer more in imagination than in reality.", author:"Seneca"},
  {text:"Man is not worried by real problems so much as by his imagined anxieties about real problems.", author:"Epictetus"},
  {text:"The intuitive mind is a sacred gift and the rational mind is a faithful servant.", author:"Albert Einstein"},
  {text:"Hardships often prepare ordinary people for an extraordinary destiny.", author:"C.S. Lewis"},
  {text:"If you change the way you look at things, the things you look at change.", author:"Wayne Dyer"},
  {text:"You don't have to control your thoughts. You just have to stop letting them control you.", author:"Dan Millman"},
  {text:"Resilience is not about bouncing back — it's about bouncing forward.", author:"Sheryl Sandberg"},
  {text:"Act the way you'd like to be and soon you'll be the way you act.", author:"George W. Crane"},
  {text:"Not all those who wander are lost.", author:"J.R.R. Tolkien"},
]"""

MOVIES_JS = """[
  {title:"The Big Short", meta:"Netflix · Ryan Gosling, Christian Bale", summary:"Wall Street insiders bet against the US mortgage market before the 2008 crash. Dark, funny, and uncomfortably accurate."},
  {title:"Margin Call", meta:"Prime · Kevin Spacey, Jeremy Irons", summary:"24 hours inside a bank on the eve of financial collapse. Cold, precise, and brilliantly acted."},
  {title:"Blow", meta:"Prime · Johnny Depp", summary:"Rise and fall of George Jung, the cocaine kingpin. A masterclass in compounding wins and catastrophic risk."},
  {title:"Whiplash", meta:"Netflix · Miles Teller, J.K. Simmons", summary:"A young drummer's obsessive pursuit of greatness under a brutal instructor. The price of mastery laid bare."},
  {title:"The Founder", meta:"Prime · Michael Keaton", summary:"Ray Kroc takes McDonald's from a burger stand to global empire. Raw ambition, ruthless execution."},
  {title:"Moneyball", meta:"Netflix · Brad Pitt", summary:"Data over dogma — Oakland A's GM rebuilds a team on edge of bankruptcy using pure analytics."},
  {title:"Succession (S1)", meta:"HBO · Brian Cox", summary:"Power, family, and the psychology of ultra-wealth. The most honest portrayal of billionaire dynamics on TV."},
  {title:"Limitless", meta:"Prime · Bradley Cooper", summary:"What happens when you operate at 100% capacity. Brilliant meditation on cognitive edge and its cost."},
  {title:"Wall Street", meta:"Prime · Michael Douglas", summary:"Gordon Gekko's 'Greed is Good' speech still resonates. The original anatomy of market manipulation."},
  {title:"The Rip", meta:"Netflix · Matt Damon, Ben Affleck", summary:"Miami cops discover millions in a stash house — trust frays as outside forces close in."},
  {title:"Inside Job", meta:"Documentary (2010)", summary:"Oscar-winning documentary about the 2008 financial crisis. Required viewing for anyone in markets."},
  {title:"Glengarry Glen Ross", meta:"Prime · Al Pacino, Jack Lemmon", summary:"Sales pressure, desperation, ethics. The most quotable business film ever made."},
  {title:"War Dogs", meta:"Prime · Jonah Hill, Miles Teller", summary:"Two Miami guys land a $300M US arms deal. Audacity meets naivety — a cautionary tale about luck."},
  {title:"The Wolf of Wall Street", meta:"Netflix · Leonardo DiCaprio", summary:"Excess, fraud, and the intoxication of market manipulation. Scorsese at his most electric."},
  {title:"Too Big to Fail", meta:"HBO · William Hurt", summary:"Inside the 2008 financial crisis from the perspective of Treasury Secretary Hank Paulson."},
]"""

MEDITATIONS_JS = """[
  {title:"Meditations", meta:"Marcus Aurelius · morning discipline", excerpt:"Begin the day expecting interference: vanity, ingratitude, haste, noise. None of this is new material. Your work is not to be surprised by human nature, but to meet it without becoming smaller, meaner, or easier to purchase."},
  {title:"Meditations", meta:"Marcus Aurelius · the inner citadel", excerpt:"You can retreat whenever you choose into the court of your own mind. No villa is quieter, no island more private, if the judgment inside is orderly. Return there often, repair the command center, then reenter the day like a man under orders."},
  {title:"Meditations", meta:"Marcus Aurelius · obstacle into material", excerpt:"The obstacle is not an interruption of the path. It is the next piece of stone handed to the sculptor. Turn delay into patience, insult into restraint, uncertainty into attention, and friction into proof that your philosophy has legs."},
  {title:"Meditations", meta:"Marcus Aurelius · death and priority", excerpt:"You could leave life right now. Let that fact edit the schedule. Petty grudges, cheap distractions, and theatrical anxieties look different when mortality enters the room with a red pen and no interest in your excuses."},
  {title:"Letters from a Stoic", meta:"Seneca · time as capital", excerpt:"Guard your time like capital, because it is the one currency no empire can mint again. Men are careful with property and careless with hours, then wonder why their lives feel stolen. Spend the morning as if you had to answer for it at sunset."},
  {title:"Letters from a Stoic", meta:"Seneca · poverty practice", excerpt:"Practice wanting less before life forces the lesson. Eat plainly, walk without status, and discover what remains when luxury stops applauding. A man who can be content with little cannot be easily threatened by fortune."},
  {title:"On the Shortness of Life", meta:"Seneca · wasted attention", excerpt:"Life is long enough for the serious, and brutally short for the scattered. The tragedy is not that time runs out; it is that so much of it is handed to distractions, resentments, and ambitions inherited from people we do not even admire."},
  {title:"On Anger", meta:"Seneca · emotional command", excerpt:"Anger sells itself as strength but usually arrives as temporary madness wearing armor. Delay the first impulse. Cross examine the insult. If your dignity can be seized by a fool, it was never secured in the first place."},
  {title:"Discourses", meta:"Epictetus · control and character", excerpt:"Some things are yours: judgment, intention, action, restraint. Most things are not: reputation, weather, markets, other people's moods. Confusing the two is how a free man volunteers for slavery and calls it realism."},
  {title:"Discourses", meta:"Epictetus · role and duty", excerpt:"Do not ask for a life with no difficult parts; ask to play your assigned role well. Son, friend, founder, investor, citizen, body in training. Each role has duties. Freedom is not escaping them; it is performing them without inner begging."},
  {title:"The Enchiridion", meta:"Epictetus · field manual", excerpt:"Do not demand that events obey your preferences. Train your preferences to obey reality, then act with precision. This is not resignation. It is command of the only kingdom that was ever fully yours."},
  {title:"The Enchiridion", meta:"Epictetus · reputation", excerpt:"If you want progress, accept looking foolish to people who worship appearances. No one becomes free while negotiating with every bystander. Let the crowd keep its applause. Your job is to keep your principles."},
  {title:"A Guide to the Good Life", meta:"William B. Irvine · Stoic joy", excerpt:"A good life is not built by getting everything you want; that is a child's treaty with chaos. It is built by wanting fewer foolish things, rehearsing loss before it arrives, and treating tranquility as a skill rather than a mood."},
  {title:"A Guide to the Good Life", meta:"William B. Irvine · negative visualization", excerpt:"Briefly imagine losing what you take for granted, not to become morbid, but to become awake. The practice turns ordinary coffee, working lungs, a loyal friend, and a quiet morning back into treasures instead of background props."},
  {title:"The Daily Stoic", meta:"Ryan Holiday · daily discipline", excerpt:"Philosophy is not a bookshelf performance. It is what remains when traffic, temptation, insult, hunger, and ambition all make their case. The daily question is simple and merciless: did your principles govern anything today, or merely decorate you?"},
  {title:"The Daily Stoic", meta:"Ryan Holiday · action over theory", excerpt:"The Stoic test is not whether you can quote the emperor, the slave, or the senator. The test is whether you answer the email, lift the weight, tell the truth, refuse the bait, and do the next useful thing without ceremony."},
  {title:"Musonius Rufus", meta:"Musonius Rufus · training the body", excerpt:"The body is not separate from philosophy; it is where philosophy pays rent. Cold, hunger, fatigue, and disciplined training expose whether your mind commands the flesh or merely writes elegant manifestos about doing so."},
  {title:"Cato the Younger", meta:"Cato · integrity under pressure", excerpt:"Principles are cheap until they cost status, money, comfort, or friends. Cato's lesson is severe: decide what cannot be bought before the buyer arrives. Otherwise the negotiation has already begun."},
  {title:"Cleanthes", meta:"Early Stoa · willing alignment", excerpt:"Do not merely get dragged by necessity; learn to walk with it. The wise man still faces storms, markets, illness, delay, and death. His advantage is that he wastes less life arguing with the weather."},
  {title:"Zeno of Citium", meta:"Founder of Stoicism · shipwreck into school", excerpt:"A ruined voyage can become a philosophy if the mind refuses to waste the wreckage. Loss is not automatically wisdom, but it can become raw material when a man asks what this disaster is trying to teach him."},
]"""

TWEET_TEMPLATES_JS = """[
  {project:"Evolution Fund", text:"Value flows to whoever reduces entropy. The market calls it alpha when it works and heresy right before it works. Today’s job: separate signal from expensive theatre."},
  {project:"Novaire Signal", text:"A dashboard should not be a Christmas tree. If a widget does not change a decision, it is just anxiety with CSS."},
  {project:"MOTR", text:"Modern masculinity does not need another slogan. It needs sleep, strength, courage, honest conversation, and fewer linen-pants gurus selling fog."},
  {project:"BOTR", text:"Most businesses do not need 'AI transformation.' They need one bot that replies faster than their hungover receptionist and never forgets the follow-up."},
  {project:"Energy Maxxing", text:"Productivity advice after bad sleep is civilization pretending the battery icon is decorative. Recover first, conquer second."},
  {project:"Retreat", text:"The best retreat is not an escape from real life. It is a pressure chamber where weak habits confess and stronger standards walk out with a passport stamp."},
  {project:"Podcast", text:"The current thing is rarely the point. The point is what it reveals about incentives, status, fear, courage, and the tiny monarchies people run inside their heads."}
]"""

BOOKS_JS = """[
  {title:"Poor Charlie's Almanack", meta:"Charlie Munger · Self-Improvement/Investing", summary:"Mental models from Berkshire's vice-chairman. The most practical philosophy book disguised as a business text."},
  {title:"The Psychology of Money", meta:"Morgan Housel · 2020 · Finance/Psychology", summary:"Timeless lessons on wealth, greed, and happiness. Behaviour — not intelligence — determines financial outcomes."},
  {title:"Thinking, Fast and Slow", meta:"Daniel Kahneman · 2011 · Psychology", summary:"The two-system model of human cognition. Essential reading for understanding your own biases in markets."},
  {title:"The Intelligent Investor", meta:"Benjamin Graham · 1949 · Investing", summary:"The definitive guide to value investing. Buffett calls it 'the best book about investing ever written.'"},
  {title:"Antifragile", meta:"Nassim Taleb · 2012 · Philosophy/Risk", summary:"Some things benefit from disorder. How to build systems — and portfolios — that get stronger under stress."},
  {title:"Zero to One", meta:"Peter Thiel · 2014 · Business/Technology", summary:"Notes on startups and how to build the future. The most contrarian business book of the decade."},
  {title:"The Black Swan", meta:"Nassim Taleb · 2007 · Philosophy/Risk", summary:"Why rare, unpredictable events drive history and markets. The book that should have predicted 2008."},
  {title:"Principles", meta:"Ray Dalio · 2017 · Leadership/Investing", summary:"Dalio's life and work philosophy from the Bridgewater founder. Radical transparency at scale."},
  {title:"Atomic Habits", meta:"James Clear · 2018 · Psychology/Productivity", summary:"Tiny changes, remarkable results. The definitive guide to habit formation and compound behavior."},
  {title:"The Art of Thinking Clearly", meta:"Rolf Dobelli · 2013 · Psychology", summary:"99 cognitive biases and thinking errors. A field guide to cleaner, more rational decision-making."},
  {title:"Shoe Dog", meta:"Phil Knight · 2016 · Memoir/Business", summary:"Nike's founder on building the brand from zero. Raw, honest, and deeply motivating."},
  {title:"Man's Search for Meaning", meta:"Viktor Frankl · 1946 · Philosophy/Psychology", summary:"Survival in Nazi camps and the discovery that meaning — not pleasure — is the deepest human drive."},
  {title:"The Almanack of Naval Ravikant", meta:"Eric Jorgenson · 2020 · Wealth/Philosophy", summary:"Curated wisdom from Naval on wealth, happiness, and clear thinking. Free online and worth every minute."},
  {title:"Reminiscences of a Stock Operator", meta:"Edwin Lefèvre · 1923 · Trading/Biography", summary:"The fictionalized life of Jesse Livermore. Timeless market psychology from 100 years ago."},
  {title:"Sapiens", meta:"Yuval Noah Harari · 2011 · History/Philosophy", summary:"A brief history of humankind. Context-setting for understanding civilizational trends and long-horizon investing."},
  {title:"The Hard Thing About Hard Things", meta:"Ben Horowitz · 2014 · Business/Leadership", summary:"Raw advice for running a startup from the Andreessen Horowitz co-founder. No sugarcoating."},
]"""

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def day_of_year():
    return datetime.now(timezone.utc).timetuple().tm_yday

def show_biweekly_monday_section():
    """Show low-frequency strategic sections only every two weeks on Monday, Bangkok time."""
    bkk = datetime.now(timezone(timedelta(hours=7)))
    return bkk.weekday() == 0 and (bkk.isocalendar().week % 2 == 0)


def open_early_week(value=None):
    """Keep weekly research expanded on Monday and Tuesday in Bangkok."""
    current = value or datetime.now(timezone.utc).astimezone(BKK_TZ)
    return current.weekday() in (0, 1)

def pick(lst, offset=0):
    return lst[(day_of_year() + offset) % len(lst)]

def fmt_price(p, decimals=None):
    if p is None: return "—"
    if decimals is not None:
        return f"${p:,.{decimals}f}"
    if p >= 1000: return f"${p:,.0f}"
    if p >= 10:   return f"${p:,.2f}"
    if p >= 0.01: return f"${p:.4f}"
    return f"${p:.6f}"

def fmt_pct(p):
    if p is None: return '<span style="color:var(--dim)">—</span>'
    cls = "positive" if p >= 0 else "negative"
    sign = "+" if p >= 0 else ""
    return f'<span class="{cls}">{sign}{p:.2f}%</span>'

def build_suggested_tweet(gs_meta=None, fed_signal=None, zh_news=None):
    """Create one non-cringe X draft: specific, copyable, and thesis-led."""
    drafts = [
        {"project": "Relationships", "text": "A relationship usually does not die when people disagree. It dies when both people learn which truths are too expensive to say."},
        {"project": "Relationships", "text": "The real green flag is not chemistry. It is repair speed: how quickly two people can tell the truth, lower the weapons, and return to the same side."},
        {"project": "Trickster", "text": "The trickster matters because polite society lies with a straight face. The joke gets through the locked door first."},
        {"project": "Trickster", "text": "Every serious man needs a little trickster in him. Not to become unserious — to stop confusing solemnity with truth."},
        {"project": "Podcast", "text": "A strong podcast question: what are smart people pretending not to know because the answer would make their current identity expensive?"},
        {"project": "Podcast", "text": "The best clips do not explain the news. They extract the pattern: incentives, status, fear, desire, courage. The headline is bait; the human machinery is the meal."},
        {"project": "MOTR", "text": "Most men ask for confidence when what they need is evidence. Keep one promise to yourself before noon and watch the personality improve."},
        {"project": "Novaire Signal", "text": "The point of a dashboard is not to display your life. It is to remove the next excuse."},
        {"project": "Evolution Fund", "text": "Energy is not a sector. It is the cost of every possible future."},
        {"project": "Energy Maxxing", "text": "If sleep is broken, productivity advice becomes cosplay. Fix the battery before negotiating with ambition."},
    ]
    item = drafts[day_of_year() % len(drafts)].copy()
    hook_source = "House thesis · relationships/trickster/podcast"
    feed_path = os.path.join(os.path.dirname(__file__), "feed.json")
    try:
        with open(feed_path, "r", encoding="utf-8") as f:
            feed = json.load(f)
        posts = feed.get("posts") or feed.get("items") or []
        if posts:
            post = posts[day_of_year() % min(len(posts), 5)]
            handle = post.get("handle") or post.get("author") or "X"
            hook_source = f"Possible angle from @{handle} · rewritten as house thesis"
    except Exception:
        pass
    if item["project"] == "Evolution Fund" and gs_meta and gs_meta.get("roi_pct_str"):
        item["text"] += f" Portfolio ROI: {gs_meta['roi_pct_str']}."
    if item["project"] == "Novaire Signal" and fed_signal and fed_signal.get("days_until") is not None:
        item["text"] += f" FOMC in {fed_signal['days_until']} days; decision quality > cortisol."
    full = item["text"].strip()
    if len(full) > 280:
        full = full[:277].rstrip(" ,.;:-") + "…"
    return {"project": item["project"], "text": full, "hook_source": hook_source, "chars": len(full)}

def get_zodiac():
    now = datetime.now(timezone.utc)
    m, d = now.month, now.day
    for z in ZODIAC_SIGNS:
        cm, cd = z["cutoff"]
        if (m == cm and d <= cd) or (m < cm):
            return z
    return ZODIAC_SIGNS[0]  # Capricorn wrap-around

def is_fresh_news(pub_str, market_days=2):
    """Returns True if pub_str is within the last N market days from now."""
    if not pub_str:
        return False
    now = datetime.now(timezone.utc)
    try:
        pub = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
    except Exception:
        # Try common formats
        for fmt in ["%b %d, %Y", "%b %d", "%Y-%m-%d"]:
            try:
                pub = datetime.strptime(pub_str, fmt)
                pub = pub.replace(tzinfo=timezone.utc, year=pub.year if pub.year > 2000 else now.year)
                break
            except Exception:
                pass
        else:
            return False
    diff = (now - pub).days
    return diff <= (market_days + 1)  # +1 buffer for weekends

# ─────────────────────────────────────────────────────────────
# DATA FETCHERS
# ─────────────────────────────────────────────────────────────

def fetch_weather():
    results = []
    session = requests.Session()
    headers = {"User-Agent": "NovaireSignal/1.0 (+https://novairesignal.com)"}
    cache_path = os.path.join(os.path.dirname(__file__), "weather_cache.json")
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            weather_cache = json.load(f)
    except Exception:
        weather_cache = {}

    def _get_json(url, timeout=12, attempts=3):
        last_err = None
        for attempt in range(attempts):
            try:
                r = session.get(url, headers=headers, timeout=timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_err = e
                if attempt < attempts - 1:
                    time.sleep(0.5 * (attempt + 1))
        raise last_err

    for city in CITIES:
        try:
            url = (f"https://api.open-meteo.com/v1/forecast"
                   f"?latitude={city['lat']}&longitude={city['lon']}"
                   f"&current=temperature_2m,weathercode,weather_code,relative_humidity_2m&timezone=auto")
            data = _get_json(url)
            cur = data.get("current", {})
            temp = cur.get("temperature_2m")
            humidity = cur.get("relative_humidity_2m")
            code = cur.get("weathercode", cur.get("weather_code", 0))
            if temp is None:
                raise ValueError(f"missing temperature for {city['name']}: {data}")
            condition = WEATHER_CODES.get(code, "Unknown")
            # Fetch air quality (AQI) from Open-Meteo
            aqi = None
            aqi_label = "—"
            try:
                aqi_url = (f"https://air-quality-api.open-meteo.com/v1/air-quality"
                           f"?latitude={city['lat']}&longitude={city['lon']}"
                           f"&current=us_aqi")
                aq_data = _get_json(aqi_url, timeout=12, attempts=2)
                aqi = aq_data.get("current", {}).get("us_aqi")
                if aqi is not None:
                    if aqi <= 50: aqi_label = "Good"
                    elif aqi <= 100: aqi_label = "Moderate"
                    elif aqi <= 150: aqi_label = "Unhealthy (SG)"
                    elif aqi <= 200: aqi_label = "Unhealthy"
                    elif aqi <= 300: aqi_label = "Very Unhealthy"
                    else: aqi_label = "Hazardous"
            except Exception as e:
                print(f"    ⚠️  AQI unavailable for {city['name']}: {e}")
            result = {**city, "temp": temp, "humidity": humidity, "condition": condition, "aqi": aqi, "aqi_label": aqi_label, "ok": True}
            results.append(result)
            weather_cache[city["name"]] = {**result, "cached_at": datetime.now(timezone.utc).isoformat()}
        except Exception as e:
            print(f"    ⚠️  Weather unavailable for {city['name']}: {e}")
            cached = weather_cache.get(city["name"])
            if cached:
                try:
                    cached_at = datetime.fromisoformat(cached.get("cached_at", "").replace("Z", "+00:00"))
                    cache_age = datetime.now(timezone.utc) - cached_at
                except Exception:
                    cache_age = timedelta.max
                if cache_age <= timedelta(hours=12) and cached.get("temp") is not None:
                    print(f"    ↳ using cached {city['name']} weather from {cached.get('cached_at')}")
                    results.append({**city, "temp": cached.get("temp"), "humidity": cached.get("humidity"), "condition": cached.get("condition", "—"), "aqi": cached.get("aqi"), "aqi_label": cached.get("aqi_label", "—"), "ok": True, "cached": True})
                    continue
            results.append({**city, "temp": None, "humidity": None, "condition": "—", "aqi": None, "aqi_label": "—", "ok": False})
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(weather_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"    ⚠️  Weather cache write failed: {e}")
    return results

def fetch_bangkok_post():
    """Return expat-relevant Thailand headlines, not random local filler."""
    headlines = []
    seen = set()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    relevant_terms = [
        "visa", "immigration", "expat", "foreigner", "foreign", "tourist", "bangkok",
        "phuket", "pattaya", "chiang mai", "arrest", "scam", "police", "crime",
        "crackdown", "overstay", "tax", "condo", "rent", "baht", "airport", "safety",
        "nightlife", "cannabis", "alcohol", "digital wallet", "health insurance"
    ]
    reject_terms = [
        "lottery", "football", "volleyball", "monk", "temple fair", "rice", "durian",
        "school sports", "village chief"
    ]
    sources = [
        ("The Thaiger", "https://thethaiger.com/feed"),
        ("Thai Examiner", "https://www.thaiexaminer.com/feed/"),
        ("Bangkok Post", "https://www.bangkokpost.com/rss/data/thailand.xml"),
        ("Bangkok Post", "https://www.bangkokpost.com/rss/data/topstories.xml"),
    ]

    def score(title, summary=""):
        text = (title + " " + summary).lower()
        points = sum(3 for term in relevant_terms if term in text)
        points -= sum(4 for term in reject_terms if term in text)
        if any(term in text for term in ["visa", "immigration", "overstay", "foreigner", "expat"]):
            points += 8
        if any(term in text for term in ["arrest", "scam", "police", "crime", "crackdown"]):
            points += 5
        if any(term in text for term in ["bangkok", "phuket", "pattaya", "chiang mai"]):
            points += 2
        return points

    def add_item(title, url, source, summary=""):
        title = " ".join((title or "").split())
        if len(title) < 28:
            return
        key = title.lower()
        if key in seen:
            return
        seen.add(key)
        headlines.append({
            "title": title,
            "url": url or "#",
            "source": source,
            "summary": " ".join((summary or "").split())[:180],
            "score": score(title, summary),
        })

    for source, url in sources:
        try:
            r = requests.get(url, headers=headers, timeout=12)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all("item") or soup.find_all("entry")
            for item in items[:20]:
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description") or item.find("summary")
                guid_el = item.find("guid")
                title = title_el.get_text(" ", strip=True) if title_el else ""
                href = ""
                if link_el:
                    href = link_el.get("href") or link_el.get_text(" ", strip=True)
                    # Bangkok Post RSS currently emits a self-closing <link/> tag
                    # followed by the URL as a text sibling, which BeautifulSoup's
                    # HTML parser leaves outside link_el.get_text(). Preserve the
                    # live source URL instead of degrading to '#'.
                    if not href and getattr(link_el, "next_sibling", None):
                        sibling = str(link_el.next_sibling).strip()
                        if sibling.startswith("http"):
                            href = sibling
                if (not href or href == "#") and guid_el:
                    href = guid_el.get_text(" ", strip=True)
                raw_summary = desc_el.get_text(" ", strip=True) if desc_el else ""
                summary = BeautifulSoup(raw_summary, "html.parser").get_text(" ", strip=True)
                add_item(title, href, source, summary)
        except Exception as e:
            print(f"    ⚠️  {source} expat feed unavailable: {e}")

    # Fallback scrape if RSS feeds are thin or blocked.
    if len(headlines) < 3:
        try:
            r = requests.get("https://www.bangkokpost.com/thailand", headers=headers, timeout=12)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                txt = a.get_text(" ", strip=True)
                href = str(a.get("href", ""))
                if href.startswith("/"):
                    href = "https://www.bangkokpost.com" + href
                if "bangkokpost.com" in href or href.startswith("http"):
                    add_item(txt, href, "Bangkok Post")
                if len(headlines) >= 8:
                    break
        except Exception as e:
            print(f"    ⚠️  Bangkok Post fallback unavailable: {e}")

    ranked = sorted(headlines, key=lambda x: x.get("score", 0), reverse=True)
    relevant = [h for h in ranked if h.get("score", 0) > 0]
    if relevant:
        return relevant[:3]
    return ranked[:3] if ranked else [{
        "title": "Thailand expat news feed temporarily unavailable",
        "url": "https://thethaiger.com/",
        "source": "The Thaiger",
        "summary": "Check visa, immigration, safety, and Bangkok lifestyle updates manually.",
        "score": 0,
    }]

def fetch_trending_recs():
    """
    Fetch daily trending recs:
    - Movie/Show: FlixPatrol #1 Netflix movie + OMDB description
    - Book: Amazon Business bestsellers #1 title + Open Library description
    Show an explicit unavailable card on failure rather than substituting a
    stale recommendation.
    """
    rec_movie = {"label": "📺 Trending Now", "title": "Live recommendation unavailable", "meta": "Source fetch failed", "summary": "No stale pick substituted."}
    rec_book  = {"label": "📖 Trending Book", "title": "Live recommendation unavailable", "meta": "Source fetch failed", "summary": "No stale pick substituted."}

    # ── Movie: FlixPatrol trending → OMDB description ──
    try:
        hdrs = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        r = requests.get("https://flixpatrol.com/top10/netflix/world/today/", headers=hdrs, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        tables = soup.find_all("table")
        candidates = []  # (title, platform, table_idx)
        for i, table in enumerate(tables[:2]):
            rows = table.find_all("tr")
            for row in rows[:3]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if cells and len(cells) >= 2:
                    raw = cells[1] if len(cells) > 1 else cells[0]
                    title = raw.strip()
                    if title and len(title) > 2:
                        label = "Netflix Movies" if i == 0 else "Netflix Shows"
                        candidates.append((title, label))
        # Pick #1 movie (table 0)
        if not candidates:
            raise ValueError("FlixPatrol returned no usable titles")
        movie_title, movie_platform = candidates[0]
        # Fetch OMDB description
        omdb = requests.get(f"http://www.omdbapi.com/?t={requests.utils.quote(movie_title)}&apikey=trilogy", timeout=8).json()
        if omdb.get("Response") == "True":
            genre = omdb.get("Genre", "")
            year  = omdb.get("Year", "")
            plot  = omdb.get("Plot", "")[:130]
            rec_movie = {"label": "📺 Trending Now", "title": movie_title,
                         "meta": f"{movie_platform} · {year} · {genre}",
                         "summary": plot}
        else:
            rec_movie = {"label": "📺 Trending Now", "title": movie_title,
                         "meta": movie_platform, "summary": "Trending #1 on Netflix today."}
    except Exception as e:
        print(f"    ⚠️  Movie rec fallback ({e})")

    # ── Book: Amazon Business Bestsellers → Open Library description ──
    try:
        hdrs2 = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", "Accept-Language": "en-US,en;q=0.9"}
        rb = requests.get("https://www.amazon.com/gp/bestsellers/books/2581/", headers=hdrs2, timeout=12)
        soup2 = BeautifulSoup(rb.text, "html.parser")
        book_title = None
        seen_b = set()
        for a in soup2.select("a.a-link-normal"):
            href = a.get("href", "")
            if "/dp/" in href or "/product/" in href:
                t = a.get_text(strip=True)
                if t and len(t) > 8 and t not in seen_b and "$" not in t and "out of 5" not in t:
                    seen_b.add(t)
                    book_title = t
                    break
        if book_title:
            # Open Library search for description
            ol = requests.get(f"https://openlibrary.org/search.json?q={requests.utils.quote(book_title)}&limit=1", timeout=8).json()
            docs = ol.get("docs", [])
            if docs:
                doc = docs[0]
                author = ", ".join(doc.get("author_name", [])[:2]) or "Unknown"
                subject = ", ".join(doc.get("subject", [])[:3]) or ""
                rec_book = {"label": "📖 Trending Book", "title": book_title[:60],
                            "meta": f"{author} · Amazon Business #1",
                            "summary": f"Currently topping Amazon Business charts. Subjects: {subject}." if subject else "Amazon Business Bestseller #1."}
            else:
                rec_book = {"label": "📖 Trending Book", "title": book_title[:60],
                            "meta": "Amazon Business #1", "summary": "Currently topping Amazon Business charts."}
    except Exception as e:
        print(f"    ⚠️  Book rec fallback ({e})")

    return rec_movie, rec_book


def fetch_zerohedge():
    """Fetch ZeroHedge headlines via RSS — timestamp-filtered to last 24h only."""
    import xml.etree.ElementTree as ET
    headlines = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
        r = requests.get("https://feeds.feedburner.com/zerohedge/feed", headers=headers, timeout=12)
        root = ET.fromstring(r.text)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el  = item.find("link")
            pub_el   = item.find("pubDate")
            if title_el is None or link_el is None:
                continue
            title = title_el.text.strip()
            link  = link_el.text.strip() if link_el.text else "#"
            # Parse pubDate and filter
            if pub_el is not None and pub_el.text:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_dt = parsedate_to_datetime(pub_el.text)
                    if pub_dt < cutoff:
                        continue  # skip anything older than 24h
                except Exception:
                    pass
            if len(title) > 20:
                headlines.append({"title": title, "url": link})
            if len(headlines) >= 4:
                break
    except Exception as e:
        headlines = [{"title": f"ZeroHedge unavailable", "url": "#"}]
    return headlines[:4] if headlines else [{"title": "No headlines in last 24h", "url": "#"}]

GSHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{PORTFOLIO_SHEET_ID}/export?format=csv&gid={TFSA_GID}"

# Map sheet exchange/ticker strings → Yahoo Finance tickers
EXCHANGE_TO_TICKER = {
    "CNSX:HG":  "HG.CN",
    "TSE:GLO":  "GLO.TO",
    "FVL":      "FVL.TO",
    "MOLY":     "MOLY.TO",
    "DML":      "DML.TO",
    "BNNLF":    "BNNLF",
    "MAXX":     "MAXX.CN",
    "CVE:TOM":  "TOM.V",
    "ASX:LOT":  "LOT.AX",
    "CVE:NAM":  "NAM.V",
    "CVE:PNPN": "PNPN.V",
    "CVE:SVE":  "SVE.V",
    "CVE:PEGA": "PEGA.V",
    "CVE:CAPT": "CAPT.V",
    "CVE:MANU": "MANU.V",
    "TSE:VZLA": "VZLA.TO",
    "ASX:AEU":  "AEU.AX",
    "CVE:AAG":  "AAG.V",
    "BQSSF":    "BQSSF",
    "CVE:EU":   "EU.V",
    "TSE:YGR":  "YGR.TO",
}

DISPLAY_OVERRIDES = {
    "_FVL_FALLBACK":  "FVL",
    "_MOLY_FALLBACK": "MOLY",
    "_MAXX_FALLBACK": "MAXX",
}


def fetch_holdings_from_gsheet():
    """Fetch portfolio holdings directly from Google Sheet CSV.
    Returns (holdings_list, meta_dict) or (None, {}) on failure.
    """
    import csv, io
    try:
        cache_bust = int(datetime.now(timezone.utc).timestamp())
        sep = "&" if "?" in GSHEET_CSV_URL else "?"
        gsheet_url = f"{GSHEET_CSV_URL}{sep}_t={cache_bust}"
        r = requests.get(
            gsheet_url,
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            timeout=20,
        )
        r.raise_for_status()
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
    except Exception as e:
        print(f"    ⚠️  Google Sheet fetch failed: {e}")
        return None, {}

    def parse_price(s):
        if not s: return None
        try: return float(s.replace("$", "").replace(",", "").strip())
        except: return None

    def parse_shares(s):
        if not s: return None
        try: return float(s.replace(",", "").strip())
        except: return None

    def parse_percent(s):
        if not s: return None
        try: return float(s.replace("%", "").replace(",", "").strip())
        except: return None

    holdings = []
    meta     = {}
    seen     = set()
    allocation_totals = {}

    for row in rows:
        while len(row) < 16:
            row.append("")
        currency = row[1].strip()

        # Portfolio meta: TOTAL row (has "TOTAL" in col 11)
        if row[11].strip() == "TOTAL":
            meta["total_cad"] = parse_price(row[10])
            meta["roi_pct_str"] = row[12].strip()
            meta["roi_abs"] = parse_price(row[13])
        # USD total row (row after TOTAL, col 9 = "USD")
        if row[9].strip() == "USD" and not meta.get("total_usd"):
            v = parse_price(row[10])
            if v and v > 10000:
                meta["total_usd"] = v
        # ATH row
        if row[9].strip() == "ATH":
            meta["ath"] = parse_price(row[10])

        # Data rows: currency must be CAD, USD, or AUD
        if currency not in ("CAD", "USD", "AUD"):
            continue

        note        = row[0].strip()
        name        = row[2].strip()
        ex_ticker   = row[3].strip()
        price_str   = row[5].strip()
        buy_str     = row[8].strip()
        shares_str  = row[9].strip()
        allocation_pct = parse_percent(row[12])
        sector      = row[15].strip() if len(row) > 15 else "Other"

        ticker = EXCHANGE_TO_TICKER.get(ex_ticker, ex_ticker)
        if not ticker or not shares_str or ticker in seen:
            continue
        seen.add(ticker)

        shares    = parse_shares(shares_str)
        cur_price = parse_price(price_str)
        buy_price = parse_price(buy_str)

        if not shares:
            continue

        # The Google Sheet's allocation chart covers the primary book only.
        # Covered-call rows are a separate strategy block and are intentionally
        # excluded from the sheet chart even though they remain in holdings.
        if note.casefold() != "ccalls" and allocation_pct and sector:
            allocation_totals[sector] = allocation_totals.get(sector, 0.0) + allocation_pct

        display = DISPLAY_OVERRIDES.get(ticker, ticker.split(".")[0])

        h = {
            "ticker":   ticker,
            "display":  display,
            "name":     name,
            "shares":   shares,
            "currency": currency,
            "sector":   sector or "Other",
        }
        # For off-Yahoo tickers, use sheet's current price as fallback
        if ticker.startswith("_") and cur_price:
            h["fallback_price"] = cur_price
        holdings.append(h)

    if allocation_totals:
        allocations = sorted(
            ((sector, round(percent, 2)) for sector, percent in allocation_totals.items()),
            key=lambda item: item[1],
            reverse=True,
        )
        allocation_total = round(sum(percent for _, percent in allocations), 2)
        if 99.5 <= allocation_total <= 100.5:
            meta["sector_allocations_pct"] = allocations
            meta["sector_allocation_total_pct"] = allocation_total
            meta["allocation_source"] = "Google Sheet · % of Fund"
        else:
            print(f"    ⚠️  Sheet allocation total is {allocation_total:.2f}%; chart withheld")

    return holdings, meta


def fetch_official_cse_hg_quote():
    """Return HydroGraph's official CSE closing auction price.

    Yahoo can stop at the 15:59 continuous-session trade and omit the CSE
    16:10 market-on-close print. The exchange's own consolidated ticker is
    authoritative for the official daily close.
    """
    import json
    import re
    try:
        url = "https://thecse.com/listings/hydrograph-clean-power-inc/"
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"},
            timeout=20,
        )
        response.raise_for_status()
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            response.text,
            re.DOTALL,
        )
        if not match:
            return None
        data = json.loads(match.group(1))
        company = data["props"]["pageProps"]["staticCompanyData"]
        ticker = company.get("consolidated", {}).get("ticker") or company.get("ticker", {})
        price = float(ticker["Last Price"])
        previous = float(ticker["Previous Closing Price"])
        if not (0 < price < 1000 and 0 < previous < 1000):
            return None
        return {
            "price": price,
            "change": (price - previous) / previous * 100,
            "volume": ticker.get("Trading Volume"),
            "time": ticker.get("Time"),
            "source": "Canadian Securities Exchange",
        }
    except Exception as exc:
        print(f"    ⚠️  Official CSE HG quote unavailable: {exc}")
        return None


def fetch_portfolio(usdcad=1.365, audusd=0.63):
    """Fetch Sheet holdings/totals first, then enrich prices with yfinance when available."""
    def to_usd(amount, currency):
        if currency == "CAD": return amount / usdcad
        if currency == "AUD": return amount * audusd
        return amount  # USD

    # Load holdings from Google Sheet; fall back to hardcoded list
    gs_holdings, gs_meta = fetch_holdings_from_gsheet()
    if gs_holdings:
        holdings_source = gs_holdings
        # Update module-level SECTORS from sheet data
        for h in gs_holdings:
            SECTORS[h["ticker"]] = h.get("sector") or "Other"
        # Build fallback prices from sheet data
        sheet_fallbacks = {
            h["ticker"]: h["fallback_price"]
            for h in gs_holdings if h.get("fallback_price")
        }
    else:
        holdings_source = HOLDINGS
        sheet_fallbacks = {}
        gs_meta = gs_meta or {}

    try:
        import yfinance as yf
    except ImportError:
        return {}, holdings_source, gs_meta

    results = {}
    official_hg = fetch_official_cse_hg_quote()
    for h in holdings_source:
        ticker   = h["ticker"]
        shares   = h["shares"]
        currency = h.get("currency", "CAD")

        # HydroGraph is MOC-eligible on the CSE. Use the exchange's 16:10
        # closing-auction print rather than Yahoo's 15:59 continuous-session
        # trade, which can differ materially on volatile days.
        if ticker == "HG.CN" and official_hg:
            p = official_hg["price"]
            value_usd = to_usd(p * shares, currency)
            results[ticker] = {
                "price": p,
                "change": official_hg["change"],
                "value": value_usd,
                "currency": currency,
                "fallback": False,
                "source": official_hg["source"],
            }
            continue

        # Off-Yahoo tickers: use sheet's live price
        if ticker.startswith("_"):
            p = sheet_fallbacks.get(ticker) or FALLBACK_PRICES.get(ticker)
            if p:
                value_usd = to_usd(p * shares, currency)
                results[ticker] = {"price": p, "change": None, "value": value_usd, "currency": currency, "fallback": True}
                continue

        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", auto_adjust=True)
            hist = hist[hist["Close"].notna()]
            if len(hist) >= 2:
                p   = float(hist["Close"].iloc[-1])
                pp  = float(hist["Close"].iloc[-2])
                chg = (p - pp) / pp * 100
            elif len(hist) == 1:
                p   = float(hist["Close"].iloc[-1])
                chg = None
            else:
                # Try fast_info, then fall back to t.info for OTC/delayed tickers (e.g. BNNLF)
                p = None; chg = None
                try:
                    fi = t.fast_info
                    p = getattr(fi, "last_price", None)
                except Exception:
                    pass
                if not p:
                    try:
                        info = t.info
                        p = info.get("regularMarketPrice") or info.get("currentPrice")
                    except Exception:
                        pass

            if p and p > 0:
                value_usd = to_usd(p * shares, currency)
                results[ticker] = {"price": p, "change": chg, "value": value_usd, "currency": currency, "fallback": False}
            else:
                results[ticker] = {"price": None, "change": None, "value": None, "currency": currency, "fallback": False}
        except Exception:
            results[ticker] = {"price": None, "change": None, "value": None, "currency": currency, "fallback": False}
    return results, holdings_source, gs_meta

def fetch_catalysts(tickers):
    """Fetch recent verified news for every requested top holding.

    Yahoo often returns no news for Canadian small caps, so each symbol also
    gets an exact-company Google News RSS scan. A 14-day window retains useful
    conference and project catalysts without filling the card with old fluff.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {}

    cats = {}
    now = datetime.now(timezone.utc)
    fresh_cutoff = now - timedelta(days=14)
    fallback_news_map = {}
    news_queries = {
        "HG.CN": "HydroGraph Clean Power",
        "_FVL_FALLBACK": "Freegold Limited Golden Summit",
        "FVL.TO": "Freegold Limited Golden Summit",
        "GLO.TO": "Global Atomic Dasa",
        "URNJ": "Sprott Junior Uranium Miners ETF",
        "BNNLF": "Bannerman Energy Etango",
        "VZLA.TO": "Vizsla Silver Panuco",
    }
    relevance_terms = {
        "HG.CN": ("hydrograph",),
        "_FVL_FALLBACK": ("freegold", "golden summit"),
        "FVL.TO": ("freegold", "golden summit"),
        "GLO.TO": ("global atomic", "dasa"),
        "URNJ": ("urnj", "sprott junior uranium"),
        "BNNLF": ("bannerman", "etango"),
        "VZLA.TO": ("vizsla silver", "panuco"),
    }

    for ticker in tickers:
        lookup_ticker = fallback_news_map.get(ticker, ticker)
        candidates = []
        if not lookup_ticker.startswith("_"):
            try:
                for item in (yf.Ticker(lookup_ticker).news or []):
                    title = item.get("content", {}).get("title") or item.get("title", "")
                    pub_raw = item.get("content", {}).get("pubDate") or item.get("providerPublishTime", "")
                    pub_dt = None
                    try:
                        pub_dt = (datetime.fromtimestamp(pub_raw, tz=timezone.utc) if isinstance(pub_raw, (int, float))
                                  else datetime.fromisoformat(str(pub_raw).replace("Z", "+00:00")))
                    except Exception:
                        pass
                    source = (item.get("content", {}).get("provider", {}).get("displayName")
                              or item.get("publisher", ""))
                    if title and pub_dt:
                        candidates.append({"title": title, "pub_dt": pub_dt, "source": source})
            except Exception:
                pass

        query = news_queries.get(ticker)
        if query:
            try:
                from urllib.parse import quote_plus
                from email.utils import parsedate_to_datetime
                import xml.etree.ElementTree as ET
                url = ("https://news.google.com/rss/search?q=" + quote_plus(f'"{query}" when:14d')
                       + "&hl=en-US&gl=US&ceid=US:en")
                response = requests.get(url, headers={"User-Agent": "NovaireSignal/1.0"}, timeout=10)
                response.raise_for_status()
                for item in ET.fromstring(response.content).findall("./channel/item"):
                    title = (item.findtext("title") or "").strip()
                    pub_raw = item.findtext("pubDate") or ""
                    if not title or not pub_raw:
                        continue
                    pub_dt = parsedate_to_datetime(pub_raw).astimezone(timezone.utc)
                    source_node = item.find("source")
                    source = ((source_node.text or "Google News").strip()
                              if source_node is not None else "Google News")
                    candidates.append({"title": title, "pub_dt": pub_dt, "source": source})
            except Exception:
                pass

        terms = relevance_terms.get(ticker, ())
        candidates = [c for c in candidates
                      if fresh_cutoff <= c["pub_dt"] <= now + timedelta(hours=2)
                      and (not terms or any(term in c["title"].lower() for term in terms))]
        if candidates:
            best = max(candidates, key=lambda c: c["pub_dt"])
            cats[ticker] = {"title": best["title"], "date": best["pub_dt"].strftime("%b %-d"),
                            "source": best["source"], "fresh": True}
        else:
            cats[ticker] = None
    return cats

def parse_yahoo_chart_quote(payload, *, period="futures session"):
    """Parse the latest two valid adjacent Yahoo chart bars."""
    try:
        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0].get("close") or []
        valid = [
            (int(ts), float(close))
            for ts, close in zip(timestamps, closes)
            if close is not None and float(close) > 0
        ]
        if len(valid) < 2:
            return None
        previous = valid[-2][1]
        price = valid[-1][1]
        quote_ts = int(result.get("meta", {}).get("regularMarketTime") or valid[-1][0])
        return {
            "price": price,
            "previous": previous,
            "change": (price - previous) / previous * 100,
            "source": "Yahoo Finance",
            "period": period,
            "quote_time": datetime.fromtimestamp(quote_ts, timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return None


def fetch_market_futures():
    """Fetch the three major US index futures from adjacent valid bars."""
    results = {}
    for symbol, meta in MARKET_FUTURES.items():
        try:
            response = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}",
                params={"range": "5d", "interval": "1d"},
                headers={"User-Agent": "NovaireSignal/1.0"},
                timeout=10,
            )
            parsed = parse_yahoo_chart_quote(response.json())
        except Exception:
            parsed = None
        results[symbol] = {**meta, **(parsed or {
            "price": None, "previous": None, "change": None,
            "source": "Yahoo Finance", "period": "futures session", "quote_time": None,
        })}
    return results


def fetch_market_indices():
    """Fetch the S&P 500, Nasdaq Composite, and Dow cash indexes."""
    results = {}
    for symbol, meta in MARKET_INDICES.items():
        try:
            response = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}",
                params={"range": "5d", "interval": "1d"},
                headers={"User-Agent": "NovaireSignal/1.0"},
                timeout=10,
            )
            parsed = parse_yahoo_chart_quote(response.json(), period="cash session")
        except Exception:
            parsed = None
        results[symbol] = {**meta, **(parsed or {
            "price": None, "previous": None, "change": None,
            "source": "Yahoo Finance", "period": "cash session", "quote_time": None,
        })}
    return results


def fetch_commodities():
    """Fetch six Investing.com futures plus the preserved uranium spot benchmark.

    These are intentionally not mixed with Yahoo contracts: Novaire uses the
    Investing.com commodities screen as the visual reference, so source,
    contract and daily-change basis must travel together.
    """
    symbols = {
        "GOLD": {"name": "Gold",        "unit": "/oz",  "cls": "c-gold"},
        "SILVER": {"name": "Silver",      "unit": "/oz",  "cls": "c-silver"},
        "COPPER": {"name": "Copper",      "unit": "/lb",  "cls": "c-copper"},
        "WTI": {"name": "Crude Oil WTI", "unit": "/bbl", "cls": "c-oil"},
        "BRENT": {"name": "Brent Oil",    "unit": "/bbl", "cls": "c-oil"},
        "NATGAS": {"name": "Natural Gas", "unit": "/MMBtu", "cls": "c-gas"},
        "URANIUM_SPOT": {"name": "Uranium", "unit": "/lb", "cls": "c-uranium"},
    }
    results = {key: {**meta, "price": None, "change": None,
                     "source": "Investing.com", "period": "daily",
                     "quote_time": None} for key, meta in symbols.items()}
    try:
        firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
        if not firecrawl_key:
            raise RuntimeError("FIRECRAWL_API_KEY unavailable")
        r = requests.post("https://api.firecrawl.dev/v2/scrape",
                          headers={"Authorization": f"Bearer {firecrawl_key}", "Content-Type": "application/json"},
                          json={"url": "https://www.investing.com/commodities/real-time-futures",
                                "formats": ["markdown"], "onlyMainContent": True}, timeout=90)
        r.raise_for_status()
        markdown = r.json().get("data", {}).get("markdown", "")
        slugs = {"GOLD": "gold", "SILVER": "silver", "COPPER": "copper",
                 "WTI": "crude-oil", "BRENT": "brent-oil", "NATGAS": "natural-gas"}
        for key, slug in slugs.items():
            marker = f"](https://www.investing.com/commodities/{slug} \""
            row = next((line for line in markdown.splitlines() if marker in line), None)
            if not row:
                continue
            cells = [cell.strip() for cell in row.strip().strip('|').split('|')]
            if len(cells) >= 8:
                results[key]["price"] = float(cells[3].replace(',', ''))
                results[key]["change"] = float(cells[7].rstrip('%').replace('−', '-'))
        results_quote_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for item in results.values():
            if item["price"] is not None:
                item["quote_time"] = results_quote_time
    except Exception:
        pass

    # Uranium is absent from Investing.com's futures screen. Preserve the
    # pre-migration Trading Economics U3O8 benchmark rather than silently
    # shrinking the user's approved commodity set to one provider's list.
    try:
        r = requests.get("https://tradingeconomics.com/commodity/uranium",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        m = re.search(r'Uranium[^".]{0,160}?\bat\s+(\d+(?:\.\d+)?)\s*USD/Lbs',
                      r.text, flags=re.IGNORECASE)
        if m:
            results["URANIUM_SPOT"].update({
                "price": float(m.group(1)), "source": "Trading Economics",
                "period": "spot benchmark",
                "quote_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })
    except Exception:
        pass
    return results

def quote_timestamp_is_fresh(close_time_ms, *, now_ms=None, max_age_seconds=300):
    """Return True only for an exchange quote updated within the allowed age."""
    try:
        close_time_ms = int(close_time_ms)
        now_ms = int(now_ms if now_ms is not None else datetime.now(timezone.utc).timestamp() * 1000)
    except (TypeError, ValueError):
        return False
    age_ms = now_ms - close_time_ms
    return 0 <= age_ms <= max_age_seconds * 1000


def fetch_crypto():
    ids = {"bitcoin":"BTC", "ethereum":"ETH", "solana":"SOL", "cardano":"ADA",
           "the-open-network":"TON", "sui":"SUI", "zcash":"ZEC", "midnight-3":"NIGHT"}
    results = {ticker: {"price": None, "change": None, "market_cap": 0,
                        "source": None, "quote_time": None} for ticker in ids.values()}
    try:
        rows = requests.get("https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency":"usd", "ids":",".join(ids), "price_change_percentage":"24h"},
            headers={"User-Agent":"NovaireSignal/1.0"}, timeout=12).json()
        for row in rows:
            ticker = ids.get(row.get("id"))
            if ticker:
                results[ticker] = {"price": row.get("current_price"),
                    "change": row.get("price_change_percentage_24h"),
                    "market_cap": row.get("market_cap") or 0,
                    "source": "CoinGecko", "quote_time": row.get("last_updated")}
    except Exception:
        pass

    # Binance is the faster live-price layer; CoinGecko remains the market-cap
    # source and the fallback quote. TON trades on Binance under its active
    # GRAM successor pair; the retired TONUSDT endpoint is stale. XRP stays excluded.
    for ticker, pair in CRYPTO_BINANCE_PAIRS.items():
        try:
            d = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair}", timeout=8).json()
            if quote_timestamp_is_fresh(d.get("closeTime")):
                results[ticker]["price"] = float(d["lastPrice"])
                results[ticker]["change"] = float(d["priceChangePercent"])
                results[ticker]["source"] = "Binance"
                results[ticker]["quote_time"] = datetime.fromtimestamp(
                    int(d["closeTime"]) / 1000, timezone.utc
                ).isoformat().replace("+00:00", "Z")
        except Exception:
            pass
    return results

def fetch_polymarket():
    """Fetch Barron147 live positions from Polymarket with % P&L"""
    INCEPTION_COST = 222.00  # total funds deposited into Polymarket — confirmed by Novaire Mar 15
    INCEPTION_TS = 1772496000  # epoch: 2026-03-03 00:00 UTC — ignore all activity before this
    try:
        import urllib.request, json
        PROXY = "0xC1541b2af765e4d1013337084D889d0DB302Aa0e"
        cache_bust = int(datetime.now(timezone.utc).timestamp())
        url = f"https://data-api.polymarket.com/positions?user={PROXY}&_t={cache_bust}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            positions = json.loads(resp.read())

        # Get cash balance. Polymarket trading cash can sit in CLOB collateral
        # rather than plain wallet USDC.e, so check the authenticated CLOB balance
        # first and fall back to on-chain USDC.e on the proxy wallet.
        est_cash = 0
        try:
            import os as _os
            from py_clob_client.client import ClobClient as _ClobClient
            from py_clob_client.clob_types import BalanceAllowanceParams as _BalanceAllowanceParams, AssetType as _AssetType
            _key = _os.getenv("POLYMARKET_PRIVATE_KEY")
            if _key:
                _client = _ClobClient("https://clob.polymarket.com", key=_key, chain_id=137, signature_type=1, funder=PROXY)
                _client.set_api_creds(_client.create_or_derive_api_creds())
                _bal = _client.get_balance_allowance(_BalanceAllowanceParams(asset_type=_AssetType.COLLATERAL))
                est_cash = int(_bal.get("balance", 0)) / 1e6
        except Exception as _e:
            est_cash = 0

        if est_cash <= 0:
            try:
                import requests as _rq
                addr_padded = PROXY[2:].lower().zfill(64)
                call_data = '0x70a08231' + addr_padded
                usdc_e = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
                rpc_r = _rq.post('https://polygon-bor-rpc.publicnode.com',
                    json={'jsonrpc':'2.0','method':'eth_call','params':[{'to':usdc_e,'data':call_data},'latest'],'id':1},
                    timeout=10)
                est_cash = int(rpc_r.json().get('result', '0x0'), 16) / 1e6
            except:
                est_cash = 0

        live = []
        total_position_val = 0
        for p in positions:
            val = float(p.get("currentValue", p.get("value", 0)))
            if val < 0.01:
                continue
            title = p.get("title", "?")
            outcome = p.get("outcome", "?")
            pct_pnl = float(p.get("percentPnl", 0))
            if len(title) > 50:
                title = title[:47] + "..."
            total_position_val += val
            live.append({"title": title, "outcome": outcome, "pct_pnl": pct_pnl, "value": val})

        # Largest weighted position first (by current position value)
        live.sort(key=lambda x: x.get("value", 0), reverse=True)

        # Inception ROI: cash + positions vs starting capital
        total_account = total_position_val + max(est_cash, 0)
        inception_roi = ((total_account / INCEPTION_COST) - 1) * 100 if INCEPTION_COST > 0 else 0

        return {
            "positions": live[:6],
            "total_account": total_account,
            "cash": max(est_cash, 0),
            "inception_roi": inception_roi,
        }
    except Exception as e:
        print(f"  ⚠ Polymarket fetch failed: {e}")
        return {"positions": [], "total_account": 0, "inception_roi": 0}

def fetch_alpaca():
    """Fetch Alpaca positions: Tier 1 = Volume Scalp (executor.py), Tier 2 = Livermore Darvas Microcap"""
    TIER1_INCEPTION = 250.0  # Tier 1 — Alpaca Volume Scalp (automated momentum)
    TIER2_INCEPTION = 250.0  # Tier 2 — Livermore Darvas Microcap (Darvas box breakout)
    TOTAL_INCEPTION = 500.0
    try:
        import urllib.request, json as _json, os as _os
        KEY = _os.getenv("ALPACA_API_KEY") or _os.getenv("APCA_API_KEY_ID")
        SECRET = _os.getenv("ALPACA_SECRET_KEY") or _os.getenv("APCA_API_SECRET_KEY")
        BASE = (_os.getenv("ALPACA_BASE_URL") or "https://api.alpaca.markets").rstrip("/")
        DATA_BASE = "https://data.alpaca.markets"
        if not KEY or not SECRET:
            raise RuntimeError("Missing Alpaca API credentials in environment")

        def alpaca_get(url, timeout=10):
            req = urllib.request.Request(url, headers={
                "APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return _json.loads(resp.read())

        def close_based_price(symbol, fallback):
            """Alpaca positions can show stale marks after-hours; prefer daily close/latest trade."""
            candidates = []
            try:
                bars = alpaca_get(f"{DATA_BASE}/v2/stocks/{symbol}/bars?timeframe=1Day&limit=1&adjustment=raw", timeout=6)
                for bar in bars.get("bars", []):
                    if bar.get("c"):
                        candidates.append(float(bar["c"]))
            except Exception:
                pass
            try:
                trade = alpaca_get(f"{DATA_BASE}/v2/stocks/{symbol}/trades/latest", timeout=6).get("trade", {})
                if trade.get("p"):
                    candidates.append(float(trade["p"]))
            except Exception:
                pass
            return candidates[0] if candidates else fallback

        # Account info
        acct = alpaca_get(f"{BASE}/v2/account")

        cash = float(acct.get("cash", 0))

        # Positions
        positions = alpaca_get(f"{BASE}/v2/positions")

        # Load tier tags
        tier1_syms = []
        try:
            import os as _os
            tags_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "../alpaca/tier_tags.json")
            with open(tags_path) as tf:
                tags = _json.load(tf)
            tier1_syms = tags.get("tier1_scalp", {}).get("symbols", [])
        except Exception:
            pass  # No tags yet, default all to tier1

        tier1_positions = []
        tier2_positions = []

        for p in positions:
            symbol = p.get("symbol", "?")
            pct_pnl = float(p.get("unrealized_plpc", 0)) * 100
            side = p.get("side", "long")
            cost = float(p.get("cost_basis", 0))
            broker_mval = float(p.get("market_value", 0))
            qty = abs(float(p.get("qty", 0) or 0))
            fallback_price = (broker_mval / qty) if qty else float(p.get("current_price", 0) or 0)
            price = close_based_price(symbol, fallback_price)
            mval = price * qty
            pct_pnl = ((mval / cost) - 1) * 100 if cost else 0
            entry = {"symbol": symbol, "pct_pnl": pct_pnl, "side": side, "cost": cost, "market_value": mval}
            # Tier 1 = Volume Scalp (executor.py); Tier 2 = Livermore Darvas
            if symbol in tier1_syms or not tier1_syms:
                tier1_positions.append(entry)
            else:
                tier2_positions.append(entry)

        tier2_positions.sort(key=lambda x: -abs(x["pct_pnl"]))
        tier1_positions.sort(key=lambda x: -abs(x["pct_pnl"]))

        # Load realized P&L by tier (tracked in tier_realized_pnl.json)
        t1_realized = 0.0
        t2_realized = 0.0
        t1_trade_count = 0
        t2_trade_count = 0
        try:
            import os as _os
            rpnl_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "../alpaca/tier_realized_pnl.json")
            with open(rpnl_path) as rf:
                rpnl = _json.load(rf)
            t1_realized = float(rpnl.get("tier1_scalp", {}).get("realized_pnl", 0))
            t2_realized = float(rpnl.get("tier2_darvas", {}).get("realized_pnl", 0))
            t1_trade_count = int(rpnl.get("tier1_scalp", {}).get("trade_count", 0))
            t2_trade_count = int(rpnl.get("tier2_darvas", {}).get("trade_count", 0))
        except Exception:
            pass

        # Tier equity = inception + realized P&L + open position unrealized P&L
        tier1_cost = sum(p["cost"] for p in tier1_positions)
        tier2_cost = sum(p["cost"] for p in tier2_positions)
        tier1_val = sum(p["market_value"] for p in tier1_positions)
        tier2_val = sum(p["market_value"] for p in tier2_positions)
        tier1_open_pnl = tier1_val - tier1_cost
        tier2_open_pnl = tier2_val - tier2_cost

        tier1_equity = TIER1_INCEPTION + t1_realized + tier1_open_pnl
        tier2_equity = TIER2_INCEPTION + t2_realized + tier2_open_pnl
        tier1_cash = max(0, tier1_equity - tier1_val)
        tier2_cash = max(0, tier2_equity - tier2_val)

        tier1_roi = ((tier1_equity / TIER1_INCEPTION) - 1) * 100 if TIER1_INCEPTION > 0 else 0
        tier2_roi = ((tier2_equity / TIER2_INCEPTION) - 1) * 100 if TIER2_INCEPTION > 0 else 0
        equity = cash + tier1_val + tier2_val
        inception_roi = ((equity / TOTAL_INCEPTION) - 1) * 100 if TOTAL_INCEPTION > 0 and equity > 0 else 0

        return {
            "tier2_positions": tier2_positions,
            "tier1_positions": tier1_positions,
            "tier2_roi": tier2_roi,
            "tier1_roi": tier1_roi,
            "tier2_equity": tier2_equity,
            "tier1_equity": tier1_equity,
            "tier2_cash": tier2_cash,
            "tier1_cash": tier1_cash,
            "t1_realized": t1_realized,
            "t2_realized": t2_realized,
            "t1_trade_count": t1_trade_count,
            "t2_trade_count": t2_trade_count,
            "inception_roi": inception_roi,
            "equity": equity,
            "cash": cash,
            "funded": equity > 0,
            # Legacy compat
            "positions": tier2_positions + tier1_positions,
        }
    except Exception as e:
        print(f"  ⚠ Alpaca fetch failed: {e}")
        return {"tier2_positions": [], "tier1_positions": [], "tier2_roi": 0, "tier1_roi": 0,
                "tier2_equity": 0, "tier1_equity": 0, "tier2_cash": 0, "tier1_cash": 0,
                "t1_realized": 0, "t2_realized": 0, "t1_trade_count": 0, "t2_trade_count": 0,
                "inception_roi": 0, "equity": 0, "cash": 0, "funded": False, "positions": []}

def fetch_fx():
    try:
        import yfinance as yf
        r = yf.Ticker("CADUSD=X").history(period="2d")
        usdcad = 1.0 / float(r["Close"].iloc[-1]) if len(r) >= 1 else 1.365
    except Exception:
        usdcad = 1.365
    try:
        import yfinance as yf
        r2 = yf.Ticker("AUDUSD=X").history(period="2d")
        audusd = float(r2["Close"].iloc[-1]) if len(r2) >= 1 else 0.630
    except Exception:
        audusd = 0.630
    return {"usdcad": usdcad, "audusd": audusd}


def fetch_fx_rates():
    """Fetch live FX rates for display — all pairs as 1 USD = X foreign currency"""
    try:
        import yfinance as yf
    except ImportError:
        return {}

    pairs = {
        "CAD": ("CADUSD=X", True,  1.365),    # invert CADUSD=X
        "THB": ("THBUSD=X", True,  34.5),     # invert THBUSD=X
        "AUD": ("AUDUSD=X", True,  1.580),    # invert AUDUSD=X
        "COP": ("COPUSD=X", True,  4150.0),   # invert COPUSD=X
        "EUR": ("EURUSD=X", True,  0.920),    # invert EURUSD=X
        "RUB": ("RUBUSD=X", True,  90.0),     # invert RUBUSD=X
        "KRW": ("KRWUSD=X", True,  1380.0),   # invert KRWUSD=X
        "JPY": ("JPYUSD=X", True,  150.0),    # invert JPYUSD=X
    }

    ICONS = {
        "CAD": "🇨🇦", "THB": "🇹🇭", "AUD": "🇦🇺",
        "COP": "🇨🇴", "EUR": "🇪🇺", "RUB": "🇷🇺", "KRW": "🇰🇷", "JPY": "🇯🇵",
    }
    SYMBOLS = {
        "CAD": "$", "THB": "฿", "AUD": "$",
        "COP": "$", "EUR": "€", "RUB": "₽", "KRW": "₩", "JPY": "¥",
    }

    results = {}
    for currency, (ticker, invert, fallback) in pairs.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if len(hist) >= 1:
                raw = float(hist["Close"].iloc[-1])
                rate = 1.0 / raw if invert else raw
            else:
                rate = fallback
        except Exception:
            rate = fallback

        # Format rate
        if currency in ("KRW", "COP"):
            fmt = f"{rate:,.0f}"
        elif currency == "JPY":
            fmt = f"{rate:.2f}"
        else:
            fmt = f"{rate:.2f}"

        results[currency] = {
            "rate":   rate,
            "fmt":    fmt,
            "icon":   ICONS[currency],
            "symbol": SYMBOLS[currency],
        }

    return results

# ─────────────────────────────────────────────────────────────
# SVG DONUT CHART
# ─────────────────────────────────────────────────────────────

ALLOCATION_PALETTES = [
    ("#F5FF5A", "#8CFF00"),  # graphene · charged lime
    ("#63FF9B", "#00E86F"),  # uranium · battery green
    ("#FFE66B", "#FFB000"),  # gold · charge amber
    ("#79F7FF", "#3D8BFF"),  # silver · electric cyan
    ("#FF875F", "#FF315D"),  # copper · warning charge
    ("#C57CFF", "#6E52FF"),  # molybdenum · ultraviolet
    ("#33FFF3", "#00B9FF"),  # hydro · ion blue
    ("#FF69F5", "#755CFF"),
    ("#F8FF7A", "#FF6B8C"),
]


def build_donut(allocations):
    """Build a scalable, luminous SVG from Google Sheet allocation percentages."""
    cx = cy = 160
    radius = 108
    stroke_width = 52
    circumference = 2 * math.pi * radius
    total = sum(v for _, v, _ in allocations)
    if total == 0:
        return ""

    gradients = []
    glows = []
    slices = []
    glosses = []
    offset = 0.0
    gap = 3.0
    description = []

    for i, (label, val, _) in enumerate(allocations):
        start, end = ALLOCATION_PALETTES[i % len(ALLOCATION_PALETTES)]
        gradient_id = f"allocation-gradient-{i}"
        gradients.append(
            f'<linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="100%" y2="100%">'
            f'<stop offset="0%" stop-color="{start}"/>'
            f'<stop offset="100%" stop-color="{end}"/>'
            f'</linearGradient>'
        )
        pct = val / total
        dash = pct * circumference
        visible_dash = max(dash - gap, 0)
        geometry = (
            f'r="{radius}" cx="{cx}" cy="{cy}" fill="none" '
            f'stroke="url(#{gradient_id})" stroke-width="{stroke_width}" '
            f'stroke-dasharray="{visible_dash:.2f} {circumference:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"'
        )
        glows.append(f'<circle class="allocation-glow" {geometry}/>' )
        slices.append(
            f'<circle class="allocation-slice" data-sector="{escape(label, quote=True)}" '
            f'data-percent="{val:.2f}" {geometry}/>'
        )
        gloss_geometry = geometry.replace(
            f'stroke="url(#{gradient_id})"',
            'stroke="url(#allocation-gloss)"',
        )
        glosses.append(f'<circle class="allocation-gloss" {gloss_geometry}/>')
        description.append(f"{label} {val:.1f}%")
        offset += dash

    return (
        '<svg class="pie-chart allocation-donut" viewBox="0 0 320 320" role="img" '
        'aria-labelledby="allocation-chart-title allocation-chart-desc" '
        'data-allocation-source="google-sheet">'
        '<title id="allocation-chart-title">Portfolio allocation from Google Sheet</title>'
        f'<desc id="allocation-chart-desc">{escape(", ".join(description))}</desc>'
        '<defs>'
        + "".join(gradients)
        + '<radialGradient id="allocation-gloss" cx="24%" cy="18%" r="84%">'
          '<stop offset="0%" stop-color="#ffffff" stop-opacity=".62"/>'
          '<stop offset="38%" stop-color="#ffffff" stop-opacity=".18"/>'
          '<stop offset="72%" stop-color="#ffffff" stop-opacity="0"/>'
          '</radialGradient>'
        + '<radialGradient id="allocation-core" cx="44%" cy="38%" r="75%">'
          '<stop offset="0%" stop-color="#191921"/>'
          '<stop offset="72%" stop-color="#0b0b10"/>'
          '<stop offset="100%" stop-color="#060608"/>'
          '</radialGradient>'
          '<filter id="allocation-bloom" x="-60%" y="-60%" width="220%" height="220%">'
          '<feGaussianBlur stdDeviation="6"/>'
          '</filter>'
          '</defs>'
        f'<circle class="allocation-aura" cx="{cx}" cy="{cy}" r="126"/>'
        f'<circle class="allocation-track" cx="{cx}" cy="{cy}" r="{radius}"/>'
        f'<g filter="url(#allocation-bloom)">{"".join(glows)}</g>'
        + "".join(slices)
        + f'<g class="allocation-gloss-layer">{"".join(glosses)}</g>'
        + f'<circle class="allocation-core" cx="{cx}" cy="{cy}" r="72"/>'
          '<text class="allocation-core-kicker" x="160" y="151" text-anchor="middle">PORTFOLIO</text>'
          '<text class="allocation-core-label" x="160" y="177" text-anchor="middle">LIVE SHEET</text>'
          '</svg>'
    )


def build_legend(allocations, total_val=None):
    """Render the percentages exactly as supplied by the Google Sheet."""
    items = []
    for i, (label, val, _) in enumerate(allocations):
        start, end = ALLOCATION_PALETTES[i % len(ALLOCATION_PALETTES)]
        safe_label = escape(label, quote=True)
        items.append(
            f'<div class="legend-item" data-allocation-sector="{safe_label}" data-allocation-pct="{val:.2f}">'
            f'<span class="legend-dot" style="--swatch-start:{start};--swatch-end:{end}"></span>'
            f'<span class="legend-name">{safe_label}</span>'
            f'<span class="legend-pct">{val:.1f}%</span></div>'
        )
    return "\n".join(items)


def build_sheet_allocation_component(gs_meta):
    """Build the allocation component exclusively from the Sheet's % of Fund data."""
    allocations = (gs_meta or {}).get("sector_allocations_pct") or []
    if not allocations:
        return (
            '<div class="allocation-unavailable">Allocation awaiting Google Sheet sync.</div>',
            "",
            '<div class="allocation-source allocation-source--offline">Google Sheet allocation unavailable</div>',
        )

    alloc_list = [(label, float(percent), "") for label, percent in allocations]
    source = escape((gs_meta or {}).get("allocation_source") or "Google Sheet · % of Fund")
    return (
        build_donut(alloc_list),
        build_legend(alloc_list),
        f'<div class="allocation-source"><span aria-hidden="true"></span>{source} · live source of truth</div>',
    )

# ─────────────────────────────────────────────────────────────
# HTML GENERATION
# ─────────────────────────────────────────────────────────────

SIGNAL_BOLT_SVG = (
    '<svg class="signal-bolt-icon" viewBox="45 38 200 264" aria-hidden="true" focusable="false">'
    '<path fill="currentColor" d="M219 44Q217 43 215 44L51 180Q49 183 51 185Q53 187 56 187L130 186Q132 186 132 188L72 289Q70 293 73 295Q76 297 83 291L239 155Q241 153 239 149Q238 147 236 147L166 148Q162 148 160 146L219 51Q222 46 219 44Z"/>'
    '</svg>'
)


def render_html(weather, bangkok_news, zh_news, portfolio_data, catalysts,
                commodities, crypto, fx, zodiac, thai_word, motivation, rec_movie=None, rec_book=None, fx_rates=None, holdings_source=None, gs_meta=None, spanish_word=None, poly_html="", alpaca_html="", fed_signal=None, economies=None, suggested_tweet=None, market_futures=None, market_indices=None):

    now       = datetime.now(timezone.utc).astimezone(BKK_TZ)
    date_str  = now.strftime("%A, %B %-d, %Y")
    gen_time  = now.strftime("%H:%M ICT")
    daily_edition = now.strftime("%Y-%m-%d")
    week_start = now - timedelta(days=now.weekday())
    weekly_edition = f"{week_start.isocalendar().year}-W{week_start.isocalendar().week:02d}"
    weekly_updated_label = week_start.strftime("%b %-d")

    # ── Next market holidays ──
    from datetime import date as _date
    _today = now.date()

    def countdown_label(target_date, past_label="since"):
        days = (target_date - _today).days
        if days > 1:
            return f"{days} days"
        if days == 1:
            return "1 day"
        if days == 0:
            return "Today"
        return f"{abs(days)} days {past_label}"

    # ── Personal countdowns ──
    trip_date = _date(2026, 9, 30)
    trans_siberian_date = _date(2027, 9, 1)
    edc_thailand_date = _date(2026, 12, 18)
    mastermind_retreat_date = _date(2027, 1, 19)
    trip_countdown_text = countdown_label(trip_date, "since departure")
    trans_siberian_countdown_text = countdown_label(trans_siberian_date, "since departure")
    edc_countdown_text = countdown_label(edc_thailand_date, "since EDC")
    retreat_countdown_text = countdown_label(mastermind_retreat_date, "since kickoff")
    _nyse = [(_date(2026,4,3),"Good Friday"),(_date(2026,5,25),"Memorial Day"),(_date(2026,6,19),"Juneteenth"),(_date(2026,7,3),"Independence Day"),(_date(2026,9,7),"Labor Day"),(_date(2026,11,26),"Thanksgiving"),(_date(2026,12,25),"Christmas")]
    _tsx = [(_date(2026,4,3),"Good Friday"),(_date(2026,5,18),"Victoria Day"),(_date(2026,7,1),"Canada Day"),(_date(2026,8,3),"Civic Holiday"),(_date(2026,9,7),"Labour Day"),(_date(2026,10,12),"Thanksgiving"),(_date(2026,12,25),"Christmas"),(_date(2026,12,28),"Boxing Day")]
    next_nyse_str = next((f"{n} · {d.strftime('%b %d')}" for d, n in _nyse if d > _today), "None scheduled")
    next_tsx_str = next((f"{n} · {d.strftime('%b %d')}" for d, n in _tsx if d > _today), "None scheduled")

    # ── Portfolio calculations ──
    total_usd   = 0
    sector_totals = {}
    port_sorted = []

    for h in (holdings_source or HOLDINGS):
        ticker = h["ticker"]
        pdata  = portfolio_data.get(ticker, {})
        price  = pdata.get("price")
        value  = pdata.get("value")
        change = pdata.get("change")
        is_fallback = pdata.get("fallback", False)
        port_sorted.append((ticker, h, price, value, change, is_fallback))

    port_sorted.sort(key=lambda x: (x[3] or 0), reverse=True)

    for ticker, h, price, value, change, is_fallback in port_sorted:
        if value:
            total_usd += value
            sector = SECTORS.get(ticker, "Other")
            sector_totals[sector] = sector_totals.get(sector, 0) + value

    total_cad  = total_usd * fx["usdcad"]
    roi_pct    = ((total_cad - PORT_BASIS_CAD) / PORT_BASIS_CAD * 100) if PORT_BASIS_CAD else 0

    # Override with sheet totals if available (source of truth)
    _meta = gs_meta or {}
    if _meta.get("total_cad"):
        total_cad = _meta["total_cad"]
    if _meta.get("total_usd"):
        total_usd = _meta["total_usd"]
    if _meta.get("roi_pct_str"):
        try:
            roi_pct = float(_meta["roi_pct_str"].replace("%", "").strip())
        except: pass
    port_ath = _meta.get("ath") or PORT_ATH
    port_roi_abs = _meta.get("roi_abs") or PORT_ROI_ABS
    port_basis_cad = (total_cad - port_roi_abs) if _meta.get("roi_abs") else PORT_BASIS_CAD

    # Build holdings rows HTML
    rows_html = ""
    for ticker, h, price, value, change, is_fallback in port_sorted:
        display = h.get("display", ticker.split(".")[0])
        name    = h["name"]
        shares  = h["shares"]
        chg_html    = fmt_pct(change)
        fallback_note = '<span class="fallback-badge">est</span>' if is_fallback else ""
        price_str   = (fmt_price(price, 2) + fallback_note) if price and price >= 0.01 else \
                      ((fmt_price(price, 4) + fallback_note) if price else "—")
        value_str   = f"${value:,.0f}" if value else "—"
        rows_html += f"""
          <tr>
            <td class="ticker chart-ticker" data-chart-symbol="{ticker}" data-chart-name="{escape(name, quote=True)}" tabindex="0" role="button" aria-label="Open {escape(display, quote=True)} price chart">{display}</td>
            <td style="color:var(--dim);font-size:.8em">{name}</td>
            <td style="text-align:right">{int(shares):,}</td>
            <td style="text-align:right">{price_str}</td>
            <td style="text-align:right">{chg_html}</td>
            <td style="text-align:right;font-weight:600">{value_str}</td>
          </tr>"""

    # ── Allocation chart: fail closed to the Google Sheet source of truth ──
    donut_svg, legend_html, allocation_source_html = build_sheet_allocation_component(_meta)

    # ── Top 5 by value ──
    top5 = [t for t, *_ in port_sorted[:5]]

    # ── Catalysts HTML (top 5, latest verified item within 14 days) ──
    # If ALL 5 have no news → one collapsed line. Otherwise show per-ticker lines.
    fresh_cats  = [(t, catalysts.get(t)) for t in top5 if catalysts.get(t) and catalysts.get(t, {}).get("fresh")]
    no_news_tks = [t for t in top5 if not (catalysts.get(t) and catalysts.get(t, {}).get("fresh"))]
    catalyst_ids = [hashlib.sha256(f"{ticker}|{cat.get('date','')}|{cat.get('source','')}|{cat.get('title','')}".encode()).hexdigest()[:16] for ticker, cat in fresh_cats]
    catalyst_fingerprint = hashlib.sha256("|".join(catalyst_ids).encode()).hexdigest()[:16]
    catalyst_ids_attr = escape(json.dumps(catalyst_ids, separators=(',', ':')), quote=True)

    cats_html = ""
    for ticker, cat in fresh_cats:
        display    = HOLDINGS_MAP.get(ticker, {}).get("display", ticker.split(".")[0])
        source_str = f' · {cat["source"]}' if cat["source"] else ""
        cats_html += f"""
            <div class="catalyst-item">
              <span class="catalyst-ticker">{display}</span>
              <span class="catalyst-sep"> · </span>
              <span class="catalyst-badge">{cat['date']}{source_str}</span>
              <span class="catalyst-sep"> — </span>
              <span class="catalyst-headline">{cat['title']}</span>
            </div>"""

    if no_news_tks:
        no_news_displays = " · ".join(
            HOLDINGS_MAP.get(t, {}).get("display", t.split(".")[0]) for t in no_news_tks
        )
        cats_html += f"""
            <div class="catalyst-item">
              <span class="catalyst-ticker">{no_news_displays}</span>
              <span class="catalyst-sep"> — </span>
              <span class="catalyst-headline" style="color:var(--dim);font-style:italic">No verified news within 14 days.</span>
            </div>"""

    # ── Radar Moonshots HTML (3 crypto + 3 resource, live Reddit) ──
    print("  🎯 Fetching Radar Moonshots (Reddit)...")
    moonshots = fetch_radar_moonshots()

    def _radar_rows(items):
        html = ""
        for item in items:
            src      = item.get("source", "")
            src_html = f'<span class="radar-source">[{src}]</span> ' if src else ""
            html    += f'<div class="radar-item">{src_html}<span class="radar-idea">{item["title"]}</span></div>'
        return html

    radar_crypto_html   = _radar_rows(moonshots.get("crypto", []))
    radar_resource_html = _radar_rows(moonshots.get("resource", []))

    weekly = load_weekly_ideas()
    weekly_rows = ""
    for idea in weekly.get("ideas", [])[:6]:
        action = escape(str(idea.get("action", "WATCH")).upper())
        asset_type = escape(str(idea.get("type", "idea")).upper())
        symbol = escape(str(idea.get("symbol", "—")))
        name = escape(str(idea.get("name", symbol)))
        snapshot = escape(str(idea.get("snapshot", "Data unavailable")))
        thesis = escape(str(idea.get("thesis", "")))
        risk = escape(str(idea.get("risk", "")))
        trigger = escape(str(idea.get("trigger", "")))
        source_url = escape(str(idea.get("source_url", "#")), quote=True)
        weekly_rows += f"""
        <div class="weekly-idea">
          <div class="weekly-idea-top"><span class="weekly-action">{action}</span><span class="weekly-type">{asset_type}</span><a href="{source_url}" target="_blank" rel="noopener">{symbol} · {name}</a></div>
          <div class="weekly-snapshot">{snapshot}</div>
          <div class="weekly-points">
            <div class="weekly-thesis"><b>Edge</b><span>{thesis}</span></div>
            <div class="weekly-risk"><b>Risk</b><span>{risk}</span></div>
            <div class="weekly-trigger"><b>Go</b><span>{trigger}</span></div>
          </div>
        </div>"""
    if not weekly_rows:
        weekly_rows = '<div class="weekly-empty">Weekly scan awaiting verified data. No counterfeit conviction.</div>'
    weekly_as_of = escape(str(weekly.get("as_of") or "awaiting scan"))
    weekly_note = escape(str(weekly.get("portfolio_note") or "Screened against current holdings and trading accounts."))

    # ── FX Rates HTML ──
    FX_ORDER = ["CAD", "THB", "AUD", "COP", "EUR", "RUB", "KRW", "JPY"]
    fx_rates_html = ""
    if fx_rates:
        for ccy in FX_ORDER:
            d = fx_rates.get(ccy)
            if not d:
                continue
            # Shorten large numbers for compact strip
            val = d['fmt']
            fx_rates_html += f"""
      <div class="fx-chip"><div class="fx-ccy">{d['icon']} {ccy}</div><span class="fx-rate" data-fx-rate="{ccy}">{val}</span></div>"""

    # ── Weather HTML ──
    import datetime as _dt
    month = _dt.datetime.utcnow().month
    def get_season(city_name, lat, month):
        if city_name == "Medellín": return "Eternal Spring"
        if city_name == "Bangkok":
            if month in (11, 12, 1, 2): return "Cool Season"
            if month in (3, 4, 5): return "Hot Season"
            return "Rainy Season"
        if lat < 0:  # Southern hemisphere
            if month in (12, 1, 2): return "Summer"
            if month in (3, 4, 5): return "Autumn"
            if month in (6, 7, 8): return "Winter"
            return "Spring"
        else:  # Northern hemisphere
            if month in (12, 1, 2): return "Winter"
            if month in (3, 4, 5): return "Spring"
            if month in (6, 7, 8): return "Summer"
            return "Autumn"

    weather_html = ""
    for w in weather:
        temp_str = f"{w['temp']:.0f}°C" if w["temp"] is not None else "—"
        season = get_season(w['name'], w.get('lat', 0), month)
        # Local time in 24h format
        import datetime as _dtmod
        local_time = _dtmod.datetime.now(_dtmod.timezone.utc) + _dtmod.timedelta(hours=w.get('tz_offset', 0))
        local_time_str = local_time.strftime("%H:%M")
        weather_html += f"""
        <div class="weather-item">
          <div class="condition live-clock" data-tz-offset="{w.get('tz_offset', 0)}" style="font-size:.7rem;margin-bottom:3px;letter-spacing:.08em;font-weight:600">{local_time_str}</div>
          <div class="city">{w['flag']} {w['name']}</div>
          <div class="temp">{temp_str}</div>
          <div class="condition">{w['condition']}</div>
          <div class="condition" style="margin-top:2px;font-style:italic">{season}</div>
          <div class="condition" style="margin-top:3px;font-size:.58rem;opacity:.7">💧 {w.get('humidity', '—') or '—'}% · AQI {w.get('aqi', '—') or '—'} ({w.get('aqi_label', '—')})</div>
        </div>"""

    # ── Wall Street futures + Fed Signal HTML ──
    fed = fed_signal or fetch_fed_signal()
    days_label = f"{fed['days_until']} day{'s' if fed['days_until'] != 1 else ''}"
    futures_data = market_futures or fetch_market_futures()
    indices_data = market_indices or fetch_market_indices()
    futures_html = ""
    for (symbol, meta), (cash_symbol, cash_meta) in zip(MARKET_FUTURES.items(), MARKET_INDICES.items()):
        item = futures_data.get(symbol, {})
        cash = indices_data.get(cash_symbol, {})
        price = item.get("price")
        change = item.get("change")
        cash_price = cash.get("price")
        cash_change = cash.get("change")
        price_text = f"{price:,.2f}" if price is not None else "—"
        change_text = f"{change:+.2f}%" if change is not None else "—"
        cash_price_text = f"{cash_price:,.2f}" if cash_price is not None else "—"
        cash_change_text = f"{cash_change:+.2f}%" if cash_change is not None else "—"
        change_class = "positive" if change is not None and change >= 0 else ("negative" if change is not None else "")
        cash_change_class = "positive" if cash_change is not None and cash_change >= 0 else ("negative" if cash_change is not None else "")
        quote_time = escape(str(item.get("quote_time") or ""), quote=True)
        futures_html += f"""
        <div class="market-future" data-future-symbol="{symbol}" data-quote-time="{quote_time}">
          <span>{meta['short']}</span>
          <b data-future-price>{price_text}</b>
          <em data-future-change class="{change_class}">{change_text}</em>
          <small title="{cash_meta['label']} cash index"><i>Cash</i><strong data-market-price="{cash_symbol}">{cash_price_text}</strong><u data-market-change="{cash_symbol}" class="{cash_change_class}">{cash_change_text}</u></small>
        </div>"""
    market_html = f"""
  <div class="card market-card">
    <div class="market-clock">
      <div class="market-primary"><span class="market-label">🗽 Wall Street</span><b class="wall-time live-clock" data-tz-offset="-4"></b></div>
      <div class="market-futures" aria-label="Live major US index futures">{futures_html}</div>
      <div class="market-calendar">NYSE {next_nyse_str} <span>·</span> TSX {next_tsx_str}</div>
    </div>
  </div>"""
    fed_html = f"""
  <details class="card fed-card signal-accordion" id="fed-signal-card">
    <summary>
      <div class="fed-title">🏛️ Fed Signal</div>
      <span class="fed-summary-rate">{fed['fed_funds_rate']}</span>
      <span class="fed-summary-sentiment">Hold {fed['hold_pct']}%</span>
    </summary>
    <div class="signal-accordion-body fed-compact">
      <div class="fed-stats">
        <div class="fed-stat"><span>Rate</span><b class="fed-rate">{fed['fed_funds_rate']}</b></div>
        <div class="fed-stat fed-fomc"><span>Next FOMC</span><b>{fed['next_decision']}</b><em>{days_label}</em></div>
        <div class="fed-stat fed-prob"><span>CME FedWatch</span><b><i>Hold {fed['hold_pct']}%</i><i>Cut {fed['cut_25bps_pct']}%</i></b></div>
      </div>
    </div>
  </details>"""
    # ── Top 5 Economies HTML: show only every two weeks on Monday ──
    eco_html = ""
    if show_biweekly_monday_section():
        eco_data = economies or fetch_top5_economies()
        iso = now.isocalendar()
        eco_edition = f"{iso.year}-W{iso.week:02d}"
        eco_rows = ""
        for e in eco_data:
            yoy = e.get('gdp_yoy', '—')
            yoy_color = "var(--green)" if yoy.startswith("+") and yoy != "+0.0%" else ("var(--red)" if yoy.startswith("-") else "var(--dim)")
            eco_rows += f"""
      <tr>
        <td><span class="eco-flag">{e['flag']}</span></td>
        <td class="eco-country">{e['country']}</td>
        <td class="eco-gdp">{e['gdp']}</td>
        <td style="text-align:right;font-size:.72rem;color:{yoy_color}">{yoy}</td>
        <td style="text-align:right;font-size:.72rem;color:var(--dim)">{e['per_capita']}</td>
        <td class="eco-infl" style="text-align:right;color:var(--dim)">{e['inflation']}</td>
      </tr>"""
        eco_html = f"""
  <details class="card signal-accordion" id="economies-card" data-edition="{eco_edition}" open>
    <summary><span class="card-title">🌍 Top 5 Economies · Biweekly Monday</span><span class="accordion-score">New edition</span></summary>
    <div class="signal-accordion-body"><table class="eco-table">
      <thead>
        <tr>
          <th colspan="2">Country</th>
          <th>GDP Nom.</th>
          <th style="text-align:right">YoY</th>
          <th style="text-align:right">Per Capita</th>
          <th style="text-align:right">Inflation</th>
        </tr>
      </thead>
      <tbody>{eco_rows}</tbody>
    </table>
    <div style="font-size:.58rem;color:var(--mute);margin-top:8px;text-align:right">IMF 2024 nom. · GDP YoY: Q4 2025 · Shows every two weeks on Monday</div>
    </div>
  </details>"""

    # ── Thailand expat news HTML ──
    bkk_html = ""
    for item in bangkok_news[:1]:
        title = escape(item.get("title", "Thailand expat news feed temporarily unavailable"))
        url = escape(item.get("url", "https://thethaiger.com/"), quote=True)
        source = escape(item.get("source", "Thailand Expat Brief"))
        summary = escape(item.get("summary", ""))
        score = escape(str(item.get("score", "")))
        verified_at = datetime.now(BKK_TZ).strftime("%b %-d, %H:%M BKK")
        summary_html = f'<div class="thai-news-summary">{summary}</div>' if summary else ''
        bkk_html += f'''<div class="thai-news-item thai-news-feature" data-thai-expat-brief="verified" data-thai-source="{source}" data-thai-score="{score}" data-thai-url="{url}">
          <div class="thai-news-source">{source} · Expat-relevant · Verified {verified_at}</div>
          <a href="{url}" style="color:var(--text);text-decoration:none" target="_blank" rel="noopener">{title}</a>
          {summary_html}
          <div class="thai-news-verify">Live check marker: expat brief has a real source, URL, summary, and score {score}.</div>
        </div>'''
    if not bkk_html:
        bkk_html = '<div class="thai-news-item">Thailand expat news feed temporarily unavailable.</div>'

    # ── ZeroHedge HTML ──
    zh_html = ""
    for i, item in enumerate(zh_news[:3], 1):
        zh_html += f"""
        <div class="headline">
          <span class="headline-num">{i}</span>
          <a href="{item['url']}" class="headline-text" style="text-decoration:none;color:var(--text)" target="_blank">{item['title']}</a>
        </div>"""

    # ── Commodities HTML ──
    comm_html = ""
    for sym, c in commodities.items():
        price_str = fmt_price(c["price"]) if c["price"] else "—"
        chg_html  = fmt_pct(c["change"]) if c["change"] is not None else '<span style="color:var(--dim)">—</span>'
        comm_html += f"""
        <div class="commodity-item" data-commodity="{sym}">
          <div class="commodity-name {c['cls']}">{c['name']}</div>
          <div class="commodity-price {c['cls']}" data-comm-price="{sym}">{price_str}</div>
          <div class="commodity-unit">{c['unit']}</div>
          <div class="commodity-change" data-comm-chg="{sym}">{chg_html}</div>
        </div>"""

    # ── Crypto HTML ──
    crypto_colors = {"BTC": "#f7931a","ETH": "#627eea","SOL": "#9945ff","SUI": "#6fd7ff",
                     "ADA": "#2a6df4","TON": "#0098ea","NIGHT": "#7868ff","ZEC": "#f4b728"}
    crypto_html = ""
    crypto_order = sorted(crypto, key=lambda coin: crypto.get(coin, {}).get("market_cap") or 0, reverse=True)
    for coin in crypto_order:
        c     = crypto.get(coin, {})
        price = c.get("price")
        chg   = c.get("change")
        price_str = fmt_price(price) if price else "—"
        chg_html  = fmt_pct(chg) if chg is not None else '<span style="color:var(--dim)">—</span>'
        color     = crypto_colors.get(coin, "#e0dde8")
        crypto_html += f"""
        <div class="crypto-item" data-coin="{coin}">
          <div class="crypto-symbol" style="color:{color}">{coin}</div>
          <div class="crypto-price" data-crypto-price="{coin}" style="color:{color}">{price_str}</div>
          <div class="crypto-change" data-crypto-chg="{coin}">{chg_html}</div>
        </div>"""

    latest_content = fetch_latest_novaire_content()
    clip = latest_content["clip"] or {
        "title": "Latest Second Renaissance clip",
        "url": SECOND_RENAISSANCE["channel_url"],
        "views": None,
        "likes": None,
    }
    episode = latest_content["episode"]
    instagram = latest_content["instagram"]
    measurable = [item.get("likes") for item in (instagram, clip, episode) if item.get("likes") is not None]
    top_likes = max(measurable) if measurable else None

    def compact_count(value):
        if value is None:
            return "—"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return f"{value:,}"

    def social_item(kicker, item, action, extra_metric=""):
        views = item.get("views")
        likes = item.get("likes")
        comments = item.get("comments")
        is_top = likes is not None and likes == top_likes and len(measurable) > 1
        top_badge = '<span class="metric-winner">Top engagement</span>' if is_top else ""
        visible_metrics = []
        if extra_metric:
            visible_metrics.append(extra_metric)
        if views is not None:
            visible_metrics.append(f'<span><b>{compact_count(views)}</b> views</span>')
        if likes is not None:
            visible_metrics.append(f'<span><b>{compact_count(likes)}</b> likes</span>')
        if comments is not None:
            visible_metrics.append(f'<span><b>{compact_count(comments)}</b> comments</span>')
        return f'''<details class="latest-novaire-item">
          <summary>
            <span class="latest-novaire-copy">
              <span class="latest-novaire-kicker">{kicker}</span>
              <strong>{escape(item["title"])}</strong>
            </span>
            <span class="latest-novaire-chevron" aria-hidden="true">⌄</span>
          </summary>
          <div class="latest-novaire-detail">
            <div class="latest-novaire-metrics">{"".join(visible_metrics)}{top_badge}</div>
            <a href="{escape(item["url"], quote=True)}" target="_blank" rel="noopener">{action} →</a>
          </div>
        </details>'''

    instagram_followers = (
        f'<span><b>{compact_count(instagram.get("followers"))}</b> followers</span>'
        if instagram.get("followers") is not None else ""
    )
    latest_social_items = "".join([
        social_item("INSTAGRAM · LATEST POST", instagram, "Open Instagram", instagram_followers),
        social_item("YOUTUBE · LATEST CLIP", clip, "Watch clip"),
        social_item("YOUTUBE · FULL EPISODE", episode, "Play episode"),
    ])

    latest_novaire_html = f"""
  <!-- LATEST FROM NOVAIRE -->
  <div class="card latest-novaire-card">
    <div class="card-title">✦ Latest from Novaire</div>
    <div class="latest-novaire-stack">
      {latest_social_items}
      <details class="latest-novaire-item">
        <summary>
          <span class="latest-novaire-copy">
            <span class="latest-novaire-kicker">READ · NOVAIRE INK</span>
            <strong>When You Don't Write, You Are Wrong</strong>
          </span>
          <span class="latest-novaire-chevron" aria-hidden="true">⌄</span>
        </summary>
        <div class="latest-novaire-detail latest-novaire-ink-detail">
          <span>Latest essay · <b id="ink-unique-views">—</b> unique readers</span>
          <a href="https://novaireink.com/#when-you-dont-write" target="_blank" rel="noopener">Read essay →</a>
        </div>
      </details>
    </div>
  </div>"""

    # Full HTML template
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Novaire Signal — Daily Brief</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#0a0a0c">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Signal ⚡">
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400;1,500&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    :root{{
      --bg:#0a0a0c;--surface:#111116;--border:#1e1e26;--text:#f0eef8;--dim:#a8a4ba;--mute:#6e6a85;
      --gold:#b59662;--gold-dim:rgba(181,150,98,.12);--gold-mid:rgba(181,150,98,.25);
      --green:#2a9d8f;--red:#e63946;--blue:#5a7bc4;--violet:#9470c8;
      --sans:'Inter',sans-serif;--serif:'Cormorant Garamond',serif;--r:6px;
    }}
    html{{scroll-behavior:smooth;font-size:110%}}
    body{{font-family:var(--sans);background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:32px 16px;font-size:18.15px;line-height:1.5}}
    .container{{max-width:720px;margin:0 auto}}

    .header-brand{{text-align:center;padding-bottom:20px}}

    .signal-bolt{{display:inline-flex;align-items:center;text-decoration:none;margin-left:6px;vertical-align:baseline;position:relative;top:-1px;transition:all .3s ease;font-size:1.1rem;color:#b59662;line-height:1}}
    .signal-bolt-icon{{width:.82em;height:1.05em;display:block;fill:currentColor}}
    .signal-bolt:hover{{opacity:.7;transform:scale(1.1)}}
    .section-bolt{{display:inline-block;color:var(--gold);font-family:'Segoe UI Symbol','Noto Sans Symbols 2',sans-serif;font-size:1em;line-height:1;vertical-align:-.04em}}
    @keyframes neon-flicker{{0%,100%{{opacity:1}}92%{{opacity:1}}93%{{opacity:.8}}94%{{opacity:1}}96%{{opacity:.9}}97%{{opacity:1}}}}

    .dateline{{text-align:center;padding:0 0 28px;margin-bottom:28px;border-bottom:1px solid var(--border)}}
    .dateline .date{{font-size:.7rem;letter-spacing:.2em;text-transform:uppercase;color:var(--dim)}}
    .dateline .gen{{font-size:.6rem;color:var(--mute);margin-top:3px}}

    .card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px;margin-bottom:14px}}
    .card-title{{font-size:.6rem;font-weight:600;letter-spacing:.24em;text-transform:uppercase;color:var(--gold);margin-bottom:16px;display:flex;align-items:center;gap:8px}}
    .card-title::after{{content:'';flex:1;height:1px;background:linear-gradient(90deg,var(--gold-mid),transparent)}}
    .signal-accordion{{padding:0;overflow:hidden}}
    .signal-accordion>summary{{list-style:none;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 20px;cursor:pointer}}
    .signal-accordion>summary::-webkit-details-marker{{display:none}}
    .signal-accordion>summary .card-title{{margin:0;flex:1}}
    .signal-accordion>summary::after{{content:'⌄';color:var(--gold);font-size:1rem;transition:transform .15s}}
    .signal-accordion[open]>summary::after{{transform:rotate(180deg)}}
    .signal-accordion-body{{padding:0 20px 20px}}
    .accordion-score{{font-size:.68rem;color:var(--dim);white-space:nowrap}}
    .accordion-score b{{color:var(--text);font-size:.78rem}}
    .catalyst-unread{{font-size:.56rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#ffd06b;border:1px solid rgba(255,208,107,.42);border-radius:999px;padding:4px 8px;white-space:nowrap}}
    #catalysts-card:not([open]).has-unread .catalyst-unread{{animation:catalyst-mail 1.35s ease-in-out infinite;box-shadow:0 0 14px rgba(255,208,107,.28)}}
    @keyframes catalyst-mail{{0%,100%{{opacity:.62;transform:scale(.98)}}50%{{opacity:1;transform:scale(1.04)}}}}
    @media(prefers-reduced-motion:reduce){{#catalysts-card:not([open]).has-unread .catalyst-unread{{animation:none}}}}
    .trading-accordion>summary{{padding-top:15px;padding-bottom:15px}}

    .trip-countdown{{padding:14px 16px}}
    .trip-row{{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap}}
    .trip-days{{font-family:var(--serif);font-size:1.35rem;color:var(--text);line-height:1.2}}
    .trip-sub{{font-size:.65rem;color:var(--gold);letter-spacing:.08em;text-transform:uppercase}}
    .countdown-strip{{padding:13px 16px}}
    .daily-signal-card{{padding:0;overflow:hidden}}
    .daily-signal-card>summary{{min-height:62px;box-sizing:border-box;padding:18px 20px}}
    .daily-signal-card:not([open])>summary{{min-height:62px}}
    #world-tour-card{{padding:0}}
    #world-tour-card .signal-accordion-body{{padding:0 16px 16px}}
    .countdown-strip-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;align-items:stretch}}
    .countdown-item{{text-align:center;padding:4px 10px;border-right:1px solid var(--border)}}
    .countdown-item:last-child{{border-right:none}}
    .countdown-label{{font-size:.56rem;font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);margin-bottom:5px;white-space:nowrap}}
    .countdown-days{{font-family:var(--serif);font-size:1.18rem;color:var(--text);line-height:1.15}}
    .countdown-date{{font-size:.58rem;color:var(--dim);letter-spacing:.08em;text-transform:uppercase;margin-top:4px}}
    @media(max-width:620px){{.countdown-strip-grid{{grid-template-columns:1fr;gap:12px}}.countdown-item{{border-right:none;border-bottom:1px solid var(--border);padding-bottom:12px}}.countdown-item:last-child{{border-bottom:none;padding-bottom:4px}}}}

    .quote{{margin-bottom:8px;padding-left:10px;border-left:1px solid var(--gold-mid)}}
    .quote:last-child{{margin-bottom:0}}
    .quote-type{{font-size:.6rem;color:var(--gold);text-transform:uppercase;letter-spacing:.14em;margin-bottom:2px;font-weight:600}}
    .quote-text{{font-family:var(--serif);font-size:1.1rem;font-style:italic;color:var(--text);line-height:1.55}}
    .quote-author{{font-size:.68rem;color:var(--dim);margin-top:3px}}
    .meditation{{margin-bottom:14px;padding:0;border:1px solid rgba(181,150,98,.22);border-radius:14px;background:linear-gradient(135deg,rgba(181,150,98,.08),rgba(255,255,255,.02));overflow:hidden}}
    .meditation>summary{{list-style:none;cursor:pointer;padding:12px 14px;position:relative;display:flex;align-items:center;justify-content:space-between;gap:12px}}
    .meditation-summary-copy{{min-width:0}}
    .meditation>summary::-webkit-details-marker{{display:none}}
    .meditation-title{{font-family:var(--serif);font-size:1rem;color:var(--gold);margin-bottom:3px}}
    .meditation-meta{{font-size:.62rem;color:var(--dim);text-transform:uppercase;letter-spacing:.12em;margin-bottom:6px}}
    .meditation-brief{{font-size:.72rem;line-height:1.48;color:var(--dim)}}
    .meditation-body{{padding:0 14px 13px}}
    .meditation-excerpt{{font-size:.86rem;line-height:1.62;color:var(--muted)}}
    .meditation-collapse{{display:block;margin:11px 0 0 auto;border:0;background:transparent;color:var(--gold);font:600 .5rem var(--sans);letter-spacing:.12em;text-transform:uppercase;cursor:pointer}}
    #quotes-card{{padding:0}}
    #quotes-card>.signal-accordion-body{{padding:0 16px 16px}}
    #quotes-card .meditation{{margin-top:0}}
    .updog-intro{{font-size:.7rem;color:var(--dim);line-height:1.45;margin:-2px 0 10px}}
    .updog-btn{{border:1px solid var(--gold-mid);border-radius:999px;padding:5px 9px;font-size:.5rem;text-align:center;text-decoration:none;text-transform:uppercase;letter-spacing:.1em;transition:.18s ease;white-space:nowrap;cursor:pointer;font-family:var(--sans)}}
    .updog-approve{{background:rgba(181,150,98,.16);color:var(--gold)}}
    .updog-retry{{color:var(--dim);border-color:rgba(255,255,255,.16);background:transparent}}
    .updog-btn:hover{{transform:translateY(-1px);filter:brightness(1.15)}}
    .tweet-card{{border-color:rgba(181,150,98,.22);background:linear-gradient(145deg,rgba(181,150,98,.07),rgba(255,255,255,.025))}}
    .tweet-top{{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap}}
    .tweet-chip{{font-size:.52rem;color:var(--gold);border:1px solid var(--gold-mid);border-radius:999px;padding:4px 8px;text-transform:uppercase;letter-spacing:.12em;background:rgba(181,150,98,.08)}}
    .tweet-source{{font-size:.58rem;color:var(--dim);letter-spacing:.06em;text-transform:uppercase}}
    .tweet-text{{font-family:var(--serif);font-size:1.02rem;line-height:1.48;color:var(--text);margin:0 0 12px}}
    .tweet-actions{{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}}
    .tweet-count{{font-size:.58rem;color:var(--mute)}}
    .keystone-row{{display:flex;width:100%;box-sizing:border-box;align-items:stretch;border:1px solid rgba(255,255,255,.12);border-radius:12px;overflow:hidden;background:rgba(0,0,0,.22)}}
    .keystone-row:focus-within{{border-color:var(--gold-mid);box-shadow:0 0 0 2px rgba(181,150,98,.08)}}
    .keystone-input{{flex:1 1 auto;width:auto;min-width:0;box-sizing:border-box;border:0;background:transparent;color:var(--text);border-radius:0;padding:10px 14px;font-size:.9rem;line-height:1.2;outline:none;min-height:42px}}
    .keystone-input:focus{{box-shadow:none}}
    .keystone-done{{flex:0 0 50px;align-self:stretch;box-sizing:border-box;display:flex;align-items:center;justify-content:center;border:0;border-left:1px solid rgba(181,150,98,.38);border-radius:0;padding:0;font-size:.42rem;letter-spacing:.08em;background:rgba(181,150,98,.12);min-height:0}}
    .keystone-done:hover{{transform:none;filter:brightness(1.15)}}
    .updog-action-card{{margin-top:-6px}}
    .action-step-heading{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}}
    .action-step-heading .card-title{{margin-bottom:0}}
    .keystone-streak{{font-size:.58rem;font-weight:650;color:var(--gold);border:1px solid var(--gold-mid);background:var(--gold-dim);border-radius:999px;padding:5px 9px;white-space:nowrap}}
    .action-steps-grid{{display:flex;flex-direction:column;gap:7px}}
    .action-step{{display:grid;grid-template-columns:28px minmax(0,1fr);gap:10px;align-items:start;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:10px;background:rgba(255,255,255,.025);min-width:0}}
    .action-step-num{{font-family:var(--serif);font-size:1rem;color:var(--gold);text-align:center;opacity:.9;line-height:1.2}}
    .action-step-copy{{min-width:0}}
    .action-step-actions{{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}}
    .action-step.done{{opacity:.62;border-color:rgba(42,157,143,.5)}}
    .action-step.ricies{{opacity:.52;border-color:rgba(180,70,55,.5)}}
    .action-step-kicker{{font-size:.5rem;color:var(--gold);letter-spacing:.12em;text-transform:uppercase;margin-bottom:3px}}
    .action-step-title{{font-family:var(--serif);font-size:.9rem;color:var(--text);line-height:1.25}}
    .action-step-ask{{font-size:.72rem;color:var(--muted);line-height:1.35;margin-top:2px}}
    .action-step-empty{{font-size:.76rem;color:var(--muted);line-height:1.45;border:1px dashed rgba(255,255,255,.14);border-radius:12px;padding:12px;background:rgba(255,255,255,.018)}}
    @media(max-width:760px){{.action-step{{grid-template-columns:22px 1fr}}}}


    .weather-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;box-sizing:border-box}}
    .weather-item{{text-align:center;padding:12px 8px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);box-sizing:border-box;display:flex;flex-direction:column;align-items:center;justify-content:center}}
    .weather-item .city{{font-size:.845rem;color:var(--dim);margin-bottom:5px;letter-spacing:.04em}}
    .weather-item .temp{{font-size:1.25rem;font-weight:500;color:var(--gold);font-family:var(--serif)}}
    .weather-item .condition{{font-size:.62rem;color:var(--dim);margin-top:3px;line-height:1.3}}

    .thai-news-compact{{margin-top:14px;padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r)}}
    .thai-news-header{{font-size:.58rem;color:var(--gold);text-transform:uppercase;letter-spacing:.16em;margin-bottom:8px;font-weight:600}}
    .thai-news-item{{font-size:.86rem;color:var(--text);padding:8px 0;border-bottom:1px solid var(--border);line-height:1.45}}
    .thai-news-feature{{padding:10px 0}}
    .thai-news-source{{font-size:.55rem;color:var(--gold);letter-spacing:.12em;text-transform:uppercase;margin-bottom:5px;opacity:.85}}
    .thai-news-summary{{font-size:.72rem;color:var(--dim);line-height:1.45;margin-top:5px}}
    .thai-news-verify{{font-size:.56rem;color:var(--mute);line-height:1.35;margin-top:6px;opacity:.7}}
    .thai-news-item:last-child{{border-bottom:none}}

    .star-sign{{padding:2px 0}}
    .star-sign-symbol{{display:none}}
    .star-sign-main{{font-family:var(--serif);font-size:.95rem;color:var(--gold);display:flex;align-items:center;gap:6px;margin-bottom:4px}}
    .star-sign-main::before{{content:attr(data-symbol);font-size:.85rem}}
    .star-sign-range{{display:inline;font-size:.65rem;color:var(--dim);letter-spacing:.08em;text-transform:uppercase;margin-left:4px;vertical-align:middle}}

    .headline{{padding:8px 0;border-bottom:1px solid var(--border)}}
    .headline:last-child{{border-bottom:none}}
    .headline-num{{display:inline-block;width:18px;height:18px;background:var(--gold-dim);color:var(--gold);border-radius:2px;text-align:center;line-height:18px;font-size:.62rem;font-weight:600;margin-right:8px}}
    .headline-text{{font-size:.86rem;color:var(--text)}}

    .portfolio-summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px}}
    .psum-item{{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:12px;text-align:center}}
    .psum-label{{font-size:.58rem;color:var(--dim);text-transform:uppercase;letter-spacing:.12em;margin-bottom:4px}}
    .psum-value{{font-family:var(--serif);font-size:1.35rem;font-weight:400}}

    .expand-btn{{width:100%;background:none;border:1px solid var(--border);color:var(--dim);font-size:.65rem;letter-spacing:.12em;text-transform:uppercase;padding:8px;cursor:pointer;border-radius:var(--r);transition:all .15s;font-family:var(--sans);margin-bottom:10px}}
    .expand-btn:hover{{border-color:var(--gold);color:var(--gold)}}
    .holdings-table-wrap{{display:none}}
    .holdings-table-wrap.open{{display:block}}

    .portfolio-table{{width:100%;border-collapse:collapse;font-size:.78rem}}
    .portfolio-table th{{text-align:left;padding:7px 5px;font-size:.58rem;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.1em;border-bottom:1px solid var(--border)}}
    .portfolio-table td{{padding:7px 5px;border-bottom:1px solid rgba(255,255,255,.025)}}
    .portfolio-table tr:hover{{background:rgba(255,255,255,.015)}}
    .ticker{{font-weight:600;color:var(--gold);font-size:.82rem}}
    .positive{{color:var(--green)}}
    .negative{{color:var(--red)}}
    .fallback-badge{{font-size:.55rem;color:var(--mute);vertical-align:middle;margin-left:3px}}

    .totals-row{{display:flex;justify-content:space-between;margin-top:16px;padding-top:14px;border-top:1px solid var(--border)}}
    .total-item{{text-align:center}}
    .total-label{{font-size:.58rem;color:var(--dim);text-transform:uppercase;letter-spacing:.1em}}
    .total-value{{font-family:var(--serif);font-size:1.4rem;font-weight:400;margin-top:3px}}
    .total-value.cad{{color:var(--green)}}
    .total-value.usd{{color:var(--gold)}}

    .allocation-section{{position:relative;isolation:isolate;display:grid;grid-template-columns:minmax(220px,280px) minmax(0,1fr);align-items:center;gap:clamp(20px,4vw,42px);margin-top:22px;padding:24px;border:1px solid rgba(140,255,0,.15);border-radius:16px;overflow:hidden;background:radial-gradient(circle at 18% 35%,rgba(140,255,0,.09),transparent 38%),radial-gradient(circle at 82% 72%,rgba(0,232,111,.065),transparent 42%),linear-gradient(145deg,rgba(121,247,255,.025),rgba(0,0,0,.2))}}
    .allocation-section::before{{content:'';position:absolute;inset:0;z-index:-1;background:linear-gradient(115deg,transparent 12%,rgba(245,255,90,.055) 42%,transparent 68%);pointer-events:none}}
    .pie-chart{{display:block;width:min(100%,280px);height:auto;aspect-ratio:1;justify-self:center;overflow:visible;flex-shrink:0;filter:drop-shadow(0 18px 28px rgba(0,0,0,.46))}}
    .allocation-aura{{fill:rgba(9,10,14,.76);stroke:rgba(140,255,0,.14);stroke-width:1}}
    .allocation-track{{fill:none;stroke:rgba(255,255,255,.045);stroke-width:52}}
    .allocation-glow{{opacity:.86}}
    .allocation-slice{{stroke-linecap:butt;filter:saturate(1.42) contrast(1.07) brightness(1.1);transition:opacity .2s ease,filter .2s ease}}
    .allocation-slice:hover{{opacity:.94;filter:saturate(1.55) contrast(1.08) brightness(1.18)}}
    .allocation-gloss-layer{{pointer-events:none;mix-blend-mode:screen}}
    .allocation-gloss{{opacity:.34}}
    .allocation-core{{fill:url(#allocation-core);stroke:rgba(121,247,255,.17);stroke-width:1.25}}
    .allocation-core-kicker,.allocation-core-label{{font-family:var(--sans);fill:#bdff94;font-size:9px;font-weight:600;letter-spacing:3px;filter:drop-shadow(0 0 5px rgba(140,255,0,.25))}}
    .allocation-copy{{min-width:0}}
    .allocation-kicker{{margin-bottom:12px;color:var(--gold);font-size:.58rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase}}
    .allocation-legend{{display:grid;grid-template-columns:1fr;gap:8px}}
    .legend-item{{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:8px;min-width:0;padding:9px 10px;border:1px solid rgba(140,255,0,.075);border-radius:9px;background:rgba(4,4,7,.34);font-size:.7rem}}
    .legend-dot{{width:11px;height:11px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,var(--swatch-start),var(--swatch-end));box-shadow:inset 0 0 4px rgba(255,255,255,.8),0 0 8px var(--swatch-start),0 0 18px color-mix(in srgb,var(--swatch-end) 72%,transparent)}}
    .legend-name{{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text)}}
    .legend-pct{{color:#d8d3e2;margin-left:auto;font-variant-numeric:tabular-nums;font-weight:500}}
    .allocation-source{{display:flex;align-items:center;gap:7px;margin-top:13px;color:var(--mute);font-size:.55rem;letter-spacing:.06em}}
    .allocation-source span{{width:6px;height:6px;border-radius:50%;background:#5ff1b8;box-shadow:0 0 10px rgba(95,241,184,.78)}}
    .allocation-source--offline{{color:var(--red)}}
    .allocation-unavailable{{grid-column:1/-1;padding:34px 18px;text-align:center;color:var(--dim);font-size:.72rem}}

    .catalyst-item{{padding:8px 0;border-bottom:1px solid var(--border);display:flex;align-items:baseline;flex-wrap:wrap;gap:2px;line-height:1.4}}
    .catalyst-item:last-child{{border-bottom:none}}
    .catalyst-ticker{{font-weight:600;color:var(--gold);font-size:.85rem;white-space:nowrap}}
    .catalyst-sep{{color:var(--dim);font-size:.8rem}}
    .catalyst-badge{{color:var(--gold);font-size:.75rem;opacity:.8;white-space:nowrap}}
    .catalyst-headline{{font-size:.8rem;color:var(--text);line-height:1.4}}
    .radar-label{{font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);opacity:.7;margin-bottom:6px;margin-top:2px}}
    .radar-item{{display:flex;align-items:baseline;flex-wrap:wrap;gap:2px;padding:5px 0;border-bottom:1px solid var(--border);line-height:1.4}}
    .radar-item:last-child{{border-bottom:none}}
    .radar-ticker{{font-weight:600;color:var(--gold);font-size:.8rem;white-space:nowrap;min-width:42px}}
    .radar-sep{{color:var(--dim);font-size:.75rem;white-space:nowrap}}
    .radar-idea{{font-size:.78rem;color:var(--text);line-height:1.4}}
    .radar-source{{font-size:.68rem;color:var(--gold);opacity:.65;font-style:italic;white-space:nowrap}}
    .weekly-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr));gap:10px;margin-top:8px}}
    .weekly-idea{{border:1px solid rgba(181,150,98,.2);border-radius:12px;padding:12px 14px;background:linear-gradient(135deg,rgba(181,150,98,.055),rgba(255,255,255,.018))}}
    .weekly-idea-top{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:5px}}
    .weekly-idea-top a{{color:var(--gold);font-weight:700;text-decoration:none}}
    .weekly-action{{font-size:.58rem;font-weight:800;letter-spacing:.1em;color:#07110b;background:var(--green);padding:3px 6px;border-radius:5px}}
    .weekly-type{{font-size:.58rem;letter-spacing:.1em;color:var(--dim)}}
    .weekly-snapshot{{font-size:.68rem;color:var(--blue);margin-bottom:8px}}
    .weekly-points{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}}
    .weekly-thesis,.weekly-risk,.weekly-trigger{{font-size:.7rem;line-height:1.35;padding:8px 9px;border-radius:8px;background:rgba(0,0,0,.18);min-width:0}}
    .weekly-points b{{display:block;font-size:.5rem;letter-spacing:.13em;text-transform:uppercase;margin-bottom:3px;color:var(--gold)}}
    .weekly-points span{{display:block;color:var(--text)}}
    .weekly-risk span{{color:#f3b0b0}} .weekly-trigger span{{color:var(--dim)}}
    .weekly-meta,.weekly-empty{{font-size:.68rem;color:var(--mute);line-height:1.5}}
    .catalyst-source{{font-size:.62rem;color:var(--dim);margin-top:2px}}
    .no-news{{color:var(--dim);font-style:italic;font-size:.78rem;margin-left:6px}}

    .commodities-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}}
    .commodity-item{{background:var(--bg);padding:12px;border:1px solid var(--border);border-radius:var(--r);text-align:center}}
    .commodity-name{{font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:5px;font-weight:600}}
    .commodity-price{{font-family:var(--serif);font-size:1.2rem;font-weight:400;margin-bottom:2px}}
    .commodity-unit{{font-size:.6rem;color:var(--dim)}}
    .commodity-change{{font-size:.72rem;margin-top:3px}}
    .c-gold{{color:#b59662}}.c-silver{{color:#b8b8b8}}.c-copper{{color:#b87333}}
    .c-oil{{color:#8b7355}}.c-gas{{color:#72a8c7}}.c-uranium{{color:#7fc87f}}

    .crypto-grid{{display:grid;grid-template-columns:repeat(8,1fr);gap:7px}}
    .crypto-item{{background:var(--bg);padding:9px 6px;border:1px solid var(--border);border-radius:var(--r);text-align:center}}
    .crypto-symbol{{font-size:.58rem;font-weight:600;text-transform:uppercase;letter-spacing:.1em;margin-bottom:3px}}
    .crypto-price{{font-family:var(--serif);font-size:.95rem;font-weight:400;margin-bottom:2px}}
    .crypto-change{{font-size:.68rem;margin-top:2px}}

    .radar-item{{display:flex;align-items:flex-start;gap:10px;padding:9px 0;border-bottom:1px solid var(--border)}}
    .radar-item:last-child{{border-bottom:none}}
    .radar-ticker{{font-size:.7rem;color:var(--gold);margin-left:5px}}
    .fresh{{background:rgba(61,158,106,.12);color:#3d9e6a;border:1px solid rgba(61,158,106,.2)}}
    .stale{{background:rgba(106,103,122,.1);color:var(--dim);border:1px solid var(--border)}}

    .currently-mini{{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:2px 0}}
    .currently-title{{font-family:var(--serif);font-size:1rem;color:var(--text)}}
    .currently-author{{font-size:.68rem;color:var(--blue);white-space:nowrap}}

    .podcast-card{{padding:14px 16px}}
    .podcast-mini{{display:flex;align-items:stretch;gap:12px;text-decoration:none;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:8px;transition:border-color .15s}}
    .podcast-mini:hover{{border-color:var(--gold)}}
    .podcast-mini img{{width:20%;min-width:128px;aspect-ratio:16/9;object-fit:cover;border-radius:4px;filter:saturate(.85) brightness(.9);flex-shrink:0}}
    .podcast-mini span{{display:flex;flex-direction:column;justify-content:center;gap:4px;min-width:0}}
    .podcast-mini strong{{font-family:var(--serif);font-size:1.18rem;font-weight:500;color:var(--text);line-height:1.12}}
    .podcast-mini em{{font-style:normal;font-size:.64rem;color:var(--gold);letter-spacing:.12em;text-transform:uppercase}}
    .podcast-mini-copy{{font-size:.72rem;color:var(--dim);line-height:1.45;margin:8px 2px 0}}
    .latest-novaire-card{{padding:15px 16px}}
    .latest-novaire-stack{{display:grid;gap:7px}}
    .latest-novaire-item{{border:1px solid var(--border);border-radius:9px;background:linear-gradient(135deg,rgba(181,150,98,.05),rgba(255,255,255,.015));overflow:hidden}}
    .latest-novaire-item summary{{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:62px;padding:10px 13px;cursor:pointer;list-style:none}}
    .latest-novaire-item summary::-webkit-details-marker{{display:none}}
    .latest-novaire-item[open] summary{{border-bottom:1px solid var(--border)}}
    .latest-novaire-copy{{display:flex;min-width:0;flex-direction:column}}
    .latest-novaire-kicker{{font-size:.49rem;color:var(--gold);letter-spacing:.14em;margin-bottom:3px}}
    .latest-novaire-copy strong{{font-family:var(--serif);font-size:.94rem;font-weight:500;color:var(--text);line-height:1.14;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .latest-novaire-chevron{{flex:none;color:var(--gold);font-size:1rem;transition:transform .15s}}
    .latest-novaire-item[open] .latest-novaire-chevron{{transform:rotate(180deg)}}
    .latest-novaire-detail{{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 13px 11px;font-size:.57rem;color:var(--dim)}}
    .latest-novaire-detail>a{{flex:none;color:var(--gold);text-decoration:none;letter-spacing:.07em;text-transform:uppercase}}
    .latest-novaire-metrics{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
    .latest-novaire-metrics b{{color:var(--text);font-weight:600}}
    .metric-winner{{padding:2px 6px;border:1px solid rgba(42,157,143,.36);border-radius:999px;color:var(--green);text-transform:uppercase;letter-spacing:.08em;font-size:.49rem}}
    .latest-novaire-ink-detail{{color:var(--dim)}}

    .sat-word-box{{padding:14px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r)}}
    .sat-word{{font-family:var(--serif);font-size:1.2rem;color:var(--gold);font-weight:500;margin-bottom:6px}}
    .sat-def{{font-size:.82rem;color:var(--text);margin-bottom:10px;font-style:italic}}
    .sat-sentence{{font-size:.78rem;color:var(--dim);line-height:1.5;border-left:2px solid var(--gold-mid);padding-left:10px}}
    .sat-source{{font-size:.68rem;color:var(--mute);margin-top:8px;text-align:right}}

    .fx-row{{display:flex;flex-wrap:wrap;justify-content:center;gap:6px;margin-top:4px}}
    .fx-chip{{text-align:center;min-width:0;flex:1 1 0;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:6px 4px}}
    .fx-chip .fx-ccy{{font-size:.54rem;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);white-space:nowrap}}
    .fx-chip .fx-rate{{display:block;font-family:'Courier New',monospace;font-size:.78rem;font-weight:600;color:var(--gold);margin-top:1px}}

    .compact-feed-card{{padding:14px 16px}}
    .compact-feed-card .card-title{{margin-bottom:8px}}
    .feed-controls{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px}}
    .feed-refresh{{font-size:.55rem;letter-spacing:.08em;cursor:pointer;background:none;border:1px solid var(--border);color:var(--dim);padding:3px 7px;border-radius:var(--r);font-family:var(--sans)}}
    .feed-refresh:hover{{border-color:var(--gold);color:var(--gold)}}
    .feed-refresh[disabled]{{opacity:.45;cursor:wait}}
    .feed-status{{font-size:.58rem;color:var(--dim);font-style:italic}}
    .feed-item{{display:grid;grid-template-columns:minmax(84px,auto) minmax(0,1fr) auto;align-items:center;gap:9px;padding:7px 0;border-bottom:1px solid var(--border);min-height:24px}}
    .feed-item:last-child{{border-bottom:none}}
    .feed-handle{{font-size:.65rem;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .feed-text{{font-size:.75rem;color:var(--text);line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}}
    .feed-link{{font-size:.6rem;color:var(--gold);text-decoration:none;opacity:.72;white-space:nowrap;text-transform:uppercase;letter-spacing:.05em}}
    .feed-link:hover{{opacity:1}}
    .feed-empty{{text-align:center;padding:12px;color:var(--dim);font-size:.75rem}}
    .feed-loading{{text-align:center;padding:12px;color:var(--dim);font-size:.75rem}}
    .feed-loading::after{{content:'...';animation:dots 1.2s steps(3,end) infinite}}
    @keyframes dots{{0%,100%{{content:'.'}}33%{{content:'..'}}66%{{content:'...'}}}}
    .feed-filter{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:5px}}
    .feed-tag{{font-size:.55rem;padding:2px 6px;border:1px solid var(--border);color:var(--dim);cursor:pointer;background:none;letter-spacing:.04em;border-radius:var(--r);font-family:var(--sans)}}
    .feed-tag.active,.feed-tag:hover{{border-color:var(--gold);color:var(--gold);background:var(--gold-dim)}}

    .fed-card,.market-card{{display:block;text-align:left;padding:0;overflow:hidden}}
    .market-card .market-clock{{border-bottom:0}}
    .market-clock{{min-width:0;display:grid;grid-template-columns:auto minmax(0,1fr);grid-template-areas:"primary futures" "calendar calendar";align-items:center;gap:8px 20px;border-bottom:1px solid var(--border);padding:12px 24px}}
    .market-primary{{grid-area:primary;display:flex;align-items:baseline;gap:12px;min-width:0}}
    .market-label{{font-size:.64rem;color:var(--gold);text-transform:uppercase;letter-spacing:.12em;white-space:nowrap}}
    .wall-time{{display:block;font-family:var(--serif);font-size:1.248rem;line-height:1;font-weight:400;color:var(--text);font-variant-numeric:tabular-nums;white-space:nowrap}}
    .market-futures{{grid-area:futures;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;min-width:0}}
    .market-future{{display:grid;grid-template-columns:1fr auto;gap:0 7px;align-items:baseline;padding-left:10px;border-left:1px solid var(--border);min-width:0}}
    .market-future span{{grid-column:1/-1;font-size:.49rem;color:var(--gold);letter-spacing:.1em;white-space:nowrap}}
    .market-future b{{font-family:var(--serif);font-size:.92rem;color:var(--text);font-weight:500;white-space:nowrap}}
    .market-future em{{font-size:.7332rem;font-style:normal;text-align:right;white-space:nowrap}}
    .market-future small{{
      grid-column:1/-1;
      display:grid;
      grid-template-columns:auto 1fr auto;
      gap:5px;
      align-items:baseline;
      margin-top:2px;
      color:var(--mute);
      font-size:.41rem;
      white-space:nowrap;
    }}
    .market-future small i{{font-style:normal;text-transform:uppercase;letter-spacing:.06em}}
    .market-future small strong{{font-size:.45rem;font-weight:500;color:var(--dim)}}
    .market-future small u{{font-size:.6396rem;text-decoration:none;text-align:right}}
    .market-calendar{{grid-area:calendar;font-size:.48rem;line-height:1.3;color:var(--mute);white-space:nowrap;text-align:right}}
    .market-calendar span{{padding:0 5px;color:var(--border)}}
    .fed-compact{{min-width:0;display:grid;grid-template-rows:auto 1fr;align-content:center;padding:17px 0 20px}}
    .fed-title{{font-size:.62rem;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);font-weight:600;margin:0 24px 12px}}
    #fed-signal-card>summary .fed-title{{margin:0;flex:1}}
    .fed-summary-rate{{font-size:.72rem;font-weight:650;color:var(--text);white-space:nowrap}}
    .fed-summary-sentiment{{font-size:.62rem;font-weight:600;color:var(--green);white-space:nowrap}}
    .fed-stats{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;align-items:stretch}}
    .fed-stat{{min-width:0;padding:0 24px;border-left:1px solid var(--border);display:flex;flex-direction:column;justify-content:center}}
    .fed-stat:first-child{{border-left:0}}
    .fed-stat span{{display:block;font-size:.53rem;color:var(--dim);text-transform:uppercase;letter-spacing:.1em;margin-bottom:7px}}
    .fed-stat b{{display:block;font-family:var(--serif);font-size:1rem;line-height:1.2;font-weight:400;color:var(--text);white-space:nowrap}}
    .fed-stat .fed-rate{{color:var(--gold)}}
    .fed-stat em{{display:block;font-style:normal;font-size:.53rem;color:var(--mute);margin-top:5px}}
    .fed-prob b{{display:flex;gap:18px}}
    .fed-prob i{{font-style:normal}}
    .fed-prob i:first-child{{color:var(--green)}}
    .fed-prob i:last-child{{color:var(--blue)}}
    @media(max-width:620px){{.market-clock{{grid-template-columns:1fr;grid-template-areas:"primary" "futures" "calendar";align-items:flex-start;padding:12px 14px}}.market-futures{{width:100%}}.market-future{{grid-template-columns:1fr;text-align:center;padding:0 8px}}.market-future:first-child{{border-left:none;padding-left:0}}.market-future span,.market-future b,.market-future em{{grid-column:1}}.market-future em{{text-align:center}}.market-future small{{grid-template-columns:auto auto;justify-content:center}}.market-future small u{{grid-column:1/-1;text-align:center}}.market-calendar{{white-space:normal;text-align:center;line-height:1.45;width:100%}}.fed-title{{margin-left:14px}}.fed-stat{{padding:0 14px}}}}
    @media(max-width:520px){{.fed-stats{{grid-template-columns:1fr 1.6fr}}.fed-prob{{grid-column:1/-1;border-left:0;padding:12px 14px 0;margin-top:11px;border-top:1px solid var(--border)}}}}
    @media(max-width:400px){{.market-clock{{gap:14px;padding-top:16px;padding-bottom:16px}}.market-primary{{gap:14px}}.market-futures{{grid-template-columns:1fr;gap:10px}}.market-future{{grid-template-columns:1fr auto;column-gap:12px;border-left:none;border-top:1px solid var(--border);padding:10px 0 2px;text-align:left}}.market-future span{{grid-column:1/-1;text-align:left}}.market-future b{{grid-column:1;text-align:left}}.market-future em{{grid-column:2;text-align:right}}.market-future small{{grid-template-columns:auto 1fr auto;justify-content:stretch;margin-top:5px}}.market-future small u{{grid-column:auto;text-align:right}}.market-calendar{{margin-top:2px;padding-top:2px}}.wall-time{{font-size:1.176rem}}}}

    .eco-table{{width:100%;border-collapse:collapse;font-size:.76rem}}
    .eco-table th{{text-align:left;padding:5px 6px;font-size:.58rem;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.1em;border-bottom:1px solid var(--border)}}
    .eco-table td{{padding:5px 6px;border-bottom:1px solid rgba(255,255,255,.025)}}
    .eco-table tr:last-child td{{border-bottom:none}}
    .eco-table tr:hover{{background:rgba(255,255,255,.015)}}
    .eco-flag{{font-size:.9rem}}
    .eco-country{{font-weight:600;color:var(--text)}}
    .eco-gdp{{color:var(--gold);font-family:var(--serif);font-size:.88rem}}
    .eco-infl{{font-size:.72rem}}

    .footer{{text-align:center;padding:40px 0 24px;border-top:1px solid var(--border);margin-top:28px}}
    .footer-logo{{font-family:var(--serif);font-size:1.6363636rem;font-weight:300;letter-spacing:.18em;text-transform:uppercase;color:var(--text);margin-bottom:4px}}
    .footer-logo span{{color:var(--gold);font-style:italic}}
    .footer-tagline{{font-size:.62rem;color:var(--dim);letter-spacing:.14em;text-transform:uppercase}}
    .footer-sub{{font-size:.58rem;color:var(--mute);margin-top:6px}}
    .footer-powered{{font-size:.62rem;color:var(--dim);margin-top:14px;letter-spacing:.05em}}
    .footer-powered a{{color:var(--gold);text-decoration:none;opacity:.82;transition:opacity .15s}}
    .footer-powered a:hover,.footer-powered a:focus-visible{{opacity:1;text-decoration:underline;text-underline-offset:3px}}
    .eco-links{{display:flex;justify-content:center;gap:20px;margin-top:12px;flex-wrap:wrap}}
    .eco-link{{font-size:.7rem;color:var(--gold);text-decoration:none;opacity:.7;transition:opacity .15s;letter-spacing:.06em}}
    .eco-link:hover{{opacity:1}}

    @media(min-width:761px){{
      html{{font-size:121%}}
      body{{font-size:19.965px;padding:35px 18px}}
      .container{{max-width:792px}}
      .card{{padding:22px;margin-bottom:15px}}
      .podcast-mini img{{min-width:141px}}
      .feed-avatar{{width:29px;height:29px}}
      .commodity-item,.weather-item,.rec-item,.psum-item{{padding:13px}}
      .crypto-item{{padding:10px 7px}}
    }}

    @media(max-width:600px){{
      .weather-grid{{grid-template-columns:repeat(2,1fr)}}
      .commodities-grid{{grid-template-columns:repeat(3,1fr)}}
      .crypto-grid{{grid-template-columns:repeat(4,1fr)}}
      .fx-row{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:8px}}
      .fx-chip{{padding:9px 4px}}
      .fx-chip .fx-ccy{{font-size:.5rem}}
      .fx-chip .fx-rate{{font-size:.7rem;margin-top:3px}}
      .allocation-section{{grid-template-columns:1fr;gap:14px;padding:18px}}
      .pie-chart{{width:min(100%,250px)}}
      .allocation-kicker{{text-align:center}}
      .allocation-legend{{grid-template-columns:1fr}}
      .rec-grid{{grid-template-columns:1fr}}
      .portfolio-summary{{grid-template-columns:repeat(3,1fr)}}
      .totals-row{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px 10px}}
      .totals-row .total-item{{text-align:left;min-width:0}}
      .totals-row .total-value{{font-size:1.05rem;white-space:nowrap}}
      .weekly-grid{{grid-template-columns:1fr}}
      .weekly-points{{grid-template-columns:1fr}}
    }}
  </style>
</head>
<body>
<div class="container">

  <!-- HEADER BRANDING -->
  <div class="header-brand">
    <div class="footer-logo">Novaire <span>Signal</span> <a href="/portfolio" class="signal-bolt" title="Portfolio" aria-label="Portfolio">{SIGNAL_BOLT_SVG}</a></div>
    <div style="font-family:var(--serif);font-size:.9rem;font-style:italic;color:var(--gold);opacity:0.7;letter-spacing:.04em;margin-top:2px;">Deciphering through the noise.</div>
  </div>

  <!-- DATE / GENERATION LINE -->
  <div class="dateline">
    <div class="date">{date_str}</div>
    <!-- removed generated timestamp -->
  </div>

  <!-- PERSONAL COUNTDOWNS -->
  <details class="card signal-accordion countdown-strip daily-signal-card" id="world-tour-card" data-edition="{daily_edition}" open>
    <summary><span class="card-title">🧭 Flâneur Life</span><span class="accordion-score" id="world-tour-viewed">Today</span></summary>
    <div class="signal-accordion-body"><div class="countdown-strip-grid">
      <div class="countdown-item">
        <div class="countdown-label">Tbilisi 🍷</div>
        <div class="countdown-days">{trip_countdown_text}</div>
        <div class="countdown-date">Sep 30 · Georgia</div>
      </div>
      <div class="countdown-item">
        <div class="countdown-label">EDC PHUKET 🎡</div>
        <div class="countdown-days">{edc_countdown_text}</div>
        <div class="countdown-date">Dec 18</div>
      </div>
      <div class="countdown-item">
        <div class="countdown-label">MAN ON THE RISE 🏝️</div>
        <div class="countdown-days">{retreat_countdown_text}</div>
        <div class="countdown-date">Jan 19</div>
      </div>
      <div class="countdown-item">
        <div class="countdown-label">SOVIET SIDE QUEST 🚂</div>
        <div class="countdown-days">{trans_siberian_countdown_text}</div>
        <div class="countdown-date">Sep 2027</div>
      </div>
    </div></div>
  </details>

  <!-- DAILY MEDITATION + QUOTES (client-side localStorage dedup) -->
  <details class="card signal-accordion daily-signal-card" id="quotes-card" data-edition="{daily_edition}" open>
    <summary><span class="card-title">📜 Daily Meditation</span><span class="accordion-score" id="meditation-card-viewed">Today</span></summary>
    <div class="signal-accordion-body">
    <details id="meditation-daily" class="meditation" open>
      <summary>
        <div class="meditation-summary-copy"><div class="meditation-title" id="med-title"></div><div class="meditation-meta" id="med-meta"></div></div>
        <span class="accordion-score" id="meditation-viewed">Today</span>
      </summary>
      <div class="meditation-body">
        <div class="meditation-excerpt" id="med-excerpt"></div>
        <button class="meditation-collapse" id="med-collapse" type="button">Collapse meditation ↑</button>
      </div>
    </details>
    <details class="signal-accordion daily-signal-block" id="quotes-daily" data-edition="{daily_edition}" open>
      <summary><span class="card-title">Quotes</span><span class="accordion-score" id="quotes-viewed">Today</span></summary>
      <div class="signal-accordion-body daily-signal-body"><div id="quote-daily" class="quote">
        <div class="quote-type" id="qt-type"></div>
        <div class="quote-text" id="qt-text"></div>
        <div class="quote-author" id="qt-auth"></div>
      </div></div>
    </details>
    </div>
  </details>

  <!-- WEATHER + THAILAND NEWS -->
  <details class="card signal-accordion daily-signal-card" id="weather-card" data-edition="{daily_edition}" open>
    <summary><span class="card-title">🌤 Weather</span><span class="accordion-score" id="weather-viewed">Today</span></summary>
    <div class="signal-accordion-body"><div class="weather-grid">{weather_html}</div></div>
  </details>

  <!-- WALL STREET TIME + LIVE MARKET PULSE -->
{market_html}

  <!-- COMMODITIES -->
  <div class="card">
    <div class="card-title">🪙 Commodities</div>
    <div class="commodities-grid">
      {comm_html}
    </div>
  </div>

  <!-- CRYPTO — 30% smaller -->
  <div class="card">
    <div class="card-title">🌐 Crypto</div>
    <div class="crypto-grid">
      {crypto_html}
    </div>
  </div>

  <!-- FX RATES — below crypto -->
  <div class="card">
    <div class="card-title">💱 FX Rates — 1 USD =</div>
    <div class="fx-row">
      {fx_rates_html}
    </div>
  </div>

<!-- ZEROHEDGE -->
  <div class="card compact-feed-card">
    <div class="card-title">📰 ZeroHedge — Top Headlines</div>
    <div class="feed-controls">
      <div class="feed-status" id="news-status">Live pool · latest three</div>
      <button class="feed-refresh" id="news-refresh" onclick="loadFreshNews(true)" title="Show the next three ranked X signals and the next three live ZeroHedge articles">↻ Refresh both</button>
    </div>
    <div id="zerohedge-feed">{zh_html}</div>
  </div>

  <!-- SIGNAL FEED -->
  <div class="card compact-feed-card">
    <div class="card-title">📡 Signal Feed — Top 3 by Engagement</div>
    <div class="feed-controls">
      <div class="feed-status" id="feed-status">Loading…</div>
    </div>
    <div id="signal-feed">
      <div class="feed-loading">Fetching signals</div>
    </div>
  </div>

  <script>
  (function() {{
    let signalPool = [];
    let zhPool = {json.dumps(zh_news)};
    let signalCursor = 0;
    let zhCursor = 0;

    function timeAgo(iso) {{
      const d = new Date(iso);
      const diff = (Date.now() - d.getTime()) / 1000;
      if (diff < 60) return Math.floor(diff) + 's ago';
      if (diff < 3600) return Math.floor(diff/60) + 'm ago';
      if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
      return Math.floor(diff/86400) + 'd ago';
    }}

    function fmtNum(n) {{
      if (!n) return '0';
      if (n >= 1000) return (n/1000).toFixed(1) + 'k';
      return String(n);
    }}

    function escHtml(s) {{
      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }}

    function sortBySlot(posts) {{
      return [...posts].sort((a, b) => (a.slot_order || 99) - (b.slot_order || 99));
    }}

    function nextBatch(pool, cursor, size) {{
      if (!pool.length) return {{ items: [], cursor: 0 }};
      const items = [];
      for (let i = 0; i < Math.min(size, pool.length); i++) items.push(pool[(cursor + i) % pool.length]);
      return {{ items, cursor: (cursor + items.length) % pool.length }};
    }}

    function renderFeed(posts) {{
      const container = document.getElementById('signal-feed');
      if (!posts.length) {{
        container.innerHTML = '<div class="feed-empty">No recent posts found. Try refreshing.</div>';
        return;
      }}
      container.innerHTML = posts.map(p => `
        <div class="feed-item">
          <span class="feed-handle">@${{escHtml(p.handle)}}</span>
          <span class="feed-text" title="${{escHtml(p.text)}}">${{escHtml(p.text)}}</span>
          <a class="feed-link" href="${{escHtml(p.url)}}" target="_blank" rel="noopener">View on X →</a>
        </div>
      `).join('');
    }}

    function renderZeroHedge(items) {{
      const container = document.getElementById('zerohedge-feed');
      container.innerHTML = items.map((item, index) => `
        <div class="headline">
          <span class="headline-num">${{index + 1}}</span>
          <a href="${{escHtml(item.url)}}" class="headline-text" style="text-decoration:none;color:var(--text)" target="_blank" rel="noopener">${{escHtml(item.title)}}</a>
        </div>
      `).join('');
    }}

    async function loadFreshNews(force) {{
      const status = document.getElementById('feed-status');
      const newsStatus = document.getElementById('news-status');
      const button = document.getElementById('news-refresh');
      button.disabled = true;
      status.textContent = force ? 'Finding next three signals…' : 'Loading ranked signal pool…';
      newsStatus.textContent = force ? 'Finding next three articles…' : 'Loading live article pool…';
      try {{
        const [signalResponse, zhResponse] = await Promise.all([
          fetch('/feed.json?_=' + Date.now(), {{ cache: 'no-store' }}),
          fetch('/api/zerohedge?_=' + Date.now(), {{ cache: 'no-store' }})
        ]);
        if (!signalResponse.ok) throw new Error('Signal HTTP ' + signalResponse.status);
        const signalJson = await signalResponse.json();
        if (!signalJson.ok || !signalJson.posts?.length) throw new Error(signalJson.error || 'No ranked signals');
        signalPool = sortBySlot(signalJson.posts);
        if (zhResponse.ok) {{
          const zhJson = await zhResponse.json();
          if (zhJson.ok && zhJson.articles?.length) zhPool = zhJson.articles;
        }}

        const signalBatch = nextBatch(signalPool, signalCursor, 3);
        const zhBatch = nextBatch(zhPool, zhCursor, 3);
        signalCursor = signalBatch.cursor;
        zhCursor = zhBatch.cursor;
        renderFeed(signalBatch.items);
        renderZeroHedge(zhBatch.items);

        const fetchedAt = signalJson.fetchedAt ? new Date(signalJson.fetchedAt) : new Date();
        const ageMin = Math.floor((Date.now() - fetchedAt.getTime()) / 60000);
        const ageStr = ageMin < 2 ? 'just now' : ageMin < 60 ? ageMin + 'm ago' : Math.floor(ageMin/60) + 'h ago';
        status.textContent = '3 of ' + signalPool.length + ' ranked signals · updated ' + ageStr;
        newsStatus.textContent = '3 of ' + zhPool.length + ' live articles';
      }} catch(err) {{
        status.textContent = 'Refresh failed · tap again';
        newsStatus.textContent = 'Keeping current headlines';
      }} finally {{
        button.disabled = false;
      }}
    }}
    window.loadFreshNews = loadFreshNews;
    document.readyState === 'loading'
      ? document.addEventListener('DOMContentLoaded', () => loadFreshNews(false))
      : loadFreshNews(false);
  }})();
  </script>

  <!-- PORTFOLIO removed — now at /portfolio -->

  <!-- WEEKLY ASYMMETRIC IDEAS -->
  <details class="card signal-accordion" id="weekly-asymmetric-ideas" data-edition="{weekly_as_of}" {'open' if open_early_week(now) else ''}>
    <summary><span class="card-title"><span class="section-bolt" aria-hidden="true">&#x26A1;&#xFE0E;</span> Weekly Asymmetry</span><span class="accordion-score">Updated {weekly_as_of}</span></summary>
    <div class="signal-accordion-body"><div class="weekly-meta">{weekly_note}</div><div class="weekly-grid">{weekly_rows}</div></div>
  </details>

  <!-- CATALYSTS — Top 5 only, fresh news highlighted -->
  <details class="card signal-accordion" id="catalysts-card" data-edition="{weekly_edition}" data-fingerprint="{catalyst_fingerprint}" data-items="{catalyst_ids_attr}" {'open' if open_early_week(now) else ''}>
    <summary><span class="card-title">🔍 Catalysts — Top 5 Holdings</span><span class="catalyst-unread" id="catalyst-unread" hidden>✉ New</span><span class="accordion-score">Updated on {weekly_updated_label}</span></summary>
    <div class="signal-accordion-body">{cats_html}</div>
  </details>

  <!-- FED SIGNAL — intentionally lower because it updates less often -->
{fed_html}

  <!-- TRADING BOOKS — placed above slower-changing Currently section -->
  {poly_html}

{alpaca_html}


  <!-- THAILAND NEWS -->
  <details class="card signal-accordion" id="thailand-news-card" data-edition="{daily_edition}" open>
    <summary><span class="card-title">🇹🇭 Thailand</span><span class="accordion-score" id="thailand-news-viewed">Today</span></summary>
    <div class="signal-accordion-body">
      <div class="thai-news-header">Thailand Expat Brief · Visa, Safety, Scandals</div>
      <div class="thai-news-compact" style="margin-top:10px">{bkk_html}</div>
    </div>
  </details>

  <!-- Daily Motivation merged into single Quote of the Day -->

  <!-- TOP 5 ECONOMIES -->
  {eco_html}


  <!-- DAILY KEYSTONE PRIORITY -->
  <div class="card" id="keystone-card">
    <div class="card-title">🎯 Daily Keystone Priority</div>
    <div class="updog-intro">Enter one Keystone priority. Signal will return one concrete move.</div>
    <div class="keystone-row">
      <input id="keystone-input" class="keystone-input" placeholder="One thing that moves health, wealth, product, or relationships...">
      <button id="keystone-done" class="updog-btn updog-approve keystone-done" type="button">Set</button>
    </div>
    <div id="keystone-status" style="margin-top:10px;color:var(--muted);font-size:.82rem">Keystone streak: 0 days.</div>
    <div id="keystone-yesterday" style="margin-top:8px;color:var(--muted);font-size:.82rem"></div>
  </div>


  <!-- DAILY ACTION STEPS -->
  <div class="card updog-action-card" id="updog-action-card">
    <div class="action-step-heading"><div class="card-title">⚔️ Daily Action Step</div><span class="keystone-streak" id="novaire-keystone-streak">🔥 0 days</span></div>
    <div class="action-steps-grid" id="action-steps-grid"></div>
  </div>

{latest_novaire_html}

  <!-- FOOTER BRANDING -->
  <div class="footer">
    <div class="footer-logo">Novaire <span>Signal</span> <a href="/portfolio" class="signal-bolt" title="Portfolio" aria-label="Portfolio">{SIGNAL_BOLT_SVG}</a></div>
    <div class="footer-tagline">Deciphering through the noise.</div>
    <div class="eco-links">
      <a href="https://novaireink.com" class="eco-link">Novaire Ink</a>
      <a href="https://evolution-fund.vercel.app" class="eco-link">Evolution Fund</a>
    </div>
    <div class="footer-powered">Powered by <a href="https://novairecito.com" aria-label="Open Novairecito OS">Novairecito OS</a></div>
    <div class="footer-sub">Live data · Updated every 2 hours · 24/7</div>
  </div>

</div>

<!-- CLIENT-SIDE JS: Quote dedup + Holdings toggle + Recs rotation -->
<script>
// ── Quote arrays (30+ per category) ──
const QUOTES_INVESTING = {QUOTES_JS_INVESTING};
const QUOTES_PSYCHOLOGY = {QUOTES_JS_PSYCHOLOGY};
const MEDITATIONS = {MEDITATIONS_JS};
const TWEET_TEMPLATES = {TWEET_TEMPLATES_JS};

(function rememberWeeklyAccordions() {{
  [
    ['weekly-asymmetric-ideas', 'nv_weekly_ideas_seen']
  ].forEach(function(config) {{
    const details = document.getElementById(config[0]);
    if (!details) return;
    const edition = details.dataset.edition;
    try {{
      if (localStorage.getItem(config[1]) === edition) details.removeAttribute('open');
      details.addEventListener('toggle', function() {{
        if (!details.open) localStorage.setItem(config[1], edition);
      }});
    }} catch (e) {{}}
  }});
}})();

(function rememberEconomiesEdition() {{
  const card = document.getElementById('economies-card');
  if (!card) return;
  const storageKey = 'nv_economies_seen';
  const edition = card.dataset.edition;
  try {{
    if (localStorage.getItem(storageKey) === edition) {{
      card.removeAttribute('open');
      const score = card.querySelector('.accordion-score');
      if (score) score.textContent = 'Viewed';
      return;
    }}
    const observer = new IntersectionObserver(function(entries) {{
      if (!entries.some(entry => entry.isIntersecting && entry.intersectionRatio >= 0.45)) return;
      window.setTimeout(function() {{
        const rect = card.getBoundingClientRect();
        const visible = rect.top < window.innerHeight && rect.bottom > 0;
        if (visible) localStorage.setItem(storageKey, edition);
      }}, 1500);
      observer.disconnect();
    }}, {{threshold:[0.45]}});
    observer.observe(card);
  }} catch (e) {{}}
}})();

function getQuoteForToday(storageKey, quotes) {{
  const today = new Date().toDateString();
  const dayKey  = 'nv_' + storageKey + '_date';
  const idxKey  = 'nv_' + storageKey + '_idx';
  const seenKey = 'nv_' + storageKey + '_seen';
  try {{
    if (localStorage.getItem(dayKey) === today) {{
      return quotes[parseInt(localStorage.getItem(idxKey) || '0') % quotes.length];
    }}
    let seen = [];
    try {{ seen = JSON.parse(localStorage.getItem(seenKey) || '[]'); }} catch(e) {{}}
    let avail = quotes.map((_,i) => i).filter(i => !seen.includes(i));
    if (!avail.length) {{ seen = []; avail = quotes.map((_,i) => i); }}
    const seed = today.split('').reduce((a,c) => (a * 31 + c.charCodeAt(0)) & 0xffffff, 0);
    const idx = avail[seed % avail.length];
    seen.push(idx);
    localStorage.setItem(seenKey, JSON.stringify(seen));
    localStorage.setItem(dayKey, today);
    localStorage.setItem(idxKey, String(idx));
    return quotes[idx];
  }} catch(e) {{
    const seed = new Date().toDateString().split('').reduce((a,c) => (a*31+c.charCodeAt(0))&0xffffff,0);
    return quotes[seed % quotes.length];
  }}
}}

function rememberDailySignalCard(cardId, scoreId, storageKey) {{
  const card = document.getElementById(cardId);
  const score = document.getElementById(scoreId);
  if (!card || !score) return;
  const edition = card.dataset.edition;
  try {{
    if (localStorage.getItem(storageKey) === edition) {{ card.removeAttribute('open'); score.textContent = 'Viewed'; }}
    card.addEventListener('toggle', function() {{
      if (!card.open) {{ localStorage.setItem(storageKey, edition); score.textContent = 'Viewed'; }}
      else if (localStorage.getItem(storageKey) !== edition) score.textContent = 'Today';
    }});
  }} catch (e) {{}}
}}
rememberDailySignalCard('weather-card', 'weather-viewed', 'nv_weather_viewed');
rememberDailySignalCard('world-tour-card','world-tour-viewed','nv_world_tour_viewed');
rememberDailySignalCard('quotes-daily','quotes-viewed','nv_quotes_viewed');

(function rememberCatalystsCard() {{
  const card = document.getElementById('catalysts-card');
  if (!card) return;
  const fingerprint = card.dataset.fingerprint || card.dataset.edition || '';
  const key = 'nv_catalysts_seen';
  try {{
    if (localStorage.getItem(key) === fingerprint) card.removeAttribute('open');
    card.addEventListener('toggle', function() {{
      if (!card.open) localStorage.setItem(key, fingerprint);
    }});
  }} catch (e) {{}}
}})();

(function rememberThailandNews() {{
  const card = document.getElementById('thailand-news-card');
  const thailandScore = document.getElementById('thailand-news-viewed');
  if (!card || !thailandScore) return;
  const edition = card.dataset.edition;
  const key = 'nv_thailand_news_viewed';
  try {{
    if (localStorage.getItem(key) === edition) {{ card.removeAttribute('open'); thailandScore.textContent = 'Viewed'; }}
    card.addEventListener('toggle', function() {{
      if (!card.open) {{ localStorage.setItem(key, edition); thailandScore.textContent = 'Viewed'; }}
      else if (localStorage.getItem(key) !== edition) thailandScore.textContent = 'Today';
    }});
  }} catch (e) {{}}
}})();

(function renderDailyMeditation() {{
  const m = getQuoteForToday("meditation", MEDITATIONS);
  const meditation = document.getElementById('meditation-daily');
  const meditationViewed = document.getElementById('meditation-viewed');
  const meditationCard = document.getElementById('quotes-card');
  const meditationCardViewed = document.getElementById('meditation-card-viewed');
  const quotesDaily = document.getElementById('quotes-daily');
  const meditationCardKey = 'nv_meditation_card_viewed';
  const localDateKey = function() {{
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
  }};
  const today = localDateKey();
  function syncMeditationShell() {{
    let meditationDone = false;
    let quoteDone = false;
    let cardDone = false;
    try {{
      meditationDone = localStorage.getItem('nv_meditation_collapsed_date') === today;
      quoteDone = localStorage.getItem('nv_quotes_viewed') === meditationCard.dataset.edition;
      cardDone = localStorage.getItem(meditationCardKey) === meditationCard.dataset.edition;
    }} catch (e) {{}}
    const consumed = cardDone || (meditationDone && quoteDone);
    if (consumed) meditationCard.removeAttribute('open');
    if (meditationCardViewed) meditationCardViewed.textContent = consumed ? 'Viewed' : 'Today';
  }}
  document.getElementById('med-title').textContent = m.title;
  document.getElementById('med-meta').textContent = m.meta;
  document.getElementById('med-excerpt').textContent = m.excerpt;
  try {{
    const collapsedDate = localStorage.getItem('nv_meditation_collapsed_date');
    meditation.open = collapsedDate !== today;
    if (collapsedDate === today && meditationViewed) meditationViewed.textContent = 'Viewed';
 syncMeditationShell();
    meditation.addEventListener('toggle', function() {{
      if (!meditation.open) {{ localStorage.setItem('nv_meditation_collapsed_date', today); if (meditationViewed) meditationViewed.textContent = 'Viewed'; }}
      else if (localStorage.getItem('nv_meditation_collapsed_date') === today) {{ localStorage.removeItem('nv_meditation_collapsed_date'); if (meditationViewed) meditationViewed.textContent = 'Today'; }}
      syncMeditationShell();
    }});
  }} catch (e) {{ meditation.open = true; }}
  quotesDaily?.addEventListener('toggle', syncMeditationShell);
  meditationCard.addEventListener('toggle', function() {{
    try {{
      if (!meditationCard.open) localStorage.setItem(meditationCardKey, meditationCard.dataset.edition);
    }} catch (e) {{}}
    syncMeditationShell();
  }});
  syncMeditationShell();
  document.getElementById('med-collapse').addEventListener('click', function() {{
    meditation.open = false;
    meditation.scrollIntoView({{behavior:'smooth',block:'nearest'}});
  }});
}})();


(function renderKeystonePriority() {{
  const input = document.getElementById('keystone-input');
  const button = document.getElementById('keystone-done');
  const status = document.getElementById('keystone-status');
  const yesterdayBox = document.getElementById('keystone-yesterday');
  if (!input || !button || !status) return;
  const today = new Date().toDateString();
  const key = 'novaire-keystone-priority';
  const data = JSON.parse(localStorage.getItem(key) || '{{"text":"","streak":0,"lastDone":"","doneDates":[],"history":[]}}');
  data.history = Array.isArray(data.history) ? data.history : [];
  data.doneDates = Array.isArray(data.doneDates) ? data.doneDates : (data.lastDone ? [data.lastDone] : []);
  data.isSet = data.date === today && Boolean(data.isSet || data.text);
  input.value = data.date === today ? (data.text || '') : '';
  function dayBefore(dateStr) {{
    const d = new Date(dateStr);
    d.setDate(d.getDate() - 1);
    return d.toDateString();
  }}
  function calculateStreak(doneDates) {{
    const done = new Set(doneDates || []);
    let cursor = done.has(today) ? today : dayBefore(today);
    let streak = 0;
    while (done.has(cursor)) {{
      streak += 1;
      cursor = dayBefore(cursor);
    }}
    return streak;
  }}
  function updateStatus() {{
    data.streak = calculateStreak(data.doneDates);
    const completeToday = data.doneDates.includes(today);
    status.textContent = completeToday
      ? 'Keystone complete · streak: ' + data.streak + ' day' + (data.streak === 1 ? '' : 's') + '.'
      : (data.isSet ? 'Today’s Keystone is set · complete the action to bank the day.' : 'Keystone streak: ' + data.streak + ' day' + (data.streak === 1 ? '' : 's') + ' · set today’s Keystone.');
    if (yesterdayBox) yesterdayBox.innerHTML = '';
    localStorage.setItem(key, JSON.stringify(data));
  }}
  window.refreshKeystoneStatus = updateStatus;
  input.addEventListener('input', function() {{
    if (data.isSet && input.value.trim() !== String(data.text || '').trim()) {{
      data.isSet = false;
      updateStatus();
      if (typeof renderActionSteps === 'function') renderActionSteps();
    }}
  }});
  button.addEventListener('click', function() {{
    const text = input.value.trim();
    if (!text) {{
      status.textContent = 'Write the Keystone first.';
      return;
    }}
    data.text = text;
    data.date = today;
    data.isSet = true;
    data.doneDates = data.doneDates.filter(d => d !== today);
    const existingToday = data.history.find(item => item && item.date === today);
    if (existingToday) existingToday.text = text;
    else data.history.push({{date: today, text: text}});
    data.history = data.history.slice(-30);
    localStorage.removeItem('novaire-keystone-feedback-' + today);
    localStorage.setItem('novaire-keystone-action-index-' + today, '0');
    updateStatus();
    if (typeof renderActionSteps === 'function') renderActionSteps();
  }});
  input.addEventListener('keydown', function(event) {{
    if (event.key === 'Enter') {{ event.preventDefault(); button.click(); }}
  }});
  updateStatus();
}})();
function escapeActionHtml(value) {{
  return String(value || '').replace(/[&<>"']/g, function(ch) {{
    return ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[ch];
  }});
}}

function renderActionSteps() {{
  const grid = document.getElementById('action-steps-grid');
  const streakEl = document.getElementById('novaire-keystone-streak');
  if (!grid) return;
  const today = new Date().toDateString();
  const dayBefore = value => {{ const d = new Date(value); d.setDate(d.getDate()-1); return d.toDateString(); }};
  function calculateKeystoneStreak(doneDates) {{ const done=new Set(doneDates||[]); let cursor=done.has(today)?today:dayBefore(today),streak=0; while(done.has(cursor)){{streak++;cursor=dayBefore(cursor)}} return streak; }}
  const data=JSON.parse(localStorage.getItem('novaire-keystone-priority')||'{{"text":"","date":"","history":[]}}'); data.doneDates=Array.isArray(data.doneDates)?data.doneDates:[];
  const streak=calculateKeystoneStreak(data.doneDates); if(streakEl)streakEl.textContent='🔥 '+streak+(streak===1?' day complete':' days complete');
  const task=data.date===today&&data.isSet?String(data.text||'').trim():'';
  if(!task){{grid.innerHTML='<div class="action-step-empty">Set today’s Keystone above. One useful move will appear here.</div>';return}}
  const lower=task.toLowerCase();
  const priorityLabel='“'+task+'”';
  function actionFor(){{
    if(/tweet|x\b|post|thread/.test(lower))return {{title:'Draft the actual post',action:'For '+priorityLabel+', write one post-ready draft with a sharp hook and one clear point.'}};
    if(/podcast|clip|record|episode|hook/.test(lower))return {{title:'Record the rough version',action:'For '+priorityLabel+', write the thesis, two hooks and three bullets, then record one rough take.'}};
    if(/relationship|date|romantic|family|friend|conversation/.test(lower))return {{title:'Start the real conversation',action:'Advance '+priorityLabel+' by sending one honest question or message to the person involved.'}};
    if(/retreat|deposit|villa|mastermind|cohort/.test(lower))return {{title:'Move one buyer closer to yes',action:'Advance '+priorityLabel+' with one direct nudge or proof asset that removes buyer uncertainty.'}};
    if(/energy|sleep|battery|health|workout|training|food/.test(lower))return {{title:'Do the body move now',action:'Advance '+priorityLabel+' by logging the key metric and completing one concrete recovery or training action.'}};
    if(/signal|dashboard|novaire|widget|prompt|build|deploy|code|site|app/.test(lower))return {{title:'Ship one verified improvement',action:'For '+priorityLabel+', make the smallest useful change, test it, and capture the live proof.'}};
    if(/fund|portfolio|stock|uranium|ai|trade|market/.test(lower))return {{title:'Turn the thesis into a rule',action:'For '+priorityLabel+', write one price, risk or evidence threshold that forces a clear decision.'}};
    if(/email|reply|message|call|contact|send/.test(lower))return {{title:'Send the consequential message',action:'Advance '+priorityLabel+' by drafting and sending the single communication that unlocks the next move.'}};
    if(/book|read|study|research|learn|review/.test(lower))return {{title:'Extract one decision-grade insight',action:'For '+priorityLabel+', complete one focused 25-minute pass and record the useful conclusion plus source.'}};
    return {{title:'Create the first proof',action:'Advance '+priorityLabel+' in one 25-minute block and finish one visible artifact that did not exist before.'}};
  }}
  const moves=[actionFor(),{{title:'Remove its bottleneck',action:'For '+priorityLabel+', name the single point of friction and spend 15 focused minutes removing it.'}},{{title:'Create visible proof',action:'Finish one artifact that proves measurable progress on '+priorityLabel+'.'}}];
  const indexKey='novaire-keystone-action-index-'+today; let actionIndex=Math.max(0,parseInt(localStorage.getItem(indexKey)||'0',10))%moves.length;
  const feedbackKey='novaire-keystone-feedback-'+today,feedback=JSON.parse(localStorage.getItem(feedbackKey)||'{{}}'),move=moves[actionIndex],state=feedback[actionIndex]?.status||'';
  window.recordKeystoneMove=function(status){{
    if(status==='ricies'){{feedback[actionIndex]={{status:'ricies',task:task,move:move.action,date:today}};localStorage.setItem(feedbackKey,JSON.stringify(feedback));localStorage.setItem(indexKey,String((actionIndex+1)%moves.length));sessionStorage.setItem('novaire-keystone-action-message','Next action generated');renderActionSteps();return}}
    feedback[actionIndex]={{status:status,task:task,move:move.action,date:today}};localStorage.setItem(feedbackKey,JSON.stringify(feedback));
    const learning=JSON.parse(localStorage.getItem('novaire-keystone-learning')||'[]');learning.push(feedback[actionIndex]);localStorage.setItem('novaire-keystone-learning',JSON.stringify(learning.slice(-80)));
    if(status==='completed'){{const keystone=JSON.parse(localStorage.getItem('novaire-keystone-priority')||'{{}}');keystone.doneDates=Array.isArray(keystone.doneDates)?keystone.doneDates:[];if(!keystone.doneDates.includes(today))keystone.doneDates.push(today);keystone.lastDone=today;localStorage.setItem('novaire-keystone-priority',JSON.stringify(keystone))}}
    renderActionSteps();
  }};
  const message=sessionStorage.getItem('novaire-keystone-action-message')||'';sessionStorage.removeItem('novaire-keystone-action-message');const cls=state==='completed'?' done':'';
  grid.innerHTML=`<div class="action-step${{cls}}"><div class="action-step-num">1</div><div class="action-step-copy"><div class="action-step-kicker">From today’s priority</div><div class="action-step-title">${{escapeActionHtml(move.title)}}</div><div class="action-step-ask">${{escapeActionHtml(move.action)}}</div><div class="action-step-actions"><button class="updog-btn updog-approve" type="button" onclick="recordKeystoneMove('completed')" ${{state==='completed'?'disabled':''}}>Completed</button><button class="updog-btn updog-retry" type="button" onclick="recordKeystoneMove('incomplete')">Didn't complete</button><button class="updog-btn updog-retry" type="button" onclick="recordKeystoneMove('ricies')">Ricies</button>${{message?'<span class="updog-status" style="display:inline">'+message+'</span>':''}}</div></div></div>`;
}}
renderActionSteps();

(function renderQuotes() {{
  const day = new Date().getDate();
  const isInv = day % 2 === 0; const q = isInv ? getQuoteForToday("investing", QUOTES_INVESTING) : getQuoteForToday("psychology", QUOTES_PSYCHOLOGY);
  document.getElementById('qt-type').textContent = isInv ? 'Investing' : 'Psychology';
  document.getElementById('qt-text').textContent = '\u201c' + q.text + '\u201d';
  document.getElementById('qt-auth').textContent = '\u2014 ' + q.author;
}})();

(function loadInkReaders() {{
  fetch('https://novaireink.com/api/article-views?slug=when-you-dont-write')
    .then(function(r) {{ return r.ok ? r.json() : Promise.reject(); }})
    .then(function(data) {{
      const el = document.getElementById('ink-unique-views');
      if (el) el.textContent = Number(data.uniqueViews || 0).toLocaleString();
    }}).catch(function() {{}});
}})();

// Recommendations are now server-side rendered (live trending data)
</script>
<script>
// Live world clocks
!function(){{var u=function(){{document.querySelectorAll(".live-clock").forEach(function(e){{var o=parseInt(e.getAttribute("data-tz-offset"))||0,n=new Date,t=n.getTime()+n.getTimezoneOffset()*6e4,l=new Date(t+o*36e5);e.textContent=String(l.getHours()).padStart(2,"0")+":"+String(l.getMinutes()).padStart(2,"0")+":"+String(l.getSeconds()).padStart(2,"0")}})}}; u(); setInterval(u,1e3)}}();

// Live crypto: fresh Binance prices every 15s; CoinGecko quotes/ranks every 60s.
!function(){{
  var coins={{"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT","ADA":"ADAUSDT","TON":"GRAMUSDT","SUI":"SUIUSDT","ZEC":"ZECUSDT","NIGHT":"NIGHTUSDT"}};
  var ids={{"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","cardano":"ADA","the-open-network":"TON","sui":"SUI","zcash":"ZEC","midnight-3":"NIGHT"}};
  function fmt(p){{return p>=1000?"$"+p.toFixed(0).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g,","):p>=1?"$"+p.toFixed(2):"$"+p.toFixed(4)}}
  function updCrypto(){{
    Object.keys(coins).forEach(function(c){{
      fetch("https://api.binance.com/api/v3/ticker/24hr?symbol="+coins[c],{{cache:"no-store"}})
        .then(function(r){{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}})
        .then(function(d){{
          if(!d.closeTime || Date.now()-Number(d.closeTime)>300000)return;
          var el=document.querySelector('[data-crypto-price="'+c+'"]');
          var ce=document.querySelector('[data-crypto-chg="'+c+'"]');
          if(el)el.textContent=fmt(parseFloat(d.lastPrice));
          if(ce){{var ch=parseFloat(d.priceChangePercent);ce.innerHTML='<span class="'+(ch>=0?"positive":"negative")+'">'+(ch>=0?"+":"")+ch.toFixed(2)+"%</span>"}}
        }}).catch(function(){{}})
    }})
  }}
  function reorderCrypto(){{
    fetch("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids="+Object.keys(ids).join(","))
      .then(function(r){{return r.json()}})
      .then(function(rows){{
        var grid=document.querySelector('.crypto-grid');if(!grid)return;
        rows.sort(function(a,b){{return (b.market_cap||0)-(a.market_cap||0)}}).forEach(function(row){{
          var ticker=ids[row.id],el=ticker&&grid.querySelector('[data-coin="'+ticker+'"]');if(!el)return;
          var pe=el.querySelector('[data-crypto-price]'),ce=el.querySelector('[data-crypto-chg]');
          if(pe&&Number.isFinite(Number(row.current_price)))pe.textContent=fmt(Number(row.current_price));
          if(ce&&Number.isFinite(Number(row.price_change_percentage_24h))){{var ch=Number(row.price_change_percentage_24h);ce.innerHTML='<span class="'+(ch>=0?"positive":"negative")+'">'+(ch>=0?"+":"")+ch.toFixed(2)+"%</span>"}}
          grid.appendChild(el)
        }})
      }}).catch(function(){{}})
  }}
  updCrypto();reorderCrypto();setInterval(updCrypto,15000);setInterval(reorderCrypto,60000);
}}();

// Live Investing.com commodities: refresh on open and every minute.
!function(){{
  function fmtCommodity(p){{return p>=1000?'$'+p.toLocaleString('en-US',{{maximumFractionDigits:2}}):p>=10?'$'+p.toFixed(2):'$'+p.toFixed(4)}}
  function refreshCommodities(){{
    fetch('/api/commodities?_='+Date.now(),{{cache:'no-store'}}).then(function(r){{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}}).then(function(data){{
      (data.quotes||[]).forEach(function(q){{
        var pe=document.querySelector('[data-comm-price="'+q.symbol+'"]'),ce=document.querySelector('[data-comm-chg="'+q.symbol+'"]');
        if(pe&&Number.isFinite(Number(q.price)))pe.textContent=fmtCommodity(Number(q.price));
        if(ce&&Number.isFinite(Number(q.change))){{var ch=Number(q.change);ce.innerHTML='<span class="'+(ch>=0?'positive':'negative')+'">'+(ch>=0?'+':'')+ch.toFixed(2)+'%</span>'}}
      }})
    }}).catch(function(){{}})
  }}
  refreshCommodities();setInterval(refreshCommodities,60000);
}}();

// Live USD FX rates: refresh on page load and every minute.
!function(){{
  function refreshFx(){{
    fetch('/api/fx-rates?_='+Date.now(),{{cache:'no-store'}}).then(function(r){{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}}).then(function(data){{
      Object.keys(data.rates||{{}}).forEach(function(ccy){{
        var el=document.querySelector('[data-fx-rate="'+ccy+'"]'),rate=Number(data.rates[ccy]);
        if(el&&Number.isFinite(rate))el.textContent=rate>=1000?Math.round(rate).toLocaleString('en-US'):rate>=10?rate.toFixed(2):rate.toFixed(4).replace(/0+$/,'').replace(/\.$/,'');
      }});
    }}).catch(function(){{}})
  }}
  refreshFx();setInterval(refreshFx,60000);
}}();

// Live Livermore Darvis ROI: refresh on every page load and every hour.
!function(){{
  function refreshDarvis(){{
    fetch('/api/alpaca-summary?_='+Date.now(),{{cache:'no-store'}}).then(function(r){{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}}).then(function(data){{
      var el=document.querySelector('[data-darvas-roi]'),roi=Number(data.inceptionRoi);
      if(el&&Number.isFinite(roi)){{el.textContent=(roi>=0?'+':'')+roi.toFixed(1)+'%';el.style.color=roi>=0?'#4ade80':'#f87171'}}
    }}).catch(function(){{}})
  }}
  refreshDarvis();setInterval(refreshDarvis,3600000);
}}();

// Live index futures: refresh through the same-origin Vercel edge proxy every minute.
!function(){{
  function refreshFutures(){{
    fetch('/api/market-futures?_='+Date.now(),{{cache:'no-store'}})
      .then(function(r){{return r.json()}})
      .then(function(data){{
        (data.quotes||[]).forEach(function(q){{
          var el=document.querySelector('[data-future-symbol="'+q.symbol+'"]');if(!el)return;
          var pe=el.querySelector('[data-future-price]'),ce=el.querySelector('[data-future-change]');
          if(pe&&Number.isFinite(Number(q.price)))pe.textContent=Number(q.price).toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}});
          if(ce&&Number.isFinite(Number(q.change))){{var ch=Number(q.change);ce.textContent=(ch>=0?'+':'')+ch.toFixed(2)+'%';ce.className=ch>=0?'positive':'negative'}}
          if(q.quoteTime)el.setAttribute('data-quote-time',q.quoteTime);
        }});
        (data.indices||[]).forEach(function(q){{
          var pe=document.querySelector('[data-market-price="'+q.symbol+'"]'),ce=document.querySelector('[data-market-change="'+q.symbol+'"]');
          if(pe&&Number.isFinite(Number(q.price)))pe.textContent=Number(q.price).toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}});
          if(ce&&Number.isFinite(Number(q.change))){{var ch=Number(q.change);ce.textContent=(ch>=0?'+':'')+ch.toFixed(2)+'%';ce.className=ch>=0?'positive':'negative'}}
        }});
      }}).catch(function(){{}})
  }}
  refreshFutures();setInterval(refreshFutures,60000);
}}();
</script>
</body>
</html>"""
    return html

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def render_portfolio_html(portfolio_data, catalysts, fx, holdings_source=None, gs_meta=None, bot_accounts_html="", evo_fund_html="", net_worth_tracker_html=""):
    """Render standalone portfolio page at /portfolio"""
    now       = datetime.now(timezone.utc).astimezone(BKK_TZ)
    date_str  = now.strftime("%A, %B %-d, %Y")
    gen_time  = now.strftime("%H:%M ICT")

    # ── Portfolio calculations (same as main) ──
    total_usd   = 0
    sector_totals = {}
    port_sorted = []

    for h in (holdings_source or HOLDINGS):
        ticker = h["ticker"]
        pdata  = portfolio_data.get(ticker, {})
        price  = pdata.get("price")
        value  = pdata.get("value")
        change = pdata.get("change")
        is_fallback = pdata.get("fallback", False)
        port_sorted.append((ticker, h, price, value, change, is_fallback))

    port_sorted.sort(key=lambda x: (x[3] or 0), reverse=True)

    for ticker, h, price, value, change, is_fallback in port_sorted:
        if value:
            total_usd += value
            sector = SECTORS.get(ticker, "Other")
            sector_totals[sector] = sector_totals.get(sector, 0) + value

    total_cad  = total_usd * fx["usdcad"]
    roi_pct    = ((total_cad - PORT_BASIS_CAD) / PORT_BASIS_CAD * 100) if PORT_BASIS_CAD else 0

    # Override with sheet totals if available (source of truth)
    _meta = gs_meta or {}
    if _meta.get("total_cad"):
        total_cad = _meta["total_cad"]
    if _meta.get("total_usd"):
        total_usd = _meta["total_usd"]
    if _meta.get("roi_pct_str"):
        try:
            roi_pct = float(_meta["roi_pct_str"].replace("%", "").strip())
        except: pass
    port_ath = _meta.get("ath") or PORT_ATH
    port_roi_abs = _meta.get("roi_abs") or PORT_ROI_ABS
    port_basis_cad = (total_cad - port_roi_abs) if _meta.get("roi_abs") else PORT_BASIS_CAD

    # Build holdings rows HTML
    rows_html = ""
    for ticker, h, price, value, change, is_fallback in port_sorted:
        display = h.get("display", ticker.split(".")[0])
        name    = h["name"]
        shares  = h["shares"]
        chg_html    = fmt_pct(change)
        fallback_note = '<span class="fallback-badge">est</span>' if is_fallback else ""
        price_str   = (fmt_price(price, 2) + fallback_note) if price and price >= 0.01 else \
                      ((fmt_price(price, 4) + fallback_note) if price else "—")
        value_str   = f"${value:,.0f}" if value else "—"
        rows_html += f"""
          <tr>
            <td class="ticker chart-ticker" data-chart-symbol="{ticker}" data-chart-name="{escape(name, quote=True)}" tabindex="0" role="button" aria-label="Open {escape(display, quote=True)} price chart">{display}</td>
            <td style="color:var(--dim);font-size:.8em">{name}</td>
            <td style="text-align:right">{int(shares):,}</td>
            <td style="text-align:right">{price_str}</td>
            <td style="text-align:right">{chg_html}</td>
            <td style="text-align:right;font-weight:600">{value_str}</td>
          </tr>"""

    # ── Allocation chart: fail closed to the Google Sheet source of truth ──
    donut_svg, legend_html, allocation_source_html = build_sheet_allocation_component(_meta)

    # ── Top 5 catalysts ──
    top5 = [t for t, *_ in port_sorted[:5]]
    fresh_cats  = [(t, catalysts.get(t)) for t in top5 if catalysts.get(t) and catalysts.get(t, {}).get("fresh")]
    no_news_tks = [t for t in top5 if not (catalysts.get(t) and catalysts.get(t, {}).get("fresh"))]

    cats_html = ""
    for ticker, cat in fresh_cats:
        display    = HOLDINGS_MAP.get(ticker, {}).get("display", ticker.split(".")[0])
        source_str = f' · {cat["source"]}' if cat["source"] else ""
        cats_html += f"""
            <div class="catalyst-item">
              <span class="catalyst-ticker">{display}</span>
              <span class="catalyst-sep"> · </span>
              <span class="catalyst-badge">{cat['date']}{source_str}</span>
              <span class="catalyst-sep"> — </span>
              <span class="catalyst-headline">{cat['title']}</span>
            </div>"""
    if no_news_tks:
        no_news_displays = " · ".join(
            HOLDINGS_MAP.get(t, {}).get("display", t.split(".")[0]) for t in no_news_tks
        )
        cats_html += f"""
            <div class="catalyst-item">
              <span class="catalyst-ticker">{no_news_displays}</span>
              <span class="catalyst-sep"> — </span>
              <span class="catalyst-headline" style="color:var(--dim);font-style:italic">No verified news within 14 days.</span>
            </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Novaire Signal — Portfolio</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta name="theme-color" content="#0a0a0c">
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400;1,500&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    :root{{
      --bg:#0a0a0c;--surface:#111116;--border:#1e1e26;--text:#f0eef8;--dim:#a8a4ba;--mute:#6e6a85;
      --gold:#b59662;--gold-dim:rgba(181,150,98,.12);--gold-mid:rgba(181,150,98,.25);
      --green:#2a9d8f;--red:#e63946;--blue:#5a7bc4;--violet:#9470c8;
      --sans:'Inter',sans-serif;--serif:'Cormorant Garamond',serif;--r:6px;
    }}
    html{{scroll-behavior:smooth;font-size:110%}}
    body{{font-family:var(--sans);background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:32px 16px;font-size:18.15px;line-height:1.5}}
    .container{{max-width:720px;margin:0 auto}}
    .header-brand{{text-align:center;padding-bottom:20px}}
    .dateline{{text-align:center;padding:0 0 28px;margin-bottom:28px;border-bottom:1px solid var(--border)}}
    .dateline .date{{font-size:.7rem;letter-spacing:.2em;text-transform:uppercase;color:var(--dim)}}
    .card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px;margin-bottom:14px}}
    .card-title{{font-size:.6rem;font-weight:600;letter-spacing:.24em;text-transform:uppercase;color:var(--gold);margin-bottom:16px;display:flex;align-items:center;gap:8px}}
    .card-title::after{{content:'';flex:1;height:1px;background:linear-gradient(90deg,var(--gold-mid),transparent)}}
    .portfolio-summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px}}
    .psum-item{{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:12px;text-align:center}}
    .psum-label{{font-size:.58rem;color:var(--dim);text-transform:uppercase;letter-spacing:.12em;margin-bottom:4px}}
    .psum-value{{font-family:var(--serif);font-size:1.35rem;font-weight:400}}
    .portfolio-table{{width:100%;border-collapse:collapse;font-size:.78rem}}
    .chart-ticker{{cursor:pointer;text-decoration:underline;text-decoration-color:rgba(181,150,98,.38);text-underline-offset:3px}}
    .chart-ticker:hover,.chart-ticker:focus-visible{{color:#dfc48f;outline:none;text-decoration-color:currentColor}}
    .holding-chart-dialog{{width:min(680px,calc(100vw - 24px));max-height:calc(100vh - 24px);padding:0;border:1px solid var(--gold-mid);border-radius:10px;color:var(--text);background:#0d0d12;box-shadow:0 24px 80px rgba(0,0,0,.75)}}
    .holding-chart-dialog::backdrop{{background:rgba(0,0,0,.78);backdrop-filter:blur(3px)}}
    .chart-shell{{padding:18px}}.chart-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}}
    .chart-symbol{{font-family:var(--serif);font-size:1.35rem;color:var(--gold)}}.chart-meta,.chart-status{{font-size:.62rem;color:var(--mute)}}
    .chart-close{{border:1px solid var(--border);border-radius:50%;width:34px;height:34px;color:var(--dim);background:transparent;cursor:pointer;font-size:1rem}}
    .chart-stage{{min-height:250px;display:grid;place-items:center;border:1px solid var(--border);border-radius:8px;background:#09090d;overflow:hidden}}.chart-stage svg{{display:block;width:100%;height:auto}}
    .portfolio-table th{{text-align:left;padding:7px 5px;font-size:.58rem;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.1em;border-bottom:1px solid var(--border)}}
    .portfolio-table td{{padding:7px 5px;border-bottom:1px solid rgba(255,255,255,.025)}}
    .portfolio-table tr:hover{{background:rgba(255,255,255,.015)}}
    .ticker{{font-weight:600;color:var(--gold);font-size:.82rem}}
    .positive{{color:var(--green)}}.negative{{color:var(--red)}}
    .fallback-badge{{font-size:.55rem;color:var(--mute);vertical-align:middle;margin-left:3px}}
    .totals-row{{display:flex;justify-content:space-between;margin-top:16px;padding-top:14px;border-top:1px solid var(--border)}}
    .total-item{{text-align:center}}
    .total-label{{font-size:.58rem;color:var(--dim);text-transform:uppercase;letter-spacing:.1em}}
    .total-value{{font-family:var(--serif);font-size:1.4rem;font-weight:400;margin-top:3px}}
    .total-value.cad{{color:var(--green)}}.total-value.usd{{color:var(--gold)}}
    .allocation-section{{position:relative;isolation:isolate;display:grid;grid-template-columns:minmax(220px,280px) minmax(0,1fr);align-items:center;gap:clamp(20px,4vw,42px);margin-top:22px;padding:24px;border:1px solid rgba(140,255,0,.15);border-radius:16px;overflow:hidden;background:radial-gradient(circle at 18% 35%,rgba(140,255,0,.09),transparent 38%),radial-gradient(circle at 82% 72%,rgba(0,232,111,.065),transparent 42%),linear-gradient(145deg,rgba(121,247,255,.025),rgba(0,0,0,.2))}}
    .allocation-section::before{{content:'';position:absolute;inset:0;z-index:-1;background:linear-gradient(115deg,transparent 12%,rgba(245,255,90,.055) 42%,transparent 68%);pointer-events:none}}
    .pie-chart{{display:block;width:min(100%,280px);height:auto;aspect-ratio:1;justify-self:center;overflow:visible;flex-shrink:0;filter:drop-shadow(0 18px 28px rgba(0,0,0,.46))}}
    .allocation-aura{{fill:rgba(9,10,14,.76);stroke:rgba(140,255,0,.14);stroke-width:1}}
    .allocation-track{{fill:none;stroke:rgba(255,255,255,.045);stroke-width:52}}
    .allocation-glow{{opacity:.86}}
    .allocation-slice{{stroke-linecap:butt;filter:saturate(1.42) contrast(1.07) brightness(1.1);transition:opacity .2s ease,filter .2s ease}}
    .allocation-slice:hover{{opacity:.94;filter:saturate(1.55) contrast(1.08) brightness(1.18)}}
    .allocation-gloss-layer{{pointer-events:none;mix-blend-mode:screen}}
    .allocation-gloss{{opacity:.34}}
    .allocation-core{{fill:url(#allocation-core);stroke:rgba(121,247,255,.17);stroke-width:1.25}}
    .allocation-core-kicker,.allocation-core-label{{font-family:var(--sans);fill:#bdff94;font-size:9px;font-weight:600;letter-spacing:3px;filter:drop-shadow(0 0 5px rgba(140,255,0,.25))}}
    .allocation-copy{{min-width:0}}
    .allocation-kicker{{margin-bottom:12px;color:var(--gold);font-size:.58rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase}}
    .allocation-legend{{display:grid;grid-template-columns:1fr;gap:8px}}
    .legend-item{{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:8px;min-width:0;padding:9px 10px;border:1px solid rgba(140,255,0,.075);border-radius:9px;background:rgba(4,4,7,.34);font-size:.7rem}}
    .legend-dot{{width:11px;height:11px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,var(--swatch-start),var(--swatch-end));box-shadow:inset 0 0 4px rgba(255,255,255,.8),0 0 8px var(--swatch-start),0 0 18px color-mix(in srgb,var(--swatch-end) 72%,transparent)}}
    .legend-name{{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text)}}
    .legend-pct{{color:#d8d3e2;margin-left:auto;font-variant-numeric:tabular-nums;font-weight:500}}
    .allocation-source{{display:flex;align-items:center;gap:7px;margin-top:13px;color:var(--mute);font-size:.55rem;letter-spacing:.06em}}
    .allocation-source span{{width:6px;height:6px;border-radius:50%;background:#5ff1b8;box-shadow:0 0 10px rgba(95,241,184,.78)}}
    .allocation-source--offline{{color:var(--red)}}
    .allocation-unavailable{{grid-column:1/-1;padding:34px 18px;text-align:center;color:var(--dim);font-size:.72rem}}
    .net-worth-tracker{{position:relative;overflow:hidden;padding:20px;background:radial-gradient(circle at 92% 8%,rgba(61,228,255,.09),transparent 33%),radial-gradient(circle at 9% 88%,rgba(255,184,0,.08),transparent 38%),var(--surface)}}
    .net-worth-tracker::before{{content:'';position:absolute;inset:0;pointer-events:none;background:linear-gradient(110deg,transparent 14%,rgba(255,255,255,.025) 46%,transparent 72%)}}
    .tracker-head{{position:relative;display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:11px}}
    .tracker-head .card-title{{margin-bottom:4px}}
    .tracker-subtitle{{color:var(--mute);font-size:.58rem;letter-spacing:.055em}}
    .tracker-asof{{display:flex;align-items:center;gap:7px;color:#73efc5;font-size:.55rem;letter-spacing:.08em;white-space:nowrap}}
    .tracker-asof span{{width:7px;height:7px;border-radius:50%;background:#5ff1b8;box-shadow:0 0 13px rgba(95,241,184,.9)}}
    .tracker-total-label{{position:relative;color:var(--dim);font-size:.57rem;letter-spacing:.17em;text-transform:uppercase}}
    .tracker-total{{position:relative;margin-top:3px;font-family:var(--serif);font-size:2.35rem;font-weight:400;line-height:1;color:#f7f1e6;text-shadow:0 0 24px rgba(255,211,38,.09);font-variant-numeric:tabular-nums}}
    .tracker-accounts{{position:relative;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0 10px}}
    .tracker-account{{padding:10px 12px;border:1px solid rgba(255,255,255,.06);border-radius:10px;background:rgba(4,4,7,.34)}}
    .tracker-account-name{{display:flex;align-items:center;gap:7px;color:var(--dim);font-size:.56rem;letter-spacing:.12em;text-transform:uppercase}}
    .tracker-account-name span{{width:7px;height:7px;border-radius:50%;background:#ffd21f;box-shadow:0 0 10px rgba(255,210,31,.7)}}
    .tracker-account--kraken .tracker-account-name span{{background:#42d8ff;box-shadow:0 0 10px rgba(66,216,255,.75)}}
    .tracker-account-value{{margin-top:3px;font-family:var(--serif);font-size:1.28rem;font-variant-numeric:tabular-nums}}
    .tracker-account-secondary{{color:var(--mute);font-size:.54rem}}
    .tracker-charts{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:2px 0 11px}}
    .tracker-chart{{position:relative;min-width:0;padding:8px;border:1px solid rgba(255,255,255,.045);border-radius:12px;background:rgba(3,3,6,.34)}}
    .tracker-chart-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin:0 2px 5px}}
    .tracker-chart-head strong{{display:block;color:var(--text);font-family:var(--serif);font-size:.85rem;font-weight:500}}
    .tracker-chart-head span{{display:block;margin-top:1px;color:var(--mute);font-size:.46rem;letter-spacing:.04em}}
    .tracker-chart-head b{{font-size:.66rem;font-variant-numeric:tabular-nums}}
    .tracker-chart svg{{display:block;width:100%;height:auto;border:1px solid rgba(255,255,255,.045);border-radius:10px;background:rgba(3,3,6,.34)}}
    .tracker-chart-axis{{display:flex;justify-content:space-between;gap:8px;margin:4px 2px 0;color:var(--mute);font-size:.46rem;font-variant-numeric:tabular-nums}}
    .tracker-chart-empty{{position:relative;padding:28px 16px;margin:4px 0 16px;border:1px solid rgba(255,255,255,.05);border-radius:12px;text-align:center;color:var(--mute);font-size:.62rem}}
    .tracker-performance-title{{position:relative;margin:2px 0 8px;padding-top:11px;border-top:1px solid rgba(255,255,255,.055);color:var(--gold);font-size:.55rem;font-weight:600;letter-spacing:.17em;text-transform:uppercase}}
    .tracker-performance{{position:relative;display:grid;gap:6px}}
    .tracker-performance-row{{display:grid;grid-template-columns:108px minmax(0,1fr);align-items:stretch;gap:8px}}
    .tracker-performance-name{{display:flex;align-items:center;padding:0 9px;border:1px solid rgba(255,255,255,.05);border-radius:8px;background:rgba(2,2,5,.2);color:var(--dim);font-size:.57rem;line-height:1.25;letter-spacing:.04em}}
    .tracker-performance-grid{{display:grid;grid-template-columns:repeat(var(--period-count,5),minmax(68px,1fr));gap:8px;min-width:0}}
    .tracker-performance-grid>div{{padding:6px 7px;border:1px solid rgba(255,255,255,.05);border-radius:8px;background:rgba(2,2,5,.3);text-align:right}}
    .tracker-performance-grid--single>div{{text-align:center}}
    .tracker-performance-grid em{{display:block;color:var(--mute);font-size:.48rem;font-style:normal;letter-spacing:.1em}}
    .tracker-period strong{{display:block;margin-top:2px;font-size:.64rem;font-variant-numeric:tabular-nums}}
    .tracker-period small{{display:block;color:var(--mute);font-size:.46rem;font-variant-numeric:tabular-nums}}
    .tracker-period--pending strong{{color:var(--mute)}}
    .tracker-foot{{position:relative;margin-top:10px;padding-top:9px;border-top:1px solid rgba(255,255,255,.045);color:var(--mute);font-size:.5rem;line-height:1.4}}
    .debt-hub{{position:relative;overflow:hidden;display:grid;grid-template-columns:minmax(0,1fr) 190px;align-items:center;gap:24px;padding:24px;border-color:rgba(255,126,54,.22);background:radial-gradient(circle at 88% 15%,rgba(255,92,39,.12),transparent 36%),linear-gradient(135deg,rgba(255,184,0,.045),rgba(4,4,7,.4)),var(--surface)}}
    .debt-hub::before{{content:'';position:absolute;inset:0;pointer-events:none;background:linear-gradient(110deg,transparent 18%,rgba(255,255,255,.025) 48%,transparent 76%)}}
    .debt-hub-copy,.debt-hub-action{{position:relative}}
    .debt-hub-action{{display:flex;align-items:stretch}}
    .debt-hub-kicker{{color:#ffad69;font-size:.56rem;font-weight:650;letter-spacing:.18em;text-transform:uppercase}}
    .debt-hub h2{{margin:6px 0 7px;font-family:var(--serif);font-size:1.48rem;font-weight:400;color:#f7f1e6}}
    .debt-hub p{{max-width:620px;margin:0;color:var(--mute);font-size:.67rem;line-height:1.55}}
    .debt-hub-link{{display:inline-flex;align-items:center;justify-content:center;width:100%;min-height:44px;padding:0 16px;border:1px solid rgba(255,173,105,.35);border-radius:9px;color:#ffd0aa;background:rgba(255,116,45,.08);font-size:.64rem;font-weight:650;letter-spacing:.06em;text-align:center;text-decoration:none;white-space:nowrap;transition:.18s ease}}
    .debt-hub-link:hover{{border-color:rgba(255,173,105,.65);background:rgba(255,116,45,.14);transform:translateY(-1px)}}
    .catalyst-item{{padding:8px 0;border-bottom:1px solid var(--border);display:flex;align-items:baseline;flex-wrap:wrap;gap:2px;line-height:1.4}}
    .catalyst-item:last-child{{border-bottom:none}}
    .catalyst-ticker{{font-weight:600;color:var(--gold);font-size:.85rem;white-space:nowrap}}
    .catalyst-sep{{color:var(--dim);font-size:.8rem}}
    .catalyst-badge{{color:var(--gold);font-size:.75rem;opacity:.8;white-space:nowrap}}
    .catalyst-headline{{font-size:.8rem;color:var(--text);line-height:1.4}}
    .footer{{text-align:center;padding:40px 0 24px;border-top:1px solid var(--border);margin-top:28px}}
    .footer-logo{{font-family:var(--serif);font-size:1.6363636rem;font-weight:300;letter-spacing:.18em;text-transform:uppercase;color:var(--text);margin-bottom:4px}}
    .footer-logo span{{color:var(--gold);font-style:italic}}
    .footer-tagline{{font-size:.62rem;color:var(--dim);letter-spacing:.14em;text-transform:uppercase}}
    .footer-sub{{font-size:.58rem;color:var(--mute);margin-top:6px}}
    .eco-links{{display:flex;justify-content:center;gap:20px;margin-top:12px;flex-wrap:wrap}}
    .eco-link{{font-size:.7rem;color:var(--gold);text-decoration:none;opacity:.7;transition:opacity .15s;letter-spacing:.06em}}
    .eco-link:hover{{opacity:1}}
    .back-link{{display:inline-block;margin-bottom:20px;font-size:.7rem;color:var(--dim);text-decoration:none;letter-spacing:.08em}}
    .back-link:hover{{color:var(--gold)}}
    @media(max-width:600px){{
      .portfolio-summary{{grid-template-columns:repeat(3,1fr)}}
      .totals-row{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px 10px}}
      .totals-row .total-item{{text-align:left;min-width:0}}
      .totals-row .total-value{{font-size:1.05rem;white-space:nowrap}}
      .allocation-section{{grid-template-columns:1fr;gap:14px;padding:18px}}
      .pie-chart{{width:min(100%,250px)}}
      .allocation-kicker{{text-align:center}}
      .allocation-legend{{grid-template-columns:1fr}}
      .net-worth-tracker{{padding:14px}}
      .tracker-head{{align-items:flex-start}}
      .tracker-total{{font-size:1.9rem}}
      .tracker-accounts{{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin:10px 0 8px}}
      .tracker-account{{padding:8px 9px}}
      .tracker-account-value{{font-size:1.08rem}}
      .tracker-charts{{grid-template-columns:1fr}}
      .tracker-performance{{overflow:visible;padding-bottom:0}}
      .tracker-performance{{gap:6px}}
      .tracker-performance-row{{grid-template-columns:1fr;gap:4px}}
      .tracker-performance-grid{{min-width:0}}
      .tracker-performance-name{{min-height:24px;padding:4px 7px}}
      .debt-hub{{grid-template-columns:1fr;padding:20px}}
      .debt-hub-link{{width:100%}}
    }}
    .collapse-toggle{{cursor:pointer;user-select:none;transition:opacity .15s;display:block;padding:10px 0 6px;margin:-2px 0}}
    .collapse-toggle:hover{{opacity:.7;background:rgba(181,150,98,0.05);border-radius:4px}}
    .collapse-toggle::after{{content:' ▾';font-size:.65rem;color:var(--mute);margin-left:4px}}
  </style>
</head>
<body>
<div class="container">

  <a href="/" class="back-link">← Back to Signal</a>

  <div class="header-brand">
    <div class="footer-logo">Novaire <span>Signal</span></div>
    <div style="font-family:var(--serif);font-size:.9rem;font-style:italic;color:var(--gold);opacity:0.7;letter-spacing:.04em;margin-top:2px;">Portfolio</div>
  </div>

  <div class="dateline">
    <div class="date">{date_str}</div>
  </div>

  <div class="card">
    <div class="card-title">📦 Portfolio</div>
    <div class="portfolio-summary">
      <div class="psum-item">
        <div class="psum-label">Live USD</div>
        <div class="psum-value" style="color:var(--gold)">${total_usd:,.0f}</div>
      </div>
      <div class="psum-item">
        <div class="psum-label">Live CAD</div>
        <div class="psum-value" style="color:var(--green)">${total_cad:,.0f}</div>
      </div>
      <div class="psum-item">
        <div class="psum-label">ROI</div>
        <div class="psum-value {'positive' if roi_pct >= 0 else 'negative'}" style="color:{'var(--green)' if roi_pct >= 0 else 'var(--red)'}">{'+'if roi_pct>=0 else ''}{roi_pct:.1f}%</div>
      </div>
    </div>
    <div class="portfolio-summary">
      <div class="psum-item">
        <div class="psum-label">Basis CAD</div>
        <div class="psum-value" style="color:var(--blue);font-size:1.1rem">${port_basis_cad:,.0f}</div>
      </div>
      <div class="psum-item">
        <div class="psum-label">ATH (w/ w/d)</div>
        <div class="psum-value" style="color:var(--violet);font-size:1.1rem">${port_ath:,}</div>
      </div>
      <div class="psum-item">
        <div class="psum-label">ROI Abs.</div>
        <div class="psum-value" style="color:var(--green);font-size:1.1rem">${port_roi_abs:,.0f}</div>
      </div>
    </div>

    <div class="collapse-toggle" style="font-size:.65rem;font-weight:600;color:var(--gold);letter-spacing:.1em;text-transform:uppercase">Holdings</div>
    <div><table class="portfolio-table">
      <thead>
        <tr>
          <th>Ticker</th><th>Name</th>
          <th style="text-align:right">Shares</th>
          <th style="text-align:right">Price</th>
          <th style="text-align:right">24h</th>
          <th style="text-align:right">Value</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table></div>
    <div class="totals-row">
      <div class="total-item">
        <div class="total-label">Live USD</div>
        <div class="total-value usd">${total_usd:,.0f}</div>
      </div>
      <div class="total-item">
        <div class="total-label">Live CAD</div>
        <div class="total-value cad">${total_cad:,.0f}</div>
      </div>
      <div class="total-item">
        <div class="total-label">Basis CAD</div>
        <div class="total-value" style="color:var(--blue)">${port_basis_cad:,.0f}</div>
      </div>
      <div class="total-item">
        <div class="total-label">ATH</div>
        <div class="total-value" style="color:var(--violet)">${port_ath:,}</div>
      </div>
      <div class="total-item">
        <div class="total-label">ROI</div>
        <div class="total-value positive">{'+' if roi_pct>=0 else ''}{roi_pct:.1f}%</div>
      </div>
    </div>
    <div class="allocation-section">
      {donut_svg}
      <div class="allocation-copy">
        <div class="allocation-kicker">Sector Allocation</div>
        <div class="allocation-legend">
          {legend_html}
        </div>
        {allocation_source_html}
      </div>
    </div>
    <div style="font-size:.6rem;color:var(--mute);margin-top:10px;text-align:center">
      <span class="fallback-badge">est</span> = estimated / last known price · Updated every 2 hours
    </div>
  </div>

  <!-- NET WORTH TRACKER — daily Google Sheet closes -->
  {net_worth_tracker_html}

  <!-- ON THE RISE FINANCES — debt progress -->
  <section class="card debt-hub" id="debt-progress">
    <div class="debt-hub-copy">
      <div class="debt-hub-kicker">On The Rise Finances · live debt progress</div>
      <h2>Put out the interest fire. Recharge the balance sheet.</h2>
      <p>Open the spreadsheet-linked fire and battery visuals, payoff milestones, monthly interest load and debt history.</p>
    </div>
    <div class="debt-hub-action"><a class="debt-hub-link" href="/portfolio/finances/">Open debt dashboard →</a></div>
  </section>

  <!-- EVOLUTION FUND -->
  {evo_fund_html}

  <!-- BOT TRADING ACCOUNTS -->
  {bot_accounts_html}

  <!-- ECOSYSTEM LINKS -->
  <div class="footer">
    <div class="footer-logo">Novaire <span>Signal</span></div>
    <div class="footer-tagline">Deciphering through the noise.</div>
    <div class="eco-links">
      <a href="https://novairesignal.com" class="eco-link">Novaire Signal</a>
      <a href="https://novaireink.com" class="eco-link">Novaire Ink</a>
      <a href="https://evolution-fund.vercel.app" class="eco-link">Evolution Fund</a>
    </div>
    <div class="footer-sub">Live data · Updated every 2 hours · 24/7</div>
  </div>

</div>
<dialog id="holding-chart-dialog" class="holding-chart-dialog">
  <div class="chart-shell">
    <div class="chart-head"><div><div id="holding-chart-title" class="chart-symbol">Price chart</div><div class="chart-meta">9-month weekly candles · Previous close</div></div><button class="chart-close" type="button" aria-label="Close chart">×</button></div>
    <div id="holding-chart-stage" class="chart-stage" aria-live="polite"><div class="chart-status">Select a ticker</div></div>
  </div>
</dialog>
<script>
document.querySelectorAll('.collapse-toggle').forEach(t => {{
  const content = t.nextElementSibling;
  if(content) content.style.display = 'none';
  t.addEventListener('click', () => {{
    if(!content) return;
    const hidden = content.style.display === 'none';
    content.style.display = hidden ? 'block' : 'none';
    t.style.opacity = hidden ? '0.7' : '1';
  }});
}});

!function(){{
  const dialog=document.getElementById('holding-chart-dialog'),stage=document.getElementById('holding-chart-stage'),title=document.getElementById('holding-chart-title');
  if(!dialog||!stage||!title)return;
  dialog.querySelector('.chart-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',event=>{{if(event.target===dialog)dialog.close()}});
  function candleSvg(data){{
    const candles=data.candles||[],W=640,H=330,p={{l:48,r:16,t:18,b:30}},innerW=W-p.l-p.r,innerH=H-p.t-p.b;
    const values=candles.flatMap(c=>[c.low,c.high]).concat(Number.isFinite(data.previousClose)?[data.previousClose]:[]),lo=Math.min(...values),hi=Math.max(...values),span=Math.max(hi-lo,.0001);
    const y=value=>p.t+(hi-value)/span*innerH,x=index=>p.l+(index+.5)/candles.length*innerW,body=Math.max(3,Math.min(10,innerW/candles.length*.58));
    const grid=[0,.25,.5,.75,1].map(q=>{{const yy=p.t+q*innerH,val=hi-q*span;return `<line x1="${{p.l}}" y1="${{yy}}" x2="${{W-p.r}}" y2="${{yy}}" stroke="#1e1e26"/><text x="${{p.l-6}}" y="${{yy+3}}" text-anchor="end" fill="#6e6a85" font-size="9">${{val.toFixed(val<1?3:2)}}</text>`}}).join('');
    const bars=candles.map((c,i)=>{{const xx=x(i),color=c.close>=c.open?'#2a9d8f':'#e63946',top=y(Math.max(c.open,c.close)),height=Math.max(1,Math.abs(y(c.open)-y(c.close)));return `<line x1="${{xx}}" y1="${{y(c.high)}}" x2="${{xx}}" y2="${{y(c.low)}}" stroke="${{color}}"/><rect x="${{xx-body/2}}" y="${{top}}" width="${{body}}" height="${{height}}" fill="${{color}}" rx="1"/>`}}).join('');
    const prev=Number.isFinite(data.previousClose)?`<line x1="${{p.l}}" y1="${{y(data.previousClose)}}" x2="${{W-p.r}}" y2="${{y(data.previousClose)}}" stroke="#b59662" stroke-dasharray="5 4"/><text x="${{W-p.r-2}}" y="${{y(data.previousClose)-5}}" text-anchor="end" fill="#b59662" font-size="9">Previous close ${{data.previousClose.toFixed(2)}}</text>`:'';
    return `<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="${{data.symbol}} 9-month weekly candlestick chart"><rect width="${{W}}" height="${{H}}" fill="#09090d"/>${{grid}}${{prev}}${{bars}}<text x="${{p.l}}" y="${{H-9}}" fill="#6e6a85" font-size="9">9 months ago</text><text x="${{W-p.r}}" y="${{H-9}}" text-anchor="end" fill="#6e6a85" font-size="9">Latest weekly bar</text></svg>`;
  }}
  async function openChart(cell){{
    const symbol=cell.dataset.chartSymbol,name=cell.dataset.chartName||symbol;title.textContent=`${{cell.textContent.trim()}} · ${{name}}`;stage.innerHTML='<div class="chart-status">Loading weekly candles…</div>';dialog.showModal();
    try{{const response=await fetch('/api/stock-chart?symbol='+encodeURIComponent(symbol),{{cache:'no-store'}});if(!response.ok)throw new Error();const data=await response.json();stage.innerHTML=candleSvg(data)}}catch(error){{stage.innerHTML='<div class="chart-status">Chart temporarily unavailable. Try again shortly.</div>'}}
  }}
  document.querySelectorAll('.chart-ticker').forEach(cell=>{{cell.addEventListener('click',()=>openChart(cell));cell.addEventListener('keydown',event=>{{if(event.key==='Enter'||event.key===' '){{event.preventDefault();openChart(cell)}}}})}});
}}();
</script>
</body>
</html>"""


def fetch_polymarket_win_rate():
    """Calculate win rate from all Polymarket trades — buy avg vs sell avg per position."""
    try:
        import requests
        wallet = "0xC1541b2af765e4d1013337084D889d0DB302Aa0e"
        offset = 0
        all_activity = []
        while True:
            r = requests.get(f"https://data-api.polymarket.com/activity?user={wallet.lower()}&limit=100&offset={offset}", timeout=15)
            batch = r.json()
            if not batch:
                break
            all_activity.extend(batch)
            if len(batch) < 100:
                break
            offset += 100

        from collections import defaultdict
        positions = defaultdict(lambda: {"buys": [], "sells": []})
        for a in all_activity:
            token = a.get("asset", "?")
            side = a.get("side", "")
            price = float(a.get("price", 0))
            size = float(a.get("size", 0))
            usdc = float(a.get("usdcSize", 0))
            if side == "BUY" and price > 0:
                positions[token]["buys"].append({"price": price, "size": size, "usdc": usdc})
            elif side == "SELL" and price > 0:
                positions[token]["sells"].append({"price": price, "size": size, "usdc": usdc})

        wins = 0
        losses = 0
        for token, data in positions.items():
            if not data["buys"] or not data["sells"]:
                continue
            buy_total = sum(b["usdc"] for b in data["buys"])
            buy_qty = sum(b["size"] for b in data["buys"])
            avg_buy = buy_total / buy_qty if buy_qty > 0 else 0
            sell_total = sum(s["usdc"] for s in data["sells"])
            sell_qty = sum(s["size"] for s in data["sells"])
            avg_sell = sell_total / sell_qty if sell_qty > 0 else 0
            if avg_sell > avg_buy:
                wins += 1
            else:
                losses += 1

        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0
        return {"win_rate": win_rate, "wins": wins, "losses": losses, "total": total}
    except Exception as e:
        print(f"  ⚠ Win rate calc failed: {e}")
        return {"win_rate": 0, "wins": 0, "losses": 0, "total": 0}
def main():

    print("🚀 Novaire Signal — generating daily brief...")

    print("  📡 Fetching weather...")
    weather = fetch_weather()

    print("  📰 Scraping Bangkok Post...")
    try:
        bangkok_news = fetch_bangkok_post()
        print(f"    ✅ {len(bangkok_news)} headlines")
    except Exception as e:
        print(f"    ❌ {e}")
        bangkok_news = [{"title": "Bangkok Post unavailable", "url": "#"}]

    print("  📰 Scraping ZeroHedge...")
    try:
        zh_news = fetch_zerohedge()
        print(f"    ✅ {len(zh_news)} headlines")
    except Exception as e:
        print(f"    ❌ {e}")
        zh_news = [{"title": "ZeroHedge unavailable", "url": "#"}]

    print("  💱 Fetching FX rates (needed for portfolio conversion)...")
    try:
        fx = fetch_fx()
        print(f"    ✅ USD/CAD={fx['usdcad']:.4f}  AUD/USD={fx['audusd']:.4f}")
    except Exception as e:
        print(f"    ❌ {e}")
        fx = {"usdcad": 1.365, "audusd": 0.630}

    print("  💱 Fetching extended FX rates for display...")
    try:
        fx_rates = fetch_fx_rates()
        loaded_fx = sum(1 for v in fx_rates.values() if v.get("rate"))
        print(f"    ✅ {loaded_fx} FX pairs loaded")
    except Exception as e:
        print(f"    ❌ {e}")
        fx_rates = {}

    print("  📈 Fetching portfolio data (yfinance)...")
    holdings_source = HOLDINGS
    try:
        portfolio_data, holdings_source, gs_meta = fetch_portfolio(usdcad=fx["usdcad"], audusd=fx["audusd"])
        loaded = sum(1 for v in portfolio_data.values() if v.get("price"))
        print(f"    ✅ {loaded}/{len(holdings_source)} tickers loaded")
        if gs_meta:
            def _fmt_sheet_value(value):
                return f"{value:,}" if isinstance(value, (int, float)) else "?"
            print(f"    📊 Sheet: CAD=${_fmt_sheet_value(gs_meta.get('total_cad'))}  USD=${_fmt_sheet_value(gs_meta.get('total_usd'))}  ROI={gs_meta.get('roi_pct_str') or '?'}  ATH=${_fmt_sheet_value(gs_meta.get('ath'))}")
    except Exception as e:
        print(f"    ❌ {e}")
        portfolio_data = {}
        gs_meta = {}

    print("  ⚡ Updating net-worth close history (TFSA/WS + Kraken)...")
    kraken_meta = fetch_kraken_totals()
    portfolio_history = load_portfolio_history(PORTFOLIO_HISTORY_PATH)
    if gs_meta.get("total_cad") and kraken_meta.get("total_cad") is not None:
        portfolio_history = upsert_daily_snapshot(portfolio_history, gs_meta, kraken_meta)
        save_portfolio_history(portfolio_history, PORTFOLIO_HISTORY_PATH)
        print(
            f"    ✅ TFSA C${gs_meta['total_cad']:,.2f} · "
            f"Kraken US${kraken_meta['total_usd']:,.2f} · "
            f"{len(portfolio_history.get('snapshots', []))} daily closes"
        )
    else:
        print("    ⚠️  Incomplete Sheet totals; preserving the last verified close")
    net_worth_tracker_html = render_tracker_html(build_tracker_model(portfolio_history))

    print("  🔍 Fetching catalysts (yfinance news)...")
    sorted_holdings = sorted(
        [h["ticker"] for h in (holdings_source or HOLDINGS)],
        key=lambda t: (portfolio_data.get(t, {}).get("value") or 0),
        reverse=True
    )
    top5 = sorted_holdings[:5]
    try:
        catalysts = fetch_catalysts(top5)
        found = sum(1 for value in catalysts.values() if value)
        print(f"    ✅ Catalysts for {', '.join(top5)} ({found}/{len(top5)} with verified news ≤14d)")
    except Exception as e:
        print(f"    ❌ {e}")
        catalysts = {}

    print("  🪙 Fetching commodities (Investing.com)...")
    try:
        commodities = fetch_commodities()
        loaded_c = sum(1 for v in commodities.values() if v.get("price"))
        print(f"    ✅ {loaded_c}/{len(commodities)} commodities loaded")
    except Exception as e:
        print(f"    ❌ {e}")
        commodities = {}

    print("  🌐 Fetching crypto (Binance)...")
    try:
        crypto = fetch_crypto()
        loaded_cr = sum(1 for v in crypto.values() if v.get("price"))
        print(f"    ✅ {loaded_cr} crypto prices loaded")
    except Exception as e:
        print(f"    ❌ {e}")
        crypto = {}

    print("  📊 Fetching Wall Street index futures...")
    try:
        market_futures = fetch_market_futures()
        loaded_f = sum(1 for v in market_futures.values() if v.get("price") is not None)
        print(f"    ✅ {loaded_f}/{len(MARKET_FUTURES)} futures loaded")
    except Exception as e:
        print(f"    ❌ {e}")
        market_futures = {}

    print("  📉 Fetching major cash indexes...")
    try:
        market_indices = fetch_market_indices()
        loaded_i = sum(1 for v in market_indices.values() if v.get("price") is not None)
        print(f"    ✅ {loaded_i}/{len(MARKET_INDICES)} cash indexes loaded")
    except Exception as e:
        print(f"    ❌ {e}")
        market_indices = {}

    # FX already fetched before portfolio; ensure fallback exists
    if not fx:
        fx = {"usdcad": 1.365, "audusd": 0.630}

    # ── Polymarket (Barron147) — top open bets + wins/losses only ──
    print("  🎰 Fetching Polymarket positions...")
    poly = fetch_polymarket()
    poly_html = ""
    if poly["positions"]:
        pm_wr_summary = fetch_polymarket_win_rate()
        bets_html = ""
        for p in poly["positions"][:4]:  # Show top 4 open bets by weight
            pnl = p["pct_pnl"]
            pnl_color = "#4ade80" if pnl >= 0 else "#f87171"
            pnl_str = f"+{pnl:.1f}%" if pnl >= 0 else f"{pnl:.1f}%"
            bets_html += f'<div style="display:flex;justify-content:space-between;padding:3px 0;font-size:.75rem"><span style="color:var(--text)">{p["outcome"]} · {p["title"][:40]}...</span><span style="font-weight:600;color:{pnl_color}">{pnl_str}</span></div>'
        settled = pm_wr_summary['wins'] + pm_wr_summary['losses']
        win_rate = (pm_wr_summary['wins'] / settled * 100) if settled else 0
        poly_html = f'''<details class="card signal-accordion trading-accordion" id="polymarket-card">
  <summary><span class="card-title">🎰 Polymarket — Barron147</span><span class="accordion-score"><b>{pm_wr_summary['wins']}W / {pm_wr_summary['losses']}L</b> · {win_rate:.0f}% win</span></summary>
  <div class="signal-accordion-body">
    <div style="font-size:.7rem;color:var(--mute);padding-bottom:4px">Geopolitics & Event Contracts</div>
    {bets_html}
  </div>
</details>'''

    # ── Alpaca (Novaire's bot) ──
    print("  📈 Fetching Alpaca positions...")
    alpaca = fetch_alpaca()
    alpaca_html = ""
    if alpaca["funded"]:
        def _alp_rows(positions, label):
            rows = ""
            for p in positions:
                pnl = p["pct_pnl"]
                pnl_color = "#4ade80" if pnl >= 0 else "#f87171"
                pnl_str = f"+{pnl:.1f}%" if pnl >= 0 else f"{pnl:.1f}%"
                rows += f'<div style="display:flex;justify-content:space-between;padding:3px 0;font-size:.75rem"><span style="color:var(--text)">🟢 {p["symbol"]}</span><span style="font-weight:600;color:{pnl_color}">{pnl_str}</span></div>'
            if not positions:
                rows = f'<div style="font-size:.75rem;color:var(--mute);padding:3px 0">No open positions</div>'
            return rows

        all_positions = alpaca.get("tier2_positions", []) + alpaca.get("tier1_positions", [])
        all_positions.sort(key=lambda x: float(x.get("market_value", 0)), reverse=True)
        total_trades = int(alpaca.get("t1_trade_count", 0)) + int(alpaca.get("t2_trade_count", 0))
        total_equity = float(alpaca.get("equity", 0))
        total_roi = float(alpaca.get("inception_roi", 0))
        total_color = "#4ade80" if total_roi >= 0 else "#f87171"
        total_str = f"+{total_roi:.1f}%" if total_roi >= 0 else f"{total_roi:.1f}%"
        all_rows = _alp_rows(all_positions, "All")

        alpaca_html = f"""<details class="card signal-accordion trading-accordion" id="darvas-card">
    <summary><span class="card-title">🦙 Livermore Darvis</span><span class="accordion-score">Inception ROI <b data-darvas-roi style="color:{total_color}">{total_str}</b></span></summary>
    <div class="signal-accordion-body">
      <div style="font-size:.65rem;color:var(--mute);margin-bottom:6px">Unified bot book · {total_trades} trades · Since Feb 24, 2026</div>
      {all_rows}
    </div>
  </details><script>document.getElementById("darvas-card")?.removeAttribute("open");</script>"""

    # ── Crypto Strategy / Kraken Margin ──
    # Removed May 29, 2026: Novaire is not holding crypto for now, so the
    # portfolio page should not show Kraken margin or crypto strategy blocks.
    kraken_html = ""

    zodiac    = get_zodiac()
    doy       = day_of_year()
    thai_word = pick(THAI_WORDS, 5)
    spanish_word = pick(SPANISH_WORDS, 7)
    motivation = pick(MOTIVATION_QUOTES, 11)

    print("  📡 Refreshing Signal Feed (Nitter RSS → feed.json)...")
    try:
        import subprocess, os as _os
        result = subprocess.run(
            ["python3", "scripts/fetch_feed.py"],
            capture_output=True, text=True, timeout=90,
            cwd=_os.path.dirname(_os.path.abspath(__file__))
        )
        if result.returncode == 0:
            print("    ✅ feed.json updated")
        else:
            print(f"    ⚠️  fetch_feed.py: {result.stderr[-150:]}")
    except Exception as e:
        print(f"    ⚠️  Signal feed refresh failed: {e}")

    print("  🎬 Fetching trending recs...")
    try:
        rec_movie, rec_book = fetch_trending_recs()
        print(f"    ✅ Movie: {rec_movie['title'][:40]} | Book: {rec_book['title'][:40]}")
    except Exception as e:
        print(f"    ❌ {e}")
        rec_movie, rec_book = None, None

    print("  🏛️ Building Fed Signal...")
    fed_signal = fetch_fed_signal()
    print(f"    ✅ Next FOMC: {fed_signal['next_decision']} ({fed_signal['days_until']} days)")

    if show_biweekly_monday_section():
        print("  🌍 Building Top 5 Economies...")
        economies = fetch_top5_economies()
        print(f"    ✅ {len(economies)} economies loaded")
    else:
        print("  🌍 Top 5 Economies hidden until next biweekly Monday")
        economies = []

    suggested_tweet = build_suggested_tweet(gs_meta=gs_meta, fed_signal=fed_signal, zh_news=zh_news)

    print("  🎨 Generating HTML...")
    html = render_html(
        weather, bangkok_news, zh_news, portfolio_data, catalysts,
        commodities, crypto, fx, zodiac, thai_word, motivation,
        rec_movie=rec_movie, rec_book=rec_book, fx_rates=fx_rates,
        holdings_source=holdings_source, gs_meta=gs_meta,
        spanish_word=spanish_word,
        poly_html=poly_html,
        alpaca_html=alpaca_html,
        fed_signal=fed_signal,
        economies=economies,
        suggested_tweet=suggested_tweet,
        market_futures=market_futures,
        market_indices=market_indices
    )

    print("  📦 Generating portfolio page...")

    # ── Bot Accounts for Portfolio page (full $ detail) ──
    bot_accounts_html = ""

    # Polymarket — Barron147
    print("  🎰 Calculating Polymarket win rate...")
    pm_wr = fetch_polymarket_win_rate()
    poly_full = fetch_polymarket()
    if poly_full["positions"] or poly_full.get("total_account", 0) > 0:
        pm_inception = 222.00  # confirmed by Novaire Mar 15  # reset 2026-03-03
        pm_rows = ""
        # Re-fetch with full data for portfolio page
        try:
            import urllib.request as _ur
            _proxy = "0xC1541b2af765e4d1013337084D889d0DB302Aa0e"
            _req = _ur.Request(f"https://data-api.polymarket.com/positions?user={_proxy}", headers={"User-Agent": "Mozilla/5.0"})
            with _ur.urlopen(_req, timeout=10) as _resp:
                _positions = json.loads(_resp.read())
            pm_pos_val = 0
            open_positions = []
            for _p in _positions:
                _val = float(_p.get("currentValue", 0))
                if _val < 0.01:
                    continue
                _title = _p.get("title", "?")
                if len(_title) > 55:
                    _title = _title[:52] + "..."
                _pnl = float(_p.get("percentPnl", 0))
                _init = float(_p.get("initialValue", 0))
                pm_pos_val += _val
                open_positions.append({
                    "title": _title,
                    "outcome": _p.get("outcome", ""),
                    "value": _val,
                    "init": _init,
                    "pnl": _pnl,
                })
            open_positions.sort(key=lambda x: x["value"], reverse=True)
            for _p in open_positions[:4]:
                _pnl = _p["pnl"]
                _pnl_color = "#4ade80" if _pnl >= 0 else "#f87171"
                _pnl_str = f"+{_pnl:.1f}%" if _pnl >= 0 else f"{_pnl:.1f}%"
                pm_rows += f'<tr><td style="font-size:.75rem">{_p["outcome"]} · {_p["title"]}</td><td style="text-align:right;font-size:.75rem;color:{_pnl_color};font-weight:600">{_pnl_str}</td></tr>'
            pm_total = poly_full.get("total_account", pm_pos_val)
            pm_cash = pm_total - pm_pos_val
        except:
            pm_rows = ""
            pm_total = 0
            pm_cash = 0
            pm_inception = 222.00  # confirmed by Novaire Mar 15  # reset 2026-03-03

        bot_accounts_html += f"""<div class="card">
    <div class="card-title">🎰 Polymarket — Barron147</div>
    <div style="display:flex;justify-content:space-between;padding:4px 0;font-size:.7rem;color:var(--mute)"><span>Account: Barron147</span><span>Total: ${pm_total:.2f}</span></div>
    <div style="display:flex;justify-content:space-between;padding:4px 0 8px;font-size:.75rem;border-bottom:1px solid var(--border)"><span>Wins vs Losses</span><span>{pm_wr['wins']}W / {pm_wr['losses']}L · {pm_wr['total']} trades</span></div>
    <div class="collapse-toggle" style="font-size:.65rem;font-weight:600;color:var(--gold);letter-spacing:.1em;text-transform:uppercase;margin-top:6px">Top 4 Open Bets</div>
    <div><table style="width:100%;border-collapse:collapse">
      <tr style="font-size:.65rem;color:var(--mute);border-bottom:1px solid var(--border)"><th style="text-align:left;padding:4px 0">Contract</th><th style="text-align:right">Open ROI</th></tr>
      {pm_rows}
      <tr style="border-top:1px solid var(--border)"><td style="font-size:.75rem;padding-top:6px">💵 Cash</td><td style="text-align:right;font-size:.75rem;padding-top:6px">${pm_cash:.2f}</td></tr>
    </table></div>
  </div>"""

    # Alpaca — unified Livermore Darvis view
    alpaca_full = fetch_alpaca()
    if alpaca_full.get("funded"):
        all_positions = (alpaca_full.get("tier2_positions", []) + alpaca_full.get("tier1_positions", []))
        all_positions.sort(key=lambda p: float(p.get("market_value", 0)), reverse=True)

        rows = ""
        for _ap in all_positions:
            _sym = _ap.get("symbol", "?")
            _side = "Long" if _ap.get("side") == "long" else "Short"
            _mval = float(_ap.get("market_value", 0))
            _cost = float(_ap.get("cost", _ap.get("cost_basis", 0)))
            _pnl = float(_ap.get("pct_pnl", 0))
            _pnl_color = "#4ade80" if _pnl >= 0 else "#f87171"
            _pnl_str = f"+{_pnl:.1f}%" if _pnl >= 0 else f"{_pnl:.1f}%"
            rows += f'<tr><td style="font-size:.75rem">{_side} · {_sym}</td><td style="text-align:right;font-size:.75rem">${_cost:.2f}</td><td style="text-align:right;font-size:.75rem">${_mval:.2f}</td><td style="text-align:right;font-size:.75rem;color:{_pnl_color};font-weight:600">{_pnl_str}</td></tr>'
        if not rows:
            rows = '<tr><td colspan="4" style="font-size:.75rem;color:var(--mute);padding:4px 0">No open positions</td></tr>'

        cash_total = float(alpaca_full.get("cash", 0))
        total_equity = float(alpaca_full.get("equity", 0))
        total_roi = float(alpaca_full.get("inception_roi", 0))
        total_roi_color = "#4ade80" if total_roi >= 0 else "#f87171"
        total_roi_str = f"+{total_roi:.1f}%" if total_roi >= 0 else f"{total_roi:.1f}%"
        total_realized = float(alpaca_full.get("t1_realized", 0)) + float(alpaca_full.get("t2_realized", 0))
        total_trades = int(alpaca_full.get("t1_trade_count", 0)) + int(alpaca_full.get("t2_trade_count", 0))
        total_realized_color = "#4ade80" if total_realized >= 0 else "#f87171"
        total_realized_str = f"+${total_realized:.2f}" if total_realized >= 0 else f"-${abs(total_realized):.2f}"

        bot_accounts_html += f"""<div class="card">
    <div class="card-title">🦙 Livermore Darvis</div>
    <div style="display:flex;justify-content:space-between;padding:4px 0;font-size:.7rem;color:var(--mute)"><span>Inception: $500.00 · {total_trades} trades</span><span>Unified Alpaca book</span></div>
    <table style="width:100%;border-collapse:collapse">
      <tr style="font-size:.65rem;color:var(--mute);border-bottom:1px solid var(--border)"><th style="text-align:left;padding:4px 0">Position</th><th style="text-align:right">Cost</th><th style="text-align:right">Value</th><th style="text-align:right">P&L</th></tr>
      {rows}
      <tr style="border-top:1px solid var(--border)"><td style="font-size:.75rem;padding-top:6px">💵 Cash</td><td></td><td style="text-align:right;font-size:.75rem;padding-top:6px">${cash_total:.2f}</td><td></td></tr>
    </table>
    <div style="display:flex;justify-content:space-between;padding:5px 0 0;border-top:1px solid var(--border);font-size:.75rem"><span style="color:var(--mute)">Realized P&amp;L</span><span style="color:{total_realized_color};font-weight:600">{total_realized_str}</span></div>
    <div style="display:flex;justify-content:space-between;padding:4px 0 0;font-size:.85rem;font-weight:700"><span>Total: ${total_equity:.2f}</span><span style="color:{total_roi_color}">Inception ROI: {total_roi_str}</span></div>
  </div>"""

    # ── Evolution Fund ──
    print("  🏛️ Fetching Evolution Fund positions...")
    evo_fund_html = ""
    evo_snapshot = {}
    try:
        EVO_HOLDINGS = [
            {"ticker": "PHYS",  "name": "Gold (Sprott)",         "shares": 16827, "avg_entry": 36.95},
            {"ticker": "URNM",  "name": "Uranium",               "shares": 6000,  "avg_entry": 67.72},
            {"ticker": "GRID",  "name": "Grid Infrastructure",   "shares": 2177,  "avg_entry": 176.81},
            {"ticker": "PSLV",  "name": "Silver (Sprott)",       "shares": 8545,  "avg_entry": 29.02},
            {"ticker": "COPX",  "name": "Copper Miners",         "shares": 2000,  "avg_entry": 83.96},
            {"ticker": "COPP",  "name": "Copper",                "shares": 5047,  "avg_entry": 43.60},
            {"ticker": "URNJ",  "name": "Jr Uranium",            "shares": 3151,  "avg_entry": 34.91},
            {"ticker": "SGDJ",  "name": "Gold Miners",           "shares": 1002,  "avg_entry": 109.73},
            {"ticker": "AAPL",  "name": "Apple",                 "shares": 31,    "avg_entry": 261.55},
            {"ticker": "CEG",   "name": "Constellation Energy",  "shares": 177,   "avg_entry": 312.30},
            {"ticker": "VST",   "name": "Vistra Energy",         "shares": 322,   "avg_entry": 170.54},
        ]
        EVO_BTC = {"shares": 6.72, "avg_entry": 65500.00, "name": "Bitcoin (8% alloc)"}

        # Fetch live prices
        evo_tickers = [h["ticker"] for h in EVO_HOLDINGS]
        import yfinance as _yf
        _evo_data = _yf.download(evo_tickers, period="2d", progress=False)
        _evo_close = _evo_data.get("Close", _evo_data.get(("Close",), None))

        # Bitcoin is an Evolution Fund position, not the removed Kraken margin book.
        btc_price = None
        try:
            _btc = _yf.Ticker("BTC-USD")
            btc_price = float(_btc.history(period="1d")["Close"].iloc[-1])
        except:
            btc_price = EVO_BTC["avg_entry"]

        evo_rows = ""
        evo_total_value = 0
        evo_total_cost = 0

        for h in EVO_HOLDINGS:
            sym = h["ticker"]
            shares = h["shares"]
            avg = h["avg_entry"]
            cost = shares * avg
            try:
                if hasattr(_evo_close, 'columns') and sym in _evo_close.columns:
                    price = float(_evo_close[sym].dropna().iloc[-1])
                else:
                    price = float(_evo_close[sym].dropna().iloc[-1]) if sym in str(_evo_close) else avg
            except:
                price = avg
            value = shares * price
            gl = value - cost
            gl_pct = (gl / cost * 100) if cost > 0 else 0
            evo_total_value += value
            evo_total_cost += cost
            evo_snapshot[sym] = {"price": round(price, 2), "gl": round(gl_pct, 1)}
            gl_color = "#4ade80" if gl >= 0 else "#f87171"
            gl_str = f"+${gl:,.0f}" if gl >= 0 else f"-${abs(gl):,.0f}"
            pct_str = f"+{gl_pct:.1f}%" if gl_pct >= 0 else f"{gl_pct:.1f}%"
            evo_rows += f'<tr><td class="ticker">{sym}</td><td style="font-size:.78rem">{h["name"]}</td><td style="text-align:right;font-size:.78rem">{shares:,}</td><td style="text-align:right;font-size:.78rem">${price:,.2f}</td><td style="text-align:right;font-size:.78rem">${value:,.0f}</td><td style="text-align:right;font-size:.78rem;color:{gl_color}">{gl_str}</td><td style="text-align:right;font-size:.78rem;color:{gl_color};font-weight:600">{pct_str}</td></tr>'

        btc_cost = EVO_BTC["shares"] * EVO_BTC["avg_entry"]
        btc_value = EVO_BTC["shares"] * btc_price
        btc_gl = btc_value - btc_cost
        btc_pct = (btc_gl / btc_cost * 100) if btc_cost > 0 else 0
        evo_total_value += btc_value
        evo_total_cost += btc_cost
        evo_snapshot["BTC"] = {"price": round(btc_price, 2), "gl": round(btc_pct, 1)}
        btc_color = "#4ade80" if btc_gl >= 0 else "#f87171"
        btc_gl_str = f"+${btc_gl:,.0f}" if btc_gl >= 0 else f"-${abs(btc_gl):,.0f}"
        btc_pct_str = f"+{btc_pct:.1f}%" if btc_pct >= 0 else f"{btc_pct:.1f}%"
        evo_rows += f'<tr><td class="ticker">BTC</td><td style="font-size:.78rem">{EVO_BTC["name"]}</td><td style="text-align:right;font-size:.78rem">{EVO_BTC["shares"]}</td><td style="text-align:right;font-size:.78rem">${btc_price:,.2f}</td><td style="text-align:right;font-size:.78rem">${btc_value:,.0f}</td><td style="text-align:right;font-size:.78rem;color:{btc_color}">{btc_gl_str}</td><td style="text-align:right;font-size:.78rem;color:{btc_color};font-weight:600">{btc_pct_str}</td></tr>'

        evo_gl_total = evo_total_value - evo_total_cost
        evo_roi = (evo_gl_total / evo_total_cost * 100) if evo_total_cost > 0 else 0
        evo_roi_color = "#4ade80" if evo_roi >= 0 else "#f87171"
        evo_roi_str = f"+{evo_roi:.2f}%" if evo_roi >= 0 else f"{evo_roi:.2f}%"
        evo_gl_str = f"+${evo_gl_total:,.0f}" if evo_gl_total >= 0 else f"-${abs(evo_gl_total):,.0f}"

        evo_fund_html = f"""<div class="card">
    <div class="card-title">🏛️ Evolution Fund <a href="/portfolio/evolutionfund" style="margin-left:8px;font-size:.5rem;font-weight:600;letter-spacing:.1em;color:#22d3ee;background:rgba(34,211,238,.1);border:1px solid rgba(34,211,238,.25);padding:2px 8px;border-radius:10px;text-decoration:none;vertical-align:middle">⚡ CC Strategy</a></div>
    <div style="display:flex;justify-content:space-between;padding:4px 0 8px;font-size:.68rem;color:var(--mute)"><span>Negentropy Evolution Fund · Live Positions</span><span><a href="https://evolution.fund" style="color:var(--gold);text-decoration:none">evolution.fund</a></span></div>
    <div class="collapse-toggle" style="font-size:.65rem;font-weight:600;color:var(--gold);letter-spacing:.1em;text-transform:uppercase">Holdings ({len(EVO_HOLDINGS)+1} positions)</div>
    <div><table class="portfolio-table">
      <thead><tr>
        <th>Ticker</th><th>Position</th>
        <th style="text-align:right">Shares</th>
        <th style="text-align:right">Price</th>
        <th style="text-align:right">Value</th>
        <th style="text-align:right">G/L $</th>
        <th style="text-align:right">G/L %</th>
      </tr></thead>
      <tbody>{evo_rows}</tbody>
    </table></div>
    <div class="totals-row">
      <div class="total-item">
        <div class="total-label">Total Value</div>
        <div class="total-value usd">${evo_total_value:,.0f}</div>
      </div>
      <div class="total-item">
        <div class="total-label">Total Cost</div>
        <div class="total-value" style="color:var(--dim)">${evo_total_cost:,.0f}</div>
      </div>
      <div class="total-item">
        <div class="total-label">Gain/Loss</div>
        <div class="total-value" style="color:{evo_roi_color}">{evo_gl_str}</div>
      </div>
      <div class="total-item">
        <div class="total-label">ROI</div>
        <div class="total-value" style="color:{evo_roi_color}">{evo_roi_str}</div>
      </div>
    </div>
  </div>"""
        print(f"    ✅ Evolution Fund: {len(EVO_HOLDINGS)+1} positions, ${evo_total_value:,.0f} total value")
    except Exception as e:
        print(f"    ❌ Evolution Fund error: {e}")
        evo_fund_html = ""

    # Keep /portfolio/evolutionfund hardcoded strategy page in sync with daily prices/G-L
    try:
        evo_strategy_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio", "evolutionfund", "index.html")
        if evo_snapshot and os.path.exists(evo_strategy_path):
            import re
            with open(evo_strategy_path, "r", encoding="utf-8") as f:
                evo_html = f.read()

            updated_count = 0
            for ticker, vals in evo_snapshot.items():
                pattern = rf'(\{{\s*ticker:\s*"{re.escape(ticker)}"[^\}}]*?price:\s*)([-0-9.]+)(,\s*gl:\s*)([-0-9.]+)'
                repl = lambda m, p=vals["price"], g=vals["gl"]: f'{m.group(1)}{p:.2f}{m.group(3)}{g:.1f}'
                evo_html, n = re.subn(pattern, repl, evo_html, count=1)
                updated_count += n

            if updated_count:
                with open(evo_strategy_path, "w", encoding="utf-8") as f:
                    f.write(evo_html)
                print(f"    ✅ Evolution CC strategy page refreshed ({updated_count} tickers)")
            else:
                print("    ⚠️  Evolution CC strategy page: no ticker matches found")
        else:
            print("    ⚠️  Evolution CC strategy page: skipped (no snapshot or file missing)")
    except Exception as e:
        print(f"    ⚠️  Evolution CC strategy page update failed: {e}")

    portfolio_html = render_portfolio_html(
        portfolio_data, catalysts, fx, holdings_source=holdings_source, gs_meta=gs_meta,
        bot_accounts_html=bot_accounts_html, evo_fund_html=evo_fund_html,
        net_worth_tracker_html=net_worth_tracker_html,
    )

    required_thai_markers = [
        'data-thai-expat-brief="verified"',
        'data-thai-url="http',
        'thai-news-summary',
        'Live check marker: expat brief has a real source',
    ]
    missing_thai_markers = [m for m in required_thai_markers if m not in html]
    if missing_thai_markers:
        raise RuntimeError(f"Thailand expat brief failed verification markers: {missing_thai_markers}")

    retired_hits = [marker for marker in RETIRED_HOME_MARKERS if marker in html]
    if retired_hits:
        raise RuntimeError(
            "Retired Novaire Signal product-voting UI detected; refusing to generate/deploy: "
            + repr(retired_hits)
        )

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    # Also copy to repo root for git push deploy
    import shutil
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    repo_index = os.path.join(repo_dir, "index.html")
    shutil.copy2(OUTPUT, repo_index)

    # Portfolio page → portfolio/index.html
    portfolio_dir = os.path.join(repo_dir, "portfolio")
    os.makedirs(portfolio_dir, exist_ok=True)
    portfolio_path = os.path.join(portfolio_dir, "index.html")
    with open(portfolio_path, "w", encoding="utf-8") as f:
        f.write(portfolio_html)
    print(f"  ✅ HTML saved to {OUTPUT} + {repo_index} ({len(html):,} bytes)")
    print(f"  ✅ Portfolio page saved to {portfolio_path} ({len(portfolio_html):,} bytes)")

    # ── Write stats.json for cron Telegram summary ──
    try:
        stats_total_usd = (gs_meta.get("total_usd") if gs_meta else None)
        stats_total_cad = (gs_meta.get("total_cad") if gs_meta else None)
        stats_roi_pct_str = (gs_meta.get("roi_pct_str") if gs_meta else None)

        # Google Sheet layout occasionally shifts and drops summary cells while
        # holdings still load. Keep heartbeat/cron summaries useful by falling
        # back to the computed portfolio values already used to render the page.
        if not stats_total_usd:
            computed_usd = sum((v.get("value") or 0) for v in (portfolio_data or {}).values())
            stats_total_usd = round(computed_usd, 2) if computed_usd else None
        if not stats_total_cad and stats_total_usd:
            stats_total_cad = round(stats_total_usd * fx.get("usdcad", 1), 2)
        if stats_roi_pct_str:
            try:
                float(str(stats_roi_pct_str).replace("%", "").strip())
            except Exception:
                stats_roi_pct_str = None
        if not stats_roi_pct_str and stats_total_cad and PORT_BASIS_CAD:
            stats_roi_pct_str = f"{((stats_total_cad - PORT_BASIS_CAD) / PORT_BASIS_CAD * 100):.2f}%"

        stats = {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "portfolio": {
                "total_cad": stats_total_cad,
                "total_usd": stats_total_usd,
                "roi_pct_str": stats_roi_pct_str,
            },
            "polymarket": {
                "total_account": poly.get("total_account", 0) if poly else 0,
            }
        }
        stats_path = os.path.join(repo_dir, "stats.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f)
        print(f"  ✅ stats.json written")
    except Exception as e:
        print(f"  ⚠️  stats.json failed: {e}")

if __name__ == "__main__":
    main()
