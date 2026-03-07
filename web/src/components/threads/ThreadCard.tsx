import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GlassPanel, Badge } from '@/components/shared'
import { useThreadsStore } from '@/stores'
import type { ThreadSummary } from '@/api/types'

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const statusVariant: Record<string, 'cyan' | 'green' | 'red' | 'default'> = {
  active: 'cyan',
  complete: 'green',
  failed: 'red',
}

const outcomeLabels: Record<string, { label: string; variant: 'green' | 'red' | 'cyan' }> = {
  success: { label: 'Success', variant: 'green' },
  failure: { label: 'Failure', variant: 'red' },
  partial: { label: 'Partial', variant: 'cyan' },
}

export function ThreadCard({ thread }: { thread: ThreadSummary }) {
  const navigate = useNavigate()
  const submitFeedback = useThreadsStore((s) => s.submitFeedback)
  const fetchThreads = useThreadsStore((s) => s.fetchThreads)
  const [submitting, setSubmitting] = useState<string | null>(null)
  const [recorded, setRecorded] = useState(thread.has_outcome ?? false)
  const [outcome, setOutcome] = useState(thread.outcome ?? null)

  const handleFeedback = async (
    e: React.MouseEvent,
    result: 'success' | 'failure' | 'partial',
  ) => {
    e.stopPropagation()
    setSubmitting(result)
    try {
      await submitFeedback(thread.thread_id, result)
      setRecorded(true)
      setOutcome(result)
      fetchThreads()
    } catch {
      // Silently fail — user can retry
    } finally {
      setSubmitting(null)
    }
  }

  const showFeedback = thread.status === 'complete' && !recorded

  return (
    <div onClick={() => navigate(`/threads/${thread.thread_id}`)}>
      <GlassPanel
        variant="interactive"
        padding="sm"
        className="group hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.3)] transition-all duration-200 ease-out"
      >
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm text-[var(--color-text)] line-clamp-2 flex-1 group-hover:text-[var(--color-primary)] transition-colors">
            {thread.question}
          </p>
          <div className="flex items-center gap-1.5 shrink-0">
            {recorded && outcome && outcomeLabels[outcome] && (
              <Badge variant={outcomeLabels[outcome].variant}>
                {outcomeLabels[outcome].label}
              </Badge>
            )}
            <Badge variant={statusVariant[thread.status] ?? 'default'}>
              {thread.status}
            </Badge>
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-3 text-[10px] font-mono text-[var(--color-text-dim)]">
            <span>{formatDate(thread.created_at)}</span>
            <span>{thread.thread_id.slice(0, 8)}</span>
          </div>
          {showFeedback && (
            <div
              className="flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              <FeedbackButton
                label="Pass"
                title="Mark as successful"
                loading={submitting === 'success'}
                disabled={submitting !== null}
                onClick={(e) => handleFeedback(e, 'success')}
                color="green"
              />
              <FeedbackButton
                label="Partial"
                title="Mark as partially correct"
                loading={submitting === 'partial'}
                disabled={submitting !== null}
                onClick={(e) => handleFeedback(e, 'partial')}
                color="cyan"
              />
              <FeedbackButton
                label="Fail"
                title="Mark as failed"
                loading={submitting === 'failure'}
                disabled={submitting !== null}
                onClick={(e) => handleFeedback(e, 'failure')}
                color="red"
              />
            </div>
          )}
        </div>
      </GlassPanel>
    </div>
  )
}

function FeedbackButton({
  label,
  title,
  loading,
  disabled,
  onClick,
  color,
}: {
  label: string
  title: string
  loading: boolean
  disabled: boolean
  onClick: (e: React.MouseEvent) => void
  color: 'green' | 'cyan' | 'red'
}) {
  const colorMap = {
    green: 'text-[var(--color-green)] hover:bg-[rgba(0,255,136,0.1)] border-[rgba(0,255,136,0.2)]',
    cyan: 'text-[var(--color-primary)] hover:bg-[rgba(0,212,255,0.1)] border-[rgba(0,212,255,0.2)]',
    red: 'text-[var(--color-red)] hover:bg-[rgba(255,59,79,0.1)] border-[rgba(255,59,79,0.2)]',
  }

  return (
    <button
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={`px-2 py-0.5 text-[10px] font-mono border rounded-[var(--radius-sm)] transition-colors disabled:opacity-40 ${colorMap[color]}`}
    >
      {loading ? '...' : label}
    </button>
  )
}
