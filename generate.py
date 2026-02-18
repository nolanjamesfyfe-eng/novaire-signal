#!/usr/bin/env python3
"""
Novaire Signal — Daily Brief Generator
Generates index.html with Evolution Fund aesthetic + live data
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

HOLDINGS = {
    "HG.CN":  {"shares": 11000, "name": "Hydrograph"},
    "GLO.TO": {"shares": 22000, "name": "Global Atomic"},
    "FVL.V":  {"shares": 10000, "name": "FreeGold Ventures"},
    "MOLY.V": {"shares": 3950,  "name": "Moly Mines"},
    "DML.TO": {"shares": 1000,  "name": "Denison Mines"},
    "BNNLF":  {"shares": 1300,  "name": "Bannerman Energy"},
    "LOT.AX": {"shares": 11000, "name": "Lotus Resources"},
    "MAXX.V": {"shares": 2000,  "name": "Power Mining"},
    "PNPN.V": {"shares": 1000,  "name": "Power Nickel"},
    "NAM.V":  {"shares": 3000,  "name": "New Age Metals"},
    "PEGA.V": {"shares": 20000, "name": "Pegasus Resources"},
    "VZLA.V": {"shares": 100,   "name": "Vizsla Silver"},
    "CAPT.V": {"shares": 400,   "name": "Capitan Silver"},
    "AEU.V":  {"shares": 2027,  "name": "Atomic Eagle"},
    "BQSSF":  {"shares": 500,   "name": "Boss Energy"},
    "SVE.V":  {"shares": 1000,  "name": "Silver One"},
    "TOM.V":  {"shares": 3000,  "name": "Torchlight Energy"},
    "EU.V":   {"shares": 125,   "name": "Encore Energy"},
    "AAG.V":  {"shares": 438,   "name": "Aftermath Silver"},
}

SALARY_USD = 4500
BTC_INVEST_USD = 500

QUOTES = {
    "investing": [
        {"text": "The stock market is a device for transferring money from the impatient to the patient.", "author": "Warren Buffett"},
        {"text": "In the short run, the market is a voting machine. In the long run, it is a weighing machine.", "author": "Benjamin Graham"},
        {"text": "It's not whether you're right or wrong, but how much money you make when you're right and how much you lose when you're wrong.", "author": "George Soros"},
        {"text": "The four most dangerous words in investing are: 'this time it's different.'", "author": "Sir John Templeton"},
        {"text": "Price is what you pay. Value is what you get.", "author": "Warren Buffett"},
        {"text": "The individual investor should act consistently as an investor and not as a speculator.", "author": "Benjamin Graham"},
        {"text": "Know what you own, and know why you own it.", "author": "Peter Lynch"},
        {"text": "Risk comes from not knowing what you're doing.", "author": "Warren Buffett"},
        {"text": "Wide diversification is only required when investors do not understand what they are doing.", "author": "Warren Buffett"},
        {"text": "An investment in knowledge pays the best interest.", "author": "Benjamin Franklin"},
        {"text": "The most contrarian thing of all is not to oppose the crowd but to think for yourself.", "author": "Peter Thiel"},
        {"text": "Compound interest is the eighth wonder of the world.", "author": "Albert Einstein"},
    ],
    "philosophy": [
        {"text": "He who has a why to live can bear almost any how.", "author": "Friedrich Nietzsche"},
        {"text": "The impediment to action advances action. What stands in the way becomes the way.", "author": "Marcus Aurelius"},
        {"text": "Man is not worried by real problems so much as by his imagined anxieties about real problems.", "author": "Epictetus"},
        {"text": "The unexamined life is not worth living.", "author": "Socrates"},
        {"text": "We suffer more in imagination than in reality.", "author": "Seneca"},
        {"text": "One must imagine Sisyphus happy.", "author": "Albert Camus"},
        {"text": "To live is the rarest thing in the world. Most people exist, that is all.", "author": "Oscar Wilde"},
        {"text": "The measure of a man is what he does with power.", "author": "Plato"},
        {"text": "Waste no more time arguing about what a good man should be. Be one.", "author": "Marcus Aurelius"},
        {"text": "The secret of happiness is freedom, and the secret of freedom is courage.", "author": "Thucydides"},
        {"text": "He is a wise man who does not grieve for the things which he has not, but rejoices for those which he has.", "author": "Epictetus"},
        {"text": "The greatest wealth is to live content with little.", "author": "Plato"},
    ],
    "psychology": [
        {"text": "The cave you fear to enter holds the treasure you seek.", "author": "Joseph Campbell"},
        {"text": "Until you make the unconscious conscious, it will direct your life and you will call it fate.", "author": "Carl Jung"},
        {"text": "Between stimulus and response there is a space. In that space is our power to choose our response.", "author": "Viktor Frankl"},
        {"text": "The curious paradox is that when I accept myself just as I am, then I can change.", "author": "Carl Rogers"},
        {"text": "What we resist persists.", "author": "Carl Jung"},
        {"text": "The first step toward change is awareness. The second step is acceptance.", "author": "Nathaniel Branden"},
        {"text": "Comparison is the thief of joy.", "author": "Theodore Roosevelt"},
        {"text": "The greatest discovery of any generation is that human beings can alter their lives by altering their attitudes.", "author": "William James"},
        {"text": "You cannot swim for new horizons until you have courage to lose sight of the shore.", "author": "William Faulkner"},
        {"text": "Inaction breeds doubt and fear. Action breeds confidence and courage.", "author": "Dale Carnegie"},
        {"text": "It is not death that a man should fear, but he should fear never beginning to live.", "author": "Marcus Aurelius"},
        {"text": "Your task is not to seek for love, but merely to seek and find all the barriers within yourself that you have built against it.", "author": "Rumi"},
    ],
    "motivation": [
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
    ],
}

THAI_WORDS = [
    {"thai": "กำลอม (kam-lom)", "meaning": "speculate — taking calculated risks for potential gains"},
    {"thai": "สบาย (sa-baai)", "meaning": "comfortable, easy, relaxed — the Thai ideal of wellbeing"},
    {"thai": "เงิน (ngern)", "meaning": "money / silver — the same word covers both in Thai"},
    {"thai": "ใจเย็น (jai-yen)", "meaning": "cool heart — stay calm, don't panic"},
    {"thai": "ไม่เป็นไร (mai-pen-rai)", "meaning": "never mind, no worries — the Thai spirit of ease"},
    {"thai": "มีโอกาส (mee-o-gard)", "meaning": "there is an opportunity — seize the moment"},
    {"thai": "ขยัน (kha-yan)", "meaning": "hardworking, diligent — a virtue deeply respected"},
    {"thai": "อดทน (ot-ton)", "meaning": "patient, endure — the long-game mindset"},
    {"thai": "กล้าหาญ (gla-harn)", "meaning": "brave, courageous — bold in the face of uncertainty"},
    {"thai": "ความสำเร็จ (kwaam-sam-ret)", "meaning": "success, achievement — the destination"},
    {"thai": "ตลาด (ta-lard)", "meaning": "market — where opportunity and risk converge"},
    {"thai": "ทอง (tong)", "meaning": "gold — precious metal and lucky color in Thai culture"},
    {"thai": "ฝัน (fan)", "meaning": "dream — the vision that drives you forward"},
    {"thai": "ชีวิต (chee-wit)", "meaning": "life — make it count"},
    {"thai": "พอใจ (por-jai)", "meaning": "satisfied, content — knowing when enough is enough"},
    {"thai": "เป้าหมาย (pao-mai)", "meaning": "goal, target — what you're aiming at"},
    {"thai": "ความเสี่ยง (kwaam-siang)", "meaning": "risk — the price of opportunity"},
    {"thai": "กำไร (gam-rai)", "meaning": "profit, gain — the reward for good judgment"},
    {"thai": "สำเร็จ (sam-ret)", "meaning": "to succeed, accomplish — to reach the summit"},
    {"thai": "นักลงทุน (nak-long-tun)", "meaning": "investor — one who plants seeds for the future"},
    {"thai": "อนาคต (a-na-kot)", "meaning": "future — the horizon you're always moving toward"},
    {"thai": "เวลา (way-la)", "meaning": "time — the most precious and non-renewable resource"},
    {"thai": "ทำงาน (tham-ngan)", "meaning": "to work — the engine of all progress"},
    {"thai": "แข็งแกร่ง (kaeng-graeng)", "meaning": "strong, resilient — built for adversity"},
    {"thai": "เรียนรู้ (rian-roo)", "meaning": "to learn — the compounding asset of the mind"},
    {"thai": "ความจริง (kwaam-jing)", "meaning": "truth, reality — what matters in the long run"},
    {"thai": "ปัญญา (pan-ya)", "meaning": "wisdom — knowledge applied with discernment"},
    {"thai": "สมดุล (som-dun)", "meaning": "balance — the key to sustainable growth"},
    {"thai": "พัฒนา (pat-ta-na)", "meaning": "develop, progress — always moving forward"},
    {"thai": "เริ่มต้น (rerm-ton)", "meaning": "to begin, start — the hardest and most important step"},
]

ZODIAC_SIGNS = [
    (120, "Sagittarius", "♐", "Nov 22 – Dec 21", "Adventurous, optimistic, and philosophical — Sagittarians seek truth and freedom beyond the horizon."),
    (150, "Capricorn",   "♑", "Dec 22 – Jan 19", "Disciplined, ambitious, and patient — Capricorns build empires one brick at a time."),
    (180, "Aquarius",    "♒", "Jan 20 – Feb 18", "Innovative, independent, and humanitarian — Aquarians are forward-thinking visionaries."),
    (210, "Pisces",      "♓", "Feb 19 – Mar 20", "Intuitive, compassionate, and creative — Pisces feel the currents others cannot see."),
    (240, "Aries",       "♈", "Mar 21 – Apr 19", "Bold, energetic, and pioneering — Aries charge headfirst into new territory."),
    (270, "Taurus",      "♉", "Apr 20 – May 20", "Steadfast, practical, and patient — Taurus builds lasting value through consistency."),
    (300, "Gemini",      "♊", "May 21 – Jun 20", "Curious, adaptable, and communicative — Gemini see every angle of the picture."),
    (330, "Cancer",      "♋", "Jun 21 – Jul 22", "Intuitive, nurturing, and protective — Cancer builds fortresses of loyalty."),
    (360, "Leo",         "♌", "Jul 23 – Aug 22", "Charismatic, bold, and generous — Leo commands the room and inspires the crowd."),
    (30,  "Virgo",       "♍", "Aug 23 – Sep 22", "Analytical, precise, and dedicated — Virgo optimizes everything they touch."),
    (60,  "Libra",       "♎", "Sep 23 – Oct 22", "Balanced, diplomatic, and aesthetic — Libra seeks harmony in all things."),
    (90,  "Scorpio",     "♏", "Oct 23 – Nov 21", "Intense, perceptive, and transformative — Scorpio sees what others hide."),
]

WEATHER_CODES = {
    0: "Clear Sky ☀️", 1: "Mainly Clear 🌤", 2: "Partly Cloudy ⛅", 3: "Overcast ☁️",
    45: "Foggy 🌫", 48: "Icy Fog 🌫", 51: "Light Drizzle 🌦", 53: "Drizzle 🌦",
    55: "Heavy Drizzle 🌧", 61: "Slight Rain 🌧", 63: "Rain 🌧", 65: "Heavy Rain 🌧",
    71: "Slight Snow 🌨", 73: "Snow 🌨", 75: "Heavy Snow ❄️", 77: "Snow Grains 🌨",
    80: "Showers 🌦", 81: "Showers 🌦", 82: "Violent Showers ⛈", 85: "Slight Snow ❄️",
    86: "Heavy Snow ❄️", 95: "Thunderstorm ⛈", 96: "Thunderstorm ⛈", 99: "Thunderstorm ⛈",
}

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def day_of_year():
    now = datetime.now(timezone.utc)
    return now.timetuple().tm_yday

def pick(lst, offset=0):
    return lst[(day_of_year() + offset) % len(lst)]

def fmt_price(p, decimals=None):
    if p is None: return "N/A"
    if decimals is not None:
        return f"${p:,.{decimals}f}"
    if p >= 1000: return f"${p:,.0f}"
    if p >= 10: return f"${p:,.2f}"
    if p >= 0.01: return f"${p:.4f}"
    return f"${p:.6f}"

def fmt_pct(p):
    if p is None: return "—"
    color = "positive" if p >= 0 else "negative"
    sign = "+" if p >= 0 else ""
    return f'<span class="{color}">{sign}{p:.2f}%</span>'

def get_zodiac():
    now = datetime.now(timezone.utc)
    m, d = now.month, now.day
    cutoffs = [
        (1, 20, "Capricorn"),  (2, 19, "Aquarius"),   (3, 21, "Pisces"),
        (4, 20, "Aries"),      (5, 21, "Taurus"),      (6, 21, "Gemini"),
        (7, 23, "Cancer"),     (8, 23, "Leo"),          (9, 23, "Virgo"),
        (10,23, "Libra"),      (11,22, "Scorpio"),      (12,22, "Sagittarius"),
    ]
    info_map = {
        "Capricorn":   ("♑", "Dec 22 – Jan 19", "Disciplined, ambitious, and patient — Capricorns build empires one brick at a time."),
        "Aquarius":    ("♒", "Jan 20 – Feb 18", "Innovative, independent, and humanitarian — forward-thinking visionaries who value freedom."),
        "Pisces":      ("♓", "Feb 19 – Mar 20", "Intuitive, compassionate, and creative — Pisces feel the currents others cannot see."),
        "Aries":       ("♈", "Mar 21 – Apr 19", "Bold, energetic, and pioneering — Aries charge headfirst into new territory."),
        "Taurus":      ("♉", "Apr 20 – May 20", "Steadfast, practical, and patient — Taurus builds lasting value through consistency."),
        "Gemini":      ("♊", "May 21 – Jun 20", "Curious, adaptable, and communicative — Gemini see every angle of the picture."),
        "Cancer":      ("♋", "Jun 21 – Jul 22", "Intuitive, nurturing, and protective — Cancer builds fortresses of loyalty."),
        "Leo":         ("♌", "Jul 23 – Aug 22", "Charismatic, bold, and generous — Leo commands the room and inspires the crowd."),
        "Virgo":       ("♍", "Aug 23 – Sep 22", "Analytical, precise, and dedicated — Virgo optimizes everything they touch."),
        "Libra":       ("♎", "Sep 23 – Oct 22", "Balanced, diplomatic, and aesthetic — Libra seeks harmony in all things."),
        "Scorpio":     ("♏", "Oct 23 – Nov 21", "Intense, perceptive, and transformative — Scorpio sees what others hide."),
        "Sagittarius": ("♐", "Nov 22 – Dec 21", "Adventurous, optimistic, and philosophical — Sagittarians seek truth beyond the horizon."),
    }
    name = "Capricorn"
    for mo, day_cut, sign in cutoffs:
        if m == mo and d >= day_cut:
            name = sign
            break
        if m == mo and d < day_cut:
            # find previous
            pass
    # simpler approach
    def zodiac_name(m, d):
        if (m == 12 and d >= 22) or (m == 1 and d <= 19): return "Capricorn"
        if (m == 1 and d >= 20) or (m == 2 and d <= 18): return "Aquarius"
        if (m == 2 and d >= 19) or (m == 3 and d <= 20): return "Pisces"
        if (m == 3 and d >= 21) or (m == 4 and d <= 19): return "Aries"
        if (m == 4 and d >= 20) or (m == 5 and d <= 20): return "Taurus"
        if (m == 5 and d >= 21) or (m == 6 and d <= 20): return "Gemini"
        if (m == 6 and d >= 21) or (m == 7 and d <= 22): return "Cancer"
        if (m == 7 and d >= 23) or (m == 8 and d <= 22): return "Leo"
        if (m == 8 and d >= 23) or (m == 9 and d <= 22): return "Virgo"
        if (m == 9 and d >= 23) or (m == 10 and d <= 22): return "Libra"
        if (m == 10 and d >= 23) or (m == 11 and d <= 21): return "Scorpio"
        return "Sagittarius"
    name = zodiac_name(m, d)
    sym, rng, desc = info_map[name]
    return {"name": name, "symbol": sym, "range": rng, "desc": desc}

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
        headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
        r = requests.get("https://www.bangkokpost.com", headers=headers, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        # Try multiple selectors
        seen = set()
        for sel in ["h2.headline a", "h3.headline a", ".article-headline a",
                    ".col-md-8 h1 a", ".col-md-8 h2 a", ".col-md-8 h3 a",
                    "article h2 a", "article h3 a", ".story-title a"]:
            for el in soup.select(sel):
                txt = el.get_text(strip=True)
                if len(txt) > 20 and txt not in seen:
                    seen.add(txt)
                    href = el.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://www.bangkokpost.com" + href
                    headlines.append({"title": txt, "url": href})
                if len(headlines) >= 5:
                    break
            if len(headlines) >= 5:
                break
        if not headlines:
            # fallback: any anchor with substantial text in main content
            for a in soup.find_all("a", href=True):
                txt = a.get_text(strip=True)
                if len(txt) > 30 and txt not in seen:
                    href = a["href"]
                    if "bangkokpost.com" in href or href.startswith("/"):
                        if href.startswith("/"):
                            href = "https://www.bangkokpost.com" + href
                        seen.add(txt)
                        headlines.append({"title": txt, "url": href})
                if len(headlines) >= 5:
                    break
    except Exception as e:
        headlines = [{"title": f"Bangkok Post unavailable: {e}", "url": "#"}]
    return headlines[:5] if headlines else [{"title": "No headlines fetched", "url": "#"}]

def fetch_zerohedge():
    headlines = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get("https://www.zerohedge.com", headers=headers, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()
        # ZeroHedge article titles
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
                if len(headlines) >= 4:
                    break
            if len(headlines) >= 4:
                break
    except Exception as e:
        headlines = [{"title": f"ZeroHedge unavailable: {e}", "url": "#"}]
    return headlines[:4] if headlines else [{"title": "No headlines fetched", "url": "#"}]

def fetch_portfolio():
    try:
        import yfinance as yf
    except ImportError:
        return {t: {"price": None, "change": None, "value": None} for t in HOLDINGS}

    results = {}
    for ticker in HOLDINGS:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", auto_adjust=True)
            hist = hist[hist["Close"].notna()]
            if len(hist) >= 2:
                p  = float(hist["Close"].iloc[-1])
                pp = float(hist["Close"].iloc[-2])
                chg = (p - pp) / pp * 100
            elif len(hist) == 1:
                p = float(hist["Close"].iloc[-1])
                chg = None
            else:
                # fallback: try info fast_info
                fi = t.fast_info
                p = getattr(fi, "last_price", None)
                chg = None
            shares = HOLDINGS[ticker]["shares"]
            if p and p > 0:
                results[ticker] = {"price": p, "change": chg, "value": p * shares}
            else:
                results[ticker] = {"price": None, "change": None, "value": None}
        except Exception as e:
            results[ticker] = {"price": None, "change": None, "value": None}
    return results

def fetch_catalysts(top5_tickers):
    try:
        import yfinance as yf
    except ImportError:
        return {}
    cats = {}
    for ticker in top5_tickers:
        try:
            t = yf.Ticker(ticker)
            news = t.news
            if news:
                item = news[0]
                title = item.get("content", {}).get("title", item.get("title", "No title"))
                pub = item.get("content", {}).get("pubDate", "")
                if pub:
                    try:
                        dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                        pub = dt.strftime("%b %d")
                    except:
                        pass
                cats[ticker] = {"title": title, "date": pub}
            else:
                cats[ticker] = None
        except Exception as e:
            cats[ticker] = None
    return cats

def fetch_commodities():
    try:
        import yfinance as yf
    except ImportError:
        return {}

    symbols = {
        "GC=F":  {"name": "Gold",     "unit": "/oz",  "cls": "gold"},
        "SI=F":  {"name": "Silver",   "unit": "/oz",  "cls": "silver"},
        "HG=F":  {"name": "Copper",   "unit": "/lb",  "cls": "copper"},
        "CL=F":  {"name": "Oil (WTI)","unit": "/bbl", "cls": "oil"},
        "PA=F":  {"name": "Palladium","unit": "/oz",  "cls": "palladium"},
        "URA":   {"name": "Uranium",  "unit": "ETF",  "cls": "uranium"},
    }
    results = {}
    for sym, meta in symbols.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                p = float(hist["Close"].iloc[-1])
                pp = float(hist["Close"].iloc[-2])
                chg = (p - pp) / pp * 100
            elif len(hist) == 1:
                p = float(hist["Close"].iloc[-1])
                chg = None
            else:
                p = None; chg = None
            results[sym] = {**meta, "price": p, "change": chg}
        except Exception:
            results[sym] = {**meta, "price": None, "change": None}
    return results

def fetch_crypto():
    cryptos = ["BTC", "ETH", "SOL", "XRP", "ZEC"]
    # TON is not on Binance standard, try TONUSDT
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
            chg = float(data.get("priceChangePercent", 0))
            results[coin] = {"price": price, "change": chg}
        except Exception:
            results[coin] = {"price": None, "change": None}
    return results

def fetch_fx():
    try:
        import yfinance as yf
        usdcad = yf.Ticker("CADUSD=X").history(period="2d")
        if len(usdcad) >= 1:
            rate = float(usdcad["Close"].iloc[-1])
            usdcad_rate = 1.0 / rate if rate and rate != 0 else 1.365
        else:
            usdcad_rate = 1.365
    except:
        usdcad_rate = 1.365

    try:
        import yfinance as yf
        usdthb = yf.Ticker("THBUSD=X").history(period="2d")
        if len(usdthb) >= 1:
            rate = float(usdthb["Close"].iloc[-1])
            usdthb_rate = 1.0 / rate if rate and rate != 0 else 33.5
        else:
            usdthb_rate = 33.5
    except:
        usdthb_rate = 33.5

    return {"usdcad": usdcad_rate, "usdthb": usdthb_rate}

def days_to_payday():
    now = datetime.now(timezone.utc)
    if now.day == 1:
        return 0, now.strftime("%b 1")
    next_month = now.replace(day=1) + timedelta(days=32)
    payday = next_month.replace(day=1)
    days = (payday - now.replace(hour=0, minute=0, second=0, microsecond=0)).days
    return days, payday.strftime("%b 1, %Y")

# ─────────────────────────────────────────────────────────────
# SVG DONUT CHART
# ─────────────────────────────────────────────────────────────

def build_donut(allocations):
    """
    allocations: list of (label, pct, color)
    Returns SVG string of a donut chart
    """
    colors = ["#d4a843", "#6b8fd4", "#a07ed6", "#2a9d8f", "#e63946", "#f4a261", "#a8dadc", "#e9c46a", "#264653"]
    r = 25
    cx, cy = 50, 50
    circumference = 2 * math.pi * r
    total = sum(v for _, v, _ in allocations)
    if total == 0:
        return ""
    offset = 0
    slices = []
    for i, (label, val, _) in enumerate(allocations):
        pct = val / total
        dash = pct * circumference
        color = colors[i % len(colors)]
        slices.append(f'<circle r="{r}" cx="{cx}" cy="{cy}" fill="transparent" '
                      f'stroke="{color}" stroke-width="50" '
                      f'stroke-dasharray="{dash:.2f} {circumference:.2f}" '
                      f'stroke-dashoffset="{-offset:.2f}" '
                      f'transform="rotate(-90 {cx} {cy})"/>')
        offset += dash
    # inner circle to make donut
    slices.append(f'<circle r="15" cx="{cx}" cy="{cy}" fill="#09090b"/>')
    svg = (f'<svg class="pie-chart" viewBox="0 0 100 100" style="width:140px;height:140px">'
           + "".join(slices) + "</svg>")
    return svg

def build_legend(allocations, total_val):
    colors = ["#d4a843", "#6b8fd4", "#a07ed6", "#2a9d8f", "#e63946", "#f4a261", "#a8dadc", "#e9c46a", "#264653"]
    total = sum(v for _, v, _ in allocations)
    items = []
    for i, (label, val, _) in enumerate(allocations):
        pct = val / total * 100 if total else 0
        color = colors[i % len(colors)]
        items.append(f'<div class="legend-item"><span class="legend-dot" style="background:{color}"></span>'
                     f'{label}<span class="legend-pct">{pct:.1f}%</span></div>')
    return "\n".join(items)

# ─────────────────────────────────────────────────────────────
# SECTOR GROUPING
# ─────────────────────────────────────────────────────────────

SECTORS = {
    "HG.CN":  "Graphene",
    "GLO.TO": "Uranium",
    "FVL.V":  "Gold",
    "MOLY.V": "Molybdenum",
    "DML.TO": "Uranium",
    "BNNLF":  "Uranium",
    "LOT.AX": "Uranium",
    "MAXX.V": "Copper",
    "PNPN.V": "Nickel",
    "NAM.V":  "Metals",
    "PEGA.V": "Uranium",
    "VZLA.V": "Silver",
    "CAPT.V": "Silver",
    "AEU.V":  "Uranium",
    "BQSSF":  "Uranium",
    "SVE.V":  "Silver",
    "TOM.V":  "Metals",
    "EU.V":   "Uranium",
    "AAG.V":  "Silver",
}

# ─────────────────────────────────────────────────────────────
# HTML GENERATION
# ─────────────────────────────────────────────────────────────

def render_html(weather, bangkok_news, zh_news, portfolio_data, catalysts,
                commodities, crypto, fx, zodiac, quotes_sel, thai_word):
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %-d, %Y")
    gen_time = now.strftime("%H:%M UTC")

    # ── Portfolio calculations ──
    total_cad = 0
    total_usd = 0
    rows_html = ""
    sector_totals = {}

    # Sort by value descending
    port_sorted = []
    for ticker, info in HOLDINGS.items():
        pdata = portfolio_data.get(ticker, {})
        price = pdata.get("price")
        value = pdata.get("value")
        change = pdata.get("change")
        port_sorted.append((ticker, info, price, value, change))
    port_sorted.sort(key=lambda x: (x[3] or 0), reverse=True)

    for ticker, info, price, value, change in port_sorted:
        shares = info["shares"]
        name = info["name"]
        change_html = fmt_pct(change) if change is not None else '<span style="color:var(--dim)">—</span>'
        price_str = fmt_price(price, 2) if price and price >= 0.01 else (fmt_price(price, 4) if price else "—")
        value_str = f"${value:,.0f}" if value else "—"
        if value:
            total_usd += value
            sector = SECTORS.get(ticker, "Other")
            sector_totals[sector] = sector_totals.get(sector, 0) + value
        rows_html += f"""
        <tr>
          <td class="ticker">{ticker.split('.')[0]}</td>
          <td style="color:var(--dim);font-size:.85em">{name}</td>
          <td style="text-align:right">{shares:,}</td>
          <td style="text-align:right">{price_str}</td>
          <td style="text-align:right">{change_html}</td>
          <td style="text-align:right;font-weight:600">{value_str}</td>
        </tr>"""

    total_cad = total_usd * fx["usdcad"]

    # ── Allocation chart ──
    alloc_sorted = sorted(sector_totals.items(), key=lambda x: x[1], reverse=True)
    alloc_list = [(s, v, "") for s, v in alloc_sorted]
    donut_svg = build_donut(alloc_list)
    legend_html = build_legend(alloc_list, total_usd)

    # ── Top 5 tickers by value ──
    top5 = [t for t, *_ in port_sorted[:5]]

    # ── Catalysts HTML ──
    cats_html = ""
    for ticker in top5:
        cat = catalysts.get(ticker)
        if cat:
            cats_html += f"""
            <div class="catalyst-item">
              <span class="catalyst-ticker">{ticker.split('.')[0]}</span>
              <span class="catalyst-badge">{cat['date']}</span>
              <div style="font-size:.9em;color:var(--dim);margin-top:6px">{cat['title']}</div>
            </div>"""
        else:
            cats_html += f"""
            <div class="catalyst-item">
              <span class="catalyst-ticker">{ticker.split('.')[0]}</span>
              <span class="no-news">No recent news available</span>
            </div>"""

    # ── Weather HTML ──
    weather_html = ""
    for w in weather:
        temp_str = f"{w['temp']:.0f}°C" if w['temp'] is not None else "—"
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
        chg_html = fmt_pct(c["change"]) if c["change"] is not None else '<span style="color:var(--dim)">—</span>'
        comm_html += f"""
        <div class="commodity-item">
          <div class="commodity-name {c['cls']}">{c['name']}</div>
          <div class="commodity-price {c['cls']}">{price_str}</div>
          <div class="commodity-unit">{c['unit']}</div>
          <div class="commodity-change">{chg_html}</div>
        </div>"""

    # ── Crypto HTML ──
    crypto_colors = {"BTC": "#f7931a", "ETH": "#627eea", "SOL": "#9945ff",
                     "XRP": "#346aa9", "TON": "#0098ea", "ZEC": "#f4b728"}
    crypto_html = ""
    for coin in ["BTC", "ETH", "SOL", "XRP", "TON", "ZEC"]:
        c = crypto.get(coin, {})
        price = c.get("price")
        chg = c.get("change")
        price_str = fmt_price(price) if price else "—"
        chg_html = fmt_pct(chg) if chg is not None else '<span style="color:var(--dim)">—</span>'
        color = crypto_colors.get(coin, "#e0dde8")
        crypto_html += f"""
        <div class="crypto-item">
          <div class="crypto-symbol" style="color:{color}">{coin}</div>
          <div class="crypto-price" style="color:{color}">{price_str}</div>
          <div class="crypto-change">{chg_html}</div>
        </div>"""

    # ── FX / Salary HTML ──
    btc_price = crypto.get("BTC", {}).get("price")
    btc_amount = BTC_INVEST_USD / btc_price if btc_price else None
    btc_str = f"{btc_amount:.6f} BTC" if btc_amount else "—"
    btc_price_str = fmt_price(btc_price) if btc_price else "N/A"

    usdcad = fx["usdcad"]
    usdthb = fx["usdthb"]
    salary_cad = SALARY_USD * usdcad
    salary_thb = SALARY_USD * usdthb
    days_pay, payday_str = days_to_payday()

    # ── Quotes ──
    q_inv  = quotes_sel["investing"]
    q_phi  = quotes_sel["philosophy"]
    q_psy  = quotes_sel["psychology"]
    q_mot  = quotes_sel["motivation"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Novaire Signal — Daily Brief</title>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400;1,500&family=Instrument+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #09090b;
      --text: #e0dde8;
      --dim: #807d8e;
      --faint: #1e1c24;
      --gold: #d4a843;
      --gold-soft: rgba(212,168,67,.12);
      --blue: #6b8fd4;
      --blue-soft: rgba(107,143,212,.12);
      --violet: #a07ed6;
      --serif: 'Cormorant Garamond', Georgia, serif;
      --sans: 'Instrument Sans', -apple-system, sans-serif;
      --positive: #4caf80;
      --negative: #e05c5c;
    }}
    *{{margin:0;padding:0;box-sizing:border-box}}
    html{{scroll-behavior:smooth}}
    body{{font-family:var(--sans);background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:40px 20px}}
    .container{{max-width:760px;margin:0 auto}}

    /* HEADER */
    .header{{text-align:center;margin-bottom:48px;padding-bottom:32px;border-bottom:1px solid var(--faint)}}
    .header h1{{
      font-family:var(--serif);font-weight:300;font-size:clamp(2rem,6vw,3.2rem);
      letter-spacing:.04em;color:var(--text);margin-bottom:10px
    }}
    .header h1 span{{color:var(--gold);font-style:italic}}
    .header .date{{font-size:.75rem;letter-spacing:.18em;text-transform:uppercase;color:var(--dim)}}
    .header .gen{{font-size:.65rem;color:#3a3840;margin-top:4px}}

    /* CARDS */
    .card{{
      background:rgba(255,255,255,.02);border:1px solid var(--faint);
      padding:24px;margin-bottom:20px;
    }}
    .card-title{{
      font-size:.68rem;font-weight:600;letter-spacing:.22em;text-transform:uppercase;
      color:var(--gold);margin-bottom:18px;display:flex;align-items:center;gap:8px
    }}
    .card-title::after{{content:'';flex:1;height:1px;background:linear-gradient(90deg,var(--gold-soft),transparent)}}

    /* QUOTES */
    .quote{{margin-bottom:16px;padding-left:16px;border-left:2px solid var(--gold-soft)}}
    .quote:last-child{{margin-bottom:0}}
    .quote-type{{font-size:.62rem;color:var(--gold);text-transform:uppercase;letter-spacing:.14em;margin-bottom:4px;font-weight:600}}
    .quote-text{{font-family:var(--serif);font-size:1.05rem;font-style:italic;color:var(--text);line-height:1.6}}
    .quote-author{{font-size:.78rem;color:var(--dim);margin-top:4px}}

    /* WEATHER */
    .weather-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
    .weather-item{{text-align:center;padding:14px 8px;background:rgba(255,255,255,.02);border:1px solid var(--faint)}}
    .weather-item .city{{font-size:.72rem;color:var(--dim);margin-bottom:6px;letter-spacing:.06em}}
    .weather-item .temp{{font-size:1.3rem;font-weight:500;color:var(--gold);font-family:var(--serif)}}
    .weather-item .condition{{font-size:.68rem;color:var(--dim);margin-top:4px;line-height:1.4}}

    /* NEWS */
    .thai-news-compact{{margin-top:16px;padding:14px;background:rgba(212,168,67,.04);border:1px solid rgba(212,168,67,.12)}}
    .thai-news-header{{font-size:.62rem;color:var(--gold);text-transform:uppercase;letter-spacing:.14em;margin-bottom:10px;font-weight:600}}
    .thai-news-item{{font-size:.88rem;color:var(--text);padding:6px 0;border-bottom:1px solid var(--faint);line-height:1.5}}
    .thai-news-item:last-child{{border-bottom:none}}

    /* STAR SIGN */
    .star-sign{{text-align:center;padding:8px}}
    .star-sign-symbol{{font-size:2.5rem;margin-bottom:8px}}
    .star-sign-main{{font-family:var(--serif);font-size:1.5rem;color:var(--gold);margin-bottom:8px}}
    .star-sign-range{{font-size:.75rem;color:var(--dim);letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px}}
    .star-sign-desc{{font-size:.9rem;color:var(--dim);line-height:1.6;max-width:520px;margin:0 auto}}

    /* HEADLINES */
    .headline{{padding:10px 0;border-bottom:1px solid var(--faint)}}
    .headline:last-child{{border-bottom:none}}
    .headline-num{{
      display:inline-block;width:22px;height:22px;background:var(--gold-soft);
      color:var(--gold);border-radius:2px;text-align:center;line-height:22px;
      font-size:.72rem;font-weight:600;margin-right:10px
    }}
    .headline-text{{font-size:.92rem;color:var(--text)}}

    /* PORTFOLIO TABLE */
    .portfolio-table{{width:100%;border-collapse:collapse;font-size:.82rem}}
    .portfolio-table th{{
      text-align:left;padding:8px 6px;font-size:.62rem;font-weight:600;
      color:var(--dim);text-transform:uppercase;letter-spacing:.1em;
      border-bottom:1px solid var(--faint)
    }}
    .portfolio-table td{{padding:8px 6px;border-bottom:1px solid rgba(255,255,255,.03)}}
    .portfolio-table tr:hover{{background:rgba(255,255,255,.02)}}
    .ticker{{font-weight:600;color:var(--gold);font-size:.88rem}}
    .positive{{color:var(--positive)}}
    .negative{{color:var(--negative)}}

    .totals-row{{display:flex;justify-content:space-between;margin-top:20px;padding-top:16px;border-top:1px solid var(--faint)}}
    .total-item{{text-align:center}}
    .total-label{{font-size:.62rem;color:var(--dim);text-transform:uppercase;letter-spacing:.1em}}
    .total-value{{font-family:var(--serif);font-size:1.6rem;font-weight:400;margin-top:4px}}
    .total-value.cad{{color:var(--positive)}}
    .total-value.usd{{color:var(--gold)}}

    .allocation-section{{display:flex;align-items:center;gap:28px;margin-top:24px;padding-top:20px;border-top:1px solid var(--faint)}}
    .pie-chart{{flex-shrink:0}}
    .allocation-legend{{flex:1;display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
    .legend-item{{display:flex;align-items:center;gap:8px;font-size:.78rem}}
    .legend-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
    .legend-pct{{color:var(--dim);margin-left:auto}}

    /* CATALYSTS */
    .catalyst-item{{padding:12px 0;border-bottom:1px solid var(--faint)}}
    .catalyst-item:last-child{{border-bottom:none}}
    .catalyst-ticker{{font-weight:600;color:var(--gold);font-size:.9rem}}
    .catalyst-badge{{display:inline-block;background:var(--gold-soft);color:var(--gold);font-size:.65rem;padding:2px 8px;border-radius:2px;margin-left:8px}}
    .no-news{{color:var(--dim);font-style:italic;font-size:.82rem;margin-left:8px}}

    /* COMMODITIES */
    .commodities-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
    .commodity-item{{background:rgba(255,255,255,.02);padding:14px;border:1px solid var(--faint);text-align:center}}
    .commodity-name{{font-size:.68rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px;font-weight:600}}
    .commodity-price{{font-family:var(--serif);font-size:1.3rem;font-weight:400;margin-bottom:2px}}
    .commodity-unit{{font-size:.65rem;color:var(--dim)}}
    .commodity-change{{font-size:.78rem;margin-top:4px}}
    .gold{{color:#d4a843}}.silver{{color:#c0c0c0}}.copper{{color:#b87333}}
    .oil{{color:#8b7355}}.palladium{{color:#cec8c6}}.uranium{{color:#7fff00}}

    /* CRYPTO */
    .crypto-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
    .crypto-item{{background:rgba(255,255,255,.02);padding:14px;border:1px solid var(--faint);text-align:center}}
    .crypto-symbol{{font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.12em;margin-bottom:6px}}
    .crypto-price{{font-family:var(--serif);font-size:1.3rem;font-weight:400;margin-bottom:2px}}
    .crypto-change{{font-size:.78rem;margin-top:4px}}

    /* FX / SALARY */
    .btc-highlight{{
      background:linear-gradient(135deg,rgba(212,168,67,.08),rgba(212,168,67,.02));
      border:1px solid rgba(212,168,67,.2);padding:18px;text-align:center;margin-bottom:16px
    }}
    .btc-highlight .label{{font-size:.65rem;color:var(--dim);text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px}}
    .btc-row{{display:flex;align-items:baseline;justify-content:center;gap:12px}}
    .btc-row .usd{{font-family:var(--serif);font-size:1.4rem;color:var(--text)}}
    .btc-row .eq{{color:var(--dim)}}
    .btc-row .btc{{font-family:var(--serif);font-size:1.4rem;color:var(--gold)}}
    .btc-row .rate{{font-size:.75rem;color:var(--dim);margin-left:4px}}
    .fx-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
    .fx-item{{background:rgba(255,255,255,.02);padding:14px;border:1px solid var(--faint);text-align:center}}
    .fx-label{{font-size:.62rem;color:var(--dim);text-transform:uppercase;letter-spacing:.1em}}
    .fx-value{{font-family:var(--serif);font-size:1.3rem;color:var(--text);margin-top:4px}}
    .fx-sub{{font-size:.72rem;color:var(--dim);margin-top:2px}}
    .countdown-item{{border-color:rgba(107,143,212,.3);background:rgba(107,143,212,.04)}}
    .countdown-item .fx-value{{color:var(--blue)}}

    /* RADAR */
    .radar-category{{
      font-size:.65rem;font-weight:600;color:var(--gold);text-transform:uppercase;
      letter-spacing:.18em;margin:18px 0 10px;padding-bottom:6px;
      border-bottom:1px solid var(--gold-soft)
    }}
    .radar-category:first-child{{margin-top:0}}
    .radar-item{{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid var(--faint)}}
    .radar-item:last-child{{border-bottom:none}}
    .radar-icon{{font-size:.9rem;width:24px;text-align:center;padding-top:2px}}
    .radar-content{{flex:1}}
    .radar-name{{font-size:.9rem;font-weight:600;color:var(--text)}}
    .radar-ticker{{font-size:.75rem;color:var(--gold);margin-left:6px}}
    .radar-mcap{{font-size:.72rem;color:var(--positive);margin-left:6px}}
    .radar-desc{{font-size:.82rem;color:var(--dim);margin-top:4px;line-height:1.5}}
    .radar-thesis{{font-size:.78rem;color:var(--blue);margin-top:4px;font-style:italic}}

    /* RECOMMENDATIONS */
    .rec-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
    .rec-item{{background:rgba(255,255,255,.02);padding:18px;border:1px solid var(--faint)}}
    .rec-label{{font-size:.62rem;color:var(--gold);text-transform:uppercase;letter-spacing:.14em;margin-bottom:8px;font-weight:600}}
    .rec-title{{font-family:var(--serif);font-size:1.1rem;color:var(--text);margin-bottom:4px}}
    .rec-meta{{font-size:.72rem;color:var(--blue);margin-bottom:6px}}
    .rec-summary{{font-size:.82rem;color:var(--dim);line-height:1.5}}

    /* THAI WORD */
    .thai-word-box{{
      display:flex;align-items:center;justify-content:center;gap:16px;
      padding:14px;background:rgba(212,168,67,.04);border:1px solid rgba(212,168,67,.12)
    }}
    .thai-word-box .word{{font-family:var(--serif);font-size:1.15rem;color:var(--gold)}}
    .thai-word-box .dot{{color:var(--faint)}}
    .thai-word-box .meaning{{font-size:.85rem;color:var(--dim)}}

    /* X PLACEHOLDER */
    .x-placeholder{{text-align:center;padding:20px;color:var(--dim);font-size:.88rem}}
    .x-placeholder a{{color:var(--gold);text-decoration:none}}

    /* FOOTER */
    .footer{{text-align:center;padding:32px 0;border-top:1px solid var(--faint);margin-top:32px}}
    .footer span{{font-size:.68rem;color:var(--faint);letter-spacing:.06em}}
    .footer .logo{{font-family:var(--serif);font-size:1rem;letter-spacing:.22em;text-transform:uppercase;color:var(--dim);display:block;margin-bottom:6px}}

    /* RESPONSIVE */
    @media(max-width:600px){{
      .weather-grid{{grid-template-columns:repeat(2,1fr)}}
      .commodities-grid{{grid-template-columns:repeat(2,1fr)}}
      .crypto-grid{{grid-template-columns:repeat(2,1fr)}}
      .fx-grid{{grid-template-columns:repeat(2,1fr)}}
      .allocation-section{{flex-direction:column}}
      .rec-grid{{grid-template-columns:1fr}}
    }}
  </style>
</head>
<body>
<div class="container">

  <!-- HEADER -->
  <div class="header">
    <h1>Novaire <span>Signal</span></h1>
    <div class="date">{date_str}</div>
    <div class="gen">Generated {gen_time} · Live data</div>
  </div>

  <!-- QUOTES -->
  <div class="card">
    <div class="card-title">📜 Quotes</div>
    <div class="quote">
      <div class="quote-type">Investing</div>
      <div class="quote-text">"{q_inv['text']}"</div>
      <div class="quote-author">— {q_inv['author']}</div>
    </div>
    <div class="quote">
      <div class="quote-type">Philosophy</div>
      <div class="quote-text">"{q_phi['text']}"</div>
      <div class="quote-author">— {q_phi['author']}</div>
    </div>
    <div class="quote">
      <div class="quote-type">Psychology</div>
      <div class="quote-text">"{q_psy['text']}"</div>
      <div class="quote-author">— {q_psy['author']}</div>
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

  <!-- STAR SIGN -->
  <div class="card">
    <div class="star-sign">
      <div class="star-sign-symbol">{zodiac['symbol']}</div>
      <div class="star-sign-main">{zodiac['name']}</div>
      <div class="star-sign-range">{zodiac['range']}</div>
      <div class="star-sign-desc">{zodiac['desc']}</div>
    </div>
  </div>

  <!-- ZEROHEDGE -->
  <div class="card">
    <div class="card-title">📰 ZeroHedge — Top Headlines</div>
    {zh_html}
  </div>

  <!-- X / SOCIAL -->
  <div class="card">
    <div class="card-title">🐦 X / Social</div>
    <div class="x-placeholder">
      <p>Personalised feed from <strong>@nolanjamesfyfe</strong>'s following.</p>
      <p style="margin-top:8px;font-size:.78rem">
        <a href="https://twitter.com/login" target="_blank">Sign in to X to view personalised posts →</a>
      </p>
    </div>
  </div>

  <!-- PORTFOLIO -->
  <div class="card">
    <div class="card-title">📦 Portfolio</div>
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
        <div class="total-label">Total USD</div>
        <div class="total-value usd">${total_usd:,.0f}</div>
      </div>
      <div class="total-item">
        <div class="total-label">Total CAD</div>
        <div class="total-value cad">${total_cad:,.0f}</div>
      </div>
    </div>
    <div class="allocation-section">
      {donut_svg}
      <div class="allocation-legend">
        {legend_html}
      </div>
    </div>
  </div>

  <!-- CATALYSTS -->
  <div class="card">
    <div class="card-title">🔍 Catalysts — Top 5 Holdings</div>
    {cats_html}
  </div>

  <!-- COMMODITIES -->
  <div class="card">
    <div class="card-title">🪙 Commodities</div>
    <div class="commodities-grid">
      {comm_html}
    </div>
  </div>

  <!-- CRYPTO -->
  <div class="card">
    <div class="card-title">🌐 Crypto</div>
    <div class="crypto-grid">
      {crypto_html}
    </div>
  </div>

  <!-- SALARY & FX -->
  <div class="card">
    <div class="card-title">💰 Salary & FX</div>
    <div class="btc-highlight">
      <div class="label">BTC Conversion</div>
      <div class="btc-row">
        <span class="usd">${BTC_INVEST_USD} USD</span>
        <span class="eq">=</span>
        <span class="btc">{btc_str}</span>
        <span class="rate">@ {btc_price_str}</span>
      </div>
    </div>
    <div class="fx-grid">
      <div class="fx-item">
        <div class="fx-label">Monthly Salary</div>
        <div class="fx-value">${SALARY_USD:,}</div>
        <div class="fx-sub">USD/month</div>
      </div>
      <div class="fx-item">
        <div class="fx-label">In CAD</div>
        <div class="fx-value">${salary_cad:,.0f}</div>
        <div class="fx-sub">@ {usdcad:.4f}</div>
      </div>
      <div class="fx-item">
        <div class="fx-label">In THB</div>
        <div class="fx-value">฿{salary_thb:,.0f}</div>
        <div class="fx-sub">@ {usdthb:.1f}</div>
      </div>
      <div class="fx-item countdown-item">
        <div class="fx-label">Days to Payday</div>
        <div class="fx-value">{days_pay}</div>
        <div class="fx-sub">{payday_str}</div>
      </div>
    </div>
  </div>

  <!-- RADAR IDEAS -->
  <div class="card">
    <div class="card-title">🎯 Radar Ideas</div>
    <div class="radar-category">🪙 Micro-Cap Crypto</div>
    <div class="radar-item">
      <span class="radar-icon">⚡</span>
      <div class="radar-content">
        <div><span class="radar-name">Penumbra</span><span class="radar-ticker">PENUMBRA</span><span class="radar-mcap">~$85M mcap</span></div>
        <div class="radar-desc">Privacy-focused Cosmos chain with shielded swaps & staking. Native DEX with anonymous positions.</div>
        <div class="radar-thesis">→ Privacy narrative + ZEC correlation + cross-chain DeFi = undervalued</div>
      </div>
    </div>
    <div class="radar-item">
      <span class="radar-icon">🔗</span>
      <div class="radar-content">
        <div><span class="radar-name">Hyperlane</span><span class="radar-ticker">Pre-token</span><span class="radar-mcap">Watch list</span></div>
        <div class="radar-desc">Permissionless interoperability — any chain to any chain without centralized bridges.</div>
        <div class="radar-thesis">→ Bridge hacks create demand for trustless alternatives; token launch catalyst</div>
      </div>
    </div>
    <div class="radar-category">⛏️ Micro-Cap Resources</div>
    <div class="radar-item">
      <span class="radar-icon">☢️</span>
      <div class="radar-content">
        <div><span class="radar-name">Forum Energy Metals</span><span class="radar-ticker">FMC.V</span><span class="radar-mcap">~$18M mcap</span></div>
        <div class="radar-desc">Athabasca Basin uranium explorer adjacent to Cameco & Orano properties. Q1 drill results pending.</div>
        <div class="radar-thesis">→ Basin-maker geology + cheap entry = asymmetric upside on drill results</div>
      </div>
    </div>
    <div class="radar-item">
      <span class="radar-icon">🔋</span>
      <div class="radar-content">
        <div><span class="radar-name">American Lithium Energy</span><span class="radar-ticker">AMLI</span><span class="radar-mcap">~$45M mcap</span></div>
        <div class="radar-desc">Nevada lithium clay project with solid-state battery tech partnership. Domestic supply play.</div>
        <div class="radar-thesis">→ Domestic lithium + IRA incentives + battery tech = strategic value</div>
      </div>
    </div>
  </div>

  <!-- RECOMMENDATIONS -->
  <div class="card">
    <div class="card-title">🎬 Recommendations</div>
    <div class="rec-grid">
      <div class="rec-item">
        <div class="rec-label">📺 Now Watching</div>
        <div class="rec-title">The Rip</div>
        <div class="rec-meta">Netflix · Matt Damon, Ben Affleck</div>
        <div class="rec-summary">Miami cops discover millions in a stash house — trust frays as outside forces close in. Crime thriller from Joe Carnahan.</div>
      </div>
      <div class="rec-item">
        <div class="rec-label">📖 Now Reading</div>
        <div class="rec-title">The Psychology of Money</div>
        <div class="rec-meta">Morgan Housel · 2020 · Finance/Psychology</div>
        <div class="rec-summary">Timeless lessons on wealth, greed, and happiness. How behaviour — not intelligence — determines financial outcomes.</div>
      </div>
    </div>
    <div style="margin-top:14px;font-size:.75rem;color:var(--dim);text-align:center">
      Updated quarterly · Last update: Q2 2025
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
    <div class="quote" style="border-left-color:rgba(107,143,212,.4)">
      <div class="quote-type" style="color:var(--blue)">Kaizen Mindset</div>
      <div class="quote-text">"{q_mot['text']}"</div>
      <div class="quote-author">— {q_mot['author']}</div>
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    <span class="logo">Novaire Signal</span>
    <span>Daily brief for focused allocators · novairesignal.com</span>
  </div>

</div>
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
    for w in weather:
        status = "✅" if w["ok"] else "❌"
        print(f"    {status} {w['name']}: {w.get('temp')}°C {w.get('condition')}")

    print("  📰 Scraping Bangkok Post...")
    try:
        bangkok_news = fetch_bangkok_post()
        print(f"    ✅ {len(bangkok_news)} headlines")
    except Exception as e:
        print(f"    ❌ {e}")
        bangkok_news = [{"title": "Bangkok Post unavailable — check site manually", "url": "#"}]

    print("  📰 Scraping ZeroHedge...")
    try:
        zh_news = fetch_zerohedge()
        print(f"    ✅ {len(zh_news)} headlines")
    except Exception as e:
        print(f"    ❌ {e}")
        zh_news = [{"title": "ZeroHedge unavailable — check site manually", "url": "#"}]

    print("  📈 Fetching portfolio data (yfinance)...")
    try:
        portfolio_data = fetch_portfolio()
        loaded = sum(1 for v in portfolio_data.values() if v.get("price"))
        print(f"    ✅ {loaded}/{len(HOLDINGS)} tickers loaded")
    except Exception as e:
        print(f"    ❌ {e}")
        portfolio_data = {}

    print("  🔍 Fetching catalysts (yfinance news)...")
    # Top 5 by value
    sorted_holdings = sorted(
        HOLDINGS.keys(),
        key=lambda t: (portfolio_data.get(t, {}).get("value") or 0),
        reverse=True
    )
    top5 = sorted_holdings[:5]
    try:
        catalysts = fetch_catalysts(top5)
        print(f"    ✅ Catalysts for {', '.join(top5)}")
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
        print(f"    ✅ USD/CAD={fx['usdcad']:.4f}, USD/THB={fx['usdthb']:.2f}")
    except Exception as e:
        print(f"    ❌ {e}")
        fx = {"usdcad": 1.365, "usdthb": 33.5}

    # Static selectors
    zodiac = get_zodiac()
    doy = day_of_year()
    quotes_sel = {
        "investing":  pick(QUOTES["investing"], 0),
        "philosophy": pick(QUOTES["philosophy"], 7),
        "psychology": pick(QUOTES["psychology"], 3),
        "motivation": pick(QUOTES["motivation"], 11),
    }
    thai_word = pick(THAI_WORDS, 5)

    print("  🎨 Generating HTML...")
    html = render_html(
        weather, bangkok_news, zh_news, portfolio_data, catalysts,
        commodities, crypto, fx, zodiac, quotes_sel, thai_word
    )

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ HTML saved to {OUTPUT} ({len(html):,} bytes)")

if __name__ == "__main__":
    main()
