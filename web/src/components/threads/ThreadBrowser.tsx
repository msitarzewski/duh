import { useEffect } from 'react'
import { useThreadsStore } from '@/stores'
import { ThreadSearch } from './ThreadSearch'
import { ThreadFilters } from './ThreadFilters'
import { ThreadCard } from './ThreadCard'
import { GlassPanel, Skeleton, GlowButton } from '@/components/shared'
import type { ThreadSummary } from '@/api/types'

export function ThreadBrowser() {
  const {
    threads, loading, error, page, pageSize,
    searchResults, searchQuery, searchLoading,
    fetchThreads, setPage,
  } = useThreadsStore()

  useEffect(() => {
    fetchThreads()
  }, [fetchThreads])

  const displayThreads: ThreadSummary[] = searchQuery
    ? searchResults.map((r) => ({
        thread_id: r.thread_id,
        question: r.question,
        status: 'complete',
        created_at: new Date().toISOString(),
      }))
    : threads

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <ThreadFilters />
        <div className="w-full sm:w-64">
          <ThreadSearch />
        </div>
      </div>

      {error && (
        <GlassPanel className="border-[var(--color-red)]/30" padding="sm">
          <span className="text-[var(--color-red)] text-sm font-mono">{error}</span>
        </GlassPanel>
      )}

      {(loading || searchLoading) && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rect" height="72px" />
          ))}
        </div>
      )}

      {!loading && !searchLoading && displayThreads.length === 0 && (
        <GlassPanel padding="lg">
          <p className="text-center text-[var(--color-text-dim)] text-sm font-mono">
            {searchQuery ? 'No results found' : 'No threads yet'}
          </p>
        </GlassPanel>
      )}

      <div className="space-y-2">
        {displayThreads.map((t) => (
          <ThreadCard key={t.thread_id} thread={t} />
        ))}
      </div>

      {!searchQuery && threads.length > 0 && (
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono text-[var(--color-text-dim)]">
            Page {page + 1}
          </span>
          <div className="flex gap-2">
            <GlowButton
              variant="ghost"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              Prev
            </GlowButton>
            <GlowButton
              variant="ghost"
              size="sm"
              disabled={threads.length < pageSize}
              onClick={() => setPage(page + 1)}
            >
              Next
            </GlowButton>
          </div>
        </div>
      )}
    </div>
  )
}
