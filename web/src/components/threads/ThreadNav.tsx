import { GlassPanel, Disclosure } from '@/components/shared'
import { useConsensusStore } from '@/stores/consensus'
import { useThreadsStore } from '@/stores/threads'
import type { Citation } from '@/api/types'

type TaggedCitation = Citation & { role: 'propose' | 'challenge' | 'revise' }

function displayHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

const ROLE_MAP: Record<string, TaggedCitation['role']> = {
  proposer: 'propose',
  challenger: 'challenge',
  reviser: 'revise',
}

function shortModel(model: string): string {
  const parts = model.split(':')
  return parts.length > 1 ? parts[1]! : model
}

export function ThreadNav() {
  const thread = useThreadsStore((s) => s.currentThread)

  if (!thread || thread.turns.length === 0) return null

  // Collect all citations from contributions, grouped by domain
  const domainGroups = (() => {
    const seen = new Set<string>()
    const tagged: TaggedCitation[] = []
    for (const turn of thread.turns) {
      for (const c of turn.contributions) {
        const role = ROLE_MAP[c.role] ?? 'propose'
        for (const cit of c.citations ?? []) {
          if (!seen.has(cit.url)) {
            seen.add(cit.url)
            tagged.push({ ...cit, role })
          }
        }
      }
    }
    const groups = new Map<string, TaggedCitation[]>()
    for (const c of tagged) {
      const domain = displayHost(c.url)
      const list = groups.get(domain) ?? []
      list.push(c)
      groups.set(domain, list)
    }
    return [...groups.entries()].sort((a, b) => b[1].length - a[1].length)
  })()

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <GlassPanel padding="sm">
      <span className="font-mono text-xs text-[var(--color-primary)] font-semibold block mb-3">
        PROGRESS
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
          const proposer = turn.contributions.find((c) => c.role === 'proposer')
          const challengers = turn.contributions.filter((c) => c.role === 'challenger')
          const reviser = turn.contributions.find((c) => c.role === 'reviser')

          return (
            <div key={turn.round_number}>
              <button
                className="font-mono text-[10px] text-[var(--color-text-dim)] hover:text-[var(--color-text)] transition-colors mb-1"
                onClick={() => scrollTo(`thread-round-${turn.round_number}`)}
              >
                ROUND {turn.round_number}
              </button>
              <div className="space-y-0.5 pl-2">
                {proposer && (
                  <button
                    className="flex items-center gap-1.5 w-full text-left text-[10px] font-mono text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors py-0.5"
                    onClick={() => scrollTo(`thread-round-${turn.round_number}-propose`)}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-green)] shrink-0" />
                    PROPOSE
                  </button>
                )}
                {challengers.map((ch, i) => (
                  <button
                    key={i}
                    className="flex items-center gap-1.5 w-full text-left text-[10px] font-mono text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors py-0.5"
                    onClick={() => scrollTo(`thread-round-${turn.round_number}-challenge`)}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-green)] shrink-0" />
                    <span className="text-[var(--color-amber)] truncate">{shortModel(ch.model_ref)}</span>
                  </button>
                ))}
                {reviser && (
                  <button
                    className="flex items-center gap-1.5 w-full text-left text-[10px] font-mono text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors py-0.5"
                    onClick={() => scrollTo(`thread-round-${turn.round_number}-revise`)}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-green)] shrink-0" />
                    REVISE
                  </button>
                )}
              </div>
            </div>
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

        {domainGroups.length > 0 && (
          <div className="pt-2 mt-2 border-t border-[var(--color-border)]">
            <Disclosure
              header={
                <span className="font-mono text-[10px] text-[var(--color-text-dim)] uppercase tracking-wide">
                  Sources ({domainGroups.reduce((sum, [, cs]) => sum + cs.length, 0)})
                </span>
              }
              defaultOpen={false}
            >
              <div className="space-y-1 mt-1">
                {domainGroups.map(([domain, citations]) => (
                  <Disclosure
                    key={domain}
                    header={
                      <span className="font-mono text-[10px] text-[var(--color-text-secondary)] truncate">
                        {domain} ({citations.length})
                      </span>
                    }
                    defaultOpen={false}
                  >
                    <ul className="space-y-1 pl-2">
                      {citations.map((c, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <span className={`font-mono text-[8px] font-semibold mt-0.5 shrink-0 ${
                            c.role === 'propose' ? 'text-[var(--color-green)]' :
                            c.role === 'challenge' ? 'text-[var(--color-amber)]' :
                            'text-[var(--color-blue)]'
                          }`}>
                            {c.role === 'propose' ? 'P' : c.role === 'challenge' ? 'C' : 'R'}
                          </span>
                          <a
                            href={c.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-[var(--color-blue)] hover:underline break-all leading-tight"
                          >
                            {c.title || c.url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </Disclosure>
                ))}
              </div>
            </Disclosure>
          </div>
        )}

        <FollowupSection followups={thread.followups} />
      </nav>
    </GlassPanel>
  )
}

function FollowupSection({ followups }: { followups?: string[] }) {
  const submitQuestion = useConsensusStore((s) => s.submitQuestion)

  if (!followups || followups.length === 0) return null

  return (
    <div className="pt-2 mt-2 border-t border-[var(--color-border)]">
      <Disclosure
        header={
          <span className="font-mono text-[10px] text-[var(--color-text-dim)] uppercase tracking-wide">
            Follow up ({followups.length})
          </span>
        }
        defaultOpen
      >
        <ul className="space-y-2 mt-1.5">
          {followups.map((q, i) => (
            <li key={i}>
              <button
                className="text-left text-[11px] leading-snug text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors"
                onClick={() => submitQuestion(q)}
              >
                {q}
              </button>
            </li>
          ))}
        </ul>
      </Disclosure>
    </div>
  )
}
