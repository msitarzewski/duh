import { useConsensusStore } from '@/stores'
import { GlassPanel, GlowButton } from '@/components/shared'
import { QuestionInput } from './QuestionInput'
import { PhaseCard } from './PhaseCard'
import { ConsensusComplete } from './ConsensusComplete'
import { CostTicker } from './CostTicker'

export function ConsensusPanel() {
  const {
    status, error, currentPhase, currentRound, rounds,
    decision, confidence, rigor, dissent, cost,
    startConsensus, reset,
  } = useConsensusStore()

  const isActive = status === 'connecting' || status === 'streaming'

  return (
    <div className="space-y-4">
      <QuestionInput
        onSubmit={(q, r, p, ms) => startConsensus(q, r, p, ms)}
        disabled={isActive}
      />

      {status === 'error' && error && (
        <GlassPanel className="border-[var(--color-red)]/30" padding="sm">
          <div className="flex items-center justify-between">
            <span className="text-[var(--color-red)] text-sm font-mono">{error}</span>
            <GlowButton variant="ghost" size="sm" onClick={reset}>Dismiss</GlowButton>
          </div>
        </GlassPanel>
      )}

      {(isActive || status === 'complete') && rounds.length > 0 && (
        <div className="space-y-6">
          {rounds.map((round) => (
            <div key={round.round} className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-[var(--color-text-dim)]">
                  ROUND {round.round}
                </span>
                {isActive && round.round === currentRound && (
                  <CostTicker cost={cost} />
                )}
              </div>

              {round.proposer && (
                <PhaseCard
                  phase="PROPOSE"
                  model={round.proposer}
                  content={round.proposal}
                  isActive={isActive && currentPhase === 'PROPOSE' && round.round === currentRound}
                />
              )}

              {(round.challengers.length > 0 || round.challenges.length > 0) && (
                <PhaseCard
                  phase="CHALLENGE"
                  models={round.challengers}
                  challenges={round.challenges}
                  isActive={isActive && currentPhase === 'CHALLENGE' && round.round === currentRound}
                />
              )}

              {round.reviser && (
                <PhaseCard
                  phase="REVISE"
                  model={round.reviser}
                  content={round.revision}
                  isActive={isActive && currentPhase === 'REVISE' && round.round === currentRound}
                />
              )}

              {round.confidence !== null && (
                <div className="flex items-center gap-3 text-xs font-mono text-[var(--color-text-dim)]">
                  <span>Confidence: {(round.confidence * 100).toFixed(0)}%</span>
                  {round.rigor !== null && <span>Rigor: {(round.rigor * 100).toFixed(0)}%</span>}
                  {round.dissent && <span className="text-[var(--color-amber)]">Dissent noted</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {status === 'complete' && decision && confidence !== null && (
        <ConsensusComplete
          decision={decision}
          confidence={confidence}
          rigor={rigor ?? 0}
          dissent={dissent}
          cost={cost}
        />
      )}

      {isActive && (
        <div className="flex justify-center">
          <GlowButton variant="danger" size="sm" onClick={reset}>
            Cancel
          </GlowButton>
        </div>
      )}

      {status === 'complete' && (
        <div className="flex justify-center">
          <GlowButton variant="ghost" size="sm" onClick={reset}>
            New Question
          </GlowButton>
        </div>
      )}
    </div>
  )
}
