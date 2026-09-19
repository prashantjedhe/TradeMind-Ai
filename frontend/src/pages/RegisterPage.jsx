import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { registerUser, loginUser, getCurrentUser } from '../api/authApi'
import { useAuthStore } from '../store/authStore'
import ImmersiveBackground from '../components/common/ImmersiveBackground'

function RegisterPage() {
  const navigate = useNavigate()
  const setTokens = useAuthStore((state) => state.setTokens)
  const setUser = useAuthStore((state) => state.setUser)

  const [form, setForm] = useState({ email: '', username: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await registerUser(form)

      const { data } = await loginUser({
        email: form.email,
        password: form.password,
      })

      setTokens(data.access_token, data.refresh_token)
      try {
        const meRes = await getCurrentUser()
        setUser(meRes.data)
      } catch {
        setUser({ username: form.username })
      }
      navigate('/dashboard')
    } catch (err) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg).join('; '))
      } else {
        setError(typeof detail === 'string' ? detail : 'Registration failed')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10 text-slate-100">
      <ImmersiveBackground />

      <div className="relative z-10 w-full max-w-md animate-rise">
        {/* Brand */}
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="relative mb-4 flex h-16 w-16 items-center justify-center">
            <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-cyan-400/70 to-violet-500/70 blur-xl animate-pulse-glow" />
            <div className="relative flex h-16 w-16 items-center justify-center rounded-3xl border border-white/25 bg-gradient-to-br from-cyan-500 to-violet-600 shadow-2xl">
              <span className="font-display text-3xl font-bold text-white">T</span>
            </div>
          </div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-white">
            TradeMind <span className="text-gradient-cyan">AI</span>
          </h1>
          <p className="mt-1 text-xs font-medium uppercase tracking-[0.3em] text-slate-500">
            Start Paper Trading
          </p>
        </div>

        {/* Card */}
        <div className="glass-deep card-3d glow-cyan rounded-3xl p-8">
          <div className="card-glow" />
          <h2 className="mb-1 font-display text-xl font-semibold text-white">Create Account</h2>
          <p className="mb-6 text-sm text-slate-400">
            Get ₹10,00,000 in virtual capital. Trade NSE stocks risk-free.
          </p>

          {error && (
            <div className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2.5 text-sm text-rose-300">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Email
              </label>
              <input
                id="email"
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                required
                placeholder="you@example.com"
                className="input-3d"
              />
            </div>

            <div>
              <label htmlFor="username" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Username
              </label>
              <input
                id="username"
                type="text"
                name="username"
                value={form.username}
                onChange={handleChange}
                required
                minLength={3}
                placeholder="trader_name"
                className="input-3d"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Password
              </label>
              <input
                id="password"
                type="password"
                name="password"
                value={form.password}
                onChange={handleChange}
                required
                minLength={8}
                placeholder="Min 8 characters"
                className="input-3d"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full rounded-xl py-3 text-sm disabled:opacity-50"
            >
              {loading ? 'Creating terminal…' : 'Create Account'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-400">
            Already registered?{' '}
            <Link to="/login" className="font-semibold text-cyan-300 transition hover:text-cyan-200">
              Log in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

export default RegisterPage