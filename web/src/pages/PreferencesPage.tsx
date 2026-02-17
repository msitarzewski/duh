import { PreferencesPanel } from '@/components/preferences'
import { PageTransition } from '@/components/shared'

export function PreferencesPage() {
  return (
    <PageTransition>
      <div className="max-w-xl mx-auto p-6">
        <PreferencesPanel />
      </div>
    </PageTransition>
  )
}
