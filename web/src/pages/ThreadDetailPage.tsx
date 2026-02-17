import { ThreadDetail } from '@/components/threads'
import { PageTransition } from '@/components/shared'

export function ThreadDetailPage() {
  return (
    <PageTransition>
      <div className="max-w-3xl mx-auto p-6">
        <ThreadDetail />
      </div>
    </PageTransition>
  )
}
