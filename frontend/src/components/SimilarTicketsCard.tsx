import type { SimilarTicket } from '../types/ticket'

interface SimilarTicketsCardProps {
  tickets?: SimilarTicket[] | null
}

export function SimilarTicketsCard({ tickets }: SimilarTicketsCardProps) {
  if (!tickets) return null

  return (
    <section className="similar-tickets-card">
      <div className="similar-tickets-heading">
        <div>
          <p className="ticket-eyebrow">RELATED</p>
          <h3>Similar tickets</h3>
        </div>
        <span>{tickets.length} found</span>
      </div>
      {tickets.length ? (
        <ul className="similar-ticket-list">
          {tickets.map((ticket) => (
            <li key={ticket.ticket_id}>
              <strong>{ticket.ticket_number ?? ticket.ticket_id}</strong>
              <p>{ticket.summary}</p>
              {ticket.resolution && (
                <p className="similar-ticket-resolution">
                  <strong>Resolution:</strong> {ticket.resolution}
                </p>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="similar-ticket-empty">No similar incidents were found.</p>
      )}
    </section>
  )
}
