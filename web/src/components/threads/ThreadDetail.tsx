import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useThreadsStore } from '@/stores'
import { TurnCard } from './TurnCard'
import { GlassPanel, GlowButton, Skeleton, Badge } from '@/components/shared'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
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

  return (
    <div className="space-y-4">
      <GlassPanel padding="md">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <p className="text-[var(--color-text)] font-medium">{currentThread.question}</p>
            <div className="flex items-center gap-3 mt-2 text-[10px] font-mono text-[var(--color-text-dim)]">
              <span>{formatDate(currentThread.created_at)}</span>
              <span>{currentThread.thread_id.slice(0, 8)}</span>
            </div>
          </div>
          <Badge variant={statusVariant[currentThread.status] ?? 'default'} size="md">
            {currentThread.status}
          </Badge>
        </div>
      </GlassPanel>

      {currentThread.turns.map((turn, i) => (
        <TurnCard key={i} turn={turn} />
      ))}

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

      <div className="flex justify-center">
        <GlowButton variant="ghost" size="sm" onClick={() => navigate('/threads')}>
          Back to threads
        </GlowButton>
      </div>
    </div>
  )
}
