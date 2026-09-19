import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCurrentUser } from '../api/authApi'
import { useAuthStore } from '../store/authStore'
import { getPortfolioSummary, getOrders } from '../api/orderApi'
import PageLayout from '../components/common/PageLayout'
import StatCard from '../components/common/StatCard'

function formatINR(value) {
  const n = Number(value)
  if (isNaN(n)) return '₹0'
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function ProfilePage() {
  const navigate = useNavigate()
  const setUser = useAuthStore((state) => state.setUser)

  const [user, setUserData] = useState(null)
  const [portfolio, setPortfolio] = useState(null)
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [meRes, portfolioRes, ordersRes] = await Promise.all([
          getCurrentUser(),
          getPortfolioSummary(),
          getOrders(),
        ])
        setUserData(meRes.data)
        setUser(meRes.data)
        setPortfolio(portfolioRes.data)
        setOrders(ordersRes.data)
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
        <div className="mx-auto h-12 w-12 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
      </div>
    )
  }

  const joined = user?.created_at ? new Date(user.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' }) : '—'
  const realised = portfolio?.total_realised_pnl ?? 0
  const wins = orders.filter((o) => o.side === 'SELL' && o.status === 'FILLED').length
  const trades = orders.filter((o) => o.status === 'FILLED').length

  return (
    <PageLayout>
      <div className="animate-rise mx-auto max-w-4xl space-y-8">
        {/* Header */}
        <div>
          <p className="chip chip-violet mb-2">Account</p>
          <h1 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Your <span className="text-gradient-cyan">Profile</span>
          </h1>
        </div>

        {/* Identity card */}
        <div className="glass-deep card-3d glow-cyan overflow-hidden rounded-3xl p-8">
          <div className="card-glow" />
          <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
            <div className="relative">
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-cyan-400/60 to-violet-500/60 blur-lg" />
              <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-white/20 bg-gradient-to-br from-cyan-500 to-violet-600 font-display text-3xl font-bold text-white">
                {(user?.username || 'U').slice(0, 1).toUpperCase()}
              </div>
            </div>
            <div className="text-center sm:text-left">
              <h2 className="font-display text-2xl font-bold text-white">{user?.username}</h2>
              <p className="text-sm text-slate-400">{user?.email}</p>
              <div className="mt-3 flex flex-wrap justify-center gap-2 sm:justify-start">
                <span className={`chip ${user?.is_active ? 'chip-bull' : 'chip-bear'}`}>
                  {user?.is_active ? '● Active' : '○ Inactive'}
                </span>
                <span className="chip chip-cyan">Member since {joined}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Virtual Balance"
            value={formatINR(user?.virtual_balance ?? 0)}
            icon="₹"
            tone="cyan"
            className="card-3d"
          />
          <StatCard
            label="Net Worth"
            value={formatINR(portfolio?.net_worth ?? user?.virtual_balance ?? 0)}
            icon="◈"
            tone="violet"
            className="card-3d"
          />
          <StatCard
            label="Realised P&L"
            value={formatINR(realised)}
            icon="↗"
            tone="bull"
            positive={Number(realised) >= 0}
            className="card-3d"
          />
          <StatCard
            label="Filled Trades"
            value={trades}
            sub={`${wins} sell exits`}
            icon="⇄"
            tone="bear"
            className="card-3d"
          />
        </div>

        {/* Account details */}
        <div className="glass rounded-2xl p-6">
          <h2 className="mb-4 font-display text-lg font-semibold text-white">Account Details</h2>
          <dl className="space-y-3">
            {[
              ['User ID', user?.id],
              ['Email', user?.email],
              ['Username', user?.username],
              ['Account Status', user?.is_active ? 'Active' : 'Inactive'],
              ['Starting Balance', formatINR(1000000)],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between rounded-xl border border-white/8 bg-white/[0.03] px-4 py-3">
                <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</dt>
                <dd className="font-mono text-sm text-slate-200">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </PageLayout>
  )
}

export default ProfilePage