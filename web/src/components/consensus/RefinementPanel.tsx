import { useState } from 'react'
import { GlassPanel, GlowButton } from '@/components/shared'
import type { ClarifyingQuestion } from '@/api/types'

interface RefinementPanelProps {
  questions: ClarifyingQuestion[]
  answers: Record<number, string>
  onAnswer: (index: number, answer: string) => void
  onSubmit: () => void
  onSkip: () => void
}

export function RefinementPanel({
  questions,
  answers,
  onAnswer,
  onSubmit,
  onSkip,
}: RefinementPanelProps) {
  const [activeTab, setActiveTab] = useState(0)
  const allAnswered = questions.every((_, i) => (answers[i] ?? '').trim().length > 0)

  const handleTextChange = (value: string) => {
    onAnswer(activeTab, value)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Tab' && !e.shiftKey && (answers[activeTab] ?? '').trim()) {
      const nextUnanswered = questions.findIndex(
        (_, i) => i > activeTab && !(answers[i] ?? '').trim(),
      )
      if (nextUnanswered >= 0) {
        e.preventDefault()
        setActiveTab(nextUnanswered)
      }
    }
  }

  return (
    <GlassPanel glow="subtle" className="animate-fade-in-up">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-[var(--color-text-dim)] uppercase tracking-wider">
            Clarifying Questions
          </span>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1.5">
          {questions.map((_, i) => {
            const answered = (answers[i] ?? '').trim().length > 0
            const isActive = i === activeTab
            return (
              <button
                key={i}
                type="button"
                onClick={() => setActiveTab(i)}
                className={[
                  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] text-xs font-mono transition-all duration-150',
                  isActive
                    ? 'bg-[var(--color-surface)] border border-[var(--color-primary)] text-[var(--color-text)]'
                    : 'bg-transparent border border-[var(--color-border)] text-[var(--color-text-dim)] hover:border-[var(--color-border-hover)]',
                ].join(' ')}
              >
                Q{i + 1}
                {answered && (
                  <svg className="w-3 h-3 text-[var(--color-green)]" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            )
          })}
        </div>

        {/* Active question */}
        {questions[activeTab] && (
          <div className="space-y-2">
            <p className="text-sm text-[var(--color-text)]">
              {questions[activeTab].question}
            </p>
            {questions[activeTab].hint && (
              <p className="text-xs italic text-[var(--color-text-dim)]">
                {questions[activeTab].hint}
              </p>
            )}
            <textarea
              value={answers[activeTab] ?? ''}
              onChange={(e) => handleTextChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Your answer..."
              rows={2}
              className="w-full bg-[var(--color-surface-solid)] border border-[var(--color-border)] rounded-[var(--radius-sm)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-dim)] resize-none outline-none focus:border-[var(--color-primary)] transition-colors"
            />
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-1">
          <GlowButton variant="ghost" size="sm" onClick={onSkip}>
            Skip
          </GlowButton>
          <GlowButton
            size="sm"
            disabled={!allAnswered}
            onClick={onSubmit}
          >
            Start Consensus
          </GlowButton>
        </div>
      </div>
    </GlassPanel>
  )
}
