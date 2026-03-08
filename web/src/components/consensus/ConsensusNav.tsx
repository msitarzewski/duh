import { GlassPanel, Disclosure } from '@/components/shared'
import { useConsensusStore } from '@/stores/consensus'
import type { Citation } from '@/api/types'

type PhaseStatus = 'complete' | 'active' | 'pending'

function getPhaseStatus(
  roundNum: number,
  phase: string,
  currentRound: number,
  currentPhase: string | null,
  isStreaming: boolean,
  roundData: { proposal: string | null; challenges: { model: string; content: string }[]; revision: string | null },
): PhaseStatus {
  if (!isStreaming) {
    if (phase === 'PROPOSE' && roundData.proposal) return 'complete'
    if (phase === 'CHALLENGE' && roundData.challenges.length > 0) return 'complete'
    if (phase === 'REVISE' && roundData.revision) return 'complete'
    return 'pending'
  }

  if (roundNum < currentRound) return 'complete'
  if (roundNum > currentRound) return 'pending'

  const phases = ['PROPOSE', 'CHALLENGE', 'REVISE', 'COMMIT']
  const currentIdx = currentPhase ? phases.indexOf(currentPhase) : -1
  const phaseIdx = phases.indexOf(phase)

  if (phaseIdx < currentIdx) return 'complete'
  if (phaseIdx === currentIdx) return 'active'
  return 'pending'
}

function StatusDot({ status }: { status: PhaseStatus }) {
  if (status === 'active') {
    return <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse-glow shrink-0" />
  }
  if (status === 'complete') {
    return <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-green)] shrink-0" />
  }
  return <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-dim)]/30 shrink-0" />
}

function displayHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function shortModel(model: string): string {
  const parts = model.split(':')
  return parts.length > 1 ? parts[1]! : model
}

export function ConsensusNav() {
  const { status, rounds, currentRound, currentPhase } = useConsensusStore()

  if (rounds.length === 0) return null

  const isStreaming = status === 'connecting' || status === 'streaming'
  const isComplete = status === 'complete'

  // Collect all citations with their phase role, grouped by domain
  type TaggedCitation = Citation & { role: 'propose' | 'challenge' | 'revise' }
  const domainGroups = (() => {
    const seen = new Set<string>()
    const tagged: TaggedCitation[] = []
    for (const round of rounds) {
      for (const c of round.proposalCitations ?? []) {
        if (!seen.has(c.url)) { seen.add(c.url); tagged.push({ ...c, role: 'propose' }) }
      }
      for (const ch of round.challenges) {
        for (const c of ch.citations ?? []) {
          if (!seen.has(c.url)) { seen.add(c.url); tagged.push({ ...c, role: 'challenge' }) }
        }
      }
    }
    // Group by hostname
    const groups = new Map<string, TaggedCitation[]>()
    for (const c of tagged) {
      const domain = displayHost(c.url)
      const list = groups.get(domain) ?? []
      list.push(c)
      groups.set(domain, list)
    }
    // Sort groups by citation count descending
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
      <nav className="space-y-3">
        {isComplete && (
          <button
            className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--color-green)] hover:text-[var(--color-text)] transition-colors pb-1 mb-1 border-b border-[var(--color-border)]"
            onClick={() => scrollTo('consensus-complete')}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-green)] shrink-0" />
            DECISION
          </button>
        )}

        {rounds.map((round) => {
          const challengeStatus = getPhaseStatus(round.round, 'CHALLENGE', currentRound, currentPhase, isStreaming, round)

          return (
            <div key={round.round}>
              <button
                className="font-mono text-[10px] text-[var(--color-text-dim)] hover:text-[var(--color-text)] transition-colors mb-1"
                onClick={() => scrollTo(`consensus-round-${round.round}`)}
              >
                ROUND {round.round}
              </button>
              <div className="space-y-0.5 pl-2">
                {round.proposer && (
                  <button
                    className="flex items-center gap-1.5 w-full text-left text-[10px] font-mono text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors py-0.5"
                    onClick={() => scrollTo(`consensus-round-${round.round}-propose`)}
                  >
                    <StatusDot status={getPhaseStatus(round.round, 'PROPOSE', currentRound, currentPhase, isStreaming, round)} />
                    PROPOSE
                  </button>
                )}
                {round.challenges.length > 0 ? (
                  round.challenges.map((ch, i) => (
                    <button
                      key={i}
                      className="flex items-center gap-1.5 w-full text-left text-[10px] font-mono text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors py-0.5"
                      onClick={() => scrollTo(`consensus-round-${round.round}-challenge`)}
                    >
                      <StatusDot status={challengeStatus} />
                      <span className="text-[var(--color-amber)] truncate">{shortModel(ch.model)}</span>
                    </button>
                  ))
                ) : round.challengers.length > 0 ? (
                  round.challengers.map((model, i) => (
                    <button
                      key={i}
                      className="flex items-center gap-1.5 w-full text-left text-[10px] font-mono text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors py-0.5"
                      onClick={() => scrollTo(`consensus-round-${round.round}-challenge`)}
                    >
                      <StatusDot status={challengeStatus} />
                      <span className="text-[var(--color-amber)] truncate">{shortModel(model)}</span>
                    </button>
                  ))
                ) : null}
                {round.reviser && (
                  <button
                    className="flex items-center gap-1.5 w-full text-left text-[10px] font-mono text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors py-0.5"
                    onClick={() => scrollTo(`consensus-round-${round.round}-revise`)}
                  >
                    <StatusDot status={getPhaseStatus(round.round, 'REVISE', currentRound, currentPhase, isStreaming, round)} />
                    REVISE
                  </button>
                )}
              </div>
            </div>
          )
        })}

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

      </nav>
    </GlassPanel>
  )
}
