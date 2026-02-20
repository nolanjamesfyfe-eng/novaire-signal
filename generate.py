#!/usr/bin/env python3
"""
Novaire Signal — Daily Brief Generator
Generates index.html with premium dark + gold aesthetic + live data
"""

import requests
import json
import math
import sys
import traceback
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
OUTPUT = "/tmp/novaire-signal/index.html"

CITIES = [
    {"name": "Bangkok",    "flag": "🇹🇭", "lat": 13.7563,  "lon": 100.5018},
    {"name": "Medellín",   "flag": "🇨🇴", "lat": 6.2442,   "lon": -75.5812},
    {"name": "Edmonton",   "flag": "🇨🇦", "lat": 53.5461,  "lon": -113.4938},
    {"name": "Montevideo", "flag": "🇺🇾", "lat": -34.9011, "lon": -56.1645},
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
    for city in CITIES:
        try:
            url = (f"https://api.open-meteo.com/v1/forecast"
                   f"?latitude={city['lat']}&longitude={city['lon']}"
                   f"&current=temperature_2m,weathercode&timezone=auto")
            r = requests.get(url, timeout=10)
            data = r.json()
            cur = data.get("current", {})
            temp = cur.get("temperature_2m")
            code = cur.get("weathercode", 0)
            condition = WEATHER_CODES.get(code, "Unknown")
            results.append({**city, "temp": temp, "condition": condition, "ok": True})
        except Exception as e:
            results.append({**city, "temp": None, "condition": "—", "ok": False})
    return results

def fetch_bangkok_post():
    headlines = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
        r = requests.get("https://www.bangkokpost.com", headers=headers, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()
        for sel in ["h2.headline a", "h3.headline a", ".article-headline a",
                    "article h2 a", "article h3 a", ".story-title a"]:
            for el in soup.select(sel):
                txt = el.get_text(strip=True)
                if len(txt) > 20 and txt not in seen:
                    seen.add(txt)
                    href = el.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://www.bangkokpost.com" + href
                    headlines.append({"title": txt, "url": href})
                if len(headlines) >= 5: break
            if len(headlines) >= 5: break
        if not headlines:
            for a in soup.find_all("a", href=True):
                txt = a.get_text(strip=True)
                if len(txt) > 30 and txt not in seen:
                    href = a["href"]
                    if "bangkokpost.com" in href or href.startswith("/"):
                        if href.startswith("/"): href = "https://www.bangkokpost.com" + href
                        seen.add(txt)
                        headlines.append({"title": txt, "url": href})
                if len(headlines) >= 5: break
    except Exception as e:
        headlines = [{"title": f"Bangkok Post unavailable", "url": "#"}]
    return headlines[:5] if headlines else [{"title": "No headlines fetched", "url": "#"}]

def fetch_trending_recs():
    """
    Fetch daily trending recs:
    - Movie/Show: FlixPatrol #1 Netflix movie + OMDB description
    - Book: Amazon Business bestsellers #1 title + Open Library description
    Fallback to hardcoded picks on any failure.
    """
    rec_movie = {"label": "📺 Now Watching", "title": "Margin Call", "meta": "Prime · Kevin Spacey, Jeremy Irons", "summary": "24 hours inside a bank on the eve of financial collapse. Cold, precise, and brilliantly acted."}
    rec_book  = {"label": "📖 Now Reading",  "title": "The Black Swan", "meta": "Nassim Taleb · Philosophy/Risk", "summary": "Why rare, unpredictable events drive history and markets. The book that should have predicted 2008."}

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
    "TSE:VZLA": "VZLA.TO",
    "ASX:AEU":  "AEU.AX",
    "CVE:AAG":  "AAG.V",
    "BQSSF":    "BQSSF",
    "CVE:EU":   "EU.V",
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
        r = requests.get(GSHEET_CSV_URL, timeout=15)
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

        # Portfolio meta: CAD total row
        if not meta.get("basis_cad"):
            for cell in row:
                if "$99" in cell or "$100" in cell or "$98" in cell:
                    v = parse_price(cell)
                    if v and 50000 < v < 200000:
                        meta["basis_cad"] = v
                        break

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
    return results, holdings_source

def fetch_catalysts(top3_tickers):
    """Fetch news for top 3 tickers. Returns dict with freshness info."""
    try:
        import yfinance as yf
    except ImportError:
        return {}

    cats = {}
    now = datetime.now(timezone.utc)
    fresh_cutoff = now - timedelta(hours=48)  # 48h hard cutoff — no old fluff

    for ticker in top3_tickers:
        if ticker.startswith("_"):
            cats[ticker] = None
            continue
        try:
            t = yf.Ticker(ticker)
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
            hist = t.history(period="2d")
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
        "BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT",
        "XRP": "XRPUSDT", "ZEC": "ZECUSDT", "TON": "TONUSDT",
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
            hist = yf.Ticker(ticker).history(period="2d")
            if len(hist) >= 1:
                raw = float(hist["Close"].iloc[-1])
                rate = 1.0 / raw if invert else raw
            else:
                rate = fallback
        except Exception:
            rate = fallback

        # Format rate
        if currency in ("KRW", "COP", "JPY"):
            fmt = f"{rate:,.3f}"
        else:
            fmt = f"{rate:.3f}"

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
                commodities, crypto, fx, zodiac, thai_word, sat_word, motivation, rec_movie=None, rec_book=None, fx_rates=None, holdings_source=None):

    now       = datetime.now(timezone.utc)
    date_str  = now.strftime("%A, %B %-d, %Y")
    gen_time  = now.strftime("%H:%M UTC")

    # ── Portfolio calculations ──
    total_usd   = 0
    sector_totals = {}
    port_sorted = []

    for h in HOLDINGS:
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
            <td style="text-align:right">{shares:,}</td>
            <td style="text-align:right">{price_str}</td>
            <td style="text-align:right">{chg_html}</td>
            <td style="text-align:right;font-weight:600">{value_str}</td>
          </tr>"""

    # ── Allocation chart ──
    alloc_sorted = sorted(sector_totals.items(), key=lambda x: x[1], reverse=True)
    alloc_list   = [(s, v, "") for s, v in alloc_sorted]
    donut_svg    = build_donut(alloc_list)
    legend_html  = build_legend(alloc_list, total_usd)

    # ── Top 3 by value ──
    top3 = [t for t, *_ in port_sorted[:3]]

    # ── Catalysts HTML (top 3, 48h fresh only) ──
    # If ALL 3 have no news → one collapsed line. Otherwise show per-ticker lines.
    fresh_cats  = [(t, catalysts.get(t)) for t in top3 if catalysts.get(t) and catalysts.get(t, {}).get("fresh")]
    no_news_tks = [t for t in top3 if not (catalysts.get(t) and catalysts.get(t, {}).get("fresh"))]

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
            fx_rates_html += f"""
        <div class="fx-item">
          <div class="fx-ccy">{d['icon']} {ccy}</div>
          <span class="fx-rate">{d['fmt']}</span>
        </div>"""

    # ── Weather HTML ──
    weather_html = ""
    for w in weather:
        temp_str = f"{w['temp']:.0f}°C" if w["temp"] is not None else "—"
        weather_html += f"""
        <div class="weather-item">
          <div class="city">{w['flag']} {w['name']}</div>
          <div class="temp">{temp_str}</div>
          <div class="condition">{w['condition']}</div>
        </div>"""

    # ── Bangkok news HTML ──
    bkk_html = ""
    for item in bangkok_news[:1]:
        bkk_html += f'<div class="thai-news-item"><a href="{item["url"]}" style="color:var(--text);text-decoration:none" target="_blank">{item["title"]}</a></div>'

    # ── ZeroHedge HTML ──
    zh_html = ""
    for i, item in enumerate(zh_news[:4], 1):
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
        <div class="commodity-item">
          <div class="commodity-name {c['cls']}">{c['name']}</div>
          <div class="commodity-price {c['cls']}">{price_str}</div>
          <div class="commodity-unit">{c['unit']}</div>
          <div class="commodity-change">{chg_html}</div>
        </div>"""

    # ── Crypto HTML ──
    crypto_colors = {"BTC": "#f7931a","ETH": "#627eea","SOL": "#9945ff",
                     "XRP": "#346aa9","TON": "#0098ea","ZEC": "#f4b728"}
    crypto_html = ""
    for coin in ["BTC","ETH","SOL","XRP","TON","ZEC"]:
        c     = crypto.get(coin, {})
        price = c.get("price")
        chg   = c.get("change")
        price_str = fmt_price(price) if price else "—"
        chg_html  = fmt_pct(chg) if chg is not None else '<span style="color:var(--dim)">—</span>'
        color     = crypto_colors.get(coin, "#e0dde8")
        crypto_html += f"""
        <div class="crypto-item">
          <div class="crypto-symbol" style="color:{color}">{coin}</div>
          <div class="crypto-price" style="color:{color}">{price_str}</div>
          <div class="crypto-change">{chg_html}</div>
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
      --bg:#0a0a0c;--surface:#111116;--border:#1e1e26;--text:#e8e6f0;--dim:#8a8699;--mute:#4a4760;
      --gold:#c9a84c;--gold-dim:rgba(201,168,76,.12);--gold-mid:rgba(201,168,76,.25);
      --green:#2a9d8f;--red:#e63946;--blue:#5a7bc4;--violet:#9470c8;
      --sans:'Inter',sans-serif;--serif:'Cormorant Garamond',serif;--r:6px;
    }}
    html{{scroll-behavior:smooth}}
    body{{font-family:var(--sans);background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:32px 16px;font-size:14px;line-height:1.5}}
    body{{font-family:var(--sans);background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:32px 16px;font-size:14px;line-height:1.5}}
    .container{{max-width:720px;margin:0 auto}}

    .header-brand{{text-align:center;padding-bottom:20px}}

    .dateline{{text-align:center;padding:0 0 28px;margin-bottom:28px;border-bottom:1px solid var(--border)}}
    .dateline .date{{font-size:.7rem;letter-spacing:.2em;text-transform:uppercase;color:var(--dim)}}
    .dateline .gen{{font-size:.6rem;color:var(--mute);margin-top:3px}}

    .card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px;margin-bottom:14px}}
    .card-title{{font-size:.6rem;font-weight:600;letter-spacing:.24em;text-transform:uppercase;color:var(--gold);margin-bottom:16px;display:flex;align-items:center;gap:8px}}
    .card-title::after{{content:'';flex:1;height:1px;background:linear-gradient(90deg,var(--gold-mid),transparent)}}

    .quote{{margin-bottom:8px;padding-left:10px;border-left:1px solid var(--gold-mid)}}
    .quote:last-child{{margin-bottom:0}}
    .quote-type{{font-size:.6rem;color:var(--gold);text-transform:uppercase;letter-spacing:.14em;margin-bottom:2px;font-weight:600}}
    .quote-text{{font-family:var(--serif);font-size:1.1rem;font-style:italic;color:var(--text);line-height:1.55}}
    .quote-author{{font-size:.68rem;color:var(--dim);margin-top:3px}}
    #quotes-card{{padding:14px 16px}}

    .weather-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
    .weather-item{{text-align:center;padding:12px 6px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r)}}
    .weather-item .city{{font-size:.65rem;color:var(--dim);margin-bottom:5px;letter-spacing:.04em}}
    .weather-item .temp{{font-size:1.25rem;font-weight:500;color:var(--gold);font-family:var(--serif)}}
    .weather-item .condition{{font-size:.62rem;color:var(--dim);margin-top:3px;line-height:1.3}}

    .thai-news-compact{{margin-top:14px;padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r)}}
    .thai-news-header{{font-size:.58rem;color:var(--gold);text-transform:uppercase;letter-spacing:.16em;margin-bottom:8px;font-weight:600}}
    .thai-news-item{{font-size:.82rem;color:var(--text);padding:5px 0;border-bottom:1px solid var(--border);line-height:1.45}}
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

    .commodities-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
    .commodity-item{{background:var(--bg);padding:12px;border:1px solid var(--border);border-radius:var(--r);text-align:center}}
    .commodity-name{{font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:5px;font-weight:600}}
    .commodity-price{{font-family:var(--serif);font-size:1.2rem;font-weight:400;margin-bottom:2px}}
    .commodity-unit{{font-size:.6rem;color:var(--dim)}}
    .commodity-change{{font-size:.72rem;margin-top:3px}}
    .c-gold{{color:#c9a84c}}.c-silver{{color:#b8b8b8}}.c-copper{{color:#b87333}}
    .c-oil{{color:#8b7355}}.c-palladium{{color:#ccc}}.c-uranium{{color:#7fc87f}}

    .crypto-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
    .crypto-item{{background:var(--bg);padding:10px 8px;border:1px solid var(--border);border-radius:var(--r);text-align:center}}
    .crypto-symbol{{font-size:.62rem;font-weight:600;text-transform:uppercase;letter-spacing:.12em;margin-bottom:4px}}
    .crypto-price{{font-family:var(--serif);font-size:1.05rem;font-weight:400;margin-bottom:2px}}
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

    .thai-word-box{{display:flex;align-items:center;justify-content:center;gap:14px;padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r)}}
    .thai-word-box .word{{font-family:var(--serif);font-size:1.1rem;color:var(--gold)}}
    .thai-word-box .dot{{color:var(--mute)}}
    .thai-word-box .meaning{{font-size:.78rem;color:var(--dim)}}
    .sat-word-box{{padding:14px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r)}}
    .sat-word{{font-family:var(--serif);font-size:1.2rem;color:var(--gold);font-weight:500;margin-bottom:6px}}
    .sat-def{{font-size:.82rem;color:var(--text);margin-bottom:10px;font-style:italic}}
    .sat-sentence{{font-size:.78rem;color:var(--dim);line-height:1.5;border-left:2px solid var(--gold-mid);padding-left:10px}}

    .fx-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:4px}}
    .fx-item{{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:10px 8px;text-align:center;font-size:.78rem;color:var(--dim)}}
    .fx-item .fx-ccy{{font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;color:var(--dim)}}
    .fx-rate{{display:block;font-family:'Courier New',monospace;font-size:.95rem;font-weight:600;color:var(--gold);margin-top:2px}}

    .feed-controls{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}}
    .feed-refresh{{font-size:.6rem;color:var(--dim);letter-spacing:.08em;cursor:pointer;background:none;border:1px solid var(--border);color:var(--dim);padding:4px 8px;border-radius:var(--r);font-family:var(--sans)}}
    .feed-refresh:hover{{border-color:var(--gold);color:var(--gold)}}
    .feed-status{{font-size:.62rem;color:var(--dim);font-style:italic}}
    .feed-item{{padding:12px 0;border-bottom:1px solid var(--border)}}
    .feed-item:last-child{{border-bottom:none}}
    .feed-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}}
    .feed-author{{display:flex;align-items:center;gap:7px}}
    .feed-avatar{{width:26px;height:26px;border-radius:50%;object-fit:cover;flex-shrink:0;background:var(--border)}}
    .feed-name{{font-size:.78rem;font-weight:600;color:var(--text)}}
    .feed-handle{{font-size:.68rem;color:var(--dim)}}
    .feed-time{{font-size:.64rem;color:var(--dim)}}
    .feed-text{{font-size:.84rem;color:var(--text);line-height:1.5;word-break:break-word;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
    .feed-stats{{display:flex;gap:12px;margin-top:6px}}
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

    .footer{{text-align:center;padding:40px 0 24px;border-top:1px solid var(--border);margin-top:28px}}
    .footer-logo{{font-family:var(--serif);font-size:1.8rem;font-weight:300;letter-spacing:.18em;text-transform:uppercase;color:var(--text);margin-bottom:4px}}
    .footer-logo span{{color:var(--gold);font-style:italic}}
    .footer-tagline{{font-size:.62rem;color:var(--dim);letter-spacing:.14em;text-transform:uppercase}}
    .footer-sub{{font-size:.58rem;color:var(--mute);margin-top:6px}}

    @media(max-width:600px){{
      .weather-grid{{grid-template-columns:repeat(2,1fr)}}
      .commodities-grid{{grid-template-columns:repeat(2,1fr)}}
      .crypto-grid{{grid-template-columns:repeat(2,1fr)}}
      .fx-grid{{grid-template-columns:repeat(2,1fr)}}
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
    <div class="footer-logo">Novaire <span>Signal</span></div>
    <div style="font-family:var(--serif);font-size:.9rem;font-style:italic;color:var(--gold);opacity:0.7;letter-spacing:.04em;margin-top:2px;">Deciphering through the noise.</div>
  </div>

  <!-- DATE / GENERATION LINE -->
  <div class="dateline">
    <div class="date">{date_str}</div>
    <div class="gen">Generated {gen_time} · Live data</div>
  </div>

  <!-- QUOTES (2 per day — client-side localStorage dedup) -->
  <div class="card">
    <div class="card-title">📜 Quotes</div>
    <div id="quote-investing" class="quote">
      <div class="quote-type">Investing</div>
      <div class="quote-text" id="qt-inv-text"></div>
      <div class="quote-author" id="qt-inv-auth"></div>
    </div>
    <div id="quote-psychology" class="quote">
      <div class="quote-type">Psychology</div>
      <div class="quote-text" id="qt-psy-text"></div>
      <div class="quote-author" id="qt-psy-auth"></div>
    </div>
  </div>

  <!-- WEATHER + THAILAND NEWS -->
  <div class="card">
    <div class="card-title">🌤 Weather</div>
    <div class="weather-grid">
      {weather_html}
    </div>
    <div class="thai-news-compact">
      <div class="thai-news-header">🇹🇭 Thailand News</div>
      {bkk_html}
    </div>
  </div>

  <!-- FX RATES -->
  <div class="card">
    <div class="card-title">💱 FX Rates — 1 USD =</div>
    <div class="fx-grid">
      {fx_rates_html}
    </div>
  </div>

  <!-- STAR SIGN — inline symbol + name, compact -->
  <div class="card">
    <div class="star-sign">
      <div class="star-sign-main" data-symbol="{zodiac['symbol']}">{zodiac['name']}<span class="star-sign-range">{zodiac['range']}</span></div>
      <div class="star-sign-desc">{zodiac['desc']}</div>
    </div>
  </div>

  <!-- ZEROHEDGE -->
  <div class="card">
    <div class="card-title">📰 ZeroHedge — Top Headlines</div>
    {zh_html}
  </div>

  <!-- SIGNAL FEED -->
  <div class="card">
    <div class="card-title">📡 Signal Feed — Top 5 by Engagement</div>
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

    // Enforce display order: zerohedge(1), TheEconomist(2), KobeissiLetter(3), engagement(4,5)
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
          <div class="feed-text">${{escHtml(p.text)}}</div>
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
        const windowHours = json.windowHours || 4;
        status.textContent = 'Top ' + allPosts.length + ' by engagement · last ' + windowHours + 'h · updated ' + ageStr;
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

  <!-- PORTFOLIO (collapsed by default) -->
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
        <div class="psum-value" style="color:var(--blue);font-size:1.1rem">${PORT_BASIS_CAD:,.0f}</div>
      </div>
      <div class="psum-item">
        <div class="psum-label">ATH (w/ w/d)</div>
        <div class="psum-value" style="color:var(--violet);font-size:1.1rem">${PORT_ATH:,}</div>
      </div>
      <div class="psum-item">
        <div class="psum-label">ROI Abs.</div>
        <div class="psum-value" style="color:var(--green);font-size:1.1rem">${PORT_ROI_ABS:,.0f}</div>
      </div>
    </div>

    <button class="expand-btn" id="holdings-btn" onclick="toggleHoldings()">
      <span id="holdings-arrow">▼</span>&nbsp; Expand Holdings
    </button>

    <div class="holdings-table-wrap" id="holdings-wrap">
      <table class="portfolio-table">
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
      </table>
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
          <div class="total-value" style="color:var(--blue)">${PORT_BASIS_CAD:,.0f}</div>
        </div>
        <div class="total-item">
          <div class="total-label">ATH</div>
          <div class="total-value" style="color:var(--violet)">${PORT_ATH:,}</div>
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
        <span class="fallback-badge">est</span> = estimated / last known price
      </div>
    </div>
  </div>

  <!-- CATALYSTS — Top 3 only, fresh news highlighted -->
  <div class="card">
    <div class="card-title">🔍 Catalysts — Top 3 Holdings</div>
    {cats_html}
  </div>

  <!-- RADAR IDEAS — 3 crypto + 3 resource, live from Reddit/News/4Chan -->
  <div class="card">
    <div class="card-title">🎯 Radar Ideas</div>
    <div class="radar-label">🪙 Micro-Cap Crypto</div>
    {radar_crypto_html}
    <div class="radar-label" style="margin-top:12px">⛏️ Micro-Cap Resources</div>
    {radar_resource_html}
    <div style="margin-top:8px;font-size:.6rem;color:var(--mute)">Live · Reddit · News · 4Chan /biz/ · Barbell plays $500–$1K · Updates every build</div>
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


    <!-- RECOMMENDATIONS — client-side localStorage rotation -->
  <div class="card">
    <div class="card-title">🎬 Recommendations</div>
    <div class="rec-grid">
      <div class="rec-item">
        <div class="rec-label">{rec_movie['label'] if rec_movie else '📺 Now Watching'}</div>
        <div class="rec-title">{rec_movie['title'] if rec_movie else '—'}</div>
        <div class="rec-meta">{rec_movie['meta'] if rec_movie else ''}</div>
        <div class="rec-summary">{rec_movie['summary'] if rec_movie else ''}</div>
      </div>
      <div class="rec-item">
        <div class="rec-label">{rec_book['label'] if rec_book else '📖 Now Reading'}</div>
        <div class="rec-title">{rec_book['title'] if rec_book else '—'}</div>
        <div class="rec-meta">{rec_book['meta'] if rec_book else ''}</div>
        <div class="rec-summary">{rec_book['summary'] if rec_book else ''}</div>
      </div>
    </div>
    <div style="margin-top:12px;font-size:.68rem;color:var(--dim);text-align:center">
      Updated daily · Netflix trending + Amazon Business #1
    </div>
  </div>

  <!-- THAI WORD OF THE DAY -->
  <div class="card">
    <div class="card-title">🇹🇭 Thai Word of the Day</div>
    <div class="thai-word-box">
      <span class="word">{thai_word['thai']}</span>
      <span class="dot">•</span>
      <span class="meaning">{thai_word['meaning']}</span>
    </div>
  </div>

  <!-- NOVAIRE'S WORD OF THE DAY -->
  <div class="card">
    <div class="card-title">📖 Novaire's Word of the Day</div>
    <div class="sat-word-box">
      <div class="sat-word">{sat_word['word']}</div>
      <div class="sat-def">{sat_word['def']}</div>
      <div class="sat-sentence">"{sat_word['sentence']}"</div>
    </div>
  </div>

  <!-- DAILY MOTIVATION -->
  <div class="card">
    <div class="card-title">💪 Daily Motivation</div>
    <div class="quote" style="border-left-color:rgba(90,123,196,.35)">
      <div class="quote-type" style="color:var(--blue)">Kaizen Mindset</div>
      <div class="quote-text">"{motivation['text']}"</div>
      <div class="quote-author">— {motivation['author']}</div>
    </div>
  </div>

  <!-- FOOTER BRANDING -->
  <div class="footer">
    <div class="footer-logo">Novaire <span>Signal</span></div>
    
    <div class="footer-sub">Updated every 2 hours</div>
  </div>

</div>

<!-- CLIENT-SIDE JS: Quote dedup + Holdings toggle + Recs rotation -->
<script>
// ── Quote arrays (30+ per category) ──
const QUOTES_INVESTING = {QUOTES_JS_INVESTING};
const QUOTES_PSYCHOLOGY = {QUOTES_JS_PSYCHOLOGY};

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

(function renderQuotes() {{
  const qi = getQuoteForToday('investing', QUOTES_INVESTING);
  const qp = getQuoteForToday('psychology', QUOTES_PSYCHOLOGY);
  document.getElementById('qt-inv-text').textContent = '\u201c' + qi.text + '\u201d';
  document.getElementById('qt-inv-auth').textContent = '\u2014 ' + qi.author;
  document.getElementById('qt-psy-text').textContent = '\u201c' + qp.text + '\u201d';
  document.getElementById('qt-psy-auth').textContent = '\u2014 ' + qp.author;
}})();

// ── Holdings toggle ──
function toggleHoldings() {{
  const wrap = document.getElementById('holdings-wrap');
  const btn  = document.getElementById('holdings-btn');
  const arrow = document.getElementById('holdings-arrow');
  const isOpen = wrap.classList.toggle('open');
  arrow.style.transform = isOpen ? 'rotate(180deg)' : '';
  btn.innerHTML = (isOpen ? '<span id="holdings-arrow" style="display:inline-block;transform:rotate(180deg)">▼</span>' : '<span id="holdings-arrow">▼</span>') + '&nbsp; ' + (isOpen ? 'Collapse Holdings' : 'Expand Holdings');
}}

// Recommendations are now server-side rendered (live trending data)
</script>
</body>
</html>"""
    return html

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

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
        portfolio_data, holdings_source = fetch_portfolio(usdcad=fx["usdcad"], audusd=fx["audusd"])
        loaded = sum(1 for v in portfolio_data.values() if v.get("price"))
        print(f"    ✅ {loaded}/{len(holdings_source)} tickers loaded")
    except Exception as e:
        print(f"    ❌ {e}")
        portfolio_data = {}

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

    zodiac    = get_zodiac()
    doy       = day_of_year()
    thai_word = pick(THAI_WORDS, 5)
    sat_word  = pick(SAT_WORDS, 7)  # Different offset than Thai word
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

    print("  🎨 Generating HTML...")
    html = render_html(
        weather, bangkok_news, zh_news, portfolio_data, catalysts,
        commodities, crypto, fx, zodiac, thai_word, sat_word, motivation,
        rec_movie=rec_movie, rec_book=rec_book, fx_rates=fx_rates,
        holdings_source=holdings_source
    )

    import os
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ HTML saved to {OUTPUT} ({len(html):,} bytes)")

if __name__ == "__main__":
    main()
