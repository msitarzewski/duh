import { DecisionSpace } from '@/components/decision-space'
import { PageTransition } from '@/components/shared'

export function DecisionSpacePage() {
  return (
    <PageTransition>
      <div className="p-6">
        <DecisionSpace />
      </div>
    </PageTransition>
  )
}
