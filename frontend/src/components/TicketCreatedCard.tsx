import { displayTicketNumber, type Ticket } from '../types/ticket'

interface TicketCreatedCardProps {
  ticket: Ticket
}

export function TicketCreatedCard({ ticket }: TicketCreatedCardProps) {
  return (
    <section className="ticket-created-card" aria-label="Ticket created">
      <div className="ticket-created-heading">
        <span className="ticket-created-check" aria-hidden="true">✓</span>
        <div>
          <p>Ticket Created</p>
          <h4>{displayTicketNumber(ticket)}</h4>
        </div>
      </div>
      <dl className="ticket-created-details">
        <div>
          <dt>Status</dt>
          <dd><span className="ticket-status-pill ticket-status-pill--open">{ticket.status}</span></dd>
        </div>
        <div>
          <dt>Assigned Group</dt>
          <dd>{ticket.assigned_group}</dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd>{ticket.priority}</dd>
        </div>
      </dl>
    </section>
  )
}
