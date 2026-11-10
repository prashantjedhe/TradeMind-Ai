import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DndContext,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  SortableContext,
  verticalListSortingStrategy,
  arrayMove,
  sortableKeyboardCoordinates,
} from '@dnd-kit/sortable'
import PageLayout from '../components/common/PageLayout'
import StatCard from '../components/common/StatCard'
import { SortableConditionRow } from '../components/strategy/ConditionRow'
import {
  createStrategy,
  getStrategies,
  getStrategyTemplates,
  activateStrategy,
  pauseStrategy,
  deleteStrategy,
} from '../api/strategyApi'
import { runDraftStrategyBacktest, runStrategyBacktest, runStrategyWalkForward } from '../api/backtestApi'
import { getWatchlist } from '../api/marketApi'

function StrategyDropZone({ children }) {
  return (
    <div className="flex min-h-[120px] flex-col gap-2.5 rounded-2xl border-2 border-dashed border-white/10 bg-white/[0.02] p-3 transition-all">
      {children}
    </div>
  )
}

const EMPTY_CONDITION = {
  left: { indicator: 'RSI', params: { period: 14 } },
  operator: '<',
  right: 30,
}

const EMPTY_OPTION_LEG = {
  side: 'BUY',
  option_type: 'CE',
  expiry_type: 'WEEKLY',
  strike_criteria: 'ATM',
  strike_offset: 0,
  quantity_lots: 1,
}

function OptionLegEditor({ legs, onChange }) {
  const update = (key, patch) => onChange(legs.map((leg) => (leg.key === key ? { ...leg, ...patch } : leg)))
  const add = () => onChange([...legs, { ...EMPTY_OPTION_LEG, key: `leg-${Date.now()}` }])
  return (
    <div className="space-y-3">
      {legs.map((leg, index) => (
        <div key={leg.key} className="rounded-xl border border-white/10 bg-black/20 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold text-white">Leg {index + 1}</span>
            {legs.length > 1 && <button type="button" onClick={() => onChange(legs.filter((item) => item.key !== leg.key))} className="text-xs text-rose-300">Remove</button>}
          </div>
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {[
              ['side', 'Side', ['BUY', 'SELL']],
              ['option_type', 'Type', ['CE', 'PE']],
              ['expiry_type', 'Expiry', ['WEEKLY', 'NEXT_WEEKLY', 'MONTHLY', 'NEXT_MONTHLY']],
              ['strike_criteria', 'Strike', ['ATM', 'ITM', 'OTM', 'STRIKE', 'PREMIUM']],
            ].map(([field, label, options]) => (
              <label key={field} className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {label}
                <select value={leg[field]} onChange={(e) => update(leg.key, { [field]: e.target.value })} className="input-3d text-xs">
                  {options.map((option) => <option key={option} value={option}>{option.replace('_', '-')}</option>)}
                </select>
              </label>
            ))}
            <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Offset / selection
              <input type="number" value={leg.strike_offset} onChange={(e) => update(leg.key, { strike_offset: Number(e.target.value) })} className="input-3d font-mono text-xs" />
            </label>
            <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Lot quantity
              <input type="number" min="1" value={leg.quantity_lots} onChange={(e) => update(leg.key, { quantity_lots: Math.max(1, Number(e.target.value)) })} className="input-3d font-mono text-xs" />
            </label>
          </div>
        </div>
      ))}
      <button type="button" onClick={add} className="btn-ghost rounded-lg px-3.5 py-2 text-xs font-semibold">＋ Add leg</button>
    </div>
  )
}

function ConditionBuilder({ conditions, logic, onLogicChange, onConditionsChange }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  const handleDragEnd = (event) => {
    const { active, over } = event
    if (over && active.id !== over.id) {
      const oldIndex = conditions.findIndex((c) => c.key === active.id)
      const newIndex = conditions.findIndex((c) => c.key === over.id)
      onConditionsChange(arrayMove(conditions, oldIndex, newIndex))
    }
  }

  const handleUpdate = (key, next) => {
    onConditionsChange(conditions.map((c) => (c.key === key ? { ...c, ...next } : c)))
  }

  const handleRemove = (key) => {
    onConditionsChange(conditions.filter((c) => c.key !== key))
  }

  const addCondition = () => {
    onConditionsChange([...conditions, { key: `c-${Date.now()}`, ...EMPTY_CONDITION }])
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Combine conditions with
          </span>
          <div className="flex rounded-lg border border-white/10 bg-black/30 p-0.5">
            {['AND', 'OR'].map((op) => (
              <button
                key={op}
                type="button"
                onClick={() => onLogicChange(op)}
                className={`rounded-md px-3 py-1 text-xs font-bold transition ${
                  logic === op
                    ? 'bg-gradient-to-r from-cyan-500 to-violet-600 text-white shadow-lg'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {op}
              </button>
            ))}
          </div>
        </div>
        <button
          type="button"
          onClick={addCondition}
          className="btn-ghost rounded-lg px-3.5 py-2 text-xs font-semibold"
        >
          ＋ Add Condition
        </button>
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={conditions.map((c) => c.key)} strategy={verticalListSortingStrategy}>
          <StrategyDropZone>
            {conditions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <span className="mb-2 text-2xl text-slate-600">⚡</span>
                <p className="text-sm text-slate-500">Drop conditions here to build your strategy</p>
                <p className="mt-1 text-[11px] text-slate-600">
                  or click <span className="text-cyan-400">＋ Add Condition</span>
                </p>
              </div>
            ) : (
              conditions.map((condition, index) => (
                <SortableConditionRow
                  key={condition.key}
                  id={condition.key}
                  index={index}
                  condition={condition}
                  onUpdate={(next) => handleUpdate(condition.key, next)}
                  onRemove={() => handleRemove(condition.key)}
                />
              ))
            )}
          </StrategyDropZone>
        </SortableContext>
      </DndContext>
    </div>
  )
}

function ActionEditor({ action, onChange }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="action-side" className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Action
        </label>
        <div className="flex rounded-lg border border-white/10 bg-black/30 p-0.5">
          {['BUY', 'SELL'].map((s) => (
            <button
              key={s}
              type="button"
              id={`action-${s.toLowerCase()}`}
              onClick={() => onChange({ ...action, side: s })}
              className={`flex-1 rounded-md px-3 py-1.5 text-xs font-bold transition ${
                action.side === s
                  ? s === 'BUY'
                    ? 'bg-emerald-500 text-white shadow-[0_4px_16px_-4px_rgba(16,185,129,0.6)]'
                    : 'bg-rose-500 text-white shadow-[0_4px_16px_-4px_rgba(239,68,68,0.6)]'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="action-order-type" className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Order Type
        </label>
        <select
          id="action-order-type"
          value={action.order_type}
          onChange={(e) => onChange({ ...action, order_type: e.target.value })}
          className="input-3d"
        >
          <option value="MARKET">MARKET</option>
          <option value="LIMIT">LIMIT</option>
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="action-qty" className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Quantity
        </label>
        <input
          id="action-qty"
          type="number"
          min={1}
          value={action.quantity}
          onChange={(e) => onChange({ ...action, quantity: Number(e.target.value) })}
          className="input-3d font-mono"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="action-settlement" className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Settlement
        </label>
        <select
          id="action-settlement"
          value={action.settlement_type}
          onChange={(e) => onChange({ ...action, settlement_type: e.target.value })}
          className="input-3d"
        >
          <option value="INTRADAY">INTRADAY</option>
          <option value="DELIVERY">DELIVERY</option>
        </select>
      </div>

      {action.order_type === 'LIMIT' && (
        <div className="col-span-2 flex flex-col gap-1">
          <label htmlFor="action-limit" className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Limit Price (₹)
          </label>
          <input
            id="action-limit"
            type="number"
            step="0.01"
            min="0.01"
            value={action.limit_price ?? ''}
            onChange={(e) => onChange({ ...action, limit_price: Number(e.target.value) })}
            className="input-3d font-mono"
            placeholder="e.g. 2450.00"
          />
        </div>
      )}
    </div>
  )
}

function Metric({ label, value, tone = 'text-white' }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 font-mono text-base font-bold ${tone}`}>{value}</p>
    </div>
  )
}

function BacktestModal({ strategy, onClose, draft = false, onCompleted }) {
  const [years, setYears] = useState(2)
  const [result, setResult] = useState(null)
  const [walkForward, setWalkForward] = useState(null)
  const [running, setRunning] = useState('')
  const [error, setError] = useState('')

  const runStandard = async () => {
    setRunning('standard')
    setError('')
    try {
      const { data } = await (draft ? runDraftStrategyBacktest(strategy, years) : runStrategyBacktest(strategy, years))
      setResult(data)
      onCompleted?.()
    } catch (err) {
      setError(err.response?.data?.detail || 'Backtest could not be completed.')
    } finally {
      setRunning('')
    }
  }

  const runWfo = async () => {
    setRunning('wfo')
    setError('')
    try {
      const { data } = await runStrategyWalkForward(strategy)
      setWalkForward(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Walk-forward analysis could not be completed.')
    } finally {
      setRunning('')
    }
  }

  const equityValues = result?.equity_curve?.values || []
  const minEquity = Math.min(...equityValues)
  const maxEquity = Math.max(...equityValues)
  const equityRange = maxEquity - minEquity || 1
  const equityPoints = equityValues
    .map((value, index) => `${index * 8},${190 - ((value - minEquity) / equityRange) * 170}`)
    .join(' ')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="glass glow-violet max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-2xl p-6 shadow-2xl">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="chip chip-violet mb-2">Historical replay</p>
            <h2 className="font-display text-xl font-bold text-white">
              Backtest: <span className="text-cyan-300">{strategy.name}</span>
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              {strategy.ticker} · {strategy.timeframe} · market fills use next-bar execution with slippage and fees
            </p>
          </div>
          <button type="button" onClick={onClose} className="btn-ghost rounded-lg px-3 py-1.5 text-lg" aria-label="Close backtest">
            ×
          </button>
        </div>

        <div className="mb-5 flex flex-wrap items-end gap-3 rounded-xl border border-white/8 bg-black/20 p-4">
          <div>
            <label htmlFor="backtest-years" className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Historical period
            </label>
            <select id="backtest-years" value={years} onChange={(e) => setYears(Number(e.target.value))} className="input-3d">
              <option value={1}>1 year</option>
              <option value={2}>2 years</option>
              <option value={3}>3 years</option>
              <option value={5}>5 years</option>
            </select>
          </div>
          <button type="button" onClick={runStandard} disabled={Boolean(running)} className="btn-primary rounded-xl px-5 py-2.5 text-sm">
            {running === 'standard' ? 'Running…' : 'Run Backtest'}
          </button>
          {!draft && (
            <button type="button" onClick={runWfo} disabled={Boolean(running)} className="btn-ghost rounded-xl px-5 py-2.5 text-sm font-semibold">
              {running === 'wfo' ? 'Running…' : 'Run Walk-Forward'}
            </button>
          )}
        </div>

        {error && <div className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{error}</div>}

        {result && (
          <div className="space-y-4">
            {result.status === 'FAILED' ? (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
                {result.error_message || 'The backtest could not be completed.'}
              </div>
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
                  <Metric label="CAGR" value={`${(result.cagr * 100).toFixed(1)}%`} tone={result.cagr >= 0 ? 'text-emerald-300' : 'text-rose-300'} />
                  <Metric label="Sharpe" value={result.sharpe.toFixed(2)} tone={result.sharpe >= 1 ? 'text-emerald-300' : 'text-amber-300'} />
                  <Metric label="Max drawdown" value={`${(result.max_drawdown * 100).toFixed(1)}%`} tone="text-rose-300" />
                  <Metric label="Win rate" value={`${(result.win_rate * 100).toFixed(1)}%`} />
                  <Metric label="Trades" value={result.total_trades} />
                  <Metric
                    label="Profit / Loss"
                    value={`₹${result.total_pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
                    tone={result.total_pnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}
                  />
                  <Metric label="Final equity" value={`₹${result.final_equity.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} />
                </div>
                {result.total_trades === 0 && (
                  <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
                    The run completed, but no trades were generated. Review the strategy conditions and historical data for this period.
                  </p>
                )}
              </>
            )}
            {result.status !== 'FAILED' && equityValues.length > 1 && (
              <div className="rounded-xl border border-white/8 bg-black/20 p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-white">Equity curve</h3>
                  <span className="text-[10px] text-slate-500">
                    {result.start_date.slice(0, 10)} → {result.end_date.slice(0, 10)}
                  </span>
                </div>
                <div className="h-48 overflow-x-auto">
                  <svg viewBox={`0 0 ${Math.max(equityValues.length * 8, 640)} 200`} className="h-full min-w-full">
                    <polyline fill="none" stroke="#22d3ee" strokeWidth="2" points={equityPoints} />
                  </svg>
                </div>
              </div>
            )}
          </div>
        )}

        {walkForward && (
          <div className="mt-5 rounded-xl border border-white/8 bg-black/20 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-white">Walk-forward validation</h3>
              <span className={`chip ${walkForward.efficiency_ratio >= 0.7 ? 'chip-bull' : 'chip-gold'}`}>
                ER {walkForward.efficiency_ratio.toFixed(2)}
              </span>
            </div>
            <div className="mb-4 grid gap-3 sm:grid-cols-3">
              <Metric label="In-sample Sharpe" value={walkForward.is_sharpe.toFixed(2)} />
              <Metric label="Out-of-sample Sharpe" value={walkForward.oos_sharpe.toFixed(2)} />
              <Metric label="Windows" value={walkForward.num_windows} />
            </div>
            {walkForward.window_results?.length > 0 && (
              <div className="overflow-x-auto">
                <table className="table-3d w-full text-xs">
                  <thead><tr><th>Train start</th><th>Test end</th><th>IS Sharpe</th><th>OOS Sharpe</th><th>ER</th></tr></thead>
                  <tbody>
                    {walkForward.window_results.map((window, index) => (
                      <tr key={`${window.train_start}-${index}`}>
                        <td>{window.train_start}</td>
                        <td>{window.test_end}</td>
                        <td>{window.is_sharpe?.toFixed(2)}</td>
                        <td>{window.oos_sharpe?.toFixed(2)}</td>
                        <td>{window.efficiency_ratio?.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function StrategyList({ strategies, onRefresh }) {
  const [backtestStrategy, setBacktestStrategy] = useState(null)

  const handleToggle = async (strategy) => {
    if (strategy.status === 'ACTIVE') {
      await pauseStrategy(strategy.id)
    } else {
      await activateStrategy(strategy.id)
    }

    onRefresh()
  }

  const handleDelete = async (strategy) => {
    if (window.confirm(`Delete strategy "${strategy.name}"?`)) {
      await deleteStrategy(strategy.id)
      onRefresh()
    }
  }

  if (strategies.length === 0) {
    return (
      <div className="glass rounded-2xl p-8 text-center">
        <p className="text-3xl">📡</p>
        <h3 className="mt-3 font-display text-lg font-semibold text-white">No strategies yet</h3>
        <p className="mt-1 text-sm text-slate-500">
          Build your first automated trading strategy above.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-white/8 bg-white/[0.02] backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-white/5 px-5 py-3.5">
        <h3 className="font-display text-sm font-semibold text-white">Your Strategies</h3>
        <span className="chip chip-cyan">{strategies.length} total</span>
      </div>
      <div className="overflow-x-auto">
        <table className="table-3d">
          <thead>
            <tr>
              <th>Name</th>
              <th>Ticker</th>
              <th>Timeframe</th>
              <th>Status</th>
              <th>Last Triggered</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map((s) => (
              <tr key={s.id}>
                <td className="font-medium text-white">{s.name}</td>
                <td className="font-mono text-cyan-300">{s.ticker}</td>
                <td>
                  <span className="chip chip-violet">{s.timeframe}</span>
                </td>
                <td>
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
                  {s.paused_reason && (
                    <p className="mt-1 max-w-[220px] truncate text-[10px] text-amber-300/90" title={s.paused_reason}>
                      ⏸ {s.paused_reason}
                    </p>
                  )}
                  {s.quantity_multiplier && Number(s.quantity_multiplier) !== 1 && (
                    <p className="mt-1 text-[10px] text-violet-300/90" title="News lot-size state: next order scaled">
                      ◈ lot ×{Number(s.quantity_multiplier).toFixed(2)}
                    </p>
                  )}
                </td>
                <td className="font-mono text-xs text-slate-500">
                  {s.last_triggered_at
                    ? new Date(s.last_triggered_at).toLocaleString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : '—'}
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setBacktestStrategy(s)}
                      className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-3 py-1.5 text-[11px] font-semibold text-cyan-300 transition hover:bg-cyan-500/20"
                    >
                      Backtest
                    </button>
                    <button
                      type="button"
                      onClick={() => handleToggle(s)}
                      className={`rounded-lg px-3 py-1.5 text-[11px] font-semibold transition ${
                        s.status === 'ACTIVE'
                          ? 'btn-ghost !text-amber-300'
                          : 'btn-ghost !text-emerald-300'
                      }`}
                    >
                      {s.status === 'ACTIVE' ? 'Pause' : 'Activate'}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(s)}
                      className="rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-1.5 text-[11px] font-semibold text-rose-400 transition hover:bg-rose-500/20"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {backtestStrategy && (
        <BacktestModal strategy={backtestStrategy} onClose={() => setBacktestStrategy(null)} />
      )}
    </div>
  )
}

const DIFFICULTY_TONE = {
  Beginner: 'chip-bull',
  Intermediate: 'chip-cyan',
  Advanced: 'chip-violet',
}

const CATEGORY_EMOJI = {
  'Trend Following': '📈',
  'Mean Reversion': '🔄',
  Momentum: '⚡',
  Breakout: '🚀',
  'Options Proxy': '🎯',
  'News Sentiment': '📰',
}

function StrategyTemplatesGallery({ templates, onUseTemplate }) {
  const [activeCategory, setActiveCategory] = useState('All')
  const [expandedId, setExpandedId] = useState(null)

  const categories = useMemo(() => {
    const set = new Set(templates.map((t) => t.category))
    return ['All', ...Array.from(set)]
  }, [templates])

  const filtered = useMemo(
    () =>
      activeCategory === 'All'
        ? templates
        : templates.filter((t) => t.category === activeCategory),
    [templates, activeCategory]
  )

  if (templates.length === 0) return null

  return (
    <div className="glass-deep rounded-2xl p-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-white">Strategy Library</h2>
          <p className="mt-1 text-xs text-slate-500">
            Classic, real-world strategies — click <span className="text-cyan-300">Use this</span> to load one into the builder, then tweak the rules, ticker and quantity to fit your capital.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={`rounded-lg px-3 py-1.5 text-[11px] font-semibold transition ${
                activeCategory === cat
                  ? 'bg-gradient-to-r from-cyan-500 to-violet-600 text-white shadow-lg'
                  : 'border border-white/10 bg-white/5 text-slate-400 hover:text-white'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {filtered.map((t) => {
          const expanded = expandedId === t.id
          return (
            <div
              key={t.id}
              className="group flex flex-col rounded-xl border border-white/8 bg-white/[0.03] p-4 transition hover:border-cyan-400/30 hover:bg-white/[0.05]"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{CATEGORY_EMOJI[t.category] || '📊'}</span>
                  <h3 className="font-display text-sm font-bold text-white">{t.name}</h3>
                </div>
                <div className="flex shrink-0 flex-wrap justify-end gap-1">
                  <span className={`chip ${DIFFICULTY_TONE[t.difficulty] || 'chip-neutral'}`}>
                    {t.difficulty}
                  </span>
                  {t.for_options && <span className="chip chip-gold">options</span>}
                </div>
              </div>

              <p className="mt-2 text-xs leading-relaxed text-slate-400">{t.summary}</p>

              <div className="mt-2.5 flex flex-wrap gap-1.5">
                <span className="chip chip-cyan">{t.ticker}</span>
                <span className="chip chip-violet">{t.timeframe}</span>
                <span className="chip chip-neutral">{t.category}</span>
              </div>

              {expanded && (
                <p className="mt-3 whitespace-pre-line rounded-lg bg-black/30 p-3 text-[11px] leading-relaxed text-slate-400">
                  {t.description}
                </p>
              )}

              <div className="mt-3 flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => setExpandedId(expanded ? null : t.id)}
                  className="text-[11px] font-semibold text-slate-500 transition hover:text-cyan-300"
                >
                  {expanded ? '− Hide details' : 'ⓘ How it works'}
                </button>
                <button
                  type="button"
                  onClick={() => onUseTemplate(t)}
                  className="btn-primary rounded-lg px-4 py-2 text-xs font-semibold"
                >
                  Use this →
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function StrategyBuilderPage() {
  const navigate = useNavigate()

  const [watchlist, setWatchlist] = useState([])
  const [strategies, setStrategies] = useState([])
  const [templates, setTemplates] = useState([])

  const [name, setName] = useState('')
  const [ticker, setTicker] = useState('')
  const [timeframe, setTimeframe] = useState('15m')
  const [strategyType, setStrategyType] = useState('SINGLE')
  const [reference, setReference] = useState('SPOT')
  const [product, setProduct] = useState('MIS')
  const [orderMode, setOrderMode] = useState('MARKET')
  const [startTime, setStartTime] = useState('09:20')
  const [squareOffTime, setSquareOffTime] = useState('15:15')
  const [tradingDays, setTradingDays] = useState(['MON', 'TUE', 'WED', 'THU', 'FRI'])
  const [legs, setLegs] = useState([{ ...EMPTY_OPTION_LEG, key: 'leg-1' }])
  const [riskControls, setRiskControls] = useState({
    sl_type: 'POINTS', sl_value: '', tp_type: 'POINTS', tp_value: '',
    max_profit: '', max_loss: '', no_trade_after: '15:00', trailing_mode: 'NONE',
    move_sl_to_cost: false, exit_all: true, pre_punch: false, wait_and_trade: false, re_entry: false,
  })
  const [conditions, setConditions] = useState([])
  const [logic, setLogic] = useState('AND')
  const [action, setAction] = useState({
    side: 'BUY',
    order_type: 'MARKET',
    quantity: 10,
    settlement_type: 'INTRADAY',
    limit_price: null,
  })

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [draftBacktest, setDraftBacktest] = useState(null)
  const [backtestedKey, setBacktestedKey] = useState(null)

  const loadData = useCallback(async () => {
    try {
      const [watchlistRes, strategiesRes, templatesRes] = await Promise.all([
        getWatchlist(),
        getStrategies(),
        getStrategyTemplates(),
      ])
      setWatchlist(watchlistRes.data.tickers || [])
      setStrategies(strategiesRes.data || [])
      setTemplates(templatesRes.data || [])
      if (!ticker && (watchlistRes.data.tickers || []).length > 0) {
        setTicker(watchlistRes.data.tickers[0])
      }
    } catch {
      navigate('/login')
    }
  }, [ticker, navigate])

  useEffect(() => {
    loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadTemplate = (template) => {
    setName(template.name)
    setTicker(template.ticker)
    setTimeframe(template.timeframe)
    setAction({
      side: template.action.side,
      order_type: template.action.order_type,
      quantity: template.action.quantity,
      settlement_type: template.action.settlement_type,
      limit_price: template.action.limit_price ?? null,
    })
    const root = template.root_condition
    if (root && root.type === 'group') {
      setLogic(root.logic || 'AND')
      const leafs = (root.conditions || []).map((c, i) => ({
        key: `t-${Date.now()}-${i}`,
        left: c.left,
        operator: c.operator,
        right: c.right,
      }))
      setConditions(leafs)
    } else if (root && root.type === 'condition') {
      setLogic('AND')
      setConditions([
        { key: `t-${Date.now()}`, left: root.left, operator: root.operator, right: root.right },
      ])
    }
    setError(null)
    setSuccess(`Loaded "${template.name}" template — review, adjust quantity, then Activate & Run.`)
    document.getElementById('strategy-name')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const rootCondition = useMemo(() => {
    const leafs = conditions.map((c) => ({
      type: 'condition',
      left: c.left,
      operator: c.operator,
      right: c.right,
    }))
    return {
      type: 'group',
      logic,
      conditions: leafs,
    }
  }, [conditions, logic])

  const optionPayload = useMemo(() => ({
    strategy_type: strategyType,
    reference,
    product,
    order_mode: orderMode,
    start_time: startTime,
    square_off_time: squareOffTime,
    trading_days: tradingDays,
    legs: legs.map((leg) =>
      Object.fromEntries(Object.entries(leg).filter(([field]) => field !== 'key'))
    ),
    risk_controls: Object.fromEntries(Object.entries(riskControls).filter(([, value]) => value !== '')),
  }), [strategyType, reference, product, orderMode, startTime, squareOffTime, tradingDays, legs, riskControls])

  const jsonPreview = useMemo(() => {
    return JSON.stringify(
      {
        name,
        ticker,
        timeframe,
        root_condition: conditions.length ? rootCondition : null,
        action: {
          side: action.side,
          order_type: action.order_type,
          quantity: action.quantity,
          settlement_type: action.settlement_type,
          ...(action.order_type === 'LIMIT' ? { limit_price: action.limit_price } : {}),
        },
        ...(strategyType !== 'SINGLE' ? optionPayload : {}),
      },
      null,
      2
    )
  }, [name, ticker, timeframe, rootCondition, action, strategyType, optionPayload])

  const handleDraftBacktest = () => {
      setError(null)
      if (!name.trim()) {
        setError('Give your strategy a name before backtesting.')
        return
      }
      if (!ticker) {
        setError('Pick a ticker before backtesting.')
        return
      }
      if (conditions.length === 0 && strategyType === 'OPTIONS_INDICATOR') {
        setError('Add at least one condition before backtesting.')
        return
      }
      if (strategyType !== 'SINGLE' && legs.length === 0) {
        setError('Add at least one option leg before backtesting.')
        return
      }
      if (action.order_type === 'LIMIT' && (!action.limit_price || action.limit_price <= 0)) {
        setError('LIMIT orders need a positive limit price.')
        return
      }
      setDraftBacktest({
        name,
        ticker,
        timeframe,
        root_condition: rootCondition,
        action: {
          side: action.side,
          order_type: action.order_type,
          quantity: action.quantity,
          settlement_type: action.settlement_type,
          ...(action.order_type === 'LIMIT' ? { limit_price: action.limit_price } : {}),
        },
        ...(strategyType !== 'SINGLE' ? optionPayload : {}),
      })
  }

  const handleSave = async (status) => {
    setError(null)
    setSuccess(null)

    if (!name.trim()) {
      setError('Give your strategy a name.')
      return
    }
    if (!ticker) {
      setError('Pick a ticker.')
      return
    }
    if (conditions.length === 0 && strategyType === 'OPTIONS_INDICATOR') {
      setError('Add at least one condition.')
      return
    }
    if (strategyType !== 'SINGLE' && legs.length === 0) {
      setError('Add at least one option leg.')
      return
    }
    if (action.order_type === 'LIMIT' && (!action.limit_price || action.limit_price <= 0)) {
      setError('LIMIT orders need a positive limit price.')
      return
    }

    setSaving(true)
    try {
      const payload = {
        name,
        ticker,
        timeframe,
        root_condition: conditions.length ? rootCondition : null,
        action: {
          side: action.side,
          order_type: action.order_type,
          quantity: action.quantity,
          settlement_type: action.settlement_type,
          ...(action.order_type === 'LIMIT' ? { limit_price: action.limit_price } : {}),
        },
        ...(strategyType !== 'SINGLE' ? optionPayload : {}),
        status,
      }
      await createStrategy(payload)
      setSuccess(`Strategy "${name}" saved as ${status === 'ACTIVE' ? 'ACTIVE — live evaluation started' : 'DRAFT'}.`)
      await loadData()
    } catch (err) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg).join('; '))
      } else {
        setError(typeof detail === 'string' ? detail : 'Failed to save strategy.')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <PageLayout>
      <div className="animate-rise">
        {/* Header */}
        <div className="mb-8 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="chip chip-violet mb-2">Phase 3 • Visual Strategy Builder</p>
            <h1 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Strategy <span className="text-gradient-cyan">Builder</span>
            </h1>
            <p className="mt-2 max-w-xl text-sm text-slate-400">
              Drag, drop and wire technical conditions together. When they turn true, TradeMind auto-fires your paper
              order — no code required.
            </p>
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleDraftBacktest}
              disabled={saving}
              className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-5 py-2.5 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-400/20 disabled:opacity-50"
            >
              📊 Backtest Strategy
            </button>
            <button
              type="button"
              onClick={() => handleSave('DRAFT')}
              disabled={saving}
              className="btn-ghost rounded-xl px-5 py-2.5 text-sm font-semibold disabled:opacity-50"
            >
              Save Draft
            </button>
            <button
              type="button"
              onClick={() => handleSave('ACTIVE')}
              disabled={saving || backtestedKey !== jsonPreview}
              title={backtestedKey !== jsonPreview ? 'Backtest this exact strategy before activating it.' : undefined}
              className="btn-primary rounded-xl px-5 py-2.5 text-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Saving…' : '⚡ Activate & Run'}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-5 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
            {success}
          </div>
        )}

        {/* ─────────────────────────────────────────────────────────
            TOP: Strategy Builder (config + conditions + action)
        ────────────────────────────────────────────────────────── */}
        <div className="space-y-6 mb-8">
          {/* Config card */}
          <div className="glass glow-cyan card-3d rounded-2xl p-6">
            <div className="card-glow" />
            <h2 className="mb-4 font-display text-lg font-semibold text-white">Strategy Setup</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="flex flex-col gap-1">
                <label htmlFor="strategy-type" className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Strategy Type</label>
                <select id="strategy-type" value={strategyType} onChange={(e) => setStrategyType(e.target.value)} className="input-3d">
                  <option value="SINGLE">Technical / Equity (classic)</option>
                  <option value="OPTIONS_TIME">Option Trading — Time Based</option>
                  <option value="OPTIONS_INDICATOR">Option Trading — Indicator Based</option>
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="strategy-name" className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Strategy Name
                </label>
                <input
                  id="strategy-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input-3d"
                  placeholder="e.g. RSI Reversal"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="strategy-ticker" className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Ticker
                </label>
                <select id="strategy-ticker" value={ticker} onChange={(e) => setTicker(e.target.value)} className="input-3d">
                  {watchlist.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="strategy-timeframe" className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Timeframe
                </label>
                <select id="strategy-timeframe" value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="input-3d">
                  <option value="15m">15 min</option>
                  <option value="1d">Daily</option>
                </select>
              </div>
            </div>
            {strategyType !== 'SINGLE' && (
              <div className="mt-5 space-y-4 border-t border-white/8 pt-5">
                <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
                  <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Reference
                    <select value={reference} onChange={(e) => setReference(e.target.value)} className="input-3d"><option value="SPOT">Spot</option><option value="FUTURE">Future</option></select>
                  </label>
                  <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Product
                    <select value={product} onChange={(e) => setProduct(e.target.value)} className="input-3d"><option value="MIS">MIS</option><option value="CNC">CNC</option><option value="BTST">BTST</option></select>
                  </label>
                  <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Order mode
                    <select value={orderMode} onChange={(e) => setOrderMode(e.target.value)} className="input-3d"><option value="MARKET">Market</option><option value="LIMIT">Limit</option></select>
                  </label>
                  <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Start time
                    <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} className="input-3d" />
                  </label>
                  <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Square-off
                    <input type="time" value={squareOffTime} onChange={(e) => setSquareOffTime(e.target.value)} className="input-3d" />
                  </label>
                  <div className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Trading days
                    <div className="flex flex-wrap gap-1 pt-1">{['MON', 'TUE', 'WED', 'THU', 'FRI'].map((day) => <button type="button" key={day} onClick={() => setTradingDays((days) => days.includes(day) ? days.filter((d) => d !== day) : [...days, day])} className={`rounded px-2 py-1 text-[10px] ${tradingDays.includes(day) ? 'bg-cyan-500 text-white' : 'bg-white/5 text-slate-500'}`}>{day.slice(0, 2)}</button>)}</div>
                  </div>
                </div>
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-white">Option legs</h3>
                  <OptionLegEditor legs={legs} onChange={setLegs} />
                </div>
              </div>
            )}
          </div>

          {strategyType !== 'SINGLE' && (
            <div className="glass card-3d rounded-2xl p-6">
              <h2 className="mb-4 font-display text-lg font-semibold text-white">Risk &amp; Advanced Controls</h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ['sl_type', 'Stop-loss type', ['POINTS', 'PERCENT', 'PREMIUM']],
                  ['tp_type', 'Target type', ['POINTS', 'PERCENT', 'PREMIUM']],
                  ['trailing_mode', 'Trailing stop', ['NONE', 'POINTS', 'PERCENT', 'PREMIUM']],
                ].map(([field, label, values]) => (
                  <label key={field} className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}
                    <select value={riskControls[field]} onChange={(e) => setRiskControls((current) => ({ ...current, [field]: e.target.value }))} className="input-3d">{values.map((value) => <option key={value}>{value}</option>)}</select>
                  </label>
                ))}
                {['sl_value', 'tp_value', 'max_profit', 'max_loss'].map((field) => (
                  <label key={field} className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">{field.replace('_', ' ')}
                    <input type="number" min="0" value={riskControls[field]} onChange={(e) => setRiskControls((current) => ({ ...current, [field]: e.target.value }))} className="input-3d font-mono" placeholder="Optional" />
                  </label>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-300">
                {['move_sl_to_cost', 'exit_all', 'pre_punch', 'wait_and_trade', 're_entry'].map((field) => (
                  <label key={field} className="flex items-center gap-2"><input type="checkbox" checked={riskControls[field]} onChange={(e) => setRiskControls((current) => ({ ...current, [field]: e.target.checked }))} />{field.replaceAll('_', ' ')}</label>
                ))}
              </div>
            </div>
          )}

          {/* Conditions card */}
          <div className="glass glow-violet card-3d rounded-2xl p-6">
            <div className="card-glow" />
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-white">Entry Conditions</h2>
              <span className="chip chip-cyan">{conditions.length} rule{conditions.length === 1 ? '' : 's'}</span>
            </div>
            <ConditionBuilder
              conditions={conditions}
              logic={logic}
              onLogicChange={setLogic}
              onConditionsChange={setConditions}
            />
          </div>

          {/* Action card */}
          <div className="glass glow-bull card-3d rounded-2xl p-6">
            <div className="card-glow" />
            <h2 className="mb-4 font-display text-lg font-semibold text-white">Auto-Fired Action</h2>
            <ActionEditor action={action} onChange={setAction} />
          </div>

          {/* Quick stats */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Rules" value={conditions.length} icon="⚙" tone="cyan" className="card-3d" />
            <StatCard label="Logic" value={logic} icon="⊢" tone="violet" className="card-3d" />
            <StatCard label="Action" value={`${action.side} ${action.order_type}`} icon="⚡" tone={action.side === 'BUY' ? 'bull' : 'bear'} className="card-3d" />
            <StatCard label="Quantity" value={action.quantity} icon="◈" tone="gold" className="card-3d" />
          </div>
        </div>

        {/* ─────────────────────────────────────────────────────────
            BOTTOM: Strategy Library (templates)
        ────────────────────────────────────────────────────────── */}
        <div className="mb-8">
          <StrategyTemplatesGallery templates={templates} onUseTemplate={loadTemplate} />
        </div>

        {/* ─────────────────────────────────────────────────────────
            BOTTOM: Your Saved Strategies
        ────────────────────────────────────────────────────────── */}
        <StrategyList strategies={strategies} onRefresh={loadData} />
      </div>
      {draftBacktest && (
        <BacktestModal
          strategy={draftBacktest}
          draft
          onClose={() => setDraftBacktest(null)}
          onCompleted={() => setBacktestedKey(JSON.stringify({
            name: draftBacktest.name,
            ticker: draftBacktest.ticker,
            timeframe: draftBacktest.timeframe,
            root_condition: draftBacktest.root_condition,
            action: draftBacktest.action,
            ...(draftBacktest.strategy_type ? {
              strategy_type: draftBacktest.strategy_type,
              reference: draftBacktest.reference,
              product: draftBacktest.product,
              order_mode: draftBacktest.order_mode,
              start_time: draftBacktest.start_time,
              square_off_time: draftBacktest.square_off_time,
              trading_days: draftBacktest.trading_days,
              legs: draftBacktest.legs,
              risk_controls: draftBacktest.risk_controls,
            } : {}),
          }))}
        />
      )}
    </PageLayout>
  )
}

export default StrategyBuilderPage