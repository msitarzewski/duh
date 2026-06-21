import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useThreadsStore } from '@/stores'
import { GlassPanel, GlowButton, Skeleton, Badge, ExportMenu, Markdown, Disclosure } from '@/components/shared'
import { ConfidenceMeter } from '@/components/consensus/ConfidenceMeter'
import { DissentBanner } from '@/components/consensus/DissentBanner'
import { PhaseCard } from '@/components/consensus/PhaseCard'
import { CostTicker } from '@/components/consensus/CostTicker'
import type { Turn } from '@/api/types'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function turnToPhaseData(turn: Turn) {
  const proposer = turn.contributions.find((c) => c.role === 'proposer')
  const challengers = turn.contributions.filter((c) => c.role === 'challenger')
  const reviser = turn.contributions.find((c) => c.role === 'reviser')
  return {
    proposer: proposer
      ? { model: proposer.model_ref, content: proposer.content, citations: proposer.citations ?? null }
      : null,
    challenges: challengers.map((c) => ({ model: c.model_ref, content: c.content, citations: c.citations ?? null })),
    challengerModels: challengers.map((c) => c.model_ref),
    reviser: reviser
      ? { model: reviser.model_ref, content: reviser.content, citations: reviser.citations ?? null }
      : null,
  }
}

const statusVariant: Record<string, 'cyan' | 'green' | 'red' | 'default'> = {
  active: 'cyan',
  complete: 'green',
  failed: 'red',
}

export function ThreadDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentThread, detailLoading, detailError, fetchThread, submitFeedback } = useThreadsStore()
  const [feedbackSent, setFeedbackSent] = useState(false)

  useEffect(() => {
    if (id) fetchThread(id)
  }, [id, fetchThread])

  if (detailLoading) {
    return (
      <div className="space-y-4">
        <Skeleton variant="rect" height="80px" />
        <Skeleton variant="rect" height="200px" />
      </div>
    )
  }

  if (detailError) {
    return (
      <GlassPanel className="border-[var(--color-red)]/30" padding="md">
        <p className="text-[var(--color-red)] text-sm font-mono">{detailError}</p>
        <GlowButton variant="ghost" size="sm" onClick={() => navigate('/threads')} className="mt-3">
          Back to threads
        </GlowButton>
      </GlassPanel>
    )
  }

  if (!currentThread) return null

  const handleFeedback = async (result: 'success' | 'failure' | 'partial') => {
    await submitFeedback(currentThread.thread_id, result)
    setFeedbackSent(true)
  }

  // Find the final decision from the last turn
  const lastTurn = currentThread.turns[currentThread.turns.length - 1]
  const finalDecision = currentThread.status === 'complete' && lastTurn?.decision ? lastTurn.decision : null

  return (
    <div className="space-y-4">
      <GlassPanel padding="md" className="relative z-10 !bg-[var(--color-surface-solid)]">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <p className="text-[var(--color-text)] font-medium">{currentThread.question}</p>
            <div className="flex items-center gap-3 mt-2 text-[10px] font-mono text-[var(--color-text-dim)]">
              <span>{formatDate(currentThread.created_at)}</span>
              <span>{currentThread.thread_id.slice(0, 8)}</span>
              {currentThread.usage && (
                <CostTicker
                  cost={currentThread.usage.cost_usd}
                  usage={currentThread.usage}
                />
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Badge variant={statusVariant[currentThread.status] ?? 'default'} size="md">
              {currentThread.status}
            </Badge>
            {currentThread.status === 'complete' && <ExportMenu thread={currentThread} />}
          </div>
        </div>
      </GlassPanel>

      {finalDecision && (
        <div id="thread-decision">
          <GlassPanel glow="strong" padding="lg" className="animate-fade-in-up">
            <Disclosure
              header={
                <>
                  <span className="font-mono text-xs text-[var(--color-green)] font-semibold">DECISION</span>
                  <div className="flex items-center gap-2 ml-auto">
                    <ConfidenceMeter value={finalDecision.confidence} size={48} label="Confidence" />
                    <ConfidenceMeter value={finalDecision.rigor} size={36} label="Rigor" />
                  </div>
                </>
              }
              defaultOpen
            >
              <div className="text-sm">
                <Markdown>{finalDecision.content}</Markdown>
              </div>
              {finalDecision.dissent && (
                <div className="mt-4">
                  <DissentBanner dissent={finalDecision.dissent} defaultOpen={false} />
                </div>
              )}
            </Disclosure>
          </GlassPanel>
        </div>
      )}

      <div id="thread-feedback">
        {currentThread.status === 'complete' && !feedbackSent && (
          <GlassPanel padding="sm">
            <p className="text-xs font-mono text-[var(--color-text-dim)] mb-2">How was this decision?</p>
            <div className="flex gap-2">
              <GlowButton variant="ghost" size="sm" onClick={() => handleFeedback('success')}>
                Success
              </GlowButton>
              <GlowButton variant="ghost" size="sm" onClick={() => handleFeedback('partial')}>
                Partial
              </GlowButton>
              <GlowButton variant="danger" size="sm" onClick={() => handleFeedback('failure')}>
                Failure
              </GlowButton>
            </div>
          </GlassPanel>
        )}

        {feedbackSent && (
          <p className="text-center text-xs font-mono text-[var(--color-green)]">Feedback recorded</p>
        )}
      </div>

      <div className="space-y-6">
        {currentThread.turns.map((turn) => {
          const phases = turnToPhaseData(turn)
          return (
            <div key={turn.round_number} id={`thread-round-${turn.round_number}`} className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-[var(--color-text-dim)]">
                  ROUND {turn.round_number}
                </span>
              </div>

              {phases.proposer && (
                <div id={`thread-round-${turn.round_number}-propose`}>
                  <PhaseCard
                    phase="PROPOSE"
                    model={phases.proposer.model}
                    content={phases.proposer.content}
                    collapsible
                    defaultOpen={false}
                    citations={phases.proposer.citations}
                  />
                </div>
              )}

              {phases.challenges.length > 0 && (
                <div id={`thread-round-${turn.round_number}-challenge`}>
                  <PhaseCard
                    phase="CHALLENGE"
                    models={phases.challengerModels}
                    challenges={phases.challenges}
                    collapsible
                    defaultOpen={false}
                  />
                </div>
              )}

              {phases.reviser && (
                <div id={`thread-round-${turn.round_number}-revise`}>
                  <PhaseCard
                    phase="REVISE"
                    model={phases.reviser.model}
                    content={phases.reviser.content}
                    collapsible
                    defaultOpen={false}
                    citations={phases.reviser.citations}
                  />
                </div>
              )}

              {turn.decision && (
                <div className="flex items-center gap-3 text-xs font-mono text-[var(--color-text-dim)]">
                  <span>Confidence: {(turn.decision.confidence * 100).toFixed(0)}%</span>
                  <span>Rigor: {(turn.decision.rigor * 100).toFixed(0)}%</span>
                  {turn.decision.dissent && <span className="text-[var(--color-amber)]">Dissent noted</span>}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="flex justify-center">
        <GlowButton variant="ghost" size="sm" onClick={() => navigate('/threads')}>
          Back to threads
        </GlowButton>
      </div>
    </div>
  )
}
