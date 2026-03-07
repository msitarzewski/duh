import { useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { GlassPanel, GlowButton } from '@/components/shared'
import { api } from '@/api/client'

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: { preventDefault: () => void }) => {
    e.preventDefault()
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    setLoading(true)
    setError(null)
    setMessage(null)
    try {
      const res = await api.resetPassword({ token, new_password: password })
      setMessage(res.message)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const inputClass = "w-full px-3 py-2 rounded-[var(--radius-sm)] bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] font-mono text-sm focus:outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)] transition-colors"

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] p-4">
        <GlassPanel glow="subtle" padding="lg">
          <p className="text-sm font-mono text-[var(--color-text)]">
            Invalid or missing reset link.
          </p>
          <Link
            to="/login"
            className="block mt-4 text-center text-xs font-mono text-[var(--color-primary)] hover:underline"
          >
            Back to Sign In
          </Link>
        </GlassPanel>
      </div>
    )
  }

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
          {message ? (
            <div className="space-y-4 text-center">
              <p className="text-xs font-mono text-[var(--color-green)] bg-[rgba(0,200,100,0.1)] px-3 py-2 rounded-[var(--radius-sm)] border border-[rgba(0,200,100,0.2)]">
                {message}
              </p>
              <Link
                to="/login"
                className="inline-block text-xs font-mono text-[var(--color-primary)] hover:underline"
              >
                Sign In
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <h2 className="text-lg font-mono font-semibold text-[var(--color-text)] text-center">
                Set New Password
              </h2>

              <div>
                <label className="block text-xs font-mono text-[var(--color-text-secondary)] mb-1">
                  New Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className={inputClass}
                  placeholder="••••••••"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--color-text-secondary)] mb-1">
                  Confirm Password
                </label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  minLength={8}
                  className={inputClass}
                  placeholder="••••••••"
                />
              </div>

              {error && (
                <p className="text-xs font-mono text-[var(--color-red)] bg-[rgba(255,59,79,0.1)] px-3 py-2 rounded-[var(--radius-sm)] border border-[rgba(255,59,79,0.2)]">
                  {error}
                </p>
              )}

              <GlowButton
                type="submit"
                loading={loading}
                className="w-full"
              >
                Reset Password
              </GlowButton>

              <p className="text-center text-xs font-mono text-[var(--color-text-dim)]">
                <Link
                  to="/login"
                  className="text-[var(--color-primary)] hover:underline"
                >
                  Back to Sign In
                </Link>
              </p>
            </form>
          )}
        </GlassPanel>
      </div>
    </div>
  )
}
