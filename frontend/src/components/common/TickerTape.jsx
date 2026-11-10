import { useEffect, useState } from 'react'
import { getWatchlist, getMarketPrices } from '../../api/marketApi'

function TickerItem({ ticker, price, change, changePeriod }) {
  const dailyChange = Number(change)
  const hasDailyChange = change !== null && change !== undefined && Number.isFinite(dailyChange)
  const isUp = hasDailyChange && dailyChange > 0
  const isDown = hasDailyChange && dailyChange < 0
  const arrow = isUp ? '▲' : isDown ? '▼' : '—'
  const periodLabel = changePeriod === 'TODAY' ? 'today' : 'last session'
  const movementLabel = isUp
    ? `Up ${dailyChange.toFixed(2)}% ${periodLabel}`
    : isDown
      ? `Down ${Math.abs(dailyChange).toFixed(2)}% ${periodLabel}`
      : hasDailyChange
        ? 'Unchanged today'
        : 'Daily change unavailable'
  const arrowColor = isUp
    ? 'border-emerald-400/60 bg-emerald-500/20 text-emerald-300'
    : isDown
      ? 'border-rose-400/60 bg-rose-500/20 text-rose-300'
      : 'border-slate-400/40 bg-slate-500/15 text-slate-300'

  return (
    <div className="flex items-center gap-2 whitespace-nowrap rounded-md px-1.5 py-1">
      <span className="font-display text-[11px] font-semibold tracking-wider text-slate-300">
        {ticker.replace('.NS', '')}
      </span>
      <span className="font-mono text-[11px] text-slate-100">₹{price}</span>
      <span
        className={`inline-flex h-5 min-w-5 shrink-0 items-center justify-center gap-1 rounded-full border px-1 text-[10px] font-extrabold leading-none ${arrowColor}`}
        aria-label={movementLabel}
        title={movementLabel}
      >
        {arrow}
        {hasDailyChange && `${dailyChange > 0 ? '+' : ''}${dailyChange.toFixed(2)}%`}
      </span>
    </div>
  )
}

function TickerTape() {
  const [items, setItems] = useState([])

  useEffect(() => {
    let mounted = true
    let loading = false
    const load = async () => {
      if (loading) return
      loading = true
      try {
        const [watchlistRes, pricesRes] = await Promise.all([
          getWatchlist(),
          getMarketPrices(),
        ])
        const tickers = watchlistRes.data.tickers || []
        const priceMap = pricesRes.data.prices || {}

        const changes = pricesRes.data.changes || {}
        const changePeriod = pricesRes.data.change_period || 'LAST SESSION'
        const build = (list) =>
          list.flatMap((t) => {
            const raw = priceMap[t]
            if (raw === undefined || raw === null) return []
            const price = Number(raw)
            if (!Number.isFinite(price) || price <= 0) return []
            return {
              ticker: t,
              price: price.toFixed(2),
              change: changes[t] ?? null,
              changePeriod,
            }
          })

        if (!mounted) return
        setItems(build(tickers))
      } catch {
        // Keep the last successful prices visible during a temporary refresh failure.
      } finally {
        loading = false
      }
    }
    load()
    const interval = window.setInterval(load, 15000)
    return () => {
      mounted = false
      window.clearInterval(interval)
    }
  }, [])

  if (items.length === 0) return null

  const doubled = [...items, ...items]
  return (
    <div className="market-ticker sticky top-0 z-50 overflow-hidden border-b border-[#1c2a41] shadow-sm shadow-black/30 lg:col-span-2 lg:row-start-1">
      <div className="ticker-wrap py-1.5 px-4">
        {doubled.map((item, i) => (
          <TickerItem key={`${item.ticker}-${i}`} {...item} />
        ))}
      </div>
    </div>
  )
}

export default TickerTape