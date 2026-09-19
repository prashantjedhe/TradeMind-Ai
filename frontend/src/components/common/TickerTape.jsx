import { useEffect, useState } from 'react'
import { getWatchlist, getMarketPrices } from '../../api/marketApi'

function TickerItem({ ticker, price, prev }) {
  const current = Number(price)
  const prevValue = prev !== null && prev !== undefined ? Number(prev) : null
  const isUp = prevValue !== null && current > prevValue
  const isDown = prevValue !== null && current < prevValue
  const arrow = isUp ? '▲' : isDown ? '▼' : '•'
  const arrowColor = isUp ? 'text-emerald-400' : isDown ? 'text-rose-400' : 'text-slate-500'

  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <span className="font-display text-[11px] font-semibold tracking-wider text-slate-300">
        {ticker.replace('.NS', '')}
      </span>
      <span className="font-mono text-[11px] text-slate-100">₹{price}</span>
      <span className={`text-[10px] ${arrowColor}`} aria-label={isUp ? 'up' : isDown ? 'down' : 'flat'}>
        {arrow}
      </span>
    </div>
  )
}

function TickerTape() {
  const [items, setItems] = useState([])

  useEffect(() => {
    const load = async () => {
      try {
        const [watchlistRes, pricesRes] = await Promise.all([
          getWatchlist(),
          getMarketPrices(),
        ])
        const tickers = watchlistRes.data.tickers || []
        const priceMap = pricesRes.data.prices || {}

        const build = (list) =>
          list.map((t) => {
            const raw = priceMap[t]
            const price = raw !== undefined && raw !== null ? Number(raw) : 0
            return {
              ticker: t,
              price: price.toFixed(2),
            }
          })

        setItems((prevState) => {
          const prevMap = Object.fromEntries(prevState.map((i) => [i.ticker, Number(i.price)]))
          const withPrev = build(tickers.slice(0, 9)).map((i) => ({
            ...i,
            prev: prevMap[i.ticker] ?? null,
          }))
          const batch2 = build(tickers.slice(9, 18)).map((i) => ({
            ...i,
            prev: prevMap[i.ticker] ?? null,
          }))
          return [...withPrev, ...batch2]
        })
      } catch {
        // no-op: tape stays hidden until data loads
      }
    }
    load()
  }, [])

  if (items.length === 0) return null

  const doubled = [...items, ...items]
  return (
    <div className="relative z-20 overflow-hidden border-b border-white/5 bg-black/30 backdrop-blur-md">
      <div className="ticker-wrap py-1.5 px-4">
        {doubled.map((item, i) => (
          <TickerItem key={`${item.ticker}-${i}`} {...item} />
        ))}
      </div>
    </div>
  )
}

export default TickerTape