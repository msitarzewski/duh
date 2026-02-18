import { useState, useEffect, useCallback } from 'react'
import { GlassPanel, GlowButton } from '@/components/shared'
import { usePreferencesStore } from '@/stores'
import { api } from '@/api/client'
import type { ModelInfo, ModelSelectionOptions } from '@/api/types'

interface QuestionInputProps {
  onSubmit: (question: string, rounds: number, protocol: string, modelSelection?: ModelSelectionOptions) => void
  disabled?: boolean
}

function ModelChip({
  model,
  selected,
  onToggle,
  dim,
}: {
  model: ModelInfo
  selected: boolean
  onToggle: () => void
  dim?: boolean
}) {
  const providerColors: Record<string, string> = {
    anthropic: 'rgba(0,212,255,0.7)',
    openai: 'rgba(0,255,136,0.7)',
    google: 'rgba(255,184,0,0.7)',
    mistral: 'rgba(255,59,79,0.7)',
    perplexity: 'rgba(180,120,255,0.7)',
  }
  const dotColor = providerColors[model.provider_id] ?? 'rgba(128,128,128,0.7)'

  return (
    <button
      type="button"
      onClick={onToggle}
      className={[
        'inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-mono border transition-all duration-150',
        selected
          ? 'bg-[var(--color-surface)] border-[var(--color-primary)] text-[var(--color-text)]'
          : 'bg-transparent border-[var(--color-border)] text-[var(--color-text-dim)] hover:border-[var(--color-border-hover)]',
        dim ? 'opacity-40' : '',
      ].join(' ')}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: dotColor }} />
      {model.provider_id}:{model.model_id}
      {!model.proposer_eligible && <span className="text-[8px] opacity-60">(challenger)</span>}
    </button>
  )
}

export function QuestionInput({ onSubmit, disabled }: QuestionInputProps) {
  const { defaultRounds, defaultProtocol } = usePreferencesStore()
  const [question, setQuestion] = useState('')
  const [rounds, setRounds] = useState(defaultRounds)
  const [protocol, setProtocol] = useState(defaultProtocol)

  // Model selection state
  const [showModels, setShowModels] = useState(false)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [modelsLoaded, setModelsLoaded] = useState(false)
  const [panel, setPanel] = useState<string[]>([])
  const [proposer, setProposer] = useState<string>('')
  const [challengers, setChallengers] = useState<string[]>([])

  const loadModels = useCallback(async () => {
    if (modelsLoaded) return
    try {
      const res = await api.models()
      setModels(res.models)
      setModelsLoaded(true)
    } catch {
      // API unavailable — model selection stays hidden
    }
  }, [modelsLoaded])

  useEffect(() => {
    if (showModels) {
      loadModels()
    }
  }, [showModels, loadModels])

  const modelRef = (m: ModelInfo) => `${m.provider_id}:${m.model_id}`

  const togglePanel = (ref: string) => {
    setPanel((prev) => (prev.includes(ref) ? prev.filter((r) => r !== ref) : [...prev, ref]))
  }

  const toggleChallenger = (ref: string) => {
    setChallengers((prev) => (prev.includes(ref) ? prev.filter((r) => r !== ref) : [...prev, ref]))
  }

  const clearModelSelection = () => {
    setPanel([])
    setProposer('')
    setChallengers([])
  }

  const hasModelSelection = panel.length > 0 || proposer !== '' || challengers.length > 0
  const selectedModelCount = new Set([...panel, ...(proposer ? [proposer] : []), ...challengers]).size

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || disabled) return

    const selection: ModelSelectionOptions | undefined = hasModelSelection
      ? {
          panel: panel.length > 0 ? panel : undefined,
          proposer: proposer || undefined,
          challengers: challengers.length > 0 ? challengers : undefined,
        }
      : undefined

    onSubmit(question.trim(), rounds, protocol, selection)
  }

  const eligibleProposers = models.filter((m) => m.proposer_eligible)

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

            <button
              type="button"
              onClick={() => setShowModels(!showModels)}
              className={[
                'font-mono text-xs transition-colors',
                showModels || hasModelSelection
                  ? 'text-[var(--color-primary)]'
                  : 'text-[var(--color-text-dim)] hover:text-[var(--color-text-secondary)]',
              ].join(' ')}
            >
              Models {hasModelSelection ? `(${selectedModelCount})` : '...'}
            </button>
          </div>

          <GlowButton type="submit" disabled={!question.trim() || disabled} size="sm">
            Ask
          </GlowButton>
        </div>

        {showModels && modelsLoaded && models.length > 0 && (
          <div className="space-y-3 border-t border-[var(--color-border)] pt-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] text-[var(--color-text-dim)] uppercase tracking-wider">
                Model Selection
              </span>
              {hasModelSelection && (
                <button
                  type="button"
                  onClick={clearModelSelection}
                  className="font-mono text-[10px] text-[var(--color-text-dim)] hover:text-[var(--color-red)] transition-colors"
                >
                  Clear all
                </button>
              )}
            </div>

            {/* Panel filter */}
            <div className="space-y-1.5">
              <span className="font-mono text-[10px] text-[var(--color-text-secondary)]">
                Panel <span className="text-[var(--color-text-dim)]">- restrict to these models</span>
              </span>
              <div className="flex flex-wrap gap-1.5">
                {models.map((m) => (
                  <ModelChip
                    key={modelRef(m)}
                    model={m}
                    selected={panel.includes(modelRef(m))}
                    onToggle={() => togglePanel(modelRef(m))}
                  />
                ))}
              </div>
            </div>

            {/* Proposer override */}
            <div className="space-y-1.5">
              <span className="font-mono text-[10px] text-[var(--color-text-secondary)]">
                Proposer <span className="text-[var(--color-text-dim)]">- override who proposes</span>
              </span>
              <div className="flex flex-wrap gap-1.5">
                {eligibleProposers.map((m) => {
                  const ref = modelRef(m)
                  return (
                    <ModelChip
                      key={ref}
                      model={m}
                      selected={proposer === ref}
                      onToggle={() => setProposer(proposer === ref ? '' : ref)}
                      dim={panel.length > 0 && !panel.includes(ref)}
                    />
                  )
                })}
              </div>
            </div>

            {/* Challengers override */}
            <div className="space-y-1.5">
              <span className="font-mono text-[10px] text-[var(--color-text-secondary)]">
                Challengers <span className="text-[var(--color-text-dim)]">- override who challenges</span>
              </span>
              <div className="flex flex-wrap gap-1.5">
                {models.map((m) => {
                  const ref = modelRef(m)
                  return (
                    <ModelChip
                      key={ref}
                      model={m}
                      selected={challengers.includes(ref)}
                      onToggle={() => toggleChallenger(ref)}
                      dim={panel.length > 0 && !panel.includes(ref)}
                    />
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {showModels && !modelsLoaded && (
          <div className="border-t border-[var(--color-border)] pt-3">
            <span className="font-mono text-[10px] text-[var(--color-text-dim)]">Loading models...</span>
          </div>
        )}
      </form>
    </GlassPanel>
  )
}
