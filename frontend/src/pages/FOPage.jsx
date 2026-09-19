import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getFnoUniverse, getFnoChain } from '../api/marketApi'
import { createOrder, getPortfolioSummary } from '../api/orderApi'
import PageLayout from '../components/common/PageLayout'
import StatCard from '../components/common/StatCard'

function formatINR(value) {
  const n = Number(value)
  if (isNaN(n)) return '₹0'
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function formatNum(value, digits = 2) {
  const n = Number(value)
  if (isNaN(n)) return '—'
  return n.toLocaleString('en-IN', { maximumFractionDigits: digits })
}

function formatPremium(value) {
  const n = Number(value)
  if (isNaN(n)) return '—'
  if (n > 0 && n < 0.01) return '<₹0.01'
  return `₹${n.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

const UNDERLYING_MAP = {
  RELIANCE: 'Oil & Gas',
  HDFCBANK: 'Banking',
  ICICIBANK: 'Banking',
  SBIN: 'Banking',
  TCS: 'IT',
  INFY: 'IT',
}

function OrderResultCard({ result }) {
  if (!result) return null
  const isPending = result.status === 'PENDING'
  return (
    <div className="mt-4 rounded-xl border border-white/10 bg-black/30 p-4 text-sm">
      <p className={`mb-2 font-semibold ${isPending ? 'text-amber-300' : 'text-emerald-400'}`}>
        {isPending ? 'Order Placed — Pending Trigger' : `Order Filled — ${result.side} ${result.quantity} ${result.ticker}`}
      </p>
      <div className="space-y-1 text-slate-400">
        {isPending ? (
          <p>
            Will trigger at <span className="font-mono text-white">₹{result.trigger_price}</span>
          </p>
        ) : (
          <>
            <p>
              Executed Price: <span className="font-mono text-white">₹{result.executed_price}</span>
            </p>
            <p>
              Total Fees: <span className="font-mono text-white">₹{result.total_fees}</span>
            </p>
          </>
        )}
      </div>
    </div>
  )
}

function FOPage() {
  const navigate = useNavigate()

  const [underlyings, setUnderlyings] = useState([])
  const [portfolio, setPortfolio] = useState(null)
  const [chainData, setChainData] = useState(null)
  const [loading, setLoading] = useState(true)

  const [underlying, setUnderlying] = useState('RELIANCE')
  const [expiry, setExpiry] = useState('')
  const [tab, setTab] = useState('OPTIONS')

  const [side, setSide] = useState('BUY')
  const [quantity, setQuantity] = useState('')
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [selectedMeta, setSelectedMeta] = useState(null)

  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const loadInitial = async () => {
    try {
      const [universeRes, portfolioRes] = await Promise.all([getFnoUniverse(), getPortfolioSummary()])
      setUnderlyings(universeRes.data.underlyings)
      setPortfolio(portfolioRes.data)
      if (universeRes.data.underlyings.length > 0) {
        setUnderlying(universeRes.data.underlyings[0])
      }
    } catch {
      navigate('/login')
    } finally {
      setLoading(false)
    }
  }

  const loadChain = async (u, exp) => {
    try {
      const res = await getFnoChain(u, exp || undefined)
      setChainData(res.data)
      setExpiry(res.data.expiry || exp)
      setSelectedSymbol(null)
      setSelectedMeta(null)
      setResult(null)
      setError(null)
    } catch {
      setError('Failed to load option chain.')
    }
  }

  useEffect(() => {
    loadInitial()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (underlying) {
      loadChain(underlying, expiry)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [underlying])

  const chain = chainData?.chain
  const strikes = useMemo(() => {
    if (!chain?.contracts) return []
    const set = new Set(chain.contracts.map((c) => c.strike))
    return Array.from(set).sort((a, b) => a - b)
  }, [chain])

  const contractsByStrike = useMemo(() => {
    const map = {}
    chain?.contracts?.forEach((c) => {
      if (!map[c.strike]) map[c.strike] = {}
      map[c.strike][c.option_type] = c
    })
    return map
  }, [chain])

  const handleOrder = async (e) => {
    e.preventDefault()
    if (!selectedSymbol) {
      setError('Select a contract from the chain first.')
      return
    }
    setSubmitting(true)
    setResult(null)
    setError(null)
    try {
      const payload = {
        ticker: selectedSymbol,
        order_type: 'MARKET',
        side,
        settlement_type: 'INTRADAY',
        quantity: Number(quantity),
      }
      const { data } = await createOrder(payload)
      setResult(data)
      setQuantity('')
      const [portfolioRes] = await Promise.all([getPortfolioSummary()])
      setPortfolio(portfolioRes.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Order failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const selectContract = (c) => {
    setSelectedSymbol(c.symbol)
    setSelectedMeta(c)
    setSide('BUY')
    setQuantity(String(c.lot_size))
    setError(null)
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
            <p className="chip chip-violet mb-2">F&O Derivatives • Simulated Chain</p>
            <h1 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Futures &amp; <span className="text-gradient-violet">Options</span>
            </h1>
            <p className="mt-2 max-w-xl text-sm text-slate-400">
              Black-Scholes-priced option chain and futures quotes, derived live from the underlying spot.
            </p>
          </div>
          {portfolio && (
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-[10px] uppercase tracking-wider text-slate-500">Virtual Balance</p>
                <p className="font-mono text-sm font-bold text-white">{formatINR(portfolio.virtual_balance)}</p>
              </div>
              <div className="text-right">
                <p className="text-[10px] uppercase tracking-wider text-slate-500">Net Worth</p>
                <p className="font-mono text-sm font-bold text-cyan-300">{formatINR(portfolio.net_worth)}</p>
              </div>
            </div>
          )}
        </div>

        {/* Underlying + expiry selector */}
        <div className="glass glow-violet card-3d rounded-2xl p-5">
          <div className="card-glow" />
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Underlying</label>
              <div className="flex flex-wrap gap-1.5">
                {underlyings.map((u) => (
                  <button
                    key={u}
                    type="button"
                    onClick={() => {
                      setUnderlying(u)
                      setExpiry('')
                    }}
                    className={`rounded-lg px-3 py-1.5 text-[11px] font-semibold transition ${
                      underlying === u
                        ? 'bg-gradient-to-r from-violet-500 to-fuchsia-600 text-white shadow-lg'
                        : 'border border-white/10 bg-white/5 text-slate-400 hover:text-white'
                    }`}
                  >
                    {u}
                    <span className="ml-1.5 text-[9px] opacity-60">{UNDERLYING_MAP[u] || 'NSE'}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Expiry</label>
              <div className="flex flex-wrap gap-1.5">
                {(chainData?.expiries || []).map((e) => (
                  <button
                    key={e}
                    type="button"
                    onClick={() => {
                      setExpiry(e)
                      loadChain(underlying, e)
                    }}
                    className={`rounded-lg px-3 py-1.5 text-[11px] font-semibold transition ${
                      expiry === e
                        ? 'bg-gradient-to-r from-cyan-500 to-violet-600 text-white shadow-lg'
                        : 'border border-white/10 bg-white/5 text-slate-400 hover:text-white'
                    }`}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Spot strip */}
        {chainData && (
          <div className="grid gap-4 sm:grid-cols-4">
            <StatCard
              label="Underlying Spot"
              value={`₹${formatNum(chainData.spot)}`}
              icon="◎"
              tone="violet"
              className="card-3d"
            />
            <StatCard
              label="Expiry"
              value={chainData.expiry}
              icon="◷"
              tone="cyan"
              className="card-3d"
            />
            <StatCard
              label="Days to Expiry"
              value={chain?.days_to_expiry ?? '—'}
              icon="⏳"
              tone="gold"
              className="card-3d"
            />
            <StatCard
              label="Contract Size (lot)"
              value={chain?.lot_size ?? '—'}
              icon="◱"
              tone="bull"
              className="card-3d"
            />
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setTab('OPTIONS')}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
              tab === 'OPTIONS' ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            ☰ Option Chain
          </button>
          <button
            type="button"
            onClick={() => setTab('FUTURES')}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
              tab === 'FUTURES' ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            ⚡ Futures
          </button>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Chain / Futures panel */}
          <div className="glass glow-cyan card-3d rounded-2xl p-6 lg:col-span-2">
            <div className="card-glow" />
            {tab === 'OPTIONS' ? (
              <>
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="font-display text-lg font-semibold text-white">
                    {underlying} Option Chain <span className="text-slate-500">• {expiry}</span>
                  </h2>
                  {chainData?.spot && (
                    <span className="chip chip-violet">Spot ₹{formatNum(chainData.spot)}</span>
                  )}
                </div>

                {chain?.contracts?.length ? (
                  <div className="max-h-[540px] overflow-x-auto overflow-y-auto">
                    <table className="table-3d w-full">
                      <thead>
                        <tr className="border-b border-white/10">
                          <th colSpan="3" className="text-center text-emerald-300">CALL (CE)</th>
                          <th className="text-center text-cyan-300">STRIKE</th>
                          <th colSpan="3" className="text-center text-rose-300">PUT (PE)</th>
                        </tr>
                        <tr>
                          <th>Contract</th>
                          <th>LTP / Premium</th>
                          <th>Delta · IV</th>
                          <th className="text-center">Strike</th>
                          <th>Delta · IV</th>
                          <th>LTP / Premium</th>
                          <th>Contract</th>
                        </tr>
                      </thead>
                      <tbody>
                        {strikes.map((strike) => {
                          const ce = contractsByStrike[strike]?.CE
                          const pe = contractsByStrike[strike]?.PE
                          const isAtm = ce?.is_atm
                          return (
                            <tr
                              key={strike}
                              className={`transition hover:bg-white/[0.04] ${
                                isAtm ? 'bg-cyan-500/[0.06]' : ''
                              }`}
                            >
                              <td
                                className="whitespace-nowrap font-mono text-[11px] text-white"
                                title="Select call contract"
                                onClick={() => ce && selectContract(ce)}
                              >
                                {ce ? ce.symbol : '—'}
                              </td>
                              <td
                                className={`whitespace-nowrap font-mono ${ce ? 'cursor-pointer text-emerald-300' : 'text-slate-600'}`}
                                title="Select call contract"
                                onClick={() => ce && selectContract(ce)}
                              >
                                {ce ? formatPremium(ce.premium) : '—'}
                              </td>
                              <td
                                className="whitespace-nowrap font-mono text-[11px] text-slate-400"
                                title="Select call contract"
                                onClick={() => ce && selectContract(ce)}
                              >
                                {ce ? `${ce.delta} · ${(Number(ce.iv) * 100).toFixed(1)}%` : '—'}
                              </td>
                              <td className="whitespace-nowrap text-center">
                                <span className={`font-mono text-xs ${isAtm ? 'font-bold text-cyan-300' : 'text-slate-300'}`}>
                                  ₹{formatNum(strike, 0)}
                                </span>
                                {isAtm && <span className="ml-1 text-[9px] text-cyan-500">ATM</span>}
                              </td>
                              <td
                                className="whitespace-nowrap cursor-pointer font-mono text-[11px] text-slate-400"
                                title="Select put contract"
                                onClick={() => pe && selectContract(pe)}
                              >
                                {pe ? `${pe.delta} · ${(Number(pe.iv) * 100).toFixed(1)}%` : '—'}
                              </td>
                              <td
                                className={`whitespace-nowrap font-mono ${pe ? 'cursor-pointer text-rose-300' : 'text-slate-600'}`}
                                title="Select put contract"
                                onClick={() => pe && selectContract(pe)}
                              >
                                {pe ? formatPremium(pe.premium) : '—'}
                              </td>
                              <td
                                className="whitespace-nowrap cursor-pointer font-mono text-[11px] text-white"
                                title="Select put contract"
                                onClick={() => pe && selectContract(pe)}
                              >
                                {pe ? pe.symbol : '—'}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="flex h-48 flex-col items-center justify-center text-center">
                    <span className="mb-2 text-3xl">📉</span>
                    <p className="text-sm text-slate-500">{chainData?.error || 'No chain available'}</p>
                  </div>
                )}
              </>
            ) : (
              <>
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="font-display text-lg font-semibold text-white">
                    {underlying} Futures <span className="text-slate-500">• 3 monthly expiries</span>
                  </h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="table-3d w-full">
                    <thead>
                      <tr>
                        <th>Contract</th>
                        <th>Expiry</th>
                        <th>Days</th>
                        <th>Price</th>
                        <th>Basis</th>
                        <th>Lot</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(chainData?.futures || []).map((f) => (
                        <tr
                          key={f.symbol}
                          className="cursor-pointer transition hover:bg-white/[0.04]"
                          onClick={() => {
                            setSelectedSymbol(f.symbol)
                            setSelectedMeta({ ...f, premium: f.price, option_type: 'FUT' })
                            setSide('BUY')
                            setQuantity(String(f.lot_size))
                            setError(null)
                          }}
                        >
                          <td className="whitespace-nowrap font-mono text-[11px] text-white">{f.symbol}</td>
                          <td className="whitespace-nowrap">{f.expiry}</td>
                          <td className="whitespace-nowrap font-mono text-slate-400">{f.days_to_expiry}</td>
                          <td className="whitespace-nowrap font-mono text-emerald-300">{formatNum(f.price)}</td>
                          <td className="whitespace-nowrap font-mono text-slate-400">{formatNum(f.basis)}</td>
                          <td className="whitespace-nowrap font-mono text-slate-400">{f.lot_size}</td>
                          <td className="whitespace-nowrap">
                            <span className="chip chip-violet">select</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>

          {/* Order ticket */}
          <div className="glass rounded-2xl p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-white">Trade Ticket</h2>
              <span className="chip chip-neutral">MARKET • INTRADAY</span>
            </div>

            {selectedMeta ? (
              <div className="mb-4 rounded-xl border border-white/10 bg-black/30 p-3">
                <p className="mb-1 truncate font-mono text-xs text-white">{selectedSymbol}</p>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400">
                  <span>{selectedMeta.option_type || 'FUT'}</span>
                  {selectedMeta.strike && <span>Strike {selectedMeta.strike}</span>}
                  <span>Last ₹{formatNum(selectedMeta.premium || selectedMeta.price)}</span>
                </div>
              </div>
            ) : (
              <p className="mb-4 text-xs text-slate-500">Click any CE / PE / future row to populate the ticket.</p>
            )}

            <form onSubmit={handleOrder} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Side
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setSide('BUY')}
                    className={`rounded-xl py-2.5 text-sm font-semibold transition ${
                      side === 'BUY' ? 'btn-bull' : 'border border-white/10 bg-white/5 text-slate-400'
                    }`}
                  >
                    BUY
                  </button>
                  <button
                    type="button"
                    onClick={() => setSide('SELL')}
                    className={`rounded-xl py-2.5 text-sm font-semibold transition ${
                      side === 'SELL' ? 'btn-bear' : 'border border-white/10 bg-white/5 text-slate-400'
                    }`}
                  >
                    SELL
                  </button>
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Quantity (lots)
                </label>
                <input
                  type="number"
                  min="1"
                  required
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="input-3d font-mono"
                  placeholder="e.g. 1"
                />
                {selectedMeta?.lot_size && (
                  <p className="mt-1 text-[11px] text-slate-500">
                    1 lot = {selectedMeta.lot_size} units
                    {selectedMeta.premium && selectedMeta.premium !== selectedMeta.price
                      ? ` • premium ₹${formatNum(selectedMeta.premium)}/unit`
                      : ''}
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={submitting || !selectedSymbol}
                className={`w-full rounded-xl py-3 text-sm font-bold disabled:opacity-40 ${
                  side === 'BUY' ? 'btn-bull' : 'btn-bear'
                }`}
              >
                {submitting ? 'Placing…' : `${side} ${selectedSymbol || 'contract'} × ${quantity || 0}`}
              </button>
            </form>

            {error && (
              <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
                {error}
              </div>
            )}
            <OrderResultCard result={result} />

            <div className="mt-5 rounded-xl border border-white/5 bg-white/[0.02] p-3 text-[11px] leading-relaxed text-slate-500">
              F&O prices are <span className="text-slate-300">simulated</span>: options via Black-Scholes (synthetic IV
              smile) and futures via an annualised carry basis, both derived from the underlying's live spot each
              refresh. Fees use F&O STT rates (0.0125% futures / 0.0625% options on sell).
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

export default FOPage