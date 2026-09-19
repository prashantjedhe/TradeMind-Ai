import uuid
from datetime import datetime
from sqlalchemy import String, Text, Numeric, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NewsArticle(Base):
    """
    Raw ingested headline (free RSS only: Google News RSS EN + HI).

    Dedupe: `url_hash` (sha256 of canonical URL) is unique, so the
    same syndicated story fetched from EN and HI feeds -- or on two
    consecutive 5-minute ingest runs -- inserts exactly once.
    `tickers` is the attribution list resolved at ingest time.
    """

    __tablename__ = "news_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(60), nullable=False, default="google-news-rss")
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    tickers: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, default=list)
    sector: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sentiment = relationship("NewsSentiment", back_populates="article", uselist=False,
                             cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<NewsArticle {self.language} {self.title[:40]!r} tickers={self.tickers}>"


class NewsSentiment(Base):
    """
    One scored row per (article, ticker). An article mentioning two
    tickers gets two rows, each scored in that ticker's context.
    `model_version` pins the scorer (e.g. "lexicon-bilingual-v1") so
    scores stay comparable and re-scoring is traceable.
    """

    __tablename__ = "news_sentiment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_articles.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)  # -1 .. +1
    magnitude: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0)  # 0 .. 1
    label: Mapped[str] = mapped_column(String(8), nullable=False, default="NEU")
    model_version: Mapped[str] = mapped_column(String(30), nullable=False, default="lexicon-bilingual-v1")
    spans: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # evidence phrases
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    article = relationship("NewsArticle", back_populates="sentiment")

    def __repr__(self) -> str:
        return f"<NewsSentiment {self.ticker} {self.label} {self.score}>"


class NewsSignal(Base):
    """
    Aggregated sentiment snapshot per (ticker, window) written every
    ingest cycle (5m). This is what the strategy evaluator reads --
    a regular time series, so `crosses_above/below` edge semantics
    work exactly like OHLCV indicators. Anti-lookahead: a signal row
    only ever aggregates articles with published_at <= its timestamp.
    """

    __tablename__ = "news_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    window_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False)
    zscore: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Impact-engine calibration history: signed ticker impact + band
    # for this bucket (see news_impact.py). Lets HIGH/MEDIUM be refit
    # by percentile from real data instead of guesswork.
    impact: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False, default=0)
    band: Mapped[str] = mapped_column(String(10), nullable=False, default="LOW")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<NewsSignal {self.ticker} {self.window_minutes}m {self.timestamp} score={self.score} n={self.article_count}>"
