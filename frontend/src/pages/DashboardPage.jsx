import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { AreaChart, Area, ResponsiveContainer, Tooltip } from 'recharts'
import { getCurrentUser } from '../api/authApi'
import { useAuthStore } from '../store/authStore'
import { getPortfolioSummary, getOrders } from '../api/orderApi'
import { getStrategies } from '../api/strategyApi'
import PageLayout from '../components/common/PageLayout'
import StatCard from '../components/common/StatCard'
import DashboardAdvisor from '../components/dashboard/DashboardAdvisor'

function formatINR(value) {
  const n = Number(value)
  if (isNaN(n)) return '₹0'
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function buildEquityData(orders, initialBalance = 1000000) {
  // Reconstruct a simple equity curve from filled orders' fee + turnover effects.
  let cash = initialBalance
  const rows = []
  const filled = orders
    .filter((o) => o.status === 'FILLED')
    .slice()
    .reverse()

  for (const o of filled) {
    const turnover = Number(o.executed_price) * Number(o.quantity)
    const fees = Number(o.total_fees || 0)
    if (o.side === 'BUY') cash -= turnover + fees
    else cash += turnover - fees
    rows.push({
      t: new Date(o.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }),
      equity: Math.round(cash * 100) / 100,
    })
  }

  if (rows.length === 0) {
    rows.push({ t: 'Start', equity: initialBalance })
  }
  return rows
}

function DashboardPage() {
  const navigate = useNavigate()
  const setUser = useAuthStore((state) => state.setUser)

  const [user, setUserData] = useState(null)
  const [portfolio, setPortfolio] = useState(null)
  const [orders, setOrders] = useState([])
  const [strategies, setStrategies] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [meRes, portfolioRes, ordersRes, strategiesRes] = await Promise.all([
          getCurrentUser(),
          getPortfolioSummary(),
          getOrders(),
          getStrategies(),
        ])
        setUserData(meRes.data)
        setUser(meRes.data)
        setPortfolio(portfolioRes.data)
        setOrders(ordersRes.data)
        setStrategies(strategiesRes.data)
      } catch {
        navigate('/login')
      } finally {
        setLoading(false)
      }
    }
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#05070f] text-white">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
          <p className="text-sm text-slate-400">Loading terminal…</p>
        </div>
      </div>
    )
  }

  const balance = portfolio?.virtual_balance ?? user?.virtual_balance ?? 0
  const netWorth = portfolio?.net_worth ?? balance
  const unrealised = portfolio?.total_unrealised_pnl ?? 0
  const realised = portfolio?.total_realised_pnl ?? 0
  const openPositions = portfolio?.positions ?? []
  const activeStrategies = strategies.filter((s) => s.status === 'ACTIVE').length
  const equityData = buildEquityData(orders, Number(balance) + Number(unrealised) - Number(realised))

  const heroUp = Number(netWorth) >= Number(balance)

  return (
    <PageLayout>
      <div className="animate-rise space-y-6">
        {/* Hero */}
        <div className="glass relative overflow-hidden rounded-2xl border border-white/10 bg-[#11171f] p-8">
          <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="chip chip-cyan mb-3">Paper Trading · NSE market data</p>
              <h1 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Welcome back,{' '}
                <span className="text-gradient-cyan">{user?.username || 'Trader'}</span>
              </h1>
              <p className="mt-2 max-w-lg text-sm text-slate-400">
                Portfolio overview and paper-trading activity, with your market tools close at hand.
              </p>
            </div>
            <div className="flex gap-3">
              <Link to="/trading" className="btn-primary rounded-xl px-6 py-3 text-sm">
                Trade Now
              </Link>
              <Link to="/strategies" className="btn-ghost rounded-xl px-6 py-3 text-sm font-semibold">
                Build Strategy
              </Link>
            </div>
          </div>

          <div className="relative mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="glass rounded-2xl p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Net Worth</p>
              <p className={`mt-1 font-display text-xl font-bold ${heroUp ? 'text-emerald-400' : 'text-rose-400'}`}>
                {formatINR(netWorth)}
              </p>
            </div>
            <div className="glass rounded-2xl p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Cash Balance</p>
              <p className="mt-1 font-display text-xl font-bold text-white">{formatINR(balance)}</p>
            </div>
            <div className="glass rounded-2xl p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Unrealised P&amp;L</p>
              <p className={`mt-1 font-display text-xl font-bold ${Number(unrealised) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {formatINR(unrealised)}
              </p>
            </div>
            <div className="glass rounded-2xl p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Lifetime Realised</p>
              <p className={`mt-1 font-display text-xl font-bold ${Number(realised) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {formatINR(realised)}
              </p>
            </div>
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Open Positions"
            value={openPositions.length}
            sub="currently held"
            icon="◈"
            tone="cyan"
          />
          <StatCard
            label="Total Trades"
            value={orders.length}
            sub="all time"
            icon="⇄"
            tone="violet"
          />
          <StatCard
            label="Strategies"
            value={strategies.length}
            sub={`${activeStrategies} active`}
            icon="⚡"
            tone="bull"
          />
          <StatCard
            label="Trading Mode"
            value="PAPER"
            sub="NSE instruments"
            icon="◉"
            tone="bull"
            positive={true}
          />
        </div>

        <DashboardAdvisor />

        {/* Equity + positions */}
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="glass rounded-2xl p-6 lg:col-span-2">
            <div className="card-glow" />
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-white">Equity Curve</h2>
              <span className="chip chip-neutral">Estimated from filled orders</span>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={equityData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#4b85c5" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#4b85c5" stopOpacity={0.015} />
                    </linearGradient>
                  </defs>
                  <Tooltip
                    contentStyle={{
                      background: '#0a0e1a',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                    labelStyle={{ color: '#94a3b8' }}
                    formatter={(value) => [formatINR(value), 'Equity']}
                  />
                  <Area
                    type="monotone"
                    dataKey="equity"
                    stroke="#4b85c5"
                    strokeWidth={2}
                    fill="url(#equityFill)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Positions */}
          <div className="glass rounded-2xl p-6">
            <div className="card-glow" />
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-white">Open Positions</h2>
              <Link to="/trading" className="text-xs font-semibold text-cyan-300 hover:text-cyan-200">
                View all →
              </Link>
            </div>
            {openPositions.length === 0 ? (
              <div className="flex h-48 flex-col items-center justify-center text-center">
                <span className="mb-2 h-1.5 w-8 rounded-full bg-slate-700" aria-hidden="true" />
                <p className="text-sm text-slate-500">No open positions</p>
                <p className="mt-1 text-[11px] text-slate-600">Place your first trade to get started.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {openPositions.slice(0, 5).map((p) => (
                  <div key={p.id} className="flex items-center justify-between rounded-lg border border-white/8 bg-white/[0.03] px-3.5 py-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{p.ticker.replace('.NS', '')}</p>
                      <p className="text-[10px] text-slate-500">
                        {p.quantity} shares @ ₹{p.avg_entry_price}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-xs text-slate-300">
                        {p.current_price ? `₹${p.current_price}` : '—'}
                      </p>
                      <p className={`text-xs font-semibold ${Number(p.unrealised_pnl) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {p.unrealised_pnl ? formatINR(p.unrealised_pnl) : '—'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Recent strategies teaser */}
        {strategies.length > 0 && (
          <div className="glass rounded-2xl p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-white">Your Strategies</h2>
              <Link to="/strategies" className="text-xs font-semibold text-cyan-300 hover:text-cyan-200">
                Open builder →
              </Link>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {strategies.slice(0, 3).map((s) => (
                <div key={s.id} className="rounded-lg border border-white/8 bg-white/[0.03] p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-white">{s.name}</p>
                    <span
                      className={`chip ${
                        s.status === 'ACTIVE'
                          ? 'chip-bull'
                          : s.status === 'PAUSED'
                            ? 'chip-gold'
                            : 'chip-neutral'
                      }`}
                    >
                      {s.status}
                    </span>
                  </div>
                  <p className="mt-2 font-mono text-xs text-cyan-300">{s.ticker}</p>
                  <p className="mt-1 text-[11px] text-slate-500">
                    {s.timeframe} • {s.action_side} {s.action_quantity}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  )
}

export default DashboardPage