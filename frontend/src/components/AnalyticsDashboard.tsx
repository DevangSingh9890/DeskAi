import { lazy, Suspense, useEffect, useState } from 'react'

import {
  getAdminAnalytics,
  getAdminDashboard,
} from '../services/adminTicketService'
import { getTicketErrorMessage } from '../services/ticketService'
import {
  getHandoffErrorMessage,
  getHumanConversations,
} from '../services/handoffService'
import type {
  AdminDashboardSummary,
  TicketAnalytics,
} from '../types/ticket'

const AnalyticsCharts = lazy(() =>
  import('./AnalyticsCharts').then((module) => ({
    default: module.AnalyticsCharts,
  })),
)

interface AnalyticsDashboardProps {
  refreshKey: number
}

export function AnalyticsDashboard({ refreshKey }: AnalyticsDashboardProps) {
  const [analytics, setAnalytics] = useState<TicketAnalytics | null>(null)
  const [summary, setSummary] = useState<AdminDashboardSummary | null>(null)
  const [humanEscalationCount, setHumanEscalationCount] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [metricsError, setMetricsError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void getAdminAnalytics()
      .then((result) => {
        if (active) {
          setAnalytics(result)
          setError(null)
        }
      })
      .catch((loadError: unknown) => {
        if (active) setError(getTicketErrorMessage(loadError))
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })

    void Promise.allSettled([getAdminDashboard(), getHumanConversations()]).then(
      ([summaryResult, conversationsResult]) => {
        if (!active) return
        const failures: string[] = []
        if (summaryResult.status === 'fulfilled') {
          setSummary(summaryResult.value)
        } else {
          failures.push(getTicketErrorMessage(summaryResult.reason))
        }
        if (conversationsResult.status === 'fulfilled') {
          setHumanEscalationCount(conversationsResult.value.length)
        } else {
          failures.push(getHandoffErrorMessage(conversationsResult.reason))
        }
        setMetricsError(
          failures.length
            ? `Some dashboard metrics are unavailable: ${failures.join(' ')}`
            : null,
        )
      },
    )
    return () => {
      active = false
    }
  }, [refreshKey])

  return (
    <section className="analytics-dashboard" aria-labelledby="analytics-dashboard-title">
      <header className="analytics-dashboard-header">
        <div>
          <p className="ticket-eyebrow">SERVICE DESK INSIGHTS</p>
          <h2 id="analytics-dashboard-title">Operations analytics</h2>
          <p>Monitor ticket demand, priority, status, and team workload.</p>
        </div>
        {analytics && <span className="analytics-total">{analytics.total_tickets} total tickets</span>}
      </header>
      {error && <div className="ticket-page-error" role="alert">{error}</div>}
      {metricsError && <div className="ticket-page-error" role="status">{metricsError}</div>}
      {isLoading ? (
        <div className="tickets-loading" role="status">
          <span className="loading-spinner" /> Loading analytics…
        </div>
      ) : analytics ? (
        <>
          <div className="analytics-summary-grid" aria-label="Service desk analytics">
            <article><span>Total tickets</span><strong>{analytics.total_tickets}</strong><small>All recorded tickets</small></article>
            <article><span>Open tickets</span><strong>{analytics.open_tickets}</strong><small>Awaiting resolution</small></article>
            <article><span>Closed tickets</span><strong>{analytics.status_distribution.find((item) => item.name.toLowerCase() === 'closed')?.count ?? '—'}</strong><small>Closed by the service desk</small></article>
            <article><span>High priority</span><strong>{analytics.high_priority_tickets}</strong><small>Needs attention</small></article>
            <article><span>Human escalations</span><strong>{humanEscalationCount ?? '—'}</strong><small>Support conversations</small></article>
            <article><span>Knowledge documents</span><strong>{summary?.knowledge_documents ?? '—'}</strong><small>Available to DeskAI</small></article>
          </div>
          <Suspense fallback={<div className="tickets-loading" role="status">Loading charts…</div>}>
            <AnalyticsCharts analytics={analytics} />
          </Suspense>
        </>
      ) : null}
    </section>
  )
}
