import { useState, useRef, useEffect } from 'react'
import { GlowButton } from './GlowButton'
import type { ThreadDetail } from '@/api/types'

type ContentMode = 'full' | 'decision'

interface ExportMenuProps {
  thread: ThreadDetail
}

function generateMarkdown(thread: ThreadDetail, content: ContentMode, includeDissent: boolean): string {
  const lines: string[] = []
  lines.push(`# Consensus: ${thread.question}`)
  lines.push('')

  // Find last decision
  let finalDecision: { content: string; confidence: number; rigor: number; dissent: string | null } | null = null
  for (let i = thread.turns.length - 1; i >= 0; i--) {
    if (thread.turns[i]?.decision) {
      finalDecision = thread.turns[i]!.decision
      break
    }
  }

  // Total cost
  const totalCost = thread.turns.reduce(
    (sum, turn) => sum + turn.contributions.reduce((s, c) => s + c.cost_usd, 0),
    0,
  )

  if (finalDecision) {
    lines.push('## Decision')
    lines.push(finalDecision.content)
    lines.push('')
    lines.push(`Confidence: ${Math.round(finalDecision.confidence * 100)}%  Rigor: ${Math.round(finalDecision.rigor * 100)}%`)
    lines.push('')

    if (includeDissent && finalDecision.dissent) {
      lines.push('## Dissent')
      lines.push(finalDecision.dissent)
      lines.push('')
    }
  }

  if (content === 'full') {
    lines.push('---')
    lines.push('')
    lines.push('## Consensus Process')
    lines.push('')

    for (const turn of thread.turns) {
      lines.push(`### Round ${turn.round_number}`)
      lines.push('')

      const proposers = turn.contributions.filter((c) => c.role === 'proposer')
      const challengers = turn.contributions.filter((c) => c.role === 'challenger')
      const revisers = turn.contributions.filter((c) => c.role === 'reviser')
      const others = turn.contributions.filter(
        (c) => !['proposer', 'challenger', 'reviser'].includes(c.role),
      )

      for (const p of proposers) {
        lines.push(`#### Proposal (${p.model_ref})`)
        lines.push(p.content)
        lines.push('')
      }

      if (challengers.length > 0) {
        lines.push('#### Challenges')
        for (const ch of challengers) {
          lines.push(`**${ch.model_ref}**: ${ch.content}`)
          lines.push('')
        }
      }

      for (const r of revisers) {
        lines.push(`#### Revision (${r.model_ref})`)
        lines.push(r.content)
        lines.push('')
      }

      for (const o of others) {
        lines.push(`#### ${o.role.charAt(0).toUpperCase() + o.role.slice(1)} (${o.model_ref})`)
        lines.push(o.content)
        lines.push('')
      }
    }
  }

  lines.push('---')
  const costStr = totalCost > 0 ? ` | Cost: $${totalCost.toFixed(4)}` : ''
  const dateStr = thread.created_at.slice(0, 10)
  lines.push(`*duh | ${dateStr}${costStr}*`)
  return lines.join('\n')
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function ExportMenu({ thread }: ExportMenuProps) {
  const [open, setOpen] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close on click outside
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const shortId = thread.thread_id.slice(0, 8)

  const handleMarkdown = (content: ContentMode) => {
    const md = generateMarkdown(thread, content, true)
    downloadBlob(new Blob([md], { type: 'text/markdown' }), `consensus-${shortId}-${content}.md`)
    setOpen(false)
  }

  const handlePdf = async (content: ContentMode) => {
    setDownloading(true)
    try {
      const params = new URLSearchParams({ format: 'pdf', content, dissent: 'true' })
      const res = await fetch(`/api/threads/${thread.thread_id}/export?${params}`)
      if (!res.ok) return
      const blob = await res.blob()
      downloadBlob(blob, `consensus-${shortId}-${content}.pdf`)
    } finally {
      setDownloading(false)
      setOpen(false)
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      <GlowButton variant="ghost" size="sm" onClick={() => setOpen(!open)} disabled={downloading}>
        {downloading ? 'Exporting...' : 'Export'}
      </GlowButton>
      {open && (
        <div className="absolute top-full right-0 mt-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg shadow-lg py-1 min-w-[200px] z-50">
          <button
            className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-bg-tertiary)] text-[var(--color-text)]"
            onClick={() => handleMarkdown('decision')}
          >
            Markdown (decision only)
          </button>
          <button
            className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-bg-tertiary)] text-[var(--color-text)]"
            onClick={() => handleMarkdown('full')}
          >
            Markdown (full report)
          </button>
          <button
            className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-bg-tertiary)] text-[var(--color-text)]"
            onClick={() => handlePdf('decision')}
          >
            PDF (decision only)
          </button>
          <button
            className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-bg-tertiary)] text-[var(--color-text)]"
            onClick={() => handlePdf('full')}
          >
            PDF (full report)
          </button>
        </div>
      )}
    </div>
  )
}
