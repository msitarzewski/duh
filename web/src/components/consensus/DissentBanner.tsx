import { GlassPanel, Markdown, Disclosure } from '@/components/shared'
import { ModelBadge } from './ModelBadge'

function parseModelFromDissent(dissent: string): { model: string | null; content: string } {
  const match = dissent.match(/^\[([^\]]+)\]:\s*/)
  if (match) {
    return { model: match[1]!, content: dissent.slice(match[0].length) }
  }
  return { model: null, content: dissent }
}

export function DissentBanner({ dissent, defaultOpen = true }: { dissent: string; defaultOpen?: boolean }) {
  const { model, content } = parseModelFromDissent(dissent)

  return (
    <GlassPanel className="border-[var(--color-amber)]/30 bg-[rgba(255,184,0,0.04)]" padding="sm">
      <Disclosure
        header={
          <>
            <span className="text-[var(--color-amber)] font-mono text-xs font-semibold">DISSENT</span>
            {model && <ModelBadge model={model} />}
          </>
        }
        defaultOpen={defaultOpen}
      >
        <div className="text-sm text-[var(--color-text-secondary)]">
          <Markdown>{content}</Markdown>
        </div>
      </Disclosure>
    </GlassPanel>
  )
}
