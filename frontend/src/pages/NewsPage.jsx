import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getWatchlist } from '../api/marketApi'
import {
  getLatestNews,
  getNewsAlerts,
  getNewsEvaluation,
  getNewsSignal,
  postAdvisor,
} from '../api/newsApi'
import { getStrategies } from '../api/strategyApi'
import PageLayout from '../components/common/PageLayout'
import StatCard from '../components/common/StatCard'

const REGIME_TONE = {
  bullish: 'chip-bull',
  'spike-bullish': 'chip-bull',
  bearish: 'chip-bear',
  'spike-bearish': 'chip-bear',
  neutral: 'chip-neutral',
  quiet: 'chip-neutral',
}

const BAND_TONE = {
  HIGH: 'chip-bear',
  MEDIUM: 'chip-gold',
  LOW: 'chip-neutral',
}

const POPULAR_TICKERS = [
  { symbol: 'NIFTY', label: 'NIFTY 50' },
  { symbol: 'BANKNIFTY', label: 'BANK NIFTY' },
  { symbol: 'HDFCBANK', label: 'HDFC BANK' },
  { symbol: 'RELIANCE', label: 'RELIANCE' },
  { symbol: 'TCS', label: 'TCS' },
  { symbol: 'TATASTEEL', label: 'TATA STEEL' },
  { symbol: 'TMPV', label: 'TATA MOTORS' },
]

function ScoreChip({ score }) {
  const n = Number(score)
  if (isNaN(n)) return <span className="chip chip-neutral">—</span>
  const tone = n > 0.15 ? 'chip-bull' : n < -0.15 ? 'chip-bear' : 'chip-neutral'
  const sign = n > 0 ? '+' : ''
  return <span className={`chip ${tone}`}>{`${sign}${n.toFixed(2)}`}</span>
}

function ImpactChip({ impact, band }) {
  const n = Number(impact)
  if (isNaN(n)) return <span className="chip chip-neutral">—</span>
  const sign = n > 0 ? '+' : ''
  return (
    <span className="flex items-center gap-1.5">
      <span className={`chip ${BAND_TONE[band] || 'chip-neutral'}`}>{band || 'LOW'}</span>
      <span className="font-mono text-xs text-slate-300">{`${sign}${n.toFixed(3)}`}</span>
    </span>
  )
}

function NewsPage() {
  const navigate = useNavigate()
  const [watchlist, setWatchlist] = useState([])
  const [ticker, setTicker] = useState('ALL')
  const [signal, setSignal] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [articles, setArticles] = useState([])
  const [selectedArticle, setSelectedArticle] = useState(null)
  const [evaluation, setEvaluation] = useState(null)
  const [evaluationError, setEvaluationError] = useState(null)
  const [evaluationLoading, setEvaluationLoading] = useState(false)
  const [strategies, setStrategies] = useState([])
  const [advisorOut, setAdvisorOut] = useState(null)
  const [advisorStrategy, setAdvisorStrategy] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)

  const loadNews = useCallback(async (t) => {
    if (!t) return
    setRefreshing(true)
    setError(null)
    setEvaluation(null)
    setEvaluationError(null)
    setEvaluationLoading(true)
    try {
      const [sigRes, alertsRes, latestRes] = await Promise.all([
        getNewsSignal(t),
        getNewsAlerts(),
        getLatestNews(t, 10),
      ])
      const latestArticles = latestRes.data.articles || []
      setSignal(sigRes.data)
      setAlerts(alertsRes.data.alerts || [])
      setArticles(latestArticles)
      setSelectedArticle((current) => {
        if (current && latestArticles.some((a) => a.url === current.url)) return current
        return latestArticles[0] || null
      })
      try {
        const evaluationRes = await getNewsEvaluation(t === 'ALL' ? null : t, 30)
        setEvaluation(evaluationRes.data)
        setEvaluationError(null)
      } catch {
        setEvaluation(null)
        setEvaluationError('Outcome evaluation is temporarily unavailable.')
      } finally {
        setEvaluationLoading(false)
      }
      if (!latestArticles.length && (!sigRes.data || !sigRes.data.windows || sigRes.data.windows.length === 0)) {
        setError('No recent news available right now. Try refreshing later.')
      }
    } catch {
      setSignal(null)
      setAlerts([])
      setArticles([])
      setSelectedArticle(null)
      setEvaluation(null)
      setEvaluationError('Outcome evaluation is temporarily unavailable.')
      setEvaluationLoading(false)
      setError('Unable to fetch news right now. Please try again later.')
    } finally {
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    const init = async () => {
      try {
        const [wlRes, stratRes] = await Promise.all([getWatchlist(), getStrategies()])
        const tickers = wlRes.data.tickers || []
        setWatchlist(tickers)
        setStrategies(stratRes.data || [])
        setTicker('ALL')
      } catch {
        navigate('/login')
      } finally {
        setLoading(false)
      }
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!ticker) return
    loadNews(ticker)
    const id = setInterval(() => loadNews(ticker), 60000)
    return () => clearInterval(id)
  }, [ticker, loadNews])

  const handleAdvisor = async () => {
    setBusy('advisor')
    setAdvisorOut(null)
    try {
      const res = await postAdvisor(
        advisorStrategy || null,
        '',
        ticker === 'ALL' ? selectedArticle?.tickers?.[0] || null : ticker,
        selectedArticle?.title || null,
        selectedArticle?.sector || null,
        selectedArticle?.score ?? null,
        selectedArticle?.label || null,
        selectedArticle?.url || null,
      )
      setAdvisorOut(res.data)
    } catch {
      setAdvisorOut({ ok: false, body: 'News advisor request failed. Please retry.' })
    } finally {
      setBusy(null)
    }
  }

  const windows = signal?.windows || []
  const counts = signal?.last_24h_counts || { POS: 0, NEG: 0, NEU: 0 }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#05070f] text-white">
        <div className="mx-auto h-12 w-12 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
      </div>
    )
  }

  return (
    <PageLayout>
      <div className="animate-rise space-y-6">
        <div>
          <p className="chip chip-violet mb-2">FinBERT EN + Lexicon HI • Free RSS • 5-min refresh</p>
          <h1 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
            News <span className="text-gradient-cyan">Intelligence</span>
          </h1>
          <p className="mt-2 max-w-xl text-sm text-slate-400">
            Impact = signed polarity × sector relevance × publisher prior × freshness.
            It explains headline relevance; it is not a price prediction. Strategy safeguards
            may react to HIGH impact, but news never places forecast-driven orders.
          </p>
        </div>

        <div className="glass card-3d rounded-2xl p-5">
          <div className="card-glow" />
          <div className="grid gap-5 lg:grid-cols-2 lg:items-end">
            <div>
              <label htmlFor="news-ticker" className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Choose market or ticker
              </label>
              <select
                id="news-ticker"
                value={ticker}
                onChange={(event) => setTicker(event.target.value)}
                className="input-3d"
              >
                <option value="ALL">All Indian markets · all sectors</option>
                {watchlist.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Popular tickers
              </p>
              <div className="flex flex-wrap gap-2">
                {POPULAR_TICKERS.filter(({ symbol }) => watchlist.includes(symbol)).map(({ symbol, label }) => (
                  <button
                    key={symbol}
                    type="button"
                    onClick={() => setTicker(symbol)}
                    aria-pressed={ticker === symbol}
                    className={`rounded-lg border px-2.5 py-2 text-[11px] font-semibold transition-colors ${
                      ticker === symbol
                        ? 'border-[#4b85c5] bg-[#1a2a3b] text-white'
                        : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-white'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Strategy Advisor (advisory-only) */}
        <div className="glass glow-violet card-3d rounded-2xl p-6">
          <div className="card-glow" />
          <h2 className="font-display text-lg font-semibold text-white">Strategy Advisor</h2>
          <p className="mt-1 text-xs text-slate-500">
            Claude reviews a strategy + recent paper trades. Advice only — it can never place,
            pause, or modify anything.
          </p>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <select
              value={advisorStrategy}
              onChange={(e) => setAdvisorStrategy(e.target.value)}
              className="input-3d flex-1"
            >
              <option value="">Overall account (no single strategy)</option>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.ticker} • {s.status})
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleAdvisor}
              disabled={busy === 'advisor'}
              className="btn-primary rounded-xl px-5 py-2.5 text-sm disabled:opacity-50"
            >
              {busy === 'advisor' ? 'Consulting…' : '✦ Ask Advisor'}
            </button>
          </div>
          {advisorOut && (
            <div className="mt-4 whitespace-pre-line rounded-xl bg-black/30 p-4 text-sm leading-relaxed text-slate-300">
              {advisorOut.body}
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            {error}
          </div>
        )}

        {/* Impact bands per window */}
        <div className="grid gap-4 sm:grid-cols-4">
          {windows.map((w) => {
            const s = w.signal
            return (
              <div key={w.window_minutes} className="glass card-3d rounded-2xl p-4">
                <div className="card-glow" />
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {w.window} impact
                </p>
                <div className="mt-2">
                  {s ? (
                    <ImpactChip impact={s.impact} band={s.band || w.band} />
                  ) : (
                    <span className="chip chip-neutral">no signal</span>
                  )}
                </div>
                <p className="mt-2 text-[11px] text-slate-500">
                  {s ? `${s.article_count ?? 0} articles • score ${Number(s.score ?? 0).toFixed(2)}` : 'ingest pending'}
                </p>
                {w.regime && (
                  <span className={`chip mt-2 ${REGIME_TONE[w.regime] || 'chip-neutral'}`}>
                    {w.regime}
                  </span>
                )}
              </div>
            )
          })}
          <StatCard
            label="24h headlines"
            value={`${counts.POS + counts.NEG + counts.NEU}`}
            icon="📰"
            tone="violet"
            className="card-3d"
          />
        </div>

        {/* Alerts */}
        {alerts.length > 0 && (
          <div className="glass rounded-2xl border-amber-500/20 p-6">
            <h2 className="mb-3 font-display text-lg font-semibold text-white">
              ⚠ Impact alerts
            </h2>
            <div className="space-y-2">
              {alerts.slice(0, 8).map((a, i) => (
                <div
                  key={i}
                  className="flex flex-col gap-1 rounded-xl border border-white/8 bg-white/[0.03] p-3 text-sm sm:flex-row sm:items-center sm:justify-between"
                >
                  <p className="truncate text-slate-200">
                    <span className="mr-2 font-mono text-cyan-300">{a.ticker}</span>
                    {a.headline || `${a.band} impact ${a.impact}`}
                  </p>
                  <span className={`chip ${BAND_TONE[a.band] || 'chip-neutral'}`}>
                    {a.band}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="glass rounded-2xl p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-lg font-semibold text-white">
              Latest headlines <span className="text-slate-500">• {ticker === 'ALL' ? 'All Indian markets' : ticker}</span>
            </h2>
            <button
              type="button"
              onClick={() => loadNews(ticker)}
              disabled={refreshing}
              className="btn-ghost rounded-lg px-3.5 py-2 text-xs font-semibold disabled:opacity-50"
            >
              {refreshing ? 'Refreshing…' : '↻ Refresh News'}
            </button>
          </div>
          {articles.length === 0 ? (
            <div className="flex h-40 flex-col items-center justify-center text-center">
              <span className="mb-2 text-3xl">📭</span>
              <p className="text-sm text-slate-500">
                No recent news available right now. Try refreshing or check again later.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                {articles.length} Headlines · scored news and estimated impact
                </p>
                {articles.map((article, i) => (
                  <button
                    key={`${article.url}-${i}`}
                    type="button"
                    onClick={() => setSelectedArticle(article)}
                    className={`block w-full rounded-xl border p-4 text-left transition ${
                      selectedArticle?.url === article.url
                        ? 'border-cyan-400/50 bg-cyan-500/10'
                        : 'border-white/8 bg-white/[0.03] hover:border-cyan-400/30 hover:bg-white/[0.05]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-white">{article.title}</p>
                        <p className="mt-1 text-[11px] text-slate-500">
                          {article.source || 'Unknown source'}
                          {article.sector ? ` • ${article.sector}` : ''}
                          {article.tickers?.length ? ` • ${article.tickers.join(', ')}` : ''}
                          {article.published_at
                            ? ` • ${new Date(article.published_at).toLocaleString('en-IN', {
                                day: '2-digit',
                                month: 'short',
                                hour: '2-digit',
                                minute: '2-digit',
                              })}`
                            : ''}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-2">
                        <ScoreChip score={article.score} />
                        <ImpactChip impact={article.impact_score} band={article.impact_band} />
                      </div>
                    </div>
                  </button>
                ))}
              </div>

              <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
                {selectedArticle ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="chip chip-violet">{selectedArticle.label || 'NEU'}</span>
                      <ScoreChip score={selectedArticle.score} />
                    </div>
                    <h3 className="text-lg font-semibold text-white">{selectedArticle.title}</h3>
                    <div className="space-y-2 text-sm text-slate-300">
                      <p><span className="text-slate-500">Source:</span> {selectedArticle.source || 'Unknown'}</p>
                      <p><span className="text-slate-500">Published:</span> {selectedArticle.published_at ? new Date(selectedArticle.published_at).toLocaleString('en-IN') : 'N/A'}</p>
                      <p><span className="text-slate-500">Symbol:</span> {ticker}</p>
                      <p><span className="text-slate-500">Sector:</span> {selectedArticle.sector || 'UNKNOWN'}</p>
                      <p><span className="text-slate-500">Sentiment:</span> {selectedArticle.label || 'NEU'} ({Number(selectedArticle.score ?? 0).toFixed(2)})</p>
                      <p><span className="text-slate-500">Headline impact:</span> {Number(selectedArticle.impact_score ?? 0).toFixed(3)}</p>
                      {selectedArticle.impact_factors && (
                        <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3 text-xs">
                          <p className="font-semibold text-slate-200">Why this impact</p>
                          <p className="mt-1 leading-relaxed text-slate-400">{selectedArticle.impact_rationale}</p>
                          <p className="mt-2 text-slate-500">
                            Factors: sector {Number(selectedArticle.impact_factors.sector_weight).toFixed(2)}
                            {' · '}publisher {Number(selectedArticle.impact_factors.source_weight).toFixed(2)}
                            {' · '}freshness {Number(selectedArticle.impact_factors.recency_factor).toFixed(2)}
                          </p>
                        </div>
                      )}
                      <p><span className="text-slate-500">Event tags:</span> {selectedArticle.event_tags?.length ? selectedArticle.event_tags.join(', ') : 'No recognized event tag'}</p>
                      <p><span className="text-slate-500">Keywords:</span> {selectedArticle.keywords?.length ? selectedArticle.keywords.join(', ') : 'Not available'}</p>
                    </div>
                    {selectedArticle.url && (
                      <a
                        href={selectedArticle.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-xs font-semibold text-cyan-200"
                      >
                        Open original source
                      </a>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">Select a headline to inspect the full article details.</p>
                )}
              </div>
            </div>
          )}
          <p className="mt-4 text-[11px] leading-relaxed text-slate-600">
            EN uses FinBERT, Hindi uses the finance lexicon. Sentiment is not a probability of price movement;
            impact is signed sentiment attenuated by sector relevance, publisher credibility, and freshness.
            Event tags and keywords are evidence hints, not verified catalysts. Automated actions require 3+ headlines.
          </p>
        </div>

        <section className="glass rounded-2xl p-5" aria-label="News outcome evaluation">
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-display text-lg font-semibold text-white">
              Outcome study <span className="text-sm font-normal text-slate-500">• {ticker === 'ALL' ? 'All tickers' : ticker} • 30 days</span>
            </h2>
            <span className="chip chip-gold">Uncalibrated research baseline</span>
          </div>
          <p className="mb-4 text-xs leading-relaxed text-slate-400">
            Measures whether the impact sign matched later closed-bar price direction for
            medium/high signals. Directional accuracy and gross aligned returns are historical
            measurements—not probability forecasts or a promise of profit. Trading costs are excluded.
          </p>
          {evaluationLoading ? (
            <p className="text-sm text-slate-400">Loading completed outcome data…</p>
          ) : evaluationError ? (
            <p className="text-sm text-amber-300">{evaluationError}</p>
          ) : (
            <>
              {evaluation?.horizons?.length > 0 &&
                evaluation.horizons.every((item) => item.eligible_signals === 0) && (
                <p className="mb-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200">
                  No qualified signals have completed a measurable horizon in this period yet. The cards below show the available sample and outcome counts; accuracy is not reported without measured data.
                </p>
              )}
              {(evaluation?.horizons || []).length ? (
                <div className="grid gap-3 sm:grid-cols-3">
                  {evaluation.horizons.map((item) => (
                    <div key={item.horizon} className="rounded-xl border border-white/8 bg-white/[0.03] p-4">
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        {item.horizon} forward horizon
                      </p>
                      <p className="mt-2 font-mono text-2xl font-semibold text-white">
                        {item.directional_accuracy_pct == null
                          ? 'Not enough data'
                          : `${item.directional_accuracy_pct.toFixed(1)}%`}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        {item.samples} measured / {item.eligible_signals} eligible
                        {item.coverage_pct == null ? '' : ` • ${item.coverage_pct.toFixed(1)}% coverage`}
                        {` • ${item.directional_samples} directional`}
                        {item.mean_aligned_return_pct == null
                          ? ''
                          : ` • ${item.mean_aligned_return_pct >= 0 ? '+' : ''}${item.mean_aligned_return_pct.toFixed(3)}% mean aligned`}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-amber-300">The outcome service returned no horizon metrics.</p>
              )}
            </>
          )}
          <p className="mt-3 text-[11px] text-slate-600">
            One first-qualified observation per ticker per UTC hour. Source bars must be fully closed
            by signal time; targets are the first fully closed bars at or after each horizon.
          </p>
        </section>

      </div>
    </PageLayout>
  )
}

export default NewsPage