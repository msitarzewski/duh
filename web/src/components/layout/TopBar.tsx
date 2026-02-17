import { useState, useEffect } from 'react'
import { api } from '@/api/client'

export function TopBar({ onMenuClick }: { onMenuClick?: () => void }) {
  const [healthy, setHealthy] = useState<boolean | null>(null)

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

  return (
    <header className="h-12 flex items-center justify-between px-4 border-b border-[var(--color-border)] bg-[var(--color-surface)] backdrop-blur-[var(--glass-blur)]">
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
      </div>
    </header>
  )
}
