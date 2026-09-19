function StatCard({
  label,
  value,
  sub,
  icon,
  tone = 'cyan',
  positive = null,
  className = '',
}) {
  const valueColor =
    positive === null
      ? 'text-white'
      : positive
        ? 'text-emerald-400'
        : 'text-rose-400'

  const glowClass = {
    cyan: 'glow-cyan',
    violet: 'glow-violet',
    bull: 'glow-bull',
    bear: 'glow-bull',
  }[tone]

  const iconBg = {
    cyan: 'from-cyan-500/30 to-cyan-500/5 text-cyan-300 border-cyan-400/20',
    violet: 'from-violet-500/30 to-violet-500/5 text-violet-300 border-violet-400/20',
    bull: 'from-emerald-500/30 to-emerald-500/5 text-emerald-300 border-emerald-400/20',
    bear: 'from-rose-500/30 to-rose-500/5 text-rose-300 border-rose-400/20',
  }[tone]

  return (
    <div className={`glass card-3d ${glowClass} rounded-2xl p-5 ${className}`}>
      <div className="card-glow" />
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            {label}
          </p>
          <p className={`mt-2 font-display text-2xl font-bold ${valueColor}`}>{value}</p>
          {sub && <p className="mt-1 text-[11px] text-slate-500">{sub}</p>}
        </div>
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl border bg-gradient-to-br text-base ${iconBg}`}
        >
          {icon}
        </div>
      </div>
    </div>
  )
}

export default StatCard