import { GlassPanel, PageTransition } from '@/components/shared'

export function SharePage() {
  return (
    <PageTransition>
    <div className="min-h-screen bg-[var(--color-bg)] p-6">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-2 mb-6">
          <span className="font-mono text-lg font-bold text-[var(--color-primary)]">duh</span>
          <span className="text-[var(--color-text-dim)] text-xs font-mono">shared consensus</span>
        </div>
        <GlassPanel>
          <p className="text-[var(--color-text-secondary)] text-sm">Shared thread will render here.</p>
        </GlassPanel>
      </div>
    </div>
    </PageTransition>
  )
}
