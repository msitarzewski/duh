import { GlassPanel, Markdown } from '@/components/shared'

export function DissentBanner({ dissent }: { dissent: string }) {
  return (
    <GlassPanel className="border-[var(--color-amber)]/30 bg-[rgba(255,184,0,0.04)]" padding="sm">
      <div className="flex items-start gap-2">
        <span className="text-[var(--color-amber)] font-mono text-xs mt-0.5 shrink-0">DISSENT</span>
        <div className="text-sm text-[var(--color-text-secondary)]">
          <Markdown>{dissent}</Markdown>
        </div>
      </div>
    </GlassPanel>
  )
}
