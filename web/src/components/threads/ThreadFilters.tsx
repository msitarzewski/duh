import { useThreadsStore } from '@/stores'

const filters = [
  { label: 'All', value: null },
  { label: 'Active', value: 'active' },
  { label: 'Complete', value: 'complete' },
  { label: 'Failed', value: 'failed' },
] as const

export function ThreadFilters() {
  const { statusFilter, setStatusFilter } = useThreadsStore()

  return (
    <div className="flex gap-1.5">
      {filters.map((f) => (
        <button
          key={f.label}
          onClick={() => setStatusFilter(f.value)}
          className={`px-3 py-1 text-xs font-mono rounded-full border transition-all duration-[var(--transition-fast)] ${
            statusFilter === f.value
              ? 'bg-[var(--color-primary-glow)] text-[var(--color-primary)] border-[var(--color-border-active)]'
              : 'text-[var(--color-text-secondary)] border-[var(--color-border)] hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]'
          }`}
        >
          {f.label}
        </button>
      ))}
    </div>
  )
}
