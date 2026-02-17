import { useState } from 'react'
import { GlassPanel, GlowButton } from '@/components/shared'
import { usePreferencesStore } from '@/stores'

interface QuestionInputProps {
  onSubmit: (question: string, rounds: number, protocol: string) => void
  disabled?: boolean
}

export function QuestionInput({ onSubmit, disabled }: QuestionInputProps) {
  const { defaultRounds, defaultProtocol } = usePreferencesStore()
  const [question, setQuestion] = useState('')
  const [rounds, setRounds] = useState(defaultRounds)
  const [protocol, setProtocol] = useState(defaultProtocol)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || disabled) return
    onSubmit(question.trim(), rounds, protocol)
  }

  return (
    <GlassPanel glow="subtle">
      <form onSubmit={handleSubmit} className="space-y-4">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question to reach consensus..."
          disabled={disabled}
          rows={3}
          className="w-full bg-transparent text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] resize-none outline-none font-[var(--font-ui)] text-sm leading-relaxed"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              handleSubmit(e)
            }
          }}
        />

        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-4 text-xs">
            <label className="flex items-center gap-2 text-[var(--color-text-secondary)]">
              <span className="font-mono">Rounds:</span>
              <select
                value={rounds}
                onChange={(e) => setRounds(Number(e.target.value))}
                className="bg-[var(--color-surface-solid)] border border-[var(--color-border)] rounded px-2 py-1 text-[var(--color-text)] font-mono text-xs"
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </label>

            <label className="flex items-center gap-2 text-[var(--color-text-secondary)]">
              <span className="font-mono">Protocol:</span>
              <select
                value={protocol}
                onChange={(e) => setProtocol(e.target.value as 'consensus' | 'voting' | 'auto')}
                className="bg-[var(--color-surface-solid)] border border-[var(--color-border)] rounded px-2 py-1 text-[var(--color-text)] font-mono text-xs"
              >
                <option value="consensus">consensus</option>
                <option value="voting">voting</option>
                <option value="auto">auto</option>
              </select>
            </label>
          </div>

          <GlowButton type="submit" disabled={!question.trim() || disabled} size="sm">
            Ask
          </GlowButton>
        </div>
      </form>
    </GlassPanel>
  )
}
