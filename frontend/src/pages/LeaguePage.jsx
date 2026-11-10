import { useState, useEffect, useCallback } from 'react'
import PageLayout from '../components/common/PageLayout'
import {
  getAllLeagues,
  getMyLeagues,
  getMyBadges,
  getLeagueLeaderboard,
  joinLeague as apiJoinLeague,
  createLeague as apiCreateLeague,
} from '../api/leagueApi'

// Badge emoji and styling map
const BADGE_ICONS = {
  'Top Trader': '🥇',
  'Drawdown Master': '🛡️',
  'Consistent Performer': '📈',
  'News Ninja': '📰',
  'Marathon Bet': '🏃',
  'First Win': '🎯',
}

const BADGE_COLORS = {
  'Top Trader': 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  'Drawdown Master': 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  'Consistent Performer': 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  'News Ninja': 'bg-violet-500/20 text-violet-300 border-violet-500/30',
  'Marathon Bet': 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  'First Win': 'bg-rose-500/20 text-rose-300 border-rose-500/30',
}

function formatINR(value) {
  const n = Number(value)
  if (isNaN(n)) return '₹0'
  const abs = Math.abs(n)
  const formatted = abs.toLocaleString('en-IN', { maximumFractionDigits: 0 })
  return n < 0 ? `-₹${formatted}` : `₹${formatted}`
}

function formatPct(value) {
  const n = Number(value) * 100
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

function RankBadge({ rank }) {
  if (rank === 1) return <span className="text-2xl" title="Rank 1">🥇</span>
  if (rank === 2) return <span className="text-2xl" title="Rank 2">🥈</span>
  if (rank === 3) return <span className="text-2xl" title="Rank 3">🥉</span>
  return (
    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/10 font-display text-xs font-bold text-slate-300">
      #{rank}
    </span>
  )
}

function LeaderboardTable({ leaderboard }) {
  if (leaderboard.length === 0) {
    return (
      <div className="flex h-32 flex-col items-center justify-center text-center">
        <span className="mb-2 text-3xl">🏆</span>
        <p className="text-sm text-slate-500">No participants yet. Join and trade to appear here!</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            <th className="pb-3 pr-4">Rank</th>
            <th className="pb-3 pr-4">Trader</th>
            <th className="pb-3 pr-4">Sharpe Ratio</th>
            <th className="pb-3 pr-4">Return</th>
            <th className="pb-3 pr-4">Realised P&L</th>
            <th className="pb-3 pr-4">Trades</th>
            <th className="pb-3 pr-4">Win Rate</th>
            <th className="pb-3">Badges</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {leaderboard.map((entry) => (
            <tr key={entry.user_id} className="group hover:bg-white/[0.02]">
              <td className="py-3 pr-4">
                <RankBadge rank={entry.rank} />
              </td>
              <td className="py-3 pr-4">
                <span className="font-semibold text-white">{entry.username}</span>
              </td>
              <td className="py-3 pr-4">
                <span
                  className={`font-mono font-semibold ${
                    entry.sharpe >= 1
                      ? 'text-emerald-400'
                      : entry.sharpe >= 0
                      ? 'text-cyan-300'
                      : 'text-rose-400'
                  }`}
                >
                  {Number(entry.sharpe).toFixed(2)}
                </span>
              </td>
              <td className="py-3 pr-4">
                <span
                  className={`font-mono ${
                    entry.return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {formatPct(entry.return_pct)}
                </span>
              </td>
              <td className="py-3 pr-4">
                <span
                  className={`font-mono ${
                    entry.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {formatINR(entry.pnl)}
                </span>
              </td>
              <td className="py-3 pr-4 font-mono text-slate-300">{entry.trades}</td>
              <td className="py-3 pr-4 font-mono text-slate-300">
                {(Number(entry.win_rate) * 100).toFixed(0)}%
              </td>
              <td className="py-3">
                <div className="flex flex-wrap gap-1">
                  {(entry.badges || []).map((badge, i) => (
                    <span
                      key={i}
                      title={badge}
                      className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 text-[10px] font-semibold ${
                        BADGE_COLORS[badge] || 'border-white/20 bg-white/10 text-slate-300'
                      }`}
                    >
                      {BADGE_ICONS[badge] || '🏅'} {badge}
                    </span>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function LeaguePage() {
  const [activeTab, setActiveTab] = useState('leagues')
  const [leagues, setLeagues] = useState([])
  const [myEntries, setMyEntries] = useState([])
  const [myBadges, setMyBadges] = useState([])
  const [selectedLeague, setSelectedLeague] = useState(null)
  const [leaderboard, setLeaderboard] = useState([])
  const [loading, setLoading] = useState(false)
  const [leaderboardLoading, setLeaderboardLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const fetchLeagues = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await getAllLeagues()
      setLeagues(Array.isArray(res.data) ? res.data : [])
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load leagues.')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchMyLeagues = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [entriesRes, badgesRes] = await Promise.all([
        getMyLeagues(),
        getMyBadges(),
      ])
      setMyEntries(Array.isArray(entriesRes.data) ? entriesRes.data : [])
      setMyBadges(Array.isArray(badgesRes.data) ? badgesRes.data : [])
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load your league entries.')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchLeaderboard = useCallback(async (league) => {
    setLeaderboardLoading(true)
    setSelectedLeague(league)
    setLeaderboard([])
    try {
      const res = await getLeagueLeaderboard(league.id)
      setLeaderboard(Array.isArray(res.data) ? res.data : [])
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load leaderboard.')
    } finally {
      setLeaderboardLoading(false)
    }
  }, [])

  const joinLeague = async (leagueId) => {
    setError('')
    setSuccess('')
    try {
      await apiJoinLeague(leagueId)
      setSuccess('Joined league successfully! 🎉 Start paper trading to climb the leaderboard.')
      fetchLeagues()
      fetchMyLeagues()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to join league.')
    }
  }

  const handleCreateLeague = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    const name = e.target.name.value.trim()
    const description = e.target.description?.value?.trim() || null
    const duration = parseInt(e.target.duration.value) || 30
    const initialBalance = parseFloat(e.target.initial_balance.value) || 1000000

    if (!name) {
      setError('League name is required.')
      return
    }

    setLoading(true)
    try {
      const res = await apiCreateLeague({
        name,
        description,
        duration_days: duration,
        initial_balance: initialBalance,
      })
      setSuccess(`League "${res.data.name}" created! 🏆`)
      e.target.reset()
      fetchLeagues()
      setActiveTab('leagues')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create league.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'leagues') fetchLeagues()
    if (activeTab === 'my') fetchMyLeagues()
  }, [activeTab, fetchLeagues, fetchMyLeagues])

  const tabs = [
    { key: 'leagues', label: '🏆 All Leagues' },
    { key: 'my', label: '📋 My Entries & Badges' },
    { key: 'create', label: '➕ Create Competition' },
  ]

  const statusColors = {
    ACTIVE: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/30',
    COMPLETED: 'bg-slate-500/20 text-slate-400 ring-1 ring-slate-500/30',
    UPCOMING: 'bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/30',
  }

  return (
    <PageLayout>
      <div className="animate-rise space-y-8">
        {/* Header */}
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight text-white">
            League <span className="text-gradient-cyan">&amp; Competitions</span>
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Compete with other paper traders on a live Sharpe Ratio leaderboard. Earn badges,
            track performance, and rise to the top.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`rounded-xl px-4 py-2 text-sm font-semibold transition-all ${
                activeTab === tab.key
                  ? 'bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/40'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Alerts */}
        {error && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            ⚠️ {error}
          </div>
        )}
        {success && (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
            ✅ {success}
          </div>
        )}

        {/* ── Tab 1: All Leagues ── */}
        {activeTab === 'leagues' && (
          <div className="space-y-4">
            {loading ? (
              <div className="flex h-32 items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
              </div>
            ) : leagues.length === 0 ? (
              <div className="glass rounded-2xl p-12 text-center">
                <span className="mb-4 block text-5xl">🏆</span>
                <p className="text-slate-400">No leagues found. Create the first one!</p>
                <button
                  onClick={() => setActiveTab('create')}
                  className="btn-primary mt-4 rounded-xl px-6 py-2 text-sm"
                >
                  Create Competition
                </button>
              </div>
            ) : (
              leagues.map((league) => (
                <div
                  key={league.id}
                  className="glass rounded-2xl p-6 transition-all hover:border-white/15"
                >
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="font-display text-lg font-semibold text-white">
                          {league.name}
                        </h3>
                        <span
                          className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                            statusColors[league.status] || 'bg-white/10 text-slate-400'
                          }`}
                        >
                          {league.status}
                        </span>
                      </div>
                      {league.description && (
                        <p className="mt-1 text-sm text-slate-400">{league.description}</p>
                      )}
                      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
                        <span>
                          📅 Ends:{' '}
                          {new Date(league.end_date).toLocaleDateString('en-IN', {
                            day: '2-digit',
                            month: 'short',
                            year: 'numeric',
                          })}
                        </span>
                        <span>
                          💰 Capital: ₹
                          {Number(league.initial_balance).toLocaleString('en-IN', {
                            maximumFractionDigits: 0,
                          })}
                        </span>
                        <span>📊 Metric: {league.ranking_metric}</span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {league.status === 'ACTIVE' && (
                        <button
                          onClick={() => joinLeague(league.id)}
                          className="btn-primary rounded-xl px-4 py-2 text-sm"
                        >
                          Join
                        </button>
                      )}
                      <button
                        onClick={() => fetchLeaderboard(league)}
                        className="btn-ghost rounded-xl px-4 py-2 text-sm font-semibold"
                      >
                        Leaderboard
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}

            {/* Inline Leaderboard modal/panel */}
            {selectedLeague && (
              <div className="glass-deep card-3d rounded-2xl p-6">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h3 className="font-display text-lg font-semibold text-white">
                      🏅 {selectedLeague.name} — Leaderboard
                    </h3>
                    <p className="text-xs text-slate-500">
                      Ranked by annualized Sharpe Ratio computed from live paper trades
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setSelectedLeague(null)
                      setLeaderboard([])
                    }}
                    className="text-slate-500 hover:text-white"
                  >
                    ✕
                  </button>
                </div>
                {leaderboardLoading ? (
                  <div className="flex h-24 items-center justify-center">
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
                  </div>
                ) : (
                  <LeaderboardTable leaderboard={leaderboard} />
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Tab 2: My Entries & Badges ── */}
        {activeTab === 'my' && (
          <div className="space-y-6">
            {/* Badges showcase */}
            <div className="glass rounded-2xl p-6">
              <h3 className="mb-3 font-display text-base font-semibold text-white">
                Earned Badges ({myBadges.length})
              </h3>
              {myBadges.length === 0 ? (
                <p className="text-xs text-slate-500">
                  No badges earned yet. Complete trades and participate in leagues to unlock badges!
                </p>
              ) : (
                <div className="flex flex-wrap gap-3">
                  {myBadges.map((badge, i) => (
                    <div
                      key={i}
                      className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-semibold ${
                        BADGE_COLORS[badge.badge_type] ||
                        'border-white/20 bg-white/10 text-slate-300'
                      }`}
                    >
                      <span className="text-xl">{BADGE_ICONS[badge.badge_type] || '🏅'}</span>
                      <div>
                        <p>{badge.badge_type}</p>
                        <p className="text-[10px] font-normal opacity-75">{badge.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* My joined leagues */}
            {loading ? (
              <div className="flex h-32 items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
              </div>
            ) : myEntries.length === 0 ? (
              <div className="glass rounded-2xl p-12 text-center">
                <span className="mb-4 block text-5xl">📋</span>
                <p className="text-slate-400">You haven't entered any competitions yet.</p>
                <button
                  onClick={() => setActiveTab('leagues')}
                  className="btn-primary mt-4 rounded-xl px-6 py-2 text-sm"
                >
                  Browse Competitions
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {myEntries.map((entry) => (
                  <div key={entry.id} className="glass rounded-2xl p-6">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <div className="flex items-center gap-3">
                          <h3 className="font-display text-lg font-semibold text-white">
                            {entry.league_name}
                          </h3>
                          <span
                            className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase ${
                              statusColors[entry.league_status] ||
                              'bg-white/10 text-slate-400'
                            }`}
                          >
                            {entry.league_status}
                          </span>
                          {entry.final_rank && <RankBadge rank={entry.final_rank} />}
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          Joined on {new Date(entry.joined_at).toLocaleDateString('en-IN')}
                        </p>
                      </div>

                      <div className="grid grid-cols-3 gap-4 text-center sm:grid-cols-6">
                        <div>
                          <p className="text-[10px] text-slate-500">Sharpe</p>
                          <p
                            className={`font-mono text-sm font-bold ${
                              entry.final_sharpe >= 1
                                ? 'text-emerald-400'
                                : entry.final_sharpe >= 0
                                ? 'text-cyan-300'
                                : 'text-rose-400'
                            }`}
                          >
                            {Number(entry.final_sharpe).toFixed(2)}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-500">Return</p>
                          <p
                            className={`font-mono text-sm font-bold ${
                              entry.final_return_pct >= 0
                                ? 'text-emerald-400'
                                : 'text-rose-400'
                            }`}
                          >
                            {formatPct(entry.final_return_pct)}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-500">P&L</p>
                          <p
                            className={`font-mono text-sm font-bold ${
                              entry.final_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                            }`}
                          >
                            {formatINR(entry.final_pnl)}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-500">Trades</p>
                          <p className="font-mono text-sm font-bold text-white">
                            {entry.final_trades}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-500">Win Rate</p>
                          <p className="font-mono text-sm font-bold text-cyan-300">
                            {(Number(entry.final_win_rate) * 100).toFixed(0)}%
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-500">Max DD</p>
                          <p className="font-mono text-sm font-bold text-rose-400">
                            {(Number(entry.final_drawdown) * 100).toFixed(1)}%
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Tab 3: Create Competition ── */}
        {activeTab === 'create' && (
          <div className="glass-deep card-3d glow-violet rounded-2xl p-8">
            <h2 className="mb-6 font-display text-xl font-bold text-white">
              Create New Competition
            </h2>
            <form onSubmit={handleCreateLeague} className="space-y-5">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Competition Name *
                </label>
                <input
                  name="name"
                  required
                  className="input-3d w-full"
                  placeholder="e.g. NIFTY Momentum League"
                  maxLength={120}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Description (optional)
                </label>
                <textarea
                  name="description"
                  className="input-3d w-full resize-none"
                  placeholder="Describe competition rules, eligibility, or themes..."
                  rows={3}
                  maxLength={500}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Duration (days)
                  </label>
                  <input
                    name="duration"
                    type="number"
                    defaultValue={30}
                    className="input-3d w-full"
                    min={7}
                    max={90}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Virtual Capital (₹)
                  </label>
                  <input
                    name="initial_balance"
                    type="number"
                    defaultValue={1000000}
                    className="input-3d w-full"
                    min={100000}
                    step={100000}
                  />
                </div>
              </div>

              {/* Rules banner */}
              <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4 text-sm text-slate-400">
                <p className="mb-2 font-semibold text-cyan-300">How the League works</p>
                <ul className="space-y-1 text-xs">
                  <li>• Participants join and trade on the paper exchange during the league window</li>
                  <li>• Rankings evaluate risk-adjusted return (Sharpe Ratio) and win rate</li>
                  <li>• Badges awarded at completion: 🥇 Top Trader, 🛡️ Drawdown Master, 📈 Consistent Performer, 📰 News Ninja</li>
                  <li>• Automatic finalization at competition end date via scheduled background task</li>
                </ul>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn-primary rounded-xl px-8 py-3 text-sm"
              >
                {loading ? 'Creating Competition…' : '🏆 Create Competition'}
              </button>
            </form>
          </div>
        )}
      </div>
    </PageLayout>
  )
}

export default LeaguePage