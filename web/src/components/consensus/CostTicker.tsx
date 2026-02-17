export function CostTicker({ cost }: { cost: number | null }) {
  if (cost === null) return null

  return (
    <span className="inline-flex items-center gap-1 font-mono text-xs text-[var(--color-text-dim)]">
      <span className="text-[var(--color-amber)]">$</span>
      <span>{cost.toFixed(4)}</span>
    </span>
  )
}
