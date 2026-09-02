import { useState, type ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { DemoBanner } from './DemoBanner'
import { ToastViewport } from './Toast'
import { useStatus } from '@/hooks/useStatus'

export const DISCLAIMER = 'Statistical analysis is not a guarantee of future results.'

export function Layout({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { status } = useStatus()

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onToggleSidebar={() => setSidebarOpen((v) => !v)} />
        <DemoBanner />
        <main className="flex-1 px-4 py-4 md:px-6" id="main">
          {children}
        </main>
        <footer className="border-t border-slate-200 bg-white px-4 py-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 md:px-6">
          <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
            <span className="font-medium">{status?.disclaimer || DISCLAIMER}</span>
            <span>
              Football Value Analytics
              {status ? ` · mode: ${status.app_mode} · tz: ${status.timezone}` : ''}
            </span>
          </div>
        </footer>
      </div>
      <ToastViewport />
    </div>
  )
}
