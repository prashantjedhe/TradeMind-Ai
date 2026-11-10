import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createOrder, getPortfolioSummary, getOrders, manualExit } from '../api/orderApi'
import { exitOnNews } from '../api/newsApi'
import { getWatchlist } from '../api/marketApi'
import PageLayout from '../components/common/PageLayout'
import StatCard from '../components/common/StatCard'

function formatINR(value) {
  const n = Number(value)
  if (isNaN(n)) return '₹0'
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function formatDateTime(isoString) {
  return new Date(isoString).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const ORDER_TYPE_HINTS = {
  MARKET: 'Executes immediately at the current market price.',
  LIMIT: 'Fills only at your specified price or better. Sits as PENDING until triggered.',
  SL: 'Stop Loss: fires when price crosses your trigger, then fills at market price (can slip). Sits as PENDING until triggered.',
  TP: 'Take Profit: fires and fills at your exact target price. Sits as PENDING until triggered.',
}

function OrderTypeBadge({ type }) {
  const map = {
    MARKET: 'chip-cyan',
    LIMIT: 'chip-violet',
    SL: 'chip-gold',
    TP: 'chip-bull',
  }
  return <span className={`chip ${map[type] || 'chip-neutral'}`}>{type}</span>
}

function SideBadge({ side }) {
  return (
    <span className={`chip ${side === 'BUY' ? 'chip-bull' : 'chip-bear'}`}>
      {side === 'BUY' ? '▲ BUY' : '▼ SELL'}
    </span>
  )
}

function TradingPage() {
  const navigate = useNavigate()

  const [watchlist, setWatchlist] = useState([])
  const [portfolio, setPortfolio] = useState(null)
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)

  const [ticker, setTicker] = useState('')
  const [orderType, setOrderType] = useState('MARKET')
  const [side, setSide] = useState('BUY')
  const [settlementType, setSettlementType] = useState('DELIVERY')
  const [quantity, setQuantity] = useState('')
  const [triggerPrice, setTriggerPrice] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const isPendingType = orderType !== 'MARKET'

  const loadData = async () => {
    try {
      const [watchlistRes, portfolioRes, ordersRes] = await Promise.all([
        getWatchlist(),
        getPortfolioSummary(),
        getOrders(),
      ])
      setWatchlist(watchlistRes.data.tickers)
      setPortfolio(portfolioRes.data)
      setOrders(ordersRes.data)
      if (!ticker && watchlistRes.data.tickers.length > 0) {
        setTicker(watchlistRes.data.tickers[0])
      }
    } catch {
      navigate('/login')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setResult(null)
    setError(null)

    try {
      const payload = {
        ticker,
        order_type: orderType,
        side,
        settlement_type: settlementType,
        quantity: Number(quantity),
      }
      if (isPendingType) {
        payload.limit_price = Number(triggerPrice)
      }

      const { data } = await createOrder(payload)
      setResult(data)
      setQuantity('')
      setTriggerPrice('')
      await loadData()
    } catch (err) {
      setError(err.response?.data?.detail || 'Order failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const pendingOrders = orders.filter((o) => o.status === 'PENDING')
  const filledOrders = orders.filter((o) => o.status !== 'PENDING')

  const [exitingPosition, setExitingPosition] = useState(null)

  const handlePositionExit = async (positionTicker, exitType) => {
    const isNewsExit = exitType === 'news'
    const description = isNewsExit ? 'at MARKET on news' : 'manually at MARKET'
    if (!window.confirm(`Exit full ${positionTicker} position ${description}?`)) return
    setExitingPosition({ ticker: positionTicker, type: exitType })
    setResult(null)
    setError(null)
    try {
      const { data } = isNewsExit
        ? await exitOnNews(positionTicker)
        : await manualExit(positionTicker)
      setResult(data)
      await loadData()
    } catch (err) {
      setError(err.response?.data?.detail || 'Position exit failed. Please try again.')
    } finally {
      setExitingPosition(null)
    }
  }

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
        {/* Header */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="chip chip-cyan mb-2">Paper Trading • NSE</p>
            <h1 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Trading <span className="text-gradient-cyan">Terminal</span>
            </h1>
            <p className="mt-2 max-w-xl text-sm text-slate-400">
              Place market, limit, stop-loss and take-profit orders on virtual balance.
            </p>
          </div>
        </div>

        {/* Balance summary */}
        {portfolio && (
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard
              label="Virtual Balance"
              value={formatINR(portfolio.virtual_balance)}
              icon="₹"
              tone="cyan"
              className="card-3d"
            />
            <StatCard
              label="Net Worth"
              value={formatINR(portfolio.net_worth)}
              icon="◈"
              tone="violet"
              className="card-3d"
            />
            <StatCard
              label="Unrealised P&L"
              value={formatINR(portfolio.total_unrealised_pnl)}
              icon="↗"
              tone={Number(portfolio.total_unrealised_pnl) >= 0 ? 'bull' : 'bear'}
              positive={Number(portfolio.total_unrealised_pnl) >= 0}
              className="card-3d"
            />
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Order form */}
          <div className="glass glow-cyan card-3d rounded-2xl p-6">
            <div className="card-glow" />
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-white">Place Order</h2>
              <span className="chip chip-neutral">0.05% slippage</span>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="ticker-select" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Ticker
                </label>
                <select
                  id="ticker-select"
                  name="ticker"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                  className="input-3d"
                >
                  {watchlist.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="order-type-select" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Order Type
                </label>
                <select
                  id="order-type-select"
                  name="order_type"
                  value={orderType}
                  onChange={(e) => setOrderType(e.target.value)}
                  className="input-3d"
                >
                  <option value="MARKET">MARKET</option>
                  <option value="LIMIT">LIMIT</option>
                  <option value="SL">SL (Stop Loss)</option>
                  <option value="TP">TP (Take Profit)</option>
                </select>
                <p className="mt-1 text-[11px] text-slate-500">{ORDER_TYPE_HINTS[orderType]}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="side-select" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Side
                  </label>
                  <select
                    id="side-select"
                    name="side"
                    value={side}
                    onChange={(e) => setSide(e.target.value)}
                    className="input-3d"
                  >
                    <option value="BUY">BUY</option>
                    <option value="SELL">SELL</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="settlement-select" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Settlement
                  </label>
                  <select
                    id="settlement-select"
                    name="settlement_type"
                    value={settlementType}
                    onChange={(e) => setSettlementType(e.target.value)}
                    className="input-3d"
                  >
                    <option value="DELIVERY">DELIVERY</option>
                    <option value="INTRADAY">INTRADAY</option>
                  </select>
                </div>
              </div>

              {isPendingType && (
                <div>
                  <label htmlFor="trigger-price-input" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Trigger Price (₹)
                  </label>
                  <input
                    id="trigger-price-input"
                    name="trigger_price"
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={triggerPrice}
                    onChange={(e) => setTriggerPrice(e.target.value)}
                    className="input-3d font-mono"
                    placeholder="e.g. 2500.00"
                  />
                </div>
              )}

              <div>
                <label htmlFor="quantity-input" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Quantity
                </label>
                <input
                  id="quantity-input"
                  name="quantity"
                  type="number"
                  min="1"
                  required
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="input-3d font-mono"
                  placeholder="e.g. 10"
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className={`w-full rounded-xl py-3 text-sm font-bold disabled:opacity-50 ${
                  side === 'BUY' ? 'btn-bull' : 'btn-bear'
                }`}
              >
                {submitting
                  ? 'Placing order…'
                  : `${side} ${ticker || ''} ${isPendingType ? `(${orderType})` : ''}`}
              </button>
            </form>

            {error && (
              <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
                {error}
              </div>
            )}

            {result && (
              <div className="mt-4 rounded-xl border border-white/10 bg-black/30 p-4 text-sm">
                {result.status === 'PENDING' ? (
                  <>
                    <p className="mb-2 font-semibold text-amber-300">Order Placed — Pending Trigger</p>
                    <p className="text-slate-400">
                      {result.side} {result.quantity} {result.ticker} ({result.order_type}) will trigger at{' '}
                      <span className="font-mono text-white">₹{result.trigger_price ?? triggerPrice}</span>
                    </p>
                  </>
                ) : (
                  <>
                    <p className="mb-2 font-semibold text-emerald-400">
                      Order Filled — {result.side} {result.quantity} {result.ticker}
                    </p>
                    <div className="space-y-1 text-slate-400">
                      <p>
                        Executed Price: <span className="font-mono text-white">₹{result.executed_price}</span>
                      </p>
                      <p>
                        Slippage: <span className="font-mono text-white">₹{result.slippage_amount}</span>
                      </p>
                      <p>
                        Total Fees: <span className="font-mono text-white">₹{result.total_fees}</span>
                      </p>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Open positions */}
          <div className="glass glow-violet card-3d rounded-2xl p-6 lg:col-span-2">
            <div className="card-glow" />
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-white">Open Positions</h2>
              {portfolio && portfolio.positions.length > 0 && (
                <span className="chip chip-cyan">{portfolio.positions.length} open</span>
              )}
            </div>
            {portfolio && portfolio.positions.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="table-3d">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Qty</th>
                      <th>Avg Entry</th>
                      <th>Current</th>
                      <th>Unrealised P&amp;L</th>
                      <th>Exit Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portfolio.positions.map((p) => (
                      <tr key={p.id}>
                        <td className="font-semibold text-white">{p.ticker}</td>
                        <td className="font-mono">{p.quantity}</td>
                        <td className="font-mono">₹{p.avg_entry_price}</td>
                        <td className="font-mono">{p.current_price ? `₹${p.current_price}` : '—'}</td>
                        <td className={Number(p.unrealised_pnl) >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                          {p.unrealised_pnl ? `₹${p.unrealised_pnl}` : '—'}
                        </td>
                        <td>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={exitingPosition?.ticker === p.ticker}
                              onClick={() => handlePositionExit(p.ticker, 'manual')}
                              title="Close the full position immediately at market"
                              className="rounded-lg border border-rose-500/30 bg-rose-500/15 px-3 py-1.5 text-[11px] font-semibold text-rose-300 transition hover:bg-rose-500/25 disabled:opacity-50"
                            >
                              {exitingPosition?.ticker === p.ticker && exitingPosition.type === 'manual'
                                ? 'Exiting…'
                                : 'Exit manually'}
                            </button>
                            <button
                              type="button"
                              disabled={exitingPosition?.ticker === p.ticker}
                              onClick={() => handlePositionExit(p.ticker, 'news')}
                              title="Close the full position at market and tag it as a news exit"
                              className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-1.5 text-[11px] font-semibold text-amber-300 transition hover:bg-amber-500/20 disabled:opacity-50"
                            >
                              {exitingPosition?.ticker === p.ticker && exitingPosition.type === 'news'
                                ? 'Exiting…'
                                : '⚡ Exit on news'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex h-48 flex-col items-center justify-center text-center">
                <span className="mb-2 text-3xl">📭</span>
                <p className="text-sm text-slate-500">No open positions</p>
              </div>
            )}

            {/* Pending orders */}
            {pendingOrders.length > 0 && (
              <>
                <hr className="hr-glow my-5" />
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="font-display text-sm font-semibold text-white">Pending Orders</h3>
                  <span className="chip chip-gold">{pendingOrders.length} waiting</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="table-3d">
                    <thead>
                      <tr>
                        <th>Placed</th>
                        <th>Ticker</th>
                        <th>Type</th>
                        <th>Side</th>
                        <th>Qty</th>
                        <th>Trigger Price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pendingOrders.map((o) => (
                        <tr key={o.id}>
                          <td className="whitespace-nowrap text-slate-500">{formatDateTime(o.created_at)}</td>
                          <td className="font-medium text-white">{o.ticker}</td>
                          <td><OrderTypeBadge type={o.order_type} /></td>
                          <td><SideBadge side={o.side} /></td>
                          <td className="font-mono">{o.quantity}</td>
                          <td className="font-mono">₹{o.trigger_price}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Transaction history */}
        {filledOrders.length > 0 && (
          <div className="glass rounded-2xl p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-white">Transaction History</h2>
              <span className="chip chip-neutral">{filledOrders.length} records</span>
            </div>
            <div className="overflow-x-auto">
              <table className="table-3d">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Ticker</th>
                    <th>Type</th>
                    <th>Side</th>
                    <th>Qty</th>
                    <th>Executed Price</th>
                    <th>Fees</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filledOrders.map((o) => (
                    <tr key={o.id}>
                      <td className="whitespace-nowrap text-slate-500">{formatDateTime(o.created_at)}</td>
                      <td className="font-medium text-white">{o.ticker}</td>
                      <td><OrderTypeBadge type={o.order_type} /></td>
                      <td><SideBadge side={o.side} /></td>
                      <td className="font-mono">{o.quantity}</td>
                      <td className="font-mono">{o.executed_price ? `₹${o.executed_price}` : '—'}</td>
                      <td className="font-mono text-slate-400">{o.total_fees ? `₹${o.total_fees}` : '—'}</td>
                      <td>
                        <span className={`chip ${o.status === 'FILLED' ? 'chip-bull' : 'chip-neutral'}`}>
                          {o.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  )
}

export default TradingPage