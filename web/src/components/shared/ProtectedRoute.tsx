import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores'
import { Skeleton } from './Skeleton'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { status, authRequired } = useAuthStore()

  // Still checking auth status
  if (authRequired === null) {
    return (
      <div className="flex items-center justify-center h-screen bg-[var(--color-bg)]">
        <div className="space-y-4 w-64">
          <Skeleton variant="rect" height="40px" />
          <Skeleton variant="rect" height="20px" />
        </div>
      </div>
    )
  }

  // Auth not required (dev mode) — always pass through
  if (!authRequired) {
    return <>{children}</>
  }

  // Auth required but still loading
  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center h-screen bg-[var(--color-bg)]">
        <div className="space-y-4 w-64">
          <Skeleton variant="rect" height="40px" />
          <Skeleton variant="rect" height="20px" />
        </div>
      </div>
    )
  }

  // Auth required but not authenticated
  if (status !== 'authenticated') {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
