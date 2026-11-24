import { displayTicketNumber, type Ticket, type TicketStatusInfo } from '../types/ticket'

interface TicketStatusCardProps {
  ticket?: Ticket
  status?: TicketStatusInfo | null
}

function formatDate(value: string | null | undefined): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? null
    : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

export function TicketStatusCard({ ticket, status }: TicketStatusCardProps) {
  const ticketId = ticket ? displayTicketNumber(ticket) : status?.ticket_id
  if (!ticketId) return null

  const currentStatus = ticket?.status ?? status?.status ?? 'Unknown'
  const assignedGroup = ticket?.assigned_group ?? status?.assigned_group
  const updatedAt = formatDate(ticket?.updated_at ?? status?.updated_at)

  return (
    <section className="ticket-status-card" aria-label={`Ticket ${ticketId} details`}>
      <div className="ticket-status-card-heading">
        <div>
          <p className="ticket-eyebrow">INCIDENT DETAILS</p>
          <h3>{ticketId}</h3>
        </div>
        <span className={`ticket-status-pill ticket-status-pill--${currentStatus.toLowerCase().replace(/[^a-z]+/g, '-')}`}>
          {currentStatus}
        </span>
      </div>
      {ticket && (
        <>
          <h4>{ticket.title}</h4>
          <p className="ticket-description">{ticket.description}</p>
          <dl className="ticket-status-fields">
            <div><dt>Category</dt><dd>{ticket.category} / {ticket.subcategory}</dd></div>
            <div><dt>Priority</dt><dd>{ticket.priority}</dd></div>
            <div><dt>Created by</dt><dd>{ticket.created_by}</dd></div>
            {ticket.resolution && <div><dt>Resolution</dt><dd>{ticket.resolution}</dd></div>}
          </dl>
        </>
      )}
      {assignedGroup && <p className="ticket-status-assignment">Assigned to {assignedGroup}</p>}
      {updatedAt && <p className="ticket-status-updated">Last updated {updatedAt}</p>}
    </section>
  )
}
