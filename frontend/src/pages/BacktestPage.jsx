import { useState } from 'react'
import PageLayout from '../components/common/PageLayout'
import axiosClient from '../api/axiosClient'

function BacktestPage() {
  const [ticker, setTicker] = useState('RELIANCE')
  const [years, setYears] = useState(2)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [wfoResult, setWfoResult] = useState(null)
  const [error, setError] = useState('')

  const runBacktest = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    setWfoResult(null)
    try {
      const { data } = await axiosClient.post('/backtest/run', null, {
        params: { ticker, years },
      })
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Backtest failed')
    } finally {
      setLoading(false)
    }
  }

  const runWalkForward = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setWfoResult(null)
    try {
      const { data } = await axiosClient.post('/backtest/walk-forward', null, {
        params: { ticker },
      })
      setWfoResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Walk-forward failed')
    } finally {
      setLoading(false)
    }
  }

  const equityData = result?.equity_curve?.values || []
  return (
    <PageLayout>
      <div className="animate-rise space-y-8">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="font-display text-3xl font-bold tracking-tight text-white">
              Backtest &amp; Walk-Forward
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Validate strategy performance before going live.
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="glass-deep card-3d glow-violet rounded-2xl p-6">
          <form onSubmit={runBacktest} className="flex flex-wrap gap-4 items-end">
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">Ticker</label>
              <input type="text" value={ticker} onChange={(e) => setTicker(e.target.value)} className="input-3d" placeholder="RELIANCE" />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">Years</label>
              <input type="number" value={years} onChange={(e) => setYears(Number(e.target.value))} className="input-3d" min={1} max={5} />
            </div>
            <button type="submit" disabled={loading} className="btn-primary rounded-xl px-6 py-2.5 text-sm">
              {loading ? 'Running…' : 'Run Backtest'}
            </button>
          </form>
          <form onSubmit={runWalkForward} className="mt-4 flex flex-wrap gap-4 items-end">
            <button type="submit" disabled={loading} className="btn-ghost rounded-xl px-6 py-2.5 text-sm font-semibold">
              Run Walk-Forward
            </button>
          </form>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            {error}
          </div>
        )}

        {/* Backtest Result */}
        {result && (
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="glass rounded-2xl p-6">
              <h3 className="font-display text-lg font-semibold text-white mb-4">Standard Backtest</h3>
              {result.status === 'FAILED' ? (
                <p className="text-sm text-rose-300">{result.error_message || 'The backtest could not be completed.'}</p>
              ) : (
                <>
                  <div className="space-y-3">
                    <StatBlock label="Sharpe" value={result.sharpe?.toFixed(2)} />
                    <StatBlock label="CAGR" value={`${(result.cagr * 100)?.toFixed(1)}%`} />
                    <StatBlock label="Max Drawdown" value={`${(result.max_drawdown * 100)?.toFixed(1)}%`} />
                    <StatBlock label="Win Rate" value={`${(result.win_rate * 100)?.toFixed(1)}%`} />
                    <StatBlock label="Total Trades" value={result.total_trades} />
                    <StatBlock label="Final Equity" value={`₹${result.final_equity?.toLocaleString('en-IN', {maximumFractionDigits: 0})}`} />
                  </div>
                  {result.total_trades === 0 && (
                    <p className="mt-4 text-xs text-amber-300">
                      No trades were generated in this period. Check the strategy conditions and available historical data.
                    </p>
                  )}
                </>
              )}
            </div>
            {result.status !== 'FAILED' && equityData.length > 1 && (
              <div className="glass rounded-2xl p-6 lg:col-span-2">
                <h3 className="font-display text-lg font-semibold text-white mb-4">Equity Curve</h3>
                <div className="h-64">
                  <svg viewBox={`0 0 ${equityData.length * 8} 200`} className="w-full h-full">
                    <polyline
                      fill="none" stroke="#22d3ee" strokeWidth="2"
                      points={equityData.map((v, i) => `${i * 8},${200 - ((v - Math.min(...equityData)) / (Math.max(...equityData) - Math.min(...equityData))) * 180}`).join(' ')}
                    />
                  </svg>
                </div>
              </div>
            )}
          </div>
        )}

        {/* WFO Result */}
        {wfoResult && (
          <div className="glass rounded-2xl p-6">
            <h3 className="font-display text-lg font-semibold text-white mb-4">Walk-Forward Results</h3>
            <div className="grid gap-4 lg:grid-cols-4">
              <StatBlock label="Efficiency Ratio" value={wfoResult.efficiency_ratio?.toFixed(3)} />
              <StatBlock label="OOS Sharpe" value={wfoResult.oos_sharpe?.toFixed(2)} />
              <StatBlock label="IS Sharpe" value={wfoResult.is_sharpe?.toFixed(2)} />
              <StatBlock label="Windows" value={wfoResult.num_windows} />
            </div>
            {wfoResult.window_results && wfoResult.window_results.length > 0 && (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-slate-400">
                      <th className="text-left pb-2">Train</th>
                      <th className="text-left pb-2">Test</th>
                      <th className="text-right pb-2">IS Sharpe</th>
                      <th className="text-right pb-2">OOS Sharpe</th>
                      <th className="text-right pb-2">ER</th>
                    </tr>
                  </thead>
                  <tbody>
                    {wfoResult.window_results.map((w, i) => (
                      <tr key={i} className="border-t border-white/5">
                        <td className="py-2">{w.train_start}</td>
                        <td className="py-2">{w.test_end}</td>
                        <td className="text-right py-2">{w.is_sharpe?.toFixed(2)}</td>
                        <td className="text-right py-2">{w.oos_sharpe?.toFixed(2)}</td>
                        <td className="text-right py-2">{w.efficiency_ratio?.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </PageLayout>
  )
}

function StatBlock({ label, value }) {
  return (
    <div className="glass rounded-xl p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 font-display text-lg font-bold text-white">{value}</p>
    </div>
  )
}

export default BacktestPage