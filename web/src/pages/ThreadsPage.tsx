import { ThreadBrowser } from '@/components/threads'
import { PageTransition } from '@/components/shared'

export function ThreadsPage() {
  return (
    <PageTransition>
      <div className="max-w-3xl mx-auto p-6">
        <ThreadBrowser />
      </div>
    </PageTransition>
  )
}
