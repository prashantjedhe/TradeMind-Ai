"""
News universe: per-ticker search aliases in English + Hindi.

Free-source strategy: Google News RSS needs no API key and supports
both `hl=en-IN` and `hl=hi-IN`, so every watchlist ticker gets EN and
HI aliases. The ingest worker builds one RSS query per alias per
language, then attributes each article to tickers by alias match
(fallback: query ticker that produced it).

Sectors reuse the Phase 6 News Intelligence sector-weight table
(BANK, IT, OIL, AUTO, FMCG, METAL, PHARMA, REALTY) plus INDEX.
"""

from __future__ import annotations

TICKER_META: dict[str, dict] = {
    "NIFTY": {
        "sector": "INDEX",
        "en": ["Nifty 50", "Nifty"],
        "hi": ["निफ्टी 50", "निफ्टी"],
    },
    "BANKNIFTY": {
        "sector": "INDEX",
        "en": ["Bank Nifty", "Nifty Bank"],
        "hi": ["बैंक निफ्टी", "बैंकनिफ्टी"],
    },
    "HDFCBANK": {
        "sector": "BANK",
        "en": ["HDFC Bank"],
        "hi": ["एचडीएफसी बैंक"],
    },
    "ICICIBANK": {
        "sector": "BANK",
        "en": ["ICICI Bank"],
        "hi": ["आईसीआईसीआई बैंक"],
    },
    "SBIN": {
        "sector": "BANK",
        "en": ["State Bank of India", "SBI"],
        "hi": ["स्टेट बैंक", "एसबीआई"],
    },
    "KOTAKBANK": {
        "sector": "BANK",
        "en": ["Kotak Mahindra Bank", "Kotak Bank"],
        "hi": ["कोटक बैंक"],
    },
    "TCS": {
        "sector": "IT",
        "en": ["Tata Consultancy Services", "TCS"],
        "hi": ["टीसीएस", "टाटा कंसल्टेंसी"],
    },
    "INFY": {
        "sector": "IT",
        "en": ["Infosys"],
        "hi": ["इंफोसिस"],
    },
    "WIPRO": {
        "sector": "IT",
        "en": ["Wipro"],
        "hi": ["विप्रो"],
    },
    "HCLTECH": {
        "sector": "IT",
        "en": ["HCL Technologies", "HCLTech"],
        "hi": ["एचसीएल टेक"],
    },
    "RELIANCE": {
        "sector": "OIL",
        "en": ["Reliance Industries", "RIL"],
        "hi": ["रिलायंस इंडस्ट्रीज", "रिलायंस"],
    },
    "ONGC": {
        "sector": "OIL",
        "en": ["Oil and Natural Gas Corporation", "ONGC"],
        "hi": ["ओएनजीसी"],
    },
    "MARUTI": {
        "sector": "AUTO",
        "en": ["Maruti Suzuki"],
        "hi": ["मारुति सुजुकी"],
    },
    "TMPV": {
        "sector": "AUTO",
        "en": ["Tata Motors"],
        "hi": ["टाटा मोटर्स"],
    },
    "HINDUNILVR": {
        "sector": "FMCG",
        "en": ["Hindustan Unilever", "HUL"],
        "hi": ["हिंदुस्तान यूनिलीवर"],
    },
    "ITC": {
        "sector": "FMCG",
        "en": ["ITC Limited", "ITC"],
        "hi": ["आईटीसी"],
    },
    "TATASTEEL": {
        "sector": "METAL",
        "en": ["Tata Steel"],
        "hi": ["टाटा स्टील"],
    },
    "JSWSTEEL": {
        "sector": "METAL",
        "en": ["JSW Steel"],
        "hi": ["जेएसडब्ल्यू स्टील"],
    },
    "SUNPHARMA": {
        "sector": "PHARMA",
        "en": ["Sun Pharmaceutical", "Sun Pharma"],
        "hi": ["सन फार्मा"],
    },
    "DLF": {
        "sector": "REALTY",
        "en": ["DLF Limited", "DLF"],
        "hi": ["डीएलएफ"],
    },
}

# Inverted index for attribution: alias (lowercased) -> ticker.
_ALIAS_TO_TICKER: dict[str, str] = {}
for _ticker, _meta in TICKER_META.items():
    _ALIAS_TO_TICKER[_ticker.lower()] = _ticker
    for _alias in _meta["en"] + _meta["hi"]:
        _ALIAS_TO_TICKER.setdefault(_alias.lower(), _ticker)


def tickers_for_text(text: str) -> list[str]:
    """Attribute free text to tickers by alias substring match."""
    lowered = text.lower()
    found: list[str] = []
    for alias, ticker in _ALIAS_TO_TICKER.items():
        if alias in lowered and ticker not in found:
            found.append(ticker)
    return found


def sector_of(ticker: str) -> str:
    return TICKER_META.get(ticker.strip().upper(), {}).get("sector", "UNKNOWN")
