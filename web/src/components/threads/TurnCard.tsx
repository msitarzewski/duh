import { GlassPanel, Markdown } from '@/components/shared'
import { ModelBadge } from '@/components/consensus/ModelBadge'
import { ConfidenceMeter } from '@/components/consensus/ConfidenceMeter'
import type { Turn } from '@/api/types'

export function TurnCard({ turn }: { turn: Turn }) {
  return (
    <GlassPanel padding="sm" className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-[var(--color-primary)] font-semibold">
          ROUND {turn.round_number}
        </span>
        <span className="font-mono text-[10px] text-[var(--color-text-dim)]">{turn.state}</span>
      </div>

      {turn.contributions.map((contrib, i) => (
        <div key={i} className="pl-3 border-l-2 border-[var(--color-border)]">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[10px] text-[var(--color-text-dim)] uppercase">
              {contrib.role}
            </span>
            <ModelBadge model={contrib.model_ref} />
            {contrib.cost_usd > 0 && (
              <span className="font-mono text-[10px] text-[var(--color-text-dim)]">
                ${contrib.cost_usd.toFixed(4)}
              </span>
            )}
          </div>
          <div className="text-sm">
            <Markdown>{contrib.content}</Markdown>
          </div>
        </div>
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
                <div className="text-sm text-[var(--color-amber)] mt-2">
                  <Markdown>{`**Dissent:** ${turn.decision.dissent}`}</Markdown>
                </div>
              )}
            </div>
            <ConfidenceMeter value={turn.decision.confidence} size={48} />
          </div>
        </div>
      )}
    </GlassPanel>
  )
}
