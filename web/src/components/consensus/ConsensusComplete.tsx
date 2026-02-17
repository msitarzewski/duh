import { useState } from 'react'
import { GlassPanel, GlowButton, Markdown } from '@/components/shared'
import { ConfidenceMeter } from './ConfidenceMeter'
import { DissentBanner } from './DissentBanner'
import { CostTicker } from './CostTicker'

interface ConsensusCompleteProps {
  decision: string
  confidence: number
  dissent: string | null
  cost: number | null
}

export function ConsensusComplete({ decision, confidence, dissent, cost }: ConsensusCompleteProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(decision)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
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
        </div>
      </GlassPanel>

      {dissent && <DissentBanner dissent={dissent} />}
    </div>
  )
}
