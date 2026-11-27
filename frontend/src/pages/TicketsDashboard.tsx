import { useEffect, useState } from 'react'

import { TicketDetailsDrawer } from '../components/TicketDetailsDrawer'
import { TicketsTable } from '../components/TicketsTable'
import {
  getAdminDashboard,
  getAdminTickets,
  type AdminTicketFilters,
} from '../services/adminTicketService'
import { getTicketErrorMessage } from '../services/ticketService'
import type {
  AdminDashboardSummary,
  Ticket,
  TicketPriority,
  TicketStatus,
} from '../types/ticket'

interface TicketsDashboardProps {
  refreshKey: number
}

const ticketStatuses: Array<'All' | TicketStatus> = [
  'All',
  'Open',
  'In Progress',
  'Resolved',
  'Closed',
]
const priorities: Array<'All' | TicketPriority> = [
  'All',
  'Critical',
  'High',
  'Medium',
  'Low',
]
const assignmentGroups = [
  'Network Support',
  'Hardware Support',
  'Email Support',
  'Identity & Access Management',
  'Security Team',
  'Database Team',
  'Cloud Support',
  'Messaging Team',
]
const pageSize = 10

export function TicketsDashboard({
  refreshKey,
}: TicketsDashboardProps) {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [summary, setSummary] = useState<AdminDashboardSummary | null>(null)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'All' | TicketStatus>('All')
  const [priorityFilter, setPriorityFilter] = useState<'All' | TicketPriority>('All')
  const [assignmentFilter, setAssignmentFilter] = useState('')
  const [sortBy, setSortBy] = useState<AdminTicketFilters['sortBy']>('created_at')
  const [sortOrder, setSortOrder] = useState<AdminTicketFilters['sortOrder']>('desc')
  const [page, setPage] = useState(1)
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null)
  const [localRefreshKey, setLocalRefreshKey] = useState(0)

  useEffect(() => {
    let active = true
    const filters: AdminTicketFilters = {
      search: query.trim(),
      status: statusFilter,
      priority: priorityFilter,
      assignmentGroup: assignmentFilter,
      sortBy,
      sortOrder,
      page,
      pageSize,
    }

    async function loadDashboard() {
      setIsLoading(true)
      const [ticketResult, dashboardResult] = await Promise.allSettled([
        getAdminTickets(filters),
        getAdminDashboard(),
      ])
      if (!active) return

      if (ticketResult.status === 'fulfilled') {
        setTickets(ticketResult.value.items)
        setTotal(ticketResult.value.total)
        setTotalPages(ticketResult.value.total_pages)
      } else {
        setError(getTicketErrorMessage(ticketResult.reason))
        setIsLoading(false)
        return
      }

      if (dashboardResult.status === 'fulfilled') {
        setSummary(dashboardResult.value)
        setError(null)
      } else {
        setError(
          `Ticket metrics are unavailable: ${getTicketErrorMessage(dashboardResult.reason)}`,
        )
      }
      if (active) {
        setIsLoading(false)
      }
    }

    void loadDashboard()
    return () => {
      active = false
    }
  }, [
    refreshKey,
    localRefreshKey,
    query,
    statusFilter,
    priorityFilter,
    assignmentFilter,
    sortBy,
    sortOrder,
    page,
  ])

  const selectedTicket =
    tickets.find((ticket) => ticket.ticket_id === selectedTicketId) ?? null

  function toggleTicket(ticket: Ticket) {
    setSelectedTicketId((current) =>
      current === ticket.ticket_id ? null : ticket.ticket_id,
    )
  }

  function changeSort(value: string) {
    const [nextSortBy, nextSortOrder] = value.split(':') as [
      AdminTicketFilters['sortBy'],
      AdminTicketFilters['sortOrder'],
    ]
    setSortBy(nextSortBy)
    setSortOrder(nextSortOrder)
    setPage(1)
  }

  return (
    <section className="tickets-dashboard" aria-labelledby="tickets-dashboard-title">
      <header className="tickets-dashboard-header">
        <div>
          <p className="ticket-eyebrow">SERVICE OPERATIONS</p>
          <h2 id="tickets-dashboard-title">Ticket Center</h2>
          <p>Review and manage incidents across your service desk.</p>
        </div>
        <span className="ticket-center-badge">
          <span aria-hidden="true">●</span> Connected to PostgreSQL
        </span>
      </header>

      <div className="ticket-center-content">
          <div className="ticket-metric-grid" aria-label="Ticket metrics">
            <article className="ticket-metric-card">
              <span>All Tickets</span><strong>{summary?.total_tickets ?? '—'}</strong>
            </article>
            <article className="ticket-metric-card ticket-metric-card--open">
              <span>Open Tickets</span><strong>{summary?.open_tickets ?? '—'}</strong>
            </article>
            <article className="ticket-metric-card ticket-metric-card--resolved">
              <span>Resolved Tickets</span><strong>{summary?.resolved_tickets ?? '—'}</strong>
            </article>
            <article className="ticket-metric-card ticket-metric-card--priority">
              <span>High Priority</span><strong>{summary?.high_priority_tickets ?? '—'}</strong>
            </article>
          </div>

          <section className="tickets-list-panel" aria-label="All service desk tickets">
            <div className="tickets-list-header">
              <div>
                <h3>All Tickets</h3>
                <p>{total ? `Showing ${Math.min((page - 1) * pageSize + 1, total)}–${Math.min(page * pageSize, total)} of ${total} incidents` : '0 incidents'}</p>
              </div>
              <div className="tickets-filters">
                <label className="tickets-search">
                  <span className="sr-only">Search tickets</span>
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <circle cx="8.5" cy="8.5" r="5.5" />
                    <path d="m13 13 4 4" />
                  </svg>
                  <input
                    type="search"
                    placeholder="Search tickets"
                    value={query}
                    onChange={(event) => {
                      setQuery(event.target.value)
                      setPage(1)
                    }}
                  />
                </label>
                <label className="ticket-filter">
                  <span className="sr-only">Filter by status</span>
                  <select
                    value={statusFilter}
                    onChange={(event) => {
                      setStatusFilter(event.target.value as 'All' | TicketStatus)
                      setPage(1)
                    }}
                  >
                    {ticketStatuses.map((status) => <option key={status}>{status}</option>)}
                  </select>
                </label>
                <label className="ticket-filter">
                  <span className="sr-only">Filter by priority</span>
                  <select
                    value={priorityFilter}
                    onChange={(event) => {
                      setPriorityFilter(event.target.value as 'All' | TicketPriority)
                      setPage(1)
                    }}
                  >
                    {priorities.map((priority) => <option key={priority}>{priority}</option>)}
                  </select>
                </label>
                <label className="ticket-filter">
                  <span className="sr-only">Filter by assignment group</span>
                  <select
                    value={assignmentFilter}
                    onChange={(event) => {
                      setAssignmentFilter(event.target.value)
                      setPage(1)
                    }}
                  >
                    <option value="">All groups</option>
                    {assignmentGroups.map((group) => <option key={group}>{group}</option>)}
                  </select>
                </label>
                <label className="ticket-filter">
                  <span className="sr-only">Sort tickets</span>
                  <select
                    value={`${sortBy}:${sortOrder}`}
                    onChange={(event) => changeSort(event.target.value)}
                  >
                    <option value="created_at:desc">Newest first</option>
                    <option value="created_at:asc">Oldest first</option>
                    <option value="updated_at:desc">Recently updated</option>
                    <option value="priority:desc">Priority</option>
                    <option value="status:asc">Status</option>
                    <option value="ticket_id:asc">Ticket number</option>
                  </select>
                </label>
              </div>
            </div>

            {error && <div className="ticket-page-error" role="alert">{error}</div>}
            {isLoading ? (
              <div className="tickets-loading" role="status">
                <span className="loading-spinner" /> Loading tickets…
              </div>
            ) : (
              <>
                <TicketsTable
                  tickets={tickets}
                  selectedTicketId={selectedTicketId}
                  onSelect={toggleTicket}
                />
                {totalPages > 1 && (
                  <nav className="ticket-pagination" aria-label="Ticket pages">
                    <span>Page {page} of {totalPages}</span>
                    <div>
                      <button type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>
                        Previous
                      </button>
                      <button type="button" disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}>
                        Next
                      </button>
                    </div>
                  </nav>
                )}
              </>
            )}
          </section>
      </div>

      {selectedTicket && (
        <TicketDetailsDrawer
          key={selectedTicket.ticket_id}
          ticket={selectedTicket}
          onClose={() => setSelectedTicketId(null)}
          onUpdated={() => {
            setPage(1)
            setLocalRefreshKey((current) => current + 1)
          }}
        />
      )}
    </section>
  )
}
