import { lazy, Suspense, useEffect, useMemo } from 'react'
import { useDecisionSpaceStore } from '@/stores'
import { useMediaQuery } from '@/hooks'
import { FilterPanel } from './FilterPanel'
import { TimelineSlider } from './TimelineSlider'
import { ScatterFallback } from './ScatterFallback'
import { Skeleton } from '@/components/shared'

const Scene3D = lazy(() => import('./Scene3D'))

export function DecisionSpace() {
  const {
    decisions, loading, error, filters, timelinePosition,
    fetchDecisions,
  } = useDecisionSpaceStore()

  const isMobile = useMediaQuery('(max-width: 768px)')

  useEffect(() => {
    fetchDecisions()
  }, [fetchDecisions])

  const filteredDecisions = useMemo(() => {
    return decisions.filter((d) => {
      if (filters.categories.length > 0 && d.category && !filters.categories.includes(d.category)) return false
      if (filters.genera.length > 0 && d.genus && !filters.genera.includes(d.genus)) return false
      if (filters.outcomes.length > 0 && d.outcome && !filters.outcomes.includes(d.outcome)) return false
      if (d.confidence < filters.confidenceMin || d.confidence > filters.confidenceMax) return false
      return true
    })
  }, [decisions, filters])

  if (loading) {
    return <Skeleton variant="rect" height="400px" />
  }

  if (error) {
    return (
      <div className="text-center text-[var(--color-red)] text-sm font-mono py-12">
        {error}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="flex-1 min-h-[400px] rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
          {isMobile ? (
            <div className="p-4">
              <ScatterFallback decisions={filteredDecisions} />
            </div>
          ) : (
            <Suspense fallback={<Skeleton variant="rect" height="400px" />}>
              <Scene3D decisions={filteredDecisions} timelinePosition={timelinePosition} />
            </Suspense>
          )}
        </div>
        <div className="w-full lg:w-56">
          <FilterPanel />
        </div>
      </div>
      <TimelineSlider />
    </div>
  )
}
