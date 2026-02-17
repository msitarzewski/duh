import { GlassPanel } from '@/components/shared'
import { usePreferencesStore } from '@/stores'

export function PreferencesPanel() {
  const {
    defaultRounds, defaultProtocol, costThreshold, soundEnabled,
    setDefaultRounds, setDefaultProtocol, setCostThreshold, setSoundEnabled,
  } = usePreferencesStore()

  return (
    <div className="space-y-4">
      <GlassPanel padding="md">
        <h3 className="font-mono text-xs text-[var(--color-primary)] font-semibold mb-4">CONSENSUS DEFAULTS</h3>

        <div className="space-y-4">
          <div>
            <label className="text-sm text-[var(--color-text-secondary)] block mb-2">
              Default Rounds: <span className="font-mono text-[var(--color-primary)]">{defaultRounds}</span>
            </label>
            <input
              type="range"
              min={1}
              max={5}
              value={defaultRounds}
              onChange={(e) => setDefaultRounds(Number(e.target.value))}
              className="w-full h-1 appearance-none bg-[var(--color-border)] rounded-full [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-[var(--color-primary)] [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-[var(--color-text-dim)] mt-1">
              <span>1</span><span>2</span><span>3</span><span>4</span><span>5</span>
            </div>
          </div>

          <div>
            <label className="text-sm text-[var(--color-text-secondary)] block mb-2">Protocol</label>
            <div className="flex gap-2">
              {(['consensus', 'voting', 'auto'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setDefaultProtocol(p)}
                  className={`px-3 py-1.5 text-xs font-mono rounded-[var(--radius-sm)] border transition-all ${
                    defaultProtocol === p
                      ? 'bg-[var(--color-primary-glow)] text-[var(--color-primary)] border-[var(--color-border-active)]'
                      : 'text-[var(--color-text-secondary)] border-[var(--color-border)] hover:border-[var(--color-border-hover)]'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>
      </GlassPanel>

      <GlassPanel padding="md">
        <h3 className="font-mono text-xs text-[var(--color-primary)] font-semibold mb-4">COST</h3>
        <div>
          <label className="text-sm text-[var(--color-text-secondary)] block mb-2">
            Cost Threshold (USD)
          </label>
          <input
            type="number"
            value={costThreshold ?? ''}
            onChange={(e) => setCostThreshold(e.target.value ? Number(e.target.value) : null)}
            placeholder="No limit"
            step={0.01}
            min={0}
            className="w-full bg-[var(--color-surface-solid)] border border-[var(--color-border)] rounded-[var(--radius-sm)] px-3 py-2 text-sm text-[var(--color-text)] font-mono outline-none focus:border-[var(--color-border-active)] transition-colors placeholder:text-[var(--color-text-dim)]"
          />
        </div>
      </GlassPanel>

      <GlassPanel padding="md">
        <h3 className="font-mono text-xs text-[var(--color-primary)] font-semibold mb-4">UI</h3>
        <label className="flex items-center justify-between cursor-pointer">
          <span className="text-sm text-[var(--color-text-secondary)]">Sound effects</span>
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`relative w-10 h-5 rounded-full transition-colors ${
              soundEnabled ? 'bg-[var(--color-primary)]' : 'bg-[var(--color-border)]'
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                soundEnabled ? 'translate-x-5' : ''
              }`}
            />
          </button>
        </label>
        <p className="text-[10px] text-[var(--color-text-dim)] mt-1">
          {soundEnabled ? 'Sounds enabled for phase transitions' : 'Sounds disabled'}
        </p>
      </GlassPanel>
    </div>
  )
}
