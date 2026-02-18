import { GlassPanel } from '@/components/shared'
import { useThreadsStore } from '@/stores/threads'

export function ThreadNav() {
  const thread = useThreadsStore((s) => s.currentThread)

  if (!thread || thread.turns.length === 0) return null

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <GlassPanel padding="sm">
      <span className="font-mono text-xs text-[var(--color-primary)] font-semibold block mb-3">
        ROUNDS
      </span>
      <nav className="space-y-1.5">
        {thread.status === 'complete' && thread.turns.some((t) => t.decision) && (
          <button
            className="flex items-center gap-1.5 w-full text-left text-[10px] font-mono text-[var(--color-green)] hover:text-[var(--color-text)] transition-colors pb-1 mb-1 border-b border-[var(--color-border)]"
            onClick={() => scrollTo('thread-decision')}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-green)] shrink-0" />
            DECISION
          </button>
        )}

        {thread.turns.map((turn) => {
          const hasDecision = !!turn.decision
          return (
            <button
              key={turn.round_number}
              className="flex items-center gap-1.5 w-full text-left text-[10px] font-mono text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors py-0.5"
              onClick={() => scrollTo(`thread-round-${turn.round_number}`)}
            >
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${hasDecision ? 'bg-[var(--color-green)]' : 'bg-[var(--color-text-dim)]/30'}`} />
              ROUND {turn.round_number}
              {hasDecision && (
                <span className="text-[var(--color-green)] ml-auto">
                  {Math.round(turn.decision!.confidence * 100)}%
                </span>
              )}
            </button>
          )
        })}

        {thread.status === 'complete' && (
          <button
            className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--color-green)] hover:text-[var(--color-text)] transition-colors pt-1 border-t border-[var(--color-border)]"
            onClick={() => scrollTo('thread-feedback')}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-green)] shrink-0" />
            FEEDBACK
          </button>
        )}
      </nav>
    </GlassPanel>
  )
}
