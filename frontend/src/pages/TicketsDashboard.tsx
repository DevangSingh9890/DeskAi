import { useEffect, useMemo, useState } from 'react'

import { TicketStatusCard } from '../components/TicketStatusCard'
import { TicketsTable } from '../components/TicketsTable'
import { getTicketErrorMessage, getTickets } from '../services/ticketService'
import type { Ticket, TicketPriority, TicketStatus } from '../types/ticket'

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

export function TicketsDashboard({ refreshKey }: TicketsDashboardProps) {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'All' | TicketStatus>('All')
  const [priorityFilter, setPriorityFilter] =
    useState<'All' | TicketPriority>('All')
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function loadTickets() {
      setIsLoading(true)
      try {
        const result = await getTickets()
        if (active) {
          setTickets(result)
          setError(null)
        }
      } catch (loadError: unknown) {
        if (active) setError(getTicketErrorMessage(loadError))
      } finally {
        if (active) setIsLoading(false)
      }
    }

    void loadTickets()
    return () => {
      active = false
    }
  }, [refreshKey])

  const filteredTickets = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return tickets.filter((ticket) => {
      const matchesQuery =
        !normalizedQuery ||
        [
          ticket.ticket_id,
          ticket.title,
          ticket.description,
          ticket.category,
          ticket.subcategory,
          ticket.assigned_group,
          ticket.resolution ?? '',
        ]
          .join(' ')
          .toLowerCase()
          .includes(normalizedQuery)
      const matchesStatus =
        statusFilter === 'All' || ticket.status === statusFilter
      const matchesPriority =
        priorityFilter === 'All' || ticket.priority === priorityFilter
      return matchesQuery && matchesStatus && matchesPriority
    })
  }, [tickets, query, statusFilter, priorityFilter])

  const selectedTicket =
    tickets.find((ticket) => ticket.ticket_id === selectedTicketId) ?? null
  const openCount = tickets.filter(
    (ticket) => ticket.status === 'Open' || ticket.status === 'In Progress',
  ).length
  const resolvedCount = tickets.filter(
    (ticket) => ticket.status === 'Resolved',
  ).length
  const highPriorityCount = tickets.filter(
    (ticket) => ticket.priority === 'High' || ticket.priority === 'Critical',
  ).length

  function toggleTicket(ticket: Ticket) {
    setSelectedTicketId((current) =>
      current === ticket.ticket_id ? null : ticket.ticket_id,
    )
  }

  return (
    <section className="tickets-dashboard" aria-labelledby="tickets-dashboard-title">
      <header className="tickets-dashboard-header">
        <div>
          <p className="ticket-eyebrow">SERVICE OPERATIONS</p>
          <h2 id="tickets-dashboard-title">Ticket Center</h2>
          <p>Review incidents created from approved AI recommendations.</p>
        </div>
        <span className="ticket-center-badge">
          <span aria-hidden="true">●</span> In-memory ticket service
        </span>
      </header>

      <div className="ticket-metric-grid" aria-label="Ticket metrics">
        <article className="ticket-metric-card">
          <span>All Tickets</span><strong>{tickets.length}</strong>
        </article>
        <article className="ticket-metric-card ticket-metric-card--open">
          <span>Open Tickets</span><strong>{openCount}</strong>
        </article>
        <article className="ticket-metric-card ticket-metric-card--resolved">
          <span>Resolved Tickets</span><strong>{resolvedCount}</strong>
        </article>
        <article className="ticket-metric-card ticket-metric-card--priority">
          <span>High Priority</span><strong>{highPriorityCount}</strong>
        </article>
      </div>

      <section className="tickets-list-panel" aria-label="All service desk tickets">
        <div className="tickets-list-header">
          <div>
            <h3>All Tickets</h3>
            <p>{filteredTickets.length} of {tickets.length} incidents</p>
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
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <label className="ticket-filter">
              <span className="sr-only">Filter by status</span>
              <select
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value as 'All' | TicketStatus)
                }
              >
                {ticketStatuses.map((status) => <option key={status}>{status}</option>)}
              </select>
            </label>
            <label className="ticket-filter">
              <span className="sr-only">Filter by priority</span>
              <select
                value={priorityFilter}
                onChange={(event) =>
                  setPriorityFilter(event.target.value as 'All' | TicketPriority)
                }
              >
                {priorities.map((priority) => <option key={priority}>{priority}</option>)}
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
          <TicketsTable
            tickets={filteredTickets}
            selectedTicketId={selectedTicketId}
            onSelect={toggleTicket}
          />
        )}
      </section>

      {selectedTicket && <TicketStatusCard ticket={selectedTicket} />}

      <aside className="admin-portal-placeholder">
        <span className="admin-placeholder-icon" aria-hidden="true">↗</span>
        <div>
          <p className="ticket-eyebrow">ADMIN PORTAL READY</p>
          <h3>Built for future service operations</h3>
          <p>
            Ticket updates, assignment, resolution workflows, and analytics can
            use the same ticket APIs when the admin portal is introduced.
          </p>
        </div>
        <span className="coming-soon-pill">Admin tools coming soon</span>
      </aside>
    </section>
  )
}
