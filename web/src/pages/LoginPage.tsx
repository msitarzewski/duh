import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { GlassPanel, GlowButton } from '@/components/shared'
import { useAuthStore } from '@/stores'
import { api } from '@/api/client'

export function LoginPage() {
  const { status, error, login, register } = useAuthStore()
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [forgotMessage, setForgotMessage] = useState<string | null>(null)
  const [forgotError, setForgotError] = useState<string | null>(null)
  const [forgotLoading, setForgotLoading] = useState(false)

  if (status === 'authenticated') {
    return <Navigate to="/" replace />
  }

  const handleSubmit = async (e: { preventDefault: () => void }) => {
    e.preventDefault()
    if (mode === 'login') {
      await login(email, password)
    } else if (mode === 'register') {
      await register(email, password, displayName)
    }
  }

  const handleForgotSubmit = async (e: { preventDefault: () => void }) => {
    e.preventDefault()
    setForgotLoading(true)
    setForgotError(null)
    setForgotMessage(null)
    try {
      const res = await api.forgotPassword({ email })
      setForgotMessage(res.message)
    } catch (err) {
      setForgotError((err as Error).message)
    } finally {
      setForgotLoading(false)
    }
  }

  const inputClass = "w-full px-3 py-2 rounded-[var(--radius-sm)] bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] font-mono text-sm focus:outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)] transition-colors"

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="font-mono text-3xl font-bold text-[var(--color-primary)] tracking-wider">
            duh
          </h1>
          <p className="text-xs text-[var(--color-text-dim)] font-mono mt-1">
            consensus engine
          </p>
        </div>

        <GlassPanel glow="subtle" padding="lg">
          {mode === 'forgot' ? (
            <form onSubmit={handleForgotSubmit} className="space-y-4">
              <h2 className="text-lg font-mono font-semibold text-[var(--color-text)] text-center">
                Reset Password
              </h2>
              <p className="text-xs font-mono text-[var(--color-text-dim)] text-center">
                Enter your email and we'll send a reset link.
              </p>

              <div>
                <label className="block text-xs font-mono text-[var(--color-text-secondary)] mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className={inputClass}
                  placeholder="you@example.com"
                />
              </div>

              {forgotMessage && (
                <p className="text-xs font-mono text-[var(--color-green)] bg-[rgba(0,200,100,0.1)] px-3 py-2 rounded-[var(--radius-sm)] border border-[rgba(0,200,100,0.2)]">
                  {forgotMessage}
                </p>
              )}

              {forgotError && (
                <p className="text-xs font-mono text-[var(--color-red)] bg-[rgba(255,59,79,0.1)] px-3 py-2 rounded-[var(--radius-sm)] border border-[rgba(255,59,79,0.2)]">
                  {forgotError}
                </p>
              )}

              <GlowButton
                type="submit"
                loading={forgotLoading}
                className="w-full"
              >
                Send Reset Link
              </GlowButton>

              <p className="text-center text-xs font-mono text-[var(--color-text-dim)]">
                <button
                  type="button"
                  onClick={() => { setMode('login'); setForgotMessage(null); setForgotError(null) }}
                  className="text-[var(--color-primary)] hover:underline"
                >
                  Back to Sign In
                </button>
              </p>
            </form>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <h2 className="text-lg font-mono font-semibold text-[var(--color-text)] text-center">
                {mode === 'login' ? 'Sign In' : 'Create Account'}
              </h2>

              {mode === 'register' && (
                <div>
                  <label className="block text-xs font-mono text-[var(--color-text-secondary)] mb-1">
                    Display Name
                  </label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    required
                    className={inputClass}
                    placeholder="Your name"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-mono text-[var(--color-text-secondary)] mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className={inputClass}
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--color-text-secondary)] mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className={inputClass}
                  placeholder="••••••••"
                />
              </div>

              {mode === 'login' && (
                <div className="text-right">
                  <button
                    type="button"
                    onClick={() => { setMode('forgot'); setEmail(''); setPassword('') }}
                    className="text-xs font-mono text-[var(--color-text-dim)] hover:text-[var(--color-primary)] transition-colors"
                  >
                    Forgot password?
                  </button>
                </div>
              )}

              {error && (
                <p className="text-xs font-mono text-[var(--color-red)] bg-[rgba(255,59,79,0.1)] px-3 py-2 rounded-[var(--radius-sm)] border border-[rgba(255,59,79,0.2)]">
                  {error}
                </p>
              )}

              <GlowButton
                type="submit"
                loading={status === 'loading'}
                className="w-full"
              >
                {mode === 'login' ? 'Sign In' : 'Create Account'}
              </GlowButton>

              <p className="text-center text-xs font-mono text-[var(--color-text-dim)]">
                {mode === 'login' ? (
                  <>
                    No account?{' '}
                    <button
                      type="button"
                      onClick={() => { setMode('register'); setEmail(''); setPassword(''); setDisplayName('') }}
                      className="text-[var(--color-primary)] hover:underline"
                    >
                      Register
                    </button>
                  </>
                ) : (
                  <>
                    Have an account?{' '}
                    <button
                      type="button"
                      onClick={() => { setMode('login'); setEmail(''); setPassword(''); setDisplayName('') }}
                      className="text-[var(--color-primary)] hover:underline"
                    >
                      Sign In
                    </button>
                  </>
                )}
              </p>
            </form>
          )}
        </GlassPanel>
      </div>
    </div>
  )
}
