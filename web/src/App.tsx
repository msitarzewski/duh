import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Shell } from '@/components/layout'
import { ErrorBoundary, ProtectedRoute } from '@/components/shared'
import {
  LoginPage,
  ResetPasswordPage,
  ConsensusPage,
  ThreadsPage,
  ThreadDetailPage,
  DecisionSpacePage,
  CalibrationPage,
  PreferencesPage,
  SharePage,
} from '@/pages'
import { useAuthStore } from '@/stores'

export function App() {
  const initialize = useAuthStore((s) => s.initialize)

  useEffect(() => {
    initialize()
  }, [initialize])

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/share/:id" element={<SharePage />} />
          <Route
            element={
              <ProtectedRoute>
                <Shell />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<ConsensusPage />} />
            <Route path="/threads" element={<ThreadsPage />} />
            <Route path="/threads/:id" element={<ThreadDetailPage />} />
            <Route path="/space" element={<DecisionSpacePage />} />
            <Route path="/calibration" element={<CalibrationPage />} />
            <Route path="/preferences" element={<PreferencesPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
