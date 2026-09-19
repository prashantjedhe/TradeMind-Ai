import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { logoutUser } from '../../api/authApi'
import { useAuthStore } from '../../store/authStore'

const NAV_LINKS = [
  { to: '/dashboard', label: 'Dashboard', icon: '◈' },
  { to: '/trading', label: 'Trading', icon: '⇄' },
  { to: '/fno', label: 'F&O', icon: '◆' },
  { to: '/news', label: 'News', icon: '📰' },
  { to: '/strategies', label: 'Strategies', icon: '⚡' },
  { to: '/league', label: 'League', icon: '🏆' },
  { to: '/profile', label: 'Profile', icon: '◉' },
]

function Navbar() {
  const navigate = useNavigate()
  const logout = useAuthStore((state) => state.logout)
  const user = useAuthStore((state) => state.user)
  const [menuOpen, setMenuOpen] = useState(false)

  const handleLogout = async () => {
    try {
      await logoutUser()
    } catch {
      // ignore - logging out client-side regardless
    } finally {
      logout()
      navigate('/login')
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-[#05070f]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Brand */}
        <NavLink to="/dashboard" className="group flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center">
            <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-cyan-400/60 to-violet-500/60 blur-[6px] transition group-hover:blur-[10px]" />
            <div className="relative flex h-10 w-10 items-center justify-center rounded-2xl border border-white/20 bg-gradient-to-br from-cyan-500 to-violet-600 shadow-lg">
              <span className="font-display text-lg font-bold text-white">T</span>
            </div>
          </div>
          <div className="leading-tight">
            <span className="font-display text-base font-bold tracking-tight text-white">
              TradeMind<span className="text-cyan-400"> AI</span>
            </span>
            <p className="text-[9px] font-medium uppercase tracking-[0.22em] text-slate-500">
              Paper Trading Engine
            </p>
          </div>
        </NavLink>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `relative rounded-xl px-4 py-2 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'text-white'
                    : 'text-slate-400 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className="mr-1.5 text-[11px]">{link.icon}</span>
                  {link.label}
                  {isActive && (
                    <span className="absolute inset-x-3 -bottom-[13px] h-[2px] rounded-full bg-gradient-to-r from-cyan-400 to-violet-500 shadow-[0_0_12px_rgba(34,211,238,0.8)]" />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User + logout */}
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2.5 rounded-xl border border-white/10 bg-white/5 py-1.5 pl-1.5 pr-3 sm:flex">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-violet-600 font-display text-xs font-bold text-white">
              {(user?.username || 'U').slice(0, 1).toUpperCase()}
            </div>
            <div className="leading-tight">
              <p className="text-xs font-semibold text-slate-200">{user?.username || 'User'}</p>
              <p className="text-[9px] text-slate-500">NSE • Live</p>
            </div>
          </div>

          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-slate-300 hover:text-white md:hidden"
            aria-label="Toggle menu"
          >
            <span className="text-sm">{menuOpen ? '✕' : '☰'}</span>
          </button>

          <button
            onClick={handleLogout}
            className="hidden items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2 text-sm font-medium text-rose-300 transition-all hover:border-rose-400/50 hover:bg-rose-500/20 hover:text-rose-200 md:flex"
          >
            Logout
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <nav className="border-t border-white/5 bg-[#070a14]/95 px-4 py-3 md:hidden">
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `block rounded-xl px-4 py-2.5 text-sm font-medium ${
                  isActive ? 'bg-white/10 text-white' : 'text-slate-400'
                }`
              }
            >
              <span className="mr-2">{link.icon}</span>
              {link.label}
            </NavLink>
          ))}
          <button
            onClick={handleLogout}
            className="mt-2 w-full rounded-xl bg-rose-500/15 px-4 py-2.5 text-sm font-medium text-rose-300"
          >
            Logout
          </button>
        </nav>
      )}
    </header>
  )
}

export default Navbar