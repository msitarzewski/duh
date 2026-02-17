import { useNavigate } from 'react-router-dom'
import { GlassPanel, Badge } from '@/components/shared'
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

export function ThreadCard({ thread }: { thread: ThreadSummary }) {
  const navigate = useNavigate()

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
          <Badge variant={statusVariant[thread.status] ?? 'default'}>
            {thread.status}
          </Badge>
        </div>
        <div className="mt-2 flex items-center gap-3 text-[10px] font-mono text-[var(--color-text-dim)]">
          <span>{formatDate(thread.created_at)}</span>
          <span>{thread.thread_id.slice(0, 8)}</span>
        </div>
      </GlassPanel>
    </div>
  )
}
