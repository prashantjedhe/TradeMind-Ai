import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

export const INDICATOR_OPTIONS = [
  { value: 'RSI', label: 'RSI', params: { period: 14 }, paramLabel: 'Period' },
  { value: 'EMA', label: 'EMA', params: { period: 20 }, paramLabel: 'Period' },
  { value: 'SMA', label: 'SMA', params: { period: 20 }, paramLabel: 'Period' },
  { value: 'MACD', label: 'MACD', params: { fast: 12, slow: 26, signal: 9 }, paramLabel: 'Params' },
  { value: 'MACD_SIGNAL', label: 'MACD Signal', params: { fast: 12, slow: 26, signal: 9 }, paramLabel: 'Params' },
  { value: 'MACD_HIST', label: 'MACD Hist', params: { fast: 12, slow: 26, signal: 9 }, paramLabel: 'Params' },
  { value: 'VOLUME', label: 'Avg Volume', params: { period: 20 }, paramLabel: 'Period' },
  { value: 'PRICE', label: 'Close Price', params: {}, paramLabel: '' },
  { value: 'SENTIMENT', label: 'News Sentiment', params: { window: '1h', metric: 'score' }, paramLabel: 'Window' },
]

export const SENTIMENT_WINDOWS = [
  { value: '15m', label: '15m' },
  { value: '1h', label: '1h' },
  { value: '1d', label: '1d' },
]

export const SENTIMENT_METRICS = [
  { value: 'score', label: 'Score' },
  { value: 'zscore', label: 'Z-Score' },
  { value: 'count', label: 'Article Count' },
]

export const OPERATORS = [
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '>=', label: '≥' },
  { value: '<=', label: '≤' },
  { value: '==', label: '=' },
  { value: 'crosses_above', label: 'Crosses Above' },
  { value: 'crosses_below', label: 'Crosses Below' },
]

export function indicatorMeta(value) {
  return INDICATOR_OPTIONS.find((o) => o.value === value) || INDICATOR_OPTIONS[0]
}

export function SortableConditionRow({ id, index, condition, onUpdate, onRemove }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
    zIndex: isDragging ? 30 : 1,
  }

  const handleLeftChange = (e) => {
    const value = e.target.value
    const meta = indicatorMeta(value)
    onUpdate({
      ...condition,
      left: { indicator: value, params: { ...meta.params } },
      // Sentiment compares against a score threshold, not another
      // indicator -- reset a stale indicator right-hand side.
      ...(value === 'SENTIMENT' && typeof condition.right === 'object'
        ? { right: 0.2 }
        : {}),
    })
  }

  const handleRightType = (isIndicator) => {
    onUpdate({
      ...condition,
      right: isIndicator
        ? { indicator: 'SMA', params: { period: 20 } }
        : 0,
    })
  }

  const rightIsIndicator = typeof condition.right === 'object' && condition.right !== null

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="group relative flex flex-col gap-2 rounded-xl border border-white/8 bg-white/[0.03] p-3 backdrop-blur-sm transition-colors hover:border-cyan-400/30 sm:flex-row sm:items-center"
    >
      <button
        {...attributes}
        {...listeners}
        className="hidden cursor-grab items-center justify-center rounded-lg border border-white/10 bg-white/5 px-2.5 py-2 text-slate-400 transition hover:text-cyan-300 active:cursor-grabbing sm:flex"
        aria-label="Drag to reorder"
      >
        ⠿
      </button>

      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 sm:w-6 sm:text-center">
        {index + 1}
      </span>

      {/* Left indicator */}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-500">
          Indicator
        </label>
        <select
          value={condition.left.indicator}
          onChange={handleLeftChange}
          className="input-3d py-1.5"
        >
          {INDICATOR_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {/* Left params */}
      <div className="flex flex-col gap-1">
        <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-500">
          {indicatorMeta(condition.left.indicator).paramLabel || '—'}
        </label>
        {condition.left.indicator === 'SENTIMENT' ? (
          <div className="flex gap-1.5">
            <select
              value={condition.left.params.window ?? '1h'}
              onChange={(e) =>
                onUpdate({
                  ...condition,
                  left: {
                    ...condition.left,
                    params: { ...condition.left.params, window: e.target.value },
                  },
                })
              }
              className="input-3d py-1.5 text-center font-mono text-xs"
              aria-label="Sentiment window"
            >
              {SENTIMENT_WINDOWS.map((w) => (
                <option key={w.value} value={w.value}>
                  {w.label}
                </option>
              ))}
            </select>
            <select
              value={condition.left.params.metric ?? 'score'}
              onChange={(e) =>
                onUpdate({
                  ...condition,
                  left: {
                    ...condition.left,
                    params: { ...condition.left.params, metric: e.target.value },
                  },
                })
              }
              className="input-3d py-1.5 text-center font-mono text-xs"
              aria-label="Sentiment metric"
            >
              {SENTIMENT_METRICS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        ) : condition.left.indicator.startsWith('MACD') ? (
          <span className="input-3d py-1.5 text-center font-mono text-xs text-cyan-300">
            {condition.left.params.fast},{condition.left.params.slow},{condition.left.params.signal}
          </span>
        ) : condition.left.indicator === 'PRICE' ? (
          <span className="input-3d py-1.5 text-center font-mono text-xs text-slate-400">—</span>
        ) : (
          <input
            type="number"
            min={1}
            value={condition.left.params.period ?? 14}
            onChange={(e) =>
              onUpdate({
                ...condition,
                left: {
                  ...condition.left,
                  params: { ...condition.left.params, period: Number(e.target.value) },
                },
              })
            }
            className="input-3d py-1.5 w-20 text-center font-mono text-xs"
          />
        )}
      </div>

      {/* Operator */}
      <div className="flex flex-col gap-1">
        <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-500">
          Operator
        </label>
        <select
          value={condition.operator}
          onChange={(e) => onUpdate({ ...condition, operator: e.target.value })}
          className="input-3d py-1.5"
        >
          {OPERATORS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {/* Right operand */}
      <div className="flex flex-1 flex-col gap-1">
        <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-500">
          vs {rightIsIndicator ? 'Indicator' : 'Value'}
        </label>
        {rightIsIndicator ? (
          <div className="flex gap-1.5">
            <select
              value={condition.right.indicator}
              onChange={(e) => {
                const meta = indicatorMeta(e.target.value)
                onUpdate({ ...condition, right: { indicator: e.target.value, params: { ...meta.params } } })
              }}
              className="input-3d py-1.5"
            >
              {INDICATOR_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <input
            type="number"
            step="any"
            value={condition.right}
            onChange={(e) => onUpdate({ ...condition, right: Number(e.target.value) })}
            className="input-3d py-1.5 font-mono text-xs"
          />
        )}
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={() => handleRightType(false)}
            className={`rounded-md px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide transition ${
              !rightIsIndicator
                ? 'bg-cyan-500/20 text-cyan-300'
                : 'bg-white/5 text-slate-500 hover:text-slate-300'
            }`}
          >
            Value
          </button>
          <button
            type="button"
            onClick={() => handleRightType(true)}
            className={`rounded-md px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide transition ${
              rightIsIndicator
                ? 'bg-violet-500/20 text-violet-300'
                : 'bg-white/5 text-slate-500 hover:text-slate-300'
            }`}
          >
            Indicator
          </button>
        </div>
      </div>

      <button
        type="button"
        onClick={onRemove}
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-rose-500/20 bg-rose-500/10 text-rose-400 transition hover:bg-rose-500/20 hover:text-rose-300"
        aria-label="Remove condition"
      >
        ✕
      </button>
    </div>
  )
}