#!/usr/bin/env python3
"""
Novaire Signal — Daily Brief Generator
Generates index.html with premium dark + gold aesthetic + live data
"""

import requests
import json
import math
import os
import sys
import time
import traceback
from html import escape
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
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
    {"ticker": "_FVL_FALLBACK",  "display": "FVL",   "name": "FreeGold Ventures",   "shares": 10000, "currency": "CAD", "sector": "Gold"},
    {"ticker": "DML.TO", "display": "DML",   "name": "Denison",             "shares": 1000,  "currency": "CAD", "sector": "Uranium"},
    {"ticker": "BNNLF",  "display": "BNNLF", "name": "Bannerman Energy",    "shares": 1300,  "currency": "USD", "sector": "Uranium"},
    {"ticker": "_MAXX_FALLBACK",  "display": "MAXX",  "name": "Power Mining Corp",   "shares": 2000,  "currency": "CAD", "sector": "Silver"},
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
    # MOLY.V (GreenLand Resources) - not on Yahoo Finance; hardcoded fallback (CAD)
    {"ticker": "_MOLY_FALLBACK", "display": "MOLY", "name": "GreenLand Resources", "shares": 5000, "currency": "CAD", "sector": "Molybdenum"},
]

# Hardcoded fallback prices (USD) for tickers unavailable on Yahoo Finance
FALLBACK_PRICES = {
    "_MOLY_FALLBACK":  1.65,  # GreenLand Resources (MOLY.V) - CAD, verified Feb 18 2026
    "_FVL_FALLBACK":   1.32,  # FreeGold Ventures (FVL.V) - CAD, verified Feb 18 2026
    "_MAXX_FALLBACK":  1.12,  # Power Mining Corp (MAXX.V) - CAD, verified Feb 18 2026
}

HOLDINGS_MAP = {h["ticker"]: {"shares": h["shares"], "name": h["name"], "display": h.get("display", h["ticker"].split(".")[0])} for h in HOLDINGS}
SECTORS      = {h["ticker"]: h["sector"] for h in HOLDINGS}

SECOND_RENAISSANCE = {
    "channel_url": "https://www.youtube.com/channel/UC0-4nIbz6OCjUa08WO0-vFw",
    "episode_title": "How Stress Makes You Stronger (Hormesis Explained)",
    "episode_url": "https://www.youtube.com/watch?v=TUgELHZm6ZU",
    "thumbnail_url": "https://img.youtube.com/vi/TUgELHZm6ZU/hqdefault.jpg",
    "episode_blurb": "DeFleur and Novaire explore hormesis: why controlled stress — from exercise, fasting, sauna, cold exposure, Stoicism, psychedelics, and debate — can make biological, psychological, and civic systems stronger.",
}

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
    fomc_date = _date(2026, 7, 29)
    days_until = (fomc_date - today).days
    return {
        "next_decision": "July 29, 2026",
        "days_until": days_until,
        "fed_funds_rate": "3.50\u20133.75%",
        "next_meeting": "July FOMC",
        "hold_pct": 89,
        "cut_25bps_pct": 3,
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

UPDOG_SUGGESTIONS_JS = """{
  motr:[
    {title:"Relationship stage filter", idea:"Add under-1-year, 1–2, 2–5, and 5+ year filters to the MOTR relationship game so couples get questions matched to their actual season.", action:"Implement MOTR relationship-stage filtering and tailor the card pool by stage."},
    {title:"Mastermind icebreaker pack", idea:"Add questions that make younger men discuss reading, discipline, money, health, relationships, family, and purpose without turning the room into a therapy swamp.", action:"Build a MOTR Mastermind question category for integrated self-improvement."},
    {title:"Love languages into actions", idea:"Turn love-language answers into weekly actions: words, time, touch, service, and gifts translated into concrete relationship behaviors.", action:"Add actionable love-language prompts and follow-up commitments to the relationship game."},
    {title:"Score report after each round", idea:"After a game session, generate a short relationship or mastermind signal report: strengths, friction, one next conversation, and one tiny practice.", action:"Add end-of-round MOTR signal reports."}
  ],
  retreat:[
    {title:"Retreat readiness quiz", idea:"Add a short quiz that tells a visitor whether they are ready for the Bangkok/Thailand MOTR retreat, then routes them to apply, waitlist, or warm-up content.", action:"Build a MOTR retreat readiness quiz and CTA flow."},
    {title:"Founder-style retreat itinerary", idea:"Show a sample day: training, deep work, mastermind, Thai food, nightlife optionality, recovery. Make the offer feel real, not brochure vapor.", action:"Add a sample MOTR retreat itinerary section."},
    {title:"Retreat objection killer", idea:"Add a tight FAQ for price, location, safety, fitness level, dating/social anxiety, and what kind of man should not come.", action:"Add a conversion-focused MOTR retreat FAQ."},
    {title:"Application signal score", idea:"Let applicants self-rate ambition, health, discipline, social courage, and coachability so the retreat attracts builders, not spiritual tourists with linen pants.", action:"Add a retreat application signal score."}
  ],
  energy:[
    {title:"Battery icon daily check-in", idea:"Make the Energy Maxxing app start with a battery score and one question: sleep, food, training, sunlight, stress, libido, or mood — what is draining the system today?", action:"Add a battery-score check-in to the Energy Maxxing app."},
    {title:"Energy leak detector", idea:"Have the app identify the top energy leak of the day: alcohol, doomscrolling, poor food, no sunlight, bad sleep, overwork, or unresolved conflict.", action:"Build an Energy Maxxing leak detector."},
    {title:"30-day prime experiment", idea:"Turn energy maxxing into a monthly experiment with one metric, one habit, and one visible proof of progress.", action:"Add a 30-day Energy Maxxing experiment mode."},
    {title:"Sleep debt warning", idea:"If sleep is poor, the app should stop giving heroic productivity advice and prescribe a recovery day like a civilized tyrant.", action:"Add sleep-aware recommendations to the Energy Maxxing app."}
  ],
  signal:[
    {title:"Daily meditation source pool", idea:"Expand the Daily Meditation block with more Stoic, practical philosophy, psychology, and investing wisdom — Marcus, Seneca, Epictetus, Frankl, Munger, Taleb.", action:"Expand Novaire Signal's Daily Meditation source pool."},
    {title:"One-tap product vote", idea:"Keep this Updog section as a daily yes/no product senate: four ideas, one click, less scattered ambition, more compounding execution.", action:"Improve the Novaire Signal Updog voting workflow."},
    {title:"Marketing channel nudge", idea:"Add one daily distribution suggestion: newsletter, X thread, short clip, retreat lead magnet, relationship-game teaser, or BOTR install pitch.", action:"Add daily marketing-channel suggestions to Novaire Signal."},
    {title:"Personal cockpit priority", idea:"Add a single daily keystone: the one action that moves health, wealth, product, or relationships furthest today.", action:"Add a daily keystone priority block to Novaire Signal."}
  ],
  podcast:[
    {title:"Three-topic wisdom slate", idea:"Suggest three podcast or clip topics from the zeitgeist, X discourse, and Novaire's core telos: wisdom, better mental models, deeper conversations, and stronger relationships.", action:"Generate three topic candidates for Novaire to rank today."},
    {title:"Relationship mental model clip", idea:"Turn a trending dating, marriage, friendship, or loneliness debate into a deeper clip about incentives, attachment, agency, status, and honest conversation.", action:"Draft one relationship-focused clip topic with a sharp mental model."},
    {title:"Zeitgeist through telos", idea:"Take one trending event or claim and filter it through Seeking Wisdom: what does it reveal about human nature, institutions, incentives, or courage?", action:"Create a podcast topic that turns the current thing into a durable lesson."},
    {title:"Conversation depth prompt", idea:"Find a trending idea that could become a dinner-table or mastermind conversation rather than a hot take: AI, money, masculinity, health, geopolitics, or meaning.", action:"Draft one deep-conversation prompt and two short-clip hooks."}
  ]
}"""

UPDOG_ACTION_STEPS_JS = """{
  motr:[
    {title:"Define the player", ask:"Who is this game for first: girlfriend, date, retreat guest, mastermind brother, or a man testing himself alone?", action:"Run one 5-minute relationship-game session today and write down where the card felt sharp, soft, or confusing."},
    {title:"Test the room", ask:"Who can play one round this week so the game stops being theory and starts bleeding real data?", action:"Send one test link and ask for the three cards that created the most honest conversation."},
    {title:"Retreat fit", ask:"Which retreat applicant or shortlist man should play this before arrival?", action:"Pick one retreat candidate and use the game as a social-depth filter before the next call."},
    {title:"Category truth", ask:"Which category reveals the most value fastest: love languages, conflict, money, health, desire, or family scripts?", action:"Play only that category for five minutes and mark one card to improve."}
  ],
  retreat:[
    {title:"Deposit scoreboard", ask:"How many $500 retreat deposits are in, how many verbal yeses, and who needs a direct close?", action:"Update the deposit count and name the next one man who should receive a personal nudge today."},
    {title:"Shortlist pressure", ask:"What is the current retreat shortlist: A-list, maybe, and not-yet?", action:"Move one person into a clearer bucket and decide the next message or disqualifier."},
    {title:"Fast proof", ask:"What proof would make the retreat feel inevitable instead of conceptual: itinerary, room photos, training day, testimonials, or founder video?", action:"Ship one proof asset or outline the exact missing asset."},
    {title:"Deadline reality", ask:"What decision is coming up fast: venue, pricing, deposit deadline, application cutoff, or first attendee call?", action:"Choose the one decision that removes the most ambiguity today."}
  ],
  energy:[
    {title:"Use it yourself", ask:"Did you open Energy Maxxing today and log the battery drain honestly?", action:"Use the app for five minutes, select today’s drain, then write one fixable leak."},
    {title:"One personal metric", ask:"Which metric would make the app more useful tomorrow: sleep, sunlight, training, food, stress, libido, or mood?", action:"Track that one metric once today instead of pretending seven metrics is discipline."},
    {title:"Friction audit", ask:"Where did the app feel slow, vague, ugly, or unnecessary when you used it?", action:"Remove or rewrite one piece of friction before adding another shiny widget."},
    {title:"Recovery command", ask:"If the battery score is low, should the app prescribe recovery, training, sunlight, food, or stress reduction first?", action:"Write one if-low-then-do rule that would actually help you today."}
  ],
  signal:[
    {title:"Remove one thing", ask:"What can come out of Novairecito today: duplicate block, weak feed, stale metric, noisy widget, or vanity data?", action:"Name one thing to remove so Signal gets sharper instead of fatter."},
    {title:"Add one signal", ask:"What one thing should Novaire Signal add: product telos question, user test reminder, retreat deposit scoreboard, or personal cockpit action?", action:"Add or draft one block that compounds the product instead of decorating the dashboard."},
    {title:"Sharper Updog", ask:"Which Updog category felt dumb today, and what would a smarter version understand about the product?", action:"Rewrite one suggestion with more context about the actual user, business model, or next bottleneck."},
    {title:"Signal versus noise", ask:"What did Novaire Signal show today that did not change a decision?", action:"Cut, shrink, or demote one non-decision item."}
  ],
  podcast:[
    {title:"Rank three topics", ask:"Which three podcast or clip topics would create wisdom, better mental models, deeper conversation, or a stronger relationship today?", action:"Write down three topic candidates from X or the zeitgeist, then rank them 1 to 3 by depth, not virality."},
    {title:"Mental model hunt", ask:"What current debate reveals a reusable mental model instead of just another opinion?", action:"Pick one trend and name the model: incentives, identity threat, status games, optionality, attachment, entropy, or courage."},
    {title:"Relationship conversation", ask:"What topic would help a couple, friend group, or mastermind room speak more honestly?", action:"Draft one question that would make people reveal values, fear, desire, or standards without turning it into therapy slop."},
    {title:"X scanner to clip", ask:"Which X signal at the top of the feed deserves Novaire's interpretation?", action:"Choose one top-engagement post and turn it into a clip thesis plus two hooks."}
  ]
}"""

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
    Fallback to hardcoded picks on any failure.
    """
    rec_movie = {"label": "📺 Now Watching", "title": "Diamond League Track & Field", "meta": "World Athletics · Sprinting, distance, jumps, throws", "summary": "Elite track and field as a weekly performance study: speed, pressure, tactics, recovery, and the psychology of peak humans under the clock."}
    rec_book  = {"label": "📖 Now Reading",  "title": "The Trickster Archetype", "meta": "James' pick · Psychology/Myth", "summary": "A study of the trickster pattern: mischief, boundary crossing, disruption, transformation, and the strange wisdom that enters through chaos."}
    return rec_movie, rec_book

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
        movie_title, movie_platform = candidates[0] if candidates else ("Margin Call", "Prime")
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

GSHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1rqRNI6z3rqXGCMlPbsbVEJUw82DCskU9qf9sKEXMnak/export?format=csv"

# Map sheet exchange/ticker strings → Yahoo Finance tickers
EXCHANGE_TO_TICKER = {
    "CNSX:HG":  "HG.CN",
    "TSE:GLO":  "GLO.TO",
    "FVL":      "_FVL_FALLBACK",
    "MOLY":     "_MOLY_FALLBACK",
    "DML":      "DML.TO",
    "BNNLF":    "BNNLF",
    "MAXX":     "_MAXX_FALLBACK",
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

    holdings = []
    meta     = {}
    seen     = set()

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

        name        = row[2].strip()
        ex_ticker   = row[3].strip()
        price_str   = row[5].strip()
        buy_str     = row[8].strip()
        shares_str  = row[9].strip()
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

    return holdings, meta


def fetch_portfolio(usdcad=1.365, audusd=0.63):
    """Fetch portfolio prices. Reads holdings from Google Sheet, prices from yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        return {}

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

    results = {}
    for h in holdings_source:
        ticker   = h["ticker"]
        shares   = h["shares"]
        currency = h.get("currency", "CAD")

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

def fetch_catalysts(top3_tickers):
    """Fetch news for top 3 tickers. Returns dict with freshness info."""
    try:
        import yfinance as yf
    except ImportError:
        return {}

    cats = {}
    now = datetime.now(timezone.utc)
    fresh_cutoff = now - timedelta(hours=48)  # 48h hard cutoff — no old fluff

    # Map fallback tickers to real Yahoo Finance tickers for news
    FALLBACK_NEWS_MAP = {
        "_FVL_FALLBACK": "FVL.V",
        "_MOLY_FALLBACK": "MOLY.V",
    }

    for ticker in top3_tickers:
        lookup_ticker = FALLBACK_NEWS_MAP.get(ticker, ticker)
        if lookup_ticker.startswith("_"):
            cats[ticker] = None
            continue
        try:
            t = yf.Ticker(lookup_ticker)
            news = t.news
            if news:
                item = news[0]
                title = (item.get("content", {}).get("title")
                         or item.get("title", "No title"))
                pub_raw = (item.get("content", {}).get("pubDate")
                           or item.get("providerPublishTime", ""))
                # Normalise to datetime
                pub_dt = None
                if pub_raw:
                    try:
                        if isinstance(pub_raw, (int, float)):
                            pub_dt = datetime.fromtimestamp(pub_raw, tz=timezone.utc)
                        else:
                            pub_dt = datetime.fromisoformat(str(pub_raw).replace("Z", "+00:00"))
                    except Exception:
                        pass
                pub_str = pub_dt.strftime("%b %-d") if pub_dt else "—"
                fresh = (pub_dt and pub_dt >= fresh_cutoff)
                source = (item.get("content", {}).get("provider", {}).get("displayName")
                          or item.get("publisher", ""))
                cats[ticker] = {
                    "title":  title,
                    "date":   pub_str,
                    "source": source,
                    "fresh":  fresh,
                }
            else:
                cats[ticker] = None
        except Exception:
            cats[ticker] = None
    return cats

def fetch_commodities():
    try:
        import yfinance as yf
    except ImportError:
        return {}

    symbols = {
        "GC=F": {"name": "Gold",     "unit": "/oz",  "cls": "c-gold"},
        "SI=F": {"name": "Silver",   "unit": "/oz",  "cls": "c-silver"},
        "HG=F": {"name": "Copper",   "unit": "/lb",  "cls": "c-copper"},
        "CL=F": {"name": "Oil (WTI)","unit": "/bbl", "cls": "c-oil"},
        "PA=F": {"name": "Palladium","unit": "/oz",  "cls": "c-palladium"},
    }
    results = {}
    for sym, meta in symbols.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            if len(hist) >= 2:
                p  = float(hist["Close"].iloc[-1])
                pp = float(hist["Close"].iloc[-2])
                chg = (p - pp) / pp * 100
            elif len(hist) == 1:
                p = float(hist["Close"].iloc[-1]); chg = None
            else:
                p = None; chg = None
            results[sym] = {**meta, "price": p, "change": chg}
        except Exception:
            results[sym] = {**meta, "price": None, "change": None}

    # Uranium spot price — scraped from tradingeconomics (U3O8 $/lb)
    try:
        r = requests.get("https://tradingeconomics.com/commodity/uranium",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        import re
        m = re.search(r'Uranium (?:fell|rose|remained)[^.]*?(\d+\.?\d*)\s*USD/Lbs', r.text)
        if m:
            spot = float(m.group(1))
            results["URANIUM_SPOT"] = {"name": "Uranium", "unit": "/lb", "cls": "c-uranium",
                                       "price": spot, "change": None}
        else:
            results["URANIUM_SPOT"] = {"name": "Uranium", "unit": "/lb", "cls": "c-uranium",
                                       "price": 88.80, "change": None}
    except Exception:
        results["URANIUM_SPOT"] = {"name": "Uranium", "unit": "/lb", "cls": "c-uranium",
                                   "price": 88.80, "change": None}
    return results

def fetch_crypto():
    all_syms = {
        "BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "SUI": "SUIUSDT",
        "XRP": "XRPUSDT", "ADA": "ADAUSDT", "TON": "TONUSDT", "ZEC": "ZECUSDT",
    }
    results = {}
    for coin, sym in all_syms.items():
        try:
            r = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={sym}", timeout=8)
            data = r.json()
            price = float(data.get("lastPrice", 0))
            chg   = float(data.get("priceChangePercent", 0))
            results[coin] = {"price": price, "change": chg}
        except Exception:
            results[coin] = {"price": None, "change": None}
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

def build_donut(allocations):
    COLORS = ["#c9a84c","#5a7bc4","#9470c8","#2a9d8f","#e63946","#f4a261","#a8dadc","#e9c46a","#264653"]
    r = 25; cx = cy = 50
    circumference = 2 * math.pi * r
    total = sum(v for _, v, _ in allocations)
    if total == 0: return ""
    offset = 0
    slices = []
    for i, (label, val, _) in enumerate(allocations):
        pct  = val / total
        dash = pct * circumference
        color = COLORS[i % len(COLORS)]
        slices.append(f'<circle r="{r}" cx="{cx}" cy="{cy}" fill="transparent" '
                      f'stroke="{color}" stroke-width="50" '
                      f'stroke-dasharray="{dash:.2f} {circumference:.2f}" '
                      f'stroke-dashoffset="{-offset:.2f}" '
                      f'transform="rotate(-90 {cx} {cy})"/>')
        offset += dash
    slices.append(f'<circle r="15" cx="{cx}" cy="{cy}" fill="#0a0a0c"/>')
    return (f'<svg class="pie-chart" viewBox="0 0 100 100" style="width:120px;height:120px">'
            + "".join(slices) + "</svg>")

def build_legend(allocations, total_val):
    COLORS = ["#c9a84c","#5a7bc4","#9470c8","#2a9d8f","#e63946","#f4a261","#a8dadc","#e9c46a","#264653"]
    total = sum(v for _, v, _ in allocations)
    items = []
    for i, (label, val, _) in enumerate(allocations):
        pct   = val / total * 100 if total else 0
        color = COLORS[i % len(COLORS)]
        items.append(f'<div class="legend-item"><span class="legend-dot" style="background:{color}"></span>'
                     f'{label}<span class="legend-pct">{pct:.1f}%</span></div>')
    return "\n".join(items)

# ─────────────────────────────────────────────────────────────
# HTML GENERATION
# ─────────────────────────────────────────────────────────────

def render_html(weather, bangkok_news, zh_news, portfolio_data, catalysts,
                commodities, crypto, fx, zodiac, thai_word, motivation, rec_movie=None, rec_book=None, fx_rates=None, holdings_source=None, gs_meta=None, spanish_word=None, poly_html="", alpaca_html="", fed_signal=None, economies=None):

    now       = datetime.now(timezone.utc).astimezone(BKK_TZ)
    date_str  = now.strftime("%A, %B %-d, %Y")
    gen_time  = now.strftime("%H:%M ICT")

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
    canada_departure_date = _date(2026, 7, 13)
    trip_date = _date(2026, 8, 25)
    edc_thailand_date = _date(2026, 12, 18)
    mastermind_retreat_date = _date(2027, 1, 19)
    canada_countdown_text = countdown_label(canada_departure_date, "since Canada flight")
    trip_countdown_text = countdown_label(trip_date, "since departure")
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
            <td class="ticker">{display}</td>
            <td style="color:var(--dim);font-size:.8em">{name}</td>
            <td style="text-align:right">{int(shares):,}</td>
            <td style="text-align:right">{price_str}</td>
            <td style="text-align:right">{chg_html}</td>
            <td style="text-align:right;font-weight:600">{value_str}</td>
          </tr>"""

    # ── Allocation chart ──
    alloc_sorted = sorted(sector_totals.items(), key=lambda x: x[1], reverse=True)
    alloc_list   = [(s, v, "") for s, v in alloc_sorted]
    donut_svg    = build_donut(alloc_list)
    legend_html  = build_legend(alloc_list, total_usd)

    # ── Top 5 by value ──
    top5 = [t for t, *_ in port_sorted[:5]]

    # ── Catalysts HTML (top 5, 48h fresh only) ──
    # If ALL 5 have no news → one collapsed line. Otherwise show per-ticker lines.
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
              <span class="catalyst-headline" style="color:var(--dim);font-style:italic">No news within 48 hours.</span>
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
      <div class="fx-chip"><div class="fx-ccy">{d['icon']} {ccy}</div><span class="fx-rate">{val}</span></div>"""

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

    # ── Fed Signal HTML ──
    fed = fed_signal or fetch_fed_signal()
    days_label = f"{fed['days_until']} day{'s' if fed['days_until'] != 1 else ''}"
    fed_html = f"""
  <div class="card fed-card">
    <div class="fed-title">🏛️ Fed Signal</div>
    <div class="fed-grid">
      <div class="fed-grid-item">
        <div class="fed-grid-label">Rate</div>
        <div class="fed-grid-val" style="color:var(--gold)">{fed['fed_funds_rate']}</div>
      </div>
      <div class="fed-grid-item">
        <div class="fed-grid-label">Next FOMC</div>
        <div class="fed-grid-val" style="color:var(--text)">{fed['next_decision']}</div>
        <div class="fed-grid-sub">{days_label}</div>
      </div>
      <div class="fed-grid-item">
        <div class="fed-grid-label">Hold</div>
        <div class="fed-grid-val" style="color:var(--green)">{fed['hold_pct']}%</div>
      </div>
      <div class="fed-grid-item">
        <div class="fed-grid-label">Cut 25bp</div>
        <div class="fed-grid-val" style="color:var(--blue)">{fed['cut_25bps_pct']}%</div>
      </div>
    </div>
    <div style="font-size:.54rem;color:var(--mute);margin-top:8px;text-align:center">{fed['next_meeting']} probabilities · CME FedWatch</div>
  </div>"""

    # ── Top 5 Economies HTML: show only every two weeks on Monday ──
    eco_html = ""
    if show_biweekly_monday_section():
        eco_data = economies or fetch_top5_economies()
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
  <div class="card">
    <div class="card-title">🌍 Top 5 Economies · Biweekly Monday</div>
    <table class="eco-table">
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
  </div>"""

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
                     "XRP": "#346aa9","ADA": "#2a6df4","TON": "#0098ea","ZEC": "#f4b728"}
    crypto_html = ""
    for coin in ["BTC","ETH","SOL","SUI","XRP","ADA","TON","ZEC"]:
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

    second_renaissance_html = f"""
  <!-- THE SECOND RENAISSANCE PODCAST -->
  <div class="card podcast-card compact-podcast-card">
    <div class="card-title">🎙 The Second Renaissance</div>
    <a class="podcast-mini" href="{SECOND_RENAISSANCE['episode_url']}" target="_blank" rel="noopener">
      <img src="{SECOND_RENAISSANCE['thumbnail_url']}" alt="The Second Renaissance Podcast" loading="lazy">
      <span>
        <strong>{SECOND_RENAISSANCE['episode_title']}</strong>
        <em>Watch on YouTube →</em>
      </span>
    </a>
    <p class="podcast-mini-copy">{SECOND_RENAISSANCE['episode_blurb']}</p>
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
      --gold:#c9a84c;--gold-dim:rgba(201,168,76,.12);--gold-mid:rgba(201,168,76,.25);
      --green:#2a9d8f;--red:#e63946;--blue:#5a7bc4;--violet:#9470c8;
      --sans:'Inter',sans-serif;--serif:'Cormorant Garamond',serif;--r:6px;
    }}
    html{{scroll-behavior:smooth}}
    body{{font-family:var(--sans);background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:32px 16px;font-size:16.5px;line-height:1.5}}
    body{{font-family:var(--sans);background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:32px 16px;font-size:16.5px;line-height:1.5}}
    .container{{max-width:720px;margin:0 auto}}

    .header-brand{{text-align:center;padding-bottom:20px}}

    .signal-bolt{{display:inline-flex;align-items:center;text-decoration:none;margin-left:6px;vertical-align:baseline;position:relative;top:-1px;transition:all .3s ease;font-size:1.1rem}}
    .signal-bolt:hover{{opacity:.7;transform:scale(1.1)}}
    @keyframes neon-flicker{{0%,100%{{opacity:1}}92%{{opacity:1}}93%{{opacity:.8}}94%{{opacity:1}}96%{{opacity:.9}}97%{{opacity:1}}}}

    .dateline{{text-align:center;padding:0 0 28px;margin-bottom:28px;border-bottom:1px solid var(--border)}}
    .dateline .date{{font-size:.7rem;letter-spacing:.2em;text-transform:uppercase;color:var(--dim)}}
    .dateline .gen{{font-size:.6rem;color:var(--mute);margin-top:3px}}

    .card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px;margin-bottom:14px}}
    .card-title{{font-size:.6rem;font-weight:600;letter-spacing:.24em;text-transform:uppercase;color:var(--gold);margin-bottom:16px;display:flex;align-items:center;gap:8px}}
    .card-title::after{{content:'';flex:1;height:1px;background:linear-gradient(90deg,var(--gold-mid),transparent)}}

    .trip-countdown{{padding:14px 16px}}
    .trip-row{{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap}}
    .trip-days{{font-family:var(--serif);font-size:1.35rem;color:var(--text);line-height:1.2}}
    .trip-sub{{font-size:.65rem;color:var(--gold);letter-spacing:.08em;text-transform:uppercase}}
    .countdown-strip{{padding:13px 16px}}
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
    .meditation{{margin-bottom:14px;padding:12px 14px;border:1px solid rgba(201,161,91,.22);border-radius:14px;background:linear-gradient(135deg,rgba(201,161,91,.08),rgba(255,255,255,.02))}}
    .meditation-title{{font-family:var(--serif);font-size:1rem;color:var(--gold);margin-bottom:3px}}
    .meditation-meta{{font-size:.62rem;color:var(--dim);text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px}}
    .meditation-excerpt{{font-size:.86rem;line-height:1.62;color:var(--muted)}}
    #quotes-card{{padding:14px 16px}}
    .updog-intro{{font-size:.7rem;color:var(--dim);line-height:1.45;margin:-2px 0 10px}}
    .updog-grid{{display:flex;flex-direction:column;gap:7px}}
    .updog-item{{display:grid;grid-template-columns:28px minmax(120px,.85fr) minmax(0,2.4fr) auto;align-items:center;gap:10px;border:1px solid rgba(201,161,91,.16);border-radius:12px;padding:8px 10px;background:linear-gradient(145deg,rgba(255,255,255,.03),rgba(201,161,91,.032));min-width:0}}
    .updog-item.open{{align-items:start}}
    .updog-item.voted{{border-color:rgba(42,157,143,.45);background:linear-gradient(145deg,rgba(42,157,143,.09),rgba(201,161,91,.03))}}
    .updog-num{{font-family:var(--serif);font-size:1rem;color:var(--gold);text-align:center;opacity:.9}}
    .updog-kicker{{font-size:.5rem;color:var(--gold);letter-spacing:.12em;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .updog-copy{{min-width:0;cursor:pointer}}
    .updog-title{{font-family:var(--serif);font-size:.86rem;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .updog-idea{{font-size:.72rem;color:var(--muted);line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .updog-expand{{display:none;margin-top:6px;font-size:.7rem;line-height:1.48;color:var(--dim);white-space:normal}}
    .updog-item.open .updog-title,.updog-item.open .updog-idea{{white-space:normal;overflow:visible;text-overflow:clip}}
    .updog-item.open .updog-expand{{display:block}}
    .updog-actions{{display:flex;gap:6px;margin-left:auto;align-items:center}}
    .updog-status{{font-size:.52rem;color:var(--green);letter-spacing:.08em;text-transform:uppercase;white-space:nowrap;display:none}}
    .updog-item.voted .updog-status{{display:inline}}
    .updog-btn{{border:1px solid var(--gold-mid);border-radius:999px;padding:5px 9px;font-size:.5rem;text-align:center;text-decoration:none;text-transform:uppercase;letter-spacing:.1em;transition:.18s ease;white-space:nowrap;cursor:pointer;font-family:var(--sans)}}
    .updog-approve{{background:rgba(201,161,91,.16);color:var(--gold)}}
    .updog-retry{{color:var(--dim);border-color:rgba(255,255,255,.16);background:transparent}}
    .updog-btn:hover{{transform:translateY(-1px);filter:brightness(1.15)}}
    .keystone-row{{display:flex;width:100%;box-sizing:border-box;align-items:stretch;border:1px solid rgba(255,255,255,.12);border-radius:12px;overflow:hidden;background:rgba(0,0,0,.22)}}
    .keystone-row:focus-within{{border-color:var(--gold-mid);box-shadow:0 0 0 2px rgba(201,168,76,.08)}}
    .keystone-input{{flex:1 1 auto;width:auto;min-width:0;box-sizing:border-box;border:0;background:transparent;color:var(--text);border-radius:0;padding:10px 14px;font-size:.9rem;line-height:1.2;outline:none;min-height:42px}}
    .keystone-input:focus{{box-shadow:none}}
    .keystone-done{{flex:0 0 50px;align-self:stretch;box-sizing:border-box;display:flex;align-items:center;justify-content:center;border:0;border-left:1px solid rgba(201,168,76,.38);border-radius:0;padding:0;font-size:.42rem;letter-spacing:.08em;background:rgba(201,161,91,.12);min-height:0}}
    .keystone-done:hover{{transform:none;filter:brightness(1.15)}}
    @media(max-width:760px){{.updog-item{{grid-template-columns:22px 1fr;align-items:start}}.updog-kicker,.updog-copy{{grid-column:2}}.updog-actions{{grid-column:2;margin-left:0;margin-top:4px}}.keystone-done{{flex-basis:46px;font-size:.4rem}}}}
    .updog-action-card{{margin-top:-6px}}
    .action-steps-grid{{display:flex;flex-direction:column;gap:7px}}
    .action-step{{display:grid;grid-template-columns:28px minmax(0,1fr);gap:10px;align-items:start;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:10px;background:rgba(255,255,255,.025);min-width:0}}
    .action-step-num{{font-family:var(--serif);font-size:1rem;color:var(--gold);text-align:center;opacity:.9;line-height:1.2}}
    .action-step-copy{{min-width:0}}
    .action-step-kicker{{font-size:.5rem;color:var(--gold);letter-spacing:.12em;text-transform:uppercase;margin-bottom:3px}}
    .action-step-title{{font-family:var(--serif);font-size:.9rem;color:var(--text);line-height:1.25}}
    .action-step-ask{{font-size:.72rem;color:var(--muted);line-height:1.35;margin-top:2px}}
    .action-step-empty{{font-size:.76rem;color:var(--muted);line-height:1.45;border:1px dashed rgba(255,255,255,.14);border-radius:12px;padding:12px;background:rgba(255,255,255,.018)}}
    @media(max-width:760px){{.action-step{{grid-template-columns:22px 1fr}}}}


    .weather-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;box-sizing:border-box}}
    .weather-item{{text-align:center;padding:12px 8px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);box-sizing:border-box;display:flex;flex-direction:column;align-items:center;justify-content:center}}
    .weather-item .city{{font-size:.65rem;color:var(--dim);margin-bottom:5px;letter-spacing:.04em}}
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
    .star-sign-desc{{font-size:.78rem;color:var(--dim);line-height:1.55;margin-top:6px}}

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

    .allocation-section{{display:flex;align-items:center;gap:24px;margin-top:20px;padding-top:16px;border-top:1px solid var(--border)}}
    .pie-chart{{flex-shrink:0}}
    .allocation-legend{{flex:1;display:grid;grid-template-columns:repeat(2,1fr);gap:6px}}
    .legend-item{{display:flex;align-items:center;gap:6px;font-size:.72rem}}
    .legend-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
    .legend-pct{{color:var(--dim);margin-left:auto}}

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
    .catalyst-source{{font-size:.62rem;color:var(--dim);margin-top:2px}}
    .no-news{{color:var(--dim);font-style:italic;font-size:.78rem;margin-left:6px}}

    .commodities-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}}
    .commodity-item{{background:var(--bg);padding:12px;border:1px solid var(--border);border-radius:var(--r);text-align:center}}
    .commodity-name{{font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:5px;font-weight:600}}
    .commodity-price{{font-family:var(--serif);font-size:1.2rem;font-weight:400;margin-bottom:2px}}
    .commodity-unit{{font-size:.6rem;color:var(--dim)}}
    .commodity-change{{font-size:.72rem;margin-top:3px}}
    .c-gold{{color:#c9a84c}}.c-silver{{color:#b8b8b8}}.c-copper{{color:#b87333}}
    .c-oil{{color:#8b7355}}.c-palladium{{color:#ccc}}.c-uranium{{color:#7fc87f}}

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

    .rec-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
    .rec-item{{background:var(--bg);padding:16px;border:1px solid var(--border);border-radius:var(--r)}}
    .rec-label{{font-size:.58rem;color:var(--gold);text-transform:uppercase;letter-spacing:.16em;margin-bottom:7px;font-weight:600}}
    .rec-title{{font-family:var(--serif);font-size:1.05rem;color:var(--text);margin-bottom:3px}}
    .rec-meta{{font-size:.68rem;color:var(--blue);margin-bottom:5px}}
    .rec-summary{{font-size:.76rem;color:var(--dim);line-height:1.45}}

    .podcast-card{{padding:14px 16px}}
    .podcast-mini{{display:flex;align-items:stretch;gap:12px;text-decoration:none;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:8px;transition:border-color .15s}}
    .podcast-mini:hover{{border-color:var(--gold)}}
    .podcast-mini img{{width:20%;min-width:128px;aspect-ratio:16/9;object-fit:cover;border-radius:4px;filter:saturate(.85) brightness(.9);flex-shrink:0}}
    .podcast-mini span{{display:flex;flex-direction:column;justify-content:center;gap:4px;min-width:0}}
    .podcast-mini strong{{font-family:var(--serif);font-size:1.18rem;font-weight:500;color:var(--text);line-height:1.12}}
    .podcast-mini em{{font-style:normal;font-size:.64rem;color:var(--gold);letter-spacing:.12em;text-transform:uppercase}}
    .podcast-mini-copy{{font-size:.72rem;color:var(--dim);line-height:1.45;margin:8px 2px 0}}

    .sat-word-box{{padding:14px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r)}}
    .sat-word{{font-family:var(--serif);font-size:1.2rem;color:var(--gold);font-weight:500;margin-bottom:6px}}
    .sat-def{{font-size:.82rem;color:var(--text);margin-bottom:10px;font-style:italic}}
    .sat-sentence{{font-size:.78rem;color:var(--dim);line-height:1.5;border-left:2px solid var(--gold-mid);padding-left:10px}}
    .sat-source{{font-size:.68rem;color:var(--mute);margin-top:8px;text-align:right}}

    .fx-row{{display:flex;flex-wrap:wrap;justify-content:center;gap:6px;margin-top:4px}}
    .fx-chip{{text-align:center;min-width:0;flex:1 1 0;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:6px 4px}}
    .fx-chip .fx-ccy{{font-size:.54rem;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);white-space:nowrap}}
    .fx-chip .fx-rate{{display:block;font-family:'Courier New',monospace;font-size:.78rem;font-weight:600;color:var(--gold);margin-top:1px}}

    .feed-controls{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}}
    .feed-refresh{{font-size:.6rem;color:var(--dim);letter-spacing:.08em;cursor:pointer;background:none;border:1px solid var(--border);color:var(--dim);padding:4px 8px;border-radius:var(--r);font-family:var(--sans)}}
    .feed-refresh:hover{{border-color:var(--gold);color:var(--gold)}}
    .feed-status{{font-size:.62rem;color:var(--dim);font-style:italic}}
    .feed-item{{padding:8px 0;border-bottom:1px solid var(--border)}}
    .feed-item:last-child{{border-bottom:none}}
    .feed-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}}
    .feed-author{{display:flex;align-items:center;gap:7px}}
    .feed-avatar{{width:26px;height:26px;border-radius:50%;object-fit:cover;flex-shrink:0;background:var(--border)}}
    .feed-name{{font-size:.78rem;font-weight:600;color:var(--text)}}
    .feed-handle{{font-size:.68rem;color:var(--dim)}}
    .feed-time{{font-size:.64rem;color:var(--dim)}}
    .feed-text{{font-size:.8rem;color:var(--text);line-height:1.5;word-break:break-word;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
    .feed-stats{{display:flex;gap:12px;margin-top:4px}}
    .feed-stat{{font-size:.64rem;color:var(--dim)}}
    .feed-stat span{{color:var(--gold)}}
    .feed-link{{display:inline-block;margin-top:5px;font-size:.64rem;color:var(--gold);text-decoration:none;opacity:.6}}
    .feed-link:hover{{opacity:1}}
    .feed-empty{{text-align:center;padding:20px;color:var(--dim);font-size:.82rem}}
    .feed-loading{{text-align:center;padding:20px;color:var(--dim);font-size:.82rem}}
    .feed-loading::after{{content:'...';animation:dots 1.2s steps(3,end) infinite}}
    @keyframes dots{{0%,100%{{content:'.'}}33%{{content:'..'}}66%{{content:'...'}}}}
    .feed-filter{{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}}
    .feed-tag{{font-size:.6rem;padding:3px 7px;border:1px solid var(--border);color:var(--dim);cursor:pointer;background:none;letter-spacing:.06em;border-radius:var(--r);font-family:var(--sans)}}
    .feed-tag.active,.feed-tag:hover{{border-color:var(--gold);color:var(--gold);background:var(--gold-dim)}}

    .fed-card{{text-align:center;padding:14px 16px}}
    .fed-title{{font-size:.58rem;letter-spacing:.16em;text-transform:uppercase;color:var(--gold);margin-bottom:10px;font-weight:600}}
    .fed-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;text-align:center}}
    .fed-grid-item{{padding:6px 4px}}
    .fed-grid-label{{font-size:.54rem;color:var(--dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}}
    .fed-grid-val{{font-family:var(--serif);font-size:1.05rem;font-weight:400;line-height:1.3}}
    .fed-grid-sub{{font-size:.52rem;color:var(--mute);margin-top:2px}}
    @media(max-width:400px){{.fed-grid{{grid-template-columns:repeat(2,1fr);gap:6px}}.fed-grid-val{{font-size:.95rem}}}}

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
    .footer-logo{{font-family:var(--serif);font-size:1.8rem;font-weight:300;letter-spacing:.18em;text-transform:uppercase;color:var(--text);margin-bottom:4px}}
    .footer-logo span{{color:var(--gold);font-style:italic}}
    .footer-tagline{{font-size:.62rem;color:var(--dim);letter-spacing:.14em;text-transform:uppercase}}
    .footer-sub{{font-size:.58rem;color:var(--mute);margin-top:6px}}
    .eco-links{{display:flex;justify-content:center;gap:20px;margin-top:12px;flex-wrap:wrap}}
    .eco-link{{font-size:.7rem;color:var(--gold);text-decoration:none;opacity:.7;transition:opacity .15s;letter-spacing:.06em}}
    .eco-link:hover{{opacity:1}}

    @media(min-width:761px){{
      html{{font-size:110%}}
      body{{font-size:18.15px;padding:35px 18px}}
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
      .fx-row{{gap:4px}}
      .fx-chip .fx-ccy{{font-size:.5rem}}
      .fx-chip .fx-rate{{font-size:.7rem}}
      .allocation-section{{flex-direction:column}}
      .rec-grid{{grid-template-columns:1fr}}
      .portfolio-summary{{grid-template-columns:repeat(3,1fr)}}
    }}
  </style>
</head>
<body>
<div class="container">

  <!-- HEADER BRANDING -->
  <div class="header-brand">
    <div class="footer-logo">Novaire <span>Signal</span> <a href="/portfolio" class="signal-bolt" title="Portfolio">⚡</a></div>
    <div style="font-family:var(--serif);font-size:.9rem;font-style:italic;color:var(--gold);opacity:0.7;letter-spacing:.04em;margin-top:2px;">Deciphering through the noise.</div>
  </div>

  <!-- DATE / GENERATION LINE -->
  <div class="dateline">
    <div class="date">{date_str}</div>
    <!-- removed generated timestamp -->
  </div>

  <!-- PERSONAL COUNTDOWNS -->
  <div class="card countdown-strip">
    <div class="countdown-strip-grid">
      <div class="countdown-item">
        <div class="countdown-label">🇨🇦 Canada</div>
        <div class="countdown-days">{canada_countdown_text}</div>
        <div class="countdown-date">Jul 13 · Passport 09:00 · BKK 15:55</div>
      </div>
      <div class="countdown-item">
        <div class="countdown-label">🚂 Trans-Siberian</div>
        <div class="countdown-days">{trip_countdown_text}</div>
        <div class="countdown-date">Aug 25</div>
      </div>
      <div class="countdown-item">
        <div class="countdown-label">🎡 EDC Thailand</div>
        <div class="countdown-days">{edc_countdown_text}</div>
        <div class="countdown-date">Dec 18</div>
      </div>
      <div class="countdown-item">
        <div class="countdown-label">🏝 Mastermind Retreat</div>
        <div class="countdown-days">{retreat_countdown_text}</div>
        <div class="countdown-date">Jan 19</div>
      </div>
    </div>
  </div>

  <!-- DAILY MEDITATION + QUOTES (client-side localStorage dedup) -->
  <div class="card" id="quotes-card">
    <div class="card-title">📜 Daily Meditation</div>
    <div id="meditation-daily" class="meditation">
      <div class="meditation-title" id="med-title"></div>
      <div class="meditation-meta" id="med-meta"></div>
      <div class="meditation-excerpt" id="med-excerpt"></div>
    </div>
    <div class="card-title">Quotes</div>
    <div id="quote-daily" class="quote">
      <div class="quote-type" id="qt-type"></div>
      <div class="quote-text" id="qt-text"></div>
      <div class="quote-author" id="qt-auth"></div>
    </div>
  </div>

  {second_renaissance_html}

  <!-- WEATHER + THAILAND NEWS -->
  <div class="card">
    <div class="card-title">🌤 Weather</div>
    <div class="weather-grid">
      {weather_html}
    </div>
  </div>

  <!-- WALL STREET CLOCK -->
  <div class="card" style="text-align:center;padding:8px 16px">
    <div style="display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap">
      <span style="font-size:.62rem;letter-spacing:.12em;text-transform:uppercase;color:var(--gold)">🗽 Wall St</span>
      <span class="live-clock" data-tz-offset="-4" style="font-family:var(--serif);font-size:1.15rem;color:var(--text);letter-spacing:.04em"></span>
      <span style="font-size:.56rem;color:var(--mute)">NYSE {next_nyse_str} · TSX {next_tsx_str}</span>
    </div>
  </div>

  <div class="card">
    <div class="card-title">💱 FX Rates — 1 USD =</div>
    <div class="fx-row">
      {fx_rates_html}
    </div>
  </div>

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

  {poly_html}

  {alpaca_html}

<!-- ZEROHEDGE -->
  <div class="card">
    <div class="card-title">📰 ZeroHedge — Top Headlines</div>
    {zh_html}
  </div>

  <!-- SIGNAL FEED -->
  <div class="card">
    <div class="card-title">📡 Signal Feed — Top 3 by Engagement</div>
    <div class="feed-controls">
      <div class="feed-status" id="feed-status">Loading…</div>
      <button class="feed-refresh" onclick="loadFeed(true)" title="Feed updates every 4 hours · filtered to last 4h · ranked by likes + retweets">↻ Refresh</button>
    </div>
    <div class="feed-filter" id="feed-filter"></div>
    <div id="signal-feed">
      <div class="feed-loading">Fetching signals</div>
    </div>
  </div>

  <script>
  (function() {{
    let allPosts = [];
    let activeFilter = null;
    const CACHE_KEY = 'novaire_feed_v4';  // bumped — busts stale localStorage
    const CACHE_TTL = 4 * 60 * 1000;    // 4min cache — matches refresh cadence

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

    // Enforce display order: top four by engagement. The Economist intentionally excluded upstream.
    function sortBySlot(posts) {{
      return [...posts].sort((a, b) => (a.slot_order || 99) - (b.slot_order || 99));
    }}

    function renderFeed(posts) {{
      const container = document.getElementById('signal-feed');
      if (!posts.length) {{
        container.innerHTML = '<div class="feed-empty">No recent posts found. Try refreshing.</div>';
        return;
      }}
      container.innerHTML = posts.map(p => `
        <div class="feed-item">
          <div class="feed-header">
            <div class="feed-author">
              ${{p.avatar ? `<img class="feed-avatar" src="${{escHtml(p.avatar)}}" alt="" loading="lazy" onerror="this.style.display='none'">` : '<div class="feed-avatar"></div>'}}
              <div>
                <div class="feed-name">${{escHtml(p.author)}}</div>
                <div class="feed-handle">@${{escHtml(p.handle)}}</div>
              </div>
            </div>
            <div class="feed-time">${{timeAgo(p.createdAt)}}</div>
          </div>
          <div class="feed-text">${{escHtml(p.text).split(" ").slice(0, 15).join(" ")}}${{escHtml(p.text).split(" ").length > 15 ? "…" : ""}}</div>
          <div class="feed-stats">
            <div class="feed-stat">♥ <span>${{fmtNum(p.likes)}}</span></div>
            <div class="feed-stat">↺ <span>${{fmtNum(p.retweets)}}</span></div>
          </div>
          <a class="feed-link" href="${{escHtml(p.url)}}" target="_blank" rel="noopener">View on X →</a>
        </div>
      `).join('');
    }}

    function renderFilter() {{
      const bar = document.getElementById('feed-filter');
      const handles = [...new Set(allPosts.map(p => p.handle))].sort();
      bar.innerHTML = `<button class="feed-tag${{!activeFilter?' active':''}}" onclick="window._feedFilter(null)">All</button>` +
        handles.map(h => `<button class="feed-tag${{activeFilter===h?' active':''}}" onclick="window._feedFilter('${{escHtml(h)}}')">${{escHtml('@'+h)}}</button>`).join('');
    }}

    window._feedFilter = function(handle) {{
      activeFilter = handle;
      renderFilter();
      renderFeed(handle ? allPosts.filter(p => p.handle === handle) : allPosts);
    }};

    async function loadFeed(force) {{
      const status = document.getElementById('feed-status');
      const now = Date.now();
      if (!force) {{
        try {{
          const cached = localStorage.getItem(CACHE_KEY);
          if (cached) {{
            const {{ ts, data }} = JSON.parse(cached);
            if (now - ts < CACHE_TTL && data.length > 0) {{
              allPosts = sortBySlot(data);
              renderFilter();
              renderFeed(activeFilter ? allPosts.filter(p=>p.handle===activeFilter) : allPosts);
              status.textContent = data.length + ' posts · cached ' + timeAgo(new Date(ts).toISOString());
              return;
            }}
          }}
        }} catch(e) {{}}
      }}
      status.textContent = 'Fetching signals…';
      document.getElementById('signal-feed').innerHTML = '<div class="feed-loading">Fetching signals</div>';
      try {{
        const resp = await fetch('/feed.json');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const json = await resp.json();
        if (!json.ok) throw new Error(json.error || 'API error');
        allPosts = sortBySlot(json.posts);
        try {{ localStorage.setItem(CACHE_KEY, JSON.stringify({{ ts: now, data: allPosts }})); }} catch(e) {{}}
        renderFilter();
        renderFeed(activeFilter ? allPosts.filter(p=>p.handle===activeFilter) : allPosts);
        const fetchedAt = json.fetchedAt ? new Date(json.fetchedAt) : new Date();
        const ageMin = Math.floor((Date.now() - fetchedAt.getTime()) / 60000);
        const ageStr = ageMin < 2 ? 'just now' : ageMin < 60 ? ageMin + 'm ago' : Math.floor(ageMin/60) + 'h ago';
        const windowHours = json.windowHours || 24;
        status.textContent = 'Top 3 by engagement · no Economist · last ' + windowHours + 'h · updated ' + ageStr;
      }} catch(err) {{
        status.textContent = 'Feed unavailable';
        document.getElementById('signal-feed').innerHTML = '<div class="feed-empty">Could not load feed: ' + err.message + '</div>';
      }}
    }}
    document.readyState === 'loading'
      ? document.addEventListener('DOMContentLoaded', () => loadFeed(false))
      : loadFeed(false);
  }})();
  </script>

  <!-- PORTFOLIO removed — now at /portfolio -->

  <!-- CATALYSTS — Top 5 only, fresh news highlighted -->
  <div class="card">
    <div class="card-title">🔍 Catalysts — Top 5 Holdings</div>
    {cats_html}
  </div>


  <!-- CURRENTLY -->
  <div class="card">
    <div class="card-title">📚 Currently</div>
    <div class="rec-grid">
      <div class="rec-item">
        <div class="rec-label">📺 Watching</div>
        <div class="rec-title">Diamond League Track & Field</div>
        <div class="rec-meta">World Athletics · Sprinting, distance, jumps, throws</div>
        <div class="rec-summary">Elite track and field as a weekly performance study: speed, pressure, tactics, recovery, and the psychology of peak humans under the clock.</div>
      </div>
      <div class="rec-item">
        <div class="rec-label">📖 Reading</div>
        <div class="rec-title">The Trickster Archetype</div>
        <div class="rec-meta">James' pick · Psychology/Myth</div>
        <div class="rec-summary">A study of the trickster pattern: mischief, boundary crossing, disruption, transformation, and the strange wisdom that enters through chaos.</div>
      </div>
    </div>
  </div>

  <!-- THAILAND NEWS -->
  <div class="card">
    <div class="card-title">🇹🇭 Thailand</div>
    <div class="thai-news-header">Thailand Expat Brief · Visa, Safety, Scandals</div>
    <div class="thai-news-compact" style="margin-top:10px">
      {bkk_html}
    </div>
  </div>

  <!-- Daily Motivation merged into single Quote of the Day -->

  <!-- LATEST FROM NOVAIRE INK -->
  <a href="https://novaireink.com/#when-you-dont-write" class="card" style="display:block;text-decoration:none;cursor:pointer;">
    <div class="card-title">📝 Latest from Novaire Ink</div>
    <div class="quote">
      <div class="quote-type">New Essay</div>
      <div class="quote-text">When You Don't Write, You Are Wrong</div>
      <div class="quote-author" style="font-style:normal;margin-top:6px;opacity:0.7;">There is a particular kind of guilt that belongs to the writer who stops writing. Not the guilt of saying something wrong, but the quieter, more corrosive guilt of saying nothing at all.</div>
      <div class="quote-type" style="margin-top:10px;color:var(--gold);">Read the full essay →</div>
    </div>
  </a>

  <!-- FED SIGNAL -->
  {fed_html}

  <!-- TOP 5 ECONOMIES -->
  {eco_html}


  <!-- DAILY KEYSTONE PRIORITY -->
  <div class="card" id="keystone-card">
    <div class="card-title">🎯 Daily Keystone</div>
    <div class="updog-intro">What is the one thing you'll feel good about if it gets done today?</div>
    <div class="keystone-row">
      <input id="keystone-input" class="keystone-input" placeholder="One thing that moves health, wealth, product, or relationships...">
      <button id="keystone-done" class="updog-btn updog-approve keystone-done" type="button">Done</button>
    </div>
    <div id="keystone-status" style="margin-top:10px;color:var(--muted);font-size:.82rem">Keystone streak: 0 days.</div>
  </div>

  <!-- DAILY UPDOG PRODUCT VOTE -->
  <div class="card" id="updog-card">
    <div class="card-title">🗳️ Daily Updog Vote</div>
    <div class="updog-intro">Daily product senate: five concise build tasks, one click to approve the next implementation.</div>
    <div class="updog-grid" id="updog-grid"></div>
  </div>

  <!-- DAILY ACTION STEPS -->
  <div class="card updog-action-card" id="updog-action-card">
    <div class="card-title">⚔️ Daily Action Steps</div>
    <div class="action-steps-grid" id="action-steps-grid"></div>
  </div>

  <!-- FOOTER BRANDING -->
  <div class="footer">
    <div class="footer-logo">Novaire <span>Signal</span> <a href="/portfolio" class="signal-bolt" title="Portfolio">⚡</a></div>
    <div class="footer-tagline">Deciphering through the noise.</div>
    <div class="eco-links">
      <a href="https://novaireink.com" class="eco-link">Novaire Ink</a>
      <a href="https://evolution-fund.vercel.app" class="eco-link">Evolution Fund</a>
    </div>
    <div class="footer-sub">Live data · Updated every 2 hours · 24/7</div>
  </div>

</div>

<!-- CLIENT-SIDE JS: Quote dedup + Holdings toggle + Recs rotation -->
<script>
// ── Quote arrays (30+ per category) ──
const QUOTES_INVESTING = {QUOTES_JS_INVESTING};
const QUOTES_PSYCHOLOGY = {QUOTES_JS_PSYCHOLOGY};
const MEDITATIONS = {MEDITATIONS_JS};
const UPDOG_SUGGESTIONS = {UPDOG_SUGGESTIONS_JS};
const UPDOG_ACTION_STEPS = {UPDOG_ACTION_STEPS_JS};

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

(function renderDailyMeditation() {{
  const m = getQuoteForToday("meditation", MEDITATIONS);
  document.getElementById('med-title').textContent = m.title;
  document.getElementById('med-meta').textContent = m.meta;
  document.getElementById('med-excerpt').textContent = m.excerpt;
}})();


(function renderKeystonePriority() {{
  const input = document.getElementById('keystone-input');
  const button = document.getElementById('keystone-done');
  const status = document.getElementById('keystone-status');
  if (!input || !button || !status) return;
  const today = new Date().toDateString();
  const key = 'novaire-keystone-priority';
  const data = JSON.parse(localStorage.getItem(key) || '{{"text":"","streak":0,"lastDone":""}}');
  input.value = data.date === today ? (data.text || '') : '';
  function save() {{
    data.text = input.value;
    data.date = today;
    localStorage.setItem(key, JSON.stringify(data));
    status.textContent = 'Keystone streak: ' + (data.streak || 0) + ' days' + (data.lastDone === today ? ' · completed today.' : '.');
    if (typeof renderActionSteps === 'function') renderActionSteps();
  }}
  input.addEventListener('input', save);
  button.addEventListener('click', function() {{
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayStr = yesterday.toDateString();
    if (data.lastDone !== today) {{
      data.streak = data.lastDone === yesterdayStr ? (data.streak || 0) + 1 : 1;
      data.lastDone = today;
    }}
    save();
  }});
  save();
}})();

(function renderUpdogVotes() {{
  const grid = document.getElementById('updog-grid');
  if (!grid) return;
  const today = new Date().toDateString();
  const voteKey = 'novaire-updog-votes-' + today;
  const votes = JSON.parse(localStorage.getItem(voteKey) || '{{}}');
  const seed = today.split('').reduce((a,c) => (a * 31 + c.charCodeAt(0)) & 0xffffff, 0);
  const dayIndex = Math.floor((new Date().setHours(0,0,0,0) - new Date(new Date().getFullYear(),0,0)) / 86400000);
  const categories = [
    ['motr', 'Man On The Rise Game'],
    ['retreat', 'Retreat'],
    ['energy', 'Energy Maxxing App'],
    ['signal', 'Novaire Signal'],
    ['podcast', 'Podcast / Clips']
  ];
  const iterationBank = {{
    motr: {{
      surfaces:['relationship game onboarding','date-night mode','mastermind room mode','couples score report','question-category selector','post-game commitment screen'],
      verbs:['tighten','ship','test','instrument','personalize','simplify'],
      bottlenecks:['first-session friction','weak follow-through','generic questions','unclear target user','no replay reason','missing shareable proof']
    }},
    retreat: {{
      surfaces:['application funnel','deposit close flow','Bangkok itinerary proof','candidate qualification screen','venue/room proof block','follow-up message sequence'],
      verbs:['clarify','pressure-test','de-risk','sell','validate','package'],
      bottlenecks:['too much concept, not enough proof','unclear buyer urgency','soft qualification','no deadline pressure','weak trust signals','missing next close']
    }},
    energy: {{
      surfaces:['daily battery check-in','sleep recovery logic','energy leak detector','30-day experiment mode','habit proof screen','recommendation engine'],
      verbs:['make','test','score','compress','personalize','enforce'],
      bottlenecks:['too many questions','vague advice','no proof loop','ignoring sleep debt','low daily retention','no obvious first action']
    }},
    signal: {{
      surfaces:['daily cockpit layout','Updog approval workflow','Thailand expat brief','keystone action step','signal/noise pruning','implementation handoff copy'],
      verbs:['sharpen','automate','trim','rank','connect','verify'],
      bottlenecks:['stale suggestions','dashboard clutter','unclear next action','manual handoff friction','weak live verification','too many passive widgets']
    }},
    podcast: {{
      surfaces:['clip topic queue','X-to-thesis scanner','relationship mental model series','wisdom monologue outline','hook/title generator','guest/conversation prompt'],
      verbs:['draft','rank','extract','package','test','angle'],
      bottlenecks:['generic topics','no durable thesis','weak hook','too much news, not enough wisdom','no recording prompt','unclear audience']
    }}
  }};
  function pickFrom(list, salt) {{ return list[(seed + dayIndex * 7 + salt) % list.length]; }}
  function synthesizeUpdogSuggestion(key, label, categoryIndex) {{
    const bank = iterationBank[key];
    const fallback = (UPDOG_SUGGESTIONS[key] || [])[0] || {{title:'Ship one iteration', idea:'Pick the next bottleneck and turn it into a concrete implementation task.', action:'Implement one focused product iteration.'}};
    if (!bank) return fallback;
    const surface = pickFrom(bank.surfaces, categoryIndex * 3);
    const bottleneck = pickFrom(bank.bottlenecks, categoryIndex * 7 + 2);
    const title = surface.charAt(0).toUpperCase() + surface.slice(1);
    return {{
      title: title,
      idea: 'Fix ' + bottleneck + ' in ' + label + '.',
      action: 'Update the ' + surface + ' to fix ' + bottleneck + '.'
    }};
  }}
  window.handleUpdogVote = function(key, kind, url) {{
    votes[key] = kind;
    localStorage.setItem(voteKey, JSON.stringify(votes));
    const row = document.querySelector('[data-updog="' + key + '"]');
    if (row) {{
      row.classList.add('voted');
      const status = row.querySelector('.updog-status');
      if (status) status.textContent = kind === 'approve' ? 'Approved' : 'Retry requested';
    }}
    window.open(url, '_blank', 'noopener');
  }};
  grid.innerHTML = categories.map(([key, label], categoryIndex) => {{
    const item = synthesizeUpdogSuggestion(key, label, categoryIndex);
    const approveText = encodeURIComponent('APPROVE UPDOG: ' + label + ' — ' + item.action + ' Context: ' + item.idea);
    const retryText = encodeURIComponent('TRY AGAIN UPDOG: Give me a sharper alternative for ' + label + '. Previous suggestion: ' + item.title + ' — ' + item.idea);
    const approveUrl = 'https://t.me/share/url?url=https%3A%2F%2Fnovairesignal.com&text=' + approveText.replace(/'/g, '%27');
    const retryUrl = 'https://t.me/share/url?url=https%3A%2F%2Fnovairesignal.com&text=' + retryText.replace(/'/g, '%27');
    const voteClass = votes[key] ? ' voted' : '';
    const voteStatus = votes[key] === 'approve' ? 'Approved' : (votes[key] === 'retry' ? 'Retry requested' : '');
    return `
      <div class="updog-item${{voteClass}}" data-updog="${{key}}" title="${{item.idea}}">
        <div class="updog-num">${{categoryIndex + 1}}</div>
        <div class="updog-kicker">${{label}}</div>
        <div class="updog-copy" onclick="this.closest('.updog-item').classList.toggle('open')">
          <div class="updog-idea">${{item.action}}</div>
          <div class="updog-expand">Target: ${{item.title}}. Why: ${{item.idea}} Vote yes to build it, or Try Again for a sharper task.</div>
        </div>
        <div class="updog-actions">
          <span class="updog-status">${{voteStatus}}</span>
          <button class="updog-btn updog-approve" type="button" onclick="handleUpdogVote('${{key}}','approve','${{approveUrl}}')">Approve</button>
          <button class="updog-btn updog-retry" type="button" onclick="handleUpdogVote('${{key}}','retry','${{retryUrl}}')">Try Again</button>
        </div>
      </div>`;
  }}).join('');
}})();

function escapeActionHtml(value) {{
  return String(value || '').replace(/[&<>"']/g, function(ch) {{
    return ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[ch];
  }});
}}

function renderActionSteps() {{
  const grid = document.getElementById('action-steps-grid');
  if (!grid) return;
  const today = new Date().toDateString();
  const data = JSON.parse(localStorage.getItem('novaire-keystone-priority') || '{{"text":"","date":""}}');
  const task = data.date === today ? String(data.text || '').trim() : '';
  if (!task) {{
    grid.innerHTML = '<div class="action-step-empty">Write today’s one thing above. This section will show one clean next action.</div>';
    return;
  }}
  const safeTask = escapeActionHtml(task);
  grid.innerHTML = `
    <div class="action-step main-action-step">
      <div class="action-step-num">1</div>
      <div class="action-step-copy">
        <div class="action-step-kicker">Next Action</div>
        <div class="action-step-title">Start the smallest visible move for: ${{safeTask}}</div>
        <div class="action-step-ask">Set a 10-minute timer. Create one piece of proof that this moved forward.</div>
      </div>
    </div>`;
}}
renderActionSteps();

(function renderQuotes() {{
  const day = new Date().getDate();
  const isInv = day % 2 === 0; const q = isInv ? getQuoteForToday("investing", QUOTES_INVESTING) : getQuoteForToday("psychology", QUOTES_PSYCHOLOGY);
  document.getElementById('qt-type').textContent = isInv ? 'Investing' : 'Psychology';
  document.getElementById('qt-text').textContent = '\u201c' + q.text + '\u201d';
  document.getElementById('qt-auth').textContent = '\u2014 ' + q.author;
}})();

// Recommendations are now server-side rendered (live trending data)
</script>
<script>
// Live world clocks
!function(){{var u=function(){{document.querySelectorAll(".live-clock").forEach(function(e){{var o=parseInt(e.getAttribute("data-tz-offset"))||0,n=new Date,t=n.getTime()+n.getTimezoneOffset()*6e4,l=new Date(t+o*36e5);e.textContent=String(l.getHours()).padStart(2,"0")+":"+String(l.getMinutes()).padStart(2,"0")+":"+String(l.getSeconds()).padStart(2,"0")}})}}; u(); setInterval(u,1e3)}}();

// Live crypto prices (Binance, every 30s)
!function(){{
  var coins={{"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT","SUI":"SUIUSDT","XRP":"XRPUSDT","ADA":"ADAUSDT","TON":"TONUSDT","ZEC":"ZECUSDT"}};
  function fmt(p){{return p>=1000?"$"+p.toFixed(0).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g,","):p>=1?"$"+p.toFixed(2):"$"+p.toFixed(4)}}
  function updCrypto(){{
    Object.keys(coins).forEach(function(c){{
      fetch("https://api.binance.com/api/v3/ticker/24hr?symbol="+coins[c])
        .then(function(r){{return r.json()}})
        .then(function(d){{
          var el=document.querySelector('[data-crypto-price="'+c+'"]');
          var ce=document.querySelector('[data-crypto-chg="'+c+'"]');
          if(el)el.textContent=fmt(parseFloat(d.lastPrice));
          if(ce){{var ch=parseFloat(d.priceChangePercent);ce.innerHTML='<span class="'+(ch>=0?"positive":"negative")+'">'+(ch>=0?"+":"")+ch.toFixed(2)+"%</span>"}}
        }}).catch(function(){{}})
    }})
  }}
  updCrypto();setInterval(updCrypto,30000);
}}();
</script>
</body>
</html>"""
    return html

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def render_portfolio_html(portfolio_data, catalysts, fx, holdings_source=None, gs_meta=None, bot_accounts_html="", evo_fund_html=""):
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
            <td class="ticker">{display}</td>
            <td style="color:var(--dim);font-size:.8em">{name}</td>
            <td style="text-align:right">{int(shares):,}</td>
            <td style="text-align:right">{price_str}</td>
            <td style="text-align:right">{chg_html}</td>
            <td style="text-align:right;font-weight:600">{value_str}</td>
          </tr>"""

    # ── Allocation chart ──
    alloc_sorted = sorted(sector_totals.items(), key=lambda x: x[1], reverse=True)
    alloc_list   = [(s, v, "") for s, v in alloc_sorted]
    donut_svg    = build_donut(alloc_list)
    legend_html  = build_legend(alloc_list, total_usd)

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
              <span class="catalyst-headline" style="color:var(--dim);font-style:italic">No news within 48 hours.</span>
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
      --gold:#c9a84c;--gold-dim:rgba(201,168,76,.12);--gold-mid:rgba(201,168,76,.25);
      --green:#2a9d8f;--red:#e63946;--blue:#5a7bc4;--violet:#9470c8;
      --sans:'Inter',sans-serif;--serif:'Cormorant Garamond',serif;--r:6px;
    }}
    html{{scroll-behavior:smooth}}
    body{{font-family:var(--sans);background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:32px 16px;font-size:16.5px;line-height:1.5}}
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
    .allocation-section{{display:flex;align-items:center;gap:24px;margin-top:20px;padding-top:16px;border-top:1px solid var(--border)}}
    .pie-chart{{flex-shrink:0}}
    .allocation-legend{{flex:1;display:grid;grid-template-columns:repeat(2,1fr);gap:6px}}
    .legend-item{{display:flex;align-items:center;gap:6px;font-size:.72rem}}
    .legend-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
    .legend-pct{{color:var(--dim);margin-left:auto}}
    .catalyst-item{{padding:8px 0;border-bottom:1px solid var(--border);display:flex;align-items:baseline;flex-wrap:wrap;gap:2px;line-height:1.4}}
    .catalyst-item:last-child{{border-bottom:none}}
    .catalyst-ticker{{font-weight:600;color:var(--gold);font-size:.85rem;white-space:nowrap}}
    .catalyst-sep{{color:var(--dim);font-size:.8rem}}
    .catalyst-badge{{color:var(--gold);font-size:.75rem;opacity:.8;white-space:nowrap}}
    .catalyst-headline{{font-size:.8rem;color:var(--text);line-height:1.4}}
    .footer{{text-align:center;padding:40px 0 24px;border-top:1px solid var(--border);margin-top:28px}}
    .footer-logo{{font-family:var(--serif);font-size:1.8rem;font-weight:300;letter-spacing:.18em;text-transform:uppercase;color:var(--text);margin-bottom:4px}}
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
      .allocation-section{{flex-direction:column}}
    }}
    .collapse-toggle{{cursor:pointer;user-select:none;transition:opacity .15s;display:block;padding:10px 0 6px;margin:-2px 0}}
    .collapse-toggle:hover{{opacity:.7;background:rgba(201,168,76,0.05);border-radius:4px}}
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
      <div class="allocation-legend">
        {legend_html}
      </div>
    </div>
    <div style="font-size:.6rem;color:var(--mute);margin-top:10px;text-align:center">
      <span class="fallback-badge">est</span> = estimated / last known price · Updated every 2 hours
    </div>
  </div>

  <!-- CATALYSTS -->
  <div class="card">
    <div class="card-title">🔍 Catalysts — Top 5 Holdings</div>
    {cats_html}
  </div>

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

    print("  🔍 Fetching catalysts (yfinance news)...")
    sorted_holdings = sorted(
        [h["ticker"] for h in HOLDINGS],
        key=lambda t: (portfolio_data.get(t, {}).get("value") or 0),
        reverse=True
    )
    top3 = sorted_holdings[:3]
    try:
        catalysts = fetch_catalysts(top3)
        print(f"    ✅ Catalysts for {', '.join(top3)}")
    except Exception as e:
        print(f"    ❌ {e}")
        catalysts = {}

    print("  🪙 Fetching commodities (yfinance)...")
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
        poly_html = f'''<div class="card" style="margin-bottom:1rem">
  <div class="card-title">🎰 Polymarket — Barron147</div>
  <div style="font-size:.7rem;color:var(--mute);padding-bottom:4px">Geopolitics & Event Contracts</div>
  {bets_html}
  <div style="display:flex;justify-content:space-between;padding:8px 0 0;border-top:1px solid var(--border);font-size:.8rem;font-weight:700"><span>Wins vs Losses</span><span>{pm_wr_summary['wins']}W / {pm_wr_summary['losses']}L</span></div>
</div>'''

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

        alpaca_html = f"""<div class="card">
    <div class="card-title">🦙 Livermore Darvis</div>
    <div style="font-size:.65rem;color:var(--mute);margin-bottom:6px">Unified bot book · {total_trades} trades</div>
    {all_rows}
    <div style="display:flex;justify-content:space-between;padding:3px 0 0;font-size:.8rem;font-weight:700"><span>Inception ROI</span><span style="color:{total_color}">{total_str}</span></div>
  </div>"""

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
        economies=economies
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
        bot_accounts_html=bot_accounts_html, evo_fund_html=evo_fund_html
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
