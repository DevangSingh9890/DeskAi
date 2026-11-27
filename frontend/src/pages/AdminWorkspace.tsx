import { useEffect, useState } from 'react'
import { AnalyticsDashboard } from '../components/AnalyticsDashboard'
import { HumanSupportQueue } from '../components/HumanSupportQueue'
import { getPerformanceStatus } from '../services/api'
import type { PerformanceStatus } from '../services/api'
import { KnowledgeBasePage } from './KnowledgeBasePage'
import { TicketsDashboard } from './TicketsDashboard'

type AdminModule = 'tickets' | 'analytics' | 'human-support' | 'knowledge-base'

const adminModules: Array<{ id: AdminModule; label: string; icon: string }> = [
  { id: 'tickets', label: 'Ticket Center', icon: '▤' },
  { id: 'analytics', label: 'Analytics', icon: '⌁' },
  { id: 'human-support', label: 'Human Support', icon: '◎' },
  { id: 'knowledge-base', label: 'Knowledge Base', icon: '▧' },
]

export function AdminWorkspace() {
  const [activeModule, setActiveModule] = useState<AdminModule>('tickets')
  const [performanceStatus, setPerformanceStatus] =
    useState<PerformanceStatus | null>(null)

  useEffect(() => {
    let active = true
    let timeoutId: number | undefined

    async function pollPerformanceStatus() {
      try {
        const status = await getPerformanceStatus()
        if (!active) return
        setPerformanceStatus(status)
        if (status.warming || status.warmup_status === 'not_started') {
          timeoutId = window.setTimeout(
            () => void pollPerformanceStatus(),
            1000,
          )
        }
      } catch {
        if (active) {
          timeoutId = window.setTimeout(
            () => void pollPerformanceStatus(),
            3000,
          )
        }
      }
    }

    void pollPerformanceStatus()
    return () => {
      active = false
      if (timeoutId !== undefined) window.clearTimeout(timeoutId)
    }
  }, [])

  return (
    <div className="dashboard-shell dashboard-shell--app admin-portal-shell">
      <header className="dashboard-header">
        <div className="dashboard-brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32">
              <path d="M16 3.5 19.1 12l8.4 4-8.4 3.1L16 28.5 12.9 19l-8.4-3 8.4-4L16 3.5Z" />
              <path d="m25.5 3 .9 2.6L29 6.5l-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6Z" />
            </svg>
          </span>
          <div className="dashboard-brand-copy">
            <h1>DeskAI</h1>
            <p>Support Operations</p>
          </div>
        </div>
        <div className="admin-portal-label">
          <span aria-hidden="true">▤</span>
          Admin Portal
        </div>
      </header>
      <div className="admin-workspace-layout">
        <aside className="admin-workspace-sidebar">
          <p className="admin-workspace-sidebar-label">WORKSPACE</p>
          <nav className="admin-workspace-nav" aria-label="Admin modules">
            {adminModules.map((module) => (
              <button
                className={activeModule === module.id
                  ? 'admin-workspace-nav-item admin-workspace-nav-item--active'
                  : 'admin-workspace-nav-item'}
                type="button"
                key={module.id}
                aria-current={activeModule === module.id ? 'page' : undefined}
                onClick={() => setActiveModule(module.id)}
              >
                <span aria-hidden="true">{module.icon}</span>
                {module.label}
              </button>
            ))}
          </nav>
          <div className="admin-workspace-sidebar-footer">
            <span aria-hidden="true">●</span>
            Support operations
          </div>
        </aside>
        <main
          className={`ticket-page-shell admin-workspace-main${activeModule === 'human-support' ? ' admin-workspace-main--human' : ''}`}
        >
          {activeModule === 'tickets' && <TicketsDashboard refreshKey={0} />}
          {activeModule === 'analytics' && <AnalyticsDashboard refreshKey={0} />}
          {activeModule === 'human-support' && <HumanSupportQueue />}
          {activeModule === 'knowledge-base' && (
            <KnowledgeBasePage performanceStatus={performanceStatus} />
          )}
        </main>
      </div>
    </div>
  )
}
