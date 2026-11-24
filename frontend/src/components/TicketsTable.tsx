import { displayTicketNumber, type Ticket } from '../types/ticket'

interface TicketsTableProps {
  tickets: Ticket[]
  selectedTicketId: string | null
  onSelect: (ticket: Ticket) => void
}

export function TicketsTable({
  tickets,
  selectedTicketId,
  onSelect,
}: TicketsTableProps) {
  if (!tickets.length) {
    return (
      <div className="tickets-empty-state">
        <span aria-hidden="true">◇</span>
        <h3>No tickets match your filters</h3>
        <p>Try another search or filter, or create a ticket from a chat recommendation.</p>
      </div>
    )
  }

  return (
    <div className="tickets-table-wrap">
      <table className="tickets-table">
        <thead>
          <tr>
            <th scope="col">Ticket</th>
            <th scope="col">Issue</th>
            <th scope="col">Priority</th>
            <th scope="col">Status</th>
            <th scope="col">Assigned Group</th>
            <th scope="col">Updated</th>
            <th scope="col"><span className="sr-only">Details</span></th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => (
            <tr
              className={selectedTicketId === ticket.ticket_id ? 'tickets-table-row--selected' : ''}
              key={ticket.ticket_id}
            >
              <td><strong className="ticket-number">{displayTicketNumber(ticket)}</strong></td>
              <td>
                <span className="ticket-table-title">{ticket.title}</span>
                <span className="ticket-table-category">{ticket.category} · {ticket.subcategory}</span>
              </td>
              <td>
                <span className={`ticket-priority-pill ticket-priority-pill--${ticket.priority.toLowerCase()}`}>
                  {ticket.priority}
                </span>
              </td>
              <td>
                <span className={`ticket-status-pill ticket-status-pill--${ticket.status.toLowerCase().replace(/[^a-z]+/g, '-')}`}>
                  {ticket.status}
                </span>
              </td>
              <td>{ticket.assigned_group}</td>
              <td>{new Date(ticket.updated_at).toLocaleDateString()}</td>
              <td>
                <button
                  className="ticket-details-button"
                  type="button"
                  aria-expanded={selectedTicketId === ticket.ticket_id}
                  onClick={() => onSelect(ticket)}
                >
                  {selectedTicketId === ticket.ticket_id ? 'Close' : 'Details'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
