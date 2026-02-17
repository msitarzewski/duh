import { useState, useEffect } from 'react'
import { useThreadsStore } from '@/stores'

export function ThreadSearch() {
  const { search, clearSearch, searchQuery } = useThreadsStore()
  const [input, setInput] = useState(searchQuery)

  useEffect(() => {
    const timeout = setTimeout(() => {
      if (input.trim()) {
        search(input.trim())
      } else {
        clearSearch()
      }
    }, 300)
    return () => clearTimeout(timeout)
  }, [input, search, clearSearch])

  return (
    <div className="relative">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Search threads..."
        className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-sm)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] outline-none focus:border-[var(--color-border-active)] transition-colors font-[var(--font-ui)]"
      />
      {input && (
        <button
          onClick={() => { setInput(''); clearSearch() }}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-dim)] hover:text-[var(--color-text)] text-xs"
        >
          ✕
        </button>
      )}
    </div>
  )
}
