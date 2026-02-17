import { NavLink } from 'react-router-dom'

const navItems = [
  { path: '/', label: 'Consensus', icon: '\u2B21' },
  { path: '/threads', label: 'Threads', icon: '\u2261' },
  { path: '/space', label: 'Decision Space', icon: '\u25CE' },
  { path: '/preferences', label: 'Preferences', icon: '\u2699' },
]

export function Sidebar({ onClose }: { onClose?: () => void }) {
  return (
    <aside className="w-56 h-full flex flex-col bg-[var(--color-surface)] backdrop-blur-[var(--glass-blur)] border-r border-[var(--color-border)]">
      <div className="px-5 py-6 border-b border-[var(--color-border)]">
        <h1 className="font-mono text-xl font-bold text-[var(--color-primary)] tracking-wider">
          duh
        </h1>
        <p className="text-[10px] text-[var(--color-text-dim)] font-mono mt-0.5">
          consensus engine
        </p>
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
        v0.4.0
      </div>
    </aside>
  )
}
