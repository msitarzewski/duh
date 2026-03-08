import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { GridOverlay, ParticleField } from '@/components/shared'

export function Shell() {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true)

  return (
    <div className="h-screen flex overflow-hidden bg-[var(--color-bg)] isolate">
      <GridOverlay />
      <ParticleField count={20} />

      {/* Desktop sidebar */}
      {desktopSidebarOpen && (
        <div className="hidden lg:flex">
          <Sidebar onToggleSidebar={() => setDesktopSidebarOpen(false)} />
        </div>
      )}

      {/* Mobile sidebar overlay */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-[var(--z-overlay)] lg:hidden">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <div className="relative z-50 h-full w-56 animate-slide-in-left">
            <Sidebar onClose={() => setMobileSidebarOpen(false)} onToggleSidebar={() => setMobileSidebarOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 relative">
        <TopBar
          onMenuClick={() => {
            // Mobile: toggle mobile overlay; Desktop: reopen sidebar
            if (window.innerWidth >= 1024) {
              setDesktopSidebarOpen(true)
            } else {
              setMobileSidebarOpen(!mobileSidebarOpen)
            }
          }}
          showSidebarToggle={!desktopSidebarOpen}
        />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
