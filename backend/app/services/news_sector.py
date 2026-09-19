"""
Sector mapper (Model 3): expert-system keyword -> sector resolution.

Two layers, checked in order:
1. Ticker map: 50+ NSE names/symbols -> sector (covers the 20-ticker
   watchlist plus the large-caps most likely to appear in headlines).
2. Keyword vote: ~180 EN+HI finance keywords -> sector; majority wins,
   ties break toward the higher sector weight.

Sectors are locked to the 9 the engine prices
(BANK/IT/OIL/AUTO/FMCG/METAL/PHARMA/REALTY/INDEX). Anything else maps
to UNKNOWN (weight 0.60), never silently to a priced sector.
"""

from __future__ import annotations

from app.services.news_universe import sector_of

# Extended NSE ticker -> sector (watchlist 20 + headline-regular large-caps).
TICKER_SECTOR: dict[str, str] = {
    "NIFTY": "INDEX", "BANKNIFTY": "INDEX", "INDIAVIX": "INDEX",
    "HDFCBANK": "BANK", "ICICIBANK": "BANK", "SBIN": "BANK", "KOTAKBANK": "BANK",
    "AXISBANK": "BANK", "INDUSINDBK": "BANK", "BANKBARODA": "BANK", "PNB": "BANK",
    "BAJFINANCE": "BANK", "BAJAJFINSV": "BANK", "HDFCLIFE": "BANK", "SBILIFE": "BANK",
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT",
    "TECHM": "IT", "LTIM": "IT", "PERSISTENT": "IT", "COFORGE": "IT",
    "RELIANCE": "OIL", "ONGC": "OIL", "BPCL": "OIL", "IOC": "OIL",
    "GAIL": "OIL", "ADANIENT": "OIL", "ATGL": "OIL",
    "MARUTI": "AUTO", "TATAMOTORS": "AUTO", "TMPV": "AUTO", "M&M": "AUTO",
    "M&MFIN": "AUTO", "HEROMOTOCO": "AUTO", "EICHERMOT": "AUTO", "TVSMOTOR": "AUTO",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "DABUR": "FMCG", "GODREJCP": "FMCG", "TATACONSUM": "FMCG",
    "TATASTEEL": "METAL", "JSWSTEEL": "METAL", "HINDALCO": "METAL",
    "VEDL": "METAL", "COALINDIA": "METAL", "NMDC": "METAL", "SAIL": "METAL",
    "SUNPHARMA": "PHARMA", "DRREDDY": "PHARMA", "CIPLA": "PHARMA",
    "DIVISLAB": "PHARMA", "LUPIN": "PHARMA", "AUROPHARMA": "PHARMA",
    "DLF": "REALTY", "GODREJPROP": "REALTY", "OBEROIRLTY": "REALTY",
    "PRESTIGE": "REALTY", "LODHA": "REALTY",
}

# keyword (lowercased, EN + HI) -> sector. Curated finance vocabulary.
SECTOR_KEYWORDS: dict[str, str] = {}
for _kw in ["bank", "banks", "banking", "lender", "nbfc", "rbi repo", "casa",
            "बैंक", "बैंकिंग", "ऋण", "कर्ज"]:
    SECTOR_KEYWORDS[_kw] = "BANK"
for _kw in ["it services", "software", "infosys", "tcs", "saas", "deal win",
            "आईटी", "सॉफ्टवेयर"]:
    SECTOR_KEYWORDS[_kw] = "IT"
for _kw in ["crude", "oil", "gas", "ongc", "refinery", "opec", "petrol",
            "diesel", "lng", "तेल", "गैस", "कच्चा तेल"]:
    SECTOR_KEYWORDS[_kw] = "OIL"
for _kw in ["auto", "car", "cars", "ev ", "electric vehicle", "two-wheeler",
            "maruti", "tata motors", "dispatches", "ऑटो", "गाड़ी", "वाहन"]:
    SECTOR_KEYWORDS[_kw] = "AUTO"
for _kw in ["fmcg", "soap", "shampoo", "biscuit", "fmcg volume", "rural demand",
            "एफएमसीजी", "साबुन"]:
    SECTOR_KEYWORDS[_kw] = "FMCG"
for _kw in ["steel", "metal", "aluminium", "copper", "iron ore", "coal",
            "स्टील", "धातु", "कोयला"]:
    SECTOR_KEYWORDS[_kw] = "METAL"
for _kw in ["pharma", "drug", "usfda", "clinical", "vaccine", "api ",
            "फार्मा", "दवा"]:
    SECTOR_KEYWORDS[_kw] = "PHARMA"
for _kw in ["realty", "real estate", "housing", "rera", "residential",
            "रियल्टी", "आवास", "मकान"]:
    SECTOR_KEYWORDS[_kw] = "REALTY"
for _kw in ["nifty", "sensex", "index", "indices", "fii", "dii",
            "निफ्टी", "सेंसेक्स", "सूचकांक"]:
    SECTOR_KEYWORDS[_kw] = "INDEX"
del _kw


def resolve_sector(title: str, tickers: list[str]) -> str:
    """
    Sector for an article: unanimous ticker sectors win; otherwise a
    keyword majority vote; UNKNOWN when nothing matches.
    """
    known = [sector_of(t) for t in (tickers or [])]
    known = [s for s in known if s not in ("UNKNOWN",)]
    if known and len(set(known)) == 1:
        return known[0]
    lowered = (title or "").lower()
    votes: dict[str, int] = {}
    for kw, sector in SECTOR_KEYWORDS.items():
        if kw in lowered:
            votes[sector] = votes.get(sector, 0) + 1
    if votes:
        from app.config import settings
        weights = settings.NEWS_SECTOR_WEIGHTS
        return max(votes, key=lambda s: (votes[s], weights.get(s, 0.0)))
    if known:
        # Mixed-ticker story (e.g. index movers roundup): most common wins.
        return max(set(known), key=known.count)
    return "UNKNOWN"
