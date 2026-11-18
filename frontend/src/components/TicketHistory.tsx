import type { TicketHistoryEntry } from '../types/ticket'

interface TicketHistoryProps {
  history: TicketHistoryEntry[]
}

const eventLabels: Record<string, string> = {
  ticket_created: 'Ticket Created',
  assignment_changed: 'Assigned',
  status_changed: 'Status Changed',
  comment_added: 'Comment Added',
}

function formatHistoryDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Date unavailable'
    : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

function describeEvent(event: TicketHistoryEntry): string {
  if (event.event_type === 'status_changed') {
    return `${event.old_value ?? 'Unknown'} → ${event.new_value ?? 'Unknown'}`
  }
  if (event.event_type === 'assignment_changed') {
    return `${event.old_value ?? 'Unassigned'} → ${event.new_value ?? 'Unassigned'}`
  }
  if (event.event_type === 'ticket_created') return event.new_value ?? 'Incident opened'
  return 'A comment was added to this ticket.'
}

function getEventLabel(event: TicketHistoryEntry): string {
  if (
    event.event_type === 'status_changed' &&
    (event.new_value === 'Resolved' || event.new_value === 'Closed')
  ) {
    return event.new_value
  }
  return eventLabels[event.event_type] ?? 'Ticket Updated'
}

export function TicketHistory({ history }: TicketHistoryProps) {
  return (
    <section className="drawer-section" aria-labelledby="ticket-history-title">
      <div className="drawer-section-heading">
        <div>
          <p className="ticket-eyebrow">AUDIT TRAIL</p>
          <h3 id="ticket-history-title">Ticket history</h3>
        </div>
      </div>
      {history.length ? (
        <ol className="ticket-history-list">
          {[...history].reverse().map((event) => (
            <li className="ticket-history-item" key={event.id}>
              <span className={`history-marker history-marker--${event.event_type}`} aria-hidden="true" />
              <div>
                <div className="ticket-history-meta">
                  <strong>{getEventLabel(event)}</strong>
                  <time dateTime={event.created_at}>{formatHistoryDate(event.created_at)}</time>
                </div>
                <p>{describeEvent(event)}</p>
                <span className="ticket-history-actor">by {event.actor}</span>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="drawer-muted">History will appear here as this ticket is updated.</p>
      )}
    </section>
  )
}
