"""
Free news ingest: Google News RSS (no API key) in English + Hindi.

Per watchlist ticker we fetch two feeds — one EN (`hl=en-IN`) and one
HI (`hl=hi-IN`) — built from the first EN/HI alias in news_universe.
40 small RSS fetches per 5-minute cycle, stdlib only (urllib +
ElementTree), each bounded by timeout + item cap, failures isolated
per feed so one bad response never aborts the cycle.

Attribution: an article is tagged with tickers matched in its title
(news_universe.tickers_for_text) union the query ticker that found
it. Language comes from the feed, not guessing.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.news import NewsArticle, NewsSentiment
from app.services.news_keywords import extract_keywords, finance_tags
from app.services.news_sector import resolve_sector
from app.services.news_sentiment import reset_finbert_budget, score_article_hybrid
from app.services.news_universe import TICKER_META, tickers_for_text

logger = logging.getLogger(__name__)

_GN_BASE = "https://news.google.com/rss/search"


def _feed_url(query: str, lang: str) -> str:
    if lang == "hi":
        return f"{_GN_BASE}?q={quote(query)}&hl=hi-IN&gl=IN&ceid=IN:hi"
    return f"{_GN_BASE}?q={quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"


def build_queries(ticker: str) -> list[tuple[str, str]]:
    """(language, query) pairs for one ticker. Bounded: 1 EN + 1 HI."""
    meta = TICKER_META.get(ticker.strip().upper())
    if not meta:
        return [("en", f"{ticker} stock market")]
    queries: list[tuple[str, str]] = []
    if meta["en"]:
        queries.append(("en", f"{meta['en'][0]} stock market"))
    if meta["hi"]:
        queries.append(("hi", f"{meta['hi'][0]} शेयर बाजार"))
    return queries


def _fetch_feed(url: str) -> list[dict]:
    """Blocking RSS fetch+parse. Runs in a thread; never raises."""
    try:
        req = Request(url, headers={"User-Agent": settings.NEWS_USER_AGENT})
        with urlopen(req, timeout=10) as resp:
            data = resp.read(2_000_000)  # 2MB cap per feed
        root = ET.fromstring(data)
        items: list[dict] = []
        for item in list(root.iter("item"))[: settings.NEWS_MAX_ITEMS_PER_FEED]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            source_el = item.find("source")
            source = (source_el.text or "").strip() if source_el is not None else ""
            if not title or not link:
                continue
            try:
                published = parsedate_to_datetime(pub)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                published = datetime.now(timezone.utc)
            items.append({"title": title, "link": link,
                          "published_at": published, "source": source})
        return items
    except Exception as exc:
        logger.warning("RSS fetch failed %s: %s", url[:80], exc)
        return []


def _canonical_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8", "ignore")).hexdigest()


async def ingest_cycle(db: AsyncSession, tickers: list[str] | None = None) -> dict:
    """
    One full ingest+score pass. Returns stats. All network I/O runs in
    threads; DB writes are bulk upserts. Idempotent (dedupe by url_hash).
    """
    tickers = tickers or settings.WATCHLIST_TICKERS
    now = datetime.now(timezone.utc)

    # 1. Fetch every feed (bounded, failures isolated per feed).
    jobs: list[tuple[str, str, str]] = []  # (ticker, lang, url)
    for ticker in tickers:
        for lang, query in build_queries(ticker):
            jobs.append((ticker, lang, _feed_url(query, lang)))

    fetched = 0
    candidates: list[dict] = []
    for ticker, lang, url in jobs:
        items = await asyncio.to_thread(_fetch_feed, url)
        fetched += len(items)
        for it in items:
            # Drop future-dated items (anti-lookahead hygiene).
            if it["published_at"] > now + timedelta(minutes=15):
                continue
            attributed = tickers_for_text(it["title"]) or [ticker.strip().upper()]
            if ticker.strip().upper() not in attributed:
                attributed.append(ticker.strip().upper())
            candidates.append({
                "ticker_query": ticker.strip().upper(),
                "language": lang,
                "title": it["title"][:500],
                "url": it["link"][:2000],
                "url_hash": _canonical_hash(it["link"]),
                "published_at": it["published_at"],
                "tickers": sorted(set(attributed)),
                # Sector resolution: keyword vote, unanimous tickers win,
                # UNKNOWN when nothing matches (never a silent guess).
                "sector": resolve_sector(it["title"], attributed),
                "source": f"google-news-rss:{lang}" + (f":{it['source']}" if it["source"] else ""),
            })

    # 2. Bulk insert new articles only.
    inserted_ids: dict[str, str] = {}  # url_hash -> article id
    if candidates:
        stmt = pg_insert(NewsArticle).values([{
            "source": c["source"], "url": c["url"], "url_hash": c["url_hash"],
            "title": c["title"], "body": "", "language": c["language"],
            "published_at": c["published_at"], "tickers": c["tickers"],
            "sector": c["sector"],
        } for c in candidates])
        stmt = stmt.on_conflict_do_nothing(constraint="uq_news_articles_url_hash")
        stmt = stmt.returning(NewsArticle.id, NewsArticle.url_hash)
        result = await db.execute(stmt)
        await db.commit()
        for row in result.all():
            inserted_ids[row[1]] = row[0]

    # 3. Score newly inserted articles (hybrid: FinBERT EN, lexicon HI).
    scored = 0
    reset_finbert_budget()
    if inserted_ids:
        by_hash = {c["url_hash"]: c for c in candidates}
        sent_rows: list[dict] = []
        for url_hash, article_id in inserted_ids.items():
            c = by_hash.get(url_hash)
            if not c:
                continue
            s = score_article_hybrid(c["title"], "")
            keywords = extract_keywords(c["title"], s.get("language", "en"))
            for t in c["tickers"]:
                sent_rows.append({
                    "article_id": article_id, "ticker": t,
                    "score": s["score"], "magnitude": s["magnitude"],
                    "label": s["label"], "model_version": s.get("model", "lexicon-bilingual-v1"),
                    "spans": {"hits": s["spans"], "language": s["language"],
                              "keywords": keywords,
                              "tags": finance_tags(c["title"])},
                })
        if sent_rows:
            stmt = pg_insert(NewsSentiment).values(sent_rows)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_news_sentiment_article")
            await db.execute(stmt)
            await db.commit()
            scored = len(sent_rows)

    stats = {"fetched": fetched, "candidates": len(candidates),
             "articles_inserted": len(inserted_ids), "sentiment_rows": scored}
    logger.info("News ingest complete: %s", stats)
    return stats
