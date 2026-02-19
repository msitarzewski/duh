import { GlassPanel, Markdown, Disclosure } from '@/components/shared'
import { ModelBadge } from './ModelBadge'
import { StreamingText } from './StreamingText'

interface PhaseCardProps {
  phase: string
  model?: string | null
  models?: string[]
  content?: string | null
  isActive?: boolean
  challenges?: Array<{ model: string; content: string; truncated?: boolean }>
  collapsible?: boolean
  defaultOpen?: boolean
  truncated?: boolean
}

export function PhaseCard({ phase, model, models, content, isActive, challenges, collapsible, defaultOpen = true, truncated }: PhaseCardProps) {
  const header = (
    <>
      <span className="font-mono text-xs text-[var(--color-primary)] font-semibold">{phase}</span>
      {isActive && (
        <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse-glow" />
      )}
      {model && <ModelBadge model={model} />}
      {models?.map((m) => <ModelBadge key={m} model={m} />)}
    </>
  )

  const body = (
    <>
      {content && (
        <div className="text-sm">
          {isActive ? (
            <StreamingText text={content} speed={80} />
          ) : (
            <Markdown>{content}</Markdown>
          )}
        </div>
      )}

      {challenges && challenges.length > 0 && (
        <div className="mt-3 space-y-2">
          {challenges.map((ch, i) => (
            <Disclosure
              key={i}
              defaultOpen={!collapsible}
              header={<ModelBadge model={ch.model} />}
              className="pl-3 border-l-2 border-[var(--color-amber)]/30"
            >
              <div className="text-sm text-[var(--color-text-secondary)]">
                <Markdown>{ch.content}</Markdown>
              </div>
            </Disclosure>
          ))}
        </div>
      )}

      {(truncated || challenges?.some((ch) => ch.truncated)) && (
        <p className="text-[10px] font-mono text-[var(--color-amber)] mt-2">
          Output truncated — response hit token limit
        </p>
      )}

      {isActive && !content && !challenges?.length && (
        <div className="flex items-center gap-2 text-[var(--color-text-dim)] text-xs font-mono">
          <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Processing...
        </div>
      )}
    </>
  )

  if (collapsible) {
    return (
      <GlassPanel
        className={`animate-fade-in-up ${isActive ? 'border-[var(--color-border-active)]' : ''}`}
        glow={isActive ? 'subtle' : 'none'}
        padding="sm"
      >
        <Disclosure header={header} defaultOpen={defaultOpen} forceOpen={isActive}>
          {body}
        </Disclosure>
      </GlassPanel>
    )
  }

  return (
    <GlassPanel
      className={`animate-fade-in-up ${isActive ? 'border-[var(--color-border-active)]' : ''}`}
      glow={isActive ? 'subtle' : 'none'}
      padding="sm"
    >
      <div className="flex items-center gap-2 mb-2">{header}</div>
      {body}
    </GlassPanel>
  )
}
