import { ThreadDetail, ThreadNav } from '@/components/threads'
import { PageTransition } from '@/components/shared'

export function ThreadDetailPage() {
  return (
    <PageTransition>
      <div className="p-6">
        <div className="flex gap-6 max-w-5xl mx-auto">
          <div className="flex-1 max-w-3xl">
            <ThreadDetail />
          </div>
          <div className="hidden lg:block w-48 shrink-0">
            <div className="sticky top-6">
              <ThreadNav />
            </div>
          </div>
        </div>
      </div>
    </PageTransition>
  )
}
