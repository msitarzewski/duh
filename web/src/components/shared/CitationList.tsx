import type { Citation } from '@/api/types'

interface CitationListProps {
  citations: Citation[]
  className?: string
}

function displayHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function CitationList({ citations, className = '' }: CitationListProps) {
  if (citations.length === 0) return null

  // Deduplicate by URL
  const seen = new Set<string>()
  const unique = citations.filter((c) => {
    if (seen.has(c.url)) return false
    seen.add(c.url)
    return true
  })

  return (
    <div className={`mt-3 pt-3 border-t border-[var(--color-border)] ${className}`}>
      <span className="font-mono text-[10px] text-[var(--color-text-dim)] uppercase tracking-wide">
        Sources
      </span>
      <ul className="mt-1.5 space-y-1">
        {unique.map((c, i) => (
          <li key={i} className="flex items-start gap-1.5 text-xs">
            <span className="text-[var(--color-text-dim)] font-mono shrink-0">{i + 1}.</span>
            <a
              href={c.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--color-blue)] hover:underline break-all leading-tight"
            >
              {c.title || displayHost(c.url)}
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}
