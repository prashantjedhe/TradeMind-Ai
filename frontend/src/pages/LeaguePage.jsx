import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/common/PageLayout'

function LeaguePage() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('leagues')
  const [leagues, setLeagues] = useState([])
  const [myEntries, setMyEntries] = useState([])
  const [leaderboard, setLeaderboard] = useState([])
  const [badges, setBadges] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const token = localStorage.getItem('trademind-auth') ? JSON.parse(localStorage.getItem('trademind-auth'))?.accessToken : null
  const headers = token ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }

  const fetchLeagues = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/v1/league', { headers })
      const data = await res.json()
      setLeagues(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchMyLeagues = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/v1/league/my', { headers })
      const data = await res.json()
      setMyEntries(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const joinLeague = async (leagueId) => {
    try {
      await fetch(`/api/v1/league/${leagueId}/join`, { method: 'POST', headers })
      fetchMyLeagues()
    } catch (err) {
      setError(err.message)
    }
  }

  const fetchLeaderboard = async (leagueId) => {
    try {
      const res = await fetch(`/api/v1/league/${leagueId}/leaderboard`, { headers })
      const data = await res.json()
      setLeaderboard(data)
    } catch (err) {
      setError(err.message)
    }
  }

  const fetchBadges = async (leagueId) => {
    try {
      const res = await fetch(`/api/v1/league/${leagueId}/badges`, { headers })
      const data = await res.json()
      setBadges(data)
    } catch (err) {
      setError(err.message)
    }
  }

  const createLeague = async (e) => {
    e.preventDefault()
    const name = e.target.name.value
    const duration = parseInt(e.target.duration.value) || 30
    setLoading(true)
    try {
      const res = await fetch('/api/v1/league', {
        method: 'POST',
        headers,
        body: JSON.stringify({ name, duration_days: duration })
      })
      const data = await res.json()
      fetchLeagues()
      e.target.reset()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageLayout>
      <div className="animate-rise space-y-8">
        <h1 className="font-display text-3xl font-bold tracking-tight text-white">
          League &amp; Competitions
        </h1>
        <p className="text-sm text-slate-400">
          Compete with other traders on a Sharpe Ratio leaderboard.
        </p>

        {/* Tabs */}
        <div className="flex gap-2">
          {[
            { key: 'leagues', label: 'All Leagues' },
            { key: 'my', label: 'My Entries' },
            { key: 'create', label: 'Create' },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => { setActiveTab(tab.key); if (tab.key === 'leagues') fetchLeagues(); if (tab.key === 'my') fetchMyLeagues(); }}
              className={`rounded-xl px-4 py-2 text-sm font-semibold ${activeTab === tab.key ? 'bg-cyan-500/20 text-cyan-300' : 'bg-white/5 text-slate-400'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {error && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            {error}
          </div>
        )}

        {/* Create Form */}
        {activeTab === 'create' && (
          <form onSubmit={createLeague} className="glass-deep card-3d glow-violet rounded-2xl p-6 flex flex-wrap gap-4 items-end">
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">Name</label>
              <input name="name" required className="input-3d" placeholder="My Challenge" />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">Duration (days)</label>
              <input name="duration" type="number" defaultValue={30} className="input-3d" min={7} max={90} />
            </div>
            <button type="submit" disabled={loading} className="btn-primary rounded-xl px-6 py-2.5 text-sm">
              Create League
            </button>
          </form>
        )}

        {/* All Leagues */}
        {activeTab === 'leagues' && (
          <div className="space-y-4">
            {loading ? <p className="text-slate-400">Loading…</p> :
              leagues.map(league => (
                <div key={league.id} className="glass rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h3 className="font-display text-lg font-semibold text-white">{league.name}</h3>
                    <p className="text-xs text-slate-500">Ends: {new Date(league.end_date).toLocaleDateString('en-IN')}</p>
                    <p className="text-xs text-slate-500">Initial: ₹{league.initial_balance?.toLocaleString('en-IN', {maximumFractionDigits: 0})}</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => joinLeague(league.id)} className="btn-primary rounded-xl px-4 py-2 text-sm">Join</button>
                    <button onClick={() => { fetchLeaderboard(league.id); fetchBadges(league.id) }} className="btn-ghost rounded-xl px-4 py-2 text-sm font-semibold">Leaderboard</button>
                  </div>
                </div>
              ))
            }
          </div>
        )}

        {/* My Entries */}
        {activeTab === 'my' && (
          <div className="space-y-4">
            {myEntries.map(entry => (
              <div key={entry.id} className="glass rounded-2xl p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-display text-lg font-semibold text-white">Rank #{entry.final_rank || '—'}</p>
                    <p className="text-xs text-slate-500">Sharpe: {entry.final_sharpe?.toFixed(2)} | Return: {(entry.final_return_pct * 100)?.toFixed(1)}%</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Leaderboard */}
        {leaderboard.length > 0 && (
          <div className="glass rounded-2xl p-6">
            <h3 className="font-display text-lg font-semibold text-white mb-4">Leaderboard</h3>
            <div className="space-y-2">
              {leaderboard.map(entry => (
                <div key={entry.user_id} className="flex items-center justify-between rounded-xl border border-white/8 bg-white/[0.03] px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="font-display text-lg font-bold text-cyan-400">#{entry.rank}</span>
                    <span className="text-sm text-slate-300">{entry.user_id?.slice(0, 8)}…</span>
                  </div>
                  <div className="flex gap-4 text-sm">
                    <span className="text-slate-400">Sharpe: {entry.sharpe?.toFixed(2)}</span>
                    <span className="text-slate-400">Trades: {entry.trades}</span>
                    <span className="text-slate-400">P&L: ₹{entry.pnl?.toLocaleString('en-IN', {maximumFractionDigits: 0})}</span>
                  </div>
                </div>
              ))}
            </div>
            {badges.length > 0 && (
              <div className="mt-6">
                <h4 className="text-sm font-semibold text-slate-400 mb-2">Badges</h4>
                <div className="flex gap-2 flex-wrap">
                  {badges.map((b, i) => (
                    <span key={i} className="chip chip-bull">🏅 {b.badge_type}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </PageLayout>
  )
}

export default LeaguePage