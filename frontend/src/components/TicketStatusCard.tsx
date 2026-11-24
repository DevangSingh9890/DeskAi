import { displayTicketNumber, type Ticket, type TicketStatusInfo } from '../types/ticket'

interface TicketStatusCardProps {
  ticket?: Ticket
  status?: TicketStatusInfo | null
}

export function TicketStatusCard({ ticket, status }: TicketStatusCardProps) {
  const ticketId = ticket ? displayTicketNumber(ticket) : status?.ticket_id
  if (!ticketId) return null

  const currentStatus = ticket?.status ?? status?.status ?? 'Unknown'

  return (
    <section className="ticket-status-card" aria-label={`Ticket ${ticketId} details`}>
      <div className="ticket-status-card-heading">
        <div>
          <p className="ticket-eyebrow">TICKET STATUS</p>
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
            {ticket.resolution && <div><dt>Resolution</dt><dd>{ticket.resolution}</dd></div>}
          </dl>
        </>
      )}
    </section>
  )
}
