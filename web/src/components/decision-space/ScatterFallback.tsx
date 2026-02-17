import type { SpaceDecision } from '@/api/types'
import { outcomeColor } from '@/utils'
import { useDecisionSpaceStore } from '@/stores'

interface ScatterFallbackProps {
  decisions: SpaceDecision[]
}

export function ScatterFallback({ decisions }: ScatterFallbackProps) {
  const { setSelected } = useDecisionSpaceStore()

  if (decisions.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-[var(--color-text-dim)] text-sm font-mono">
        No decisions yet
      </div>
    )
  }

  const dates = decisions.map((d) => new Date(d.created_at).getTime())
  const minDate = Math.min(...dates)
  const maxDate = Math.max(...dates)
  const dateRange = maxDate - minDate || 1

  const width = 400
  const height = 250
  const pad = 30

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full max-w-lg mx-auto">
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="rgba(0,212,255,0.15)" />
      <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="rgba(0,212,255,0.15)" />
      <text x={width / 2} y={height - 5} fill="#52525b" fontSize="9" textAnchor="middle" fontFamily="JetBrains Mono">time</text>
      <text x={10} y={height / 2} fill="#52525b" fontSize="9" textAnchor="middle" fontFamily="JetBrains Mono" transform={`rotate(-90, 10, ${height / 2})`}>confidence</text>

      {decisions.map((d) => {
        const x = pad + ((new Date(d.created_at).getTime() - minDate) / dateRange) * (width - 2 * pad)
        const y = height - pad - d.confidence * (height - 2 * pad)
        const r = 4 + d.confidence * 4

        return (
          <circle
            key={d.id}
            cx={x}
            cy={y}
            r={r}
            fill={outcomeColor(d.outcome)}
            opacity={0.7}
            className="cursor-pointer hover:opacity-100 transition-opacity"
            onClick={() => setSelected(d.id)}
          >
            <title>{d.question}</title>
          </circle>
        )
      })}
    </svg>
  )
}
