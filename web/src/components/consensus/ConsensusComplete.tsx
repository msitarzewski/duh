import { useState, useRef, useEffect } from 'react'
import { GlassPanel, GlowButton, Markdown, Disclosure } from '@/components/shared'
import { ConfidenceMeter } from './ConfidenceMeter'
import { DissentBanner } from './DissentBanner'
import { CostTicker } from './CostTicker'
import { useConsensusStore } from '@/stores/consensus'
import type { RoundData } from '@/stores/consensus'
import type { Usage } from '@/api/types'

interface ConsensusCompleteProps {
  decision: string
  confidence: number
  rigor: number
  dissent: string | null
  cost: number | null
  usage?: Usage | null
  collapsible?: boolean
  overview: string | null
}

export function generateExportMarkdown(
  question: string | null,
  decision: string,
  confidence: number,
  rigor: number,
  dissent: string | null,
  cost: number | null,
  rounds: RoundData[],
  content: 'full' | 'decision',
  includeDissent: boolean,
  overview?: string | null,
): string {
  const lines: string[] = []
  lines.push(`# Consensus: ${question ?? 'Unknown'}`)
  lines.push('')

  if (overview) {
    lines.push('## Executive Overview')
    lines.push(overview)
    lines.push('')
  }

  lines.push('## Decision')
  lines.push(decision)
  lines.push('')
  lines.push(`Confidence: ${Math.round(confidence * 100)}%  Rigor: ${Math.round(rigor * 100)}%`)
  lines.push('')

  if (includeDissent && dissent) {
    lines.push('## Dissent')
    lines.push(dissent)
    lines.push('')
  }

  if (content === 'full') {
    lines.push('---')
    lines.push('')
    lines.push('## Consensus Process')
    lines.push('')

    for (const round of rounds) {
      lines.push(`### Round ${round.round}`)
      lines.push('')

      if (round.proposal && round.proposer) {
        lines.push(`#### Proposal (${round.proposer})`)
        lines.push(round.proposal)
        lines.push('')
      }

      if (round.challenges.length > 0) {
        lines.push('#### Challenges')
        for (const ch of round.challenges) {
          lines.push(`**${ch.model}**: ${ch.content}`)
          lines.push('')
        }
      }

      if (round.revision && round.reviser) {
        lines.push(`#### Revision (${round.reviser})`)
        lines.push(round.revision)
        lines.push('')
      }
    }
  }

  lines.push('---')
  const costStr = cost !== null ? ` | Cost: $${cost.toFixed(4)}` : ''
  lines.push(`*duh | ${new Date().toISOString().slice(0, 10)}${costStr}*`)
  return lines.join('\n')
}

function downloadFile(content: string | Blob, filename: string, mimeType: string) {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function ConsensusComplete({ decision, confidence, rigor, dissent, cost, usage, collapsible, overview }: ConsensusCompleteProps) {
  const [copied, setCopied] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const exportRef = useRef<HTMLDivElement>(null)
  const { question, rounds, threadId } = useConsensusStore()

  // Close the export menu when clicking outside it
  useEffect(() => {
    if (!exportOpen) return
    const handler = (e: MouseEvent) => {
      if (exportRef.current && !exportRef.current.contains(e.target as Node)) {
        setExportOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [exportOpen])

  const handleCopy = async () => {
    await navigator.clipboard.writeText(overview ?? decision)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleExportMarkdown = (content: 'full' | 'decision') => {
    const md = generateExportMarkdown(question, decision, confidence, rigor, dissent, cost, rounds, content, true, overview)
    downloadFile(md, `consensus-${content}.md`, 'text/markdown')
    setExportOpen(false)
  }

  const handleExportPdf = async (content: 'full' | 'decision') => {
    if (!threadId) return
    const params = new URLSearchParams({ format: 'pdf', content, dissent: 'true' })
    const response = await fetch(`/api/threads/${threadId}/export?${params}`)
    if (!response.ok) return
    const blob = await response.blob()
    downloadFile(blob, `consensus-${content}.pdf`, 'application/pdf')
    setExportOpen(false)
  }

  const header = (
    <>
      <span className="font-mono text-xs text-[var(--color-green)] font-semibold">CONSENSUS REACHED</span>
      <CostTicker cost={cost} usage={usage} />
      <div className="flex items-center gap-3 ml-auto">
        <ConfidenceMeter value={confidence} label="Confidence" />
        <ConfidenceMeter value={rigor} size={48} label="Rigor" />
      </div>
    </>
  )

  const actions = (
    <div className="flex gap-2 mb-4">
      <GlowButton variant="ghost" size="sm" onClick={handleCopy}>
        {copied ? 'Copied' : 'Copy'}
      </GlowButton>
      <div className="relative" ref={exportRef}>
        <GlowButton variant="ghost" size="sm" onClick={() => setExportOpen(!exportOpen)}>
          Export
        </GlowButton>
        {exportOpen && (
          <div className="absolute top-full left-0 mt-1 bg-[var(--color-surface-solid)] border border-[var(--color-border)] rounded-[var(--radius-md)] shadow-lg py-1 min-w-[200px] z-[var(--z-dropdown)]">
            <button
              className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-surface-hover)] text-[var(--color-text)]"
              onClick={() => handleExportMarkdown('decision')}
            >
              Markdown (decision only)
            </button>
            <button
              className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-surface-hover)] text-[var(--color-text)]"
              onClick={() => handleExportMarkdown('full')}
            >
              Markdown (full report)
            </button>
            <button
              className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-surface-hover)] text-[var(--color-text)]"
              onClick={() => handleExportPdf('decision')}
            >
              PDF (decision only)
            </button>
            <button
              className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-surface-hover)] text-[var(--color-text)]"
              onClick={() => handleExportPdf('full')}
            >
              PDF (full report)
            </button>
          </div>
        )}
      </div>
    </div>
  )

  const body = (
    <>
      {actions}
      {overview ? (
        <>
          <Markdown className="text-sm">{overview}</Markdown>
          <div className="mt-4">
            <Disclosure header={<span className="font-mono text-xs text-[var(--color-text-dim)]">Full Decision</span>} defaultOpen={false}>
              <Markdown className="text-sm">{decision}</Markdown>
            </Disclosure>
          </div>
        </>
      ) : (
        <Markdown className="text-sm">{decision}</Markdown>
      )}
    </>
  )

  if (collapsible) {
    return (
      <div className="space-y-4 animate-fade-in-up">
        <GlassPanel glow="strong" padding="lg">
          <Disclosure header={header} defaultOpen>
            {body}
            {dissent && <div className="mt-4"><DissentBanner dissent={dissent} /></div>}
          </Disclosure>
        </GlassPanel>
      </div>
    )
  }

  return (
    <div className="space-y-4 animate-fade-in-up">
      <GlassPanel glow="strong" padding="lg">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-[var(--color-green)] font-semibold">CONSENSUS REACHED</span>
            <CostTicker cost={cost} usage={usage} />
          </div>
          <div className="flex items-center gap-3">
            <ConfidenceMeter value={confidence} label="Confidence" />
            <ConfidenceMeter value={rigor} size={48} label="Rigor" />
          </div>
        </div>
        {body}
        {dissent && <div className="mt-4"><DissentBanner dissent={dissent} /></div>}
      </GlassPanel>
    </div>
  )
}
