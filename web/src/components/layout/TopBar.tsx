import { useState, useEffect } from 'react'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores'
import { Badge } from '@/components/shared'

export function TopBar({ onMenuClick }: { onMenuClick?: () => void }) {
  const [healthy, setHealthy] = useState<boolean | null>(null)
  const { user, authRequired, logout } = useAuthStore()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    api.health()
      .then(() => setHealthy(true))
      .catch(() => setHealthy(false))

    const interval = setInterval(() => {
      api.health()
        .then(() => setHealthy(true))
        .catch(() => setHealthy(false))
    }, 30000)

    return () => clearInterval(interval)
  }, [])

  const handleLogout = () => {
    logout()
    window.location.href = '/login'
  }

  const showUserMenu = authRequired && user && user.id !== 'guest'

  return (
    <header className="h-12 flex items-center justify-between px-4 border-b border-[var(--color-border)] bg-[var(--color-surface)] backdrop-blur-[var(--glass-blur)] relative z-20">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="lg:hidden text-[var(--color-text-secondary)] hover:text-[var(--color-text)] p-1"
          aria-label="Toggle menu"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M3 5h14M3 10h14M3 15h14" />
          </svg>
        </button>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div
            className={`w-1.5 h-1.5 rounded-full ${
              healthy === true
                ? 'bg-[var(--color-green)]'
                : healthy === false
                  ? 'bg-[var(--color-red)]'
                  : 'bg-[var(--color-text-dim)]'
            }`}
          />
          <span className="text-[10px] font-mono text-[var(--color-text-dim)]">
            {healthy === true ? 'API OK' : healthy === false ? 'API DOWN' : '...'}
          </span>
        </div>

        {showUserMenu && (
          <div className="relative">
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center gap-2 px-2 py-1 rounded-[var(--radius-sm)] text-xs font-mono text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
            >
              <span className="hidden sm:inline">{user.display_name}</span>
              <Badge variant="default">{user.role}</Badge>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M3 5l3 3 3-3" />
              </svg>
            </button>

            {menuOpen && (
              <>
                {/* Invisible backdrop — closes menu on any outside click */}
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setMenuOpen(false)}
                />
                <div className="absolute right-0 top-full mt-1 w-48 rounded-[var(--radius-md)] bg-[var(--color-surface)] border border-[var(--color-border)] shadow-lg z-50 py-1">
                  <div className="px-3 py-2 border-b border-[var(--color-border)]">
                    <p className="text-xs font-mono text-[var(--color-text)]">{user.display_name}</p>
                    <p className="text-[10px] font-mono text-[var(--color-text-dim)]">{user.email}</p>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-3 py-2 text-xs font-mono text-[var(--color-red)] hover:bg-[var(--color-surface-hover)] transition-colors"
                  >
                    Sign Out
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
