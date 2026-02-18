import { useEffect } from 'react'
import { useCalibrationStore } from '@/stores'

function eceRating(ece: number): { label: string; color: string } {
  if (ece < 0.05) return { label: 'Excellent', color: 'var(--color-success, #22c55e)' }
  if (ece < 0.1) return { label: 'Good', color: 'var(--color-primary)' }
  if (ece < 0.2) return { label: 'Fair', color: 'var(--color-warning, #eab308)' }
  return { label: 'Poor', color: 'var(--color-error, #ef4444)' }
}

export function CalibrationDashboard() {
  const {
    buckets,
    totalDecisions,
    totalWithOutcomes,
    overallAccuracy,
    ece,
    loading,
    error,
    fetchCalibration,
  } = useCalibrationStore()

  useEffect(() => {
    fetchCalibration()
  }, [fetchCalibration])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--color-text-dim)]">
        Loading calibration data...
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20 text-[var(--color-error,#ef4444)]">
        Error: {error}
      </div>
    )
  }

  const rating = eceRating(ece)

  return (
    <div className="space-y-6 max-w-4xl">
      <h2 className="text-xl font-bold text-[var(--color-text)]">
        Confidence Calibration
      </h2>
      <p className="text-sm text-[var(--color-text-secondary)]">
        Are confidence scores accurate? Compare predicted confidence against actual
        outcomes.
      </p>

      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Decisions" value={String(totalDecisions)} />
        <MetricCard label="With Outcomes" value={String(totalWithOutcomes)} />
        <MetricCard
          label="Overall Accuracy"
          value={totalWithOutcomes > 0 ? `${(overallAccuracy * 100).toFixed(1)}%` : '-'}
        />
        <MetricCard
          label="ECE"
          value={totalWithOutcomes > 0 ? ece.toFixed(4) : '-'}
          sublabel={totalWithOutcomes > 0 ? rating.label : undefined}
          sublabelColor={totalWithOutcomes > 0 ? rating.color : undefined}
        />
      </div>

      {totalWithOutcomes === 0 && (
        <div className="text-center py-12 text-[var(--color-text-dim)] text-sm">
          No outcomes recorded yet. Use{' '}
          <code className="bg-[var(--color-surface-hover)] px-1.5 py-0.5 rounded text-xs">
            duh feedback
          </code>{' '}
          to record outcomes for your decisions.
        </div>
      )}

      {totalWithOutcomes > 0 && (
        <>
          {/* Calibration chart */}
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-md)] p-5">
            <h3 className="text-sm font-semibold text-[var(--color-text)] mb-4">
              Calibration Chart
            </h3>
            <div className="space-y-2">
              {buckets.map((b) => {
                const lo = Math.round(b.range_lo * 100)
                const hi = Math.round(b.range_hi * 100)
                const label = `${lo}-${hi}%`
                const accWidth =
                  b.with_outcomes > 0 ? (b.accuracy * 100).toFixed(0) : '0'
                const confWidth = (b.mean_confidence * 100).toFixed(0)
                return (
                  <div key={lo} className="flex items-center gap-3 text-xs">
                    <span className="w-14 text-right text-[var(--color-text-dim)] font-mono">
                      {label}
                    </span>
                    <div className="flex-1 relative h-5">
                      {/* Accuracy bar */}
                      {b.with_outcomes > 0 && (
                        <div
                          className="absolute inset-y-0 rounded-sm"
                          style={{
                            width: `${accWidth}%`,
                            backgroundColor: 'var(--color-primary)',
                            opacity: 0.7,
                          }}
                        />
                      )}
                      {/* Perfect calibration line */}
                      <div
                        className="absolute top-0 bottom-0 w-px"
                        style={{
                          left: `${confWidth}%`,
                          backgroundColor: 'var(--color-text-dim)',
                          opacity: 0.5,
                        }}
                      />
                    </div>
                    <span className="w-20 text-[var(--color-text-secondary)] font-mono">
                      {b.with_outcomes > 0
                        ? `${(b.accuracy * 100).toFixed(0)}% (n=${b.with_outcomes})`
                        : '-'}
                    </span>
                  </div>
                )
              })}
            </div>
            <div className="flex items-center gap-4 mt-3 text-[10px] text-[var(--color-text-dim)]">
              <span className="flex items-center gap-1">
                <span
                  className="inline-block w-3 h-2 rounded-sm"
                  style={{ backgroundColor: 'var(--color-primary)', opacity: 0.7 }}
                />
                Actual accuracy
              </span>
              <span className="flex items-center gap-1">
                <span
                  className="inline-block w-px h-3"
                  style={{ backgroundColor: 'var(--color-text-dim)' }}
                />
                Expected (mean confidence)
              </span>
            </div>
          </div>

          {/* Bucket table */}
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-md)] p-5 overflow-x-auto">
            <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
              Bucket Details
            </h3>
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-[var(--color-text-dim)] border-b border-[var(--color-border)]">
                  <th className="text-left py-2 pr-3">Range</th>
                  <th className="text-right py-2 px-2">Count</th>
                  <th className="text-right py-2 px-2">Outcomes</th>
                  <th className="text-right py-2 px-2">Success</th>
                  <th className="text-right py-2 px-2">Partial</th>
                  <th className="text-right py-2 px-2">Failure</th>
                  <th className="text-right py-2 px-2">Accuracy</th>
                  <th className="text-right py-2 px-2">Confidence</th>
                  <th className="text-right py-2 pl-2">Gap</th>
                </tr>
              </thead>
              <tbody>
                {buckets
                  .filter((b) => b.count > 0)
                  .map((b) => {
                    const lo = Math.round(b.range_lo * 100)
                    const hi = Math.round(b.range_hi * 100)
                    const gap =
                      b.with_outcomes > 0
                        ? Math.abs(b.accuracy - b.mean_confidence)
                        : null

                    return (
                      <tr
                        key={lo}
                        className="border-b border-[var(--color-border)] last:border-0 text-[var(--color-text-secondary)]"
                      >
                        <td className="py-1.5 pr-3">{lo}-{hi}%</td>
                        <td className="text-right py-1.5 px-2">{b.count}</td>
                        <td className="text-right py-1.5 px-2">{b.with_outcomes}</td>
                        <td className="text-right py-1.5 px-2">{b.success}</td>
                        <td className="text-right py-1.5 px-2">{b.partial}</td>
                        <td className="text-right py-1.5 px-2">{b.failure}</td>
                        <td className="text-right py-1.5 px-2">
                          {b.with_outcomes > 0
                            ? `${(b.accuracy * 100).toFixed(1)}%`
                            : '-'}
                        </td>
                        <td className="text-right py-1.5 px-2">
                          {(b.mean_confidence * 100).toFixed(1)}%
                        </td>
                        <td className="text-right py-1.5 pl-2">
                          {gap != null ? `${(gap * 100).toFixed(1)}%` : '-'}
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

function MetricCard({
  label,
  value,
  sublabel,
  sublabelColor,
}: {
  label: string
  value: string
  sublabel?: string
  sublabelColor?: string
}) {
  return (
    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-md)] p-4">
      <div className="text-[10px] text-[var(--color-text-dim)] uppercase tracking-wider mb-1">
        {label}
      </div>
      <div className="text-xl font-bold text-[var(--color-text)] font-mono">
        {value}
      </div>
      {sublabel && (
        <div
          className="text-xs font-semibold mt-0.5"
          style={{ color: sublabelColor }}
        >
          {sublabel}
        </div>
      )}
    </div>
  )
}
