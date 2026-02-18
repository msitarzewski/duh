import { useState } from 'react'
import { GlassPanel, GlowButton, Markdown } from '@/components/shared'
import { ConfidenceMeter } from './ConfidenceMeter'
import { DissentBanner } from './DissentBanner'
import { CostTicker } from './CostTicker'
import { useConsensusStore } from '@/stores/consensus'
import type { RoundData } from '@/stores/consensus'

interface ConsensusCompleteProps {
  decision: string
  confidence: number
  dissent: string | null
  cost: number | null
}

export function generateExportMarkdown(
  question: string | null,
  decision: string,
  confidence: number,
  dissent: string | null,
  cost: number | null,
  rounds: RoundData[],
  content: 'full' | 'decision',
  includeDissent: boolean,
): string {
  const lines: string[] = []
  lines.push(`# Consensus: ${question ?? 'Unknown'}`)
  lines.push('')
  lines.push('## Decision')
  lines.push(decision)
  lines.push('')
  lines.push(`Confidence: ${Math.round(confidence * 100)}%`)
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

export function ConsensusComplete({ decision, confidence, dissent, cost }: ConsensusCompleteProps) {
  const [copied, setCopied] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const { question, rounds, threadId } = useConsensusStore()

  const handleCopy = async () => {
    await navigator.clipboard.writeText(decision)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleExportMarkdown = (content: 'full' | 'decision') => {
    const md = generateExportMarkdown(question, decision, confidence, dissent, cost, rounds, content, true)
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

  return (
    <div className="space-y-4 animate-fade-in-up">
      <GlassPanel glow="strong" padding="lg">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-[var(--color-green)] font-semibold">CONSENSUS REACHED</span>
            <CostTicker cost={cost} />
          </div>
          <ConfidenceMeter value={confidence} />
        </div>

        <Markdown className="text-sm">{decision}</Markdown>

        <div className="flex gap-2 mt-4">
          <GlowButton variant="ghost" size="sm" onClick={handleCopy}>
            {copied ? 'Copied' : 'Copy'}
          </GlowButton>
          <div className="relative">
            <GlowButton variant="ghost" size="sm" onClick={() => setExportOpen(!exportOpen)}>
              Export
            </GlowButton>
            {exportOpen && (
              <div className="absolute bottom-full left-0 mb-1 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-lg py-1 min-w-[200px] z-10">
                <button
                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-bg-tertiary)] text-[var(--color-text)]"
                  onClick={() => handleExportMarkdown('decision')}
                >
                  Markdown (decision only)
                </button>
                <button
                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-bg-tertiary)] text-[var(--color-text)]"
                  onClick={() => handleExportMarkdown('full')}
                >
                  Markdown (full report)
                </button>
                <button
                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-bg-tertiary)] text-[var(--color-text)]"
                  onClick={() => handleExportPdf('decision')}
                >
                  PDF (decision only)
                </button>
                <button
                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-bg-tertiary)] text-[var(--color-text)]"
                  onClick={() => handleExportPdf('full')}
                >
                  PDF (full report)
                </button>
              </div>
            )}
          </div>
        </div>
      </GlassPanel>

      {dissent && <DissentBanner dissent={dissent} />}
    </div>
  )
}
