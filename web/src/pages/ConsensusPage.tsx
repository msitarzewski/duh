import { ConsensusPanel } from '@/components/consensus'
import { PageTransition } from '@/components/shared'

export function ConsensusPage() {
  return (
    <PageTransition>
      <div className="max-w-3xl mx-auto p-6">
        <ConsensusPanel />
      </div>
    </PageTransition>
  )
}
