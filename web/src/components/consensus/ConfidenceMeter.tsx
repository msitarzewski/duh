import { useEffect, useState } from 'react'

interface ConfidenceMeterProps {
  value: number
  size?: number
}

function getColor(value: number): string {
  if (value < 0.5) return 'var(--color-red)'
  if (value < 0.7) return 'var(--color-amber)'
  if (value < 0.9) return 'var(--color-primary)'
  return 'var(--color-green)'
}

export function ConfidenceMeter({ value, size = 64 }: ConfidenceMeterProps) {
  const radius = (size - 8) / 2
  const circumference = 2 * Math.PI * radius
  const targetOffset = circumference * (1 - value)
  const color = getColor(value)

  const [offset, setOffset] = useState(circumference)

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      setOffset(targetOffset)
    })
    return () => cancelAnimationFrame(frame)
  }, [targetOffset])

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth="3"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <span className="font-mono text-xs" style={{ color }}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  )
}
