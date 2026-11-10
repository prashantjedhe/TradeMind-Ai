import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { logoutUser } from '../../api/authApi'
import { useAuthStore } from '../../store/authStore'

const NAV_LINKS = [
  { to: '/dashboard', label: 'Dashboard', icon: '▦' },
  { to: '/trading', label: 'Trading', icon: '↗' },
  { to: '/fno', label: 'F&O', icon: '◫' },
  { to: '/news', label: 'News', icon: '◉' },
  { to: '/strategies', label: 'Strategies', icon: '⌘' },
  { to: '/league', label: 'League', icon: '♙' },
  { to: '/profile', label: 'Profile', icon: '⚙' },
]

function Brand() {
  return (
    <NavLink to="/dashboard" className="group flex items-center gap-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-cyan-300/25 bg-gradient-to-br from-cyan-500/30 via-blue-500/25 to-violet-600/40 shadow-[0_0_20px_rgba(84,220,245,0.12)]">
        <span className="font-display text-lg font-bold text-white">T</span>
      </div>
      <div className="leading-tight">
        <span className="font-display text-base font-bold tracking-tight text-white">TradeMind AI</span>
        <p className="text-[9px] font-medium uppercase tracking-[0.22em] text-slate-500">
          Paper Trading Engine
        </p>
      </div>
    </NavLink>
  )
}

function Navbar() {
  const navigate = useNavigate()
  const logout = useAuthStore((state) => state.logout)
  const user = useAuthStore((state) => state.user)
  const [menuOpen, setMenuOpen] = useState(false)

  const handleLogout = async () => {
    try {
      await logoutUser()
    } catch {
      // Keep client-side logout available if the server request fails.
    } finally {
      logout()
      navigate('/login')
    }
  }

  const linkClass = ({ isActive }) =>
    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
      isActive
        ? 'border border-cyan-300/20 bg-gradient-to-r from-cyan-950/70 via-blue-950/60 to-violet-950/55 text-white shadow-[inset_2px_0_0_#54dcf5]'
        : 'text-slate-400 hover:bg-white/5 hover:text-white'
    }`

  return (
    <>
      <aside className="sticky top-[34px] z-40 col-start-1 row-start-2 hidden h-[calc(100vh-34px)] w-56 flex-col overflow-y-auto border-r border-[#1c2a41] bg-[#0a0f1c]/95 px-3 py-5 backdrop-blur-xl lg:flex">
        <div className="border-b border-white/10 px-2 pb-6">
          <Brand />
        </div>

        <div className="px-2 pt-6">
          <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
            Workspace
          </p>
          <nav aria-label="Primary navigation" className="space-y-1">
            {NAV_LINKS.map((link) => (
              <NavLink key={link.to} to={link.to} className={linkClass}>
                <span aria-hidden="true" className="w-5 text-center text-base text-slate-400">
                  {link.icon}
                </span>
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="mt-auto">
          <div className="mx-1 mb-4 rounded-lg border border-white/10 bg-white/[0.03] p-3">
            <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-slate-500">
              Trading mode
            </p>
            <p className="mt-2 text-xs font-semibold text-slate-200">Paper account</p>
            <p className="mt-1 text-[10px] text-slate-500">NSE market data</p>
          </div>

          <div className="flex items-center gap-2 border-t border-white/10 px-1 pt-4">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-cyan-300/25 bg-gradient-to-br from-cyan-500/30 via-blue-500/25 to-violet-600/40 font-display text-xs font-bold text-white">
              {(user?.username || 'U').slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1 leading-tight">
              <p className="truncate text-xs font-semibold text-slate-200">{user?.username || 'User'}</p>
              <p className="mt-1 text-[9px] text-slate-500">NSE · Paper</p>
            </div>
            <button
              onClick={handleLogout}
              className="rounded-md border border-rose-500/30 bg-rose-500/10 px-2 py-1.5 text-[10px] font-medium text-rose-300 transition-colors hover:bg-rose-500/20"
            >
              Logout
            </button>
          </div>
        </div>
      </aside>

      <header className="sticky top-0 z-40 border-b border-[#1c2a41] bg-[#080d18]/95 backdrop-blur-xl lg:hidden">
        <div className="flex h-16 items-center justify-between px-4">
          <Brand />
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-slate-300 hover:text-white"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
          >
            <span className="text-sm">{menuOpen ? '✕' : '☰'}</span>
          </button>
        </div>

        {menuOpen && (
          <nav aria-label="Primary navigation" className="border-t border-[#1c2a41] bg-[#0c1220] px-4 py-3">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium ${
                    isActive
                      ? 'border border-cyan-300/20 bg-gradient-to-r from-cyan-950/70 via-blue-950/60 to-violet-950/55 text-white'
                      : 'text-slate-400'
                  }`
                }
              >
                <span aria-hidden="true" className="w-5 text-center">{link.icon}</span>
                {link.label}
              </NavLink>
            ))}
            <div className="mt-2 flex items-center justify-between border-t border-white/10 px-3 pt-3">
              <span className="text-xs text-slate-400">{user?.username || 'User'}</span>
              <button
                onClick={handleLogout}
                className="rounded-md bg-rose-500/15 px-3 py-2 text-xs font-medium text-rose-300"
              >
                Logout
              </button>
            </div>
          </nav>
        )}
      </header>
    </>
  )
}

export default Navbar
