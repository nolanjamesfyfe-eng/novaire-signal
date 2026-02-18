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
# FVL.V → FGOVF (OTC); MAXX.V → MAXXF (OTC); VZLA.V → VZLA (OTC); MOLY.V → fallback
HOLDINGS = [
    {"ticker": "HG.CN",  "display": "HG",    "name": "Hydrograph",         "shares": 10000, "sector": "Graphene"},
    {"ticker": "GLO.TO", "display": "GLO",   "name": "Global Atomic",       "shares": 23000, "sector": "Uranium"},
    {"ticker": "FGOVF",  "display": "FVL",   "name": "FreeGold Ventures",   "shares": 10000, "sector": "Gold"},
    {"ticker": "DML.TO", "display": "DML",   "name": "Denison",             "shares": 1000,  "sector": "Uranium"},
    {"ticker": "BNNLF",  "display": "BNNLF", "name": "Bannerman Energy",    "shares": 1300,  "sector": "Uranium"},
    {"ticker": "MAXXF",  "display": "MAXX",  "name": "Power Mining Corp",   "shares": 2000,  "sector": "Silver"},
    {"ticker": "TOM.V",  "display": "TOM",   "name": "Trinity One Metals",  "shares": 5000,  "sector": "Silver"},
    {"ticker": "LOT.AX", "display": "LOT",   "name": "Lotus Resources",     "shares": 956,   "sector": "Uranium"},
    {"ticker": "NAM.V",  "display": "NAM",   "name": "New Age Metals",      "shares": 3772,  "sector": "Copper"},
    {"ticker": "PNPN.V", "display": "PNPN",  "name": "Power Nickel",        "shares": 1000,  "sector": "Copper"},
    {"ticker": "SVE.V",  "display": "SVE",   "name": "Silver One",          "shares": 2000,  "sector": "Silver"},
    {"ticker": "PEGA.V", "display": "PEGA",  "name": "Pegasus Uranium",     "shares": 20000, "sector": "Uranium"},
    {"ticker": "CAPT.V", "display": "CAPT",  "name": "Capitan Silver",      "shares": 500,   "sector": "Silver"},
    {"ticker": "VZLA",   "display": "VZLA",  "name": "Vizsla Silver",       "shares": 200,   "sector": "Silver"},
    {"ticker": "AEU.AX", "display": "AEU",   "name": "Atomic Eagle",        "shares": 2027,  "sector": "Uranium"},
    {"ticker": "AAG.V",  "display": "AAG",   "name": "Aftermath Silver",    "shares": 1000,  "sector": "Copper"},
    {"ticker": "BQSSF",  "display": "BQSSF", "name": "Boss Energy",         "shares": 500,   "sector": "Uranium"},
    {"ticker": "EU.V",   "display": "EU",    "name": "Encore Energy",       "shares": 125,   "sector": "Uranium"},
    # MOLY.V (GreenLand Resources) - not on Yahoo Finance; hardcoded fallback
    {"ticker": "_MOLY_FALLBACK", "display": "MOLY", "name": "GreenLand Resources", "shares": 5000, "sector": "Molybdenum"},
]

# Hardcoded fallback prices (USD) for tickers unavailable on Yahoo Finance
FALLBACK_PRICES = {
    "_MOLY_FALLBACK": 0.05,   # GreenLand Resources - estimated
}

HOLDINGS_MAP = {h["ticker"]: {"shares": h["shares"], "name": h["name"], "display": h.get("display", h["ticker"].split(".")[0])} for h in HOLDINGS}
SECTORS      = {h["ticker"]: h["sector"] for h in HOLDINGS}

# Portfolio basis stats (from spreadsheet)
PORT_BASIS_CAD = 99_234.14
PORT_ATH       = 113_522
PORT_ROI_ABS   = 24_660.95

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

def fetch_zerohedge():
    headlines = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get("https://www.zerohedge.com", headers=headers, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()
        for sel in ["h2 a", "h3 a", ".article-summary h2 a", ".post-title a",
                    "[class*='headline'] a", "[class*='title'] a", "article a"]:
            for el in soup.select(sel):
                txt = el.get_text(strip=True)
                if len(txt) > 20 and txt not in seen:
                    seen.add(txt)
                    href = el.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://www.zerohedge.com" + href
                    headlines.append({"title": txt, "url": href})
                if len(headlines) >= 4: break
            if len(headlines) >= 4: break
    except Exception as e:
        headlines = [{"title": f"ZeroHedge unavailable", "url": "#"}]
    return headlines[:4] if headlines else [{"title": "No headlines fetched", "url": "#"}]

def fetch_portfolio():
    try:
        import yfinance as yf
    except ImportError:
        return {}

    results = {}
    for h in HOLDINGS:
        ticker = h["ticker"]
        shares = h["shares"]

        # Handle hardcoded fallback tickers
        if ticker.startswith("_") and ticker in FALLBACK_PRICES:
            p = FALLBACK_PRICES[ticker]
            results[ticker] = {"price": p, "change": None, "value": p * shares, "fallback": True}
            continue

        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", auto_adjust=True)
            hist = hist[hist["Close"].notna()]
            if len(hist) >= 2:
                p  = float(hist["Close"].iloc[-1])
                pp = float(hist["Close"].iloc[-2])
                chg = (p - pp) / pp * 100
            elif len(hist) == 1:
                p   = float(hist["Close"].iloc[-1])
                chg = None
            else:
                fi = t.fast_info
                p = getattr(fi, "last_price", None)
                chg = None

            if p and p > 0:
                results[ticker] = {"price": p, "change": chg, "value": p * shares, "fallback": False}
            else:
                results[ticker] = {"price": None, "change": None, "value": None, "fallback": False}
        except Exception:
            results[ticker] = {"price": None, "change": None, "value": None, "fallback": False}
    return results

def fetch_catalysts(top3_tickers):
    """Fetch news for top 3 tickers. Returns dict with freshness info."""
    try:
        import yfinance as yf
    except ImportError:
        return {}

    cats = {}
    now = datetime.now(timezone.utc)
    # "Fresh" = within last 4 calendar days (covers 2 market days + weekend)
    fresh_cutoff = now - timedelta(days=4)

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
        "URA":  {"name": "Uranium",  "unit": "ETF",  "cls": "c-uranium"},
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
    return {"usdcad": usdcad}

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
                commodities, crypto, fx, zodiac, thai_word, motivation):

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

    # ── Catalysts HTML (top 3, fresh-only dates highlighted) ──
    cats_html = ""
    for ticker in top3:
        cat = catalysts.get(ticker)
        display = HOLDINGS_MAP.get(ticker, {}).get("display", ticker.split(".")[0])
        if cat:
            badge_cls = "catalyst-badge" if cat["fresh"] else "catalyst-badge stale"
            fresh_note = "" if cat["fresh"] else ' <span style="color:var(--mute);font-style:italic;font-size:.6rem">(older than 2 market days)</span>'
            source_str = f' · {cat["source"]}' if cat["source"] else ""
            cats_html += f"""
            <div class="catalyst-item">
              <span class="catalyst-ticker">{display}</span>
              <span class="{badge_cls}">{cat['date']}</span>
              <div class="catalyst-headline">{cat['title']}{fresh_note}</div>
              <div class="catalyst-source">{cat['date']}{source_str}</div>
            </div>"""
        else:
            cats_html += f"""
            <div class="catalyst-item">
              <span class="catalyst-ticker">{display}</span>
              <span class="catalyst-badge stale">No fresh news</span>
              <div class="catalyst-headline" style="color:var(--dim);font-style:italic">No news from last 2 market days</div>
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
    for item in bangkok_news[:3]:
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

    # ── Radar dates ──
    radar_added = {
        "Penumbra":               "Jan 15",
        "Hyperlane":              "Jan 22",
        "Forum Energy Metals":    "Feb 3",
        "American Lithium Energy":"Feb 10",
    }

    # Full HTML template
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Novaire Signal — Daily Brief</title>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400;1,500&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0a0a0c;
      --surface: #111114;
      --border: #1d1d22;
      --text: #d8d5e0;
      --dim: #6a677a;
      --mute: #3a3840;
      --gold: #c9a84c;
      --gold-dim: rgba(201,168,76,.1);
      --gold-mid: rgba(201,168,76,.2);
      --blue: #5a7bc4;
      --blue-dim: rgba(90,123,196,.1);
      --violet: #9470c8;
      --serif: 'Cormorant Garamond', Georgia, serif;
      --sans: 'Inter', -apple-system, sans-serif;
      --green: #3d9e6a;
      --red: #cc4f4f;
      --r: 2px;
    }}
    *{{margin:0;padding:0;box-sizing:border-box}}
    html{{scroll-behavior:smooth}}
    body{{font-family:var(--sans);background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:32px 16px;font-size:14px;line-height:1.5}}
    .container{{max-width:720px;margin:0 auto}}

    .dateline{{text-align:center;padding:0 0 28px;margin-bottom:28px;border-bottom:1px solid var(--border)}}
    .dateline .date{{font-size:.7rem;letter-spacing:.2em;text-transform:uppercase;color:var(--dim)}}
    .dateline .gen{{font-size:.6rem;color:var(--mute);margin-top:3px}}

    .card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px;margin-bottom:14px}}
    .card-title{{font-size:.6rem;font-weight:600;letter-spacing:.24em;text-transform:uppercase;color:var(--gold);margin-bottom:16px;display:flex;align-items:center;gap:8px}}
    .card-title::after{{content:'';flex:1;height:1px;background:linear-gradient(90deg,var(--gold-mid),transparent)}}

    .quote{{margin-bottom:14px;padding-left:14px;border-left:2px solid var(--gold-mid)}}
    .quote:last-child{{margin-bottom:0}}
    .quote-type{{font-size:.58rem;color:var(--gold);text-transform:uppercase;letter-spacing:.16em;margin-bottom:3px;font-weight:600}}
    .quote-text{{font-family:var(--serif);font-size:1.1rem;font-style:italic;color:var(--text);line-height:1.55}}
    .quote-author{{font-size:.72rem;color:var(--dim);margin-top:3px}}

    .weather-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
    .weather-item{{text-align:center;padding:12px 6px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r)}}
    .weather-item .city{{font-size:.65rem;color:var(--dim);margin-bottom:5px;letter-spacing:.04em}}
    .weather-item .temp{{font-size:1.25rem;font-weight:500;color:var(--gold);font-family:var(--serif)}}
    .weather-item .condition{{font-size:.62rem;color:var(--dim);margin-top:3px;line-height:1.3}}

    .thai-news-compact{{margin-top:14px;padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:var(--r)}}
    .thai-news-header{{font-size:.58rem;color:var(--gold);text-transform:uppercase;letter-spacing:.16em;margin-bottom:8px;font-weight:600}}
    .thai-news-item{{font-size:.82rem;color:var(--text);padding:5px 0;border-bottom:1px solid var(--border);line-height:1.45}}
    .thai-news-item:last-child{{border-bottom:none}}

    .star-sign{{display:flex;align-items:center;gap:16px;padding:4px 0}}
    .star-sign-left{{text-align:center;flex-shrink:0;width:60px}}
    .star-sign-symbol{{font-size:1.6rem;line-height:1}}
    .star-sign-main{{font-family:var(--serif);font-size:1rem;color:var(--gold);margin-top:3px}}
    .star-sign-range{{font-size:.58rem;color:var(--dim);letter-spacing:.06em;text-transform:uppercase;margin-top:2px}}
    .star-sign-desc{{font-size:.78rem;color:var(--dim);line-height:1.5;flex:1}}

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

    .catalyst-item{{padding:10px 0;border-bottom:1px solid var(--border)}}
    .catalyst-item:last-child{{border-bottom:none}}
    .catalyst-ticker{{font-weight:600;color:var(--gold);font-size:.85rem}}
    .catalyst-badge{{display:inline-block;background:var(--gold-dim);color:var(--gold);font-size:.6rem;padding:2px 7px;border-radius:2px;margin-left:6px}}
    .catalyst-badge.stale{{background:rgba(106,103,122,.1);color:var(--dim)}}
    .catalyst-headline{{font-size:.8rem;color:var(--text);margin-top:5px;line-height:1.45}}
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

    .radar-category{{font-size:.58rem;font-weight:600;color:var(--gold);text-transform:uppercase;letter-spacing:.2em;margin:16px 0 8px;padding-bottom:5px;border-bottom:1px solid var(--gold-mid)}}
    .radar-category:first-child{{margin-top:0}}
    .radar-item{{display:flex;align-items:flex-start;gap:10px;padding:9px 0;border-bottom:1px solid var(--border)}}
    .radar-item:last-child{{border-bottom:none}}
    .radar-icon{{font-size:.85rem;width:22px;text-align:center;padding-top:1px}}
    .radar-content{{flex:1}}
    .radar-name{{font-size:.85rem;font-weight:600;color:var(--text)}}
    .radar-ticker{{font-size:.7rem;color:var(--gold);margin-left:5px}}
    .radar-mcap{{font-size:.66rem;color:var(--green);margin-left:5px}}
    .radar-desc{{font-size:.76rem;color:var(--dim);margin-top:3px;line-height:1.45}}
    .radar-thesis{{font-size:.72rem;color:var(--blue);margin-top:3px;font-style:italic}}
    .freshness-badge{{display:inline-block;font-size:.55rem;padding:2px 6px;border-radius:2px;margin-left:6px;vertical-align:middle;font-weight:600;letter-spacing:.06em}}
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
    .feed-text{{font-size:.84rem;color:var(--text);line-height:1.5;word-break:break-word}}
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
      .allocation-section{{flex-direction:column}}
      .rec-grid{{grid-template-columns:1fr}}
      .portfolio-summary{{grid-template-columns:repeat(3,1fr)}}
    }}
  </style>
</head>
<body>
<div class="container">

  <!-- DATE STRIP (branding moved to footer) -->
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

  <!-- STAR SIGN — compact (~50% smaller) -->
  <div class="card">
    <div class="star-sign">
      <div class="star-sign-left">
        <div class="star-sign-symbol">{zodiac['symbol']}</div>
        <div class="star-sign-main">{zodiac['name']}</div>
        <div class="star-sign-range">{zodiac['range']}</div>
      </div>
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
    const CACHE_KEY = 'novaire_feed_v2';
    const CACHE_TTL = 15 * 60 * 1000;

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
              allPosts = data;
              renderFilter();
              renderFeed(activeFilter ? data.filter(p=>p.handle===activeFilter) : data);
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
        allPosts = json.posts;
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

  <!-- RADAR IDEAS — with freshness badges -->
  <div class="card">
    <div class="card-title">🎯 Radar Ideas</div>
    <div class="radar-category">🪙 Micro-Cap Crypto</div>
    <div class="radar-item">
      <span class="radar-icon">⚡</span>
      <div class="radar-content">
        <div>
          <span class="radar-name">Penumbra</span>
          <span class="radar-ticker">PENUMBRA</span>
          <span class="radar-mcap">~$85M mcap</span>
          <span class="freshness-badge stale">Added Jan 15</span>
        </div>
        <div class="radar-desc">Privacy-focused Cosmos chain with shielded swaps &amp; staking. Native DEX with anonymous positions.</div>
        <div class="radar-thesis">→ Privacy narrative + ZEC correlation + cross-chain DeFi = undervalued</div>
      </div>
    </div>
    <div class="radar-item">
      <span class="radar-icon">🔗</span>
      <div class="radar-content">
        <div>
          <span class="radar-name">Hyperlane</span>
          <span class="radar-ticker">Pre-token</span>
          <span class="radar-mcap">Watch list</span>
          <span class="freshness-badge stale">Added Jan 22</span>
        </div>
        <div class="radar-desc">Permissionless interoperability — any chain to any chain without centralized bridges.</div>
        <div class="radar-thesis">→ Bridge hacks create demand for trustless alternatives; token launch catalyst</div>
      </div>
    </div>
    <div class="radar-category">⛏️ Micro-Cap Resources</div>
    <div class="radar-item">
      <span class="radar-icon">☢️</span>
      <div class="radar-content">
        <div>
          <span class="radar-name">Forum Energy Metals</span>
          <span class="radar-ticker">FMC.V</span>
          <span class="radar-mcap">~$18M mcap</span>
          <span class="freshness-badge stale">Added Feb 3</span>
        </div>
        <div class="radar-desc">Athabasca Basin uranium explorer adjacent to Cameco &amp; Orano properties. Q1 drill results pending.</div>
        <div class="radar-thesis">→ Basin-maker geology + cheap entry = asymmetric upside on drill results</div>
      </div>
    </div>
    <div class="radar-item">
      <span class="radar-icon">🔋</span>
      <div class="radar-content">
        <div>
          <span class="radar-name">American Lithium Energy</span>
          <span class="radar-ticker">AMLI</span>
          <span class="radar-mcap">~$45M mcap</span>
          <span class="freshness-badge stale">Added Feb 10</span>
        </div>
        <div class="radar-desc">Nevada lithium clay project with solid-state battery tech partnership. Domestic supply play.</div>
        <div class="radar-thesis">→ Domestic lithium + IRA incentives + battery tech = strategic value</div>
      </div>
    </div>
    <div style="margin-top:10px;font-size:.62rem;color:var(--mute);text-align:center">
      🟢 Fresh = added within last 2 market days · Grey = older idea, still on watch
    </div>
  </div>

  <!-- RECOMMENDATIONS — client-side localStorage rotation -->
  <div class="card">
    <div class="card-title">🎬 Recommendations</div>
    <div class="rec-grid" id="rec-grid">
      <!-- Filled by JS dedup rotation -->
    </div>
    <div style="margin-top:12px;font-size:.68rem;color:var(--dim);text-align:center">
      Rotating daily · deduped via localStorage
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
    <div class="footer-tagline">Daily brief for focused allocators</div>
    <div class="footer-sub">novairesignal.com · Generated daily · Live data from Yahoo Finance &amp; Binance</div>
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

// ── Recommendations rotation ──
const MOVIES = {MOVIES_JS};
const BOOKS = {BOOKS_JS};

(function renderRecs() {{
  const movie = getQuoteForToday('movie', MOVIES);
  const book  = getQuoteForToday('book',  BOOKS);
  document.getElementById('rec-grid').innerHTML = `
    <div class="rec-item">
      <div class="rec-label">📺 Now Watching</div>
      <div class="rec-title">${{movie.title}}</div>
      <div class="rec-meta">${{movie.meta}}</div>
      <div class="rec-summary">${{movie.summary}}</div>
    </div>
    <div class="rec-item">
      <div class="rec-label">📖 Now Reading</div>
      <div class="rec-title">${{book.title}}</div>
      <div class="rec-meta">${{book.meta}}</div>
      <div class="rec-summary">${{book.summary}}</div>
    </div>
  `;
}})();
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

    print("  📈 Fetching portfolio data (yfinance)...")
    try:
        portfolio_data = fetch_portfolio()
        loaded = sum(1 for v in portfolio_data.values() if v.get("price"))
        print(f"    ✅ {loaded}/{len(HOLDINGS)} tickers loaded")
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

    print("  💱 Fetching FX rates...")
    try:
        fx = fetch_fx()
        print(f"    ✅ USD/CAD={fx['usdcad']:.4f}")
    except Exception as e:
        print(f"    ❌ {e}")
        fx = {"usdcad": 1.365}

    zodiac    = get_zodiac()
    doy       = day_of_year()
    thai_word = pick(THAI_WORDS, 5)
    motivation = pick(MOTIVATION_QUOTES, 11)

    print("  🎨 Generating HTML...")
    html = render_html(
        weather, bangkok_news, zh_news, portfolio_data, catalysts,
        commodities, crypto, fx, zodiac, thai_word, motivation
    )

    import os
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ HTML saved to {OUTPUT} ({len(html):,} bytes)")

if __name__ == "__main__":
    main()
