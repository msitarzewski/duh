interface CostTickerUsage {
  input_tokens: number
  output_tokens: number
}

export function CostTicker({
  cost,
  usage,
}: {
  cost: number | null
  usage?: CostTickerUsage | null
}) {
  const hasUsage =
    !!usage && (usage.input_tokens > 0 || usage.output_tokens > 0)

  if (cost === null && !hasUsage) return null

  return (
    <span className="inline-flex items-center gap-2 font-mono text-xs text-[var(--color-text-dim)]">
      {cost !== null && (
        <span className="inline-flex items-center gap-1">
          <span className="text-[var(--color-amber)]">$</span>
          <span>{cost.toFixed(4)}</span>
        </span>
      )}
      {hasUsage && (
        <span className="inline-flex items-center gap-2" title="Input / output tokens">
          <span>↑{usage!.input_tokens.toLocaleString()}</span>
          <span>↓{usage!.output_tokens.toLocaleString()}</span>
        </span>
      )}
    </span>
  )
}
