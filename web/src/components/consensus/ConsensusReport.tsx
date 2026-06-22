import { useState, type ReactNode } from 'react'
import { GlassPanel, GlowButton, Markdown, Disclosure } from '@/components/shared'
import { ConfidenceMeter } from './ConfidenceMeter'
import { DissentBanner } from './DissentBanner'
import { CostTicker } from './CostTicker'
import type { Usage } from '@/api/types'

interface ConsensusReportProps {
  /** Header label, e.g. "CONSENSUS REACHED". */
  label: string
  /** The full decision text (markdown). */
  decision: string
  /** Executive summary; when present it leads and the decision collapses. */
  overview?: string | null
  confidence: number
  rigor: number
  dissent?: string | null
  cost?: number | null
  usage?: Usage | null
  /** View-specific export control rendered next to Copy. */
  exportSlot?: ReactNode
  /** Wrap the whole report in a Disclosure (live view collapses on follow-up). */
  collapsible?: boolean
}

/**
 * The unified consensus decision report, shared by the live view
 * (ConsensusComplete) and the stored thread view (ThreadDetail) so both
 * render identically: meters, Copy/Export, an executive summary that leads
 * with the full decision tucked into a disclosure, and dissent.
 */
export function ConsensusReport({
  label,
  decision,
  overview,
  confidence,
  rigor,
  dissent,
  cost = null,
  usage = null,
  exportSlot,
  collapsible = false,
}: ConsensusReportProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(overview ?? decision)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const header = (
    <>
      <span className="font-mono text-xs text-[var(--color-green)] font-semibold">{label}</span>
      <CostTicker cost={cost} usage={usage} />
      <div className="flex items-center gap-3 ml-auto">
        <ConfidenceMeter value={confidence} label="Confidence" />
        <ConfidenceMeter value={rigor} size={48} label="Rigor" />
      </div>
    </>
  )

  const body = (
    <>
      <div className="flex gap-2 mb-4">
        <GlowButton variant="ghost" size="sm" onClick={handleCopy}>
          {copied ? 'Copied' : 'Copy'}
        </GlowButton>
        {exportSlot}
      </div>

      {overview ? (
        <>
          <Markdown className="text-sm">{overview}</Markdown>
          <div className="mt-4">
            <Disclosure
              header={<span className="font-mono text-xs text-[var(--color-text-dim)]">Full Decision</span>}
              defaultOpen={false}
            >
              <Markdown className="text-sm">{decision}</Markdown>
            </Disclosure>
          </div>
        </>
      ) : (
        <Markdown className="text-sm">{decision}</Markdown>
      )}

      {dissent && (
        <div className="mt-4">
          <DissentBanner dissent={dissent} defaultOpen={false} />
        </div>
      )}
    </>
  )

  return (
    <GlassPanel glow="strong" padding="lg" className="animate-fade-in-up">
      {collapsible ? (
        <Disclosure header={header} defaultOpen>
          {body}
        </Disclosure>
      ) : (
        <>
          <div className="flex items-center gap-3 mb-4">{header}</div>
          {body}
        </>
      )}
    </GlassPanel>
  )
}
