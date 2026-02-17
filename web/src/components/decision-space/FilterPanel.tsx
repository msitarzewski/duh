import { GlassPanel, GlowButton } from '@/components/shared'
import { useDecisionSpaceStore } from '@/stores'

export function FilterPanel() {
  const {
    availableCategories, availableGenera,
    filters, setFilter, resetFilters,
  } = useDecisionSpaceStore()

  return (
    <GlassPanel padding="sm" className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-[var(--color-primary)]">FILTERS</span>
        <GlowButton variant="ghost" size="sm" onClick={resetFilters}>Reset</GlowButton>
      </div>

      {availableCategories.length > 0 && (
        <div>
          <label className="text-[10px] font-mono text-[var(--color-text-dim)] block mb-1">Category</label>
          <div className="flex flex-wrap gap-1">
            {availableCategories.map((c) => (
              <button
                key={c}
                onClick={() => {
                  const cats = filters.categories.includes(c)
                    ? filters.categories.filter((x) => x !== c)
                    : [...filters.categories, c]
                  setFilter('categories', cats)
                }}
                className={`px-2 py-0.5 text-[10px] font-mono rounded-full border transition-all duration-200 ease-out active:scale-95 ${
                  filters.categories.includes(c)
                    ? 'bg-[rgba(0,212,255,0.1)] text-[var(--color-primary)] border-[rgba(0,212,255,0.3)] shadow-[0_0_8px_rgba(0,212,255,0.1)]'
                    : 'text-[var(--color-text-dim)] border-[var(--color-border)] hover:border-[var(--color-border-hover)]'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
      )}

      {availableGenera.length > 0 && (
        <div>
          <label className="text-[10px] font-mono text-[var(--color-text-dim)] block mb-1">Genus</label>
          <div className="flex flex-wrap gap-1">
            {availableGenera.map((g) => (
              <button
                key={g}
                onClick={() => {
                  const gen = filters.genera.includes(g)
                    ? filters.genera.filter((x) => x !== g)
                    : [...filters.genera, g]
                  setFilter('genera', gen)
                }}
                className={`px-2 py-0.5 text-[10px] font-mono rounded-full border transition-all duration-200 ease-out active:scale-95 ${
                  filters.genera.includes(g)
                    ? 'bg-[rgba(0,212,255,0.1)] text-[var(--color-primary)] border-[rgba(0,212,255,0.3)] shadow-[0_0_8px_rgba(0,212,255,0.1)]'
                    : 'text-[var(--color-text-dim)] border-[var(--color-border)] hover:border-[var(--color-border-hover)]'
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </div>
      )}

      <div>
        <label className="text-[10px] font-mono text-[var(--color-text-dim)] block mb-1">Outcome</label>
        <div className="flex gap-1">
          {['success', 'failure', 'partial'].map((o) => (
            <button
              key={o}
              onClick={() => {
                const outs = filters.outcomes.includes(o)
                  ? filters.outcomes.filter((x) => x !== o)
                  : [...filters.outcomes, o]
                setFilter('outcomes', outs)
              }}
              className={`px-2 py-0.5 text-[10px] font-mono rounded-full border transition-all duration-200 ease-out active:scale-95 ${
                filters.outcomes.includes(o)
                  ? 'bg-[rgba(0,212,255,0.1)] text-[var(--color-primary)] border-[rgba(0,212,255,0.3)] shadow-[0_0_8px_rgba(0,212,255,0.1)]'
                  : 'text-[var(--color-text-dim)] border-[var(--color-border)] hover:border-[var(--color-border-hover)]'
              }`}
            >
              {o}
            </button>
          ))}
        </div>
      </div>
    </GlassPanel>
  )
}
