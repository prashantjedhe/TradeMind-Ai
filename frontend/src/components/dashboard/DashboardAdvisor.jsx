import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { confirmMarketTrade, getMarketBrief } from '../../api/newsApi'
import { confirmTradeProposal, getTradeProposals } from '../../api/orderApi'

const SENTIMENT_STYLE = {
  bullish: 'chip-bull',
  bearish: 'chip-bear',
  mixed: 'chip-gold',
  unavailable: 'chip-neutral',
}

function DashboardAdvisor() {
  const [brief, setBrief] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [proposalError, setProposalError] = useState('')
  const [orderMessage, setOrderMessage] = useState('')
  const [strategyProposals, setStrategyProposals] = useState([])
  const [confirmingStrategyProposal, setConfirmingStrategyProposal] = useState('')

  const loadBrief = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const [briefResult, proposalResult] = await Promise.all([
        getMarketBrief(),
        getTradeProposals(),
      ])
      setBrief(briefResult.data)
      setStrategyProposals(proposalResult.data)
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Market brief could not be loaded.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  const submitStrategyProposal = async (proposal) => {
    if (confirmingStrategyProposal) return
    setConfirmingStrategyProposal(proposal.id)
    setProposalError('')
    setOrderMessage('')
    try {
      const { data } = await confirmTradeProposal(proposal.id)
      setOrderMessage(
        `Paper LIMIT ${data.side} ${data.quantity} ${data.ticker} at ₹${Number(data.trigger_price).toFixed(2)} is ${String(data.status).toLowerCase()}.`
      )
      await loadBrief(true)
    } catch (requestError) {
      setProposalError(
        requestError.response?.data?.detail || 'The strategy proposal could not be submitted.'
      )
      await loadBrief(true)
    } finally {
      setConfirmingStrategyProposal('')
    }
  }

  const submitProposal = async () => {
    const proposal = brief?.trade_proposal
    if (!proposal || confirming) return

    setConfirming(true)
    setProposalError('')
    setOrderMessage('')
    try {
      const { data } = await confirmMarketTrade(proposal.proposal_id, proposal.signal_id)
      setOrderMessage(
        `Paper LIMIT ${data.side} ${data.quantity} ${data.ticker} at ₹${Number(data.trigger_price).toFixed(2)} is ${String(data.status).toLowerCase()}.`
      )
      await loadBrief(true)
    } catch (requestError) {
      setProposalError(
        requestError.response?.data?.detail || 'The proposed order could not be submitted.'
      )
      if (requestError.response?.status === 409) await loadBrief(true)
    } finally {
      setConfirming(false)
    }
  }

  useEffect(() => {
    loadBrief()
    const intervalId = window.setInterval(() => loadBrief(true), 5 * 60 * 1000)
    return () => window.clearInterval(intervalId)
  }, [loadBrief])

  return (
    <section className="glass rounded-2xl p-6" aria-labelledby="dashboard-advisor-heading">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
            News intelligence · past 60 minutes
          </p>
          <h2 id="dashboard-advisor-heading" className="mt-1 font-display text-lg font-semibold text-white">
            Market Brief
          </h2>
        </div>
        <div className="flex items-center gap-3">
          {brief && (
            <span className={`chip ${SENTIMENT_STYLE[brief.sentiment] || 'chip-neutral'}`}>
              {brief.sentiment === 'unavailable' ? 'No signal' : `${brief.sentiment} news`}
            </span>
          )}
          <button
            type="button"
            onClick={() => loadBrief(true)}
            disabled={refreshing || loading}
            className="btn-ghost rounded-lg px-3 py-2 text-xs font-semibold disabled:opacity-50"
          >
            {refreshing ? 'Updating…' : 'Refresh'}
          </button>
        </div>
      </div>

      {proposalError && (
        <p className="mt-3 text-sm text-rose-300" role="alert">{proposalError}</p>
      )}
      {orderMessage && (
        <p className="mt-3 text-sm text-emerald-300" role="status">{orderMessage}</p>
      )}

      {strategyProposals.length > 0 && (
        <div className="mt-4 space-y-3" aria-label="Strategy trade proposals">
          {strategyProposals.map((proposal) => (
            <article key={proposal.id} className="rounded-xl border border-amber-400/25 bg-amber-400/[0.035] p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-amber-200">
                    Strategy setup · final confirmation required
                  </p>
                  <p className="mt-2 text-sm font-semibold text-white">
                    {proposal.side} {proposal.quantity} {proposal.ticker}
                    {' '}· LIMIT ₹{Number(proposal.limit_price).toFixed(2)}
                  </p>
                  <p className="mt-1 text-sm leading-5 text-slate-300">{proposal.rationale}</p>
                  {proposal.evidence?.strategy_name && (
                    <p className="mt-1 text-xs text-slate-400">
                      Strategy: {proposal.evidence.strategy_name}
                      {proposal.evidence.timeframe ? ` · ${proposal.evidence.timeframe}` : ''}
                    </p>
                  )}
                  {proposal.evidence?.headlines?.slice(0, 2).map((headline) => (
                    <p key={headline.url} className="mt-1 text-xs leading-5 text-slate-400">
                      {headline.title}
                    </p>
                  ))}
                  <p className="mt-2 text-xs text-slate-500">
                    Expires {new Date(proposal.expires_at).toLocaleTimeString()} · not an executed order
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => submitStrategyProposal(proposal)}
                  disabled={Boolean(confirmingStrategyProposal) || refreshing}
                  className="btn-primary shrink-0 rounded-lg px-4 py-2.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {confirmingStrategyProposal === proposal.id ? 'Checking setup…' : 'Confirm LIMIT order'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {loading ? (
        <p className="mt-5 text-sm text-slate-400" role="status">Loading latest scored headlines…</p>
      ) : error ? (
        <div className="mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300" role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => loadBrief(true)} className="mt-2 underline underline-offset-2">
            Try again
          </button>
        </div>
      ) : brief ? (
        <>
          <div className="mt-4 rounded-xl border border-white/8 bg-white/[0.025] p-4">
            <p className="text-sm leading-6 text-slate-200">{brief.summary}</p>
            <p className="mt-2 text-xs leading-5 text-slate-400">
              {brief.article_count} scored headline{brief.article_count === 1 ? '' : 's'}
              {brief.average_sentiment !== null
                ? ` · average sentiment ${Number(brief.average_sentiment).toFixed(2)}`
                : ''}
              {brief.average_impact !== null
                ? ` · heuristic impact ${Number(brief.average_impact).toFixed(2)}`
                : ''}
            </p>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-white/8 bg-white/[0.02] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">Suggested next move</p>
              <p className="mt-2 text-sm leading-6 text-slate-200">{brief.action}</p>
            </div>
            <div className="rounded-xl border border-white/8 bg-white/[0.02] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">Strategy to consider</p>
              <p className="mt-2 text-sm leading-6 text-slate-200">{brief.strategy}</p>
              <p className="mt-2 text-xs text-slate-500">
                Confidence: {brief.confidence} · NIFTY trend: {brief.market_snapshot?.daily_trend === 'unknown' ? 'unconfirmed' : brief.market_snapshot?.daily_trend || 'unavailable'}
              </p>
            </div>
          </div>

          {brief.trade_proposal && (
            <div className="mt-4 rounded-xl border border-cyan-400/25 bg-cyan-400/[0.04] p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-cyan-200">
                    Proposed paper setup · user confirmation required
                  </p>
                  <p className="mt-2 text-sm font-semibold text-white">
                    {brief.trade_proposal.side} {brief.trade_proposal.quantity} {brief.trade_proposal.ticker}
                    {' '}· LIMIT ₹{Number(brief.trade_proposal.limit_price).toFixed(2)}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-slate-300">
                    {brief.trade_proposal.rationale} Impact {brief.trade_proposal.impact_band.toLowerCase()}
                    {' '}({Number(brief.trade_proposal.impact).toFixed(2)}), based on
                    {' '}{brief.trade_proposal.article_count} headlines.
                  </p>
                  <p className="mt-2 text-xs leading-5 text-slate-400">
                    {brief.trade_proposal.risk_note}
                  </p>
                  {brief.trade_proposal.headlines?.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {brief.trade_proposal.headlines.slice(0, 2).map((headline) => (
                        <li key={headline.url} className="text-xs leading-5 text-slate-400">
                          {headline.title} <span className="text-slate-500">· {headline.label}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <button
                  type="button"
                  onClick={submitProposal}
                  disabled={confirming || loading || refreshing}
                  className="btn-primary shrink-0 rounded-lg px-4 py-2.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {confirming ? 'Submitting…' : 'Confirm LIMIT order'}
                </button>
              </div>
            </div>
          )}
          {!brief.trade_proposal && strategyProposals.length === 0 && (
            <p className="mt-4 rounded-lg border border-white/8 bg-white/[0.02] px-4 py-3 text-sm leading-5 text-slate-400">
              No confirmable trade setup right now. {brief.setup_reason}
              {' '}Only activated strategies are monitored; matching conditions create a proposal and never submit an order automatically.
            </p>
          )}

          {brief.headlines?.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">Recent headlines</p>
              <ul className="mt-2 divide-y divide-white/5">
                {brief.headlines.map((item, index) => (
                  <li key={`${item.published_at}-${index}`} className="flex items-start justify-between gap-3 py-2.5">
                    <span className="text-sm leading-5 text-slate-300">{item.headline}</span>
                    <span className={`chip shrink-0 ${item.label === 'POS' ? 'chip-bull' : item.label === 'NEG' ? 'chip-bear' : 'chip-neutral'}`}>
                      {item.label}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-4 flex flex-col gap-2 border-t border-white/8 pt-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[11px] leading-5 text-slate-500">
              {brief.disclaimer} Updates every 5 minutes.
              {brief.as_of ? ` Updated ${new Date(brief.as_of).toLocaleTimeString()}.` : ''}
            </p>
            <Link to="/strategies" className="shrink-0 text-xs font-semibold text-cyan-300 hover:text-cyan-200">
              Open strategy builder →
            </Link>
          </div>
        </>
      ) : (
        <p className="mt-5 text-sm text-slate-400">No market brief is available yet.</p>
      )}
    </section>
  )
}

export default DashboardAdvisor
