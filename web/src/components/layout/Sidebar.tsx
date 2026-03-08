import { NavLink, useNavigate } from 'react-router-dom'
import { useConsensusStore } from '@/stores'

const navItems = [
  { path: '/', label: 'Consensus', icon: '\u2B21' },
  { path: '/threads', label: 'Threads', icon: '\u2261' },
  { path: '/space', label: 'Decision Space', icon: '\u25CE' },
  { path: '/calibration', label: 'Calibration', icon: '\u25C9' },
  { path: '/preferences', label: 'Preferences', icon: '\u2699' },
]

export function Sidebar({ onClose, onToggleSidebar }: { onClose?: () => void; onToggleSidebar?: () => void }) {
  const navigate = useNavigate()
  const reset = useConsensusStore((s) => s.reset)

  const handleNewQuestion = () => {
    reset()
    navigate('/')
    onClose?.()
  }

  return (
    <aside className="w-56 h-full flex flex-col bg-[var(--color-surface)] backdrop-blur-[var(--glass-blur)] border-r border-[var(--color-border)]">
      <div className="px-3 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
        <div>
          <h1 className="font-mono text-lg font-bold text-[var(--color-primary)] tracking-wider leading-none">
            duh
          </h1>
          <p className="text-[9px] text-[var(--color-text-dim)] font-mono">
            consensus engine
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleNewQuestion}
            className="p-1.5 rounded-[var(--radius-sm)] text-[var(--color-text-dim)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
            aria-label="New question"
          >
            {/* Heroicons: pencil-square (outline, 24px scaled to 18) */}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zM19.5 7.125L16.862 4.487" />
              <path d="M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
            </svg>
          </button>
          {onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              className="p-1.5 rounded-[var(--radius-sm)] text-[var(--color-text-dim)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
              aria-label="Hide sidebar"
            >
              <svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="1.5" y="2" width="13" height="12" rx="2" />
                <path d="M5.5 2v12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-[var(--radius-sm)] text-sm transition-all duration-200 ease-out ${
                isActive
                  ? 'bg-[var(--color-primary-glow)] text-[var(--color-primary)] border border-[var(--color-border-active)] shadow-[0_0_12px_rgba(0,212,255,0.06)]'
                  : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] hover:pl-3.5 border border-transparent'
              }`
            }
          >
            <span className="font-mono text-base w-5 text-center">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-3 border-t border-[var(--color-border)] text-[10px] text-[var(--color-text-dim)] font-mono">
        v0.6.0
      </div>
    </aside>
  )
}
