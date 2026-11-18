import { lazy, Suspense, useEffect, useState } from 'react'

import { getAdminAnalytics } from '../services/adminTicketService'
import { getTicketErrorMessage } from '../services/ticketService'
import type { TicketAnalytics } from '../types/ticket'

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
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
      {isLoading ? (
        <div className="tickets-loading" role="status">
          <span className="loading-spinner" /> Loading analytics…
        </div>
      ) : analytics ? (
        <Suspense fallback={<div className="tickets-loading" role="status">Loading charts…</div>}>
          <AnalyticsCharts analytics={analytics} />
        </Suspense>
      ) : null}
    </section>
  )
}
