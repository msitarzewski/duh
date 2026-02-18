import { GlassPanel, Markdown, Disclosure } from '@/components/shared'
import { ModelBadge } from '@/components/consensus/ModelBadge'
import { ConfidenceMeter } from '@/components/consensus/ConfidenceMeter'
import { DissentBanner } from '@/components/consensus/DissentBanner'
import type { Turn } from '@/api/types'

interface TurnCardProps {
  turn: Turn
  collapsible?: boolean
  defaultOpen?: boolean
}

export function TurnCard({ turn, collapsible, defaultOpen = true }: TurnCardProps) {
  const header = (
    <>
      <span className="font-mono text-xs text-[var(--color-primary)] font-semibold">
        ROUND {turn.round_number}
      </span>
      <span className="font-mono text-[10px] text-[var(--color-text-dim)]">{turn.state}</span>
    </>
  )

  const collapsedPreview = turn.decision && (
    <span className="font-mono text-[10px] text-[var(--color-green)] ml-auto">
      {Math.round(turn.decision.confidence * 100)}%
    </span>
  )

  const body = (
    <div className="space-y-3">
      {turn.contributions.map((contrib, i) => (
        <Disclosure
          key={i}
          defaultOpen={!collapsible}
          header={
            <>
              <span className="font-mono text-[10px] text-[var(--color-text-dim)] uppercase">
                {contrib.role}
              </span>
              <ModelBadge model={contrib.model_ref} />
              {contrib.cost_usd > 0 && (
                <span className="font-mono text-[10px] text-[var(--color-text-dim)]">
                  ${contrib.cost_usd.toFixed(4)}
                </span>
              )}
            </>
          }
          className="pl-3 border-l-2 border-[var(--color-border)]"
        >
          <div className="text-sm">
            <Markdown>{contrib.content}</Markdown>
          </div>
        </Disclosure>
      ))}

      {turn.decision && (
        <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <span className="font-mono text-xs text-[var(--color-green)] font-semibold">DECISION</span>
              <div className="text-sm mt-1">
                <Markdown>{turn.decision.content}</Markdown>
              </div>
              {turn.decision.dissent && (
                <div className="mt-3">
                  <DissentBanner dissent={turn.decision.dissent} />
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <ConfidenceMeter value={turn.decision.confidence} size={48} label="Confidence" />
              <ConfidenceMeter value={turn.decision.rigor} size={36} label="Rigor" />
            </div>
          </div>
        </div>
      )}
    </div>
  )

  if (collapsible) {
    return (
      <GlassPanel padding="sm">
        <Disclosure
          header={<>{header}{collapsedPreview}</>}
          defaultOpen={defaultOpen}
        >
          {body}
        </Disclosure>
      </GlassPanel>
    )
  }

  return (
    <GlassPanel padding="sm" className="space-y-3">
      <div className="flex items-center gap-2">{header}</div>
      {body}
    </GlassPanel>
  )
}
