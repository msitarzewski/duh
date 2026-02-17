import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Shell } from '@/components/layout'
import { ErrorBoundary } from '@/components/shared'
import {
  ConsensusPage,
  ThreadsPage,
  ThreadDetailPage,
  DecisionSpacePage,
  PreferencesPage,
  SharePage,
} from '@/pages'

export function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/share/:id" element={<SharePage />} />
          <Route element={<Shell />}>
            <Route path="/" element={<ConsensusPage />} />
            <Route path="/threads" element={<ThreadsPage />} />
            <Route path="/threads/:id" element={<ThreadDetailPage />} />
            <Route path="/space" element={<DecisionSpacePage />} />
            <Route path="/preferences" element={<PreferencesPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
